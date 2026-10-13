"""
tests/test_yayin_paketi.py — src/yayin/ paketinin birim testleri (2026-10-13).

Davranışın bütünü tests/test_yayinla_altin.py'de donduruldu; burada paketin kendi sözleşmeleri sınanır:
kanal seçim kuralları, yapısal başarı/hata durumu, dağıtım motorunun hata yalıtımı ve ilerleme göstergesi.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import concurrent.futures
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import telegram_bot
from src.yayin import dagitim, hedef
from src.yayin.baglam import YayinBaglami
from src.yayin.ilerleme import Ilerleme
from src.yayin.sonuc import BILGI, HATA, YAYINDA, DagitimSonucu, KanalSonucu, Satir


def baglam(hedef_ham: str, tur: str = "haber") -> YayinBaglami:
    b = YayinBaglami(istek=hedef.istek_olustur(tur, "1", hedef_ham))
    hedef.bayraklari_belirle(b)
    return b


class TestKanalSecimi(unittest.TestCase):
    def setUp(self):
        self._li = patch("src.linkedin.kullanilabilir_mi", return_value=False)
        self._tw = patch("src.twitter.kullanilabilir_mi", return_value=False)
        self._li.start()
        self._tw.start()

    def tearDown(self):
        self._li.stop()
        self._tw.stop()

    def test_hepsi_haber_instagram_besleme_reels_degil(self):
        self.assertEqual(hedef.kanal_listesi(baglam("hepsi")),
                         ["tiktok", "instagram", "story", "threads", "facebook", "youtube"])

    def test_hepsi_reels_turunde_instagram_yerine_reels(self):
        self.assertEqual(hedef.kanal_listesi(baglam("hepsi", tur="reels")),
                         ["tiktok", "reels", "story", "threads", "facebook_reels", "youtube"])

    def test_reels_secilince_instagram_besleme_kapanir(self):
        b = baglam("reels,ig")
        self.assertTrue(b.paylas_reels)
        self.assertFalse(b.paylas_ig)
        self.assertEqual(hedef.kanal_listesi(b), ["reels"])

    def test_facebook_reels_modunda_video_kanalidir(self):
        self.assertEqual(hedef.kanal_listesi(baglam("reels,fb")), ["reels", "facebook_reels"])
        self.assertEqual(hedef.kanal_listesi(baglam("fb")), ["facebook"])

    def test_takma_adlar(self):
        self.assertEqual(hedef.kanal_listesi(baglam("tt,th,yt")), ["tiktok", "threads", "youtube"])
        self.assertEqual(hedef.kanal_listesi(baglam("shorts")), ["youtube"])

    def test_video_gerekliligi(self):
        self.assertFalse(baglam("ig,threads").video_lazim)
        self.assertTrue(baglam("yt").video_lazim)
        self.assertTrue(baglam("reels").video_lazim)
        self.assertFalse(baglam("fb").video_lazim)
        self.assertTrue(baglam("fb,reels").video_lazim)
        self.assertTrue(baglam("fb,ses_muzikli").video_lazim)
        self.assertTrue(baglam("tt,ses_muziksiz").video_lazim)
        self.assertFalse(baglam("tt").video_lazim)

    def test_ses_modu(self):
        self.assertEqual(baglam("yt,ses_muzikli").ses_modu, "muzikli")
        self.assertEqual(baglam("yt,ses_muziksiz").ses_modu, "muziksiz")
        self.assertIsNone(baglam("yt").ses_modu)

    def test_linkedin_acik_istenirse_ve_hepsi_icinde_yalniz_yapilandirildiysa(self):
        self.assertEqual(hedef.kanal_listesi(baglam("li")), ["linkedin"])
        self.assertNotIn("linkedin", hedef.kanal_listesi(baglam("hepsi")))
        with patch("src.linkedin.kullanilabilir_mi", return_value=True):
            self.assertIn("linkedin", hedef.kanal_listesi(baglam("hepsi")))

    def test_twitter_hicbir_hedefle_secilmez_eski_davranis(self):
        """X işçisi yazılı ama eskiden de seçilmiyordu; açmak ayrı karar (src/yayin/kanallar/tw.py)."""
        with patch("src.twitter.kullanilabilir_mi", return_value=True):
            self.assertEqual(hedef.kanal_listesi(baglam("x,twitter")), [])
            self.assertNotIn("twitter", hedef.kanal_listesi(baglam("hepsi")))

    def test_hedef_ayristirma_bosluk_ve_buyuk_harf(self):
        istek = hedef.istek_olustur("haber", "5", " IG , Threads ,, ")
        self.assertEqual(istek.hedefler, {"ig", "threads"})
        self.assertTrue(istek.hedef_mi("ig"))
        self.assertFalse(istek.hedef_mi("fb"))


class TestSonuc(unittest.TestCase):
    def test_basari_ve_hata_satir_durumundan_gelir_metinden_degil(self):
        """Eski kod "✓"/"✗" karakteri arıyordu; metne yazılan her şey durumu bozabilirdi."""
        k = KanalSonucu("instagram", "x")
        k.ekle("Hiçbir işaret yok ama yayında", YAYINDA)
        k.ekle("✓ işaretli ama hata", HATA)
        s = DagitimSonucu(kanallar={"instagram": k})
        self.assertTrue(s.herhangi_yayinda)
        self.assertTrue(s.hata_var)

    def test_bilgi_satiri_ne_basari_ne_hata(self):
        """TikTok taslağı / elle paylaşılacak Reels videosu: eskiden ne ✓ ne ✗ taşırdı; durum makinesi başarı saymazdı."""
        k = KanalSonucu("tiktok", "📥 Taslak Yüklendi")
        k.ekle("🎵 TikTok: Taslak 📥", BILGI)
        s = DagitimSonucu(kanallar={"tiktok": k}, on_satirlar=[Satir("🎙️ Seslendirme", BILGI)])
        self.assertFalse(s.herhangi_yayinda)
        self.assertFalse(s.hata_var)
        self.assertEqual([x.metin for x in s.satirlar], ["🎙️ Seslendirme", "🎵 TikTok: Taslak 📥"])

    def test_satir_sirasi_on_kanallar_son(self):
        k = KanalSonucu("youtube", "x")
        k.ekle("kanal", YAYINDA)
        s = DagitimSonucu(kanallar={"youtube": k}, on_satirlar=[Satir("on", BILGI)], son_satirlar=[Satir("son", BILGI)])
        self.assertEqual([x.metin for x in s.satirlar], ["on", "kanal", "son"])

    def test_kimlik_ve_ham_erisimi(self):
        fb = KanalSonucu("facebook_reels", "x", kimlik="FB9")
        yt = KanalSonucu("youtube", "x", ham={"durum": True, "video_id": "V1"})
        reels = KanalSonucu("reels", "x", ham={"video_telegrama_gitti": True})
        s = DagitimSonucu(kanallar={"facebook_reels": fb, "youtube": yt, "reels": reels})
        self.assertEqual(s.fb_id, "FB9")
        self.assertEqual(s.yt_res["video_id"], "V1")
        self.assertTrue(s.video_telegrama_gitti)
        self.assertIsNone(s.ig_id)
        self.assertEqual(s.tt_res, {})


class SiraliYurutucu:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def submit(self, fn, *a, **k):
        f = concurrent.futures.Future()
        try:
            f.set_result(fn(*a, **k))
        except BaseException as e:  # noqa: BLE001
            f.set_exception(e)
        return f


class TestDagitim(unittest.TestCase):
    def _isci(self, ad, satir=None, durum=YAYINDA, hata=None):
        def isci(b, ilerleme):
            if hata:
                raise hata
            s = KanalSonucu(ad, "✅ Yayında", kimlik=f"{ad}-id")
            s.ekle(satir or f"{ad} tamam", durum)
            return s
        return isci

    def test_rapor_sirasi_kanal_sirasi_ve_bir_isci_coksa_digerleri_yasar(self):
        kayit = {"a": self._isci("a"), "b": self._isci("b", hata=RuntimeError("beklenmedik")), "c": self._isci("c")}
        b = baglam("ig")
        ilerleme = Ilerleme(["a", "b", "c"], None, "başlık")
        with patch.object(dagitim, "KANALLAR", kayit), patch("concurrent.futures.ThreadPoolExecutor", SiraliYurutucu):
            sonuc = dagitim.dagit(b, ["a", "b", "c"], ilerleme)
        self.assertEqual(list(sonuc.kanallar), ["a", "b", "c"])
        metinler = [s.metin for s in sonuc.satirlar]
        self.assertEqual(metinler[0], "a tamam")
        self.assertIn("beklenmedik", metinler[1])
        self.assertTrue(metinler[1].endswith("✗"))
        self.assertEqual(metinler[2], "c tamam")
        self.assertTrue(sonuc.hata_var)
        self.assertTrue(sonuc.herhangi_yayinda)

    def test_bilinmeyen_kanal_atlanir(self):
        with patch.object(dagitim, "KANALLAR", {"a": self._isci("a")}), patch("concurrent.futures.ThreadPoolExecutor", SiraliYurutucu):
            sonuc = dagitim.dagit(baglam("ig"), ["yok", "a"], Ilerleme(["yok", "a"], None, "b"))
        self.assertEqual(list(sonuc.kanallar), ["a"])

    def test_hic_kanal_yoksa_bos_sonuc(self):
        sonuc = dagitim.dagit(baglam("ig"), [], Ilerleme([], None, "b"))
        self.assertEqual(sonuc.satirlar, [])

    def test_gercek_paralel_yurutucuyle_de_calisir(self):
        kayit = {"a": self._isci("a"), "b": self._isci("b"), "c": self._isci("c")}
        with patch.object(dagitim, "KANALLAR", kayit):
            sonuc = dagitim.dagit(baglam("ig"), ["a", "b", "c"], Ilerleme(["a", "b", "c"], None, "b"))
        self.assertEqual(list(sonuc.kanallar), ["a", "b", "c"])  # tamamlanma sırası değil, kanal sırası


class TestIlerleme(unittest.TestCase):
    def test_mesaj_id_yoksa_telegrama_hic_yazmaz(self):
        with patch("src.telegram.durum_metni.canli_yayin_durumu_guncelle") as g:
            i = Ilerleme(["a", "b"], None, "b")
            i.baslat()
            i.bildir("a", "x", increment=True)
        g.assert_not_called()

    def test_tamamlanma_her_zaman_gider_ara_guncellemeler_sinirlanir(self):
        with patch("src.telegram.durum_metni.canli_yayin_durumu_guncelle") as g:
            i = Ilerleme(["a", "b", "c"], 5, "b")
            i.bildir("a", "1", increment=True)   # ilk güncelleme geçer
            i.bildir("b", "2", increment=True)   # 1,2 sn içinde: atlanır
            i.bildir("c", "3", increment=True)   # tamamlanma: geçer
        adimlar = [c.kwargs["adim"] for c in g.call_args_list]
        self.assertEqual(adimlar, [1, 3])

    def test_baslangic_gosterimi_sifir_adim(self):
        with patch("src.telegram.durum_metni.canli_yayin_durumu_guncelle") as g:
            Ilerleme(["a", "b"], 5, "b").baslat()
        self.assertEqual(g.call_args.kwargs["adim"], 0)
        self.assertEqual(g.call_args.kwargs["toplam_adim"], 2)

    def test_telegram_hatasi_yayini_durdurmaz(self):
        with patch("src.telegram.durum_metni.canli_yayin_durumu_guncelle", side_effect=RuntimeError("tg")):
            i = Ilerleme(["a"], 5, "b")
            i.baslat()
            i.bildir("a", "x", increment=True)  # istisna dışarı sızmamalı

    def test_adim_toplami_asmaz(self):
        i = Ilerleme(["a"], None, "b")
        for _ in range(5):
            i.bildir("a", "x", increment=True)
        self.assertEqual(i.tamamlanan, 1)


class TestPaketYapisi(unittest.TestCase):
    def test_scripts_yayinla_ince_giris_noktasi(self):
        """İş mantığı src/yayin/'dedir; scripts/yayinla.py yalnız komut satırı girişidir (kod parçalanması geri dönmesin)."""
        satir = (KOK / "scripts" / "yayinla.py").read_text(encoding="utf-8").count("\n")
        self.assertLess(satir, 80, "scripts/yayinla.py yeniden büyüyor: mantığı src/yayin/ altına koy")

    def test_hicbir_modul_dev_degil(self):
        """Tek dosyada her şey 1571 satıra böyle ulaşmıştı: modül başına üst sınır."""
        buyuk = []
        for yol in (KOK / "src" / "yayin").rglob("*.py"):
            n = yol.read_text(encoding="utf-8").count("\n")
            if n > 250:
                buyuk.append(f"{yol.relative_to(KOK)}: {n} satır")
        self.assertFalse(buyuk, f"Bölünmesi gereken modüller: {buyuk}")

    def test_kanal_kaydi_her_kanal_icin_isci_var(self):
        from src.yayin.kanallar import KANALLAR
        beklenen = {"tiktok", "instagram", "reels", "story", "threads", "facebook", "facebook_reels", "youtube", "linkedin", "twitter", "x"}
        self.assertEqual(set(KANALLAR), beklenen)
        for ad, isci in KANALLAR.items():
            self.assertTrue(callable(isci), ad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
