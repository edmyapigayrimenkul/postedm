"""
tests/test_kapanis_stilleri.py
10 Farklı Kapanış Tasarım Konsepti + Editoryal Düzen Testleri
"""

import unittest
from pathlib import Path
from PIL import Image

from src.kapanis_stilleri import STIL_HARITASI, kapanis_ciz
from src.make_image import slayt_kapanis


class TestKapanisStilleri(unittest.TestCase):
    def setUp(self):
        self.ornek_veri = {
            "slayt_4_cta": {
                "slogan_parca_1": "Doğru adımlarla",
                "slogan_vurgu": "GÜVENLİ KİRALAMA",
                "aciklama": "Silivri ve Trakya genelinde mülk yönetimi ve hukuki süreçlerinizde yanınızdayız.",
                "kaydet_metni": "BU REHBERİ KAYDEDİN · İHTİYAÇ ANINDA ELİNİZİN ALTINDA OLSUN",
            },
            "telefon": "0536 343 41 97",
            "danisman_isim": "METİN ÖZDOĞAN",
            "danisman_unvan": "Kurucu Danışman",
            "adres": "Alibey Mah. Albay Yunus Dirik Cad. No: 58/A · Silivri",
            "eposta": "info@edmyapigayrimenkul.com",
            "site": "edmyapigayrimenkul.com",
            "hesap": "@edmyapigayrimenkul",
            "rozet_metni": "EDM DANIŞMANLIK",
        }

    def test_tum_stiller_hatasiz_ve_dogru_boyutta_uretiliyor(self):
        benzersiz_fonksiyonlar = set(STIL_HARITASI.values())
        self.assertEqual(len(benzersiz_fonksiyonlar), 11)

        stiller = [
            "kartvizit", "kitap_afis", "split_screen", "mimari_pafta",
            "kurucu_mektubu", "paspartu_fotograf", "dikey_tipografi",
            "iletisim_terminali", "dev_numara", "resmi_muhur", "editoryal"
        ]

        for stil in stiller:
            with self.subTest(stil=stil):
                dosya = kapanis_ciz(stil, self.ornek_veri, "04 / 04")
                self.assertTrue(dosya.exists(), f"{stil} çıktısı oluşturulamadı: {dosya}")
                with Image.open(dosya) as img:
                    self.assertEqual(img.size, (1080, 1350), f"{stil} boyutu 1080x1350 olmalı, alınan: {img.size}")

    def test_slayt_kapanis_delegasyonu_ve_override(self):
        # Override ile farklı stil çağrısı
        veri_split = dict(self.ornek_veri)
        veri_split["kapanis_stili"] = "split_screen"
        dosya = slayt_kapanis(veri_split, "04 / 04")
        self.assertTrue(dosya.exists())
        self.assertIn("03_split_screen", dosya.name)

        # Varsayılan stil (editoryal)
        veri_default = dict(self.ornek_veri)
        dosya_default = slayt_kapanis(veri_default, "04 / 04")
        self.assertTrue(dosya_default.exists())
        self.assertIn("11_editoryal", dosya_default.name)


if __name__ == "__main__":
    unittest.main()
