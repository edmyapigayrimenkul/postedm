"""
tests/test_capraz_denetim.py — Anlam kayması hakemi (2026-10-07).

Düzenli ifade "geçerlidir" ile "geçersizdir"i ayıramaz; ikinci bir model kaynakla içeriği karşılaştırır.
Hakem modeldir ve yanılabilir: bulgu yalnızca ⚠️ olur ve her bulgu iki yerden kanıt ister (içerikten ve
kaynaktan birebir alıntı). Ağ yok: model yanıtı sahte `cagri` ile verilir.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import json
import unittest
from unittest.mock import patch

from src import capraz_denetim as cd, dogrula

KAYNAK = (
    "Madde 30 – Kat malikleri kurulu, kat maliklerinin sayı ve arsa payı bakımından yarısından fazlasiyle "
    "toplanır ve oy çokluğuyla karar verir. [4] İkinci toplantıda karar yeter sayısı, katılanların salt "
    "çoğunluğudur. Bu kanunda yeter sayı için ayrıca konulmuş olan hükümler saklıdır. Toplantıya katılmayan "
    "kat malikine karar noter aracılığıyla bildirilir."
)

VERI = {
    "bicim": "B1",
    "format_turu": "net_cevap",
    "kategori_kodu": "TAPU_VE_HUKUK",
    "manset": "Kat malikleri kurulunda karar nasıl alınır?",
    "spot": "İlk toplantıda da ikinci toplantıda da katılanların salt çoğunluğu karar verir.",
    "kartlar": [
        {"baslik": "İlk toplantı", "aciklama": "Kat maliklerinin sayı ve arsa payı bakımından yarısından fazlası toplanmalıdır."},
        {"baslik": "Bildirim", "aciklama": "Gelmeyen malike karar noter aracılığıyla bildirilir."},
    ],
    "caption_instagram": "Kat malikleri kurulu kararları.\nedmyapigayrimenkul.com\n#kmk #apartman",
    "_brief": {"mevzuat": "Kat Mülkiyeti Kanunu md. 30"},
}


def _cevap(*sorunlar) -> str:
    return json.dumps({"sorunlar": list(sorunlar)}, ensure_ascii=False)


GERCEK = {
    "tur": "birlestirme", "satir": 2,
    "icerik_alintisi": "İlk toplantıda da ikinci toplantıda da katılanların salt çoğunluğu karar verir",
    "kaynak_alintisi": "İkinci toplantıda karar yeter sayısı, katılanların salt çoğunluğudur",
    "aciklama": "Salt çoğunluk yalnız ikinci toplantı içindir; ilk toplantıda yarıdan fazlası aranır.",
}


class _Hakem:
    """Sahte model: verilen yanıtı döner, kaç kez sorulduğunu ve istemi tutar."""

    def __init__(self, yanit):
        self.yanit, self.sayi, self.istemler = yanit, 0, []

    def __call__(self, istem, sistem):
        self.sayi += 1
        self.istemler.append((istem, sistem))
        if isinstance(self.yanit, Exception):
            raise self.yanit
        return self.yanit


class TestIcerikSatirlari(unittest.TestCase):
    def test_teknik_alanlar_kodlar_ve_adresler_girmez(self):
        satirlar = cd.icerik_satirlari({
            **VERI, "gorsel_url": "https://x.com/a b c d e f.jpg", "ulke_kodu": "TR",
            "hashtags": "kat mülkiyeti apartman yönetimi", "ikon": "kapı anahtar simge adı",
            "kaynak_url": "kaynak sitesi adresi burada", "foto_url": "fotoğraf dosyası yolu burada",
        })
        metin = " ".join(satirlar)
        for teknik in ("apartman yönetimi", "simge adı", "sitesi adresi", "dosyası yolu"):
            self.assertNotIn(teknik, metin)
        self.assertNotIn("TAPU_VE_HUKUK", metin)
        self.assertNotIn("net_cevap", metin)
        self.assertNotIn("https://", metin)
        self.assertNotIn("Kat Mülkiyeti Kanunu md. 30", metin)  # _brief

    def test_caption_govdesi_girer_hashtag_ve_iletisim_satiri_girmez(self):
        metin = " ".join(cd.icerik_satirlari(VERI))
        self.assertIn("Kat malikleri kurulu kararları.", metin)
        self.assertNotIn("#kmk", metin)
        self.assertNotIn("edmyapigayrimenkul", metin)

    def test_kalin_isareti_silinir_ve_tekrar_atilir(self):
        satirlar = cd.icerik_satirlari({"manset": "Karar **salt çoğunlukla** alınır", "slayt": "Karar salt çoğunlukla alınır"})
        self.assertEqual(satirlar, ["Karar salt çoğunlukla alınır"])

    def test_haber_semasi_alanlari_girer(self):
        satirlar = cd.icerik_satirlari({"detay_yazisi": "Birinci paragraf burada.\n\nİkinci paragraf burada.", "vurgu_sayi": "%5"})
        self.assertTrue(any("Birinci paragraf" in s for s in satirlar))


class TestGurultuSuzgecleri(unittest.TestCase):
    """2026-10-07 gerçek model denemesinde çıkan yanlış alarmlar: kapanış çağrısı ve yazarın yorumu."""

    def setUp(self):
        cd._ONBELLEK.clear()

    def test_kapanis_cagrisi_icerik_sayilmaz(self):
        veri = {**VERI, "caption_instagram": "Kat malikleri kurulu kararları nasıl alınır.\nTapu randevusundan önce açıp bakmak için kaydedin.\nedmyapigayrimenkul.com"}
        metin = " ".join(cd.icerik_satirlari(veri))
        self.assertIn("kararları nasıl alınır", metin)
        self.assertNotIn("kaydedin", metin)

    def test_uzun_cumle_icindeki_kaydet_kelimesi_cagri_sayilmaz(self):
        uzun = "Kat malikleri kurulunun aldığı her kararı toplantı tutanağına kaydetmek ve defter tutmak zorunludur."
        self.assertGreater(len(uzun), 90)
        # Kapanış çağrısı süzgeci yalnız captionlarda çalışır; orada da kısa satırları eler
        self.assertIn(uzun, cd.icerik_satirlari({"caption_instagram": uzun + "\nedmyapigayrimenkul.com"}))

    def test_yorum_alani_istemde_isaretlenir(self):
        hakem = _Hakem(_cevap())
        cd.denetle({**VERI, "sana_etkisi": "Faiz beklentileri kredi maliyetlerinizi etkileyebilir."}, KAYNAK, cagri=hakem)
        self.assertIn("(yorum) Faiz beklentileri", hakem.istemler[0][0])
        self.assertNotIn("(yorum) Kat malikleri kurulunda", hakem.istemler[0][0])

    def test_yorum_satirinda_desteksiz_bulgu_atilir_celiski_kalir(self):
        veri = {**VERI, "sana_etkisi": "Gelmeyen malik kararla bağlı kalmaz ve itiraz süresi işlemez."}
        desteksiz = {"tur": "desteksiz", "icerik_alintisi": "Gelmeyen malik kararla bağlı kalmaz",
                     "kaynak_alintisi": "", "aciklama": "Kaynakta yok."}
        self.assertEqual(cd.denetle(veri, KAYNAK, cagri=_Hakem(_cevap(desteksiz))), [])
        cd._ONBELLEK.clear()
        celiski = {**desteksiz, "tur": "celiski", "kaynak_alintisi": "Toplantıya katılmayan kat malikine karar noter aracılığıyla bildirilir"}
        self.assertEqual(len(cd.denetle(veri, KAYNAK, cagri=_Hakem(_cevap(celiski)))), 1)

    def test_dusuk_ciddiyetli_bulgu_atilir_eksik_ciddiyet_yuksek_sayilir(self):
        dusuk = {**GERCEK, "ciddiyet": "dusuk"}
        self.assertEqual(cd.denetle(VERI, KAYNAK, cagri=_Hakem(_cevap(dusuk))), [])
        cd._ONBELLEK.clear()
        self.assertEqual(len(cd.denetle(VERI, KAYNAK, cagri=_Hakem(_cevap({**GERCEK, "ciddiyet": "yuksek"})))), 1)
        cd._ONBELLEK.clear()
        self.assertEqual(len(cd.denetle(VERI, KAYNAK, cagri=_Hakem(_cevap(GERCEK)))), 1)  # alan yoksa

    def test_uzun_metin_kelime_ortasinda_kesilmez(self):
        kesik = cd._kes("Kadastrosu tamamlanan çalışma alanı içerisinde kalan eski tapu kayıtları", 40)
        self.assertTrue(kesik.endswith("…"))
        self.assertNotIn("kayıt", kesik)  # tam kelimeye gelmeyen parça düşer
        self.assertEqual(cd._kes("kısa", 40), "kısa")

    def test_zincirde_lite_model_yok(self):
        self.assertFalse(any("lite" in m for m in cd.DENETCI_MODELLER))


class TestDenetle(unittest.TestCase):
    def setUp(self):
        cd._ONBELLEK.clear()

    def test_gercek_bulgu_uyari_olur_iki_alinti_ile(self):
        hakem = _Hakem(_cevap(GERCEK))
        u = cd.denetle(VERI, KAYNAK, cagri=hakem)
        self.assertEqual(len(u), 1)
        self.assertTrue(u[0].startswith("⚠️ ANLAM KAYMASI"))
        self.assertIn("ayrı hükümler birleştirilmiş", u[0])
        self.assertIn("kaynakta:", u[0])
        self.assertFalse(dogrula.kritik_var(u))  # hakem ⛔ üretmez

    def test_istem_kaynagi_ve_numarali_satirlari_tasir(self):
        hakem = _Hakem(_cevap())
        cd.denetle(VERI, KAYNAK, cagri=hakem)
        istem = hakem.istemler[0][0]
        self.assertIn("salt çoğunluğudur", istem)
        self.assertIn("[1] Kat malikleri kurulunda karar nasıl alınır?", istem)
        self.assertIn("kip", istem)

    def test_icerikte_olmayan_alinti_atilir(self):
        uydurma = {**GERCEK, "icerik_alintisi": "Karar her zaman oybirliğiyle alınır ve noterde onaylanır"}
        self.assertEqual(cd.denetle(VERI, KAYNAK, cagri=_Hakem(_cevap(uydurma))), [])

    def test_kaynakta_olmayan_alinti_atilir(self):
        uydurma = {**GERCEK, "kaynak_alintisi": "Karar için kat maliklerinin dörtte üçünün oyu şarttır ve bu zorunludur"}
        self.assertEqual(cd.denetle(VERI, KAYNAK, cagri=_Hakem(_cevap(uydurma))), [])

    def test_desteksizde_kaynak_alintisi_istenmez(self):
        d = {"tur": "desteksiz", "satir": 4, "icerik_alintisi": "Gelmeyen malike karar noter aracılığıyla bildirilir",
             "kaynak_alintisi": "", "aciklama": "Bu bildirim yöntemi kaynakta yok."}
        u = cd.denetle(VERI, KAYNAK.replace("noter aracılığıyla", "yazılı olarak"), cagri=_Hakem(_cevap(d)))
        self.assertEqual(len(u), 1)
        self.assertNotIn("kaynakta:", u[0])

    def test_kanun_dipnotu_alinti_eslesmesini_bozmaz(self):
        kaynak = KAYNAK.replace("oy çokluğuyla karar verir. [4] İkinci", "oy çokluğuyla karar verir. İkinci").replace(
            "salt çoğunluğudur.", "salt [4] çoğunluğudur.")
        self.assertEqual(len(cd.denetle(VERI, kaynak, cagri=_Hakem(_cevap(GERCEK)))), 1)

    def test_bilinmeyen_tur_ve_bozuk_bulgu_atilir(self):
        bulgular = [{**GERCEK, "tur": "ustunluk"}, "metin", {**GERCEK, "aciklama": ""}, None]
        self.assertEqual(cd.denetle(VERI, KAYNAK, cagri=_Hakem(_cevap(*bulgular))), [])

    def test_en_cok_uc_bulgu(self):
        alintilar = ["Kat malikleri kurulunda karar nasıl alınır", "Gelmeyen malike karar noter aracılığıyla bildirilir",
                     "yarısından fazlası toplanmalıdır", "İlk toplantıda da ikinci toplantıda da katılanların"]
        bulgular = [{**GERCEK, "icerik_alintisi": a, "kaynak_alintisi": "oy çokluğuyla karar verir"} for a in alintilar]
        self.assertEqual(len(cd.denetle(VERI, KAYNAK, cagri=_Hakem(_cevap(*bulgular)))), cd.AZAMI_BULGU)

    def test_ayni_cumle_birden_cok_turle_isaretlenirse_tek_uyari(self):
        ayni = [{**GERCEK, "tur": t} for t in ("celiski", "kip", "ozne", "birlestirme")]
        self.assertEqual(len(cd.denetle(VERI, KAYNAK, cagri=_Hakem(_cevap(*ayni)))), 1)

    def test_html_kacirilir(self):
        d = {**GERCEK, "aciklama": "Fark <b>büyük</b> & önemli."}
        u = cd.denetle(VERI, KAYNAK, cagri=_Hakem(_cevap(d)))
        self.assertIn("&lt;b&gt;", u[0])
        self.assertNotIn("<b>", u[0])


class TestDayaniklilik(unittest.TestCase):
    def setUp(self):
        cd._ONBELLEK.clear()

    def test_kisa_kaynakta_model_hic_sorulmaz(self):
        hakem = _Hakem(_cevap(GERCEK))
        self.assertEqual(cd.denetle(VERI, "Kısa kaynak.", cagri=hakem), [])
        self.assertEqual(cd.denetle(VERI, "", cagri=hakem), [])
        self.assertEqual(hakem.sayi, 0)

    def test_icerik_bossa_model_sorulmaz(self):
        hakem = _Hakem(_cevap(GERCEK))
        self.assertEqual(cd.denetle({"bicim": "B1"}, KAYNAK, cagri=hakem), [])
        self.assertEqual(hakem.sayi, 0)

    def test_hakem_hata_verirse_fail_open(self):
        for yanit in (RuntimeError("kota"), None, "", "bu json degil", "[]", "42"):
            with self.subTest(yanit=yanit):
                cd._ONBELLEK.clear()
                self.assertEqual(cd.denetle(VERI, KAYNAK, cagri=_Hakem(yanit)), [])

    def test_hata_onbellege_yazilmaz_sonra_tekrar_denenir(self):
        self.assertEqual(cd.denetle(VERI, KAYNAK, cagri=_Hakem(None)), [])
        self.assertEqual(len(cd.denetle(VERI, KAYNAK, cagri=_Hakem(_cevap(GERCEK)))), 1)

    def test_ayni_girdi_modele_bir_kez_sorulur(self):
        hakem = _Hakem(_cevap(GERCEK))
        a = cd.denetle(VERI, KAYNAK, cagri=hakem)
        b = cd.denetle(VERI, KAYNAK, cagri=hakem)
        self.assertEqual(a, b)
        self.assertEqual(hakem.sayi, 1)

    def test_test_modunda_cagri_verilmezse_ag_yok(self):
        # Hata yutulduğu için istisna fırlatmak yetmez: çağrının HİÇ yapılmadığı sayılır
        with patch("src.generate_text._gemini_cagri") as ag:
            self.assertEqual(cd.denetle(VERI, KAYNAK), [])
        ag.assert_not_called()


class TestUcNoktaToleransi(unittest.TestCase):
    """Model uzun kaynak cümlesini "..." ile kısaltıyor; parçalar sırayla aranır (2026-10-08, S2-006)."""

    KAYNAK_N = cd._normal(KAYNAK)

    def test_parcalar_sirayla_bulunursa_kabul(self):
        self.assertTrue(cd._bulunur("İkinci toplantıda karar yeter sayısı... salt çoğunluğudur", self.KAYNAK_N))
        # "…" kelime atladığında bölünmezse parçalar birleşik aranır ve bulunamaz
        self.assertTrue(cd._bulunur("İkinci toplantıda karar yeter sayısı … salt çoğunluğudur", self.KAYNAK_N))

    def test_sira_bozuksa_reddedilir(self):
        self.assertFalse(cd._bulunur("salt çoğunluğudur... İkinci toplantıda karar yeter sayısı", self.KAYNAK_N))

    def test_bir_parca_metinde_yoksa_reddedilir(self):
        self.assertFalse(cd._bulunur("İkinci toplantıda karar yeter sayısı... oybirliği gerekir", self.KAYNAK_N))

    def test_hepsi_kisa_parcalarsa_kanit_sayilmaz(self):
        # Üç parça da metinde SIRAYLA geçiyor ama hiçbiri 12 karakter değil: tek başına kanıt değil
        self.assertFalse(cd._bulunur("karar... kat... salt", self.KAYNAK_N))

    def test_ucnoktasiz_alinti_eskisi_gibi(self):
        self.assertTrue(cd._bulunur("İkinci toplantıda karar yeter sayısı, katılanların salt çoğunluğudur", self.KAYNAK_N))
        self.assertFalse(cd._bulunur("", self.KAYNAK_N))

    def test_kisaltilmis_kaynak_alintili_bulgu_kabul_edilir(self):
        bulgu = {**GERCEK, "kaynak_alintisi": "İkinci toplantıda karar yeter sayısı... salt çoğunluğudur"}
        self.assertEqual(len(cd.denetle(VERI, KAYNAK, cagri=_Hakem(_cevap(bulgu)))), 1)


class TestAyrintiliSonuc(unittest.TestCase):
    """`denetle_ayrintili`: "bulgu yok" ile "hakem çalışmadı" ayrılır; otomatik yayın buna dayanır."""

    def setUp(self):
        cd._ONBELLEK.clear()

    def test_temiz_yanit_hakem_calisti_demek(self):
        self.assertEqual(cd.denetle_ayrintili(VERI, KAYNAK, cagri=_Hakem(_cevap())), ([], True))

    def test_bulgu_varsa_calisti_ve_uyari(self):
        uyarilar, calisti = cd.denetle_ayrintili(VERI, KAYNAK, cagri=_Hakem(_cevap(GERCEK)))
        self.assertTrue(calisti)
        self.assertEqual(len(uyarilar), 1)

    def test_calismadigi_durumlar_false(self):
        for ad, yanit in (("None", None), ("bos", ""), ("bozuk", "json degil"), ("istisna", RuntimeError("kota"))):
            with self.subTest(durum=ad):
                cd._ONBELLEK.clear()
                self.assertEqual(cd.denetle_ayrintili(VERI, KAYNAK, cagri=_Hakem(yanit)), ([], False))

    def test_kaynak_yoksa_ya_da_kisaysa_false(self):
        hakem = _Hakem(_cevap())
        self.assertEqual(cd.denetle_ayrintili(VERI, "", cagri=hakem), ([], False))
        self.assertEqual(cd.denetle_ayrintili(VERI, "kısa", cagri=hakem), ([], False))
        self.assertEqual(hakem.sayi, 0)

    def test_test_modunda_cagri_yoksa_false(self):
        self.assertEqual(cd.denetle_ayrintili(VERI, KAYNAK), ([], False))

    def test_onbellekten_gelen_sonuc_da_calisti_sayilir(self):
        hakem = _Hakem(_cevap(GERCEK))
        ilk = cd.denetle_ayrintili(VERI, KAYNAK, cagri=hakem)
        ikinci = cd.denetle_ayrintili(VERI, KAYNAK, cagri=hakem)
        self.assertEqual(ilk, ikinci)
        self.assertEqual(hakem.sayi, 1)

    def test_denetle_eski_arayuzu_korur(self):
        self.assertEqual(cd.denetle(VERI, KAYNAK, cagri=_Hakem(None)), [])
        self.assertEqual(len(cd.denetle(VERI, KAYNAK, cagri=_Hakem(_cevap(GERCEK)))), 1)


class TestKapiBaglantisi(unittest.TestCase):
    def setUp(self):
        cd._ONBELLEK.clear()
        self.brief = {"mevzuat": "KMK md. 30", "mevzuat_metni": KAYNAK}
        self.veri = {**VERI, "_brief": self.brief}

    def test_uyari_kapidan_gecer_ve_yayini_kilitlemez(self):
        with patch.object(cd, "denetle", return_value=["⚠️ ANLAM KAYMASI (x): y"]) as m:
            u = dogrula.icerigi_denetle(self.veri, None)
        self.assertIn("⚠️ ANLAM KAYMASI (x): y", u)
        self.assertFalse(dogrula.kritik_var(u))
        self.assertEqual(m.call_args[0][1], KAYNAK)  # kaynak olarak brief'in madde metni verildi

    def test_kritik_varken_hakem_cagrilmaz(self):
        veri = {**self.veri, "spot": "Kat Mülkiyeti Kanunu madde 99 uyarınca karar verilir."}
        with patch.object(cd, "denetle", return_value=["⚠️ x"]) as m:
            u = dogrula.icerigi_denetle(veri, None)
        self.assertTrue(dogrula.kritik_var(u), u)  # uydurma madde numarası ⛔
        m.assert_not_called()

    def test_anlam_kapaliyken_hakem_cagrilmaz(self):
        with patch.object(cd, "denetle", return_value=["⚠️ x"]) as m:
            u = dogrula.icerigi_denetle(self.veri, None, anlam=False)
        m.assert_not_called()
        self.assertNotIn("⚠️ x", u)

    def test_hakem_patlarsa_kapi_calismaya_devam_eder(self):
        with patch.object(cd, "denetle", side_effect=RuntimeError("boom")):
            u = dogrula.icerigi_denetle(self.veri, None)
        self.assertIsInstance(u, list)

    def test_kaynaksiz_icerikte_hakem_bos_kaynakla_cagrilir_ve_atlar(self):
        veri = {k: v for k, v in VERI.items() if k != "_brief"}
        hakem = _Hakem(_cevap(GERCEK))
        with patch.object(cd, "_varsayilan_cagri", return_value=hakem):
            u = dogrula.icerigi_denetle(veri, None)
        self.assertEqual(hakem.sayi, 0)
        self.assertFalse(any("ANLAM KAYMASI" in x for x in u))


if __name__ == "__main__":
    unittest.main()
