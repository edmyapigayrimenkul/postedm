"""
tests/test_konu_mukerrerlik_kalkani.py — Hukuki Madde ve Semantik Mükerrerlik Kalkanı Testleri.

Kapsam:
1. Kanun maddesi normalizasyonu ve aralık genişletme (mevzuat_maddeleri_cikar).
2. Metin n-gram Jaccard benzerliği (metin_jaccard_benzerlik).
3. Hukuki ve semantik mükerrerlik denetimi (konu_mukerrer_mi).
4. sonraki_konu akışında çakışan maddelerin otomatik elenmesi.
5. Yeni eklenen 10 konunun havuz bütünlüğü ve şema doğrulaması.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py
import unittest
from unittest.mock import patch

from src import db, konu_bankasi, mukerrerlik


class TestKonuMukerrerlikKalkani(unittest.TestCase):

    def setUp(self):
        os.environ["POSTEDM_TEST_MODU"] = "1"

    def test_mevzuat_maddeleri_cikar(self):
        """Farklı kanun ve madde formatları doğru normalize edilmelidir."""
        # Aralık içeren TMK
        m1 = mukerrerlik.mevzuat_maddeleri_cikar("Türk Medeni Kanunu md. 732-734")
        self.assertIn("TMK:732", m1)
        self.assertIn("TMK:733", m1)
        self.assertIn("TMK:734", m1)

        # Virgüllü TBK
        m2 = mukerrerlik.mevzuat_maddeleri_cikar("Türk Borçlar Kanunu md. 347, 350")
        self.assertIn("TBK:347", m2)
        self.assertIn("TBK:350", m2)

        # İmar Kanunu
        m3 = mukerrerlik.mevzuat_maddeleri_cikar("İmar Kanunu md. 18")
        self.assertEqual(m3, ["IMAR:18"])

        # Kat Mülkiyeti Kanunu
        m4 = mukerrerlik.mevzuat_maddeleri_cikar("Kat Mülkiyeti Kanunu md. 19")
        self.assertEqual(m4, ["KMK:19"])

        # Boş / None
        self.assertEqual(mukerrerlik.mevzuat_maddeleri_cikar(None), [])

    def test_metin_jaccard_benzerlik(self):
        """Benzer başlıklar yüksek, alakasız başlıklar düşük skor almalıdır."""
        t1 = "Hisseli tapuda önalım şufa davası açma şartları"
        t2 = "Hisseli tapuda şufa önalım davası süresi ve şartları"
        skor_benzer = mukerrerlik.metin_jaccard_benzerlik(t1, t2)
        self.assertGreater(skor_benzer, 0.60, f"Benzer başlıklar yüksek skor almalıydı: {skor_benzer}")

        t3 = "Kiracı tahliyesinde 10 yıllık uzama süresi"
        skor_alakasiz = mukerrerlik.metin_jaccard_benzerlik(t1, t3)
        self.assertLess(skor_alakasiz, 0.20, f"Farklı konular düşük skor almalıydı: {skor_alakasiz}")

    def test_konu_mukerrer_mi_mevzuat_cakismasi(self):
        """Son günlerde işlenmiş kanun maddesini içeren konu mükerrer sayılmalıdır."""
        aday = {
            "kod": "S1-YENI",
            "baslik": "Paydaşın pay satışında dava hakkı",
            "mevzuat": "Türk Medeni Kanunu md. 732",
        }
        aktif_maddeler = {"TMK:732", "TBK:347"}
        cakisiyor, gerekce = mukerrerlik.konu_mukerrer_mi(aday, son_konular=[], aktif_maddeler=aktif_maddeler)
        self.assertTrue(cakisiyor)
        self.assertIn("Mevzuat çakışması", gerekce)

    def test_konu_mukerrer_mi_semantik_baslik_cakismasi(self):
        """Kanun maddesi belirtilmese bile başlık semantiği çok yakınsa mükerrer sayılmalıdır."""
        aday = {
            "kod": "S1-YENI2",
            "baslik": "Hisseli tapuda önalım şufa davası açma şartları",
            "mevzuat": None,
        }
        son_konular = [{
            "kod": "S1-ESKI",
            "baslik": "Hisseli tapuda şufa önalım davası şartları",
            "mevzuat": None,
        }]
        cakisiyor, gerekce = mukerrerlik.konu_mukerrer_mi(aday, son_konular=son_konular, aktif_maddeler=set())
        self.assertTrue(cakisiyor)
        self.assertIn("semantik", gerekce)

    def test_konu_mukerrer_mi_temiz_konu_gecer(self):
        """Farklı madde ve farklı başlığa sahip konu mükerrerlik filtresinden temiz geçmelidir."""
        aday = {
            "kod": "S3-028",
            "baslik": "İmar uygulamasında DOP kesintisi yüzde 45'i geçemez",
            "mevzuat": "İmar Kanunu md. 18",
        }
        son_konular = [{
            "kod": "S2-001",
            "baslik": "Kira artış oranı nasıl belirlenir",
            "mevzuat": "Türk Borçlar Kanunu md. 344",
        }]
        aktif_maddeler = {"TBK:344"}
        cakisiyor, gerekce = mukerrerlik.konu_mukerrer_mi(aday, son_konular=son_konular, aktif_maddeler=aktif_maddeler)
        self.assertFalse(cakisiyor)
        self.assertEqual(gerekce, "")

    def test_sonraki_konu_cakisan_maddeyi_atlar(self):
        """sonraki_konu seçimi yapılırken son mevzuat maddesi çakışan adaylar öncelikli elenmelidir."""
        with patch("src.mukerrerlik.son_kullanilan_mevzuatlar", return_value={"TMK:194", "TBK:342"}):
            # Seçilen konunun TMK:194 (S1-031) veya TBK:342 (S2-031) olmaması gerekir
            secim = konu_bankasi.sonraki_konu(sutun="S1")
            self.assertIsNotNone(secim)
            if secim.get("mevzuat"):
                maddeler = mukerrerlik.mevzuat_maddeleri_cikar(secim["mevzuat"])
                self.assertNotIn("TMK:194", maddeler)

    def test_yeni_eklenen_10_konu_yuklenir_ve_dogrudur(self):
        """Havuzdaki 130 konunun tamamı geçerli olmalı ve 10 yeni konu eksiksiz bulunmalıdır."""
        havuz = {k["kod"]: k for k in konu_bankasi.havuzu_yukle(tazele=True)}
        self.assertGreaterEqual(len(havuz), 130)

        beklenen_yeni_kodlar = [
            "S1-031", "S1-032", "S1-033",
            "S2-031", "S2-032", "S2-033",
            "S3-027", "S3-028", "S3-029",
            "S4-019",
        ]
        for kod in beklenen_yeni_kodlar:
            self.assertIn(kod, havuz, f"Yeni konu {kod} havuzda bulunamadı")
            k = havuz[kod]
            self.assertTrue(k.get("baslik"))
            self.assertTrue(k.get("aci"))
            self.assertTrue(k.get("mevzuat"))
            self.assertTrue(k.get("dayanak_alintisi"))


if __name__ == "__main__":
    unittest.main()
