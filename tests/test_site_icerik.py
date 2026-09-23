"""postEDM haberinden site taslağı üretiminin ağsız sözleşme testleri."""

from __future__ import annotations

import unittest

from src.site_icerik import haber_site_girdisi


def haber() -> dict:
    return {
        "id": 42,
        "kaynak": "TÜİK",
        "orijinal_url": "https://data.tuik.gov.tr/bulten/42",
        "orijinal_baslik": "Silivri konut piyasasında haftanın görünümü",
        "orijinal_ozet": "Silivri ve çevresinde konut piyasasındaki hareketleri resmi veriler eşliğinde değerlendirdik.",
        "makale_metni": "Silivri konut piyasasında bu hafta görülen hareketleri, ilan sürelerini ve alıcı taleplerini resmi kaynaklarla birlikte ele alıyoruz. Bu metin yatırım tavsiyesi değildir; yerel piyasa gözlemlerini ve açıklanan verileri değerlendirmek için hazırlanmıştır.",
        "kategori": "PIYASA_VE_YATIRIM",
        "gorsel_url": "https://cdn.example.com/kapak.jpg",
    }


class TestSiteIcerik(unittest.TestCase):
    def test_gecerli_haber_kaynakli_taslak_sozlesmesine_donusur(self) -> None:
        girdi = haber_site_girdisi(haber())
        self.assertEqual(girdi["disKimlik"], "postedm:haber:42")
        self.assertEqual(girdi["tur"], "bulten")
        self.assertEqual(girdi["kaynakUrlleri"], ["https://data.tuik.gov.tr/bulten/42"])
        self.assertEqual(girdi["kategori"], "Piyasa & Yatırım")
        self.assertRegex(girdi["slug"], r"^[a-z0-9-]+$")

    def test_kaynaksiz_veya_kisa_metinli_haber_siteye_gonderilemez(self) -> None:
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            haber_site_girdisi({**haber(), "orijinal_url": "http://127.0.0.1/gizli"})
        with self.assertRaisesRegex(ValueError, "160"):
            haber_site_girdisi({**haber(), "makale_metni": "Kısa metin."})
