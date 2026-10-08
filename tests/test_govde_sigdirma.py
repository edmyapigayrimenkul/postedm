"""
tests/test_govde_sigdirma.py — Gövde metni sığdırma: kelimeyi bölmeden önce yazıyı küçült (2026-10-08).

Sözlük kartlarının çizimi denenirken görüldü: dar alana uzun bir kelime düşünce eski sığdırma kelimeyi
ORTASINDAN bölüp ("Sorumluluk-larından") büyük punto ile devam ediyordu. Doğrusu önce puntoyu düşürüp
kelimeyi bütün tutmak; kelime en küçük puntoda bile sığmazsa son çare olarak bölünür ve satır alandan
taşmaz. Ağ yok, yalnız yazı tipi ölçümü.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import unittest

from PIL import Image, ImageDraw

from src import make_image as mi

DRAW = ImageDraw.Draw(Image.new("RGB", (1080, 1350)))
YOL = mi.FONT_SANS_MEDIUM
UZUN_KELIME = "Sorumluluklarından"


def _genislik(metin: str, boyut: int) -> int:
    return DRAW.textbbox((0, 0), metin, font=mi._font_yukle(YOL, boyut))[2]


class TestMetinSar(unittest.TestCase):
    def setUp(self):
        self.font = mi._font_yukle(YOL, 60)
        # kelime tek başına bile 60 punto ile bu alana sığmaz
        self.alan = _genislik(UZUN_KELIME, 60) - 80

    def test_varsayilan_sigmayan_kelimeyi_boler(self):
        satirlar = mi._metin_sar(UZUN_KELIME, self.font, self.alan, DRAW)
        self.assertGreater(len(satirlar), 1)
        self.assertEqual("".join(satirlar).replace("-", ""), UZUN_KELIME)

    def test_kelime_bol_kapaliyken_kelime_butun_kalir(self):
        satirlar = mi._metin_sar(UZUN_KELIME, self.font, self.alan, DRAW, kelime_bol=False)
        self.assertEqual(satirlar, [UZUN_KELIME])

    def test_kelime_bol_kapaliyken_diger_kelimeler_yine_sarilir(self):
        metin = f"Bu madde {UZUN_KELIME} söz eder ve ayrıca birkaç kelime daha içerir"
        satirlar = mi._metin_sar(metin, self.font, self.alan, DRAW, kelime_bol=False)
        self.assertIn(UZUN_KELIME, satirlar)       # kelime kendi satırında bütün
        self.assertEqual(" ".join(satirlar), metin)  # hiçbir kelime kaybolmadı ya da bölünmedi


class TestGovdeSigdir(unittest.TestCase):
    def test_once_punto_dusurulur_kelime_bolunmez(self):
        alan = _genislik(UZUN_KELIME, 44) + 4           # 44 puntoda sığar, 60'ta sığmaz
        font, satirlar = mi._govde_sigdir(UZUN_KELIME, YOL, 60, 20, alan, 3, DRAW)
        self.assertEqual(satirlar, [UZUN_KELIME])
        self.assertLessEqual(font.size, 44)
        self.assertGreater(font.size, 20)              # gereğinden fazla küçültülmedi

    def test_tum_satirlar_alana_sigar(self):
        metin = f"{UZUN_KELIME} ve kısa kelimeler birlikte yazılırsa ne olur"
        alan = _genislik(UZUN_KELIME, 40) + 4
        font, satirlar = mi._govde_sigdir(metin, YOL, 60, 20, alan, 6, DRAW)
        self.assertTrue(all(_genislik(s, font.size) <= alan for s in satirlar), satirlar)
        self.assertIn(UZUN_KELIME, satirlar)

    def test_en_kucuk_puntoda_bile_sigmayan_kelime_son_care_bolunur(self):
        alan = _genislik(UZUN_KELIME, 20) - 40          # 20 puntoda bile sığmaz
        font, satirlar = mi._govde_sigdir(UZUN_KELIME, YOL, 60, 20, alan, 3, DRAW)
        self.assertEqual(font.size, 20)
        self.assertGreater(len(satirlar), 1)
        self.assertTrue(all(_genislik(s, font.size) <= alan for s in satirlar), satirlar)

    def test_rahat_sigan_metin_baslangic_puntosunda_kalir(self):
        metin = "Kısa bir cümle."
        font, satirlar = mi._govde_sigdir(metin, YOL, 40, 20, 1000, 3, DRAW)
        self.assertEqual(font.size, 40)
        self.assertEqual(satirlar, [metin])

    def test_satir_siniri_asilinca_punto_dusurulur(self):
        metin = " ".join(["kelime"] * 18)
        font, satirlar = mi._govde_sigdir(metin, YOL, 50, 20, 600, 3, DRAW)
        self.assertLessEqual(len(satirlar), 3)
        self.assertLess(font.size, 50)
        self.assertGreater(font.size, 20)


if __name__ == "__main__":
    unittest.main()
