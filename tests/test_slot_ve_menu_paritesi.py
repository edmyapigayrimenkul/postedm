"""
tests/test_slot_ve_menu_paritesi.py — 3 Slotluk Günlük İçerik Rotasyonu ve Instabot Menü Paritesi Testleri
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

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
        """10:00 içeriği dört formatlı döngüde döner (vaka elle tetiklenir); B1 iki kez. Sözlük döngüde YOK:
        12:30'da ayrıca yayınlandığı için döngüde kalsaydı beşinci günde aynı gün iki sözlük çıkardı."""
        self.assertNotIn("sozluk", konu_bankasi.BILGILENDIRICI_FORMATLAR)
        beklenen = ["b1", "nedir_dogrusu", "net_cevap", "b1", "b1", "nedir_dogrusu", "net_cevap", "b1"]
        gorulen = []
        for _ in beklenen:
            f = konu_bankasi.siradaki_bilgilendirici_format()
            gorulen.append(f)
            konu_bankasi.bilgilendirici_format_kaydet(f)
        self.assertEqual(gorulen, beklenen)

    def test_eski_sozluk_sirasi_donguyu_bozmaz_basa_doner(self):
        """Üretimdeki eski kayıt döngünün 5. sırasını (sözlük) göstermiş olabilir: aralık dışı sıra ve "sozluk"
        son formatı hata vermez, döngü b1'den başlar."""
        db.ayar_yaz("bilgilendirici_sira", "4")
        db.ayar_yaz("son_bilgilendirici_format", "sozluk")
        self.assertEqual(konu_bankasi.siradaki_bilgilendirici_format(), "b1")
        konu_bankasi.bilgilendirici_format_kaydet("sozluk")          # döngüde olmayan format kaydı bozmaz
        self.assertEqual(konu_bankasi.siradaki_bilgilendirici_format(), "b1")

    def test_eski_kayittan_rotasyon_devam_eder(self):
        """Üretimdeki eski anahtar (yalnızca format adı) döngüyü bozmadan devralınır."""
        db.ayar_yaz("son_bilgilendirici_format", "net_cevap")
        self.assertEqual(konu_bankasi.siradaki_bilgilendirici_format(), "b1")

    @patch("src.telegram.akislar.uretim.hizli_icerik_uret")
    def test_slot_bilgilendirici_rotasyonu_calisir(self, mock_hizli):
        """Günün içeriği döngüdeki formatı üretmeli ve sırayı kaydetmeli."""
        mock_hizli.return_value = True
        konu_bankasi.bilgilendirici_format_kaydet("b1")  # sıra 0

        res = telegram_bot.slot_icerigi_hazirla_ve_sun(slot="bilgilendirici")
        self.assertTrue(res)
        mock_hizli.assert_called_once_with(format_turu="nedir_dogrusu")
        self.assertEqual(db.ayar_oku("son_bilgilendirici_format"), "nedir_dogrusu")

    @patch("src.telegram.istemci.mesaj_gonder", return_value={"message_id": 1})
    @patch("src.telegram.akislar.sozluk.sozluk_karti_hazirla_ve_sun", return_value=None)
    @patch("src.telegram.akislar.uretim.hizli_icerik_uret")
    def test_slot_sozluk_calisir(self, mock_hizli, mock_kart, mock_mesaj):
        """Slot 2: hazır kart kalmadıysa sozluk formatı modelle üretilip onaya sunulmalı."""
        mock_hizli.return_value = True
        res = telegram_bot.slot_icerigi_hazirla_ve_sun(slot="sozluk")
        self.assertTrue(res)
        mock_kart.assert_called_once_with()
        mock_hizli.assert_called_once_with(format_turu="sozluk")

    @patch("src.telegram.akislar.sozluk.sozluk_karti_hazirla_ve_sun", return_value=True)
    @patch("src.telegram.akislar.uretim.hizli_icerik_uret")
    def test_slot_sozluk_once_hazir_karti_dener(self, mock_hizli, mock_kart):
        """Hazır kart varken model hiç çağrılmaz (kota ve doğruluk: kart önceden doğrulanmıştır)."""
        res = telegram_bot.slot_icerigi_hazirla_ve_sun(slot="sozluk")
        self.assertTrue(res)
        mock_kart.assert_called_once_with()
        mock_hizli.assert_not_called()

    @patch("src.telegram.istemci.mesaj_gonder", return_value={"message_id": 1})
    @patch("src.fetch_news.rss_tara", return_value=[])
    @patch("src.telegram.akislar.uretim.hizli_icerik_uret")
    def test_slot_haber_icerik_uretmez_oneri_duser(self, mock_hizli, mock_rss, mock_mesaj):
        """Haber slotu içerik üretmez (içerik günde bir); taze haberi tarihiyle öneri olarak düşürür."""
        from datetime import datetime, timedelta, timezone
        taze = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        bayat = (datetime.now(timezone.utc) - timedelta(hours=60)).isoformat()
        with db._baglanti_al() as conn:
            for url, puan, tarih, kat in (("https://ornek.com/a", 9, taze, "S1"),
                                           ("https://ornek.com/b", 5, taze, "S1"),
                                           ("https://ornek.com/c", 9, bayat, "S1"),
                                           ("https://ornek.com/d", 9, taze, "rehber")):
                conn.execute(
                    "INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet, yayin_tarihi,"
                    " eklenme_tarihi, onem_puani, kategori, durum) VALUES (?,?,?,?,?,?,?,?, 'yeni')",
                    ("Emlakkulisi", f"Başlık {url[-1]}", url, "Özet", tarih, taze, puan, kat),
                )
            conn.commit()

        res = telegram_bot.slot_icerigi_hazirla_ve_sun(slot="haber")
        self.assertTrue(res)
        mock_hizli.assert_not_called()
        gonderilen = [c.args[0] for c in mock_mesaj.call_args_list]
        self.assertEqual(len(gonderilen), 1, gonderilen)
        self.assertIn("Başlık a", gonderilen[0])
        self.assertIn("🗓", gonderilen[0])
        self.assertIn("saat önce", gonderilen[0])
        # Instabot'un öneri taslağı (2026-09-26): numaralı seçim, 🔍 inceleme, Hazırla, Hiçbiri
        klavye = mock_mesaj.call_args_list[0].kwargs["reply_markup"]["inline_keyboard"]
        self.assertEqual([[b["callback_data"].split(":")[0] for b in satir] for satir in klavye],
                         [["sec"], ["incele"], ["hazirla_secilenler"], ["oneri_gec"]])
        with db._baglanti_al() as conn:
            durum = conn.execute("SELECT durum FROM haberler WHERE orijinal_url = 'https://ornek.com/a'").fetchone()[0]
        self.assertEqual(durum, "onerildi")

        # İkinci turda aynı haber tekrar önerilmez
        mock_mesaj.reset_mock()
        telegram_bot.slot_icerigi_hazirla_ve_sun(slot="haber")
        self.assertFalse(any("Başlık a" in c.args[0] for c in mock_mesaj.call_args_list))

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
        self.assertIn("ses_menu:3", callbackler)  # 🎙️ Sesli Yayınla (2026-09-26)
        self.assertIn("manuel_paket", callbackler)
        self.assertNotIn("ertele", callbackler)  # ⏰ 1 saat ertele kaldırıldı (hatırlatma yok, 24 saat kuralı)
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
