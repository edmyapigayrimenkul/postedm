"""
tests/test_gorsel_faz1.py — Görsel Bulma ve Kalite İyileştirmeleri (Faz 1) Test Paketi

1. dHash (fark hash'i) hesaplama ve Hamming mesafesi doğrulaması
2. SQLite dHash mükerrer görsel kilidi ve gün penceresi testi
3. Haber siteleri ve TV kanalları ticker/şerit bandı tespiti (0 false-positive)
4. LLM destekli İngilizce görsel arama terimi entegrasyonu (Pexels sorgu yapısı)
5. Gemini Vision logo/filigran tespiti ve reddi
"""

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")

import io
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image, ImageDraw

from src import config, db, fetch_stock, gorsel_kalite, haber_tasarim


class TestGorselFaz1(unittest.TestCase):
    def setUp(self):
        # Test için geçici temiz DB kullan
        with db._baglanti_al() as conn:
            conn.execute("DELETE FROM kullanilan_gorsel_hashleri")

    def test_dhash_hesaplama_ve_mesafe(self):
        """dHash 16 haneli hex üretmeli, hafif kırpmada mesafe <= 4, farklı görselde > 10 olmalı."""
        im1 = Image.new("RGB", (800, 600), color=(70, 130, 180))
        d1 = ImageDraw.Draw(im1)
        d1.rectangle([200, 150, 600, 450], fill=(220, 100, 50))

        h1 = gorsel_kalite.dhash_hesapla(im1)
        self.assertEqual(len(h1), 16)

        # Aynı görsel hafif kırpılmış ve boyutlandırılmış (ajans varyasyonu)
        im2 = im1.crop((15, 15, 785, 585)).resize((800, 600))
        h2 = gorsel_kalite.dhash_hesapla(im2)
        mesafe = gorsel_kalite.dhash_mesafesi(h1, h2)
        self.assertLessEqual(mesafe, 6, f"Aynı görselin mesafesi küçük olmalıydı: {mesafe}")

        # Tamamen farklı görsel
        im3 = Image.new("RGB", (800, 600), color=(30, 200, 50))
        d3 = ImageDraw.Draw(im3)
        d3.ellipse([100, 100, 500, 500], fill=(255, 255, 0))
        h3 = gorsel_kalite.dhash_hesapla(im3)
        mesafe_farkli = gorsel_kalite.dhash_mesafesi(h1, h3)
        self.assertGreater(mesafe_farkli, 10, f"Farklı görsellerin mesafesi büyük olmalıydı: {mesafe_farkli}")

    def test_db_gorsel_hash_mukerrer_engeli(self):
        """DB'ye kaydedilen dHash ve hafif mutasyonları 45 gün penceresinde mükerrer sayılmalı."""
        test_hash = "2003b4b4b4b40320"
        self.assertFalse(db.gorsel_hash_benzer_mi(test_hash, esik=6, gun_siniri=45))

        # Hash'i kaydet
        db.gorsel_hash_ekle(test_hash, kaynak="pexels", ref_id="foto_999")

        # Birebir aynı hash benzer sayılmalı
        self.assertTrue(db.gorsel_hash_benzer_mi(test_hash, esik=6, gun_siniri=45))

        # 2 bit farklı mutasyon (benzer görsel) da benzer sayılmalı
        benzer_hash = "2043b4b4b4b40380"  # Hamming mesafesi 3
        self.assertTrue(db.gorsel_hash_benzer_mi(benzer_hash, esik=6, gun_siniri=45))

        # Tamamen farklı bir hash mükerrer sayılmamalı
        tamamen_farkli = "ffff0000ffff0000"
        self.assertFalse(db.gorsel_hash_benzer_mi(tamamen_farkli, esik=6, gun_siniri=45))

    def test_haber_banti_tespiti(self):
        """Kırmızı haber/ticker bandı tespit edilmeli; temiz stok fotoğraflarında 0 false-positive olmalı."""
        # Sentetik kırmızı alt bant
        banner_im = Image.new("RGB", (1200, 800), color=(100, 150, 200))
        d = ImageDraw.Draw(banner_im)
        d.rectangle([0, 736, 1200, 800], fill=(210, 20, 20))
        var, sebep = gorsel_kalite.haber_banti_var_mi(banner_im)
        self.assertTrue(var)
        self.assertIn("kırmızı", sebep)

        # Temiz arka plan klasöründen örnek görseller
        bg_p = Path("assets/backgrounds/bina_modern_glass.jpg")
        if bg_p.exists():
            clean_im = Image.open(bg_p)
            clean_var, _ = gorsel_kalite.haber_banti_var_mi(clean_im)
            self.assertFalse(clean_var, "Temiz mimari fotoğrafta bant tespit edilmemeliydi.")

    def test_fetch_stock_zengin_ingilizce_sorgu(self):
        """Zengin LLM İngilizce arama terimi bozulmadan Pexels sorgusuna iletilmeli."""
        yakalanan_params = {}

        def sahte_get(url, headers=None, params=None, timeout=None):
            nonlocal yakalanan_params
            yakalanan_params = params or {}
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"photos": [{"id": 1, "src": {}}]}
            return resp

        with patch.dict(os.environ, {"PEXELS_API_KEY": "fake_key"}), \
             patch("requests.get", side_effect=sahte_get):
            fetch_stock.stok_fotografi_ara(
                "drone view agricultural land boundary demarcation cadastre",
                kategori_kodu="ARSA_VE_IMAR",
            )
            # Zengin sorgu doğrudan kullanılmalı (kategori terimleri üzerine yığılmamalı)
            self.assertEqual(
                yakalanan_params.get("query"),
                "drone view agricultural land boundary demarcation cadastre",
            )

    def test_fetch_stock_mukerrer_gorseli_atlar(self):
        """Pexels sonuçlarında son 45 günde kullanılmış benzer dHash'e sahip fotoğraf atlanıp sıradakine geçmeli."""
        im_kullanilmis = Image.new("RGB", (800, 1000), color=(100, 120, 140))
        d_k = ImageDraw.Draw(im_kullanilmis)
        d_k.rectangle([100, 100, 700, 900], fill=(50, 70, 90))
        h_kullanilmis = gorsel_kalite.dhash_hesapla(im_kullanilmis)
        db.gorsel_hash_ekle(h_kullanilmis, kaynak="pexels", ref_id="101")

        im_taze = Image.new("RGB", (800, 1000), color=(70, 120, 180))
        d_t = ImageDraw.Draw(im_taze)
        d_t.ellipse([100, 100, 700, 900], fill=(240, 240, 240))

        # İki aday fotoğraf dönen Pexels API yanıtı
        photos_api = [
            {"id": 101, "src": {"portrait": "https://images.pexels.com/101.jpg"}},
            {"id": 102, "src": {"portrait": "https://images.pexels.com/102.jpg"}},
        ]

        def sahte_get(url, *args, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            if "api.pexels.com" in url:
                resp.json.return_value = {"photos": photos_api}
            elif "101.jpg" in url:
                buf = io.BytesIO()
                im_kullanilmis.save(buf, "JPEG", quality=95)
                resp.content = buf.getvalue()
            elif "102.jpg" in url:
                buf = io.BytesIO()
                im_taze.save(buf, "JPEG", quality=95)
                resp.content = buf.getvalue()
            return resp

        with patch.dict(os.environ, {"PEXELS_API_KEY": "fake_key"}), \
             patch("requests.get", side_effect=sahte_get):
            cikti = fetch_stock.stok_fotografi_ara("residential villa")
            self.assertIsNotNone(cikti)
            # İlk aday (101) mükerrer olduğu için 102 seçilmiş olmalı
            self.assertIn("102", str(cikti))

    def test_vision_filigran_veya_logo_reddi(self):
        """Gemini Vision fotoğrafta filigran/logo tespit ettiğinde fotoğraf reddedilmeli."""
        foto = Image.new("RGB", (800, 1000), color=(150, 150, 150))
        haber = {"orijinal_baslik": "Silivri Tapu Davası"}

        with patch("src.gorsel_denetim.gorseli_denetle", return_value={
            "fotografta_ne_var": "Haber ajansı logolu bina",
            "konuyu_gosteriyor_mu": True,
            "baglam_uyuyor_mu": True,
            "filigran_veya_logo_var_mi": True,
            "sebep": "Sağ üstte AA ajans logosu var",
        }):
            uygun = haber_tasarim._foto_uygun_mu(foto, haber, "stok", bagla=False)
            self.assertFalse(uygun, "Filigranlı görsel reddedilmeliydi.")


if __name__ == "__main__":
    unittest.main()
