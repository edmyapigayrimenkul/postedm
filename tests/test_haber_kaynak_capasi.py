"""
tests/test_haber_kaynak_capasi.py — Haber içeriği yalnızca kaynak metinden yazılır (2026-10-07).

Yayınlanan dört haberin (#365, #452, #470, #509) dördünde de ikinci madde
uydurma bir Silivri/Trakya cümlesiydi; #509'da kaynaktaki altı rakamın hiçbiri
içeriğe girmedi, #452'de "5 yıl şartı kaldırıldı" yazıldı. Sebep: modele
yalnızca triyaj alıntısı gidiyor, şema her habere dört sabit açı dayatıyordu,
denetim haberde rakamı ve yerel bağı yalnızca ⚠️ sayıyordu.
Ayrıca aynı denetimde bulunan rozet ve dizgi kusurları burada.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import json
import unittest
from unittest.mock import patch

from src import dogrula, fetch_article, generate_text, hook_motoru, konu_bankasi, mevzuat
from src.yeni_formatlar import kategori_temizle, rozet_okunur_mu

KAYNAK = {
    "orijinal_baslik": "MUFG: TCMB'nin faiz indirimi için alanı açıldı",
    "kaynak": "Ekonomim",
    "orijinal_url": "https://www.ekonomim.com/ornek",
    "makale_metni": (
        "MUFG raporunda yıllık enflasyonun eylülde ağustostaki yüzde 31,5 seviyesinden "
        "yüzde 29,7'ye gerilediği belirtildi. Reel politika faizi yüzde 7,3'e yükseldi. "
        "TCMB 22 Ekim'de toplanacak. Swap oranları yaklaşık 120 baz puanlık indirimi fiyatlıyor."
    ),
}

TEMIZ = {
    "bicim": "B5", "format_turu": "dailybrief",
    "kanca": "SWAP PİYASASI // 120 BAZ PUAN",
    "manset": "Enflasyon %29,7'ye indi, MUFG faiz indirimi bekliyor",
    "spot": "Reel politika faizi %7,3'e yükseldi. TCMB 22 Ekim'de toplanacak.",
    "detay_maddeleri": [{"etiket": "ENFLASYON VERİSİ", "metin": "Yıllık enflasyon %31,5'ten %29,7'ye geriledi.",
                         "renk": "kirmizi"}],
    "caption_instagram": "Enflasyon %29,7'ye indi.\n\nedmyapigayrimenkul.com · 0212 727 29 55\n\n#Silivri #TCMB",
}


def _denetle(veri):
    return dogrula.denetle(veri, dogrula._birlesik_brief(veri, KAYNAK))


class TestHaberDenetimi(unittest.TestCase):
    def test_kaynaga_sadik_haber_temiz(self):
        # Sistemin eklediği telefon ve #Silivri etiketi uydurma sayılmaz
        self.assertEqual(_denetle(TEMIZ), [])

    def test_kaynakta_olmayan_sayi_kritik(self):
        # Eskiden haberde veri_kaynagi hep dolu olduğu için yalnızca ⚠️ idi
        veri = dict(TEMIZ, spot="Faiz indiriminin 150 baz puan olacağı belirtildi.")
        u = _denetle(veri)
        self.assertTrue(any(x.startswith("⛔ SAYI KAYNAKTA YOK") and "150" in x for x in u), u)

    def test_yuvarlanmis_sayi_kritik(self):
        veri = dict(TEMIZ, spot="Enflasyon yaklaşık %30'a indi.")
        self.assertTrue(dogrula.kritik_var(_denetle(veri)))

    def test_uydurma_yerel_bag_kritik(self):
        # #509'un yayına çıkan cümlesi
        veri = dict(TEMIZ, detay_maddeleri=[{"etiket": "BÖLGESEL ETKİ", "metin": (
            "Faiz indirimi öngörüleri, Silivri ve Trakya genelindeki arsa ve konut piyasasında "
            "uzun vadeli yatırım iştahını dolaylı olarak destekliyor.")}])
        u = _denetle(veri)
        self.assertTrue(any(x.startswith("⛔ YEREL BAĞ KAYNAKTA YOK") for x in u), u)

    def test_kaynakta_gecen_yerel_ad_serbest(self):
        kaynak = dict(KAYNAK, makale_metni=KAYNAK["makale_metni"] + " Silivri'de yeni imar planı askıya çıktı.")
        veri = dict(TEMIZ, spot="Silivri'de yeni imar planı askıya çıktı.")
        u = dogrula.denetle(veri, dogrula._birlesik_brief(veri, kaynak))
        self.assertFalse(dogrula.kritik_var(u), u)

    def test_kaynakta_olmayan_ad_uyarir(self):
        veri = dict(TEMIZ, spot="Açıklamayı Hazine ve Maliye Bakanı Ahmet Yılmazer yaptı.")
        u = _denetle(veri)
        self.assertTrue(any("AD KAYNAKTA YOK" in x and "Yılmazer" in x for x in u), u)

    def test_eski_numarali_etiket_sayi_sayilmaz(self):
        veri = dict(TEMIZ, detay_maddeleri=[{"etiket": "01 // ENFLASYON", "metin": "Enflasyon %29,7'ye geriledi."}])
        self.assertEqual(_denetle(veri), [])

    def test_takvim_yili_sure_sayilmaz(self):
        # #452 yeniden üretiminde "2018 yılında" ⛔ SÜRE KAYNAKTA YOK veriyordu
        self.assertEqual(mevzuat.sure_ifadeleri("2018 yılında yenilenen sözleşme"), set())
        self.assertIn(("5", "yıl"), mevzuat.sure_ifadeleri("5 yıl geçmeden dava açılabilir"))

    def test_ici_bos_kanca(self):
        self.assertTrue(dogrula.kanca_ici_bos_mu("JAPON FİNANS GRUBU // RAPOR YAYINLANDI"))
        self.assertTrue(dogrula.kanca_ici_bos_mu("TAPUDA YENİ DÖNEM"))
        self.assertFalse(dogrula.kanca_ici_bos_mu("120 BAZ PUAN // SWAP PİYASASI"))
        self.assertFalse(dogrula.kanca_ici_bos_mu("14 MECLİS ÜYESİ DE AYRILDI"))
        self.assertFalse(dogrula.kanca_ici_bos_mu(""))

    def test_ici_bos_kanca_kapaga_cizilmez(self):
        haber = dict(TEMIZ, kanca="JAPON FİNANS GRUBU // RAPOR YAYINLANDI", detay_maddeleri=[])
        sonuc = hook_motoru.hook_olustur(haber)
        self.assertFalse(sonuc and "RAPOR YAYINLANDI" in f"{sonuc.get('t1')} {sonuc.get('t2')}", sonuc)


class TestHaberUretimi(unittest.TestCase):
    def test_sema_sabit_aci_ve_ornek_rakam_tasimaz(self):
        sema = generate_text._SEMA_B5
        for yasak in ("Silivri, Çatalca", "KDV muafiyeti", "BÖLGESEL PİYASAYA", "Milli Emlak"):
            self.assertNotIn(yasak, sema)
        # Promptta örnek oran yazılmaz (MEMORY §8.3): model kopyalıyor
        self.assertNotRegex(sema + generate_text.HABER_KURALLARI, r"\d+,\d")

    def test_haber_ortak_kurallarla_degil_kendi_kurallariyla_uretilir(self):
        cagrilar = []

        def sahte(girdi, sistem, sicaklik=0.7, **k):
            cagrilar.append(sistem)
            return json.dumps({"bicim": "B5", "manset": "Enflasyon %29,7'ye indi"})

        with patch.object(generate_text, "_gemini_cagri", side_effect=sahte):
            generate_text._uret("KAYNAK", "B5")
            generate_text._uret("KONU", "B1")
        self.assertIn("YALNIZCA KAYNAK", cagrilar[0])
        self.assertNotIn("MANŞET YAPISI (üç parça)", cagrilar[0])
        self.assertIn("MANŞET YAPISI (üç parça)", cagrilar[1])

    def test_brief_tam_metni_tasir(self):
        brief = {"kod": "HABER-1", "sutun": "S4", "bicim": "B5", "baslik": "x", "aci": "y",
                 "kanca_kalip": "rakam", "mevzuat": None, "yerel": None,
                 "_dayanak": "kısa alıntı", "_makale": KAYNAK["makale_metni"]}
        metin = konu_bankasi.brief_metni(brief)
        self.assertIn("120 baz puan", metin)
        self.assertIn("KAYNAK HABERİN TAM METNİ", metin)
        self.assertNotIn("Kanun maddesi numarası YAZMA", metin)

    def test_haber_mansetine_75_karakter(self):
        veri = {"bicim": "B5", "manset": "x" * 70}
        self.assertEqual(generate_text.butce_ihlalleri(veri), [])
        self.assertTrue(generate_text.butce_ihlalleri({"bicim": "B5", "manset": "x" * 80}))

    def test_cerez_kuyrugu_kesilir(self):
        govde = ("Enflasyon eylülde geriledi. " * 20) + (
            "Bu site deneyimlerinizi kişiselleştirmek amacıyla KVKK ve GDPR uyarınca "
            "çerez(cookie) kullanmaktadır.")
        temiz = fetch_article.kuyrugu_kes(govde)
        self.assertNotIn("çerez", temiz)
        self.assertIn("Enflasyon", temiz)


class TestRozetVeDizgi(unittest.TestCase):
    def test_prompt_kodlari_turkce_etiketle_basilir(self):
        # Kayıtlı içeriğin yarısı bu kodlarla geliyor; rozete "SEKTOREL HABER VE ANALIZ" basılıyordu
        beklenen = {
            "TAPU_VE_HUKUK": "TAPU & HUKUK",
            "EV_SAHIBI_VE_KIRACI": "KİRACI & EV SAHİBİ",
            "YATIRIM_VE_PIYASA": "YATIRIM & PİYASA",
            "ARSA_IMAR_VE_TINY_HOUSE": "ARSA & İMAR",
            "SEKTOREL_HABER_VE_ANALIZ": "SEKTÖR GÜNDEMİ",
        }
        for kod, etiket in beklenen.items():
            self.assertEqual(kategori_temizle(kod), etiket)
        # Her prompt kodu haritada olmalı: yeni kod eklenip haritaya eklenmezse kırılır
        import re
        for kod in re.findall(r"[A-Z_]{6,}", generate_text._SEMA_B1.split('"kategori_kodu":')[1].split("\n")[0]):
            self.assertNotIn("_", kategori_temizle(kod), kod)

    def test_ic_kod_rozete_sizmaz(self):
        self.assertEqual(kategori_temizle("S5-004"), "FİNANS & KREDİ")
        self.assertEqual(kategori_temizle("S4-010"), "RAKAM & BÖLGE")
        for kod in ("KREDI-01", "Trakya-TicariKira-01", "YENI_KOD"):
            self.assertEqual(kategori_temizle(kod), "GAYRİMENKUL REHBERİ")
        # Boşluklu serbest metin olduğu gibi kalır
        self.assertEqual(kategori_temizle("Arsa ve Tarla Kredisi"), "Arsa ve Tarla Kredisi")

    def test_harf_buyuklugu_bozuk_rozet_basilmaz(self):
        self.assertFalse(rozet_okunur_mu("NE YAPMalisiniz"))
        self.assertTrue(rozet_okunur_mu("NE YAPMALISINIZ"))
        self.assertTrue(rozet_okunur_mu("Korunma adımları"))
        self.assertFalse(rozet_okunur_mu(""))


if __name__ == "__main__":
    unittest.main()
