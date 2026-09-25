"""
tests/test_sesli_yayin.py — "🎙️ Sesli Yayınla" ve Instabot biçimli haber önerisi (2026-09-26).

Kullanıcı kararları:
  * Düz "✅ Yayınla" eskisi gibi: seslendirme yok; YouTube/Facebook fon müzikli.
  * "🎙️ Sesli Yayınla" → "🎵 Fon müzikli" / "🔇 Fon müziksiz" → aynı zaman menüsü.
    Seslendirme yalnızca video kanallarına uygulanır; TikTok'u video kipine alır.
  * Haber önerisi Instabot'un öneri taslağıyla aynı: günde iki tur, tek mesajda
    en fazla beş numaralı başlık, çoklu seçim, 🔍 inceleme, "▶️ Hazırla (n)".
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from scripts import yayinla  # noqa: E402
from src import haber_oneri, telegram_bot  # noqa: E402


def _callbackler(menu):
    return [b["callback_data"] for satir in menu["inline_keyboard"] for b in satir]


class TestMenuler(unittest.TestCase):
    def test_sesli_yayinla_yayinla_ile_ayni_satirda(self):
        satirlar = telegram_bot.ana_menu(adet=3)["inline_keyboard"]
        satir = next(s for s in satirlar if any(b["callback_data"] == "yayin_menu:3" for b in s))
        self.assertEqual([b["callback_data"] for b in satir], ["yayin_menu:3", "ses_menu:3"])

    def test_ses_menusu_iki_secenek_ve_geri(self):
        cb = _callbackler(telegram_bot.ses_menusu(adet=3))
        for beklenen in ("ses_zaman:muzikli:3", "ses_zaman:muziksiz:3", "yayin_geri:3", "kanal:youtube"):
            self.assertIn(beklenen, cb)

    def test_sesli_zaman_menusu_yayinla_ile_ayni_yapi(self):
        duz = _callbackler(telegram_bot.yayin_zamani_menusu(adet=3))
        sesli = _callbackler(telegram_bot.sesli_yayin_zamani_menusu("muziksiz", adet=3))
        self.assertEqual(len(duz), len(sesli))
        self.assertIn("yayinla_ses:muziksiz", sesli)
        self.assertIn("yayinla_ses_sonra:muziksiz:240", sesli)
        self.assertEqual(sesli[-1], "ses_menu:3")  # geri: müzik seçimine döner
        self.assertIn("yayinla_ses:muzikli", _callbackler(telegram_bot.sesli_yayin_zamani_menusu("bozuk")))

    def test_callback_data_64_bayt_siniri(self):
        menuler = [telegram_bot.ana_menu(adet=10), telegram_bot.ses_menusu(adet=10),
                   telegram_bot.sesli_yayin_zamani_menusu("muziksiz", adet=10)]
        for menu in menuler:
            for cb in _callbackler(menu):
                self.assertLessEqual(len(cb.encode("utf-8")), 64, cb)


class TestYayinKipleri(unittest.TestCase):
    """yayinla.main hangi videoyu hangi kanala verir."""

    def setUp(self):
        self.gecici = KOK / "data/output/test_sesli_yayin"
        self.gecici.mkdir(parents=True, exist_ok=True)
        self.sessiz = self.gecici / "reels_1.mp4"
        self.muzikli = self.gecici / "reels_1_sesli.mp4"
        self.anlatimli = self.gecici / "reels_1_anlatim_sesli.mp4"
        for p in (self.sessiz, self.muzikli, self.anlatimli):
            p.write_bytes(b"video")
        self._kapi = patch("src.telegram_bot.yayin_kapisi", return_value=(True, []))
        self._kapi.start()

    def tearDown(self):
        self._kapi.stop()
        for p in self.gecici.glob("*"):
            p.unlink()
        self.gecici.rmdir()

    def _yayinla(self, hedef, anlatim_basarili=True, onay_videosu=None):
        haber = {
            "id": 901, "manset": "Silivri'de plan askıda", "ig_caption": "açıklama", "durum": "onay_bekliyor",
            "detay_metni": json.dumps({"format_turu": "dailybrief", "manset": "Silivri'de plan askıda",
                                       "spot": "Plan otuz gün askıda kalacak."}),
            "slayt_urlleri": json.dumps(["https://cdn.example.com/1.jpg", "https://cdn.example.com/2.jpg"]),
            "video_yolu": str(onay_videosu) if onay_videosu else None,
        }

        def anlatimli(slaytlar, veri=None, muzik=True, sonuc=None, **_):
            if sonuc is not None:
                sonuc["anlatim"] = anlatim_basarili
            return self.anlatimli

        def muzik_ekle(v, ses_seviyesi=0.2, muzik=True, **_):
            if Path(v).stem.endswith("_sesli") or not muzik:
                return Path(v)
            return self.muzikli

        cikti = io.StringIO()
        with (
            patch.object(yayinla.sys, "argv", ["yayinla.py", "--tur", "haber", "--id", "901", "--hedef", hedef]),
            patch.object(yayinla.db, "haber_getir", return_value=haber),
            patch.object(yayinla.db, "haber_guncelle"),
            patch.object(yayinla.db, "onay_istegi_sonuclandir"),
            patch.object(yayinla.video, "slaytlardan_reels_uret", return_value=self.sessiz) as duz_video,
            patch.object(yayinla.ses, "anlatimli_video_uret", side_effect=anlatimli) as sesli_video,
            patch.object(yayinla.ses, "sesli_video_hazirla", side_effect=muzik_ekle) as muzik,
            patch.object(yayinla.youtube, "shorts_yukle", return_value={"durum": True, "url": "https://youtu.be/x"}) as yt,
            patch.object(yayinla.tiktok, "video_yukle", return_value={"durum": True}) as tt_video,
            patch.object(yayinla.tiktok, "foto_yayinla", return_value={"durum": True}) as tt_foto,
            patch.object(yayinla.telegram_bot, "mesaj_gonder"),
            patch.object(yayinla.telegram_bot, "video_gonder") as tg_video,
            patch.object(yayinla.telegram_bot, "sonucu_yaz"),
            contextlib.redirect_stdout(cikti),
        ):
            yayinla.main()
        satir = next(s for s in cikti.getvalue().splitlines() if s.startswith("POSTEDM_SONUC="))
        rapor = "\n".join(json.loads(satir.split("=", 1)[1])["rapor"])
        return dict(duz_video=duz_video, sesli_video=sesli_video, muzik=muzik, yt=yt, tt_video=tt_video,
                    tt_foto=tt_foto, tg_video=tg_video, rapor=rapor)

    def test_duz_yayin_eskisi_gibi_seslendirmesiz_ve_fon_muzikli(self):
        s = self._yayinla("youtube,tiktok")
        s["sesli_video"].assert_not_called()
        s["duz_video"].assert_called_once()
        self.assertEqual(s["yt"].call_args[0][0], self.muzikli)  # YouTube fon müzikli
        s["tt_foto"].assert_called_once()  # TikTok eskisi gibi fotoğraf karuseli
        s["tt_video"].assert_not_called()
        self.assertNotIn("Seslendirme", s["rapor"])

    def test_sesli_muzikli_butun_video_kanallarinda(self):
        s = self._yayinla("youtube,tiktok,ses_muzikli")
        self.assertTrue(s["sesli_video"].call_args.kwargs["muzik"])
        s["duz_video"].assert_not_called()
        self.assertEqual(s["yt"].call_args[0][0], self.anlatimli)
        self.assertEqual(s["tt_video"].call_args[0][0], self.anlatimli)  # TikTok video kipine geçer
        s["tt_foto"].assert_not_called()
        self.assertEqual(s["tg_video"].call_args[0][0], self.anlatimli)  # kayıt için gruba da gelir
        self.assertIn("Seslendirme (fon müzikli):</b> Eklendi", s["rapor"])

    def test_sesli_muziksiz_hic_muzik_eklenmez(self):
        s = self._yayinla("youtube,ses_muziksiz")
        self.assertFalse(s["sesli_video"].call_args.kwargs["muzik"])
        self.assertFalse(s["muzik"].call_args.kwargs["muzik"])
        self.assertEqual(s["yt"].call_args[0][0], self.anlatimli)
        self.assertIn("fon müziksiz", s["rapor"])

    def test_seslendirme_duserse_raporda_saklanmaz(self):
        s = self._yayinla("youtube,ses_muzikli", anlatim_basarili=False)
        self.assertIn("Seslendirme:</b> Üretilemedi", s["rapor"])
        s["yt"].assert_called_once()  # kanallar yine yayınlanır; yayın "başarısız" sayılmaz

    def test_seslendirme_satiri_kanal_sonucu_sayilmaz(self):
        """✓/✗ kanal sonucudur: seslendirme satırı yayını başarılı/başarısız göstermemeli."""
        for basarili in (True, False):
            s = self._yayinla("youtube,ses_muzikli", anlatim_basarili=basarili)
            satir = next(r for r in s["rapor"].splitlines() if "Seslendirme" in r)
            self.assertNotIn("✓", satir)
            self.assertNotIn("✗", satir)

    def test_sesli_yayinda_onaydaki_seslendirmesiz_video_kullanilmaz(self):
        s = self._yayinla("youtube,ses_muzikli", onay_videosu=self.muzikli)
        s["sesli_video"].assert_called_once()
        self.assertEqual(s["yt"].call_args[0][0], self.anlatimli)


def _haber(i, **ek):
    h = {"id": 300 + i, "orijinal_baslik": f"Konut kredisinde {i}. düzenleme yürürlüğe girdi",
         "orijinal_url": f"https://emlakkulisi.com/haber-{i}", "orijinal_ozet": "Bankalar oranları güncelledi. Ayrıntı.",
         "kaynak": "Emlakkulisi", "kategori": "S4", "onem_puani": 8, "yayin_tarihi": "2026-09-25T09:00:00+00:00"}
    h.update(ek)
    return h


class TestOneriListesi(unittest.TestCase):
    def test_instabot_bicimi(self):
        metin, klavye = haber_oneri.oneri_listesi_mesaji([_haber(i) for i in range(7)])
        self.assertTrue(metin.startswith("📰 <b>Günün Öne Çıkan Haber Adayları</b>"))
        satirlar = klavye["inline_keyboard"]
        self.assertEqual([b["text"] for b in satirlar[0]], ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"])  # en fazla beş
        self.assertEqual([b["callback_data"] for b in satirlar[1]], [f"incele:{300 + i}" for i in range(5)])
        self.assertEqual(satirlar[2], [{"text": "▶️ Hazırla (0)", "callback_data": "hazirla_secilenler"}])
        self.assertEqual(satirlar[3], [{"text": "❌ Hiçbiri", "callback_data": "oneri_gec"}])
        self.assertEqual(metin.count("🗓"), 5)  # her haberin tarihi yazar
        self.assertIn("/incele_300", metin)
        self.assertIn('href="https://emlakkulisi.com/haber-0"', metin)
        self.assertIn("💬 <i>Bankalar oranları güncelledi.</i>", metin)

    def test_uzun_basliklarla_bile_telegram_sinirinda(self):
        uzun = [_haber(i, orijinal_baslik="Ç" * 300, orijinal_ozet="Ş" * 2000) for i in range(5)]
        metin, _ = haber_oneri.oneri_listesi_mesaji(uzun)
        self.assertLess(len(metin), 4096)

    def test_baslikla_ayni_ozet_tekrarlanmaz(self):
        metin, _ = haber_oneri.oneri_listesi_mesaji([_haber(1, orijinal_ozet="Konut kredisinde 1. düzenleme yürürlüğe girdi")])
        self.assertNotIn("💬", metin)

    def test_zararli_baslik_kacirilir(self):
        metin, _ = haber_oneri.oneri_listesi_mesaji([_haber(1, orijinal_baslik="<b>kalın</b> & <script>",
                                                             orijinal_url='https://x.com/"><script>')])
        self.assertNotIn("<script>", metin)
        self.assertIn("&lt;b&gt;kalın&lt;/b&gt; &amp;", metin)

    def test_secilenler_sirayla_ve_bir_kez(self):
        with patch.object(haber_oneri, "haberden_icerige", return_value=True) as tek:
            self.assertEqual(haber_oneri.haberlerden_icerige([272, 273, 272]), 2)
        self.assertEqual([c.args[0] for c in tek.call_args_list], [272, 273])

    def test_incele_haber_onerisine_haber_ayrintisi_icerige_icerik_karti(self):
        """🔍 / /incele_272 mevcut inceleme yolundan gider; ham habere "Şimdi Yayınla" sunulmaz."""
        with patch.object(telegram_bot.db, "haber_getir", return_value=_haber(1, durum="onerildi")):
            metin, klavye = telegram_bot.icerik_incele_karti(301)
        self.assertIn("🔍 <b>Haber #301</b>", metin)
        self.assertEqual(_callbackler(klavye), ["haber_uret:301"])

        icerik = _haber(1, durum="onay_bekliyor", detay_metni=json.dumps({"spot": "s"}), manset="Manşet")
        with patch.object(telegram_bot.db, "haber_getir", return_value=icerik):
            metin, klavye = telegram_bot.icerik_incele_karti(301)
        self.assertIn("İÇERİK İNCELEME", metin)

        with patch.object(telegram_bot.db, "haber_getir", return_value=_haber(1, durum="yayinlandi")):
            _, klavye = telegram_bot.icerik_incele_karti(301)
        self.assertNotIn("haber_uret:301", _callbackler(klavye))

    def test_hazirla_virgullu_kimlik_listesi(self):
        from scripts import hazirla
        with patch.object(sys, "argv", ["hazirla.py", "--haberden", "272,273"]), \
             patch("src.haber_oneri.haberlerden_icerige") as cok:
            hazirla.main()
        cok.assert_called_once_with([272, 273])


if __name__ == "__main__":
    unittest.main()
