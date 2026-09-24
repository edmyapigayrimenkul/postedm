"""
tests/test_faz2_ozellikleri.py — Kardeş görsel havuzu, TikTok Photo Mode aciklama_kur ve failover testleri.
"""

import sqlite3
import unittest
from unittest.mock import MagicMock, patch
from src import make_image, tiktok, youtube


class TestFaz2Ozellikleri(unittest.TestCase):
    def test_konu_imzasi_ve_kardes_linkler(self):
        baslik1 = "Silivri Alibey Mahallesi Yeni İmar Planı Askıya Çıktı"
        kelimeler, isimler = make_image.konu_imzasi(baslik1)
        self.assertIn("silivri", isimler)
        self.assertIn("alibey", isimler)
        self.assertIn("imar", kelimeler)

        # Bellek içi SQLite ile kardeş haber havuzu testi
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        con.execute(
            """CREATE TABLE haberler (
                id INTEGER PRIMARY KEY,
                baslik TEXT,
                link TEXT,
                foto_url TEXT,
                eklenme_tarihi TEXT
            )"""
        )
        con.execute(
            """INSERT INTO haberler (id, baslik, link, foto_url, eklenme_tarihi)
               VALUES (1, 'Silivri Alibey Mahallesi İmar Planı Askıda', 'https://haber1.com/imar', 'https://img.com/1.jpg', datetime('now'))"""
        )
        con.execute(
            """INSERT INTO haberler (id, baslik, link, foto_url, eklenme_tarihi)
               VALUES (2, 'Silivri Alibey İmarında Yeni Gelişme', 'https://haber2.com/imar-detay', 'https://img.com/2.jpg', datetime('now'))"""
        )
        con.execute(
            """INSERT INTO haberler (id, baslik, link, foto_url, eklenme_tarihi)
               VALUES (3, 'Antalya Kaş Bölgesinde Turizm İlanı', 'https://haber3.com/kas', 'https://img.com/3.jpg', datetime('now'))"""
        )

        haber = {"id": 10, "baslik": baslik1, "link": "https://ana.com/haber"}
        kardesler = make_image.kardes_linkler(con, haber)
        # Antalya haberi eşleşmemeli, Silivri Alibey haberleri eşleşmeli
        self.assertIn("https://haber1.com/imar", kardesler)
        self.assertIn("https://haber2.com/imar-detay", kardesler)
        self.assertNotIn("https://haber3.com/kas", kardesler)

    def test_tiktok_aciklama_kur_dedupe_ve_kuyruk(self):
        metin_kirli = (
            "Silivri'de arsa alırken dikkat edilmesi gereken kritik detaylar.\n\n"
            "#Arsa #Silivri #Emlak"
        )
        ek_etiketler = ["#Silivri", "#Yatırım", "#EDMYapı"]
        sonuc = tiktok.aciklama_kur(metin_kirli, etiketler=ek_etiketler)

        # Gövde korunmalı
        self.assertTrue(sonuc.startswith("Silivri'de arsa alırken dikkat edilmesi gereken kritik detaylar."))
        # Mükerrer #Silivri temizlenmeli, sadece 1 kez geçmeli
        self.assertEqual(sonuc.count("#Silivri"), 1)
        self.assertIn("#Arsa", sonuc)
        self.assertIn("#Yatırım", sonuc)
        self.assertIn("#EDMYapı", sonuc)

    def test_tiktok_foto_carousel_alias(self):
        # foto_carousel_yukle alias'ı mevcut olmalı
        self.assertEqual(tiktok.foto_carousel_yukle, tiktok.foto_yayinla)

    def test_youtube_projeleri_getir_ve_failover(self):
        with patch.dict("os.environ", {
            "YOUTUBE_CLIENT_ID": "cid1",
            "YOUTUBE_CLIENT_SECRET": "sec1",
            "YOUTUBE_REFRESH_TOKEN": "ref1",
            "YOUTUBE_CLIENT_ID_2": "cid2",
            "YOUTUBE_CLIENT_SECRET_2": "sec2",
            "YOUTUBE_REFRESH_TOKEN_2": "ref2",
        }):
            projeler = youtube.projeleri_getir()
            self.assertEqual(len(projeler), 2)
            self.assertEqual(projeler[0]["proje_no"], 1)
            self.assertEqual(projeler[1]["proje_no"], 2)


if __name__ == "__main__":
    unittest.main()
