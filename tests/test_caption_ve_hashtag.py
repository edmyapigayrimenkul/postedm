"""
tests/test_caption_ve_hashtag.py — Açıklamalara Hook, Soru ve Hashtag Standardı Testleri
"""

import unittest
from unittest.mock import MagicMock, patch

from src import generate_text, telegram_bot


class TestCaptionVeHashtag(unittest.TestCase):
    def test_caption_zenginlestir_temel(self):
        """Düz bir metne kanca, etkileşim sorusu ve hashtagler eklenmeli."""
        duz_metin = (
            "Hisseli tapularda diğer ortakların yasal ön alım hakkı vardır. "
            "Noterden feragatname almadan yapılan satışlarda ortaklar tapu bedeli üzerinden hisseyi geri alabilir."
        )
        zengin = generate_text.caption_zenginlestir(duz_metin, kategori_kodu="TAPU_VE_HUKUK", platform="instagram")

        # 1. Kanca ilk satırda olmalı
        satirlar = [s.strip() for s in zengin.split("\n") if s.strip()]
        self.assertTrue(len(satirlar) >= 3)
        self.assertIn("Hisseli tapularda", satirlar[0])

        # 2. Soru işareti (?) bulunmalı
        self.assertIn("?", zengin)
        self.assertTrue(any("?" in s for s in satirlar))

        # 3. Hashtag bloğu ve marka etiketleri bulunmalı
        self.assertIn("#EDMYapıGayrimenkul", zengin)
        self.assertIn("#Silivri", zengin)
        self.assertIn("#Gayrimenkul", zengin)
        self.assertIn("#Tapu", zengin)

    def test_caption_zenginlestir_idempotent(self):
        """Zaten zenginleştirilmiş bir metin tekrar işlendiğinde mükerrer soru ve etiket oluşmamalı."""
        metin = (
            "Tapuda bu imzayı atlarsanız mülkünüz elinizden gidebilir.\n\n"
            "Tüm hissedarlardan noter onaylı feragatname almayı unutmayın.\n\n"
            "Siz daha önce hisseli tapu alımında benzer bir durum yaşadınız mı? Yorumlarda buluşalım.\n\n"
            "#EDMYapıGayrimenkul #Silivri #Gayrimenkul #Arsa #Yatırım #Tapu"
        )
        tekrar = generate_text.caption_zenginlestir(metin, kategori_kodu="TAPU_VE_HUKUK", platform="instagram")

        # Soru sayısı 1 olmalı (iki kez soru eklenmemeli)
        self.assertEqual(tekrar.count("?"), 1)

        # Hashtag tekilleşmeli
        self.assertEqual(tekrar.count("#EDMYapıGayrimenkul"), 1)
        self.assertEqual(tekrar.count("#Silivri"), 1)

    def test_kategoriye_ozel_soru_ve_hashtagler(self):
        """Kira, arsa, tapu ve finans kategorilerine göre hedeflenmiş soru ve etiket seçilmeli."""
        # A. Kira konusu
        kira_metni = "Kira kontratında tahliye taahhütnamesinin tarihi boş bırakılırsa ne olur."
        kira_zengin = generate_text.caption_zenginlestir(kira_metni, kategori_kodu="EV_SAHIBI_VE_KIRACI")
        self.assertIn("?", kira_zengin)
        self.assertTrue("kira" in kira_zengin.lower() or "tahliye" in kira_zengin.lower())
        self.assertIn("#KiraSözleşmesi", kira_zengin)

        # B. Arsa / İmar konusu
        arsa_metni = "Tarla vasfındaki arazilere imar planı olmadan yapı ruhsatı verilmez."
        arsa_zengin = generate_text.caption_zenginlestir(arsa_metni, kategori_kodu="ARSA_IMAR_VE_TINY_HOUSE")
        self.assertIn("?", arsa_zengin)
        self.assertTrue("arsa" in arsa_zengin.lower() or "imar" in arsa_zengin.lower())
        self.assertTrue("#SilivriArsa" in arsa_zengin or "#İmar" in arsa_zengin)

        # C. Finans konusu
        finans_metni = "Konut kredisi faiz oranları ve BDDK ekspertiz değer limitleri."
        finans_zengin = generate_text.caption_zenginlestir(finans_metni, kategori_kodu="FINANS_VE_BANKACILIK")
        self.assertIn("?", finans_zengin)
        self.assertTrue("piyasa" in finans_zengin.lower() or "mevduat" in finans_zengin.lower() or "kredi" in finans_zengin.lower())
        self.assertIn("#KonutKredisi", finans_zengin)

    def test_threads_karakter_limiti(self):
        """Threads caption'ı 480 karakter bütçesini asla aşmamalı."""
        uzun_metin = (
            "Silivri ve Trakya genelinde arsa yatırımı yaparken tapu kütüğündeki şerhler ve beyanlar hanesini "
            "mutlaka inceleyin. Parselin üzerinde kamulaştırma, haciz veya ön alım hakkı şerhi bulunabilir. "
            "Belediyeden 1/1000'lik uygulama imar planı durumunu teyit etmeden kaparo vermeyin veya sözleşme imzalamayın. "
            "Aksi takdirde inşaat izni alamayacağınız bir parsele yüksek bedel ödemiş olursunuz."
        )
        th_caption = generate_text.caption_zenginlestir(uzun_metin, kategori_kodu="ARSA_IMAR_VE_TINY_HOUSE", platform="threads")
        self.assertLessEqual(len(th_caption), 480)
        self.assertIn("?", th_caption)
        self.assertIn("#", th_caption)

    def test_tiktok_karakter_limiti(self):
        """TikTok başlığı 150 karakter bütçesini aşmamalı ve anahtar etiketleri içermeli."""
        baslik = "Hisseli Tapuda Şufa Tuzağına Düşmemek İçin Yapılması Gerekenler"
        tt_baslik = generate_text.caption_zenginlestir(baslik, kategori_kodu="TAPU_VE_HUKUK", platform="tiktok")
        self.assertLessEqual(len(tt_baslik), 150)
        self.assertIn("#", tt_baslik)

    def test_captionlari_zenginlestir_sozluk(self):
        """_captionlari_zenginlestir sözlük içindeki tüm caption alanlarını güncellemelidir."""
        veri = {
            "manset_parca_1": "Hisseli Tapuda",
            "manset_vurgu": "ŞUFA TUZAĞI",
            "manset_parca_2": "İki Yıl Peşinizi Bırakmaz",
            "kategori_kodu": "TAPU_VE_HUKUK",
            "caption_instagram": "Payınızı diğer ortaklardan habersiz satarsanız şufa davası açılabilir.",
            "caption_threads": "Hisseli tapuda satış yaparken noter ihtarını unutmayın.",
        }
        zengin_veri = generate_text._captionlari_zenginlestir(veri)

        # Instagram zenginleştirilmiş olmalı
        self.assertIn("?", zengin_veri["caption_instagram"])
        self.assertIn("#EDMYapıGayrimenkul", zengin_veri["caption_instagram"])

        # Facebook otomatik türetilmiş veya zenginleştirilmiş olmalı
        self.assertIn("caption_facebook", zengin_veri)
        self.assertIn("?", zengin_veri["caption_facebook"])

        # Threads <= 480 olmalı
        self.assertLessEqual(len(zengin_veri["caption_threads"]), 480)
        self.assertIn("#", zengin_veri["caption_threads"])


if __name__ == "__main__":
    unittest.main()
