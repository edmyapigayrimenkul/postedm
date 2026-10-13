"""
tests/test_reply_ve_hata_butonlari.py — Telegram Reply ile Metin Düzenleme ve Akıllı Hata Butonları Testleri
"""

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

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
    def test_09_ana_menu_yeniden_uret_ve_mesaji_sil(self):
        from src import telegram_bot
        menu = telegram_bot.ana_menu(adet=3)
        callbacks = [btn["callback_data"] for row in menu["inline_keyboard"] for btn in row]
        self.assertIn("yenile:3", callbacks)
        self.assertIn("mesaji_sil", callbacks)

    def test_10_son_onay_istegi_mesajlarini_getir_ve_sil(self):
        from unittest.mock import patch
        from src import db, telegram_bot
        
        # Test için onay istekleri ekle
        db.onay_istegi_kaydet("haber", "999", 501, 12345)
        db.onay_istegi_kaydet("haber", "999", 502, 12345)
        db.onay_istegi_kaydet("haber", "999", 503, 12345)

        mids = db.son_onay_istegi_mesajlarini_getir(adet=1)
        self.assertEqual(mids, [501, 502, 503])

        with patch("src.telegram.istemci.mesaji_sil", return_value=True) as mock_sil:
            silinen = telegram_bot.son_mesajlari_sil(adet=1)
            self.assertEqual(silinen, 3)
            self.assertEqual(mock_sil.call_count, 3)

        # Silindi olarak işaretlendiğini doğrula
        mids_kalan = db.son_onay_istegi_mesajlarini_getir(adet=1)
        self.assertNotIn(501, mids_kalan)

    def test_11_medya_grubu_id_ayiklama(self):
        from unittest.mock import MagicMock
        from src import telegram_bot

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "ok": True,
            "result": [
                {"message_id": 801},
                {"message_id": 802},
                {"message_id": 803},
            ]
        }
        mids = telegram_bot._ayikla_medya_mesaj_idleri(mock_resp)
        self.assertEqual(mids, [801, 802, 803])
        self.assertEqual(telegram_bot.son_medya_grubu_mesaj_idleri(), [801, 802, 803])


if __name__ == "__main__":
    unittest.main()

