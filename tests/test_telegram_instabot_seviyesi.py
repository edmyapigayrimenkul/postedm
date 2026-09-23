"""
tests/test_telegram_instabot_seviyesi.py — Instabot Seviyesi Komutlar, Ayar Menüsü ve Yönetim Kartları Testi
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import json
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import ayar, db, komutlar, ozel_icerik, telegram_bot


class TestTelegramInstabotSeviyesi(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_db = Path(self.tmpdir.name) / "test_instabot.db"
        self.db_patcher = patch("src.db.DB_YOLU", self.tmp_db)
        self.db_patcher.start()
        db.tablolari_olustur()

    def tearDown(self):
        self.db_patcher.stop()
        self.tmpdir.cleanup()

    def test_ayar_oku_ve_kaydet(self):
        """Ayar okuma, dönüştürme ve kaydetme döngüsü doğrulanır."""
        # Varsayılanlar
        self.assertTrue(ayar.ayar_oku("oto_yayin"))
        self.assertTrue(ayar.ayar_oku("kanal_threads"))
        self.assertFalse(ayar.ayar_oku("reels_varsayilan"))

        # Güncelleme
        basarili = ayar.ayar_kaydet("oto_yayin", False)
        self.assertTrue(basarili)
        self.assertFalse(ayar.ayar_oku("oto_yayin"))

        # Tekrar açma (string "true" ile de dönüştürülmeli)
        basarili = ayar.ayar_kaydet("oto_yayin", "true")
        self.assertTrue(basarili)
        self.assertTrue(ayar.ayar_oku("oto_yayin"))

        # İzin verilmeyen anahtar reddedilmeli
        gecersiz = ayar.ayar_kaydet("admin_sifresi", "12345")
        self.assertFalse(gecersiz)
        self.assertIsNone(ayar.ayar_oku("admin_sifresi"))

    def test_ayar_menusu_butonlari_ve_byte_limiti(self):
        """Ayar menüsü butonlarının formatı ve 64 byte kuralı doğrulanır."""
        menu = ayar.ayar_menusu()
        self.assertIn("inline_keyboard", menu)
        satirlar = menu["inline_keyboard"]
        self.assertGreaterEqual(len(satirlar), len(ayar.DEGISTIRILEBILIR) + 1)

        for row in satirlar:
            for btn in row:
                cb = btn.get("callback_data", "")
                self.assertLessEqual(len(cb.encode("utf-8")), 64, f"Callback 64 baytı aştı: {cb}")
                self.assertTrue(
                    cb.startswith("ayarsec:") or cb in ("panel", "durum"),
                    f"Beklenmeyen callback formatı: {cb}"
                )

    @patch("src.telegram_bot.haber_onayina_sun")
    @patch("src.telegram_bot.mesaj_gonder")
    @patch("src.db_senkron.hemen_kaydet")
    @patch("src.generate_text._gemini_cagri")
    @patch("src.generate_text.konudan_uret")
    def test_arastir_icerik_uret(self, mock_konu, mock_gemini, mock_senkron, mock_mesaj, mock_onay):
        """Derin gayrimenkul araştırması (/arastir) akışı ve DB kaydı doğrulanır."""
        mock_gemini.return_value = "Tapu Kanunu 26. Madde uyarınca miras intikalinde harç muafiyeti şartları şunlardır..."
        mock_konu.return_value = {
            "manset": "2026 Tapu Harcı Muafiyeti Rehberi",
            "spot": "Miras ve bağış işlemlerinde güncel istisnalar.",
            "caption_instagram": "Tapu harcı rehberi #tapu #emlak",
            "caption_threads": "Tapu harcından muafiyet şartları neler?",
        }
        mock_onay.return_value = True

        haber_id = ozel_icerik.arastir_icerik_uret("2026 miras intikalinde tapu harcı muafiyeti")
        self.assertIsNotNone(haber_id)
        self.assertGreater(haber_id, 0)

        haber = db.haber_getir(haber_id)
        self.assertEqual(haber["kaynak"], "EDM Araştırma Masası")
        self.assertEqual(haber["kategori"], "TAPU_VE_HUKUK")
        self.assertEqual(haber["durum"], "onay_bekliyor")
        self.assertIn("2026 Tapu Harcı", haber["manset"])
        mock_onay.assert_called_once_with(haber_id)

    @patch("src.telegram_bot.haber_onayina_sun")
    @patch("src.telegram_bot.mesaj_gonder")
    @patch("src.db_senkron.hemen_kaydet")
    @patch("src.generate_text._gemini_cagri")
    @patch("src.generate_text.konudan_uret")
    def test_dosya_icerik_uret(self, mock_konu, mock_gemini, mock_senkron, mock_mesaj, mock_onay):
        """Özel dosya / süreç analizi (/dosya) akışı ve DB kaydı doğrulanır."""
        mock_gemini.return_value = "1. Aşama: Başvuru belgeleri, 2. Aşama: Değerleme raporu, 3. Aşama: Tapu tescili..."
        mock_konu.return_value = {
            "manset": "İmar Barışı ve Yapı Kayıt Belgesi Dosyası",
            "spot": "Adım adım başvuru ve risk yönetimi.",
            "caption_instagram": "İmar barışı dosya haberi #imar #hukuk",
            "caption_threads": "Yapı kayıt belgesi nasıl alınır?",
        }
        mock_onay.return_value = True

        haber_id = ozel_icerik.dosya_icerik_uret("İmar Barışı ve Yapı Kayıt Belgesi")
        self.assertIsNotNone(haber_id)
        self.assertGreater(haber_id, 0)

        haber = db.haber_getir(haber_id)
        self.assertEqual(haber["kaynak"], "EDM Dosya Masası")
        self.assertEqual(haber["kategori"], "IMAR_VE_MEVZUAT")
        self.assertEqual(haber["durum"], "onay_bekliyor")
        mock_onay.assert_called_once_with(haber_id)

    def test_icerik_incele_karti(self):
        """İçerik inceleme kartı metni ve butonları doğrulanır."""
        # 1. Olmayan id kontrolü
        metin_yok, kbd_yok = telegram_bot.icerik_incele_karti(9999)
        self.assertIn("bulunamadı", metin_yok)
        self.assertEqual(kbd_yok["inline_keyboard"][0][0]["callback_data"], "panel")

        # 2. Var olan haber ekle ve test et
        simdi = "2026-09-19T03:00:00+00:00"
        with db._baglanti_al() as conn:
            cur = conn.execute(
                """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet,
                                         eklenme_tarihi, onem_puani, kategori, manset, detay_metni, durum)
                   VALUES ('Test', 'Hisseli Tapu Testi', 'https://test.com', 'Özet', ?, 8, 'HUKUK', 'Hisseli Tapu Manşet', '{}', 'onay_bekliyor')""",
                (simdi,),
            )
            hid = cur.lastrowid
            conn.commit()

        metin, kbd = telegram_bot.icerik_incele_karti(hid)
        self.assertIn(f"#{hid}", metin)
        self.assertIn("Hisseli Tapu Manşet", metin)

        cb_listesi = []
        for row in kbd["inline_keyboard"]:
            for btn in row:
                cb = btn.get("callback_data", "")
                self.assertLessEqual(len(cb.encode("utf-8")), 64)
                cb_listesi.append(cb)

        self.assertIn(f"yayinla:{hid}", cb_listesi)
        self.assertIn(f"yenile:{hid}", cb_listesi)
        self.assertIn(f"yayin_kontrol:{hid}", cb_listesi)
        self.assertIn(f"cope_at:{hid}", cb_listesi)
        self.assertIn("panel", cb_listesi)

    def test_son_postlar_raporu(self):
        """Son postlar raporu ve butonları doğrulanır."""
        # Örnek 2 haber ekleyelim
        with db._baglanti_al() as conn:
            conn.execute(
                """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, eklenme_tarihi, onem_puani, kategori, manset, durum)
                   VALUES ('T1', 'Başlık 1', 'u1', '2026-09-19T01:00:00', 9, 'K1', 'Manşet 1', 'yayinlandi'),
                          ('T2', 'Başlık 2', 'u2', '2026-09-19T02:00:00', 8, 'K2', 'Manşet 2', 'onay_bekliyor')"""
            )
            conn.commit()

        metin, kbd = telegram_bot.son_postlar_raporu()
        self.assertIn("SON İÇERİKLER & YAYIN DURUMU", metin)
        self.assertIn("Manşet 1", metin)
        self.assertIn("Manşet 2", metin)

        for row in kbd["inline_keyboard"]:
            for btn in row:
                cb = btn.get("callback_data", "")
                self.assertLessEqual(len(cb.encode("utf-8")), 64)
                self.assertTrue(cb.startswith("incele:") or cb == "panel")

    def test_yayin_kontrol_karti_ve_kanallar(self):
        """Yayın kontrol kartı, tekil kanal retry ve kurtarma butonları doğrulanır."""
        with db._baglanti_al() as conn:
            cur = conn.execute(
                """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, eklenme_tarihi, onem_puani, kategori, manset, durum)
                   VALUES ('T', 'Test Kontrol', 'u', '2026-09-19', 9, 'K', 'Yayın Kontrol Testi', 'onay_bekliyor')"""
            )
            hid = cur.lastrowid
            conn.commit()

        metin, kbd = telegram_bot.yayin_kontrol_karti(hid)
        self.assertIn(f"#{hid}", metin)
        self.assertIn("Yayın Kontrol Testi", metin)

        cb_listesi = []
        for row in kbd["inline_keyboard"]:
            for btn in row:
                cb = btn.get("callback_data", "")
                self.assertLessEqual(len(cb.encode("utf-8")), 64)
                cb_listesi.append(cb)

        self.assertIn(f"retry_kanal:ig:{hid}", cb_listesi)
        self.assertIn(f"retry_kanal:threads:{hid}", cb_listesi)
        self.assertIn(f"retry_kanal:reels:{hid}", cb_listesi)
        self.assertIn(f"retry_kanal:tiktok:{hid}", cb_listesi)
        self.assertIn(f"retry_kanal:facebook:{hid}", cb_listesi)
        self.assertIn(f"retry_kanal:youtube:{hid}", cb_listesi)
        self.assertIn(f"kurtar:{hid}", cb_listesi)
        self.assertIn(f"incele:{hid}", cb_listesi)

    def test_komutlar_senkronizasyonu_ve_gecerliligi(self):
        """komutlar.py içindeki komutların geçerliliği ve senkronizasyonu test edilir."""
        # 1. MESAJSIZ_KOMUTLAR kontrolü
        beklenen_mesajsiz = {
            "arastir", "dosya", "kronoloji", "link", "ozel",
            "incele", "sonpostlar", "kurtar", "yayin_kontrol",
            "retry_kanal", "ayar", "temizle", "cope_at"
        }
        for k in beklenen_mesajsiz:
            self.assertIn(k, komutlar.MESAJSIZ_KOMUTLAR, f"Eksik mesajsız komut: {k}")

        # 2. KOMUT_MENUSU telegram format doğrulaması (1-32 karakter, a-z0-9_)
        komut_regex = re.compile(r"^[a-z0-9_]{1,32}$")
        menu_komut_isimleri = set()
        for item in komutlar.KOMUT_MENUSU:
            cmd = item["command"]
            desc = item["description"]
            self.assertTrue(komut_regex.match(cmd), f"Geçersiz komut adı formatı: {cmd}")
            self.assertGreater(len(desc), 3, f"Açıklama çok kısa: {desc}")
            menu_komut_isimleri.add(cmd)

        for onemli in ["arastir", "dosya", "incele", "sonpostlar", "ayar", "yayin_kontrol", "kurtar"]:
            self.assertIn(onemli, menu_komut_isimleri, f"Komut menüsünde eksik: {onemli}")

    def test_worker_kritik_komutlari_isliyor(self):
        """Komut ve butonların tek işleyicisi Worker (scripts/telegram_poller.py kaldırıldı:
        webhook açıkken getUpdates 409 döner, poller hiç çalışamıyordu ama bu test onu
        Worker'la senkron tutmaya zorluyordu)."""
        worker_js = (KOK / "worker/index.js").read_text(encoding="utf-8")
        for cmd in ["/arastir", "/dosya", "/incele", "/sonpostlar", "/ayar", "/yayin_kontrol", "/kurtar"]:
            self.assertIn(cmd, worker_js, f"Worker index.js eksik komut: {cmd}")
        for cb in ["ayarsec:", "incele:", "yayin_kontrol:", "kurtar:", "retry_kanal:"]:
            self.assertIn(cb, worker_js, f"Worker index.js eksik callback: {cb}")


if __name__ == "__main__":
    unittest.main()
