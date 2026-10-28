"""
tests/test_cizim_paketi.py — src/cizim modüler çizim motoru paket sözleşmesi testleri.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")

import unittest
from pathlib import Path

from src import make_image
import src.cizim as cizim


class TestCizimPaketSozlesmesi(unittest.TestCase):
    """src/cizim altındaki her dosyanın 250 satır kuralına uyduğunu denetler."""

    def test_dosya_satir_sayilari_250_altinda(self):
        kok = Path("src/cizim")
        self.assertTrue(kok.exists() and kok.is_dir(), "src/cizim dizini bulunamadı")
        
        hatali_dosyalar = []
        for py_dosya in kok.glob("*.py"):
            satirlar = py_dosya.read_text(encoding="utf-8").splitlines()
            if len(satirlar) > 250:
                hatali_dosyalar.append(f"{py_dosya.name}: {len(satirlar)} satır (> 250)")

        self.assertEqual(
            hatali_dosyalar,
            [],
            f"src/cizim altında 250 satırı aşan dosyalar var: {hatali_dosyalar}"
        )

    def test_make_image_facade_250_altinda(self):
        mi_dosya = Path("src/make_image.py")
        satirlar = mi_dosya.read_text(encoding="utf-8").splitlines()
        self.assertLessEqual(len(satirlar), 250, f"src/make_image.py 250 satırı aştı: {len(satirlar)}")

    def test_make_image_facade_ana_sembolleri_disa_aktarir(self):
        beklenen_semboller = [
            "tuval",
            "GENISLIK",
            "YUKSEKLIK",
            "TUVAL_OLCULERI",
            "TasmaHatasi",
            "EksikIcerik",
            "otorite_gonderi_slaytlari_uret",
            "haber_dailybrief_slaytlari_uret",
            "haber_dailybrief_slayti_ciz",
            "ilan_kapak_slayti_ciz",
            "ilan_detay_slayti_ciz",
            "ilan_kapanis_slayti_ciz",
            "slayt_tek_fikir",
            "slayt_ikili_fikir",
            "slayt_adim",
            "slayt_kapanis",
            "_metin_sar",
            "_foto_indir_veya_ac",
            "_haber_gorseli_alternatifi",
            "BUYUKLUK_KELIMELERI",
            "AZAMI_SARILACAK",
        ]
        for sembol in beklenen_semboller:
            self.assertTrue(
                hasattr(make_image, sembol),
                f"make_image facade'inde beklenen sembol eksik: {sembol}"
            )


if __name__ == "__main__":
    unittest.main()
