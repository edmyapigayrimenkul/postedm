"""
tests/test_haber_semasi.py — Haber içerik şeması Instabot'la aynıdır (2026-10-07 kararı).

Model artık `detay_yazisi` (4-5 paragraf), `vurgu_sayi`, `alinti`, `neden_onemli`, `sana_etkisi`,
`sirada_ne_var`, `ulke_kodu` üretir; başlık ve özet anahtarları (`manset`, `spot`) korunur.
Eski B5 kayıtları (`detay_maddeleri`, `uzman_notu`) okunmaya devam eder.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import json
import unittest
from unittest.mock import patch

from src import dogrula, generate_text, haber_alanlari, linkedin, video
from src.make_image import TasmaHatasi

KAYNAK = ("MUFG raporunda yıllık enflasyonun eylülde ağustostaki yüzde 31,5 seviyesinden yüzde 29,7'ye gerilediği "
          "belirtildi. Aylık enflasyon yüzde 1,8 oldu. Reel politika faizi yüzde 7,3'e yükseldi. TCMB 22 Ekim'de "
          "toplanacak. Swap oranları yaklaşık 120 baz puanlık indirimi fiyatlıyor. MUFG analisti \"faiz indirimi "
          "için alan açıldı\" dedi.")

YENI = {
    "bicim": "B5", "format_turu": "dailybrief",
    "manset": "Enflasyon %29,7'ye geriledi, reel faiz %7,3'e yükseldi",
    "spot": "**MUFG**, TCMB'nin **22 Ekim** toplantısında faiz indirimine başlamasını bekliyor.",
    "kanca": "120 BAZ PUAN",
    "detay_yazisi": ("Yıllık enflasyon eylülde **%29,7**'ye geriledi.\n\n"
                     "Aylık enflasyon **%1,8** oldu; reel politika faizi **%7,3**'e yükseldi.\n\n"
                     "Swap oranları yaklaşık 120 baz puanlık indirimi fiyatlıyor."),
    "vurgu_sayi": "%1,8", "vurgu_etiket": "aylık enflasyon",
    "alinti": "faiz indirimi için alan açıldı", "alinti_sahibi": "MUFG analisti",
    "neden_onemli": "Reel faizin yükselmesi indirim için zemin hazırlıyor.",
    "sana_etkisi": "Kredi faizlerinde indirim beklentisi güçleniyor.",
    "sirada_ne_var": "TCMB 22 Ekim'de toplanacak.",
    "ulke_kodu": "tr", "ulke_adi": "Türkiye",
    "caption_instagram": "Enflasyon geriledi.", "caption_threads": "Enflasyon geriledi.",
}


class TestOkuyucu(unittest.TestCase):
    def test_paragraflar_iki_semadan(self):
        self.assertEqual(len(haber_alanlari.detay_paragraflari(YENI)), 3)
        eski = {"detay_maddeleri": [{"etiket": "A", "metin": "Bir."}, {"etiket": "B", "metin": "İki."}]}
        self.assertEqual(haber_alanlari.detay_paragraflari(eski), ["Bir.", "İki."])

    def test_kalin_isareti_duz_metinde_yok(self):
        for p in haber_alanlari.detay_paragraflari(YENI, kalin=False):
            self.assertNotIn("**", p)
        self.assertIn("**", haber_alanlari.detay_paragraflari(YENI)[0])
        self.assertNotIn("**", haber_alanlari.duz_metin(YENI))

    def test_sana_etkisi_eski_uzman_notuna_duser(self):
        self.assertEqual(haber_alanlari.sana_etkisi({"uzman_notu": "Eski not."}), "Eski not.")
        self.assertEqual(haber_alanlari.sana_etkisi(YENI), YENI["sana_etkisi"])

    def test_vurgu_ve_alinti(self):
        self.assertEqual(haber_alanlari.vurgu(YENI), ("%1,8", "aylık enflasyon"))
        self.assertEqual(haber_alanlari.vurgu({"vurgu_etiket": "yalnız etiket"}), ("", ""))
        self.assertEqual(haber_alanlari.alinti({"alinti": "“söz”", "alinti_sahibi": "X"}), ("söz", "X"))


class TestUretimTemizligi(unittest.TestCase):
    def test_kalin_yalniz_detay_ve_spotta_korunur(self):
        ham = {"manset": "Başlık **kalın**", "spot": "Özet **kalın** burada", "detay_yazisi": "Metin **kalın**.\n\nİkinci.",
               "caption_instagram": "Caption **kalın**"}
        t = generate_text._temizle(ham, haber_alanlari.KALIN_ALANLAR)
        self.assertEqual(t["manset"], "Başlık kalın")
        self.assertEqual(t["caption_instagram"], "Caption kalın")
        self.assertIn("**kalın**", t["spot"])
        self.assertIn("**kalın**", t["detay_yazisi"])
        self.assertIn("\n\n", t["detay_yazisi"])      # paragraf ayracı korunur

    def test_eslesmeyen_yildiz_atilir_ve_unlem_kalkar(self):
        t = generate_text._temizle({"spot": "Açık **vurgu kapanmıyor!"}, ("spot",))
        self.assertNotIn("**", t["spot"])
        self.assertNotIn("!", t["spot"])

    def test_diger_bicimlerde_eskisi_gibi(self):
        self.assertEqual(generate_text._temizle({"spot": "x **y**"})["spot"], "x y")

    def test_detay_kelime_butcesi(self):
        uzun = {"bicim": "B5", "detay_yazisi": " ".join(["kelime"] * 260)}
        self.assertTrue(any("detay_yazisi" in i for i in generate_text.butce_ihlalleri(uzun)))
        self.assertEqual(generate_text.butce_ihlalleri({"bicim": "B5", "detay_yazisi": " ".join(["kelime"] * 200)}), [])

    def test_prompt_instabot_alanlarini_ister_sabit_aci_ve_rakam_yok(self):
        sema = generate_text._SEMA_B5
        for alan in ("detay_yazisi", "vurgu_sayi", "vurgu_etiket", "alinti", "neden_onemli", "sana_etkisi",
                     "sirada_ne_var", "ulke_kodu", "kanca"):
            self.assertIn(f'"{alan}"', sema)
        for yasak in ("uzman_notu", "detay_maddeleri", "Silivri, Çatalca", "KDV muafiyeti"):
            self.assertNotIn(yasak, sema)
        # Promptta örnek oran/süre yok: model kopyalıyor (MEMORY §8.3)
        import re
        self.assertIsNone(re.search(r"%\d|\d+,\d|\d+\.\d{3}|\d+ milyar", sema + generate_text.HABER_KURALLARI))


class TestSadelestirme(unittest.TestCase):
    def _s(self, **ek):
        v = {**YENI, **ek}
        return dogrula.haber_alanlarini_sadelestir(v, KAYNAK)

    def test_gecerli_icerik_dokunulmaz(self):
        v = self._s()
        self.assertEqual((v["alinti"], v["vurgu_sayi"]), ("faiz indirimi için alan açıldı", "%1,8"))

    def test_uydurma_alinti_atilir_icerik_durmaz(self):
        v = self._s(alinti="Bu tamamen uydurulmuş bir söz ve kaynakta hiç geçmiyor", alinti_sahibi="Bakan")
        self.assertEqual((v["alinti"], v["alinti_sahibi"]), ("", ""))
        self.assertEqual(dogrula.denetle(v, dogrula.haberden_brief({"orijinal_baslik": "x", "makale_metni": KAYNAK, "kaynak": "S"})), [])

    def test_kaynakta_olmayan_vurgu_sayisi_atilir(self):
        v = self._s(vurgu_sayi="%47", vurgu_etiket="mevduat faizi")
        self.assertEqual((v["vurgu_sayi"], v["vurgu_etiket"]), ("", ""))

    def test_basliktaki_ya_da_kancadaki_sayi_vurgu_olmaz(self):
        self.assertEqual(self._s(vurgu_sayi="%29,7", vurgu_etiket="yıllık enflasyon")["vurgu_sayi"], "")
        self.assertEqual(self._s(vurgu_sayi="120 baz puan", vurgu_etiket="swap")["vurgu_sayi"], "")   # kancada var

    def test_zayif_vurgu_atilir(self):
        self.assertEqual(self._s(vurgu_sayi="3", vurgu_etiket="madde")["vurgu_sayi"], "")

    def test_cok_uzun_vurgu_atilir_etiket_kisalir(self):
        self.assertEqual(self._s(vurgu_sayi="%1.250.000.000.000,50 milyar")["vurgu_sayi"], "")
        v = self._s(vurgu_etiket="aylık enflasyon oranı ve onun bütün alt kalemleri ile ilgili çok uzun açıklama")
        self.assertLessEqual(len(v["vurgu_etiket"]), 44)

    def test_baslik_sonundaki_nokta_kalkar(self):
        self.assertEqual(self._s(manset="Başlık nokta ile bitiyor.")["manset"], "Başlık nokta ile bitiyor")

    def test_bos_ovgu_elenir(self):
        v = self._s(sana_etkisi="Bu tarihi başarı tüm Türkiye'de büyük bir gurur ve coşku yaratıyor.")
        self.assertEqual(v["sana_etkisi"], "")

    def test_ince_kaynakta_dolgu_kesilir(self):
        ince = "Plan askıya çıktı. Askı süresi otuz gündür."
        v = dogrula.haber_alanlarini_sadelestir(
            {**YENI, "detay_yazisi": "Bir.\n\nİki.\n\nÜç dolgu.\n\nDört dolgu."}, ince)
        self.assertEqual(len(haber_alanlari.detay_paragraflari(v)), 2)
        self.assertEqual((v["neden_onemli"], v["sana_etkisi"]), ("", ""))
        # Kaynak uzunluğu bilinmiyorsa ("") dokunulmaz
        v2 = dogrula.haber_alanlarini_sadelestir({**YENI}, "")
        self.assertEqual(len(haber_alanlari.detay_paragraflari(v2)), 3)

    def test_ulke_kodu_gecersizse_ad_da_gider(self):
        v = self._s(ulke_kodu="Türkiye!!", ulke_adi="Türkiye")
        self.assertEqual((v["ulke_kodu"], v["ulke_adi"]), ("", ""))

    def test_genel_kelimelerden_olusan_kanca_bos_sayilir(self):
        self.assertTrue(dogrula.kanca_ici_bos_mu("GEREKLİ BELGE VE KRİTERLER"))
        self.assertFalse(dogrula.kanca_ici_bos_mu("TOKİ BAŞVURU ŞARTLARI"))     # özel ad var
        self.assertFalse(dogrula.kanca_ici_bos_mu("13 FİRMA TEKLİF VERDİ"))


class TestDenetim(unittest.TestCase):
    def _brief(self):
        return dogrula._birlesik_brief(YENI, {"orijinal_baslik": "x", "kaynak": "Ekonomim", "makale_metni": KAYNAK})

    def test_yeni_semada_temiz_icerik_temiz(self):
        self.assertEqual(dogrula.denetle(YENI, self._brief()), [])

    def test_detay_yazisindaki_uydurma_sayi_kritik(self):
        v = {**YENI, "detay_yazisi": YENI["detay_yazisi"] + "\n\nSwap oranları 250 baz puan fiyatlıyor."}
        self.assertTrue(dogrula.kritik_var(dogrula.denetle(v, self._brief())))

    def test_vurgu_sayisindaki_uydurma_sayi_kritik(self):
        v = {**YENI, "vurgu_sayi": "%88"}
        self.assertTrue(dogrula.kritik_var(dogrula.denetle(v, self._brief())))

    def test_yeni_alanlardaki_uydurma_yerel_bag_kritik(self):
        v = {**YENI, "sana_etkisi": "Silivri'deki arsa fiyatları da bu karardan etkilenecek."}
        self.assertTrue(dogrula.kritik_var(dogrula.denetle(v, self._brief())))

    def test_kaynakta_suclama_varsa_ihtiyat_dili_istenir(self):
        kaynak = "Şüpheli hakkında soruşturma başlatıldı. Sahte tapu düzenlediği iddia ediliyor."
        v = {"manset": "Sahte tapu çetesi çökertildi", "spot": "Çete lideri sahte tapu üretti.",
             "detay_yazisi": "Çete sahte tapu üretti."}
        self.assertTrue(dogrula.suclama_dili_denetle(v, kaynak))
        v["spot"] = "Çete lideri hakkında soruşturma başlatıldı."
        self.assertEqual(dogrula.suclama_dili_denetle(v, kaynak), [])
        self.assertEqual(dogrula.suclama_dili_denetle(v, "Sıradan bir gayrimenkul haberi."), [])


class TestTuketiciler(unittest.TestCase):
    def test_linkedin_paragraflari_ve_etkiyi_yazar(self):
        m = linkedin.linkedin_metni_hazirla(dict(YENI))
        self.assertIn("Aylık enflasyon %1,8 oldu", m)
        self.assertNotIn("**", m)
        self.assertIn(YENI["sana_etkisi"], m)
        self.assertNotIn("UZMAN DEĞERLENDİRMESİ", m)

    def test_linkedin_eski_sema_hala_calisir(self):
        eski = {"manset": "Başlık", "spot": "Özet", "detay_maddeleri": [{"etiket": "A", "metin": "Madde metni."}],
                "uzman_notu": "Not."}
        m = linkedin.linkedin_metni_hazirla(eski)
        self.assertIn("Madde metni.", m)
        self.assertIn("Not.", m)

    def test_video_suresi_yeni_alanlari_sayar(self):
        self.assertGreater(video._detay_kelime_sayisi(dict(YENI)), 30)
        self.assertEqual(video._detay_kelime_sayisi({"manset": "Yalnız kapak", "spot": "Kapak"}), 0)


class TestSayfaKapisi(unittest.TestCase):
    def test_sayfaya_sigmayan_detay_uretimi_durdurur(self):
        from src import haber_tasarim as ht
        cumle = "Bu paragraf yeterince uzun bir bilgi taşıyor ve her cümle sayfada gerçekten yer kaplıyor. " * 3
        with self.assertRaises(TasmaHatasi):
            ht.detay_sayfalara_bol("\n\n".join([cumle] * 14), ht.AYARLAR)

    def test_makul_detay_sigar_ve_kayip_yok(self):
        from src import haber_tasarim as ht
        sayfalar = ht.detay_sayfalara_bol("\n\n".join(haber_alanlari.detay_paragraflari(YENI)), ht.AYARLAR,
                                         vurgu=("%1,8", "aylık enflasyon"), alinti=("söz söz söz", "MUFG"),
                                         sana_etkisi=YENI["sana_etkisi"])
        self.assertEqual(sum(len(s) for s in sayfalar), 3 + 3)   # vurgu + 3 paragraf + etki + alıntı


if __name__ == "__main__":
    unittest.main()
