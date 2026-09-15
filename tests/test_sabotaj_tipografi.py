"""
test_sabotaj_tipografi.py — Tipografi, Para Birimi & Unvan Bütünlüğü Sabotaj Testleri
Instabot / Daily Brief test_sabotaj_tipografi.py mimarisinden uyarlanmıştır.

Bu test modülü Doğukan'ın bildirdiği sorunları agresif senaryolarla sınar:
  1. ₺ sembolünün önceki sayıdan ayrılmaması (asla satır başında yetim ₺ kalmaz)
  2. Büyüklük + Para birimi üçlüsünün (350 bin ₺) kopmaması
  3. Unvanların (Doç., Dr., Av., No.) satır sonu ve sayfa geçişinde bölünmemesi
  4. Sıra sayılarının (14. cadde, 3. sokak) satır sonunda tek kalmaması
  5. filtre modülü tipografi ve kaçış dizisi temizliği
"""

import re
import unittest
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from src import filtre
from src.make_image import (
    _metin_sar,
    _font_yukle,
    FONT_MONO,
    FONT_MONO_BOLD,
    _is_para_birimi,
    _is_sayi,
    _is_unvan_veya_on_ek,
)

DUMMY_IMG = Image.new("RGB", (1080, 1350))
DUMMY_DRAW = ImageDraw.Draw(DUMMY_IMG)
TEST_FONT = _font_yukle(FONT_MONO, 32)


class TestSabotajTipografi(unittest.TestCase):
    def test_sabotaj_tl_sembolu_rakamdan_kopmaz(self):
        """1. Sabotaj: 2.500 ₺ ifadesinde ₺ sembolü yeni satıra tek başına düşemez."""
        metin = "Silivri Selimpaşa'da arsa metrekare fiyatı 2.500 ₺ olarak belirlendi."
        w_2500 = DUMMY_DRAW.textbbox((0, 0), "Silivri Selimpaşa'da arsa metrekare fiyatı 2.500", font=TEST_FONT)[2]
        w_tam = DUMMY_DRAW.textbbox((0, 0), "Silivri Selimpaşa'da arsa metrekare fiyatı 2.500 ₺", font=TEST_FONT)[2]

        azami_w = int(w_2500 + (w_tam - w_2500) / 2)
        satirlar = _metin_sar(metin, TEST_FONT, azami_w, DUMMY_DRAW)

        self.assertGreaterEqual(len(satirlar), 2)
        for i, s in enumerate(satirlar):
            kelimeler = s.split()
            if kelimeler and kelimeler[0] == "₺":
                self.fail(f"Satır {i+1} yetim ₺ ile başladı! Satırlar: {satirlar}")

        # 2.500 ve ₺ aynı satırda olmalı
        tl_satiri = [s for s in satirlar if "₺" in s][0]
        self.assertIn("2.500 ₺", tl_satiri, f"2.500 ve ₺ birbirinden ayrılmış: {satirlar}")

    def test_sabotaj_buyukluk_ve_para_birimi_kopmaz(self):
        """2. Sabotaj: 350 bin ₺ ifadesinde ₺ veya bin ₺ tek başına kopamaz."""
        metin = "Toplam yatırım bedeli 350 bin ₺ seviyesine ulaştı."
        w_350 = DUMMY_DRAW.textbbox((0, 0), "Toplam yatırım bedeli 350", font=TEST_FONT)[2]
        w_350_bin = DUMMY_DRAW.textbbox((0, 0), "Toplam yatırım bedeli 350 bin", font=TEST_FONT)[2]
        w_tam = DUMMY_DRAW.textbbox((0, 0), "Toplam yatırım bedeli 350 bin ₺", font=TEST_FONT)[2]

        # ₺'nin sığmayacağı sınır
        azami_w = int(w_350_bin + (w_tam - w_350_bin) / 2)
        satirlar = _metin_sar(metin, TEST_FONT, azami_w, DUMMY_DRAW)

        self.assertGreaterEqual(len(satirlar), 2)
        for s in satirlar:
            self.assertFalse(s.startswith("₺"), f"Satır yetim ₺ ile başladı: {satirlar}")

        satir_str = " ".join([s for s in satirlar if "350" in s or "bin" in s or "₺" in s])
        self.assertTrue("350 bin ₺" in satirlar[0] or "350 bin ₺" in satirlar[1], f"350 bin ₺ bölünmüş: {satirlar}")

    def test_sabotaj_unvan_ve_kisaltmalar_kopmaz(self):
        """3. Sabotaj: Doç. Dr. veya Av. kısaltmaları satır sonunda tek başına kalamaz."""
        metin = "Gayrimenkul hukukunda uzman Av. Mehmet Demir açıklama yaptı."
        w_av = DUMMY_DRAW.textbbox((0, 0), "Gayrimenkul hukukunda uzman Av.", font=TEST_FONT)[2]
        w_tam = DUMMY_DRAW.textbbox((0, 0), "Gayrimenkul hukukunda uzman Av. Mehmet", font=TEST_FONT)[2]

        azami_w = int(w_av + (w_tam - w_av) / 2)
        satirlar = _metin_sar(metin, TEST_FONT, azami_w, DUMMY_DRAW)

        self.assertGreaterEqual(len(satirlar), 2)
        ilk_satir = satirlar[0].strip()
        self.assertFalse(ilk_satir.endswith("Av."), f"Satır sonunda yetim unvan kaldı: {satirlar}")
        self.assertIn("Av. Mehmet", " ".join(satirlar))

    def test_sabotaj_sira_sayilari_kopmaz(self):
        """4. Sabotaj: 14. cadde ifadesinde '14.' satır sonunda tek kalamaz."""
        metin = "Silivri merkezindeki 14. parselde inşaat başladı."
        w_14 = DUMMY_DRAW.textbbox((0, 0), "Silivri merkezindeki 14.", font=TEST_FONT)[2]
        w_tam = DUMMY_DRAW.textbbox((0, 0), "Silivri merkezindeki 14. parselde", font=TEST_FONT)[2]

        azami_w = int(w_14 + (w_tam - w_14) / 2)
        satirlar = _metin_sar(metin, TEST_FONT, azami_w, DUMMY_DRAW)

        self.assertGreaterEqual(len(satirlar), 2)
        ilk_satir = satirlar[0].strip()
        self.assertFalse(ilk_satir.endswith("14."), f"Satır sonunda yetim sıra sayısı kaldı: {satirlar}")
        self.assertIn("14. parselde", " ".join(satirlar))

    def test_filtre_tipografi_temizligi(self):
        """5. Test: Sayı, TL ve yüzde standartları temizlenir."""
        ham = "Silivri'de arsa için 2 bin 410 metrekare alanda yüzde 25 imar ve 7,76 TL fiyat açıklandı."
        temiz = filtre.tipografi_temizle(ham)
        self.assertIn("2.410", temiz)
        self.assertIn("%25", temiz)
        self.assertIn("7,76 ₺", temiz)

    def test_filtre_markdown_ve_kacis_temizligi(self):
        """6. Test: **bold** temizlenir ama #hashtag korunur, literal \\n gerçek satıra döner."""
        ham = "## Önemli Duyuru\\n\\n**EDM Yapı** ile **arsa** yatırımı. #Silivri #Emlak"
        temiz = filtre.markdown_temizle(ham)
        self.assertNotIn("**", temiz)
        self.assertNotIn("##", temiz)
        self.assertIn("#Silivri", temiz)
        self.assertIn("#Emlak", temiz)
        self.assertIn("EDM Yapı", temiz)


if __name__ == "__main__":
    unittest.main()
