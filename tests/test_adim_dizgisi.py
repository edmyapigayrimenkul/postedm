"""
tests/test_adim_dizgisi.py — Adım slaytları ve Örnek Olay sonuç slaytı (2026-10-07).

Ölçüm: bir cümlelik adımlar sayfanın yalnız %34'ünü dolduruyordu; gövdesi tek satıra sığan adımın numarası
iki satır tutanınkinden aşağıda durup kaydırırken zıplıyordu; Örnek Olay'ın 2. slaytında hüküm tepeye
yapışık, ders kutusu dipteydi, ortası boştu. Kapanış slaytına dokunulmadı (kullanıcı kararı).
Denetim betiğinin çizim olay kaydı kullanılır; ağ yok.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import make_image, yeni_formatlar

KOK = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("gorsel_denetim_betik", KOK / "scripts" / "gorsel_denetim.py")
gd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gd)

KISA = [
    {"no": "01", "baslik": "Tapu kaydını oku", "aciklama": "Tapu senedinde hangisinin yazdığına bak."},
    {"no": "02", "baslik": "İskânı sor", "aciklama": "İskân yoksa kat mülkiyetine geçilemez."},
    {"no": "03", "baslik": "Noterde sözleşme", "aciklama": "Arsa payı satışı tapuda resmî şekilde yapılır."},
]
UZUN = [
    {"no": "01", "baslik": "Tapu kaydını ve şerhleri tek tek oku",
     "aciklama": "Tapu senedinde kat irtifakı mı kat mülkiyeti mi yazdığına bak; beyanlar hanesindeki yönetim planı ve şerh "
                 "bilgilerini mutlaka kontrol et, çünkü bunlar satış sonrası hak kaybına yol açabilir."},
    {"no": "02", "baslik": "İskân durumunu belediyeden doğrula",
     "aciklama": "Yapı kullanma izin belgesi yoksa kat mülkiyetine geçilemez. Belediye imar müdürlüğünden iskân tarihini ve "
                 "belgeyi yazılı olarak iste, sözlü bilgiye güvenme."},
    {"no": "03", "baslik": "Satış işlemini tapuda yap",
     "aciklama": "Arsa payı devri ve bağımsız bölüm satışı noterde değil tapu müdürlüğünde resmî şekilde yapılır."},
]


def _net_cevap(adimlar):
    return {"format_turu": "net_cevap", "kategori_kodu": "TAPU_VE_HUKUK",
            "soru": "Tapuda kat irtifakı ile kat mülkiyeti aynı şey mi?",
            "net_cevap": "Hayır. Kat irtifakı bina bitmeden, kat mülkiyeti bina bitince kurulur.",
            "aciklama": "Kat irtifakı yapı yapılmadan önce kurulur.",
            "slayt_3_cozum": {"baslik_vurgu": "NE YAPMALI", "maddeler": copy.deepcopy(adimlar)}}


def _vaka(hukum):
    return {"format_turu": "vaka", "kategori_kodu": "TAPU_VE_HUKUK",
            "manset": "Ortağına haber vermeden hissesini sattı", "olay_detay": "Ayşe Hanım hisseli tarladaki payını üçüncü bir kişiye sattı.",
            "yargitay_hukmu": hukum, "cikarilacak_ders": "Hisse satışında noter bildirimi süreyi başlatır."}


def _ciz(veri, olcu="besleme"):
    """Slaytları çizer; (yollar, slayt olay kayıtları) döner. Çizim olayları denetim betiğinden gelir."""
    gd.kaydi_ac()
    try:
        gd._OLAYLAR.clear()
        gd._SLAYTLAR.clear()
        with tempfile.TemporaryDirectory() as tmp:
            yollar = yeni_formatlar.slaytlari_uret(veri, cikti_dizini=Path(tmp), cikti_onek="t", olcu=olcu)
            adlar = [Path(y).name for y in yollar]
            slaytlar = {Path(s["yol"]).name: s for s in gd._SLAYTLAR}
        return adlar, slaytlar
    finally:
        gd.kaydi_kapat()


def _metin_olaylari(slayt, w_h):
    return [o for o in slayt["olaylar"] if o["tur"] == "metin" and o["boyut"] == w_h and o["bbox"]]


class TestIriMi(unittest.TestCase):
    def test_hepsi_kisaysa_iri(self):
        self.assertTrue(make_image.adim_iri_mi(KISA))

    def test_tek_uzun_govde_kumeyi_normal_yapar(self):
        self.assertFalse(make_image.adim_iri_mi(KISA + [UZUN[0]]))

    def test_govde_siniri_somut_degerle(self):
        # Başlık kuralından bağımsız: kısa başlık, yalnız gövde uzunluğu değişiyor
        for uzunluk, beklenen in ((100, True), (110, True), (111, False), (200, False)):
            with self.subTest(uzunluk=uzunluk):
                self.assertEqual(make_image.adim_iri_mi([{"no": "01", "baslik": "Kısa başlık", "aciklama": "a" * uzunluk}]), beklenen)

    def test_uzun_baslik_kumeyi_normal_yapar(self):
        uzun_baslik = copy.deepcopy(KISA)
        uzun_baslik[1]["baslik"] = "İskân durumunu belediyeden yazılı doğrula"
        self.assertGreater(len(uzun_baslik[1]["baslik"]), make_image.ADIM_IRI_BASLIK)
        self.assertFalse(make_image.adim_iri_mi(uzun_baslik))

    def test_bos_ve_bozuk_girdi(self):
        self.assertFalse(make_image.adim_iri_mi([]))
        self.assertFalse(make_image.adim_iri_mi(None))
        self.assertFalse(make_image.adim_iri_mi(["metin", 3]))

    def test_sinir_degeri_dahil(self):
        sinirda = [{"no": "01", "baslik": "b" * make_image.ADIM_IRI_BASLIK, "aciklama": "a" * make_image.ADIM_IRI_GOVDE}]
        self.assertTrue(make_image.adim_iri_mi(sinirda))
        sinirda[0]["aciklama"] += "a"
        self.assertFalse(make_image.adim_iri_mi(sinirda))


class TestAdimOlcegi(unittest.TestCase):
    def _numara_puntolari(self, adimlar, olcu="besleme"):
        _, slaytlar = _ciz(_net_cevap(adimlar), olcu)
        adim_slaytlari = [s for ad, s in sorted(slaytlar.items()) if ad.endswith("_adim.jpg")]
        puntolar = []
        for s in adim_slaytlari:
            wh = s["boyut"]
            sayilar = [o for o in _metin_olaylari(s, wh) if o["metin"] in ("01", "02", "03")]
            puntolar.append(sayilar[0]["punto"])
        return puntolar

    def test_kisa_kumede_numara_iri_uzunda_normal(self):
        for olcu in ("besleme", "story"):
            self.assertEqual(set(self._numara_puntolari(KISA, olcu)), {190}, olcu)
            self.assertEqual(set(self._numara_puntolari(UZUN, olcu)), {150}, olcu)

    def test_karisik_kumede_olcek_ayni_kalir_zipalamaz(self):
        karisik = KISA[:2] + [UZUN[0]]
        self.assertEqual(len(set(self._numara_puntolari(karisik))), 1)


class TestHiza(unittest.TestCase):
    """Numara, kümedeki her slaytta aynı yükseklikte durur."""

    def _numara_y(self, adimlar, olcu):
        _, slaytlar = _ciz(_net_cevap(adimlar), olcu)
        ys = []
        for ad, s in sorted(slaytlar.items()):
            if not ad.endswith("_adim.jpg"):
                continue
            sayilar = [o for o in _metin_olaylari(s, s["boyut"]) if o["metin"] in ("01", "02", "03")]
            ys.append(round(sayilar[0]["bbox"][1]))
        return ys

    def test_gövde_satir_sayisi_farkli_olsa_da_numara_ayni_yukseklikte(self):
        for adimlar in (KISA, UZUN):
            for olcu in ("besleme", "story"):
                with self.subTest(kume=len(adimlar[0]["aciklama"]), olcu=olcu):
                    ys = self._numara_y(adimlar, olcu)
                    self.assertEqual(len(ys), 3)
                    # "01", "02", "03" glifleri üst boşlukta 1 px farklı; 2 px'in üstü gerçek kayma
                    self.assertLessEqual(max(ys) - min(ys), 2, ys)

    def test_b1_carousel_adimlari_da_ayni_yukseklikte(self):
        veri = gd.fikstur("B1")
        veri["slayt_3_cozum"] = {"baslik_vurgu": "NE YAPMALI", "maddeler": copy.deepcopy(KISA)}
        _, slaytlar = _ciz(veri, "besleme")
        ys = []
        for ad, s in sorted(slaytlar.items()):
            if ad.endswith("_adim.jpg"):
                sayilar = [o for o in _metin_olaylari(s, s["boyut"]) if o["metin"] in ("01", "02", "03")]
                ys.append(round(sayilar[0]["bbox"][1]))
        self.assertEqual(len(ys), 3, ys)
        self.assertLessEqual(max(ys) - min(ys), 2, ys)

    def test_hiza_yuksekligi_olmadan_zipliyordu(self):
        # Kanıt: kullanılan hizalama kapatılırsa aynı kümede numara yükseklikleri ayrışır
        orijinal = make_image.slayt_adim

        def hizasiz(*a, **k):
            k["hiza_yuksekligi"] = 0
            return orijinal(*a, **k)

        with patch.object(make_image, "slayt_adim", hizasiz):
            ys = self._numara_y(KISA, "besleme")
        self.assertGreater(max(ys) - min(ys), 10, ys)


class TestDoluluk(unittest.TestCase):
    def _doluluk(self, slayt):
        w_h = slayt["boyut"]
        govde = [o for o in _metin_olaylari(slayt, w_h) if (o.get("punto") or 0) >= 30 and o["metin"].strip()]
        return (max(o["bbox"][3] for o in govde) - min(o["bbox"][1] for o in govde)) / 1080

    def _ortalama(self, olcu):
        _, slaytlar = _ciz(_net_cevap(KISA), olcu)
        oranlar = [self._doluluk(s) for ad, s in slaytlar.items() if ad.endswith("_adim.jpg")]
        return sum(oranlar) / len(oranlar)

    def test_kisa_adim_slayti_iri_dizgiyle_daha_dolu(self):
        # Eski ölçüm: besleme %34, story %35. İri dizgi kapatılınca (eski davranış) ortalama düşmeli.
        for olcu in ("besleme", "story"):
            with self.subTest(olcu=olcu):
                yeni = self._ortalama(olcu)
                with patch.object(make_image, "adim_iri_mi", return_value=False):
                    eski = self._ortalama(olcu)
                self.assertGreater(yeni, eski + 0.04, (yeni, eski))


class TestVakaSonuc(unittest.TestCase):
    def _etiket_ve_kutu(self, hukum, olcu="besleme"):
        _, slaytlar = _ciz(_vaka(hukum), olcu)
        s = next(v for ad, v in slaytlar.items() if ad.endswith("_02_vaka.jpg"))
        olaylar = _metin_olaylari(s, s["boyut"])
        etiket = next(o for o in olaylar if o["metin"].strip() == "KANUNA GÖRE SONUÇ")
        ders = next(o for o in olaylar if "ÇIKARILACAK DERS" in o["metin"])
        hukum_satirlari = [o for o in olaylar if (o.get("punto") or 0) >= 40 and o["bbox"][1] > etiket["bbox"][3]]
        return etiket, ders, hukum_satirlari

    def test_kisa_hukum_tepeye_yapismaz_dikey_ortalanir(self):
        for olcu in ("besleme", "story"):
            with self.subTest(olcu=olcu):
                etiket, ders, satirlar = self._etiket_ve_kutu("Diğer paydaşlar payı hâkimin belirlediği rayiç değerle alabilir.", olcu)
                yer_ust = etiket["bbox"][1]
                ilk_y = min(o["bbox"][1] for o in satirlar)
                son_y = max(o["bbox"][3] for o in satirlar)
                ust_bosluk = yer_ust - 170  # rozet/logo bandının altı
                alt_bosluk = ders["bbox"][1] - son_y
                # Eskiden üst boşluk ≤ 36 px, alt boşluk yüzlerce px'ti. Artık ikisi de belirgin ve dengeli.
                self.assertGreater(ust_bosluk, 60, (ust_bosluk, alt_bosluk))
                self.assertLess(abs(ust_bosluk - alt_bosluk), 130, (ust_bosluk, alt_bosluk))
                self.assertLess(ilk_y, ders["bbox"][1])
                # Sığan en büyük punto: kısa hükümde eski 54 sınırında kalmaz
                self.assertGreaterEqual(max(o["punto"] for o in satirlar), 58)

    def test_uzun_hukum_hala_sigar_ve_ders_kutusunu_ezmez(self):
        uzun = ("Diğer paydaşlar, satışın kendilerine noter aracılığıyla bildirilmesinden itibaren üç ay içinde "
                "önalım hakkını kullanarak payı alıcıdan, hâkimin belirlediği rayiç değerle alabilir; süre kaçırılırsa "
                "hak düşer ve satış geçerli kalır. ") * 2
        etiket, ders, satirlar = self._etiket_ve_kutu(uzun)
        self.assertLessEqual(max(o["bbox"][3] for o in satirlar), ders["bbox"][1])

    def test_kapanis_slayti_degismedi(self):
        # Kullanıcı kararı: kapanış aynı kalır. Çizim imzası: aynı metinler aynı noktalarda.
        adlar, slaytlar = _ciz(_net_cevap(KISA), "besleme")
        kapanis = next(v for ad, v in slaytlar.items() if ad.endswith("_kapanis.jpg"))
        metinler = " ".join(o["metin"] for o in _metin_olaylari(kapanis, kapanis["boyut"]))
        self.assertIn("bilgilendirmedir", metinler)


if __name__ == "__main__":
    unittest.main()
