"""
tests/test_gorsel_faz2.py — Görsel Kalite ve Tasarım Motoru Faz 2 Testleri.

Kapsam:
1. Enerji Odaklı Akıllı Kırpma (akilli_odak_x).
2. Metin Bölgesi Dinamik Perde Kontrast Adaptasyonu (dinamik_perde_hesapla).
3. 25 Görsellik Genişletilmiş Yerel Tematik Stok Havuzu doğrulaması.
4. Otorite Kapak ve Haber Kapak çizimlerinin dinamik adaptasyon ile doğrulanması.
"""

from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest.mock import patch
from PIL import Image, ImageDraw

from src import config, gorsel_kalite
from src.cizim import stok, otorite_kapak, haber_kapak
from src.cizim.tuval import dinamik_perde_hesapla


class TestGorselFaz2(unittest.TestCase):

    def setUp(self):
        os.environ["POSTEDM_TEST_MODU"] = "1"

    def test_akilli_odak_x_dikey_gorsel_merkez_doner(self):
        """Dikey (portre) görsellerde yatay kırpma yapılmadığı için merkez (0.5) döner."""
        img = Image.new("RGB", (800, 1200), (100, 100, 100))
        odak = gorsel_kalite.akilli_odak_x(img)
        self.assertEqual(odak, 0.5)

    def test_akilli_odak_x_sol_ve_sag_agirlikli_enerji(self):
        """Solunda veya sağında yoğun kenar enerjisi olan yatay fotoğrafta odak doğru tarafa kaymalıdır."""
        # Solda bina/kenar olan 16:9 görsel (1600x900)
        img_sol = Image.new("RGB", (1600, 900), (220, 220, 220))
        draw_sol = ImageDraw.Draw(img_sol)
        for x in range(100, 400, 15):
            draw_sol.line([(x, 100), (x, 800)], fill=(20, 20, 20), width=4)
        odak_sol = gorsel_kalite.akilli_odak_x(img_sol)
        self.assertLess(odak_sol, 0.45, f"Soldaki bina için odak < 0.45 olmalıydı: {odak_sol}")
        self.assertGreaterEqual(odak_sol, 0.25)

        # Sağda bina/kenar olan 16:9 görsel
        img_sag = Image.new("RGB", (1600, 900), (220, 220, 220))
        draw_sag = ImageDraw.Draw(img_sag)
        for x in range(1200, 1500, 15):
            draw_sag.line([(x, 100), (x, 800)], fill=(20, 20, 20), width=4)
        odak_sag = gorsel_kalite.akilli_odak_x(img_sag)
        self.assertGreater(odak_sag, 0.55, f"Sağdaki bina için odak > 0.55 olmalıydı: {odak_sag}")
        self.assertLessEqual(odak_sag, 0.75)

    def test_akilli_odak_x_homojen_gorselde_merkez(self):
        """Düz renk veya kenar olmayan görselde merkez (0.5) döner."""
        img = Image.new("RGB", (1200, 800), (150, 150, 150))
        self.assertEqual(gorsel_kalite.akilli_odak_x(img), 0.5)

    def test_dinamik_perde_kontrast_adaptasyonu(self):
        """Alt metin bölgesinin parlaklığına göre dinamik perde parametreleri doğru uyarlanmalıdır."""
        # 1. Beyaz / Parlak arka plan (Luminance > 125) -> Güçlü perde (WCAG AAA)
        canvas_parlak = Image.new("RGB", (1080, 1350), (240, 240, 240))
        p_alfa, max_a, ofs_y = dinamik_perde_hesapla(canvas_parlak, baslangic_y=600)
        self.assertEqual(p_alfa, 215)
        self.assertEqual(max_a, 255)
        self.assertEqual(ofs_y, 30)

        # 2. Karanlık / Gece arka planı (Luminance < 55) -> Hafif perde
        canvas_koyu = Image.new("RGB", (1080, 1350), (20, 25, 30))
        p_alfa_k, max_a_k, ofs_y_k = dinamik_perde_hesapla(canvas_koyu, baslangic_y=600)
        self.assertEqual(p_alfa_k, 165)
        self.assertEqual(max_a_k, 238)
        self.assertEqual(ofs_y_k, 0)

        # 3. Dengeli / Orta gri zemin
        canvas_orta = Image.new("RGB", (1080, 1350), (100, 100, 100))
        p_alfa_o, max_a_o, ofs_y_o = dinamik_perde_hesapla(canvas_orta, baslangic_y=600)
        self.assertEqual(p_alfa_o, 185)
        self.assertEqual(max_a_o, 252)
        self.assertEqual(ofs_y_o, 10)

    def test_arka_plan_havuzu_25_gorseli_kapsar(self):
        """assets/backgrounds/ altındaki 25 HD görselin tamamı ARKA_PLAN_HAVUZU içinde yer almalıdır."""
        bg_dir = config.yol_al("assets/backgrounds")
        if not bg_dir.exists():
            self.skipTest("assets/backgrounds dizini bulunamadı")

        disk_dosyalari = {p.name for p in bg_dir.glob("*.jpg")}
        self.assertEqual(len(disk_dosyalari), 25, f"Diskte 25 görsel bekleniyordu, {len(disk_dosyalari)} bulundu")

        havuz_tum_dosyalar = set()
        for kategori, dosyalar in stok.ARKA_PLAN_HAVUZU.items():
            havuz_tum_dosyalar.update(dosyalar)

        eksik_dosyalar = disk_dosyalari - havuz_tum_dosyalar
        self.assertEqual(len(eksik_dosyalar), 0, f"Havuzda eksik kalan görseller: {eksik_dosyalar}")

    def test_temiz_arkaplan_al_tum_kategorilerde_calisir(self):
        """Her kategori için _temiz_arkaplan_al fonksiyonu akıllı kırpma ile geçerli tuval döner."""
        for kat in ("ARSA", "KONUT", "BINA", "ICMEKAN", "INSAAT"):
            img = stok._temiz_arkaplan_al(kategori_kodu=kat)
            self.assertIsInstance(img, Image.Image)
            self.assertEqual(img.size, (1080, 1350))

    def test_otorite_kapak_cizim_dinamik_perde_ile_calisir(self):
        """Otorite kapak çizimi dinamik perde ve akıllı kırpma ile hatasız çalışmalıdır."""
        veri = {
            "kategori_kodu": "ARSA",
            "manset_parca_1": "Hisseli Tapuda",
            "manset_vurgu": "ŞUFA HAKKI",
            "manset_parca_2": "Nasıl Kullanılır?",
            "spot": "Hissedarlardan birinin payını üçüncü kişiye satması durumunda diğer hissedarların yasal önalım hakkı bulunur.",
            "rozet_metni": "EDM HUKUK // GAYRİMENKUL",
        }
        cikti = otorite_kapak.otorite_slayt_1_kapak(veri)
        self.assertTrue(Path(cikti).exists())
        self.assertGreater(Path(cikti).stat().st_size, 50000)

    def test_haber_kapak_cizim_akilli_sigdir_ile_calisir(self):
        """Haber kapak çizimi akıllı kırpma ve dinamik perde ile hatasız çalışmalıdır."""
        haber = {
            "id": "test_hb_01",
            "kategori": "ARSA",
            "baslik": "Silivri Çanta Köyü İmar Planı Değişikliği Askıya Çıktı",
            "manset": "Silivri Çanta Köyü İmar Planı Askıda",
            "spot": "Çevre, Şehircilik ve İklim Değişikliği Bakanlığı tarafından onaylanan yeni 1/5000 ölçekli nazım imar planı muhtarlıkta askıya çıkarıldı.",
            "kaynak": "Silivri Belediyesi",
        }
        cikti = haber_kapak.haber_dailybrief_slayti_ciz(haber)
        self.assertTrue(Path(cikti).exists())
        self.assertGreater(Path(cikti).stat().st_size, 50000)


if __name__ == "__main__":
    unittest.main()
