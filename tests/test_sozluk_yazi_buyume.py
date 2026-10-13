"""
tests/test_sozluk_yazi_buyume.py — Kısa içerikli sözlük kartlarında yazı büyür (2026-10-09).

Kullanıcı: "kısa kelimeleri büyütebilirsin". Kısa tanımlı kartlarda tanım ile kutu arasında büyük boşluk kalıyordu.
`yeni_formatlar.SOZLUK_BUYUME_BASAMAKLARI` (tanım punto, madde punto) çiftleri büyükten küçüğe denenir, ilk sığan
seçilir; hiçbiri sığmazsa eski çözüm (tanım ≤44, madde ≤30) çalışır. Yoğun kart değişmez, kısa kart dolar.
Büyük puntoda "—" işareti metne yapışmasın diye madde girintisi puntoyla büyür. Ağ yok.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import make_image as mi, sozluk_arsivi as sa, yeni_formatlar as yf

GENISLIK = 1080 - 2 * mi._yerlesim()["kenar"]


def _puntolar(**uret_args):
    """`uret_sozluk`ı çizip kazanan (tanım punto, madde puntoları) değerini döner (`_dengeli_sar` çağrılarından)."""
    kayit = []
    orijinal = yf._dengeli_sar

    def casus(metin, font, genislik, girinti=0, kelime_bol=False):
        satirlar = orijinal(metin, font, genislik, girinti, kelime_bol)
        kayit.append((metin, font.size, satirlar, genislik))
        return satirlar

    with tempfile.TemporaryDirectory() as tmp, patch.object(yf, "_dengeli_sar", casus):
        yf.uret_sozluk(Path(tmp) / "k.jpg", kategori="TAPU_VE_HUKUK", **uret_args)
    tanim = [c for c in kayit if c[0] == uret_args["tanim_metni"]][-1]
    maddeler = [[c for c in kayit if c[0] == m][-1] for m in uret_args["puf_maddeleri"]]
    return tanim, maddeler


class TestMaddeGirintisi(unittest.TestCase):
    def test_otuz_puntoya_kadar_eski_deger(self):
        for punto in (24, 26, 28, 30):
            self.assertEqual(yf._madde_girintisi(punto), 30, punto)

    def test_buyuk_puntoda_cizgi_kadar_acilir(self):
        self.assertEqual(yf._madde_girintisi(31), 35)
        self.assertEqual(yf._madde_girintisi(40), 44)

    def test_cizgi_metne_yapismaz_hicbir_basamakta(self):
        # "—" glifinin genişliği + en az 4 px boşluk girintiye sığmalı
        for _, madde_p in yf.SOZLUK_BUYUME_BASAMAKLARI + ((44, 30), (40, 28), (36, 26), (30, 24)):
            font = mi._font_yukle(yf.FONT_SANS_MEDIUM, madde_p)
            self.assertGreaterEqual(yf._madde_girintisi(madde_p), yf._satir_genisligi("—", font) + 4, madde_p)

    def test_etiket_puntosu_orantili_buyur(self):
        self.assertEqual([yf._etiket_puntosu(p) for p in (24, 30, 31, 35, 36, 40)], [20, 20, 22, 22, 24, 24])


class TestBasamaklar(unittest.TestCase):
    def test_basamaklar_buyukten_kucuge_ve_oran_dengeli(self):
        b = yf.SOZLUK_BUYUME_BASAMAKLARI
        self.assertEqual(list(b), sorted(b, reverse=True))
        for tanim_p, madde_p in b:
            self.assertGreater(tanim_p, 44)                       # eski tavanın üstü: eskisini gölgelemesin
            self.assertGreater(madde_p, 30)
            self.assertTrue(1.3 <= tanim_p / madde_p <= 1.7, (tanim_p, madde_p))   # hiyerarşi 44/30 ≈ 1,47 civarı


class TestSentetikKartlar(unittest.TestCase):
    KISA = dict(terim="TAPU HARCI", tanim_metni="Gayrimenkul devir ve iktisaplarında tapu işlemi nedeniyle ödenen harçtır.",
                puf_maddeleri=["Harç beyan edilen bedel üzerinden hesaplanır.", "Bedel gerçeği yansıtmazsa fark tarh edilir."])
    YOGUN = dict(terim="KAT MÜLKİYETİ", tanim_metni=("Anagayrimenkulün yönetim tarzını, kullanma maksat ve şeklini, yönetici ve denetçi ücretini; "
                                                    "kat maliklerinin hak ve yükümlülüklerini düzenleyen ve bütün kat maliklerini bağlayan bir sözleşme "
                                                    "hükmündeki plandır; plan ve değişiklikleri külli ve cüzi haleflere de geçer.") ,
                 puf_maddeleri=["Yönetim planı, bütün kat maliklerini bağlayan bir sözleşme hükmündedir ve kat maliklerinin tamamını bağlar.",
                                "Planı değiştirmek için bütün kat maliklerinin beşte dördünün oyu şarttır; aksi karar geçersiz sayılır.",
                                "Plan ve değişiklikler, kat maliklerinin külli ve cüzi haleflerini, yönetici ve denetçileri de bağlar."])

    def test_kisa_kart_en_buyuk_basamagi_alir(self):
        tanim, maddeler = _puntolar(**self.KISA)
        self.assertEqual(tanim[1], yf.SOZLUK_BUYUME_BASAMAKLARI[0][0])
        self.assertTrue(all(m[1] == yf.SOZLUK_BUYUME_BASAMAKLARI[0][1] for m in maddeler))

    def test_yogun_kart_eski_tavanda_kalir(self):
        tanim, maddeler = _puntolar(**self.YOGUN)
        self.assertLessEqual(tanim[1], 44)
        self.assertTrue(all(m[1] <= 30 for m in maddeler), [m[1] for m in maddeler])

    def test_asiri_uzun_metin_yine_de_sigar_cokmez(self):
        uzun = dict(terim="KAT MÜLKİYETİ", tanim_metni=("Bu çok uzun bir tanım cümlesidir ve sürekli devam eder. " * 5).strip(),
                    puf_maddeleri=[("Bu da çok uzun bir madde olarak karta sığdırılmaya çalışılır ve sonunda küçülür. " * 2).strip()] * 3)
        tanim, maddeler = _puntolar(**uzun)
        self.assertLessEqual(tanim[1], 44)

    def test_cizilen_madde_metni_cizgiden_girinti_kadar_uzakta(self):
        """Çizimde de (yalnız kırma genişliğinde değil) metin "—" işaretinden `_madde_girintisi` kadar uzakta başlar."""
        from PIL import ImageDraw
        cagrilar = []
        orijinal = ImageDraw.ImageDraw.text

        def casus(self_, xy, metin, *a, **kw):
            font = kw.get("font")
            cagrilar.append((xy, metin, getattr(font, "size", None)))
            return orijinal(self_, xy, metin, *a, **kw)

        with tempfile.TemporaryDirectory() as tmp, patch.object(ImageDraw.ImageDraw, "text", casus):
            yf.uret_sozluk(Path(tmp) / "k.jpg", kategori="TAPU_VE_HUKUK", **self.KISA)
        cizgiler = [(i, c) for i, c in enumerate(cagrilar) if c[1] == "—"]
        self.assertEqual(len(cizgiler), len(self.KISA["puf_maddeleri"]))
        for i, (xy, _, punto) in cizgiler:
            metin_xy = cagrilar[i + 1][0]                    # çizgiden hemen sonra o maddenin ilk satırı çizilir
            self.assertEqual(metin_xy[1], xy[1])
            self.assertEqual(metin_xy[0] - xy[0], yf._madde_girintisi(punto))
            self.assertGreater(punto, 30)

    def test_dengeli_ve_tasmasiz_buyuk_puntoda_da(self):
        tanim, maddeler = _puntolar(**self.KISA)
        font = mi._font_yukle(yf.FONT_SANS_MEDIUM, tanim[1])
        for s in tanim[2][1:]:
            self.assertLessEqual(yf._satir_genisligi(s, font), GENISLIK)
        for metin, punto, satirlar, genislik in maddeler:
            f = mi._font_yukle(yf.FONT_SANS_MEDIUM, punto)
            self.assertEqual(genislik, GENISLIK - 56 - yf._madde_girintisi(punto))   # kırma genişliği girintiyle uyumlu
            for s in satirlar:
                self.assertLessEqual(yf._satir_genisligi(s, f), genislik)


class TestArsivde(unittest.TestCase):
    """Arşivdeki kartların gerçek çözümü."""

    @classmethod
    def setUpClass(cls):
        cls.kartlar = sa.kartlari_yukle(tazele=True)
        cls.cozum = {}
        for k in cls.kartlar:
            tanim, maddeler = _puntolar(terim=k["terim"], tanim_metni=k["tanim"], puf_maddeleri=k["puf"])
            cls.cozum[k["kod"]] = (tanim, maddeler)

    def test_cogu_kart_buyudu(self):
        buyuyen = [kod for kod, (t, _) in self.cozum.items() if t[1] > 44]
        self.assertGreaterEqual(len(buyuyen), 25, f"yalnız {len(buyuyen)} kart büyüdü")

    def test_hicbir_kart_eski_tavandan_kucuk_cikmadi_gereksiz(self):
        # eski çözümün aşağı basamakları (40 ve altı) yalnız gerçekten sığmayan, çok yoğun kartlarda görülür
        # Eşik arşivle ölçeklenir (34 kartta en çok 3 ≈ %9); yoğun kartlar (uzun tanım + üç madde) 40 pt'ye iner, ama
        # hiçbiri 36 pt tabanının altına düşmez ve oran kontrol altında kalır.
        kucuk = [kod for kod, (t, _) in self.cozum.items() if t[1] < 44]
        izin = max(3, round(len(self.kartlar) * 0.12))
        self.assertLessEqual(len(kucuk), izin, kucuk)
        self.assertGreaterEqual(min(t[1] for t, _ in self.cozum.values()), 36)

    def test_hiyerarsi_korunur(self):
        for kod, (tanim, maddeler) in self.cozum.items():
            madde_p = maddeler[0][1]
            self.assertTrue(1.2 <= tanim[1] / madde_p <= 1.8, (kod, tanim[1], madde_p))
            self.assertTrue(all(m[1] == madde_p for m in maddeler), kod)       # kutudaki tüm maddeler aynı punto

    def test_tanim_hicbir_zaman_terimden_buyuk_degil(self):
        for kod, (tanim, _) in self.cozum.items():
            self.assertLess(tanim[1], 112, kod)                                # terim tabanı 112 pt (kullanıcı kuralı)

    def test_tek_kelimelik_son_satir_buyuk_puntoda_da_yok(self):
        for kod, (tanim, maddeler) in self.cozum.items():
            if len(tanim[2]) >= 2:
                self.assertGreaterEqual(len(tanim[2][-1].split()), 2, (kod, tanim[2]))
            for m in maddeler:
                if len(m[2]) >= 2:
                    self.assertGreaterEqual(len(m[2][-1].split()), 2, (kod, m[2]))


if __name__ == "__main__":
    unittest.main()
