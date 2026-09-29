"""
tests/test_derin_kazima_stres.py — Derin Haber Kazıma, Çoklu Görsel ve Stres/Sabotaj Testleri.
"""

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")

import unittest
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup
from src import fetch_article


class TestDerinKazimaStres(unittest.TestCase):
    def test_paragraf_baslik_ve_liste_toplama(self):
        """Alt başlıklar (h2, h3) ve madde imleri (li) gövdeye düzgün dahil ediliyor mu?"""
        html = """
        <article>
            <h2>Milli Emlak İhale Şartları Açıklandı</h2>
            <p>Çevre ve Şehircilik Bakanlığı 47 ilde 383 arsa için satış takvimini belirledi.</p>
            <h3>Ödeme Kolaylıkları ve Vergiler</h3>
            <ul>
                <li>Peşin ödemede yüzde 20 indirim sağlanacak.</li>
                <li>Satın alınan araziler 5 yıl süreyle emlak vergisinden muaf tutulacak.</li>
                <li>24 aya varan taksit seçenekleri sunulacak.</li>
            </ul>
        </article>
        """
        soup = BeautifulSoup(html, "html.parser")
        metin = fetch_article._paragraflardan_topla(soup)
        self.assertIsNotNone(metin)
        self.assertIn("Milli Emlak İhale Şartları", metin)
        self.assertIn("Peşin ödemede yüzde 20", metin)
        self.assertIn("5 yıl süreyle emlak vergisinden", metin)

    def test_sabote_ve_bozuk_html(self):
        """Bozuk tagler, kapanmamış divler ve script enjeksiyonları güvenle temizleniyor mu?"""
        bozuk_html = """
        <div>
            <script>alert('sabotaj');</script>
            <style>.reklam { display:none; }</style>
            <h1>Silivri Selimpaşa İmar Planı Askıya Çıktı</h1>
            <div>
                <p>Silivri Alibey ve Selimpaşa mahallelerinde yeni imar planı 30 gün boyunca askıda kalacak.</p>
                <p>Malikler itirazlarını doğrudan belediyenin imar müdürlüğüne yazılı olarak iletebilecekler.</p>
            <!-- kapanmamış etiket
        """
        with patch("src.fetch_article._sayfayi_getir") as mock_get:
            mock_resp = MagicMock()
            mock_resp.content = bozuk_html.encode("utf-8")
            mock_get.return_value = mock_resp

            metin = fetch_article.makale_metni_cek("https://test.com/haber", baslik="Silivri Selimpaşa İmar Planı Askıda")
            self.assertIsNotNone(metin)
            self.assertNotIn("alert", metin)
            self.assertNotIn("display:none", metin)
            self.assertIn("30 gün boyunca askıda kalacak", metin)

    def test_coklu_gorsel_ve_filtreleme(self):
        """Reklam, sayaç, 1x1 piksel ve ikonlar elenip asıl içerik fotoğrafları toplanıyor mu?"""
        html_gorseller = """
        <html>
        <head>
            <meta property="og:image" content="https://haber.com/kapak.jpg">
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "NewsArticle",
                "image": ["https://haber.com/galeri1.jpg", "https://haber.com/galeri2.jpg"]
            }
            </script>
        </head>
        <body>
            <article>
                <img src="https://googleads.g.doubleclick.net/pagead/ads?id=123" />
                <img src="https://haber.com/icerik_foto.png" />
                <img src="https://facebook.com/tr?id=999" />
                <img src="https://haber.com/static/logo.svg" />
            </article>
        </body>
        </html>
        """
        with patch("src.fetch_article._sayfayi_getir") as mock_get:
            mock_resp = MagicMock()
            mock_resp.content = html_gorseller.encode("utf-8")
            mock_get.return_value = mock_resp

            gorseller = fetch_article.tum_gorselleri_cek("https://haber.com/arsa-haberi")
            self.assertIn("https://haber.com/kapak.jpg", gorseller)
            self.assertIn("https://haber.com/galeri1.jpg", gorseller)
            self.assertIn("https://haber.com/icerik_foto.png", gorseller)
            # Reklam ve logolar elenmeli:
            self.assertFalse(any("doubleclick" in g for g in gorseller))
            self.assertFalse(any("facebook.com/tr" in g for g in gorseller))
            self.assertFalse(any(".svg" in g for g in gorseller))

    def test_alakasiz_sayfa_reddi(self):
        """Haber başlığı ile alakası olmayan genel anasayfa veya paywall metinleri eleniyor mu?"""
        alakasiz_html = """
        <article>
            <p>Günün en çok okunan astroloji ve magazin haberleri için sayfayı kaydırın. Ünlü sanatçının yeni albümü rekor kırdı.</p>
            <p>Hava durumu tahminlerine göre yarın Marmara bölgesinde şiddetli yağış bekleniyor.</p>
        </article>
        """
        with patch("src.fetch_article._sayfayi_getir") as mock_get:
            mock_resp = MagicMock()
            mock_resp.content = alakasiz_html.encode("utf-8")
            mock_get.return_value = mock_resp

            # Başlık emlak ve arsa hakkında, sayfa magazin hakkında
            metin = fetch_article.makale_metni_cek("https://test.com/magazin", baslik="Milli Emlak Çatalca Parsel Satışı")
            self.assertIsNone(metin)


if __name__ == "__main__":
    unittest.main()
