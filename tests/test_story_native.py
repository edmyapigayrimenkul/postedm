"""
tests/test_story_native.py — Story native 9:16 kapak (2026-10-07).

Kullanıcı bildirimi: "story de 4:5'in üstü kesik hali gidiyo, 9:16 versiyonu gitmeli". Story, onaylanan
4:5 besleme kapağını alıp `video._cercevele_9_16` ile 9:16'ya yerleştiriyordu; tam boy fotoğraflı ana kare
hiç gitmiyordu. Artık içerik, Reels videosundaki gibi doğrudan 1080x1920 çizilir; onaylı kapağı
çerçevelemek yalnızca yedek yoldur.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from scripts import yayinla
from src.yayin.kanallar import story as story_modulu
from src import haber_tasarim

REF = "99901"
HABER_DETAY = {
    "format_turu": "dailybrief", "bicim": "B5", "kategori_kodu": "SEKTOREL_HABER_VE_ANALIZ",
    "manset": "Konut kredisi faizleri geriledi", "spot": "Merkez Bankası politika faizini sabit tuttu.",
    "kanca": "Faizler düşüyor mu", "detay_yazisi": "Merkez Bankası politika faizini yüzde 40'ta sabit tuttu.\n\nKarar piyasada olumlu karşılandı.",
    "kaynak": "Bloomberg HT",
}
SOZLUK = {"format_turu": "sozluk", "kategori_kodu": "S3", "terim": "İFRAZ",
          "tanim_metni": "Bir parselin, imar planına uygun olarak birden fazla parsele bölünmesidir.",
          "puf_maddeleri": ["İmar durumu alın.", "Asgari büyüklüğü sorgulayın.", "Yola cephe şartını kontrol edin."]}
NET_CEVAP = {"format_turu": "net_cevap", "kategori_kodu": "S2", "soru": "Kira ödenmezse ev sahibi hemen dava açabilir mi",
             "net_cevap": "Hayır. Önce yazılı ihtar gerekir.", "aciklama": "Kanun ödeme için süre tanır."}
NEDIR = {"format_turu": "nedir_dogrusu", "kategori_kodu": "S1",
         "yanlis_metin": "Hisseli tapuda ortak, yıllar sonra bile hisseyi geri alabilir.",
         "dogru_metin": "Önalım hakkı süre geçince düşer.", "altin_kural": "Satıştan sonra noter bildirimi yaptırın."}
VAKA = {"format_turu": "vaka", "kategori_kodu": "S1", "manset": "Ortağına haber vermeden hissesini sattı",
        "olay_detay": "Ayşe Hanım hisseli tarladaki payını üçüncü bir kişiye sattı.",
        "yargitay_hukmu": "Diğer paydaşlar payı rayiç değerle alabilir.", "cikarilacak_ders": "Noter bildirimi süreyi başlatır."}
B1 = {"bicim": "B1", "kategori_kodu": "S1", "manset_parca_1": "Tapuda", "manset_vurgu": "şerhe", "manset_parca_2": "dikkat",
      "slayt_2_detay": {"kartlar": [{"baslik": "Şerh nedir", "aciklama": "Tapu kaydına işlenen kısıtlamadır."}]},
      "slayt_3_cozum": {"baslik_vurgu": "NE YAPMALI", "maddeler": [
          {"no": "01", "baslik": "Kaydı oku", "aciklama": "Beyanlar hanesine bak."}]},
      "slayt_4_cta": {"slogan_parca_1": "Kaydet", "slogan_vurgu": "EDM", "aciklama": "x", "kaydet_metni": "Kaydet"}}
ILAN = {"id": 1, "baslik": "Silivri'de satılık arsa", "fiyat": 1500000, "metrekare": 500, "konum": "Silivri",
        "mahalle": "Selimpaşa", "kategori": "arsa", "ilan_no": "123", "tur": "arsa", "aciklama": "Yola cephe imarlı arsa.",
        "foto_url": None}


def _foto() -> Image.Image:
    return Image.new("RGB", (900, 600), (60, 90, 140))


class _Temizlik(unittest.TestCase):
    def tearDown(self):
        for dizin in (KOK / "data/output/gonderiler", KOK / "data/output"):
            for p in dizin.glob(f"*{REF}*"):
                if p.is_file():
                    p.unlink(missing_ok=True)


class TestNativeKapak(_Temizlik):
    def _uret(self, detay, haber=None, tur="haber", ilan=None):
        with patch.object(haber_tasarim, "fotografi_sec", return_value=_foto()):
            return yayinla.story_kapagi_uret(detay, haber, REF, tur, ilan)

    def test_her_format_1080x1920_native_uretir(self):
        vakalar = {"haber": HABER_DETAY, "sozluk": SOZLUK, "net_cevap": NET_CEVAP,
                   "nedir_dogrusu": NEDIR, "vaka": VAKA, "b1_carousel": B1,
                   "reels_formati_b1": {**B1, "format_turu": "reels"}}
        for ad, detay in vakalar.items():
            with self.subTest(format=ad):
                yol = self._uret(detay)
                self.assertIsNotNone(yol, ad)
                with Image.open(yol) as im:
                    self.assertEqual(im.size, (1080, 1920), ad)

    def test_ilan_kapagi_9_16(self):
        yol = self._uret({}, tur="ilan", ilan=ILAN)
        self.assertIsNotNone(yol)
        try:
            with Image.open(yol) as im:
                self.assertEqual(im.size, (1080, 1920))
        finally:
            Path(yol).unlink(missing_ok=True)

    def test_haberin_onaylanan_fotografi_foto_yolu_olarak_verilir(self):
        haber = {"gorsel_url": "https://haber.example/onayli.jpg"}
        with patch.object(haber_tasarim, "fotografi_sec", return_value=_foto()) as sec:
            yayinla.story_kapagi_uret(dict(HABER_DETAY), haber, REF, "haber")
        self.assertEqual(sec.call_args[0][1], "https://haber.example/onayli.jpg")
        self.assertEqual(sec.call_args[0][0]["id"], REF)  # sabitlenen dosya adı haber kimliğini taşır

    def test_kayitta_kendi_fotografi_varsa_ezilmez(self):
        detay = {**HABER_DETAY, "foto_yolu": "/tmp/kendi.jpg"}
        with patch.object(haber_tasarim, "fotografi_sec", return_value=_foto()) as sec:
            yayinla.story_kapagi_uret(detay, {"gorsel_url": "https://haber.example/baska.jpg"}, REF, "haber")
        self.assertEqual(sec.call_args[0][1], "/tmp/kendi.jpg")

    def test_girdi_degistirilmez(self):
        detay = dict(HABER_DETAY)
        self._uret(detay, {"gorsel_url": "https://x/y.jpg"})
        self.assertEqual(detay, HABER_DETAY)

    def test_tanimsiz_ya_da_bos_icerik_none(self):
        self.assertIsNone(yayinla.story_kapagi_uret({}, None, REF, "haber"))
        self.assertIsNone(yayinla.story_kapagi_uret(None, None, REF, "haber"))
        self.assertIsNone(yayinla.story_kapagi_uret({"format_turu": "bilinmeyen_bicim"}, None, REF, "haber"))

    def test_cizici_hata_verirse_none_yedek_yol_devralir(self):
        with patch("src.yeni_formatlar.slaytlari_uret", side_effect=RuntimeError("çizim patladı")):
            self.assertIsNone(yayinla.story_kapagi_uret(dict(HABER_DETAY), None, REF, "haber"))


class TestStoryAkisi(_Temizlik):
    """`main` içindeki Story kanalı: native kapak varsa o gider, onaylı 4:5 kapak çerçevelenmez."""

    def setUp(self):
        self.dummy = KOK / f"data/output/test_story_{REF}.jpg"
        self.dummy.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1080, 1350), "blue").save(self.dummy, "JPEG")
        self.native = KOK / f"data/output/test_story_native_{REF}.jpg"
        Image.new("RGB", (1080, 1920), (200, 20, 30)).save(self.native, "JPEG")
        self._kapi = patch("src.telegram.akislar.kapi.yayin_kapisi", return_value=(True, []))
        self._kapi.start()

    def tearDown(self):
        self._kapi.stop()
        self.dummy.unlink(missing_ok=True)
        self.native.unlink(missing_ok=True)
        super().tearDown()

    def _yayinla(self, story_kapagi):
        haber = {
            "id": int(REF), "manset": "Test", "ig_caption": "Açıklama", "gorsel_url": "https://haber.example/onayli.jpg",
            "detay_metni": json.dumps(HABER_DETAY),
            "slayt_yollari": json.dumps([str(self.dummy), str(self.dummy)]),
            "slayt_urlleri": json.dumps(["https://cdn.com/1.jpg", "https://cdn.com/2.jpg"]),
        }
        yuklenen = []

        def yukle(yol, *a, **k):
            with Image.open(yol) as im:
                yuklenen.append((im.size, im.convert("RGB").getpixel((540, 960))))
            return "https://cdn.example.com/story.jpg"

        cerceve = MagicMock(side_effect=yayinla.video._cercevele_9_16)
        with (
            patch.object(yayinla.sys, "argv", ["yayinla.py", "--tur", "haber", "--id", REF, "--hedef", "story"]),
            patch.object(yayinla.db, "haber_getir", return_value=haber),
            patch.object(yayinla.db, "haber_guncelle"),
            patch.object(yayinla.db, "onay_istegi_sonuclandir"),
            patch.object(story_modulu, "story_kapagi_uret", return_value=story_kapagi) as native,
            patch.object(yayinla.video, "_cercevele_9_16", cerceve),
            patch.object(yayinla.upload_image, "gorsel_yukle", side_effect=yukle),
            patch.object(yayinla.instagram, "story_yayinla", return_value="ig-s") as ig_story,
            patch.object(yayinla.facebook, "story_yayinla", return_value="fb-s") as fb_story,
            patch("src.telegram.istemci.mesaj_gonder"),
            patch("src.telegram.sonuc_mesaji.sonucu_yaz"),
            patch("requests.get", return_value=MagicMock(status_code=200, content=self.dummy.read_bytes())),
        ):
            yayinla.main()
        return native, cerceve, yuklenen, ig_story, fb_story

    def test_native_kapak_varsa_onayli_4_5_cerceveye_girmez(self):
        native, cerceve, yuklenen, ig_story, fb_story = self._yayinla(self.native)
        native.assert_called_once()
        cerceve.assert_not_called()
        boyut, orta = yuklenen[-1]  # önceki yüklemeler besleme slaytlarının onarımı; sonuncusu Story
        self.assertEqual(boyut, (1080, 1920))
        self.assertGreater(orta[0], 150)  # native dosyanın kırmızısı: onaylı mavi 4:5 kapak DEĞİL
        self.assertLess(orta[2], 100)
        ig_story.assert_called_once()
        fb_story.assert_called_once()

    def test_native_uretilemezse_onayli_kapak_yedek_olarak_cerceve(self):
        native, cerceve, yuklenen, ig_story, _ = self._yayinla(None)
        native.assert_called_once()
        cerceve.assert_called_once()  # eski yol: story yine de gider, boş kalmaz
        boyut, orta = yuklenen[-1]
        self.assertEqual(boyut, (1080, 1920))
        self.assertGreater(orta[2], orta[0])  # onaylı mavi kapaktan türedi
        ig_story.assert_called_once()

    def test_story_ve_threads_es_zamanli_cizim_race_condition_olusturmaz(self):
        """Threads (4:5 besleme) ve Story (9:16) aynı anda ThreadPool'da çalışsa bile
        _tuval_lock sayesinde tuval boyutları birbirini ezmez; Story her zaman 1080x1920 kalır.
        """
        import concurrent.futures
        from src import make_image

        def _threads_gorevi():
            with patch.object(haber_tasarim, "fotografi_sec", return_value=_foto()):
                return make_image.otorite_gonderi_slaytlari_uret(dict(B1), cikti_onek=f"th_{REF}", olcu="besleme")

        def _story_gorevi():
            with patch.object(haber_tasarim, "fotografi_sec", return_value=_foto()):
                return yayinla.story_kapagi_uret(dict(B1), None, f"{REF}_st", "reels")

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f_th = ex.submit(_threads_gorevi)
            f_st = ex.submit(_story_gorevi)
            th_yollar = f_th.result()
            st_yol = f_st.result()

        self.assertIsNotNone(st_yol)
        with Image.open(st_yol) as im_st:
            self.assertEqual(im_st.size, (1080, 1920), "Story tuvali Threads tarafından 1350'ye ezilmemeli")
        with Image.open(th_yollar[0]) as im_th:
            self.assertEqual(im_th.size, (1080, 1350), "Threads tuvali 1350 kalmalı")


if __name__ == "__main__":
    unittest.main()
