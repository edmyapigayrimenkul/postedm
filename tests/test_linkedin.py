"""
tests/test_linkedin.py — LinkedIn modülü birim ve entegrasyon testleri.
"""

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")

import unittest
from unittest.mock import patch, MagicMock
from src import linkedin


class TestLinkedIn(unittest.TestCase):
    def test_kullanilabilir_mi(self):
        with patch("src.config.env_al") as mock_env:
            mock_env.side_effect = lambda k: "fake_token" if k == "LINKEDIN_ACCESS_TOKEN" else ("12345" if k == "LINKEDIN_ORGANIZATION_URN" else "")
            self.assertTrue(linkedin.kullanilabilir_mi())

        with patch("src.config.env_al") as mock_env:
            mock_env.return_value = ""
            self.assertFalse(linkedin.kullanilabilir_mi())

    def test_linkedin_metni_hazirla(self):
        haber = {
            "manset": "Milli Emlak Çatalca'da 49 Bin TL'ye Arazi Satışına Başladı",
            "kanca": "47 İLDE 383 PARSEL // RESMİ SATIŞTA",
            "spot": "Hazine arazileri uygun ödeme seçenekleri ve emlak vergisi muafiyetiyle satışa sunuldu.",
            "detay_maddeleri": [
                {"etiket": "01 // RESMİ GELİŞME", "metin": "Çevre ve Şehircilik Bakanlığı 47 ilde ihaleleri açtı."},
                {"etiket": "02 // BÖLGESEL PİYASA", "metin": "Çatalca ve Silivri fiyat dengesini doğrudan etkileyecek."}
            ],
            "uzman_notu": "İhaleye girmeden önce zemin durumunu ve kadastro yolunu bizzat kontrol edin."
        }
        metin = linkedin.linkedin_metni_hazirla(haber)
        self.assertIn("47 İLDE 383 PARSEL", metin)
        self.assertIn("Milli Emlak Çatalca", metin)
        self.assertIn("RESMİ GELİŞME: Çevre ve Şehircilik Bakanlığı", metin)
        self.assertIn("UZMAN DEĞERLENDİRMESİ", metin)
        self.assertIn("#GayrimenkulYatırımı", metin)
        self.assertIn("edmyapigayrimenkul.com", metin)

    def test_paylas_metin(self):
        linkedin._DOGRULANMIS_AUTHOR = None
        with patch("src.linkedin._hesap_bilgileri") as mock_hesap, \
             patch("requests.post") as mock_post:
            mock_hesap.return_value = ("fake_token", "urn:li:person:12345", None)
            mock_resp = MagicMock()
            mock_resp.status_code = 201
            mock_resp.headers = {"x-restli-id": "urn:li:share:987654"}
            mock_post.return_value = mock_resp

            post_id = linkedin.paylas("Test LinkedIn Gönderisi")
            self.assertEqual(post_id, "urn:li:share:987654")

    def test_aktif_author_fallback(self):
        linkedin._DOGRULANMIS_AUTHOR = None
        with patch("src.linkedin._hesap_bilgileri") as mock_hesap, \
             patch("requests.post") as mock_post:
            mock_hesap.return_value = ("fake_token", "urn:li:organization:9999", "urn:li:person:12345")
            mock_resp = MagicMock()
            mock_resp.status_code = 400
            mock_resp.text = '{"message":"Organization permissions must be used"}'
            mock_post.return_value = mock_resp

            author = linkedin._aktif_author("fake_token")
            self.assertEqual(author, "urn:li:person:12345")


if __name__ == "__main__":
    unittest.main()
