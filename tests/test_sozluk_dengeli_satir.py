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


class TestBirimlereAyir(unittest.TestCase):
    """Yapışkanlık kuralları (make_image._metin_sar ile aynı): rakam+büyüklük+para simgesi ve unvan/ön ek bölünmez."""

    def test_rakam_buyukluk_para_simgesi_tek_birim(self):
        self.assertEqual(yf._birimlere_ayir("Bedel 2.500 ₺ olur"), ["Bedel", "2.500 ₺", "olur"])
        self.assertEqual(yf._birimlere_ayir("Bedel 350 bin ₺ olur"), ["Bedel", "350 bin ₺", "olur"])
        self.assertEqual(yf._birimlere_ayir("350 bin lira"), ["350 bin", "lira"])        # "lira" para simgesi değil (eski kural aynen)

    def test_unvan_ve_on_ek_sonraki_kelimeyle_kalir(self):
        self.assertEqual(yf._birimlere_ayir("aşırı ifa (md. 138) hükmü"), ["aşırı", "ifa", "(md. 138)", "hükmü"])
        self.assertEqual(yf._birimlere_ayir("14. madde uyarınca"), ["14. madde", "uyarınca"])

    def test_metin_ayni_temizlikten_gecer_ve_kelime_kaybolmaz(self):
        metin = "Kanun  bunu   “sıkı” şekil şartlarına bağlar…"
        birimler = yf._birimlere_ayir(metin)
        self.assertEqual(" ".join(birimler), " ".join(mi._temizle_tipografi(metin).split()))


class TestEnEsitKir(unittest.TestCase):
    def setUp(self):
        self.font = _font(40)

    def test_tam_n_satir_ve_hicbir_satir_tasmaz(self):
        birimler = DULLU.split()
        asgari = len(yf._girintili_sar(DULLU, self.font, GENISLIK, 64))       # açgözlü kırma en az satırı verir
        self.assertIsNone(yf._en_esit_kir(birimler, self.font, GENISLIK, 64, asgari - 1))   # daha az satıra sığmaz
        for n in (asgari, asgari + 1, asgari + 2):
            satirlar = yf._en_esit_kir(birimler, self.font, GENISLIK, 64, n)
            self.assertEqual(len(satirlar), n, n)
            self.assertEqual(" ".join(satirlar), DULLU)
            self.assertLessEqual(yf._satir_genisligi(satirlar[0], self.font), GENISLIK - 64)
            for s in satirlar[1:]:
                self.assertLessEqual(yf._satir_genisligi(s, self.font), GENISLIK)

    def test_ilk_satir_girinti_kadar_dar(self):
        satirlar = yf._en_esit_kir(DULLU.split(), self.font, GENISLIK, 200, 4)
        self.assertLessEqual(yf._satir_genisligi(satirlar[0], self.font), GENISLIK - 200)

    def test_dul_satir_mumkunse_olusmaz(self):
        # Gerçek vaka (CI/Linux): son kelime uzun, açgözlü kırma onu tek başına bırakıyordu
        metin = "Miras yoluyla mal edinenlerin, edindikleri malları vergi dairesine bildirmek için verdikleri beyannamedir."
        for punto in range(44, 62, 2):
            font = _font(punto)
            for kayma in (0, 8, 16, 24, 32):
                w = GENISLIK - kayma
                n = len(yf._girintili_sar(metin, font, w, int(punto * 1.6)))
                if n >= 2:
                    satirlar = yf._en_esit_kir(metin.split(), font, w, int(punto * 1.6), n)
                    self.assertIsNotNone(satirlar, (punto, kayma))
                    self.assertGreaterEqual(len(satirlar[-1].split()), 2, (punto, kayma, satirlar))

    def test_esit_genislikli_birimler_esit_satirlara_dagilir(self):
        # sekiz aynı birim, dört satır: en eşit dağılım satır başına ikidir (maliyet işe yaramıyorsa ilk uygun bölme seçilirdi)
        birim = "kelime"
        satirlar = yf._en_esit_kir([birim] * 8, self.font, GENISLIK, 0, 4)
        self.assertEqual(satirlar, [f"{birim} {birim}"] * 4)

    def test_dul_satir_kacinilmazsa_yine_de_yerlesir(self):
        # iki geniş birim bir satıra sığmaz: iki satır, ikincisi tek birim — ceza kaçınılmaz ama sonuç dönmeli
        genis = "M" * 18
        satirlar = yf._en_esit_kir([genis, genis], self.font, int(yf._satir_genisligi(genis, self.font) * 1.3), 0, 2)
        self.assertEqual(satirlar, [genis, genis])

    def test_sigmayan_birim_none_doner(self):
        self.assertIsNone(yf._en_esit_kir(["M" * 200, "kısa"], self.font, GENISLIK, 0, 2))

    def test_birim_sayisi_satir_sayisindan_azsa_none(self):
        self.assertIsNone(yf._en_esit_kir(["tek"], self.font, GENISLIK, 0, 2))

    def test_dagilim_acgozluden_daha_esit(self):
        font, girinti = _font(44), int(44 * 1.6)
        acgozlu = yf._girintili_sar(DULLU, font, GENISLIK, girinti)
        dengeli = yf._en_esit_kir(DULLU.split(), font, GENISLIK, girinti, len(acgozlu))
        # en uzun ile en kısa satır arasındaki fark (ilk satır girinti kadar kısa çizildiği için genişliğine eklenir)
        aralik = lambda ss: max(yf._satir_genisligi(s, font) + (girinti if i == 0 else 0) for i, s in enumerate(ss)) \
            - min(yf._satir_genisligi(s, font) + (girinti if i == 0 else 0) for i, s in enumerate(ss))
        self.assertLess(aralik(dengeli), aralik(acgozlu))


class TestMetrikDegisimi(unittest.TestCase):
    """GitHub'ın Linux ortamı (HarfBuzz kerning) metni birkaç piksel farklı ölçüyor: macOS'ta kusursuz görünen kırma orada
    dul satır ya da taşma üretmemeli. Genişlik ve punto kaydırılarak farklı ölçüm ortamları taklit edilir."""

    KAYMALAR = (0, 14, 30)

    @classmethod
    def setUpClass(cls):
        cls.kartlar = sa.kartlari_yukle(tazele=True)

    def _kontrol(self, metin, font, genislik, girinti, kod):
        acgozlu = yf._girintili_sar(metin, font, genislik, girinti)
        dengeli = yf._dengeli_sar(metin, font, genislik, girinti)
        self.assertEqual(len(dengeli), len(acgozlu), (kod, font.size, genislik))
        self.assertEqual(" ".join(dengeli), " ".join(mi._temizle_tipografi(metin).split()), kod)
        if len(dengeli) >= 2:
            self.assertGreaterEqual(len(dengeli[-1].split()), 2, (kod, font.size, genislik, dengeli))
        ilk_sinir = genislik - girinti if girinti else genislik
        self.assertLessEqual(yf._satir_genisligi(dengeli[0], font), ilk_sinir, (kod, font.size))
        for s in dengeli[1:]:
            self.assertLessEqual(yf._satir_genisligi(s, font), genislik, (kod, font.size))

    def test_tanimlar_farkli_olcumlerde(self):
        for k in self.kartlar:
            for punto in (44, 52, 60):
                font = _font(punto)
                for kayma in self.KAYMALAR:
                    self._kontrol(k["tanim"], font, GENISLIK - kayma, int(punto * 1.6), k["kod"])

    def test_maddeler_farkli_olcumlerde(self):
        for k in self.kartlar:
            for m in k["puf"]:
                for punto in (30, 35, 40):
                    font = _font(punto)
                    for kayma in self.KAYMALAR:
                        self._kontrol(m, font, GENISLIK - 56 - yf._madde_girintisi(punto) - kayma, 0, k["kod"])

    def test_unvan_satir_sonunda_kalmaz(self):
        for k in self.kartlar:
            for m in k["puf"] + [k["tanim"]]:
                for punto in (30, 40, 52):
                    for kayma in self.KAYMALAR:
                        for satir in yf._dengeli_sar(m, _font(punto), GENISLIK - 90 - kayma, 0)[:-1]:
                            self.assertFalse(satir.split()[-1].lower() in ("md.", "no.", "dr.", "av."), (k["kod"], satir))


if __name__ == "__main__":
    unittest.main()
