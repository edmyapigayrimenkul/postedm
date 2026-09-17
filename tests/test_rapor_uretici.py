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

    def test_sifirlanma_fonksiyonlari(self):
        ay = rapor_uretici.sifirlanma_ay_basi()
        self.assertIn("gun", ay)
        self.assertRegex(ay, r"\d{2}\.\d{2} \(\d+ gun\)")

        gece = rapor_uretici.sifirlanma_gece_yarisi()
        self.assertIn("00:00", gece)
        self.assertIn("saat", gece)

        yt = rapor_uretici.sifirlanma_youtube()
        self.assertIn("10:00 TSI", yt)

        saat = rapor_uretici.sifirlanma_saatlik()
        self.assertIn("Saatlik", saat)
        self.assertIn("d)", saat)

    def test_cloudflare_kullanimi(self):
        cf = rapor_uretici.cloudflare_kullanimi()
        self.assertIn("worker_istek", cf)
        self.assertIn("kv_yazma", cf)
        self.assertIn("r2_depolama", cf)
        self.assertIn("sifirlanma", cf)

    def test_github_rest_api_kullanimi(self):
        gh_api = rapor_uretici.github_rest_api_kullanimi()
        self.assertIn("istek", gh_api)
        self.assertIn("sifirlanma", gh_api)

    def test_sosyal_medya_ve_yayin_kotalari(self):
        sm = rapor_uretici.sosyal_medya_ve_yayin_kotalari()
        self.assertIn("ig_kullanilan", sm)
        self.assertIn("ig_kalan", sm)
        self.assertIn("yt_birim", sm)
        self.assertIn("yt_kalan_shorts", sm)
        self.assertIn("yt_sifirlanma", sm)
        self.assertIn("db_mb", sm)
        self.assertIn("git_mb", sm)
        self.assertIn("disk_gb", sm)

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
                    "updated_at": "2026-09-17T11:00:30Z",  # 30s -> 1 dk
                },
            ],
        }

        with patch("requests.get", return_value=mock_response):
            res = rapor_uretici.github_actions_kullanimi(token="ghp_test_token_123")
            self.assertEqual(res["kaynak"], "canli_api")
            self.assertEqual(res["harcanan_dk"], 3)
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
        self.assertIn("model_katmani", res)

    def test_format_kompakt_kutu_ve_35_karakter_genislik(self):
        bolumler = [
            ("BOLUM 1", [("Anahtar 1", "Deger 1"), ("Anahtar 2", "Deger 2")]),
            ("BOLUM 2", [("Anahtar 3", "Deger 3")]),
        ]
        kutu = rapor_uretici.format_kompakt_kutu("BASLIK", "18.09.2026", bolumler)
        self.assertTrue(kutu.startswith("<pre>"))
        self.assertTrue(kutu.endswith("</pre>"))
        self.assertIn("┌", kutu)
        self.assertIn("└", kutu)
        self.assertIn("BOLUM 1", kutu)
        self.assertIn("Anahtar 1", kutu)
        self.assertIn("Deger 1", kutu)

        # Kutunun her satırının tam 35 karakter olduğunu doğrula
        satirlar = [s for s in kutu.replace("<pre>\n", "").replace("\n</pre>", "").split("\n") if s]
        for s in satirlar:
            self.assertEqual(len(s), 35, f"Satır genişliği 35 değil ({len(s)}): '{s}'")

    def test_kota_secenek_menusu(self):
        metin, butonlar = rapor_uretici.kota_secenek_menusu()
        self.assertIn("EDM SİSTEM & KOTA İZLEME MERKEZİ", metin)
        self.assertIn("1. Bulut, Yapay Zeka & API Kotaları", metin)
        self.assertIn("2. Sosyal Medya, Yayın & Depolama Kotaları", metin)
        self.assertIn("inline_keyboard", butonlar)
        tous = [btn["callback_data"] for row in butonlar["inline_keyboard"] for btn in row]
        self.assertIn("kota_kat:1", tous)
        self.assertIn("kota_kat:2", tous)
        self.assertIn("panel", tous)

    def test_kota_metni_uret_kategori_1(self):
        metin = rapor_uretici.kota_metni_uret(kategori=1)
        self.assertIn("EDM BULUT, AI & API KOTALARI", metin)
        self.assertIn("GITHUB ACTIONS (2.000 dk)", metin)
        self.assertIn("YAPAY ZEKA (Gemini AI)", metin)
        self.assertIn("CLOUDFLARE (Worker & KV)", metin)
        self.assertIn("GITHUB REST API", metin)
        self.assertIn("<pre>", metin)
        self.assertIn("</pre>", metin)

        # 35 karakter kesin genişlik kontrolü
        pre_icerik = metin.split("<pre>\n")[1].split("\n</pre>")[0]
        for satir in pre_icerik.split("\n"):
            if satir.strip():
                self.assertEqual(len(satir), 35, f"Kategori 1 satırı 35 karakter değil ({len(satir)}): {satir}")

    def test_kota_metni_uret_kategori_2(self):
        metin = rapor_uretici.kota_metni_uret(kategori=2)
        self.assertIn("EDM SOSYAL MEDYA & YAYIN KOTALARI", metin)
        self.assertIn("INSTAGRAM GRAPH API", metin)
        self.assertIn("YOUTUBE DATA API", metin)
        self.assertIn("DEPOLAMA & VERITABANI", metin)
        self.assertIn("YAYIN HAVUZU & REZERV", metin)
        self.assertIn("<pre>", metin)
        self.assertIn("</pre>", metin)

        # 35 karakter kesin genişlik kontrolü
        pre_icerik = metin.split("<pre>\n")[1].split("\n</pre>")[0]
        for satir in pre_icerik.split("\n"):
            if satir.strip():
                self.assertEqual(len(satir), 35, f"Kategori 2 satırı 35 karakter değil ({len(satir)}): {satir}")

    def test_kota_gonder(self):
        with patch("src.telegram_bot.mesaj_gonder") as mock_gonder, \
             patch("src.telegram_bot.mesaji_guncelle") as mock_guncelle:

            # 1. Menü gönderimi (varsayılan)
            rapor_uretici.kota_gonder(mesaj_id=None, kategori="menu")
            mock_gonder.assert_called_once()
            args, kwargs = mock_gonder.call_args
            self.assertIn("EDM SİSTEM & KOTA İZLEME MERKEZİ", args[0])

            # 2. Kategori 1 güncelleme
            rapor_uretici.kota_gonder(mesaj_id=12345, kategori=1)
            mock_guncelle.assert_called_once()
            args, kwargs = mock_guncelle.call_args
            self.assertEqual(args[0], 12345)
            self.assertIn("BULUT, AI & API KOTALARI", args[1])

            # 3. Kategori 2 gönderimi
            rapor_uretici.kota_gonder(mesaj_id=None, kategori=2)
            self.assertEqual(mock_gonder.call_count, 2)
            args, kwargs = mock_gonder.call_args
            self.assertIn("SOSYAL MEDYA & YAYIN KOTALARI", args[0])

            # 4. Geriye dönük takma adlar
            rapor_uretici.detayli_rapor_gonder(mesaj_id=None, kategori=1)
            self.assertEqual(mock_gonder.call_count, 3)
            rapor_uretici.kota(mesaj_id=None, kategori=2)
            self.assertEqual(mock_gonder.call_count, 4)


if __name__ == "__main__":
    unittest.main()
