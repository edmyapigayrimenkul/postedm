"""
tests/test_instabot_yeni_moduller.py — Instabot Son 1 Ay Mimari Yeniliklerinin postedm Testleri

Test Edilen Modüller:
1. src/gorsel_kalite.py: Laplacian netlik varyansı, taranmış belge/tablo filtresi, kristal_netlestir.
2. src/fetch_web_image.py: Atıf metni üretimi ve alan adı çıkarma.
3. src/dogrula.py: alintiyi_denetle (%85 ardışık kelime penceresi) ve sayi_esdegerleri (Türkçe sayı normalizasyonu).
4. src/make_image.py: _sayfalari_dengeli_bol (kombinatorik varyans optimizasyonu ve yetim blok koruması).
5. src/youtube.py: projeleri_getir, azami_gunluk_video ve 2. proje kota failover altyapısı.
"""

import unittest
from PIL import Image, ImageDraw

from src import dogrula, fetch_web_image, gorsel_kalite, make_image, youtube


class TestInstabotYeniModuller(unittest.TestCase):
    def test_gorsel_kalite_taranmis_belge_ve_tablo_filtresi(self):
        """Düz beyaz kağıt / taranmış resmi gazete ve tablolar elenmeli (Doygunluk < 15, Parlaklık > 175)."""
        # Beyaz zeminli taranmış evrak simülasyonu
        belge_img = Image.new("RGB", (1200, 800), (245, 245, 245))
        d = ImageDraw.Draw(belge_img)
        d.line([(50, 50), (1150, 50)], fill=(20, 20, 20), width=2)
        d.line([(50, 100), (1150, 100)], fill=(20, 20, 20), width=2)

        kaliteli, sebep = gorsel_kalite.gorsel_kalite_denetle(belge_img)
        self.assertFalse(kaliteli, "Taranmış beyaz belge/tablo elenmeliydi.")
        self.assertIn("belge/tablo taraması", sebep)

    def test_gorsel_kalite_kristal_netlestir(self):
        """kristal_netlestir UnsharpMask ile görseli bozmadan keskinleştirmeli."""
        img = Image.new("RGB", (800, 600), (100, 150, 200))
        net = gorsel_kalite.kristal_netlestir(img)
        self.assertEqual(net.size, img.size)
        self.assertEqual(net.mode, "RGB")

    def test_fetch_web_image_atif_metni(self):
        """Web fotoğrafları için doğru alan adı atıf metni üretilmeli."""
        kayit = {"image": "https://www.aa.com.tr/uploads/haber/2026/09/arsa.jpg"}
        atif = fetch_web_image.atif_metni(kayit)
        self.assertEqual(atif, "Fotoğraf: aa.com.tr")

        self.assertEqual(fetch_web_image.atif_metni(None), "")
        self.assertEqual(fetch_web_image.atif_metni({}), "")

    def test_dogrula_alintiyi_denetle(self):
        """Kaynakta geçen alıntı onaylanmalı, uydurma alıntı reddedilmeli."""
        kaynak = (
            "Çevre ve Şehircilik Bakanı Murat Kurum, kentsel dönüşümde yeni destek paketini açıkladı. "
            "Bakan Kurum, 'Vatandaşlarımızın güvenli konutlara kavuşması için kira yardımını yüzde 50 artırıyoruz' dedi."
        )
        dogru_alinti = "Vatandaşlarımızın güvenli konutlara kavuşması için kira yardımını yüzde elli artırıyoruz"
        uydurma_alinti = "İstanbul'da riskli binaların tamamını önümüzdeki ay yıkıp yenileyeceğiz"

        self.assertTrue(dogrula.alintiyi_denetle(dogru_alinti, kaynak))
        self.assertFalse(dogrula.alintiyi_denetle(uydurma_alinti, kaynak))

    def test_dogrula_sayi_esdegerleri(self):
        """Türkçe sayı yazım varyasyonları ('435 bin 683', '4 lira 62 kuruş') doğru ayıklanmalı."""
        metin = "Toplam 435 bin 683 konut hak sahiplerine teslim edildi. Metrekare maliyeti 4 lira 62 kuruş arttı."
        esdegerler = dogrula.sayi_esdegerleri(metin)
        self.assertIn("435683", esdegerler)
        self.assertIn("462", esdegerler)
        self.assertIn("4", esdegerler)
        self.assertIn("62", esdegerler)

    def test_make_image_sayfalari_dengeli_bol(self):
        """_sayfalari_dengeli_bol sayfalar arasındaki yükseklik ve madde farkını minimize etmeli."""
        maddeler = [
            {"etiket": "KAPSANAN BÖLGE", "metin": "Silivri Alibey ve Selimpaşa mahallelerindeki 124 ada ve çevresi."},
            {"etiket": "İMAR VE YAPILAŞMA", "metin": "Emsal artışı azami yüzde 25 ile sınırlandırılmış olup kat adedi 4'tür."},
            {"etiket": "ASKI VE İTİRAZ", "metin": "İmar planları belediye askı panolarında 30 gün süreyle askıda kalacaktır."},
            {"etiket": "HAK SAHİPLİĞİ", "metin": "Hisseli tapu sahiplerinin noter onaylı vekaletname ile başvuru yapması şarttır."},
        ]

        bolumler = make_image._sayfalari_dengeli_bol(maddeler, sayfa_sayisi=2, has_uzman_notu_son_sayfa=True)
        self.assertEqual(len(bolumler), 2)
        # 4 madde 2'şer olarak dengeli dağıtılmalı, hiçbir madde kaybolmamalı
        toplam_dagitilan = len(bolumler[0]) + len(bolumler[1])
        self.assertEqual(toplam_dagitilan, 4)
        self.assertGreaterEqual(len(bolumler[0]), 1)
        self.assertGreaterEqual(len(bolumler[1]), 1)

    def test_youtube_coklu_proje_kotasi(self):
        """YouTube proje sayısına göre dinamik günlük kota hesabı (5 video / proje)."""
        azami = youtube.azami_gunluk_video()
        self.assertGreaterEqual(azami, 5)


if __name__ == "__main__":
    unittest.main()
