"""
tests/test_reply_ve_hata_butonlari.py — Telegram Reply ile Metin Düzenleme ve Akıllı Hata Butonları Testleri
"""

import subprocess
import sys
import unittest
from pathlib import Path

from scripts.metin_duzenle import metin_ayristir
from src import hata_bildir


class TestReplyVeHataButonlari(unittest.TestCase):
    def test_01_metin_ayristir_tekil_baslik(self):
        sira, baslik, aciklama = metin_ayristir("Tapu Harcı 2026 Güncellemesi")
        self.assertIsNone(sira)
        self.assertEqual(baslik, "Tapu Harcı 2026 Güncellemesi")
        self.assertIsNone(aciklama)

    def test_02_metin_ayristir_baslik_ve_aciklama_pipe(self):
        sira, baslik, aciklama = metin_ayristir("Rayiç Bedel Nedir? | Yeni oranlar ve belediye tarifesi.")
        self.assertIsNone(sira)
        self.assertEqual(baslik, "Rayiç Bedel Nedir?")
        self.assertEqual(aciklama, "Yeni oranlar ve belediye tarifesi.")

    def test_03_metin_ayristir_numarali_slayt(self):
        sira, baslik, aciklama = metin_ayristir("3: Tapu İptal Davası Şartları")
        self.assertEqual(sira, 3)
        self.assertEqual(baslik, "Tapu İptal Davası Şartları")
        self.assertIsNone(aciklama)

    def test_04_metin_ayristir_numarali_slayt_ve_aciklama(self):
        sira, baslik, aciklama = metin_ayristir("2. İmar Durumu Sorgulama | Parsel sorgu ekranından ada parsel girilir.")
        self.assertEqual(sira, 2)
        self.assertEqual(baslik, "İmar Durumu Sorgulama")
        self.assertEqual(aciklama, "Parsel sorgu ekranından ada parsel girilir.")

    def test_05_metin_ayristir_coklu_satir(self):
        metin = "Kat Mülkiyeti Geçişi\nApartman sakinlerinin beşte dördünün rızası gerekmektedir."
        sira, baslik, aciklama = metin_ayristir(metin)
        self.assertIsNone(sira)
        self.assertEqual(baslik, "Kat Mülkiyeti Geçişi")
        self.assertEqual(aciklama, "Apartman sakinlerinin beşte dördünün rızası gerekmektedir.")

    def test_06_hata_butonlari_yapisi(self):
        markup = hata_bildir._butonlar(
            eylem="yeniden_yayinla",
            nerede="Yayınla",
            tur="haber",
            ref_id="456",
            hedef="ig,threads",
            run_url="https://github.com/edmyapigayrimenkul/postedm/actions/runs/12345",
        )
        self.assertIsNotNone(markup)
        rows = markup["inline_keyboard"]

        # 1. Satır: Tekrar Yayınla ve Bu Turu Atla
        self.assertEqual(len(rows[0]), 2)
        self.assertEqual(rows[0][0]["text"], "🔄 Tekrar Yayınla")
        self.assertEqual(rows[0][0]["callback_data"], "onayla:haber:ig,threads:456")
        self.assertEqual(rows[0][1]["text"], "❌ Bu Turu Atla")
        self.assertEqual(rows[0][1]["callback_data"], "reddet:haber:456")

        # 2. Satır: Ham Hata Göster ve Sistem Durumu
        self.assertEqual(len(rows[1]), 2)
        self.assertEqual(rows[1][0]["text"], "🔍 Ham Hata Göster")
        self.assertEqual(rows[1][0]["callback_data"], "hata_ayrinti")
        self.assertEqual(rows[1][1]["text"], "📊 Sistem Durumu")
        self.assertEqual(rows[1][1]["callback_data"], "durum")

        # 3. Satır: GitHub Log Linki
        self.assertEqual(len(rows[2]), 1)
        self.assertEqual(rows[2][0]["text"], "🌐 GitHub Logunu Aç")
        self.assertEqual(rows[2][0]["url"], "https://github.com/edmyapigayrimenkul/postedm/actions/runs/12345")

    def test_07_hata_bildir_cli_yardim(self):
        res = subprocess.run(
            [sys.executable, "-m", "src.hata_bildir", "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--run-url", res.stdout)
        self.assertIn("--islem", res.stdout)

    def test_08_metin_duzenle_cli_yardim(self):
        res = subprocess.run(
            [sys.executable, "scripts/metin_duzenle.py", "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--mesaj-id", res.stdout)
        self.assertIn("--metin", res.stdout)


if __name__ == "__main__":
    unittest.main()
