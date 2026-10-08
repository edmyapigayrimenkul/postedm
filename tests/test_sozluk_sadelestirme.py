"""
tests/test_sozluk_sadelestirme.py — Sözlük kaydının sadeleştirilmesi ve konu uygunluğu (2026-10-08).

12 gerçek üretimde (2026-10-07): model sözlük için de B1'in bütün şemasını dolduruyor; kullanılmayan
`slayt_*` blokları hiçbir kanala gitmiyor ama kapıyı ve hakemi yanıltıyordu (5/12 yanlış "yerel bağ" uyarısı,
1/12 yanlış ⛔). Başlık da modelin serbest cümlesiydi. Ağ yok.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import copy
import unittest
from unittest.mock import patch

from src import dogrula, generate_text as gt, konu_bankasi as kb

# Gerçek üretimden alınan biçim (S1-013, 2026-10-07)
URETIM = {
    "bicim": "B1", "format_turu": "sozluk", "terim": "ZİLYETLİKLE TESCİL",
    "tanim_metni": "Tapuda kayıtlı olmayan arazilerin yirmi yıl davasız kullanılarak tescil ettirilmesini sağlayan hukuki yoldur. Dava Hazineye açılır.",
    "puf_maddeleri": ["Süreç Hazineye karşı açılan dava ile yürütülür.", "Mera ve orman gibi yerlerde işlemez."],
    "kategori_kodu": "TAPU_VE_HUKUK", "rozet_metni": "TAPU REHBERİ", "yasal_dayanak": "Türk Medeni Kanunu md. 713 ve bilmediğim madde",
    "manset_parca_1": "Tapusuz arazide", "manset_vurgu": "20 YIL KULLANIM", "manset_parca_2": "tescil istenir",
    "spot": "Tapuda kaydı bulunmayan taşınmazları yirmi yıl aralıksız kullananlar tescil davası açabilir.",
    "soru": "Tapusuz arazi nasıl tescil edilir?",
    "slayt_2_detay": {"kartlar": [{"baslik": "Şartlar", "aciklama": "Yirmi yıl gerekir."}]},
    "slayt_3_cozum": {"maddeler": [{"no": "01", "baslik": "Dava açın", "aciklama": "Mahkemeye başvurun, bir gün bekleyin."}]},
    "slayt_4_cta": {"slogan_parca_1": "Silivri'de", "aciklama": "Trakya'daki arazilerinizde yakından takip ediyoruz.", "kaydet_metni": "Kaydet"},
    "onem_puani": 9, "caption_instagram": "Yirmi yıllık kullanım tescil sağlar.\n\nedmyapigayrimenkul.com · 0212 727 29 55\n\n#Zilyetlik",
    "konu_kodu": "S1-013", "_brief": {"mevzuat": "Türk Medeni Kanunu md. 713", "yerel": None, "veri_kaynagi": None},
}
KONU = {"kod": "S1-013", "mevzuat": "Türk Medeni Kanunu md. 713"}


class TestSadelestir(unittest.TestCase):
    def setUp(self):
        self.v = gt.sozluk_sadelestir(copy.deepcopy(URETIM), KONU)

    def test_kullanilmayan_bloklar_silinir(self):
        for alan in ("slayt_2_detay", "slayt_3_cozum", "slayt_4_cta", "soru"):
            self.assertNotIn(alan, self.v)

    def test_gosterilen_ve_yayinlanan_alanlar_aynen_kalir(self):
        for alan in ("terim", "tanim_metni", "puf_maddeleri", "caption_instagram", "kategori_kodu", "onem_puani", "_brief"):
            self.assertEqual(self.v[alan], URETIM[alan], alan)

    def test_baslik_terimden_uretilir_modelin_cumlesinden_degil(self):
        self.assertEqual(gt.manset_birlestir(self.v), "ZİLYETLİKLE TESCİL nedir?")
        self.assertNotIn("20 YIL", gt.manset_birlestir(self.v))

    def test_spot_tanimin_ilk_cumlesi(self):
        self.assertEqual(self.v["spot"], "Tapuda kayıtlı olmayan arazilerin yirmi yıl davasız kullanılarak tescil ettirilmesini sağlayan hukuki yoldur.")

    def test_yasal_dayanak_konunun_dogrulanmis_atfidir(self):
        self.assertEqual(self.v["yasal_dayanak"], "Türk Medeni Kanunu md. 713")

    def test_uzun_ilk_cumle_kelime_sinirinda_kesilir(self):
        v = gt.sozluk_sadelestir({"terim": "X Y", "tanim_metni": "kelime " * 80 + "."}, None)
        self.assertLessEqual(len(v["spot"]), 181)
        self.assertTrue(v["spot"].endswith("…"))

    def test_konu_atfi_yoksa_yasal_dayanak_ezilmez(self):
        v = gt.sozluk_sadelestir(copy.deepcopy(URETIM), {"kod": "X", "mevzuat": None})
        self.assertEqual(v["yasal_dayanak"], URETIM["yasal_dayanak"])

    def test_bozuk_girdide_cokmez(self):
        self.assertIsNone(gt.sozluk_sadelestir(None))
        self.assertEqual(gt.sozluk_sadelestir({}, None), {})
        self.assertEqual(gt.sozluk_sadelestir({"terim": ""}, None).get("manset_vurgu"), None)

    def test_kapi_yanlis_alarmlari_kesilir(self):
        # Eski kayıt: "Silivri'de" kullanılmayan CTA bloğundan, "1 gün" kullanılmayan adımdan geliyordu
        brief = {"mevzuat": "Türk Medeni Kanunu md. 713", "yerel": None, "veri_kaynagi": None}
        with patch.object(dogrula, "_kanun_metni", return_value=""):
            eski = dogrula.denetle(copy.deepcopy(URETIM), brief)
            yeni = dogrula.denetle(self.v, brief)
        self.assertTrue(any("YEREL BAĞ" in u for u in eski), eski)
        self.assertFalse(any("YEREL BAĞ" in u for u in yeni), yeni)


class TestUretimeBaglanti(unittest.TestCase):
    """`konudan_uret` sözlükte ilk üretimi de onarım turunu da sadeleştirir."""

    KONU = {"kod": "S1-013", "sutun": "S1", "bicim": "B1", "baslik": "Zilyetlikle tapu kazanma", "aci": "a",
            "kanca_kalip": "k", "mevzuat": "Türk Medeni Kanunu md. 713"}

    def _uret(self, format_turu, denetim):
        with patch.object(gt, "_uret", side_effect=lambda *a, **k: copy.deepcopy(URETIM)) as u, \
             patch.object(kb, "brief_metni", return_value="BRIEF"), \
             patch.object(dogrula, "denetle", side_effect=denetim):
            return gt.konudan_uret(dict(self.KONU), format_turu=format_turu), u

    def test_ilk_uretim_sadelesir(self):
        veri, _ = self._uret("sozluk", lambda *a, **k: [])
        self.assertNotIn("slayt_4_cta", veri)
        self.assertEqual(gt.manset_birlestir(veri), "ZİLYETLİKLE TESCİL nedir?")
        self.assertEqual(veri["yasal_dayanak"], "Türk Medeni Kanunu md. 713")

    def test_onarim_turu_da_sadelesir(self):
        yanitlar = iter([["⛔ SÜRE KAYNAKTA YOK: 1 gün"], []])
        veri, u = self._uret("sozluk", lambda *a, **k: next(yanitlar))
        self.assertEqual(u.call_count, 2)  # onarım turu çalıştı
        self.assertNotIn("slayt_3_cozum", veri)
        self.assertEqual(veri["manset_parca_2"], "nedir?")

    def test_diger_formatlar_dokunulmaz(self):
        veri, _ = self._uret("net_cevap", lambda *a, **k: [])
        self.assertIn("slayt_4_cta", veri)
        self.assertEqual(veri["manset_vurgu"], "20 YIL KULLANIM")


class TestKutuEtiketi(unittest.TestCase):
    """Kutu başlığı kitleye göre; "YATIRIMCI İÇİN ÖNEMİ" her karta yazılıyordu."""

    def test_kategoriye_gore_etiket(self):
        from src import yeni_formatlar as yf
        kiracilar = ("KIRA_VE_TAHLIYE", "EV_SAHIBI_VE_KIRACI", "KIRACI_VE_EV_SAHIBI", "KIRA", "kira_ve_tahliye")
        yatirimcilar = ("YATIRIM_VE_PIYASA", "FINANS_VE_BANKACILIK", "PIYASA_VE_YATIRIM", "YATIRIM_VE_DEGERLEME")
        genel = ("TAPU_VE_HUKUK", "IMAR_VE_PARSEL", "VERGI_VE_HARC", "MIRAS_VE_INTIKAL", "", None)
        for k in kiracilar:
            self.assertEqual(yf.sozluk_kutu_etiketi(k), "KİRACI VE EV SAHİBİ İÇİN:", k)
        for k in yatirimcilar:
            self.assertEqual(yf.sozluk_kutu_etiketi(k), "YATIRIMCI İÇİN ÖNEMİ:", k)
        for k in genel:
            self.assertEqual(yf.sozluk_kutu_etiketi(k), "BİLİNMESİ GEREKENLER:", k)

    def _kartin_etiketi(self, kategori_kodu, **ek):
        import importlib.util
        import tempfile
        from pathlib import Path
        from src import yeni_formatlar as yf
        kok = Path(__file__).resolve().parent.parent
        spec = importlib.util.spec_from_file_location("gd_etiket", kok / "scripts" / "gorsel_denetim.py")
        gd = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gd)
        gd.kaydi_ac()
        try:
            gd._OLAYLAR.clear(); gd._SLAYTLAR.clear()
            with tempfile.TemporaryDirectory() as tmp:
                yf.slaytlari_uret({"format_turu": "sozluk", "kategori_kodu": kategori_kodu, "terim": "GÜVENCE BEDELİ",
                                   "tanim_metni": "Kiracının bankaya yatırdığı güvence tutarıdır.",
                                   "puf_maddeleri": ["Üç aylık kirayı aşamaz.", "Vadeli hesapta tutulur."], **ek},
                                  cikti_dizini=Path(tmp), cikti_onek="t", olcu="besleme")
            metinler = [o["metin"] for s in gd._SLAYTLAR for o in s["olaylar"] if o["tur"] == "metin"]
        finally:
            gd.kaydi_kapat()
        return metinler

    def test_cizilen_kartta_dogru_etiket_gorunur(self):
        kira = self._kartin_etiketi("KIRA_VE_TAHLIYE")
        self.assertIn("KİRACI VE EV SAHİBİ İÇİN:", kira)
        self.assertNotIn("YATIRIMCI İÇİN ÖNEMİ:", kira)
        tapu = self._kartin_etiketi("TAPU_VE_HUKUK")
        self.assertIn("BİLİNMESİ GEREKENLER:", tapu)
        self.assertNotIn("YATIRIMCI İÇİN ÖNEMİ:", tapu)


    def test_iki_sayfali_sozlukte_de_dogru_etiket(self):
        kira = self._kartin_etiketi("KIRA_VE_TAHLIYE", iki_sayfa=True, ornek="Kira bitince depozito iade edilir.")
        self.assertIn("KİRACI VE EV SAHİBİ İÇİN:", kira)
        self.assertNotIn("YATIRIMCI İÇİN ÖNEMİ:", kira)


class TestKonuUygunlugu(unittest.TestCase):
    """Sözlük yalnız kanun metninden alıntıyla doğrulanmış konulardan üretilir."""

    @staticmethod
    def _k(kod, **ek):
        return {"kod": kod, "sutun": "S1", "bicim": "B1", "baslik": f"Konu {kod}", "aci": "a", "kanca_kalip": "k", **ek}

    def _sec(self, havuz, format_turu):
        with patch.object(kb, "havuzu_yukle", return_value=havuz), \
             patch.object(kb, "_kullanim_gecmisi", return_value={}), \
             patch.object(kb, "_format_gecmisi", return_value={}), \
             patch.object(kb, "_engellenen_konular", return_value=set()), \
             patch.object(kb, "_son_kullanilan_sutunlar", return_value=[]), \
             patch.object(kb, "tabloyu_kur"):
            return kb.sonraki_konu(sutun="S1", format_turu=format_turu)

    def test_sozluk_alintisiz_konuyu_secmez(self):
        havuz = [self._k("A", mevzuat="Kanun md. 1"), self._k("B", mevzuat="Kanun md. 2", dayanak_alintisi="x" * 50)]
        for _ in range(15):
            self.assertEqual(self._sec(havuz, "sozluk")["kod"], "B")

    def test_sozluk_icin_uygun_konu_yoksa_none(self):
        self.assertIsNone(self._sec([self._k("A", mevzuat="Kanun md. 1")], "sozluk"))

    def test_diger_formatlar_alintisiz_konuyu_secebilir(self):
        havuz = [self._k("A", mevzuat="Kanun md. 1")]
        self.assertEqual(self._sec(havuz, "net_cevap")["kod"], "A")
        self.assertEqual(self._sec(havuz, None)["kod"], "A")


if __name__ == "__main__":
    unittest.main()
