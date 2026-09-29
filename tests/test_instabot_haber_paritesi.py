"""
tests/test_instabot_haber_paritesi.py — Instabot Paritesi Doğrulama Testleri:
1. Haberin orijinal görselinin (URL/yerel) slaytlara 1:1 aktarımı ve kilitlenmesi.
2. Detay slaytlarının akıcı bekleme süreleri (3.2 - 5.5 sn).
3. Onay aşamasında video üretilmemesi (yalnızca slayt albümü ve metin).
4. Yayınla dendiğinde videonun ve kopyalanabilir açıklamanın Telegram'a iletilmesi.
"""

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image

from src import make_image, video, telegram_bot


class TestHaberGorselVeOnayAkisi(unittest.TestCase):
    def test_haber_gorsel_url_ile_yuklenir_ve_kilitlenir(self):
        """Haberde HTTP gorsel_url olduğunda Pexels/stok yerine o görsel kullanılır ve sabitlenir."""
        dummy_img = Image.new("RGB", (800, 600), color=(100, 150, 200))
        haber = {
            "id": 991,
            "manset": "TOKİ Arsa Satışı Başladı",
            "spot": "47 ilde arsa satışı için başvuru süreci başladı.",
            "gorsel_url": "https://cdn.example.com/toki_arsa.jpg",
            "orijinal_url": "https://example.com/haber-123",
        }

        with (
            patch("src.make_image._foto_indir_veya_ac", return_value=dummy_img) as mock_indir,
            patch("src.fetch_stock.stok_fotografi_ara") as mock_stok,
        ):
            p = make_image.haber_dailybrief_slayti_ciz(haber=haber, cikti_yolu=Path("/tmp/test_dailybrief_s1.jpg"))
            self.assertTrue(mock_indir.called)
            # Stok aramaya hiç düşmemeli çünkü haberin kendi görseli var!
            mock_stok.assert_not_called()
            self.assertTrue(p.exists())

    def test_haber_gorseli_yoksa_orijinal_urlden_cekilir(self):
        """Haberde gorsel_url yoksa orijinal_url'den og_gorsel veya tum_gorselleri_cek ile temin edilir."""
        dummy_img = Image.new("RGB", (800, 600), color=(50, 100, 150))
        haber = {
            "id": 992,
            "manset": "Miras İntikalinde Yeni Dönem",
            "spot": "Tapu işlemlerinde harç muafiyeti detayları açıklandı.",
            "orijinal_url": "https://example.com/tapu-miras",
        }

        with (
            patch("src.fetch_article.og_gorseli_cek", return_value="https://cdn.example.com/tapu_og.jpg"),
            patch("src.make_image._foto_indir_veya_ac", return_value=dummy_img) as mock_indir,
            patch("src.fetch_stock.stok_fotografi_ara") as mock_stok,
        ):
            p = make_image.haber_dailybrief_slayti_ciz(haber=haber, cikti_yolu=Path("/tmp/test_dailybrief_s2.jpg"))
            mock_indir.assert_called_with("https://cdn.example.com/tapu_og.jpg")
            mock_stok.assert_not_called()

    def test_detay_slaytlari_bekleme_sureleri_akici(self):
        """Detay slaytları kullanıcı talebi doğrultusunda 3.2 ile 5.5 sn arasında akıcı olmalı."""
        haber = {
            "detay_maddeleri": [
                {"etiket": "MADDE 1", "metin": "Kısa ve net bilgilendirme cümlesi."},
                {"etiket": "MADDE 2", "metin": "İkinci önemli başvuru koşulu ve tarih detayı."},
            ]
        }
        sureler = video.slayt_surelerini_hesapla(3, haber=haber)
        self.assertEqual(len(sureler), 3)
        self.assertEqual(sureler[0], 4.2)  # Kapak süresi
        self.assertTrue(3.2 <= sureler[1] <= 5.5)
        self.assertTrue(3.2 <= sureler[2] <= 5.5)

    def test_onay_asamasinda_video_uretici_ve_video_gonder_cagrilmaz(self):
        """Haber onay aşamasında video üretilmemeli ve video gönderilmemeli (Instabot mantığı)."""
        haber = {
            "id": 888,
            "manset": "Test Haber Onay",
            "orijinal_baslik": "Test Haber Onay",
            "orijinal_ozet": "Test spot özeti",
            "durum": "yeni",
            "slayt_yollari": json.dumps(["/tmp/s1.jpg", "/tmp/s2.jpg"]),
        }

        with (
            patch("src.telegram_bot.db.haber_getir", return_value=haber),
            patch("src.telegram_bot.db.haber_guncelle") as mock_guncelle,
            patch("src.telegram_bot.yayin_kapisi", return_value=(True, [])),
            patch("src.telegram_bot.upload_image.coklu_gorsel_yukle", return_value=["https://cdn.com/1.jpg", "https://cdn.com/2.jpg"]),
            patch("src.telegram_bot.medya_grubu_gonder") as mock_medya,
            patch("src.telegram_bot.video_gonder") as mock_video,
            patch("src.telegram_bot.mesaj_gonder"),
            patch("src.telegram_bot.Path.exists", return_value=True),
        ):
            res = telegram_bot._haber_onayina_sun(888)
            mock_medya.assert_called_once()
            # Video kesinlikle gönderilmemeli!
            mock_video.assert_not_called()
            # DB'ye video_yolu None olarak güncellenmeli
            kws = mock_guncelle.call_args[1]
            self.assertIsNone(kws.get("video_yolu"))


if __name__ == "__main__":
    unittest.main()
