"""
tests/test_slot_ve_menu_paritesi.py — 3 Slotluk Günlük İçerik Rotasyonu ve Instabot Menü Paritesi Testleri
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import db, komutlar, konu_bankasi, telegram_bot


class TestSlotVeMenuParitesi(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_db = Path(self.tmpdir.name) / "test_slots.db"
        self.db_patcher = patch("src.db.DB_YOLU", self.tmp_db)
        self.db_patcher.start()
        db.tablolari_olustur()
        self.kullanildi_patcher = patch("src.konu_bankasi.kullanildi_isaretle")
        self.kullanildi_patcher.start()

    def tearDown(self):
        self.kullanildi_patcher.stop()
        self.db_patcher.stop()
        self.tmpdir.cleanup()

    def test_bilgilendirici_format_rotasyonu(self):
        """Slot 1 bilgilendirici rotasyonu her gün sırayla döner."""
        # 1. Başlangıçta ilk format nedir_dogrusu olmalı
        ilk = konu_bankasi.siradaki_bilgilendirici_format()
        self.assertEqual(ilk, "nedir_dogrusu")

        # 2. nedir_dogrusu kaydedildikten sonra vaka gelmeli
        konu_bankasi.bilgilendirici_format_kaydet("nedir_dogrusu")
        ikinci = konu_bankasi.siradaki_bilgilendirici_format()
        self.assertEqual(ikinci, "vaka")

        # 3. vaka sonrası net_cevap gelmeli
        konu_bankasi.bilgilendirici_format_kaydet("vaka")
        ucuncu = konu_bankasi.siradaki_bilgilendirici_format()
        self.assertEqual(ucuncu, "net_cevap")

        # 4. net_cevap sonrası b1 gelmeli
        konu_bankasi.bilgilendirici_format_kaydet("net_cevap")
        dorduncu = konu_bankasi.siradaki_bilgilendirici_format()
        self.assertEqual(dorduncu, "b1")

        # 5. b1 sonrası tekrar nedir_dogrusu'na dönmeli
        konu_bankasi.bilgilendirici_format_kaydet("b1")
        besinci = konu_bankasi.siradaki_bilgilendirici_format()
        self.assertEqual(besinci, "nedir_dogrusu")

    @patch("src.telegram_bot.hizli_icerik_uret")
    def test_slot_bilgilendirici_rotasyonu_calisir(self, mock_hizli):
        """Slot 1 çağrıldığında rotasyondaki formatı üretmeli ve formatı kaydetmeli."""
        mock_hizli.return_value = True
        konu_bankasi.bilgilendirici_format_kaydet("nedir_dogrusu")

        res = telegram_bot.slot_icerigi_hazirla_ve_sun(slot="bilgilendirici")
        self.assertTrue(res)
        mock_hizli.assert_called_once_with(format_turu="vaka")
        self.assertEqual(db.ayar_oku("son_bilgilendirici_format"), "vaka")

    @patch("src.telegram_bot.hizli_icerik_uret")
    def test_slot_sozluk_calisir(self, mock_hizli):
        """Slot 2 çağrıldığında sozluk formatı üretilmeli."""
        mock_hizli.return_value = True
        res = telegram_bot.slot_icerigi_hazirla_ve_sun(slot="sozluk")
        self.assertTrue(res)
        mock_hizli.assert_called_once_with(format_turu="sozluk")

    @patch("src.fetch_news.rss_tara", return_value=[])
    @patch("src.telegram_bot.hizli_icerik_uret")
    def test_slot_haber_fallback_yapar(self, mock_hizli, mock_rss):
        """Slot 3'te triyajı geçen haber yoksa otomatik olarak bilgilendirici rotasyona fallback yapmalı."""
        mock_hizli.return_value = True
        konu_bankasi.bilgilendirici_format_kaydet("b1")

        res = telegram_bot.slot_icerigi_hazirla_ve_sun(slot="haber")
        self.assertTrue(res)
        mock_hizli.assert_called_once_with(format_turu="nedir_dogrusu")
        self.assertEqual(db.ayar_oku("son_bilgilendirici_format"), "nedir_dogrusu")

    def test_ana_menu_ve_kontrol_paneli_tuslari(self):
        """Instabot buton paritesi doğrulanmalı: kanallar, formatlar ve kontroller."""
        menu = telegram_bot.ana_menu(adet=3)
        keyboard = menu["inline_keyboard"]
        callbackler = [btn["callback_data"] for row in keyboard for btn in row]

        # Kanal butonları mevcut
        self.assertIn("kanal:ig", callbackler)
        self.assertIn("kanal:reels", callbackler)
        self.assertIn("kanal:story", callbackler)
        self.assertIn("kanal:threads", callbackler)
        self.assertIn("kanal:facebook", callbackler)
        self.assertIn("kanal:youtube", callbackler)
        self.assertIn("kanal:tiktok", callbackler)

        # Temel eylem butonları
        self.assertIn("yayin_menu:3", callbackler)
        self.assertIn("manuel_paket", callbackler)
        self.assertIn("ertele", callbackler)
        self.assertIn("iptal", callbackler)
        self.assertIn("cope_at", callbackler)

        # Kontrol paneli butonları
        panel = telegram_bot.kontrol_merkezi_menusu()
        p_cb = [btn["callback_data"] for row in panel["inline_keyboard"] for btn in row]
        self.assertIn("hizli_uret:rotasyon", p_cb)
        self.assertIn("hizli_uret:reels", p_cb)
        self.assertIn("hizli_uret:sozluk", p_cb)
        self.assertIn("hizli_uret:nedir_dogrusu", p_cb)
        self.assertIn("hizli_uret:vaka", p_cb)
        self.assertIn("hizli_uret:net_cevap", p_cb)
        self.assertIn("hizli_uret:haber", p_cb)
        self.assertIn("hizli_uret:b1", p_cb)

    def test_komutlar_sozlugu(self):
        """Komutlar sözlüğünde /gonderi, /reels, /haber ve tüm temel komutlar tanımlı olmalı."""
        self.assertTrue(komutlar.mesajsiz_komut_mu("gonderi"))
        self.assertTrue(komutlar.mesajsiz_komut_mu("/gonderi"))
        self.assertTrue(komutlar.mesajsiz_komut_mu("reels"))
        self.assertTrue(komutlar.mesajsiz_komut_mu("haber"))
        self.assertTrue(komutlar.mesajsiz_komut_mu("sozluk"))
        self.assertTrue(komutlar.mesajsiz_komut_mu("dogrusu"))
        self.assertTrue(komutlar.mesajsiz_komut_mu("vaka"))
        self.assertTrue(komutlar.mesajsiz_komut_mu("soru"))
        self.assertTrue(komutlar.mesajsiz_komut_mu("panel"))


if __name__ == "__main__":
    unittest.main()
