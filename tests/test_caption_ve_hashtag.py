"""
tests/test_caption_ve_hashtag.py — Açıklamalara Hook, Kapanış Çağrısı ve Hashtag Standardı Testleri
"""

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import unittest
from unittest.mock import MagicMock, patch

from src import generate_text, telegram_bot


class TestCaptionVeHashtag(unittest.TestCase):
    """2026-09-24 kararı: caption soruyla değil kaydet/gönder çağrısıyla biter,
    site ve telefon satırı taşır, genel etiket (#Gayrimenkul, #Yatırım) yerine
    konunun kendi terimini etiketler."""

    def test_caption_zenginlestir_temel(self):
        duz_metin = (
            "Hisseli tapularda diğer ortakların yasal ön alım hakkı vardır. "
            "Noterden feragatname almadan yapılan satışlarda ortaklar hisseyi alıcıdan alabilir."
        )
        zengin = generate_text.caption_zenginlestir(duz_metin, kategori_kodu="TAPU_VE_HUKUK", platform="instagram")

        satirlar = [s.strip() for s in zengin.split("\n") if s.strip()]
        self.assertIn("Hisseli tapularda", satirlar[0])
        self.assertNotIn("?", zengin)
        self.assertIn("Hisseli tapusu olan birine gönderin.", zengin)
        self.assertIn("edmyapigayrimenkul.com", zengin)
        self.assertIn("0536 343 41 97", zengin)

        import re
        etiketler = re.findall(r"#[A-Za-z0-9ÇĞİÖŞÜçğıöşü_]+", zengin)
        self.assertLessEqual(len(etiketler), 5)
        self.assertIn("#EDMYapıGayrimenkul", etiketler)
        self.assertIn("#Silivri", etiketler)
        self.assertIn("#HisseliTapu", etiketler)
        self.assertNotIn("#Gayrimenkul", etiketler)
        self.assertNotIn("#Yatırım", etiketler)

    def test_caption_zenginlestir_idempotent(self):
        """Yayın anında tekrar çağrılır: soru paragrafı atılır, çağrı/etiket/iletişim tekrarlanmaz."""
        metin = (
            "Tapuda bu imzayı atlarsanız hissenizi satamayabilirsiniz.\n\n"
            "Tüm hissedarlardan noter onaylı feragatname isteyin.\n\n"
            "Siz daha önce hisseli tapu alımında benzer bir durum yaşadınız mı? Yorumlarda buluşalım.\n\n"
            "#EDMYapıGayrimenkul #Silivri #Gayrimenkul #Arsa #Yatırım"
        )
        bir = generate_text.caption_zenginlestir(metin, kategori_kodu="TAPU_VE_HUKUK", platform="instagram")
        iki = generate_text.caption_zenginlestir(bir, kategori_kodu="TAPU_VE_HUKUK", platform="instagram")
        self.assertEqual(bir, iki)
        self.assertNotIn("?", bir)
        self.assertEqual(bir.count("gönderin"), 1)
        self.assertEqual(bir.count("edmyapigayrimenkul.com"), 1)
        self.assertEqual(bir.count("#EDMYapıGayrimenkul"), 1)
        self.assertNotIn("#Gayrimenkul ", bir + " ")

    def test_konuya_ozel_cagri_ve_etiketler(self):
        kira = generate_text.caption_zenginlestir(
            "Kira kontratında tahliye taahhütnamesinin tarihi boş bırakılırsa geçersiz sayılabilir.",
            kategori_kodu="EV_SAHIBI_VE_KIRACI")
        self.assertIn("Kira sözleşmesini yenilemeden önce", kira)
        self.assertIn("#Tahliye", kira)

        arsa = generate_text.caption_zenginlestir(
            "Tarla vasfındaki arazilere imar planı olmadan yapı ruhsatı verilmez.",
            kategori_kodu="ARSA_IMAR_VE_TINY_HOUSE")
        self.assertIn("Arsaya bakmaya gideceğiniz gün", arsa)
        self.assertTrue("#İmarDurumu" in arsa or "#TarlaAlırken" in arsa)

        finans = generate_text.caption_zenginlestir(
            "Konut kredisi faiz oranları ve BDDK ekspertiz değer limitleri.",
            kategori_kodu="FINANS_VE_BANKACILIK")
        self.assertIn("Kredi başvurusundan önce", finans)
        self.assertIn("#KonutKredisi", finans)

    def test_threads_karakter_limiti(self):
        uzun_metin = (
            "Silivri ve Trakya genelinde arsa yatırımı yaparken tapu kütüğündeki şerhler ve beyanlar hanesini "
            "inceleyin. Parselin üzerinde kamulaştırma, haciz veya ön alım hakkı şerhi bulunabilir. "
            "Belediyeden 1/1000'lik uygulama imar planı durumunu teyit etmeden kaparo vermeyin veya sözleşme imzalamayın. "
            "Aksi takdirde inşaat izni alamayacağınız bir parsele yüksek bedel ödemiş olursunuz."
        )
        th = generate_text.caption_zenginlestir(uzun_metin, kategori_kodu="ARSA_IMAR_VE_TINY_HOUSE", platform="threads")
        self.assertLessEqual(len(th), 480)
        self.assertIn("kaydedin", th)
        self.assertIn("#", th)
        # Threads tek konu etiketini bağlar: ilk etiket konunun kendisi
        import re
        self.assertNotEqual(re.findall(r"#\S+", th)[0], "#Silivri")

    def test_tiktok_karakter_limiti(self):
        baslik = "Hisseli tapuda önalım hakkı nasıl kullanılır"
        tt = generate_text.caption_zenginlestir(baslik, kategori_kodu="TAPU_VE_HUKUK", platform="tiktok")
        self.assertLessEqual(len(tt), 150)
        self.assertIn("#", tt)

    def test_captionlari_zenginlestir_sozluk(self):
        veri = {
            "manset_parca_1": "Hisseli tapuda",
            "manset_vurgu": "ÖNALIM HAKKI",
            "manset_parca_2": "satıştan sonra da kullanılabilir",
            "kategori_kodu": "TAPU_VE_HUKUK",
            "caption_instagram": "Payınızı diğer ortaklara bildirmeden satarsanız önalım davası açılabilir.",
            "caption_threads": "Hisseli tapuda satış yaparken noter bildirimini atlamayın.",
        }
        zengin = generate_text._captionlari_zenginlestir(veri)
        self.assertNotIn("?", zengin["caption_instagram"])
        self.assertIn("#EDMYapıGayrimenkul", zengin["caption_instagram"])
        self.assertIn("caption_facebook", zengin)
        self.assertIn("gönderin", zengin["caption_facebook"])
        self.assertLessEqual(len(zengin["caption_threads"]), 480)
        self.assertIn("#", zengin["caption_threads"])

    def test_tum_platformlarda_azami_bes_hashtag(self):
        """Instagram, Facebook, Threads, TikTok ve YouTube'da azami hashtag sayısı 5'i geçemez."""
        import re
        from src import tiktok, youtube

        metin = "Silivri Çanta bölgesinde 500 m² müstakil parsel satılık arsa fırsatı."

        # 1. Instagram
        ig = generate_text.caption_zenginlestir(metin, kategori_kodu="ARSA_IMAR_VE_TINY_HOUSE", platform="instagram")
        ig_tags = re.findall(r"#[A-Za-z0-9ÇĞİÖŞÜçğıöşü_]+", ig)
        self.assertLessEqual(len(ig_tags), 5, f"Instagram'da 5'ten fazla etiket var: {ig_tags}")

        # 2. Facebook
        fb = generate_text.caption_zenginlestir(metin, kategori_kodu="ARSA_IMAR_VE_TINY_HOUSE", platform="facebook")
        fb_tags = re.findall(r"#[A-Za-z0-9ÇĞİÖŞÜçğıöşü_]+", fb)
        self.assertLessEqual(len(fb_tags), 5, f"Facebook'ta 5'ten fazla etiket var: {fb_tags}")

        # 3. Threads
        th = generate_text.caption_zenginlestir(metin, kategori_kodu="ARSA_IMAR_VE_TINY_HOUSE", platform="threads")
        th_tags = re.findall(r"#[A-Za-z0-9ÇĞİÖŞÜçğıöşü_]+", th)
        self.assertLessEqual(len(th_tags), 5, f"Threads'te 5'ten fazla etiket var: {th_tags}")

        # 4. TikTok
        tt = tiktok.baslik_kur("Silivri Satılık Arsa", ["#arsa", "#tarla", "#yatırım", "#silivri", "#emlak", "#fırsat", "#keşfet"])
        tt_tags = re.findall(r"#[A-Za-z0-9ÇĞİÖŞÜçğıöşü_]+", tt)
        self.assertLessEqual(len(tt_tags), 5, f"TikTok'ta 5'ten fazla etiket var: {tt_tags}")

        # 5. YouTube Shorts İmzası
        yt_imza = "\n\n#Shorts #Silivri #EDMYapıGayrimenkul"
        yt_tags = re.findall(r"#[A-Za-z0-9ÇĞİÖŞÜçğıöşü_]+", yt_imza)
        self.assertLessEqual(len(yt_tags), 5, f"YouTube'da 5'ten fazla etiket var: {yt_tags}")


if __name__ == "__main__":
    unittest.main()
