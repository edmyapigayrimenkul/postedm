"""
tests/test_sozluk_dengeli_satir.py — Sözlük kartında dengeli satır kırma (2026-10-09).

Açgözlü satır kırma satırı sonuna kadar doldurur ve son satıra TEK kelime kalır ("…Halk arasında depozito / denir.").
34 sözlük tanımının 10'unda vardı. `_dengeli_sar` satır sayısını artırmadan en dar genişliği arar; tek kelimelik son
satır kalmaz, yükseklik ve boyut seçimi değişmez, hiçbir satır alandan taşmaz. Ağ yok, yalnız yazı tipi ölçümü.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import make_image as mi, sozluk_arsivi as sa, yeni_formatlar as yf

YOL = mi.FONT_SANS_MEDIUM
GENISLIK = 1080 - 2 * mi._yerlesim()["kenar"]
# 44 puntoda açgözlü kırma son satıra tek kelime ("denir.") bırakır
DULLU = "Konut ve çatılı işyeri kiralarında kiracıdan sözleşmeyle istenen güvencedir; üç aylık kira bedelini aşamaz. Halk arasında depozito denir."


def _font(punto: int):
    return mi._font_yukle(YOL, punto)


def _kelime(satir: str) -> int:
    return len(satir.split())


class TestDengeliSar(unittest.TestCase):
    def test_acgozlu_kirma_dul_satir_birakir_dengeli_birakmaz(self):
        font, girinti = _font(44), int(44 * 1.6)
        acgozlu = yf._girintili_sar(DULLU, font, GENISLIK, girinti)
        self.assertEqual(_kelime(acgozlu[-1]), 1, acgozlu)          # kusurun kendisi
        dengeli = yf._dengeli_sar(DULLU, font, GENISLIK, girinti)
        self.assertGreaterEqual(_kelime(dengeli[-1]), 2, dengeli)

    def test_satir_sayisi_artmaz_ve_metin_degismez(self):
        font, girinti = _font(44), int(44 * 1.6)
        acgozlu = yf._girintili_sar(DULLU, font, GENISLIK, girinti)
        dengeli = yf._dengeli_sar(DULLU, font, GENISLIK, girinti)
        self.assertEqual(len(dengeli), len(acgozlu))
        self.assertEqual(" ".join(dengeli), DULLU)                    # kelime kaybolmadı, bölünmedi, sırası aynı

    def test_hicbir_satir_alandan_tasmaz(self):
        font, girinti = _font(44), int(44 * 1.6)
        dengeli = yf._dengeli_sar(DULLU, font, GENISLIK, girinti)
        self.assertLessEqual(yf._satir_genisligi(dengeli[0], font) + girinti, GENISLIK)
        for s in dengeli[1:]:
            self.assertLessEqual(yf._satir_genisligi(s, font), GENISLIK)

    def test_satirlar_acgozluden_daha_esit(self):
        font, girinti = _font(44), int(44 * 1.6)
        olc = lambda ss: max(yf._satir_genisligi(s, font) for s in ss) - min(yf._satir_genisligi(s, font) for s in ss)
        self.assertLess(olc(yf._dengeli_sar(DULLU, font, GENISLIK, girinti)[1:]),
                        olc(yf._girintili_sar(DULLU, font, GENISLIK, girinti)[1:]))

    def test_tek_satirlik_ve_bos_metin_degismez(self):
        font = _font(44)
        self.assertEqual(yf._dengeli_sar("Kısa tanım.", font, GENISLIK, 70), ["Kısa tanım."])
        self.assertEqual(yf._dengeli_sar("", font, GENISLIK, 70), [])

    def test_zaten_dengeli_metin_bozulmaz(self):
        font = _font(44)
        metin = "Tapu kütüğünde kayıtlı olmayan taşınmazı davasız ve aralıksız yirmi yıl, malik sıfatıyla kullanan kişinin tescil isteyebilmesidir."
        dengeli = yf._dengeli_sar(metin, font, GENISLIK, 70)
        self.assertEqual(" ".join(dengeli), metin)
        self.assertGreaterEqual(_kelime(dengeli[-1]), 2)

    def test_para_simgesi_rakamdan_kopmaz(self):
        # make_image'ın yapışkanlık kuralları (₺ rakamdan, unvan sonraki kelimeden) dengeli kırmada da korunur
        font = _font(44)
        metin = "Bu işlemde tapu harcı ile birlikte toplam 2.500 ₺ tutarında ek masraf ve vergi ayrıca ödenir ve belgelenir mi sorusu."
        for s in yf._dengeli_sar(metin, font, GENISLIK, 70):
            self.assertFalse(s.startswith("₺"), s)
            self.assertFalse(s.rstrip().endswith("2.500") and "₺" not in s, s)


class TestSigdirDengeli(unittest.TestCase):
    def test_boyut_secimi_degismez_yalniz_satirlar_esitlenir(self):
        puntolar = [44, 40, 36]
        kosul = dict(genislik=GENISLIK, azami_yukseklik=300, satir_carpani=1.38, girinti_carpani=1.6)
        a = yf._sigdir(DULLU, YOL, puntolar, **kosul)
        b = yf._sigdir(DULLU, YOL, puntolar, dengeli=True, **kosul)
        self.assertEqual(a[0].size, b[0].size)
        self.assertEqual(len(a[1]), len(b[1]))
        self.assertEqual(a[2:], b[2:])
        self.assertGreaterEqual(_kelime(b[1][-1]), 2)

    def test_varsayilan_dengesiz_diger_bicimler_etkilenmez(self):
        kosul = dict(genislik=GENISLIK, azami_yukseklik=300, satir_carpani=1.38, girinti_carpani=1.6)
        varsayilan = yf._sigdir(DULLU, YOL, [44], **kosul)
        self.assertEqual(varsayilan[1], yf._girintili_sar(DULLU, _font(44), GENISLIK, int(44 * 1.6)))


class TestKartlarda(unittest.TestCase):
    """34 kartın gerçek yerleşimi: tanım ve maddelerin hiçbirinin son satırı tek kelime değil."""

    @classmethod
    def setUpClass(cls):
        cls.kartlar = sa.kartlari_yukle(tazele=True)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.kayit = {}
        orijinal = yf._dengeli_sar

        def casus(metin, font, genislik, girinti=0, kelime_bol=False):
            satirlar = orijinal(metin, font, genislik, girinti, kelime_bol)
            cls.kayit.setdefault(metin, []).append((satirlar, font.size, genislik, girinti))
            return satirlar

        with patch.object(yf, "_dengeli_sar", casus):
            for k in cls.kartlar:
                yf.slaytlari_uret(sa.karttan_veri(k), format_turu="sozluk", cikti_dizini=Path(cls.tmp.name),
                                  cikti_onek=f"d_{k['kod']}", olcu="besleme")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_renderer_dengeli_kiriciyi_tanim_ve_maddelerde_kullanir(self):
        for k in self.kartlar:
            self.assertIn(k["tanim"], self.kayit, k["kod"])
            for m in k["puf"]:
                self.assertIn(m, self.kayit, f"{k['kod']}: {m[:30]}")

    def test_hicbir_tanimin_son_satiri_tek_kelime_degil(self):
        for k in self.kartlar:
            satirlar = self.kayit[k["tanim"]][-1][0]
            if len(satirlar) >= 2:
                self.assertGreaterEqual(_kelime(satirlar[-1]), 2, f"{k['kod']} {k['terim']}: {satirlar}")

    def test_hicbir_maddenin_son_satiri_tek_kelime_degil(self):
        for k in self.kartlar:
            for m in k["puf"]:
                satirlar = self.kayit[m][-1][0]
                if len(satirlar) >= 2:
                    self.assertGreaterEqual(_kelime(satirlar[-1]), 2, f"{k['kod']}: {satirlar}")

    def test_kazanan_yerlesimde_satirlar_taşmaz(self):
        for k in self.kartlar:
            satirlar, punto, genislik, girinti = self.kayit[k["tanim"]][-1]
            font = _font(punto)
            self.assertLessEqual(yf._satir_genisligi(satirlar[0], font) + girinti, genislik + 1, k["kod"])
            for s in satirlar[1:]:
                self.assertLessEqual(yf._satir_genisligi(s, font), genislik, k["kod"])


if __name__ == "__main__":
    unittest.main()
