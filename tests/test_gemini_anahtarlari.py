"""
tests/test_gemini_anahtarlari.py — Yedek Gemini anahtarları (2026-10-08).

GitHub sırları `GEMINI_API_KEY_YEDEK` ve `GEMINI_API_KEY_YEDEK2` adıyla tanımlıydı, kod ise yalnız
`GEMINI_API_KEY_2` ve `GEMINI_IMAGE_API_KEY`'i okuyordu: yedekler ortamda dururken hiç denenmiyordu.
Anahtar ücretsiz katmanda (model başına günlük istek sınırı); 2026-10-07'de tek günlük yoğun denemeyle
üç modelin kotası doldu. Ağ yok: istekler sahte.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import unittest
from unittest.mock import MagicMock, patch

from src import generate_text as gt

ANAHTAR_ADLARI = ("GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_YEDEK", "GEMINI_API_KEY_YEDEK2", "GEMINI_IMAGE_API_KEY")


def _ortam(**degerler):
    """Yalnız verilen Gemini anahtarları tanımlı bir ortam (başka testlerin sızdırdıkları temizlenir)."""
    temiz = {ad: "" for ad in ANAHTAR_ADLARI}
    temiz.update(degerler)
    return patch.dict(os.environ, temiz)


class TestAnahtarListesi(unittest.TestCase):
    def test_sirlardaki_yedek_adlari_okunur(self):
        with _ortam(GEMINI_API_KEY="a", GEMINI_API_KEY_YEDEK="b", GEMINI_API_KEY_YEDEK2="c"):
            adlar_degerler = gt._anahtarlari_al()
        self.assertEqual([d for _, d in adlar_degerler], ["a", "b", "c"])
        self.assertEqual(adlar_degerler[0][0], "birincil")
        self.assertEqual(len({ad for ad, _ in adlar_degerler}), 3)  # kota takibi için adlar benzersiz

    def test_eski_adlar_hala_calisir(self):
        with _ortam(GEMINI_API_KEY="a", GEMINI_API_KEY_2="b", GEMINI_IMAGE_API_KEY="c"):
            self.assertEqual([d for _, d in gt._anahtarlari_al()], ["a", "b", "c"])

    def test_ayni_deger_tekrarlanmaz(self):
        with _ortam(GEMINI_API_KEY="a", GEMINI_API_KEY_YEDEK="a", GEMINI_IMAGE_API_KEY="a"):
            self.assertEqual([d for _, d in gt._anahtarlari_al()], ["a"])

    def test_bos_ve_bosluk_degerleri_atilir(self):
        with _ortam(GEMINI_API_KEY="a", GEMINI_API_KEY_YEDEK="   ", GEMINI_API_KEY_YEDEK2=""):
            self.assertEqual([d for _, d in gt._anahtarlari_al()], ["a"])

    def test_birincil_yokken_yedek_kullanilir(self):
        with _ortam(GEMINI_API_KEY_YEDEK="b"):
            sonuc = gt._anahtarlari_al()
        self.assertEqual([d for _, d in sonuc], ["b"])

    def test_hic_anahtar_yoksa_bos(self):
        with _ortam():
            self.assertEqual(gt._anahtarlari_al(), [])


class TestKotaYedegi(unittest.TestCase):
    def setUp(self):
        gt._TUKENMIS.clear()

    def tearDown(self):
        gt._TUKENMIS.clear()

    @staticmethod
    def _yanit(durum, mesaj="", metin="tamam"):
        r = MagicMock()
        r.status_code = durum
        r.text = mesaj
        r.json.return_value = (
            {"candidates": [{"content": {"parts": [{"text": metin}]}, "finishReason": "STOP"}]}
            if durum == 200 else {"error": {"message": mesaj}}
        )
        return r

    def test_birincilin_gunluk_kotasi_dolunca_yedek_anahtar_yanit_verir(self):
        gunluk = "You exceeded your quota ... GenerateRequestsPerDayPerProjectPerModel-FreeTier"

        def post(url, headers=None, **kw):
            return self._yanit(429, gunluk) if headers["x-goog-api-key"] == "birincil-anahtar" else self._yanit(200, metin="yedekten")

        with _ortam(GEMINI_API_KEY="birincil-anahtar", GEMINI_API_KEY_YEDEK="yedek-anahtar"), \
             patch.object(gt.requests, "post", side_effect=post) as p:
            sonuc = gt._gemini_cagri("istem", "sistem", modeller=["model-a"])
        self.assertEqual(sonuc, "yedekten")
        self.assertEqual(p.call_count, 2)
        self.assertIn(("model-a", "birincil"), gt._TUKENMIS)   # birincil bu model için bir daha denenmez

    def test_kotasi_dolan_anahtar_ayni_surecte_tekrar_denenmez(self):
        gunluk = "GenerateRequestsPerDayPerProjectPerModel-FreeTier"
        cagrilar = []

        def post(url, headers=None, **kw):
            cagrilar.append(headers["x-goog-api-key"])
            return self._yanit(429, gunluk) if headers["x-goog-api-key"] == "b" else self._yanit(200)

        with _ortam(GEMINI_API_KEY="b", GEMINI_API_KEY_YEDEK="y"), patch.object(gt.requests, "post", side_effect=post):
            gt._gemini_cagri("i", "s", modeller=["m"])
            gt._gemini_cagri("i", "s", modeller=["m"])
        self.assertEqual(cagrilar, ["b", "y", "y"])  # ikinci çağrıda birincil atlandı


if __name__ == "__main__":
    unittest.main()
