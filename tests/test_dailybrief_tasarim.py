"""
tests/test_dailybrief_tasarim.py — Instabot DailyBrief Haber Tasarımı ve Sabotaj Testleri
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from PIL import Image

from src import make_image


class TestDailyBriefTasarim(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

        # Örnek test görseli
        self.test_foto = self.tmp_path / "foto.jpg"
        im = Image.new("RGB", (1200, 800), color="darkblue")
        im.save(self.test_foto, "JPEG")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_haber_dailybrief_besleme_olcusu(self):
        """Besleme modunda 1080x1350 piksel boyutunda üretilmeli."""
        haber = {
            "manset": "Silivri İmar Planı Askıya Çıktı",
            "spot": "Yeni düzenlemeyle birlikte tarım arazilerinde yapılaşma koşulları netleşti.",
            "kategori": "ARSA_VE_IMAR",
            "kaynak": "Emlakkulisi",
        }
        cikti = self.tmp_path / "dailybrief_besleme.jpg"
        res = make_image.haber_dailybrief_slayti_ciz(
            haber,
            foto_yolu=self.test_foto,
            cikti_yolu=cikti,
            olcu="besleme",
        )
        self.assertTrue(cikti.exists())
        im = Image.open(res)
        self.assertEqual(im.size, (1080, 1350))

    def test_haber_dailybrief_story_olcusu(self):
        """Story modunda 1080x1920 piksel boyutunda üretilmeli."""
        haber = {
            "manset": "Tapu Harcında 2026 Beyan Zorunluluğu",
            "spot": "Eksik beyan edilen tapu devirlerinde vergi ziyaı cezası uygulanacak.",
            "kategori": "TAPU_VE_HUKUK",
            "kaynak": "Resmi Gazete",
        }
        cikti = self.tmp_path / "dailybrief_story.jpg"
        res = make_image.haber_dailybrief_slayti_ciz(
            haber,
            foto_yolu=self.test_foto,
            cikti_yolu=cikti,
            olcu="story",
        )
        self.assertTrue(cikti.exists())
        im = Image.open(res)
        self.assertEqual(im.size, (1080, 1920))

    def test_haber_dailybrief_sabotaj_ve_eksik_alanlar(self):
        """Fotoğraf yolu yokken ve alanlar boşken çökmeden yedek zeminle üretilmeli."""
        haber_bos = {
            "manset": None,
            "spot": "",
            "kategori": None,
        }
        cikti = self.tmp_path / "dailybrief_sabotaj.jpg"
        res = make_image.haber_dailybrief_slayti_ciz(
            haber_bos,
            foto_yolu=self.tmp_path / "olmayan_foto.jpg",
            cikti_yolu=cikti,
            olcu="besleme",
        )
        self.assertTrue(cikti.exists())
        im = Image.open(res)
        self.assertEqual(im.size, (1080, 1350))

    def test_haber_dailybrief_stres_asiri_uzun_metin(self):
        """Çok uzun metin geldiğinde taşma yapmadan 3 satırda kırparak sığdırmalı."""
        haber_uzun = {
            "manset": "Silivri Selimpaşa'da Hisseli Tarla Satışlarında Yaşanan Önalım Şufa Davaları ve Hukuki İhtilaflar Hakkında Bilinmesi Gereken En Önemli Ayrıntılar",
            "spot": "Bu çok uzun bir spot metnidir ve defalarca tekrarlanarak " * 10,
            "kategori": "KENTSEL_DONUSUM",
            "kaynak": "Çevre ve Şehircilik Bakanlığı",
        }
        cikti = self.tmp_path / "dailybrief_stres.jpg"
        res = make_image.haber_dailybrief_slayti_ciz(
            haber_uzun,
            foto_yolu=self.test_foto,
            cikti_yolu=cikti,
            olcu="story",
        )
        self.assertTrue(cikti.exists())
        im = Image.open(res)
        self.assertEqual(im.size, (1080, 1920))


if __name__ == "__main__":
    unittest.main()
