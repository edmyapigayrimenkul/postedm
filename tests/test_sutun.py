"""tests/test_sutun.py — kategori alanındaki üç adlandırmadan tek sütun kodu."""

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.sutun import sutun_bul  # noqa: E402


class TestSutun(unittest.TestCase):
    def test_uc_adlandirma_tek_koda_iner(self):
        self.assertEqual(sutun_bul("S4"), "S4")
        self.assertEqual(sutun_bul("S4-005"), "S4")
        self.assertEqual(sutun_bul("TAPU_VE_HUKUK"), "S1")
        self.assertEqual(sutun_bul("FINANS_VE_BANKACILIK"), "S5")

    def test_konu_kodu_kategoriden_once_gelir(self):
        self.assertEqual(sutun_bul("TAPU_VE_HUKUK", "EDM Konu Bankası // S4-011"), "S4")
        self.assertEqual(sutun_bul("REELS", "EDM Konu Bankası // S3-007"), "S3")
        self.assertEqual(sutun_bul(None, "EDM Finans // S5-014"), "S5")

    def test_bilinmiyorsa_uydurulmaz(self):
        self.assertIsNone(sutun_bul("rehber", "Habertürk Ekonomi"))
        self.assertIsNone(sutun_bul(None, None))
        self.assertIsNone(sutun_bul("S9"))
        self.assertIsNone(sutun_bul("BUS1"))


if __name__ == "__main__":
    unittest.main()
