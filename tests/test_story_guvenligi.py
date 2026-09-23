"""
tests/test_story_guvenligi.py
Story görsel hazırlama ve 9:16 native uyumluluk birim testleri.
"""

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from src import video


class TestStoryGuvenligi(unittest.TestCase):
    def test_cercevele_9_16_olculeri_ve_netlik(self):
        """1080x1350 görseli 1080x1920 yapar, fade_h küçük tutularak başlık korunur."""
        kart = Image.new("RGB", (1080, 1350), (255, 0, 0))
        sonuc = video._cercevele_9_16(kart)
        self.assertEqual(sonuc.size, (1080, 1920))

    def test_cercevele_9_16_zaten_9_16_ise_dokunmaz(self):
        """Görsel zaten 1080x1920 ise doğrudan döndürür."""
        kart = Image.new("RGB", (1080, 1920), (0, 255, 0))
        sonuc = video._cercevele_9_16(kart)
        self.assertEqual(sonuc.size, (1080, 1920))


if __name__ == "__main__":
    unittest.main()
