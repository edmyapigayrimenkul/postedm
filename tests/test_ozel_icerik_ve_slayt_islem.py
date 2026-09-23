"""
tests/test_ozel_icerik_ve_slayt_islem.py — Özel İçerik Üretimi ve Slayt Operasyonları Testleri
"""

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src import db, ozel_icerik, telegram_bot


class TestOzelIcerikVeSlaytIslem(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_db = Path(self.tmpdir.name) / "test_ozel.db"
        self.db_patcher = patch("src.db.DB_YOLU", self.tmp_db)
        self.db_patcher.start()
        db.tablolari_olustur()

    def tearDown(self):
        self.db_patcher.stop()
        self.tmpdir.cleanup()
    def test_01_slayt_islem_menusu_butonlari(self):
        menu = telegram_bot.slayt_islem_menusu(sira=2, adet=4)
        self.assertIn("inline_keyboard", menu)
        rows = menu["inline_keyboard"]

        # 1. Satır: 2. slayt için EN BAŞA al butonu olmalı
        self.assertEqual(rows[0][0]["callback_data"], "slayt_basa:2")

        # 2. Satır: Yukarı ve Aşağı taşı butonları
        self.assertEqual(rows[1][0]["callback_data"], "slayt_yukari:2")
        self.assertEqual(rows[1][1]["callback_data"], "slayt_asagi:2")

        # Çarpıcı Yap, Elle Düzenle, Uzat, Kısalt, Sil ve Geri butonları
        tum_cbler = [btn["callback_data"] for row in rows for btn in row]
        self.assertIn("slayt_carpici:2", tum_cbler)
        self.assertIn("slayt_elle:2", tum_cbler)
        self.assertIn("slayt_uzat:2", tum_cbler)
        self.assertIn("slayt_kisalt:2", tum_cbler)
        self.assertIn("slayt_sil:2", tum_cbler)
        self.assertIn("slayt_menu:4", tum_cbler)

    def test_02_slayt_islem_menusu_ilk_slayt(self):
        # 1. slaytta yukarı taşı ve başa al butonu olmamalı
        menu = telegram_bot.slayt_islem_menusu(sira=1, adet=3)
        rows = menu["inline_keyboard"]
        tum_cbler = [btn["callback_data"] for row in rows for btn in row]
        self.assertNotIn("slayt_basa:1", tum_cbler)
        self.assertNotIn("slayt_yukari:1", tum_cbler)
        self.assertIn("slayt_asagi:1", tum_cbler)

    def test_03_db_askidaki_onaylari_temizle(self):
        import time
        test_url = f"test://temizle_{int(time.time() * 1000)}"
        # Bir haber ve bir ilan kaydını 'onay_bekliyor' yap
        with db._baglanti_al() as conn:
            conn.execute(
                """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, eklenme_tarihi, durum)
                   VALUES ('test', 'Test Haber', ?, '2026-01-01', 'onay_bekliyor')""",
                (test_url,),
            )
            conn.execute(
                """INSERT OR REPLACE INTO ilanlar (id, baslik, durum)
                   VALUES ('test_ilan_temizle', 'Test İlan', 'onay_bekliyor')"""
            )
            conn.commit()

        adet = db.askidaki_onaylari_temizle()
        self.assertGreaterEqual(adet, 2)

        # Durumların değiştiğini doğrula
        with db._baglanti_al() as conn:
            h = conn.execute("SELECT durum FROM haberler WHERE orijinal_url = ?", (test_url,)).fetchone()
            self.assertEqual(h["durum"], "iptal")
            i = conn.execute("SELECT durum FROM ilanlar WHERE id = 'test_ilan_temizle'").fetchone()
            self.assertEqual(i["durum"], "aktif")

    def test_04_db_gunluk_yayin_ozeti(self):
        ozet = db.gunluk_yayin_ozeti()
        self.assertIn("bugun_yayinlanan", ozet)
        self.assertIn("bekleyen_onay", ozet)
        self.assertIn("toplam_haber", ozet)
        self.assertIn("toplam_ilan", ozet)
        self.assertIsInstance(ozet["toplam_haber"], int)

    @patch("src.ozel_icerik.generate_text.konudan_uret")
    @patch("src.ozel_icerik.telegram_bot.haber_onayina_sun")
    @patch("src.ozel_icerik.telegram_bot.mesaj_gonder")
    @patch("src.ozel_icerik.db_senkron.hemen_kaydet")
    def test_05_konudan_ozel_icerik_uret(self, mock_kaydet, mock_mesaj, mock_onay, mock_uret):
        mock_uret.return_value = {
            "manset_parca_1": "Tarla Alırken Şufa Hakkı",
            "manset_vurgu": "Ön Alım",
            "spot": "Hisseli tarlalarda ortakların ön alım hakkı vardır.",
            "caption_instagram": "Tarla alırken dikkat edilmesi gerekenler...",
            "caption_threads": "Tarla alırken dikkat...",
        }
        mock_onay.return_value = True

        haber_id = ozel_icerik.konudan_ozel_icerik_uret("Tarla alırken hisseli tapuda şufa hakkı")
        self.assertIsNotNone(haber_id)

        haber = db.haber_getir(haber_id)
        self.assertIsNotNone(haber)
        self.assertEqual(haber["kategori"], "TAPU_VE_HUKUK")
        self.assertIn("Şufa Hakkı", haber["manset"])

    @patch("src.ozel_icerik._url_bilgisi_al")
    @patch("src.ozel_icerik.generate_text.konudan_uret")
    @patch("src.ozel_icerik.telegram_bot.haber_onayina_sun")
    @patch("src.ozel_icerik.telegram_bot.mesaj_gonder")
    @patch("src.ozel_icerik.db_senkron.hemen_kaydet")
    def test_06_linkten_icerik_uret(self, mock_kaydet, mock_mesaj, mock_onay, mock_uret, mock_url):
        mock_url.return_value = (
            "Resmi Gazete Tapu Tebliği Yayınlandı",
            "Tapu ve Kadastro Genel Müdürlüğü yeni bir genelge yayınladı...",
            "https://resmigazete.gov.tr/logo.png",
            "Resmigazete",
        )
        mock_uret.return_value = {
            "manset_parca_1": "Yeni Tapu Tebliği Yürürlükte",
            "spot": "Yeni düzenleme ile tapu işlemleri kolaylaşıyor.",
            "caption_instagram": "Yeni tapu tebliği yürürlükte...",
        }
        mock_onay.return_value = True

        haber_id = ozel_icerik.linkten_icerik_uret("https://www.resmigazete.gov.tr/ilan/123")
        self.assertIsNotNone(haber_id)

        haber = db.haber_getir(haber_id)
        self.assertEqual(haber["kaynak"], "Resmigazete")
        self.assertIn("Yeni Tapu Tebliği", haber["manset"])


if __name__ == "__main__":
    unittest.main()
