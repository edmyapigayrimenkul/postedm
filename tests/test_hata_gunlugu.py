"""
tests/test_hata_gunlugu.py — hata günlüğü kalıcılığı ve gizli değer maskeleme (2026-10-12 denetimi)

Bulgular:
  · Günlük `data/hata_kayitlari.jsonl` ve `data/son_hata.txt` dosyalarına yazılıyordu; ikisi de .gitignore'da ve
    Actions makinesi iş bitince silinir: kayıt ertesi güne ulaşmıyordu.
  · Okuyucu `tarih_iso` anahtarını arıyordu, yazıcı `tarih` yazıyordu: dosya var olsa bile hiçbir kayıt eşleşmiyordu.
  · `python -m src.hata_bildir` içinde `sys` içe aktarılmamıştı (NameError).
  · Kayıt DB'ye (git'e giden dosya) yazılacağı için requests istisnasındaki access_token maskelenmeli.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import config, db, gizlilik, hata_bildir, rapor_uretici  # noqa: E402

SIR_DEGERLERI = [
    "EAABwzLixnjYBO1234567890abcdefghijklmnop",
    "AIzaSyA1234567890abcdefghijklmnopqr",
    "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ_0123456",
    "ghp_abcdefghijklmnopqrstuvwxyz0123456789",
    "sk_0123456789abcdef0123456789abcdef",
    "ya29.a0AfH6SMBxxxxxxxxxxxxxxxxxxxxxxxx",
]


class TestMaskeleme(unittest.TestCase):
    def test_url_sorgu_parametresi(self):
        m = gizlilik.maskele("HTTPError url: https://graph.facebook.com/v21.0/1/insights?metric=reach&access_token=EAAB1234567890abcdefghijklmn&x=1")
        self.assertNotIn("EAAB1234567890", m)
        self.assertIn("metric=reach", m)
        self.assertIn("x=1", m)

    def test_bearer_ve_json(self):
        m = gizlilik.maskele('{"access_token": "abc.def.ghi123456", "client_secret":"zzzyyyxxx"} Authorization: Bearer tok_1234567890abcdef')
        for gizli in ("abc.def.ghi123456", "zzzyyyxxx", "tok_1234567890abcdef"):
            self.assertNotIn(gizli, m)

    def test_bicimi_taninan_jetonlar_anahtar_adi_olmadan_da_gizlenir(self):
        for deger in SIR_DEGERLERI:
            with self.subTest(deger=deger[:8]):
                self.assertNotIn(deger, gizlilik.maskele(f"beklenmeyen yanıt: {deger} ve devamı"))

    def test_telegram_bot_adresi(self):
        m = gizlilik.maskele("POST https://api.telegram.org/bot123456789:ABCdefGHIjklMNOpqrSTUvwxYZ_0123456/sendMessage 400")
        self.assertNotIn("ABCdefGHIjkl", m)
        self.assertIn("sendMessage", m)

    def test_sade_metne_dokunmaz(self):
        metin = "TikTok API erişim yetkisinin süresi dolmuş. Instagram carousel yayını 3 kez denendi (HTTP 400)."
        self.assertEqual(gizlilik.maskele(metin), metin)

    def test_none_ve_metin_olmayan_girdi(self):
        self.assertEqual(gizlilik.maskele(None), "")
        self.assertEqual(gizlilik.maskele(404), "404")

    def test_ikinci_maskeleme_kararli(self):
        once = gizlilik.maskele("access_token=EAAB1234567890abcdefghijklmn")
        self.assertEqual(gizlilik.maskele(once), once)


class TestHataKaydiKalici(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._yama = [patch.object(hata_bildir, "HATA_LOG_YOLU", Path(self.tmp.name) / "h.jsonl"),
                      patch.object(hata_bildir, "SON_HATA_YOLU", Path(self.tmp.name) / "son.txt")]
        for y in self._yama:
            y.start()
        db.tablolari_olustur()
        with db._baglanti_al() as conn:
            conn.execute("DELETE FROM hata_kayitlari")
            conn.commit()

    def tearDown(self):
        for y in self._yama:
            y.stop()
        self.tmp.cleanup()

    def test_hata_db_ye_yazilir_ve_dosya_olmadan_okunur(self):
        teshis = hata_bildir.hatayi_analiz_et("database is locked")
        hata_bildir.hata_kaydet("Yayınla", "Yayınla", "database is locked", teshis)
        # Dosyalar Actions makinesiyle gider; DB kalır
        hata_bildir.HATA_LOG_YOLU.unlink()
        hata_bildir.SON_HATA_YOLU.unlink()
        kayitlar = hata_bildir.son_hatalari_ozetle(saat=24)
        self.assertEqual(len(kayitlar), 1)
        self.assertEqual(kayitlar[0]["nerede"], "Yayınla")
        self.assertTrue(kayitlar[0]["tanindi"])
        self.assertIn("database is locked", db.son_hata_metni())

    def test_db_ve_dosyaya_gizli_deger_yazilmaz(self):
        ham = "ConnectionError: https://graph.facebook.com/v21.0/9?access_token=EAAB1234567890abcdefghijklmn&fields=id"
        hata_bildir.hata_kaydet("Yayınla", "Yayınla", ham, hata_bildir.hatayi_analiz_et(ham))
        self.assertNotIn("EAAB1234567890", db.son_hata_metni())
        self.assertNotIn("EAAB1234567890", hata_bildir.SON_HATA_YOLU.read_text(encoding="utf-8"))
        self.assertNotIn("EAAB1234567890", hata_bildir.HATA_LOG_YOLU.read_text(encoding="utf-8"))

    def test_son_ham_hata_dosyasi_da_maskeli(self):
        hata_bildir.son_ham_hata_kaydet("hata url: ?access_token=EAAB1234567890abcdefghijklmn")
        self.assertNotIn("EAAB1234567890", hata_bildir.SON_HATA_YOLU.read_text(encoding="utf-8"))

    def test_24_saatten_eski_kayit_ozete_girmez(self):
        hata_bildir.hata_kaydet("A", "A", "x", {})
        with db._baglanti_al() as conn:
            conn.execute("UPDATE hata_kayitlari SET tarih = '2020-01-01T00:00:00+00:00'")
            conn.commit()
        self.assertEqual(hata_bildir.son_hatalari_ozetle(saat=24), [])

    def test_otuz_gunden_eski_kayitlar_yeni_kayitla_temizlenir(self):
        db.hata_kaydi_ekle("eski", "eski", "", "", "", False, "x")
        with db._baglanti_al() as conn:
            conn.execute("UPDATE hata_kayitlari SET tarih = '2020-01-01T00:00:00+00:00'")
            conn.commit()
        db.hata_kaydi_ekle("yeni", "yeni", "", "", "", False, "y")
        with db._baglanti_al() as conn:
            adlar = [r[0] for r in conn.execute("SELECT nerede FROM hata_kayitlari")]
        self.assertEqual(adlar, ["yeni"])

    def test_sys_ice_aktarilmis(self):
        """`python -m src.hata_bildir` yolundaki sys.exit(0) NameError vermemeli."""
        self.assertTrue(hasattr(hata_bildir, "sys"))

    def test_test_modunda_dosyalar_depodaki_data_klasorune_yazilmaz(self):
        self.assertNotEqual(config.veri_yolu("x").parent, config.KOK_DIZIN / "data")


class TestRaporSatirlari(unittest.TestCase):
    def test_olculemeyen_basarisiz_is_sifir_gosterilmez(self):
        with patch.object(rapor_uretici, "basarisiz_is_akislari", return_value=None):
            satirlar = dict(rapor_uretici.hata_gunlugu_satirlari())
        self.assertEqual(satirlar["Basarisiz is"], "ölçülemedi")

    def test_olculen_deger_yazilir(self):
        with patch.object(rapor_uretici, "basarisiz_is_akislari", return_value=3):
            self.assertIn("3", dict(rapor_uretici.hata_gunlugu_satirlari())["Basarisiz is"])
        with patch.object(rapor_uretici, "basarisiz_is_akislari", return_value=0):
            self.assertIn("0", dict(rapor_uretici.hata_gunlugu_satirlari())["Basarisiz is"])

    def test_jeton_yoksa_olculemedi(self):
        with patch.object(rapor_uretici, "_github_token_al", return_value=None):
            self.assertIsNone(rapor_uretici.basarisiz_is_akislari())

    def test_api_hatasinda_olculemedi(self):
        class Cevap:
            status_code = 403
            text = "forbidden"
        with patch.object(rapor_uretici, "_github_token_al", return_value="t"), \
             patch.object(rapor_uretici.requests, "get", return_value=Cevap()):
            self.assertIsNone(rapor_uretici.basarisiz_is_akislari())

    def test_sayi_total_count_ten_okunur(self):
        class Cevap:
            status_code = 200
            text = ""
            def json(self):
                return {"total_count": 4, "workflow_runs": []}
        with patch.object(rapor_uretici, "_github_token_al", return_value="t"), \
             patch.object(rapor_uretici.requests, "get", return_value=Cevap()) as get:
            self.assertEqual(rapor_uretici.basarisiz_is_akislari(saat=24), 4)
        self.assertEqual(get.call_args.kwargs["params"]["status"], "failure")


if __name__ == "__main__":
    unittest.main(verbosity=2)
