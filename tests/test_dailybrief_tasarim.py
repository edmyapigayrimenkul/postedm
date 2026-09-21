"""
tests/test_dailybrief_tasarim.py — Instabot DailyBrief Haber Tasarımı ve Sabotaj Testleri
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from PIL import Image

from src import make_image


class TestDailyBriefTasarim(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

        # Örnek test görseli
        self.test_foto = self.tmp_path / "foto.jpg"
        im = Image.new("RGB", (1200, 800), color="darkblue")
        im.save(self.test_foto, "JPEG")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_haber_dailybrief_besleme_olcusu(self):
        """Besleme modunda 1080x1350 piksel boyutunda üretilmeli."""
        haber = {
            "manset": "Silivri İmar Planı Askıya Çıktı",
            "spot": "Yeni düzenlemeyle birlikte tarım arazilerinde yapılaşma koşulları netleşti.",
            "kategori": "ARSA_VE_IMAR",
            "kaynak": "Emlakkulisi",
        }
        cikti = self.tmp_path / "dailybrief_besleme.jpg"
        res = make_image.haber_dailybrief_slayti_ciz(
            haber,
            foto_yolu=self.test_foto,
            cikti_yolu=cikti,
            olcu="besleme",
        )
        self.assertTrue(cikti.exists())
        im = Image.open(res)
        self.assertEqual(im.size, (1080, 1350))

    def test_haber_dailybrief_story_olcusu(self):
        """Story modunda 1080x1920 piksel boyutunda üretilmeli."""
        haber = {
            "manset": "Tapu Harcında 2026 Beyan Zorunluluğu",
            "spot": "Eksik beyan edilen tapu devirlerinde vergi ziyaı cezası uygulanacak.",
            "kategori": "TAPU_VE_HUKUK",
            "kaynak": "Resmi Gazete",
        }
        cikti = self.tmp_path / "dailybrief_story.jpg"
        res = make_image.haber_dailybrief_slayti_ciz(
            haber,
            foto_yolu=self.test_foto,
            cikti_yolu=cikti,
            olcu="story",
        )
        self.assertTrue(cikti.exists())
        im = Image.open(res)
        self.assertEqual(im.size, (1080, 1920))

    def test_haber_dailybrief_sabotaj_ve_eksik_alanlar(self):
        """Fotoğraf yolu yokken ve alanlar boşken çökmeden yedek zeminle üretilmeli."""
        haber_bos = {
            "manset": None,
            "spot": "",
            "kategori": None,
        }
        cikti = self.tmp_path / "dailybrief_sabotaj.jpg"
        res = make_image.haber_dailybrief_slayti_ciz(
            haber_bos,
            foto_yolu=self.tmp_path / "olmayan_foto.jpg",
            cikti_yolu=cikti,
            olcu="besleme",
        )
        self.assertTrue(cikti.exists())
        im = Image.open(res)
        self.assertEqual(im.size, (1080, 1350))

    def test_haber_dailybrief_stres_asiri_uzun_metin(self):
        """Çok uzun metin geldiğinde taşma yapmadan 3 satırda kırparak sığdırmalı."""
        haber_uzun = {
            "manset": "Silivri Selimpaşa'da Hisseli Tarla Satışlarında Yaşanan Önalım Şufa Davaları ve Hukuki İhtilaflar Hakkında Bilinmesi Gereken En Önemli Ayrıntılar",
            "spot": "Bu çok uzun bir spot metnidir ve defalarca tekrarlanarak " * 10,
            "kategori": "KENTSEL_DONUSUM",
            "kaynak": "Çevre ve Şehircilik Bakanlığı",
        }
        cikti = self.tmp_path / "dailybrief_stres.jpg"
        res = make_image.haber_dailybrief_slayti_ciz(
            haber_uzun,
            foto_yolu=self.test_foto,
            cikti_yolu=cikti,
            olcu="story",
        )
        self.assertTrue(cikti.exists())
        im = Image.open(res)
        self.assertEqual(im.size, (1080, 1920))

    def test_haber_dailybrief_detay_slayti_uret(self):
        """Detay slaytı 4:5 ve 9:16 boyutlarında, maddeler ve uzman notuyla üretilmeli."""
        haber = {
            "manset": "Silivri Selimpaşa'da Yeni İmar Planı Askıya Çıktı",
            "kategori": "ARSA_VE_IMAR",
            "kaynak": "İBB Şehircilik",
            "detay_maddeleri": [
                {"etiket": "KAPSANAN ALAN", "metin": "Selimpaşa D-100 aksı ve Ortaköy sanayi sınırı gelişim parselleri.", "renk": "kirmizi"},
                {"etiket": "YAPILAŞMA ŞARTLARI", "metin": "KAKS 0.60'a yükseltildi, ticaret ve konut fonksiyonu verildi.", "renk": "turkuaz"},
                {"etiket": "ASKI SÜRESİ", "metin": "30 günlük itiraz süreci başladı.", "renk": "yesil"},
            ],
            "uzman_notu": "Parselinizin yeni imar durumunu e-devletten hemen teyit edin.",
        }
        # 4:5 Besleme
        cikti_besleme = self.tmp_path / "dailybrief_detay_4_5.jpg"
        res1 = make_image.haber_dailybrief_detay_slayti_ciz(
            haber,
            foto_yolu=self.test_foto,
            cikti_yolu=cikti_besleme,
            olcu="besleme",
            sayfa_no="02 / 02",
        )
        self.assertTrue(cikti_besleme.exists())
        with Image.open(res1) as im1:
            self.assertEqual(im1.size, (1080, 1350))

        # 9:16 Story
        cikti_story = self.tmp_path / "dailybrief_detay_9_16.jpg"
        res2 = make_image.haber_dailybrief_detay_slayti_ciz(
            haber,
            foto_yolu=self.test_foto,
            cikti_yolu=cikti_story,
            olcu="story",
            sayfa_no="02 / 02",
        )
        self.assertTrue(cikti_story.exists())
        with Image.open(res2) as im2:
            self.assertEqual(im2.size, (1080, 1920))

    def test_dinamik_slayt_sayisi_belirle(self):
        """Dinamik slayt sayısı belirleyici (Seçenek 2) kural setini doğrulamalı."""
        # 3 maddeli zengin haber -> 3 slayt
        h3 = {
            "detay_maddeleri": [
                {"etiket": "BÖLGE", "metin": "Selimpaşa 142 ada ve 85 parsel"},
                {"etiket": "EMSAL", "metin": "KAKS 0.60, Yençok 3 kat"},
                {"etiket": "ASKI", "metin": "30 günlük askı süresi başladı"},
            ]
        }
        self.assertEqual(make_image.dailybrief_slayt_sayisi_belirle(h3), 3)

        # 2 maddeli teknik zengin haber -> 3 slayt
        h2_zengin = {
            "detay_maddeleri": [
                {"etiket": "KAPSANAN PARSELLER", "metin": "Selimpaşa D-100 kuzey aksı ile Ortaköy sanayi gelişim koridorundaki 142 ada ve muhtelif 85 parseli doğrudan kapsıyor."},
                {"etiket": "YENİ YAPILAŞMA VE EMSAL", "metin": "Konut ve ticaret alanlarında KAKS 0.60, Yençok 3 kat olarak sınırlandı. Donatı terkleri ve parselasyon şartları yeniden düzenlendi."},
            ]
        }
        self.assertEqual(make_image.dailybrief_slayt_sayisi_belirle(h2_zengin), 3)

        # 1 maddeli kısa haber -> 2 slayt
        h_kisa = {
            "spot": "Tahliye taahhütnamesinde tarih sonradan doldurulmuşsa ispat yükü kiracıya aittir."
        }
        self.assertEqual(make_image.dailybrief_slayt_sayisi_belirle(h_kisa), 2)

        # Açıkça belirtilmiş slayt_sayisi
        self.assertEqual(make_image.dailybrief_slayt_sayisi_belirle({"slayt_sayisi": 2, **h3}), 2)
        self.assertEqual(make_image.dailybrief_slayt_sayisi_belirle({"slayt_sayisi": 3, **h_kisa}), 3)

    def test_haber_dailybrief_slaytlari_uret_dinamik_3_ve_2(self):
        """make_image.haber_dailybrief_slaytlari_uret dinamik 2 veya 3 slayt üretmeli."""
        h_zengin = {
            "manset": "Silivri Selimpaşa ve Ortaköy'de Yeni İmar Planı Askıya Çıktı",
            "spot": "Çevre ve Şehircilik koordinasyonunda hazırlanan revizyon planı ilan edildi.",
            "kaynak": "Resmi Gazete",
            "detay_maddeleri": [
                {"etiket": "KAPSANAN BÖLGE", "metin": "142 ada ve 85 parsel kapsama alındı.", "renk": "kirmizi"},
                {"etiket": "YAPILAŞMA ŞARTLARI", "metin": "KAKS 0.60, Yençok 3 kat olarak sınırlandı.", "renk": "turkuaz"},
                {"etiket": "ASKI SÜRESİ", "metin": "30 günlük resmi askı süreci başlamıştır.", "renk": "yesil"},
            ],
            "uzman_notu": "Askı süresi dolmadan belediye askı panolarından parselinizi sorgulayın.",
        }
        slaytlar_3 = make_image.haber_dailybrief_slaytlari_uret(
            haber=h_zengin,
            cikti_dizini=self.tmp_path / "test_3s",
            cikti_onek="zengin_haber",
            foto_yolu=self.test_foto,
        )
        self.assertEqual(len(slaytlar_3), 3)
        for s in slaytlar_3:
            self.assertTrue(s.exists())
            with Image.open(s) as im:
                self.assertEqual(im.size, (1080, 1350))

        h_yalin = {
            "manset": "Merkez Bankası Faiz Kararını Açıkladı",
            "spot": "Politika faizi yüzde 45 seviyesinde sabit tutuldu.",
            "kaynak": "TCMB",
            "uzman_notu": "Kredi faiz oranlarının seyrini takip etmekte fayda var.",
        }
        slaytlar_2 = make_image.haber_dailybrief_slaytlari_uret(
            haber=h_yalin,
            cikti_dizini=self.tmp_path / "test_2s",
            cikti_onek="yalin_haber",
            foto_yolu=self.test_foto,
        )
        self.assertEqual(len(slaytlar_2), 2)
        for s in slaytlar_2:
            self.assertTrue(s.exists())
            with Image.open(s) as im:
                self.assertEqual(im.size, (1080, 1350))

    def test_yeni_formatlar_slaytlari_uret_dinamik_secenek_2(self):
        """yeni_formatlar.slaytlari_uret format_turu='dailybrief' için dinamik 3 ve 2 slaytı entegre üretmeli."""
        from src import yeni_formatlar
        zengin_veri = {
            "manset": "Silivri İmar Planı Revizyonu",
            "spot": "Yeni plan askıya çıktı.",
            "kategori": "ARSA_VE_IMAR",
            "kaynak": "Resmi Gazete",
            "format_turu": "dailybrief",
            "detay_maddeleri": [
                {"etiket": "PARSELLER", "metin": "Selimpaşa sanayi koridorundaki 142 ada ve muhtelif 85 parsel."},
                {"etiket": "EMSALLER", "metin": "Konut ve ticaret alanlarında KAKS 0.60 olarak güncellendi."},
                {"etiket": "İTİRAZ", "metin": "15 Ekim tarihine kadar itiraz dilekçesi verilebilecek."},
            ],
            "uzman_notu": "Askı süresini kaçırmayın, parselinizi sorgulayın.",
            "foto_yolu": str(self.test_foto),
        }
        res = yeni_formatlar.slaytlari_uret(
            zengin_veri,
            cikti_dizini=self.tmp_path / "yf_test",
            cikti_onek="yf_zengin",
            format_turu="dailybrief",
        )
        self.assertEqual(len(res), 3)

    def test_hook_motoru_stat_punch_ve_minimal_vurgu(self):
        """Hook motoru gayrimenkul verilerini ve editoryal kancaları doğru formatta üretmeli."""
        from src import hook_motoru

        # 1. Ada ve parsel verisinden stat_punch
        h_imar = {
            "manset": "Silivri Selimpaşa'da Yeni İmar Planı Askıya Çıktı",
            "spot": "142 ada ve 85 parseli kapsayan plan ilan edildi.",
            "kategori": "ARSA_VE_IMAR",
        }
        hook_imar = hook_motoru.hook_olustur(h_imar)
        self.assertIsNotNone(hook_imar)
        self.assertEqual(hook_imar["format"], "stat_punch")
        self.assertEqual(hook_imar["num_txt"], "142")
        self.assertEqual(hook_imar["unit_txt"], "ADA")
        self.assertIn("85 PARSEL", hook_imar["t1"])

        # 2. Açıkça belirtilmiş kanca alanından minimal_vurgu
        h_hukuk = {
            "manset": "Tahliye Taahhütnamesinde Emsal Karar",
            "spot": "Kiracının açtığı tespit davası reddedildi.",
            "kategori": "TAPU_VE_HUKUK",
            "kanca": "Boş Taahhütname Geçerli Sayıldı",
        }
        hook_hukuk = hook_motoru.hook_olustur(h_hukuk)
        self.assertIsNotNone(hook_hukuk)
        self.assertEqual(hook_hukuk["format"], "minimal_vurgu")
        self.assertIn("YARGITAY", hook_hukuk["kicker"])

        # 3. Başlıkla birebir örtüşen kancanın elenmesi
        self.assertFalse(
            hook_motoru._basliktan_farkli_mi(
                "SİLİVRİ İMAR PLANI",
                "ASKIYA ÇIKTI",
                "Silivri İmar Planı Askıya Çıktı",
            )
        )

    def test_haber_dailybrief_kapak_hook_entegrasyonu(self):
        """Kapak slaytında hook uygulandığında görsel boyutları ve bütünlüğü korunmalı."""
        h = {
            "manset": "Silivri Alibey Mahallesi İmar Planı Değişikliği",
            "spot": "30 günlük askı ve itiraz süreci resmen başladı.",
            "kategori": "ARSA_VE_IMAR",
            "kaynak": "İBB Şehircilik",
        }
        cikti = self.tmp_path / "kapak_hook_test.jpg"
        res = make_image.haber_dailybrief_slayti_ciz(
            h,
            foto_yolu=self.test_foto,
            cikti_yolu=cikti,
            olcu="besleme",
            sayfa_no="01 / 02",
        )
        self.assertTrue(cikti.exists())
        with Image.open(res) as im:
            self.assertEqual(im.size, (1080, 1350))


if __name__ == "__main__":
    unittest.main()

