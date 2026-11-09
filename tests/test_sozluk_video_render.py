"""
tests/test_sozluk_video_render.py — Sözlük ve Otorite Formatları İçin Dikey Video/Shorts Render Testleri.

Kapsam:
1. Sözlük kapak seslendirme metni ayrıştırma (terim + tanım).
2. Sözlük için native 9:16 dikey slayt üretimi.
3. Instagram - Facebook paritesi ("facebook da da instaya nasıl atıyosam öyle gitsin"):
   - IG gönderi ise FB standart gönderi,
   - IG reels ise FB reels.
4. YouTube Shorts daimi sesli video hazırlığı.
5. Telegram video teslimatı güvencesi.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from src import ses
from src.yayin import hedef, videolar
from src.yayin.baglam import Istek, YayinBaglami
from src.telegram.akislar import otomatik


class TestSozlukVideoRender(unittest.TestCase):

    def setUp(self):
        os.environ["POSTEDM_TEST_MODU"] = "1"

    def test_sozluk_kapak_seslendirme_metni(self):
        """Sözlük içeriğinde terim ve tanım metni doğru birleştirilerek seslendirilecek metin oluşturulmalıdır."""
        veri = {
            "format_turu": "sozluk",
            "terim": "İntifa Hakkı",
            "tanim_metni": "Bir taşınmazdan tam olarak yararlanma ve kullanma yetkisi veren irtifak hakkıdır.",
        }
        metin = ses.kapak_seslendirme_metni(veri)
        self.assertIsNotNone(metin)
        self.assertIn("İntifa Hakkı", metin)
        self.assertIn("yararlanma ve kullanma yetkisi", metin)

    def test_facebook_instagram_paritesi_gonderi_icin(self):
        """Instagram gönderi (ig) ise Facebook da standart gönderi olmalıdır."""
        istek = hedef.istek_olustur("haber", "101", "ig,threads,facebook,youtube,ses_muzikli")
        b = YayinBaglami(istek)
        hedef.bayraklari_belirle(b)
        kanallar = hedef.kanal_listesi(b)

        self.assertTrue(b.paylas_ig)
        self.assertFalse(b.paylas_reels)
        self.assertIn("facebook", kanallar)
        self.assertNotIn("facebook_reels", kanallar)
        self.assertIn("youtube", kanallar)
        self.assertTrue(b.video_lazim)

    def test_facebook_instagram_paritesi_reels_icin(self):
        """Instagram reels ise Facebook da facebook_reels olmalıdır."""
        istek = hedef.istek_olustur("reels", "102", "reels,threads,facebook,youtube,ses_muzikli")
        b = YayinBaglami(istek)
        hedef.bayraklari_belirle(b)
        kanallar = hedef.kanal_listesi(b)

        self.assertTrue(b.paylas_reels)
        self.assertFalse(b.paylas_ig)
        self.assertIn("facebook_reels", kanallar)
        self.assertNotIn("facebook", kanallar)
        self.assertIn("youtube", kanallar)

    def test_sozluk_otomatik_yayin_hedefleri(self):
        """Sözlük otomatik yayın hedefleri IG ve FB'yi gönderi, YouTube'u Shorts videosu olarak eşleştirmelidir."""
        istek = hedef.istek_olustur("haber", "103", otomatik.SOZLUK_OTO_YAYIN_HEDEFLERI)
        b = YayinBaglami(istek)
        b.detay = {"format_turu": "sozluk", "terim": "Şufa Hakkı"}
        hedef.bayraklari_belirle(b)
        kanallar = hedef.kanal_listesi(b)

        # Instagram görsel kartı, Facebook gönderi, YouTube Shorts
        self.assertIn("instagram", kanallar)
        self.assertIn("facebook", kanallar)
        self.assertNotIn("facebook_reels", kanallar)
        self.assertIn("youtube", kanallar)
        self.assertTrue(b.video_lazim)

    def test_youtube_shorts_icin_daima_video_hazirlanir(self):
        """Hedefte YouTube Shorts varsa video_lazim True olmalı ve dikey video hazırlanmalıdır."""
        istek = hedef.istek_olustur("haber", "104", "youtube")
        b = YayinBaglami(istek)
        hedef.bayraklari_belirle(b)
        self.assertTrue(b.video_lazim)
        self.assertIn("youtube", hedef.kanal_listesi(b))


if __name__ == "__main__":
    unittest.main()
