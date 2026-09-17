"""
tests/test_rapor_uretici.py — Detaylı Sistem ve Kota Raporu Birim Testleri
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ["POSTEDM_TEST_MODU"] = "1"

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import rapor_uretici


class TestRaporUretici(unittest.TestCase):
    def test_cizgi_bar(self):
        self.assertEqual(rapor_uretici.cizgi_bar(0), "□□□□□□□□□□")
        self.assertEqual(rapor_uretici.cizgi_bar(100), "■■■■■■■■■■")
        self.assertEqual(rapor_uretici.cizgi_bar(50), "■■■■■□□□□□")
        self.assertEqual(rapor_uretici.cizgi_bar(-10), "□□□□□□□□□□")
        self.assertEqual(rapor_uretici.cizgi_bar(120), "■■■■■■■■■■")
        self.assertEqual(len(rapor_uretici.cizgi_bar(33, uzunluk=10)), 10)

    def test_format_tablo(self):
        basliklar = ("Metrik", "Değer")
        satirlar = [("Aylik Dahil Kota", "2.000 dk"), ("Harcanan Sure", "120 dk")]
        tablo = rapor_uretici.format_tablo(basliklar, satirlar, w1=18, w2=10)

        self.assertTrue(tablo.startswith("<pre>"))
        self.assertTrue(tablo.endswith("</pre>"))
        self.assertIn("┌", tablo)
        self.assertIn("┐", tablo)
        self.assertIn("│ Metrik", tablo)
        self.assertIn("Aylik Dahil Kota", tablo)
        self.assertIn("120 dk", tablo)

    def test_github_actions_kullanimi_fallback_token_yok(self):
        with patch.dict(os.environ, {}, clear=True):
            res = rapor_uretici.github_actions_kullanimi(token=None)
            self.assertIn("harcanan_dk", res)
            self.assertIn("kalan_dk", res)
            self.assertIn("yuzde", res)
            self.assertEqual(res["kaynak"], "tahmin")

    def test_github_actions_kullanimi_canli_api_mock(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_count": 2,
            "workflow_runs": [
                {
                    "name": "Site İlan Kuyruğu",
                    "status": "completed",
                    "run_started_at": "2026-09-17T10:00:00Z",
                    "updated_at": "2026-09-17T10:01:20Z",  # 80s -> 2 dk
                },
                {
                    "name": "Testler",
                    "status": "completed",
                    "run_started_at": "2026-09-17T11:00:00Z",
                    "updated_at": "2026-09-17T11:00:30Z",  # 30s -> 1 dk (min 1 dk kuralı)
                },
            ],
        }

        with patch("requests.get", return_value=mock_response):
            res = rapor_uretici.github_actions_kullanimi(token="ghp_test_token_123")
            self.assertEqual(res["kaynak"], "canli_api")
            self.assertEqual(res["harcanan_dk"], 3)  # 2 + 1
            self.assertEqual(res["kalan_dk"], 1997)
            self.assertAlmostEqual(res["yuzde"], 3 / 2000.0 * 100.0, places=2)
            self.assertEqual(res["is_akislari"]["Site İlan Kuyruğu"], 2)
            self.assertEqual(res["is_akislari"]["Testler"], 1)

    def test_yapay_zeka_kullanimi(self):
        res = rapor_uretici.yapay_zeka_kullanimi()
        self.assertIn("bu_ay_haber", res)
        self.assertIn("bugun_haber", res)
        self.assertIn("tahmini_token", res)
        self.assertIn("gunluk_cagri", res)
        self.assertIn("kalan_cagri", res)
        self.assertEqual(res["model_katmani"], "Gemini 3.x Flash")

    def test_sosyal_medya_ve_api_sagligi(self):
        sm = rapor_uretici.sosyal_medya_ve_api_sagligi()
        self.assertIsInstance(sm, list)
        self.assertTrue(len(sm) >= 5)
        for platform, durum in sm:
            self.assertIsInstance(platform, str)
            self.assertTrue("Aktif" in durum or "Secrets" in durum)

    def test_icerik_ve_rezerv_durumu(self):
        ic = rapor_uretici.icerik_ve_rezerv_durumu()
        self.assertIn("yayinlanan_ay", ic)
        self.assertIn("bekleyen", ic)
        self.assertIn("havuz", ic)
        self.assertIn("bakir", ic)
        self.assertIn("kalan_hafta", ic)

    def test_detayli_rapor_metni_uret(self):
        metin = rapor_uretici.detayli_rapor_metni_uret()
        self.assertIn("EDM SİSTEM, KOTA & PERFORMANS RAPORU", metin)
        self.assertIn("GITHUB ACTIONS KULLANIMI", metin)
        self.assertIn("YAPAY ZEKA (GEMINI AI) KULLANIMI", metin)
        self.assertIn("SOSYAL MEDYA & API SAĞLIĞI", metin)
        self.assertIn("İÇERİK & KONU BANKASI HAVUZU", metin)
        self.assertIn("<pre>", metin)
        self.assertIn("</pre>", metin)

    def test_detayli_rapor_gonder(self):
        with patch("src.telegram_bot.mesaj_gonder") as mock_gonder, \
             patch("src.telegram_bot.mesaji_guncelle") as mock_guncelle:
            rapor_uretici.detayli_rapor_gonder(mesaj_id=None)
            mock_gonder.assert_called_once()

            rapor_uretici.detayli_rapor_gonder(mesaj_id=12345)
            mock_guncelle.assert_called_once()
            args, kwargs = mock_guncelle.call_args
            self.assertEqual(args[0], 12345)


if __name__ == "__main__":
    unittest.main()
