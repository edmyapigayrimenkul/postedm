"""
tests/test_piyasa_verisi.py — Emlakjet bölge ortalamaları: ayrıştırma, doğrulama, depo ve içerik blokları (2026-10-08).

Fikstürler (tests/fixtures/emlakjet_*.html) Emlakjet'in 2026-10-08 tarihli GERÇEK bölge sayfalarından birebir
kesilmiş parçalardır; hiçbir sayı elle yazılmadı. Sayfa biçimi değişirse gerçek sayfayı yeniden kesip fikstürü
yenilemek yeterli. Ağ yok: istekler sahte.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import copy
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

from src import db, dogrula, piyasa_verisi as pv

FIKSTUR = Path(__file__).resolve().parent / "fixtures"


def _html(ad: str) -> str:
    return (FIKSTUR / ad).read_text(encoding="utf-8")


DAIRE = _html("emlakjet_satilik_daire_silivri.html")
ARSA = _html("emlakjet_satilik_arsa_silivri.html")
CATALCA = _html("emlakjet_satilik_daire_catalca.html")


def _daire():
    return pv.sayfa_coz(DAIRE, "satilik-daire", "istanbul-silivri")


def _arsa():
    return pv.sayfa_coz(ARSA, "satilik-arsa", "istanbul-silivri")


def _catalca():
    return pv.sayfa_coz(CATALCA, "satilik-daire", "istanbul-catalca")


def _tarla():
    """Tarla sayfasının 2026-10-08'de canlıda okunan değerleri (fikstürü yok; arsa ölçümünden türetilir)."""
    return {**_arsa(), "tur": "satilik-tarla", "m2_fiyat": 1862.0, "m2_degisim": 0.123,
            "ort_fiyat": 5937918.0, "ilan_sayisi": 482, "mahalleler": []}


# ---------------------------------------------------------------------------
# Biçimleme
# ---------------------------------------------------------------------------

class TestBicimleme(unittest.TestCase):
    def test_tl_turkce_ayraclar(self):
        self.assertEqual(pv.tl(51094), "51.094")
        self.assertEqual(pv.tl(7153160), "7.153.160")
        self.assertEqual(pv.tl(290.39, 2), "290,39")
        self.assertEqual(pv.tl(14.66, 1), "14,7")
        self.assertEqual(pv.tl(0), "0")

    def test_yuzde(self):
        self.assertEqual(pv.yuzde(0.3162), "%31,6")
        self.assertEqual(pv.yuzde(0.0682, 2), "%6,82")
        self.assertEqual(pv.yuzde(-0.0755), "%-7,5")

    def test_tarih_yazisi(self):
        self.assertEqual(pv.tarih_yazisi("2026-10-08"), "8 Ekim 2026")
        self.assertEqual(pv.tarih_yazisi("2027-01-01"), "1 Ocak 2027")
        self.assertEqual(pv.tarih_yazisi("2026-12-31"), "31 Aralık 2026")


# ---------------------------------------------------------------------------
# Ayrıştırma (gerçek sayfa parçaları)
# ---------------------------------------------------------------------------

class TestAyristirma(unittest.TestCase):
    def test_satilik_daire_silivri_tum_alanlar(self):
        o = _daire()
        self.assertEqual((o["tur"], o["bolge"], o["bolge_adi"]), ("satilik-daire", "istanbul-silivri", "Silivri"))
        self.assertEqual(o["m2_fiyat"], 51094)
        self.assertAlmostEqual(o["m2_degisim"], 0.3162)
        self.assertEqual(o["ort_fiyat"], 7153160)
        self.assertAlmostEqual(o["m2_kira"], 290.39)
        self.assertAlmostEqual(o["m2_kira_degisim"], 0.2798)
        self.assertEqual(o["ort_kira"], 31943)
        self.assertAlmostEqual(o["getiri"], 6.82)
        self.assertEqual(o["geri_donus_yil"], 15)
        self.assertEqual(o["ilan_sayisi"], 239)
        self.assertEqual(o["mahalle_basligi"], 29)

    def test_arsada_kira_alanlari_bos(self):
        o = _arsa()
        self.assertEqual((o["m2_fiyat"], o["ort_fiyat"], o["ilan_sayisi"]), (10118, 5676198, 825))
        self.assertAlmostEqual(o["m2_degisim"], 0.1511)
        for alan in ("m2_kira", "m2_kira_degisim", "ort_kira", "getiri", "geri_donus_yil"):
            self.assertIsNone(o[alan], alan)

    def test_catalca(self):
        o = _catalca()
        self.assertEqual((o["bolge_adi"], o["m2_fiyat"], o["ilan_sayisi"]), ("Çatalca", 62962, 26))
        self.assertEqual((o["geri_donus_yil"], o["getiri"]), (14, 6.93))

    def test_mahalle_satirlari_ad_fiyat_ve_ilan_sayisi(self):
        mh = {m["bolge"]: m for m in _daire()["mahalleler"]}
        yeni = mh["istanbul-silivri-yeni-mahallesi"]
        self.assertEqual((yeni["bolge_adi"], yeni["m2_fiyat"], yeni["ilan_sayisi"]), ("Yeni Mahallesi", 51972, 88))
        self.assertAlmostEqual(yeni["m2_degisim"], 0.3831)
        self.assertEqual(mh["istanbul-silivri-piri-mehmet-pasa-mahallesi"]["ilan_sayisi"], 12)
        self.assertEqual(mh["istanbul-silivri-alibey-mahallesi"]["ilan_sayisi"], 9)
        self.assertEqual(mh["istanbul-silivri-akoren-mahallesi"]["ilan_sayisi"], 0)
        self.assertEqual(len(mh), 9)

    def test_tum_mahalleler_ilcenin_oneklidir_ve_turu_dogru(self):
        for m in _daire()["mahalleler"]:
            self.assertTrue(m["bolge"].startswith("istanbul-silivri-"), m)

    def test_bozuk_akis_parcasi_digerlerini_gotürmez(self):
        # bir push parçası geçersiz kaçışla bozulursa atlanır; öbür parçalardaki veri okunur
        bozuk = DAIRE.replace("</body>", '<script>self.__next_f.push([1,"bozuk \\x kaçış"])</script></body>')
        self.assertEqual(pv.sayfa_coz(bozuk, "satilik-daire", "istanbul-silivri")["m2_fiyat"], 51094)

    def test_json_ld_ile_kart_celisirse_hata(self):
        sahte = DAIRE.replace('"value":51094', '"value":60000')
        with self.assertRaisesRegex(pv.SayfaHatasi, "çelişiyor"):
            pv.sayfa_coz(sahte, "satilik-daire", "istanbul-silivri")

    def test_kucuk_fark_celiski_sayilmaz(self):
        # yuvarlama farkı (%1 içinde) hata değildir
        kucuk = DAIRE.replace('"value":51094', '"value":51300')
        self.assertEqual(pv.sayfa_coz(kucuk, "satilik-daire", "istanbul-silivri")["m2_fiyat"], 51094)

    def test_ne_kart_ne_json_ld_varsa_hata(self):
        bos = "<html><body>Just a moment...</body></html>"
        with self.assertRaisesRegex(pv.SayfaHatasi, "JSON-LD.*kartta bulundu"):
            pv.sayfa_coz(bos, "satilik-daire", "istanbul-silivri")

    def test_yalniz_json_ld_ile_temel_fiyat_okunur_gerisi_bos(self):
        yalniz = DAIRE.replace('\\"label\\":\\"Ort. m² Fiyatı\\"', '\\"label\\":\\"Başka\\"')
        yalniz = yalniz.replace('"label":"Ort. m² Fiyatı"', '"label":"Başka"')
        o = pv.sayfa_coz(yalniz, "satilik-daire", "istanbul-silivri")
        self.assertEqual(o["m2_fiyat"], 51094)
        self.assertIsNone(o["m2_degisim"])

    def test_ayni_kart_farkli_degerle_iki_kez_gecerse_belirsiz_hata(self):
        akis_oncesi = "</body>"
        cift = DAIRE.replace(akis_oncesi, '<script>self.__next_f.push([1,"{\\"label\\":\\"Ort. m² Fiyatı\\",\\"amount\\":9999,'
                                          '\\"type\\":\\"unitPrice\\"}"])</script></body>')
        with self.assertRaisesRegex(pv.SayfaHatasi, "birden çok kez"):
            pv.sayfa_coz(cift, "satilik-daire", "istanbul-silivri")

    def test_ayni_kart_ayni_degerle_tekrar_ederse_sorun_degil(self):
        ayni = DAIRE.replace("</body>", '<script>self.__next_f.push([1,"{\\"label\\":\\"Ort. m² Fiyatı\\",\\"amount\\":51094,'
                                        '\\"type\\":\\"unitPrice\\",\\"annualChangeRatio\\":0.3162}"])</script></body>')
        self.assertEqual(pv.sayfa_coz(ayni, "satilik-daire", "istanbul-silivri")["m2_fiyat"], 51094)

    def test_turkce_binlik_noktali_ilan_sayisi(self):
        sahte = DAIRE.replace("239 adet", "1.443 adet")
        self.assertEqual(pv.sayfa_coz(sahte, "satilik-daire", "istanbul-silivri")["ilan_sayisi"], 1443)

    def test_ilan_sayisi_yoksa_none(self):
        sahte = DAIRE.replace("239 adet", "çok sayıda")
        self.assertIsNone(pv.sayfa_coz(sahte, "satilik-daire", "istanbul-silivri")["ilan_sayisi"])

    def test_baska_turun_ve_baska_bolgenin_satiri_alinmaz(self):
        # aynı sayfada başka türün (arsa) ya da başka ilçenin (Çatalca) satırı geçerse mahalle sayılmaz
        yabanci = (
            '"className":"group listing-subregion-pill","children":[["$","$L3f",null,{"href":"/satilik-arsa/istanbul-silivri-x-mahallesi",'
            '"title":"x"}],["$","div",null,{"children":[["$","$Ld1",null,{"amount":111,"annualChangeRatio":0.1}]]}]]'
            '"className":"group listing-subregion-pill","children":[["$","$L3f",null,{"href":"/satilik-daire/istanbul-catalca-y-mahallesi",'
            '"title":"y"}],["$","div",null,{"children":[["$","$Ld1",null,{"amount":222,"annualChangeRatio":0.1}]]}]]'
        )
        import json
        kacisli = json.dumps(yabanci, ensure_ascii=False)[1:-1]
        sahte = DAIRE.replace("</body>", f'<script>self.__next_f.push([1,"{kacisli}"])</script></body>')
        adlar = {m["bolge"] for m in pv.sayfa_coz(sahte, "satilik-daire", "istanbul-silivri")["mahalleler"]}
        self.assertNotIn("istanbul-silivri-x-mahallesi", adlar)
        self.assertNotIn("istanbul-catalca-y-mahallesi", adlar)
        self.assertIn("istanbul-silivri-yeni-mahallesi", adlar)

    def test_satir_degeri_baska_akis_satiriyle_bolunse_de_dogru_okunur(self):
        # Gerçek sayfada bir mahalle satırının href'i ile tutarı arasına başka bir akış satırı girebiliyor
        # (Piri Mehmet Paşa: 33 bin karakterlik ilan verisi). Burada aynı durum, içinde yanıltıcı bir
        # `{"amount":…}` nesnesi taşıyan YAPAY bir yabancı satırla kurulur: satır kendi tutarını almalı.
        tutar = '[\\"$\\",\\"$Ld1\\",null,{\\"amount\\":51972'
        self.assertIn(tutar, DAIRE)
        yabanci = '\\n\\nca:[[\\"$\\",\\"$Le7\\",null,{}],{\\"amount\\":999999,\\"annualChangeRatio\\":9}]\\n'
        bolunmus = DAIRE.replace(tutar, yabanci + tutar, 1)
        mh = {m["bolge"]: m for m in pv.sayfa_coz(bolunmus, "satilik-daire", "istanbul-silivri")["mahalleler"]}
        self.assertEqual(mh["istanbul-silivri-yeni-mahallesi"]["m2_fiyat"], 51972)
        self.assertAlmostEqual(mh["istanbul-silivri-yeni-mahallesi"]["m2_degisim"], 0.3831)
        self.assertEqual(len(mh), 9)

    def test_tutari_olmayan_satir_komsusunun_tutarini_almaz(self):
        # ilk satırın tutar nesnesini sil: ikinci satırın tutarı birinciye atanmamalı
        i = DAIRE.index('{\\"amount\\":51972,\\"annualChangeRatio\\":0.3831}')
        sahte = DAIRE[:i] + DAIRE[i:].replace('{\\"amount\\":51972,\\"annualChangeRatio\\":0.3831}', "{}", 1)
        mh = {m["bolge"]: m for m in pv.sayfa_coz(sahte, "satilik-daire", "istanbul-silivri")["mahalleler"]}
        self.assertNotIn("istanbul-silivri-yeni-mahallesi", mh)
        self.assertEqual(mh["istanbul-silivri-mimar-sinan-mahallesi"]["m2_fiyat"], 49559)

    def test_ilan_sayisi_celiskiliyse_none(self):
        # aynı mahalle iki farklı sayıyla geçerse sayı belirsizdir: satır yayına girmez
        ek = '{"id":"140921","name":"Yeni Mahallesi","slug":"istanbul-silivri-yeni-mahallesi","count":5}'
        import json
        kacisli = json.dumps(ek, ensure_ascii=False)[1:-1]
        sahte = DAIRE.replace("</body>", f'<script>self.__next_f.push([1,"{kacisli}"])</script></body>')
        mh = {m["bolge"]: m for m in pv.sayfa_coz(sahte, "satilik-daire", "istanbul-silivri")["mahalleler"]}
        self.assertIsNone(mh["istanbul-silivri-yeni-mahallesi"]["ilan_sayisi"])


# ---------------------------------------------------------------------------
# Makullük
# ---------------------------------------------------------------------------

class TestOlcumSorunlari(unittest.TestCase):
    def test_gercek_olcumler_temiz(self):
        for o in (_daire(), _arsa(), _catalca(), _tarla()):
            self.assertEqual(pv.olcum_sorunlari(o), [], o["tur"])

    def _bozuk(self, **ek):
        return {**_daire(), **ek}

    def test_fiyat_aralik_disinda(self):
        self.assertTrue(pv.olcum_sorunlari(self._bozuk(m2_fiyat=900)))
        self.assertTrue(pv.olcum_sorunlari(self._bozuk(m2_fiyat=5_000_000)))
        self.assertTrue(pv.olcum_sorunlari(self._bozuk(m2_fiyat=None)))
        self.assertTrue(pv.olcum_sorunlari(self._bozuk(m2_fiyat=0)))

    def test_tur_basina_farkli_aralik(self):
        # 5.000 ₺/m² arsa için makul, daire için değil
        self.assertEqual(pv.olcum_sorunlari({**_arsa(), "m2_fiyat": 5000.0, "ort_fiyat": 5000.0 * 500}), [])
        self.assertTrue(pv.olcum_sorunlari(self._bozuk(m2_fiyat=1500.0, ort_fiyat=1500.0 * 140)))

    def test_ilan_sayisi_yetersiz_ya_da_okunamadi(self):
        self.assertTrue(any("yetersiz" in s for s in pv.olcum_sorunlari(self._bozuk(ilan_sayisi=8))))
        self.assertTrue(any("okunamadı" in s for s in pv.olcum_sorunlari(self._bozuk(ilan_sayisi=None))))
        self.assertEqual(pv.olcum_sorunlari(self._bozuk(ilan_sayisi=pv.ILCE_ASGARI_ILAN)), [])
        self.assertTrue(pv.olcum_sorunlari(self._bozuk(ilan_sayisi=pv.ILCE_ASGARI_ILAN - 1)))

    def test_yillik_degisim_makul_disinda(self):
        self.assertTrue(pv.olcum_sorunlari(self._bozuk(m2_degisim=3.5)))
        self.assertTrue(pv.olcum_sorunlari(self._bozuk(m2_degisim=-0.7)))
        self.assertEqual(pv.olcum_sorunlari(self._bozuk(m2_degisim=None)), [])

    def test_ima_edilen_alan_makul_degilse(self):
        # ort. fiyat ÷ m² fiyatı = 2 m² ya da 5.000 m² daire: birim/sütun kayması
        self.assertTrue(pv.olcum_sorunlari(self._bozuk(ort_fiyat=100000.0)))
        self.assertTrue(pv.olcum_sorunlari(self._bozuk(ort_fiyat=51094.0 * 5000)))

    def test_kira_aralik_disinda(self):
        self.assertTrue(pv.olcum_sorunlari(self._bozuk(m2_kira=12.0)))
        self.assertTrue(pv.olcum_sorunlari(self._bozuk(m2_kira=29000.0)))

    def test_sayfadaki_getiri_kendi_hesabimizla_tutmazsa(self):
        self.assertTrue(any("getiri" in s for s in pv.olcum_sorunlari(self._bozuk(getiri=9.5))))
        self.assertEqual(pv.olcum_sorunlari(self._bozuk(getiri=6.7)), [])      # 0,3 puan içinde

    def test_sayfadaki_geri_donus_tutmazsa(self):
        self.assertTrue(any("geri dönüş" in s for s in pv.olcum_sorunlari(self._bozuk(geri_donus_yil=25))))
        self.assertEqual(pv.olcum_sorunlari(self._bozuk(geri_donus_yil=14)), [])


# ---------------------------------------------------------------------------
# Toplama (sahte ağ)
# ---------------------------------------------------------------------------

class TestTopla(unittest.TestCase):
    HEDEFLER = (("satilik-daire", "istanbul-silivri"), ("satilik-arsa", "istanbul-silivri"), ("satilik-daire", "istanbul-catalca"))

    def _cek(self, haritasi, cagrilar):
        def cek(tur, bolge):
            cagrilar.append((tur, bolge))
            sonuc = haritasi[(tur, bolge)]
            if isinstance(sonuc, Exception):
                raise sonuc
            return sonuc
        return cek

    def test_hepsi_basarili_istekler_arasi_beklenir(self):
        cagrilar, beklemeler = [], []
        haritasi = {self.HEDEFLER[0]: DAIRE, self.HEDEFLER[1]: ARSA, self.HEDEFLER[2]: CATALCA}
        olcumler, hatalar = pv.topla(self.HEDEFLER, self._cek(haritasi, cagrilar), beklemeler.append)
        self.assertEqual(hatalar, [])
        self.assertEqual([o["bolge"] for o in olcumler], ["istanbul-silivri", "istanbul-silivri", "istanbul-catalca"])
        self.assertEqual(cagrilar, list(self.HEDEFLER))
        self.assertEqual(beklemeler, [pv.ISTEK_ARASI_SN, pv.ISTEK_ARASI_SN])     # ilk istekten önce beklenmez

    def test_bozuk_sayfa_atlanir_digerleri_devam_eder(self):
        haritasi = {self.HEDEFLER[0]: "<html>Just a moment...</html>", self.HEDEFLER[1]: ARSA, self.HEDEFLER[2]: CATALCA}
        olcumler, hatalar = pv.topla(self.HEDEFLER, self._cek(haritasi, []), lambda s: None)
        self.assertEqual(len(olcumler), 2)
        self.assertEqual(len(hatalar), 1)
        self.assertIn("satilik-daire/istanbul-silivri", hatalar[0])

    def test_makullugu_gecemeyen_olcum_kaydedilmez(self):
        sahte = DAIRE.replace('"value":51094', '"value":900').replace('\\"amount\\":51094', '\\"amount\\":900')
        haritasi = {self.HEDEFLER[0]: sahte, self.HEDEFLER[1]: ARSA, self.HEDEFLER[2]: CATALCA}
        olcumler, hatalar = pv.topla(self.HEDEFLER, self._cek(haritasi, []), lambda s: None)
        self.assertEqual(len(olcumler), 2)
        self.assertTrue(any("makul" in h for h in hatalar), hatalar)

    def test_erisim_kapaninca_kalan_hedefler_denenmez(self):
        cagrilar = []
        haritasi = {self.HEDEFLER[0]: pv.ErisimKapali("403"), self.HEDEFLER[1]: ARSA, self.HEDEFLER[2]: CATALCA}
        olcumler, hatalar = pv.topla(self.HEDEFLER, self._cek(haritasi, cagrilar), lambda s: None)
        self.assertEqual(olcumler, [])
        self.assertEqual(cagrilar, [self.HEDEFLER[0]])           # siteyi zorlamadan durur
        self.assertEqual(len(hatalar), 1)

    def test_ag_hatasi_atlanir(self):
        haritasi = {self.HEDEFLER[0]: pv.SayfaHatasi("zaman aşımı"), self.HEDEFLER[1]: ARSA, self.HEDEFLER[2]: CATALCA}
        olcumler, hatalar = pv.topla(self.HEDEFLER, self._cek(haritasi, []), lambda s: None)
        self.assertEqual(len(olcumler), 2)
        self.assertIn("zaman aşımı", hatalar[0])


class TestSayfayiCek(unittest.TestCase):
    @staticmethod
    def _yanit(kod, metin=""):
        r = MagicMock()
        r.status_code = kod
        r.text = metin
        return r

    def test_basarili_istek_kendini_tanitan_ajanla_gider(self):
        with patch.object(pv.requests, "get", return_value=self._yanit(200, "<html>ok</html>")) as get:
            self.assertEqual(pv.sayfayi_cek("satilik-daire", "istanbul-silivri"), "<html>ok</html>")
        self.assertEqual(get.call_args.args[0], "https://www.emlakjet.com/satilik-daire/istanbul-silivri")
        ajan = get.call_args.kwargs["headers"]["User-Agent"]
        self.assertIn("EDM-Yapi", ajan)
        self.assertNotIn("Mozilla", ajan)                       # tarayıcı taklidi yapılmaz
        self.assertGreaterEqual(get.call_args.kwargs["timeout"], 10)

    def test_403_ve_429_zorlanmaz_tek_istek(self):
        for kod in (403, 429):
            with patch.object(pv.requests, "get", return_value=self._yanit(kod)) as get, patch.object(pv.time, "sleep"):
                with self.assertRaises(pv.ErisimKapali):
                    pv.sayfayi_cek("satilik-daire", "istanbul-silivri")
            self.assertEqual(get.call_count, 1, kod)

    def test_404_bolge_yok(self):
        with patch.object(pv.requests, "get", return_value=self._yanit(404)) as get:
            with self.assertRaises(pv.SayfaHatasi) as e:
                pv.sayfayi_cek("satilik-daire", "istanbul-yok")
        self.assertNotIsInstance(e.exception, pv.ErisimKapali)
        self.assertEqual(get.call_count, 1)

    def test_gecici_hata_bir_kez_yeniden_denenir(self):
        with patch.object(pv.requests, "get", side_effect=[self._yanit(503), self._yanit(200, "tamam")]) as get, \
             patch.object(pv.time, "sleep") as uyku:
            self.assertEqual(pv.sayfayi_cek("satilik-daire", "istanbul-silivri"), "tamam")
        self.assertEqual(get.call_count, 2)
        uyku.assert_called_once()

    def test_ag_kopmasi_iki_denemeden_sonra_hata(self):
        with patch.object(pv.requests, "get", side_effect=requests.ConnectionError("x")) as get, patch.object(pv.time, "sleep"):
            with self.assertRaises(pv.SayfaHatasi):
                pv.sayfayi_cek("satilik-daire", "istanbul-silivri")
        self.assertEqual(get.call_count, 2)


# ---------------------------------------------------------------------------
# Depo
# ---------------------------------------------------------------------------

class _Depo(unittest.TestCase):
    def setUp(self):
        pv.tabloyu_kur()
        self._temizle()

    def tearDown(self):
        self._temizle()

    @staticmethod
    def _temizle():
        with db._baglanti_al() as conn:
            conn.execute("DELETE FROM piyasa_verisi")


class TestDepo(_Depo):
    def test_kaydet_ve_son_olcum_mahalleleriyle(self):
        yazilan = pv.kaydet([_daire()], tarih="2026-10-08")
        self.assertEqual(yazilan, 1 + 9)                       # ilçe + 9 mahalle satırı
        o = pv.son_olcum("satilik-daire", "istanbul-silivri", bugun="2026-10-09")
        self.assertEqual((o["m2_fiyat"], o["ilan_sayisi"], o["tarih"]), (51094, 239, "2026-10-08"))
        self.assertAlmostEqual(o["m2_kira"], 290.39)
        self.assertEqual(len(o["mahalleler"]), 9)
        yeni = next(m for m in o["mahalleler"] if m["bolge"] == "istanbul-silivri-yeni-mahallesi")
        self.assertEqual((yeni["bolge_adi"], yeni["m2_fiyat"], yeni["ilan_sayisi"]), ("Yeni Mahallesi", 51972, 88))

    def test_ayni_gun_tekrar_kaydi_eskisini_siler(self):
        pv.kaydet([_daire()], tarih="2026-10-08")
        pv.kaydet([_daire()], tarih="2026-10-08")
        with db._baglanti_al() as conn:
            sayi = conn.execute("SELECT COUNT(*) FROM piyasa_verisi").fetchone()[0]
        self.assertEqual(sayi, 1 + 9)                          # yinelenmedi

    def test_ayni_gun_baska_bolge_silinmez(self):
        pv.kaydet([_daire(), _catalca(), _arsa()], tarih="2026-10-08")
        pv.kaydet([_daire()], tarih="2026-10-08")
        self.assertIsNotNone(pv.son_olcum("satilik-daire", "istanbul-catalca", bugun="2026-10-08"))
        self.assertIsNotNone(pv.son_olcum("satilik-arsa", "istanbul-silivri", bugun="2026-10-08"))

    def test_farkli_gunler_gecmisi_korur_en_yenisi_okunur(self):
        eski = {**_daire(), "m2_fiyat": 40000.0}
        pv.kaydet([eski], tarih="2026-09-08")
        pv.kaydet([_daire()], tarih="2026-10-08")
        self.assertEqual(pv.son_olcum("satilik-daire", "istanbul-silivri", bugun="2026-10-09")["m2_fiyat"], 51094)
        with db._baglanti_al() as conn:
            gunler = {r[0] for r in conn.execute("SELECT tarih FROM piyasa_verisi")}
        self.assertEqual(gunler, {"2026-09-08", "2026-10-08"})

    def test_bayat_olcum_okunmaz(self):
        pv.kaydet([_daire()], tarih="2026-10-08")
        self.assertIsNotNone(pv.son_olcum("satilik-daire", "istanbul-silivri", bugun="2026-11-17"))     # 40 gün
        self.assertIsNone(pv.son_olcum("satilik-daire", "istanbul-silivri", bugun="2026-11-18"))        # 41 gün

    def test_olmayan_bolge_none(self):
        self.assertIsNone(pv.son_olcum("satilik-daire", "istanbul-yok", bugun="2026-10-08"))

    def test_yinelenen_satirda_en_yeni_id_kazanir(self):
        pv.kaydet([_daire()], tarih="2026-10-08")
        with db._baglanti_al() as conn:      # iki yazarın aynı mantıksal satırı eklemesi (birleştirme sonrası)
            conn.execute(
                "INSERT INTO piyasa_verisi (kaynak, tur, bolge, bolge_adi, tarih, m2_fiyat, ilan_sayisi) "
                "VALUES ('emlakjet', 'satilik-daire', 'istanbul-silivri', 'Silivri', '2026-10-08', 52000, 240)")
        self.assertEqual(pv.son_olcum("satilik-daire", "istanbul-silivri", bugun="2026-10-08")["m2_fiyat"], 52000)

    def test_durum_ozeti(self):
        self.assertIn("hiç toplanmadı", pv.durum_ozeti("2026-10-08"))
        pv.kaydet([_daire()], tarih="2026-10-08")
        self.assertIn("güncel", pv.durum_ozeti("2026-10-09"))
        self.assertIn("1 gün", pv.durum_ozeti("2026-10-09"))
        self.assertIn("bayat", pv.durum_ozeti("2026-12-01"))

    def test_mahalleleri_olmayan_olcum_kaydedilir(self):
        pv.kaydet([_tarla()], tarih="2026-10-08")
        o = pv.son_olcum("satilik-tarla", "istanbul-silivri", bugun="2026-10-08")
        self.assertEqual(o["mahalleler"], [])


# ---------------------------------------------------------------------------
# İçerik blokları
# ---------------------------------------------------------------------------

BUGUN = "2026-10-09"


class TestKiraCarpani(unittest.TestCase):
    def test_silivri(self):
        c = pv.kira_carpani(_daire())
        self.assertAlmostEqual(c["yil"], 51094 / (290.39 * 12), places=6)
        self.assertAlmostEqual(c["getiri"], 290.39 * 12 / 51094 * 100, places=6)
        self.assertEqual(pv.tl(c["yil"], 1), "14,7")

    def test_sayfadaki_getiriyle_tutarli(self):
        for o in (_daire(), _catalca()):
            c = pv.kira_carpani(o)
            self.assertAlmostEqual(c["getiri"], o["getiri"], delta=0.05)

    def test_kirasi_olmayanda_none(self):
        self.assertIsNone(pv.kira_carpani(_arsa()))


class TestBloklar(_Depo):
    def setUp(self):
        super().setUp()
        pv.kaydet([_daire(), _catalca(), _arsa(), _tarla()], tarih="2026-10-08")

    def test_her_blok_kaynak_tarih_nitelik_ve_kurallari_tasir(self):
        for anahtar in pv.BLOKLAR:
            with self.subTest(anahtar):
                metin = pv.blok(anahtar, BUGUN)
                self.assertIn("Emlakjet", metin)
                self.assertIn("Endeksa", metin)
                self.assertIn("8 Ekim 2026", metin)
                self.assertIn("TAHMİNİ", metin)
                self.assertIn("tapu bedeli", metin)            # nitelik: tapu bedeli DEĞİL
                self.assertIn("KURALLAR:", metin)

    def test_mahalle_blogu_yalniz_yeterli_ilanli_mahalleleri_siralar(self):
        metin = pv.blok("silivri_daire_mahalle", BUGUN)
        for ad, fiyat in (("Selimpaşa Mahallesi", "54.034"), ("Cumhuriyet Mahallesi", "52.166"), ("Yeni Mahallesi", "51.972"),
                          ("Mimar Sinan Mahallesi", "49.559"), ("Piri Mehmet Paşa Mahallesi", "36.671")):
            self.assertIn(f"- {ad}: {fiyat} ₺/m²", metin)
        for dislanan in ("Alibey", "Alipaşa", "Ortaköy", "Akören"):      # 9, 6, 2 ve 0 ilan
            self.assertNotIn(dislanan, metin)
        sira = [metin.index(a) for a in ("Selimpaşa Mahallesi:", "Cumhuriyet Mahallesi:", "Yeni Mahallesi:", "Mimar Sinan Mahallesi:",
                                         "Piri Mehmet Paşa Mahallesi:")]
        self.assertEqual(sira, sorted(sira))                            # pahalıdan ucuza

    def test_mahalle_blogu_ilce_ortalamasi_ve_hesaplanmis_fark(self):
        metin = pv.blok("silivri_daire_mahalle", BUGUN)
        self.assertIn("ortalama 51.094 ₺/m² (239 ilan; son bir yılda %31,6 değişim)", metin)
        beklenen = pv.tl((54034 / 36671 - 1) * 100, 1)
        self.assertEqual(beklenen, "47,3")
        self.assertIn(f"yüzde {beklenen} fark", metin)
        self.assertIn("(Selimpaşa Mahallesi)", metin)
        self.assertIn("(Piri Mehmet Paşa Mahallesi)", metin)

    def test_mahalle_siniri_tam_on_dahil_dokuz_haric(self):
        with db._baglanti_al() as conn:
            conn.execute("UPDATE piyasa_verisi SET ilan_sayisi = 10 WHERE bolge = 'istanbul-silivri-alibey-mahallesi'")
            conn.execute("UPDATE piyasa_verisi SET ilan_sayisi = 9 WHERE bolge = 'istanbul-silivri-piri-mehmet-pasa-mahallesi'")
        metin = pv.blok("silivri_daire_mahalle", BUGUN)
        self.assertIn("- Alibey Mahallesi: 30.784 ₺/m² (10 ilan)", metin)
        self.assertNotIn("Piri Mehmet Paşa", metin)

    def test_mahalle_blogu_yeterli_mahalle_yoksa_none(self):
        with db._baglanti_al() as conn:
            conn.execute("UPDATE piyasa_verisi SET ilan_sayisi = 5 WHERE ust_bolge = 'istanbul-silivri' AND tur = 'satilik-daire' "
                         "AND ilan_sayisi >= 10")
        self.assertIsNone(pv.blok("silivri_daire_mahalle", BUGUN))

    def test_mahalle_blogu_en_az_uc_mahalle_ister(self):
        with db._baglanti_al() as conn:
            conn.execute("UPDATE piyasa_verisi SET ilan_sayisi = 5 WHERE bolge IN ('istanbul-silivri-yeni-mahallesi', "
                         "'istanbul-silivri-mimar-sinan-mahallesi', 'istanbul-silivri-selimpasa-mahallesi')")
        self.assertIsNone(pv.blok("silivri_daire_mahalle", BUGUN))      # geriye 2 mahalle kaldı

    def test_kira_carpani_blogu(self):
        metin = pv.blok("silivri_kira_carpani", BUGUN)
        self.assertIn("satılık daire ortalama 51.094 ₺/m²", metin)
        self.assertIn("aylık 290,39 ₺/m²", metin)
        self.assertIn("14,7 yıl", metin)
        self.assertIn("%6,82", metin)
        self.assertIn("- Çatalca: satılık daire 62.962 ₺/m², kira 363,75 ₺/m²; kira çarpanı 14,4 yıl, brüt getiri %6,93", metin)
        self.assertIn("brüt", metin)
        self.assertIn("aidat", metin)

    def test_kira_carpani_komsusuz_da_kurulur(self):
        with db._baglanti_al() as conn:
            conn.execute("DELETE FROM piyasa_verisi WHERE bolge LIKE 'istanbul-catalca%'")
        metin = pv.blok("silivri_kira_carpani", BUGUN)
        self.assertIn("14,7 yıl", metin)
        self.assertNotIn("KOMŞU BÖLGELER", metin)

    def test_kira_carpani_komsu_baska_gunse_o_satir_yazilmaz(self):
        with db._baglanti_al() as conn:
            conn.execute("UPDATE piyasa_verisi SET tarih = '2026-10-01' WHERE bolge LIKE 'istanbul-catalca%'")
        self.assertNotIn("Çatalca", pv.blok("silivri_kira_carpani", BUGUN))

    def test_kira_carpani_kirasiz_olcumde_none(self):
        with db._baglanti_al() as conn:
            conn.execute("UPDATE piyasa_verisi SET m2_kira = NULL WHERE tur = 'satilik-daire' AND bolge = 'istanbul-silivri'")
        self.assertIsNone(pv.blok("silivri_kira_carpani", BUGUN))

    def test_arsa_tarla_daire_blogu(self):
        metin = pv.blok("silivri_arsa_tarla_daire", BUGUN)
        self.assertIn("SİLİVRİ SATILIK ARSA: ortalama 10.118 ₺/m² (825 ilan; son bir yılda %15,1 değişim)", metin)
        self.assertIn("SİLİVRİ SATILIK TARLA: ortalama 1.862 ₺/m² (482 ilan; son bir yılda %12,3 değişim)", metin)
        self.assertIn("SİLİVRİ SATILIK DAİRE: ortalama 51.094 ₺/m² (239 ilan; son bir yılda %31,6 değişim)", metin)
        self.assertIn("getiri hesabı değildir", metin)

    def test_arsa_tarla_daire_biri_eksikse_none(self):
        with db._baglanti_al() as conn:
            conn.execute("DELETE FROM piyasa_verisi WHERE tur = 'satilik-tarla'")
        self.assertIsNone(pv.blok("silivri_arsa_tarla_daire", BUGUN))

    def test_arsa_tarla_daire_olcumler_ayni_gunden_olmali(self):
        with db._baglanti_al() as conn:
            conn.execute("UPDATE piyasa_verisi SET tarih = '2026-10-02' WHERE tur = 'satilik-tarla'")
        self.assertIsNone(pv.blok("silivri_arsa_tarla_daire", BUGUN))

    def test_bayat_veri_hicbir_blogu_kurmaz(self):
        for anahtar in pv.BLOKLAR:
            self.assertIsNone(pv.blok(anahtar, "2026-12-01"), anahtar)

    def test_hic_veri_yoksa_none(self):
        self._temizle()
        for anahtar in pv.BLOKLAR:
            self.assertIsNone(pv.blok(anahtar, BUGUN), anahtar)

    def test_bilinmeyen_anahtar_hatadir_sessizce_kapanmaz(self):
        with self.assertRaises(KeyError):
            pv.blok("silivri_yok", BUGUN)

    def test_brief_blok_metnini_olcut_yapar(self):
        metin = pv.blok("silivri_kira_carpani", BUGUN)
        brief = pv.brief_olustur(metin)
        self.assertEqual(brief["mevzuat_metni"], metin)
        self.assertEqual(brief["veri_blogu_metni"], metin)
        self.assertIsNone(brief["mevzuat"])
        self.assertNotIn("veri_kaynagi", brief)
        self.assertNotIn("kaynak_metin_olcut", brief)


# ---------------------------------------------------------------------------
# Kapı: içerik veri bloğuna karşı denetlenir
# ---------------------------------------------------------------------------

class TestKapi(_Depo):
    def setUp(self):
        super().setUp()
        pv.kaydet([_daire(), _catalca()], tarih="2026-10-08")
        self.blok = pv.blok("silivri_kira_carpani", BUGUN)
        self.brief = pv.brief_olustur(self.blok)

    def _icerik(self, **ek):
        icerik = {
            "bicim": "B4", "format_turu": "b1",
            "manset": "Silivri'de kira çarpanı 14,7 yıl",
            "spot": "Emlakjet'in 8 Ekim 2026 verilerine göre Silivri'de satılık daire ortalama 51.094 ₺/m², kira ortalama 290,39 ₺/m².",
            "slayt_2_detay": {"baslik": "Brüt getiri", "metin": "Yıllık brüt kira getirisi %6,82; Çatalca'da kira çarpanı 14,4 yıl."},
            "caption_instagram": "Kaynak: Emlakjet / Endeksa tahmini bölge ortalamaları.",
        }
        icerik.update(ek)
        return icerik

    def test_bloktaki_rakamlarla_yazilan_icerik_temiz_gecer(self):
        self.assertEqual(dogrula.denetle(self._icerik(), self.brief), [])

    def test_blokta_olmayan_yuzde_kritik(self):
        u = dogrula.denetle(self._icerik(spot="Silivri'de ortalama m² fiyatı bir yılda %45 arttı. Kaynak: Emlakjet."), self.brief)
        self.assertTrue(dogrula.kritik_var(u), u)
        self.assertTrue(any("45" in x for x in u), u)

    def test_yuvarlama_kritik(self):
        u = dogrula.denetle(self._icerik(manset="Silivri'de kira çarpanı 15 yıl"), self.brief)
        self.assertTrue(dogrula.kritik_var(u), u)                         # blokta 14,7 var, 15 yok

    def test_kendi_hesabi_kritik(self):
        u = dogrula.denetle(self._icerik(spot="100 m²'lik daire ortalama 5.109.400 ₺ eder. Emlakjet verisi."), self.brief)
        self.assertTrue(dogrula.kritik_var(u), u)

    def test_blokta_olmayan_ilan_sayisi_ve_m2_kritik(self):
        for ifade in ("Silivri'de 500 ilan incelendi", "ortalama 120 m² daire"):
            with self.subTest(ifade):
                u = dogrula.denetle(self._icerik(spot=f"{ifade}. Emlakjet ortalamaları."), self.brief)
                self.assertTrue(dogrula.kritik_var(u), u)

    def test_tek_basina_1_veri_iddiasi_sayilmaz(self):
        # mahalle bloğunda "son bir yılda %31,6" geçer; içerik "1 yıl" yazarsa blokla çelişen bir iddia değildir
        blok = pv.blok("silivri_daire_mahalle", BUGUN)
        icerik = {"spot": "Emlakjet'e göre son 1 yılda ortalama fiyat %31,6 değişti: 51.094 ₺/m²."}
        u = dogrula.denetle(icerik, pv.brief_olustur(blok))
        self.assertFalse(any("VERİ BLOĞUNDA" in x for x in u), u)
        self.assertFalse(dogrula.kritik_var(u), u)

    def test_tek_basina_1_sayisi_denetlenmez_ama_2_denetlenir(self):
        # "1 kat", "%1" gibi tek başına 1 veri iddiası değildir; 2 ise blokta yoksa uydurmadır
        blok = "SİLİVRİ: ortalama 51.094 ₺/m²"
        temiz = dogrula.veri_blogu_denetimi({"spot": "Emlakjet'e göre ortalama 51.094 ₺/m²; 1 kat fark yok."}, blok)
        self.assertFalse(any("VERİ BLOĞUNDA" in x for x in temiz), temiz)
        sorunlu = dogrula.veri_blogu_denetimi({"spot": "Emlakjet'e göre ortalama 51.094 ₺/m²; 2 kat fark var."}, blok)
        self.assertTrue(any("VERİ BLOĞUNDA YOK: 2" in x for x in sorunlu), sorunlu)

    def test_birimsiz_sayilar_denetlenmez(self):
        u = dogrula.denetle(self._icerik(slayt_3_cozum={"maddeler": [{"no": "01", "baslik": "Üç adım", "aciklama": "3 adımda bak."}]}), self.brief)
        self.assertEqual(u, [])

    def test_kaynak_atfi_yoksa_kritik(self):
        icerik = self._icerik(spot="Silivri'de satılık daire ortalama 51.094 ₺/m².",
                              caption_instagram="Ortalama kira 290,39 ₺/m².")
        u = dogrula.denetle(icerik, self.brief)
        self.assertTrue(dogrula.kritik_var(u), u)
        self.assertTrue(any("KAYNAK ATFI" in x for x in u), u)

    def test_endeksa_anmak_da_yeter(self):
        icerik = self._icerik(spot="Endeksa hesaplarına göre ortalama 51.094 ₺/m².", caption_instagram="Kira ortalama 290,39 ₺/m².")
        self.assertFalse(any("KAYNAK ATFI" in x for x in dogrula.denetle(icerik, self.brief)))

    def test_ortalama_demeyen_icerik_uyarilir_kritik_degil(self):
        icerik = self._icerik(spot="Emlakjet'e göre Silivri'de daire 51.094 ₺/m².", caption_instagram="Kira 290,39 ₺/m².",
                              slayt_2_detay={"baslik": "Getiri", "metin": "Yıllık getiri %6,82."}, manset="Silivri'de kira çarpanı 14,7 yıl")
        u = dogrula.denetle(icerik, self.brief)
        self.assertTrue(any("ORTALAMA DEMİYOR" in x for x in u), u)
        self.assertFalse(dogrula.kritik_var(u), u)

    def test_tapu_bedeli_iddiasi_uyarilir(self):
        u = dogrula.denetle(self._icerik(spot="Emlakjet'e göre ortalama tapu bedeli 51.094 ₺/m²."), self.brief)
        self.assertTrue(any("NİTELİK" in x for x in u), u)

    def test_kanun_maddesi_anmak_uydurmadir(self):
        u = dogrula.denetle(self._icerik(slayt_2_detay={"baslik": "Hukuk", "metin": "TBK md. 344 gereği artış sınırlıdır."}), self.brief)
        self.assertTrue(dogrula.kritik_var(u), u)

    def test_sure_blokta_olmayan_kritik(self):
        u = dogrula.denetle(self._icerik(slayt_2_detay={"baslik": "Süre", "metin": "Yatırım 25 yılda geri döner."}), self.brief)
        self.assertTrue(dogrula.kritik_var(u), u)

    def test_veri_blogu_olmayan_brief_eskisi_gibi(self):
        # piyasa verisi kullanmayan içerik bu denetimden etkilenmez
        self.assertEqual(dogrula.veri_blogu_denetimi({"spot": "Emlakjet ortalama"}, "51.094"), [])
        u = dogrula.denetle({"spot": "Kira artışı %25 olabilir."}, {"mevzuat": None, "yerel": None, "veri_kaynagi": "TÜİK"})
        self.assertFalse(any("VERİ BLOĞUNDA" in x for x in u), u)


# ---------------------------------------------------------------------------
# Konu seçimi, brief ve üretim bağlantısı
# ---------------------------------------------------------------------------

from src import generate_text as gt, konu_bankasi as kb


def _konu(kod: str, veri_blogu=None, sutun: str = "S4") -> dict:
    konu = {"kod": kod, "sutun": sutun, "bicim": "B4", "baslik": f"Konu {kod}", "aci": "açı", "kanca_kalip": "rakam",
            "mevzuat": None, "yerel": "Doğrudan Silivri"}
    if veri_blogu:
        konu["veri_blogu"] = veri_blogu
    return konu


class TestKonuSecimi(unittest.TestCase):
    def _sec(self, havuz, *, blok="BLOK", format_turu="b1"):
        blok_yama = patch.object(pv, "blok", side_effect=blok if callable(blok) else (lambda anahtar, bugun=None: blok))
        with patch.object(kb, "havuzu_yukle", return_value=havuz), \
             patch.object(kb, "_kullanim_gecmisi", return_value={}), \
             patch.object(kb, "_format_gecmisi", return_value={}), \
             patch.object(kb, "_engellenen_konular", return_value=set()), \
             patch.object(kb, "_son_kullanilan_sutunlar", return_value=[]), \
             patch.object(kb, "tabloyu_kur"), blok_yama as yama:
            secim = kb.sonraki_konu(sutun="S4", format_turu=format_turu)
        return secim, yama

    def test_veri_varken_konu_secilebilir(self):
        secim, _ = self._sec([_konu("S4-001", "silivri_daire_mahalle")])
        self.assertEqual(secim["kod"], "S4-001")

    def test_veri_yokken_konu_secilmez_baska_konu_secilir(self):
        havuz = [_konu("S4-001", "silivri_daire_mahalle"), _konu("S4-005")]
        for _ in range(15):
            self.assertEqual(self._sec(havuz, blok=None)[0]["kod"], "S4-005")

    def test_yalniz_veri_konusu_varken_veri_yoksa_hic_konu_uretilmez(self):
        self.assertIsNone(self._sec([_konu("S4-001", "silivri_daire_mahalle")], blok=None)[0])

    def test_b1_disi_formatlarda_veri_konusu_secilmez(self):
        for fmt in ("nedir_dogrusu", "net_cevap", "vaka", "reels", "finans", "sozluk"):
            with self.subTest(fmt):
                self.assertIsNone(self._sec([_konu("S4-001", "silivri_daire_mahalle")], format_turu=fmt)[0])

    def test_veri_okuma_hatasi_konuyu_atlar_secimi_cokertmez(self):
        def patla(anahtar, bugun=None):
            raise RuntimeError("db kilitli")
        havuz = [_konu("S4-001", "silivri_daire_mahalle"), _konu("S4-005")]
        self.assertEqual(self._sec(havuz, blok=patla)[0]["kod"], "S4-005")

    def test_anahtarsiz_konu_veriye_hic_bakmaz(self):
        secim, yama = self._sec([_konu("S4-005")])
        self.assertEqual(secim["kod"], "S4-005")
        yama.assert_not_called()

    def test_engelli_ve_gercek_konular_tutarli(self):
        # gerçek konu bankası: veri konuları geçerli anahtar taşır, engelli olanlar bu mekanizmayı kullanmaz
        veri_konulari = [k for k in kb.havuzu_yukle() if k.get("veri_blogu")]
        self.assertGreaterEqual(len(veri_konulari), 3)
        for k in veri_konulari:
            self.assertIn(k["veri_blogu"], pv.BLOKLAR, k["kod"])
            self.assertFalse(k.get("engel"), k["kod"])
            self.assertIsNone(k.get("mevzuat"), k["kod"])       # piyasa içeriği kanun maddesi anmaz
            self.assertEqual(k["bicim"], "B4", k["kod"])


class TestBriefMetni(unittest.TestCase):
    def test_blok_brief_e_girer_ve_veri_yok_yasagi_kalkar(self):
        konu = {**_konu("S4-004", "silivri_kira_carpani"), "_veri_blogu": "SİLİVRİ: 51.094 ₺/m²"}
        metin = kb.brief_metni(konu)
        self.assertIn("PİYASA VERİSİ", metin)
        self.assertIn("SİLİVRİ: 51.094 ₺/m²", metin)
        self.assertNotIn("VERİ KAYNAĞI: YOK", metin)          # B4 için "oran verme" yasağı veri varken geçersiz
        self.assertIn("Kanun maddesi numarası YAZMA", metin)  # mevzuat yine yok

    def test_blogu_olmayan_b4_konu_eskisi_gibi_oran_vermez(self):
        metin = kb.brief_metni(_konu("S4-005"))
        self.assertIn("VERİ KAYNAĞI: YOK", metin)
        self.assertNotIn("PİYASA VERİSİ", metin)


class TestKonudanUret(_Depo):
    """`generate_text.konudan_uret`: blok çözülür, prompta girer, brief'e ölçüt olur; veri yoksa model çağrılmaz."""

    def setUp(self):
        super().setUp()
        pv.kaydet([_daire(), _catalca()], tarih="2026-10-08")
        self._tarih = patch.object(pv, "_tr_bugun", return_value=BUGUN)
        self._tarih.start()
        self.konu = _konu("S4-004", "silivri_kira_carpani")

    def tearDown(self):
        self._tarih.stop()
        super().tearDown()

    TEMIZ = {
        "bicim": "B4", "format_turu": "b1",
        "manset": "Silivri'de kira çarpanı 14,7 yıl",
        "spot": "Emlakjet'in 8 Ekim 2026 verilerine göre Silivri'de satılık daire ortalama 51.094 ₺/m², kira ortalama 290,39 ₺/m².",
        "caption_instagram": "Kaynak: Emlakjet / Endeksa tahmini bölge ortalamaları. Brüt getiri %6,82.",
    }

    def test_blok_prompta_ve_brief_e_girer(self):
        with patch.object(gt, "_uret", return_value=copy.deepcopy(self.TEMIZ)) as uret:
            veri = gt.konudan_uret(self.konu, "b1")
        girdi = uret.call_args.args[0]
        self.assertIn("PİYASA VERİSİ", girdi)
        self.assertIn("14,7 yıl", girdi)
        brief = veri["_brief"]
        self.assertEqual(brief["veri_blogu_metni"], brief["mevzuat_metni"])
        self.assertIn("14,7 yıl", brief["veri_blogu_metni"])
        self.assertIsNone(brief["mevzuat"])
        self.assertNotIn("veri_kaynagi", brief)
        self.assertEqual(veri["konu_kodu"], "S4-004")

    def test_veri_yoksa_model_hic_cagrilmaz(self):
        self._temizle()
        with patch.object(gt, "_uret") as uret:
            self.assertIsNone(gt.konudan_uret(self.konu, "b1"))
        uret.assert_not_called()

    def test_bayat_veride_model_cagrilmaz(self):
        self._tarih.stop()
        with patch.object(pv, "_tr_bugun", return_value="2026-12-30"), patch.object(gt, "_uret") as uret:
            self.assertIsNone(gt.konudan_uret(self.konu, "b1"))
        uret.assert_not_called()
        self._tarih.start()

    def test_uydurma_rakamli_icerik_duzeltme_turuna_girer(self):
        uydurma = {**copy.deepcopy(self.TEMIZ), "spot": "Emlakjet'e göre Silivri'de fiyatlar bir yılda %45 arttı; ortalama 51.094 ₺/m²."}
        with patch.object(gt, "_uret", side_effect=[uydurma, copy.deepcopy(self.TEMIZ)]) as uret:
            veri = gt.konudan_uret(self.konu, "b1")
        self.assertEqual(uret.call_count, 2)
        self.assertIn("RAKAM VERİ BLOĞUNDA YOK", uret.call_args_list[1].args[0])
        self.assertNotIn("%45", veri["spot"])

    def test_blogu_olmayan_konu_etkilenmez(self):
        konu = _konu("S4-005")
        with patch.object(gt, "_uret", return_value={"bicim": "B4", "manset": "x"}) as uret:
            veri = gt.konudan_uret(konu, "b1")
        self.assertNotIn("PİYASA VERİSİ", uret.call_args.args[0])
        self.assertNotIn("veri_blogu_metni", veri["_brief"])


# ---------------------------------------------------------------------------
# Betik ve iş akışı
# ---------------------------------------------------------------------------

import contextlib
import importlib.util
import io
import sys

import yaml

KOK = Path(__file__).resolve().parent.parent


def _betik():
    spec = importlib.util.spec_from_file_location("piyasa_topla_betik", KOK / "scripts" / "piyasa_topla.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class TestBetik(_Depo):
    @classmethod
    def setUpClass(cls):
        cls.bt = _betik()

    def _calistir(self, *argv, toplama):
        with patch.object(sys, "argv", ["piyasa_topla.py", *argv]), patch.object(pv, "topla", return_value=toplama), \
             contextlib.redirect_stdout(io.StringIO()) as cikti:
            kod = self.bt.main()
        return kod, cikti.getvalue()

    def _satir_sayisi(self):
        with db._baglanti_al() as conn:
            return conn.execute("SELECT COUNT(*) FROM piyasa_verisi").fetchone()[0]

    def test_basarili_toplama_kaydeder_ve_sifir_doner(self):
        kod, _ = self._calistir(toplama=([_daire(), _arsa()], []))
        self.assertEqual(kod, 0)
        self.assertEqual(self._satir_sayisi(), (1 + 9) + (1 + 4))

    def test_kismi_basari_iyi_olanlari_kaydeder_ama_kirmizi_biter(self):
        kod, _ = self._calistir(toplama=([_daire()], ["satilik-arsa/istanbul-silivri: 403"]))
        self.assertEqual(kod, 1)
        self.assertEqual(self._satir_sayisi(), 1 + 9)

    def test_hic_olcum_yoksa_veritabanina_dokunulmaz(self):
        kod, _ = self._calistir(toplama=([], ["hepsi: 403"]))
        self.assertEqual(kod, 1)
        self.assertEqual(self._satir_sayisi(), 0)

    def test_kuru_calisma_kaydetmez(self):
        kod, _ = self._calistir("--kuru", toplama=([_daire()], []))
        self.assertEqual(kod, 0)
        self.assertEqual(self._satir_sayisi(), 0)
        kod, _ = self._calistir("--kuru", toplama=([_daire()], ["x: hata"]))
        self.assertEqual(kod, 1)
        self.assertEqual(self._satir_sayisi(), 0)

    def test_goster_veriyi_ve_bloklari_yazar(self):
        pv.kaydet([_daire(), _catalca(), _arsa(), _tarla()], tarih=pv._tr_bugun())
        with patch.object(sys, "argv", ["piyasa_topla.py", "--goster"]), patch.object(pv, "topla") as topla, \
             contextlib.redirect_stdout(io.StringIO()) as cikti:
            kod = self.bt.main()
        topla.assert_not_called()                      # göstermek ağa çıkmaz
        self.assertEqual(kod, 0)
        yazi = cikti.getvalue()
        self.assertIn("Piyasa verisi: son toplama", yazi)
        self.assertIn("silivri_kira_carpani: HAZIR", yazi)
        self.assertIn("14,7 yıl", yazi)

    def test_goster_veri_yoksa_blogu_kuramiyor_der(self):
        with patch.object(sys, "argv", ["piyasa_topla.py", "--goster"]), contextlib.redirect_stdout(io.StringIO()) as cikti:
            self.assertEqual(self.bt.main(), 0)
        self.assertIn("KURULAMIYOR", cikti.getvalue())


class TestIsAkisi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metin = (KOK / ".github/workflows/piyasa-verisi.yml").read_text(encoding="utf-8")
        cls.yml = yaml.safe_load(cls.metin)

    def test_aylik_ve_elle_tetiklenir(self):
        on = self.yml.get("on") or self.yml.get(True)
        self.assertEqual([s["cron"] for s in on["schedule"]], ["0 6 1 * *"])
        self.assertIn("workflow_dispatch", on)

    def test_veritabani_kuyruguna_girer_ve_yazma_izni_var(self):
        self.assertEqual(self.yml["concurrency"]["group"], "edm-veritabani")
        self.assertFalse(self.yml["concurrency"]["cancel-in-progress"])
        self.assertEqual(self.yml["jobs"]["topla"]["permissions"]["contents"], "write")

    def test_adimlar_sirasi_toplama_kaydetme_bildirim(self):
        adimlar = self.yml["jobs"]["topla"]["steps"]
        komutlar = [str(a.get("run", "")) for a in adimlar]
        topla = next(i for i, k in enumerate(komutlar) if "piyasa_topla.py" in k and "--goster" not in k)
        kaydet = next(i for i, k in enumerate(komutlar) if "db_kaydet.py" in k)
        self.assertLess(topla, kaydet)
        self.assertEqual(adimlar[kaydet].get("if"), "always()")     # kısmi başarı da kaydedilir
        self.assertEqual(adimlar[-1].get("if"), "failure()")
        self.assertIn("TELEGRAM_BOT_TOKEN", adimlar[-1]["env"])

    def test_zaman_asimi_var(self):
        self.assertLessEqual(self.yml["jobs"]["topla"]["timeout-minutes"], 30)


if __name__ == "__main__":
    unittest.main()
