"""
tests/test_platform_metinleri_ve_sabotaj.py — Platforma Özel Metin & Kanca Mimarisi ve Sabotaj/Stres Testleri.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src import generate_text, linkedin, threads, tiktok
from src.yayin import baglam, dagitim, hedef, sonuc


class TestPlatformMetinleriVeKancalar(unittest.TestCase):
    """Her platform için üretilen kanca (hook) ve metinlerin editoryal doğruluğunu denetler."""

    def setUp(self):
        self.ornek_haber = {
            "id": 888,
            "manset": "Hisseli Tapuda Şufa Hakkı Riski",
            "kanca": "Tapuda bu şerhi görmezden gelen mülkünü kaybedebilir",
            "spot": "Hisseli tarla ve arsa alımlarında diğer hissedarların 2 yıllık önalım hakkı davası açma riski bulunuyor.",
            "kategori": "TAPU_VE_HUKUK",
            "kategori_kodu": "TAPU_VE_HUKUK",
            "yasal_dayanak": "Türk Medeni Kanunu md. 732 ve 733",
            "detay_maddeleri": [
                {"etiket": "NOTER BİLDİRİMİ", "metin": "Satışın diğer hissedarlara noter kanalıyla bildirilmesi dava süresini 3 aya indirir."},
                {"etiket": "FİİLİ TAKSİM", "metin": "Arsa fiilen bölünmüş ve herkes kendi yerini kullanıyorsa şufa hakkı kullanılamaz."}
            ],
            "uzman_notu": "Silivri ve Çatalca'daki hisseli tarla yatırımlarında noter tebligatı olmadan yapılan alımlar ciddi dava riski taşır.",
            "sana_etkisi": "Silivri ve Çatalca'daki hisseli tarla yatırımlarında noter tebligatı olmadan yapılan alımlar ciddi dava riski taşır.",
        }

        self.ornek_otorite = {
            "bicim": "B3",
            "kategori_kodu": "KIRA_VE_TAHLIYE",
            "manset": "Tahliye Taahhüdünde Tarih Tuzağı",
            "spot": "Boş kağıda imza atan kiracı yasal olarak zor durumda kalabilir.",
            "yasal_dayanak": "6098 sayılı Türk Borçlar Kanunu md. 352",
            "slayt_2_detay": {
                "kart_1": {"baslik": "Kira Günü İmza", "aciklama": "Sözleşmeyle aynı gün verilen taahhütname geçersizdir."},
                "kart_2": {"baslik": "Yazılı Şekil", "aciklama": "Taahhüdün geçerli olması için yazılı olması şarttır."}
            },
            "slayt_3_cozum": {
                "maddeler": [
                    {"baslik": "Tarihi Kontrol Edin", "aciklama": "Düzenleme tarihi sözleşmeden sonraki bir gün olmalıdır."},
                    {"baslik": "Noter Şartı", "aciklama": "İspat kolaylığı için taahhüt noter huzurunda verilmelidir."}
                ]
            },
            "slayt_4_cta": {
                "kaydet_metni": "Kira sözleşmenizi imzalamadan önce haklarınızı korumak için bu bilgiyi kaydedin."
            }
        }

    # 1. LINKEDIN B2B EDİTORYAL TESTLERİ
    def test_linkedin_metni_b2b_ve_hukuki_yapisi(self):
        """LinkedIn metni B2B, mevzuat dayanağı ve sektörel analiz blokları içermelidir."""
        metin = linkedin.linkedin_metni_hazirla(self.ornek_haber)
        
        self.assertIn("Hisseli Tapuda Şufa Hakkı Riski", metin)
        self.assertIn("MEVZUAT VE YASAL DAYANAK", metin)
        self.assertIn("Türk Medeni Kanunu md. 732 ve 733", metin)
        self.assertIn("📊 ÖNE ÇIKAN VERİLER VE ANALİZ:", metin)
        self.assertIn("NOTER BİLDİRİMİ", metin)
        self.assertIn("BÖLGESEL PİYASA DEĞERLENDİRMESİ", metin)
        self.assertIn("edmyapigayrimenkul.com", metin)
        self.assertIn("#GayrimenkulYatırımı", metin)
        # Soru kalıbı olmamalı
        self.assertNotIn("Yorumlarda buluşalım", metin)
        self.assertNotIn("Siz ne düşünüyorsunuz?", metin)

    def test_linkedin_metni_otorite_ve_sozluk_kartlarini_zenginlestirir(self):
        """LinkedIn metni B3/Otorite şemasındaki kartları ve çözüm adımlarını maddeli döker."""
        metin = linkedin.linkedin_metni_hazirla(self.ornek_otorite)
        self.assertIn("HUKUKİ ANALİZ VE ÇÖZÜM ADIMLARI:", metin)
        self.assertIn("Risk/Hata: Kira Günü İmza", metin)
        self.assertIn("Yasal Kural: Yazılı Şekil", metin)
        self.assertIn("Tarihi Kontrol Edin", metin)
        self.assertIn("6098 sayılı Türk Borçlar Kanunu md. 352", metin)

    # 2. THREADS ZİNCİR VE KANCA TESTLERİ
    def test_threads_zincir_kancasi_ve_parca_dagilimi(self):
        """Threads kök gönderisi merak uyandıran zincir kancasıyla başlamalı, her slayt 480 karakter altında kalmalıdır."""
        gorseller = ["https://cdn.example.com/1.jpg", "https://cdn.example.com/2.jpg", "https://cdn.example.com/3.jpg", "https://cdn.example.com/4.jpg"]
        sayfalar = threads.metinleri_slaytlara_dagit(self.ornek_otorite, gorseller)

        self.assertEqual(len(sayfalar), 4)
        
        # 1. Parça (Kök Gönderi)
        kok = sayfalar[0]["metin"]
        self.assertIn("📌", kok)
        self.assertIn("👇", kok)
        self.assertIn("zincirde 🧵", kok)
        self.assertLessEqual(len(kok), 480)

        # Son Parça (Kapanış)
        son = sayfalar[-1]["metin"]
        self.assertIn("🤝", son)
        self.assertIn("kaydedin", son)
        self.assertNotIn("Yorumlarda buluşalım", son)
        self.assertNotIn("Siz bu konuda ne düşünüyorsunuz?", son)
        self.assertLessEqual(len(son), 480)

        # Tüm parçalar karakter sınırında
        for idx, s in enumerate(sayfalar, 1):
            self.assertLessEqual(len(s["metin"]), 480, f"Sayfa {idx} 480 sınırı aştı: {len(s['metin'])}")

    # 3. TIKTOK KANCA VE BAŞLIK TESTLERİ
    def test_tiktok_baslik_ve_aciklama_kancasi(self):
        """TikTok başlığı 150 karakter sınırını aşmamalı, carousel açıklaması zengin olmalıdır."""
        baslik = "Hisseli Tapulu Arsa Alırken Bu 3 Kuralı Bilmeyen Parasını Kaybediyor!"
        etiketler = ["#Tapu", "#ArsaYatırımı", "#Silivri", "#Emlak", "#keşfet"]
        
        tt_baslik = tiktok.baslik_kur(baslik, etiketler)
        self.assertLessEqual(len(tt_baslik), 150)
        self.assertIn("Hisseli Tapulu Arsa", tt_baslik)
        self.assertIn("#Tapu", tt_baslik)

        tt_aciklama = tiktok.aciklama_kur(
            metin="Tapuda şufa hakkı ve noter tebligatı yapılmadığında diğer hissedarlar 2 yıl içinde dava açabilir.\n\n#Tapu #Silivri",
            etiketler=["#EDMYapı", "#Gayrimenkul"]
        )
        self.assertIn("Tapuda şufa hakkı", tt_aciklama)
        self.assertIn("#Silivri", tt_aciklama)
        self.assertIn("#EDMYapı", tt_aciklama)
        self.assertLessEqual(len(tt_aciklama), 4000)

    # 4. INSTAGRAM VE FACEBOOK EDİTORYAL TESTLERİ
    def test_caption_zenginlestir_platform_ayrisimi(self):
        """caption_zenginlestir platforma göre doğru kurumsal kapanış ve etiket üretmelidir."""
        ham_metin = "Silivri'de hisseli arsa satışlarında yeni dönem başladı. Noter şartı getirildi."
        
        ig_metin = generate_text.caption_zenginlestir(ham_metin, platform="instagram", manset="Hisseli Arsa Satışında Noter Şartı")
        self.assertIn("edmyapigayrimenkul.com", ig_metin)
        self.assertIn("#EDMYapıGayrimenkul", ig_metin)
        self.assertNotIn("?", ig_metin.split("\n")[-1])  # Soruyla bitmemeli

        threads_metin = generate_text.caption_zenginlestir(ham_metin, platform="threads", manset="Hisseli Arsa")
        self.assertLessEqual(len(threads_metin), 480)
        self.assertIn("edmyapigayrimenkul.com", threads_metin)

        li_metin = generate_text.caption_zenginlestir(ham_metin, platform="linkedin", manset="Hisseli Arsa Analizi")
        self.assertIn("#GayrimenkulYatırımı", li_metin)

    # 5. TÜM İÇERİK FORMATLARININ (HABER, NEDİR DOĞRUSU, NET CEVAP, VAKA, SÖZLÜK, REELS, İLAN) UYUMLULUĞU
    def test_tum_icerik_formatlari_tum_platformlara_uyumludur(self):
        """Haber, Nedir Doğrusu, Net Cevap, Vaka, Sözlük, Reels ve İlan formatlarının tüm platform çıktıları kurallara uymalıdır."""
        format_ornekleri = [
            # 1. Haber
            {
                "tur": "haber",
                "manset": "Silivri İmar Planı Askıya Çıktı",
                "spot": "Yeni konut ve ticaret alanları için askı süreci başladı.",
                "yasal_dayanak": "3194 sayılı İmar Kanunu md. 8",
                "detay_maddeleri": [{"etiket": "İtiraz Süresi", "metin": "30 gün içinde itiraz edilebilir."}]
            },
            # 2. Nedir Doğrusu
            {
                "tur": "nedir_dogrusu",
                "manset": "Tapu Harcını Kim Öder?",
                "spot": "Alıcı ve satıcı arasındaki harç paylaşımı kuralları.",
                "yasal_dayanak": "492 sayılı Harçlar Kanunu",
                "slayt_2_detay": {
                    "kart_1": {"baslik": "Yaygın Hata", "aciklama": "Hepsini alıcı öder sanılır."},
                    "kart_2": {"baslik": "Yasal Kural", "aciklama": "Yarı yarıya (%2 + %2) ödenir."}
                },
                "slayt_3_cozum": {"maddeler": [{"baslik": "Sözleşme Maddesi", "aciklama": "Aksi kararlaştırılabilir."}]}
            },
            # 3. Net Cevap
            {
                "tur": "net_cevap",
                "manset": "Hisseli Tapuya Ev Yapılır mı?",
                "spot": "Tüm hissedarların muvafakati olmadan yapı ruhsatı alınamaz.",
                "yasal_dayanak": "3194 sayılı İmar Kanunu md. 22",
                "slayt_2_detay": {"kart_1": {"baslik": "Ruhsat Şartı", "aciklama": "Hissedar imzası şarttır."}}
            },
            # 4. Örnek Olay / Vaka
            {
                "tur": "vaka",
                "manset": "Notersiz Gayrimenkul Satış Vaadi Tuzağı",
                "spot": "Adi yazılı senetle arsa alan yatırımcı tapuyu alamadı.",
                "yasal_dayanak": "TBK md. 237 ve Noterlik Kanunu md. 60",
                "slayt_2_detay": {"kart_1": {"baslik": "Hukuki Hata", "aciklama": "Resmi şekil şartına uyulmadı."}}
            },
            # 5. Sözlük Kartı
            {
                "tur": "sozluk",
                "manset": "Şufa (Önalım) Hakkı Nedir?",
                "spot": "Paydaşın payını üçüncü kişiye satması durumunda diğer paydaşların öncelikle satın alma hakkıdır.",
                "yasal_dayanak": "TMK md. 732",
                "detay_metni": json.dumps({"terim": "ŞUFA HAKKI", "anlam": "Paydaşın öncelikle alma hakkı", "yasal_dayanak": "TMK md. 732"})
            },
            # 6. Reels
            {
                "tur": "reels",
                "manset": "Arsa Alırken Dikkat Edilmesi Gereken 3 Madde",
                "spot": "Kadastro yolu olmayan araziye inşaat izni verilmez.",
                "yasal_dayanak": "Plansız Alanlar İmar Yönetmeliği"
            },
            # 7. İlan
            {
                "tur": "ilan",
                "baslik": "Silivri Alibey Satılık Arsa",
                "manset": "Silivri Alibey Satılık Arsa",
                "spot": "İmar sınırında 500 m2 müstakil parsel.",
                "kaynak_url": "https://edmyapigayrimenkul.com/ilan/123"
            }
        ]

        gorseller = ["https://cdn.example.com/s1.jpg", "https://cdn.example.com/s2.jpg", "https://cdn.example.com/s3.jpg"]

        for ornek in format_ornekleri:
            tur = ornek["tur"]
            # 1. LinkedIn
            li = linkedin.linkedin_metni_hazirla(ornek)
            self.assertNotIn("*", li, f"{tur} formatında LinkedIn'de * kaldı")
            self.assertNotIn("Yorumlarda buluşalım", li, f"{tur} formatında LinkedIn'de soru kalıbı kaldı")
            self.assertIn("edmyapigayrimenkul.com", li)

            # 2. Threads Zinciri
            th_zincir = threads.metinleri_slaytlara_dagit(ornek, gorseller)
            for idx, sayfa in enumerate(th_zincir):
                metin = sayfa["metin"]
                self.assertLessEqual(len(metin), 480, f"{tur} formatında Threads sayfa {idx} 480 k. aştı")
                self.assertNotIn("*", metin, f"{tur} formatında Threads sayfa {idx}'de * kaldı")
                self.assertNotIn("Yorumlarda buluşalım", metin)

            # 3. TikTok Başlık ve Açıklama
            tt_b = tiktok.baslik_kur(ornek.get("manset") or ornek.get("baslik", ""))
            tt_a = tiktok.aciklama_kur(ornek.get("spot") or ornek.get("manset", ""))
            self.assertLessEqual(len(tt_b), 150, f"{tur} formatında TikTok başlığı 150 k. aştı")
            self.assertNotIn("*", tt_b)
            self.assertNotIn("*", tt_a)

            # 4. Instagram Caption
            ig = generate_text.caption_zenginlestir(ornek.get("spot") or ornek.get("manset", ""), platform="instagram", manset=ornek.get("manset"))
            self.assertNotIn("*", ig, f"{tur} formatında Instagram'da * kaldı")
            self.assertNotIn("Yorumlarda buluşalım", ig)


class TestSabotajVeStres(unittest.TestCase):
    """Bozuk veri, aşırı yük ve kanal çöküşlerine karşı sistemin dayanıklılığını test eder."""

    # 1. BOZUK VE NULL GİRDİ SABOTAJI
    def test_null_ve_bozuk_veri_sabotaji(self):
        """None, boş sözlük veya hasarlı tipler metin motorunu çökertmemelidir."""
        self.assertEqual(linkedin.linkedin_metni_hazirla({}), "")
        self.assertEqual(linkedin.linkedin_metni_hazirla(None), "")
        self.assertEqual(threads.metinleri_slaytlara_dagit({}, []), [])
        self.assertEqual(threads.metinleri_slaytlara_dagit(None, []), [])
        self.assertIn("#EDMYapı", tiktok.baslik_kur("", None))
        self.assertEqual(tiktok.aciklama_kur("", None), "#EDMYapı #Emlak #Silivri #Gayrimenkul #keşfet")
        self.assertEqual(generate_text.caption_zenginlestir("", platform="instagram"), "")
        self.assertEqual(generate_text.caption_zenginlestir(None, platform="threads"), "")

    # 2. AŞIRI UZUNLUK (BUFFER OVERFLOW) SABOTAJI
    def test_asiri_uzunluk_stresi(self):
        """10.000 karakterlik metin verildiğinde hiçbir platform çökmemeli ve limitlerine sığmalıdır."""
        dev_metin = "EDM Yapı Gayrimenkul Silivri Analizi " * 300  # ~10.800 karakter
        
        # Threads: 480 karakter sınırı
        th_metin = generate_text.caption_zenginlestir(dev_metin, platform="threads", manset="Dev Başlık")
        self.assertLessEqual(len(th_metin), 480)
        self.assertTrue(th_metin.endswith("…") or "#" in th_metin)

        # TikTok: 150 karakter sınırı
        tt_baslik = tiktok.baslik_kur(dev_metin, ["#tag1", "#tag2"])
        self.assertLessEqual(len(tt_baslik), 150)

        # LinkedIn: 10.000 karakteri temizlemeli ama çökmemeli
        li_metin = linkedin.linkedin_metni_hazirla({"manset": "Dev Başlık", "spot": dev_metin})
        self.assertTrue(len(li_metin) > 0)

    # 3. XSS VE SQL ENJEKSİYONU SABOTAJI
    def test_xss_ve_enjeksiyon_sabotaji(self):
        """Zararlı HTML/JS ve SQL enjeksiyonları filtrelenmeli ve temizlenmelidir."""
        zararli = "<script>alert('pwned');</script> '; DROP TABLE haberler; -- <b>Kritik Uyarı</b>"
        
        temiz_ig = generate_text.caption_zenginlestir(zararli, platform="instagram")
        self.assertNotIn("<script>", temiz_ig)
        self.assertNotIn("</script>", temiz_ig)
        
        temiz_li = linkedin.linkedin_metni_hazirla({"manset": zararli, "spot": zararli})
        self.assertNotIn("<script>", temiz_li)
        
        sayfalar = threads.metinleri_slaytlara_dagit({"manset": zararli}, ["https://cdn.example.com/1.jpg"])
        self.assertNotIn("<script>", sayfalar[0]["metin"])

    # 3b. AÇIKLAMALARDA MARKDOWN YILDIZ (*) VE BOLD TEMİZLİĞİ
    def test_markdown_yildiz_ve_bold_isaretleri_asla_aciklamaya_sizmaz(self):
        """Instagram, Threads, LinkedIn, TikTok ve Facebook açıklamalarında hiçbir zaman * veya ** işaretleri görünmemelidir."""
        kirli_metin = "**Önemli Uyarı:** Tapu devrinde *kesinlikle* boş kağıda imza atmayın! ***Dikkat*** * Madde 1 * Madde 2"
        
        # Instagram
        ig_sonuc = generate_text.caption_zenginlestir(kirli_metin, platform="instagram")
        self.assertNotIn("*", ig_sonuc)
        self.assertIn("Önemli Uyarı:", ig_sonuc)
        self.assertIn("kesinlikle", ig_sonuc)

        # Threads
        th_sonuc = generate_text.caption_zenginlestir(kirli_metin, platform="threads")
        self.assertNotIn("*", th_sonuc)

        # LinkedIn
        li_sonuc = linkedin.linkedin_metni_hazirla({"manset": kirli_metin, "spot": kirli_metin})
        self.assertNotIn("*", li_sonuc)

        # TikTok Başlık & Açıklama
        tt_b = tiktok.baslik_kur(kirli_metin)
        tt_a = tiktok.aciklama_kur(kirli_metin)
        self.assertNotIn("*", tt_b)
        self.assertNotIn("*", tt_a)

        # Threads Zincir Sayfaları
        sayfalar = threads.metinleri_slaytlara_dagit({"manset": kirli_metin, "spot": kirli_metin}, ["url1", "url2"])
        for s in sayfalar:
            self.assertNotIn("*", s["metin"])

    # 4. KANAL HATA İZOLASYONU (BİRİ ÇÖKSE DE DİĞERLERİ YAŞAMALI)
    def test_dagitim_motoru_kanal_hatalarini_izole_eder(self):
        """Bir veya iki kanal API hatası fırlatsa dahi dağıtım motoru çökmez, diğer kanallar başarıyla çalışır."""
        istek = hedef.istek_olustur("haber", "999", "ig,threads,linkedin,tiktok")
        b = baglam.YayinBaglami(
            istek=istek,
            haber={"id": 999, "manset": "Test Başlık", "kategori": "GENEL"},
            baslik="Test Başlık",
            caption="Test Açıklaması",
        )
        b.public_urller = ["https://cdn.example.com/s1.jpg", "https://cdn.example.com/s2.jpg"]
        b.slayt_yollari = ["/tmp/s1.jpg", "/tmp/s2.jpg"]

        mock_ilerleme = MagicMock()

        # Simülasyon:
        # Instagram: Başarılı
        # Threads: Başarılı
        # TikTok: 403 Unaudited hatası (HATA)
        # LinkedIn: 500 Network Exception (HATA)
        with (
            patch("src.instagram.carousel_yayinla", return_value="ig_post_123"),
            patch("src.threads.paylas", return_value="th_post_456"),
            patch("src.threads.zincir_paylas_sonuc", return_value={"kok_id": "th_post_456", "yayinlanan": 2, "toplam": 2, "eksik": []}),
            patch("src.tiktok.foto_yayinla", return_value={"durum": False, "hata": "HTTP 403 unaudited_client"}),
            patch("src.linkedin.kullanilabilir_mi", return_value=True),
            patch("src.linkedin.paylas", side_effect=RuntimeError("LinkedIn 500 Internal Server Error")),
        ):
            sonuc_dagitim = dagitim.dagit(b, ["instagram", "threads", "tiktok", "linkedin"], mock_ilerleme)

            # Doğrulamalar:
            # 1. Instagram başarılı ve kimliği var
            self.assertEqual(sonuc_dagitim.ig_id, "ig_post_123")
            # 2. Threads başarılı ve kimliği var
            self.assertEqual(sonuc_dagitim.threads_id, "th_post_456")
            # 3. TikTok ve LinkedIn hata verdi ama sistem ÇÖKMEDİ
            self.assertIn("tiktok", sonuc_dagitim.kanallar)
            self.assertIn("linkedin", sonuc_dagitim.kanallar)
            self.assertTrue(sonuc_dagitim.hata_var)
            self.assertTrue(sonuc_dagitim.herhangi_yayinda)

            # Rapor satırları incelenir: başarılı olanlar da hatalı olanlar da raporda var
            metinler = [s.metin for s in sonuc_dagitim.satirlar]
            self.assertTrue(any("Instagram" in m and "Paylaşıldı ✓" in m for m in metinler))
            self.assertTrue(any("Threads" in m and "paylaşıldı ✓" in m for m in metinler))
            self.assertTrue(any("TikTok" in m and "HTTP 403" in m for m in metinler))
            self.assertTrue(any("LinkedIn" in m and "Hata" in m for m in metinler))

    # 5. UNICODE, EMOJI VE ÖZEL KARAKTER STRES SABOTAJI
    def test_unicode_emoji_ve_karakter_sabotaji(self):
        """Ağır emojili, sıfır genişlikli boşluklu veya karışık dilli metinler motoru kilitlememeli."""
        karisik_metin = "🏢🔥 EDMYapı & Gayrimenkul 🚀💯 \u200b\u200c\u200d Silivri Arsa & Tarla Özel Fırsatı! 🇹🇷"
        
        # Instagram
        ig_res = generate_text.caption_zenginlestir(karisik_metin, platform="instagram")
        self.assertIn("EDMYapı", ig_res)
        self.assertIn("Silivri", ig_res)

        # Threads
        th_res = generate_text.caption_zenginlestir(karisik_metin, platform="threads")
        self.assertLessEqual(len(th_res), 480)

        # TikTok Başlık
        tt_res = tiktok.baslik_kur(karisik_metin, ["#EDM🚀", "#Silivri📍"])
        self.assertLessEqual(len(tt_res), 150)
        self.assertIn("EDMYapı", tt_res)

        # LinkedIn
        li_res = linkedin.linkedin_metni_hazirla({"manset": karisik_metin, "spot": karisik_metin})
        self.assertIn("EDMYapı", li_res)

    # 6. DEV PARÇALI THREADS ZİNCİRLEME STRESİ
    def test_dev_parcali_threads_zincir_stresi(self):
        """15 slaytlık devasa bir içerik verildiğinde 15 parçanın tümü eksiksiz ve limitler içinde dağıtılmalıdır."""
        gorseller = [f"https://cdn.example.com/slide_{i}.jpg" for i in range(1, 16)]
        dev_detay = {
            "manset": "Silivri İmar ve Arsa Yatırımının 15 Altın Kuralı",
            "spot": "Arsa alırken mağdur olmamak için bilmeniz gereken tüm hukuki ve teknik detaylar.",
            "detay_metni": json.dumps({
                "slayt_2_detay": {"kart_1": {"baslik": "Kural 1", "aciklama": "İmar durumunu sorgulayın."}},
                "slayt_3_cozum": {"maddeler": [{"baslik": f"Madde {k}", "aciklama": f"Açıklama detayı {k}"} for k in range(2, 14)]},
                "slayt_4_cta": {"kaydet_metni": "Bu 15 maddelik rehberi mutlaka kaydedin ve arşivleyin."}
            })
        }
        
        sayfalar = threads.metinleri_slaytlara_dagit(dev_detay, gorseller)
        self.assertEqual(len(sayfalar), 15)
        
        # 1. sayfa kanca olmalı
        self.assertIn("👇", sayfalar[0]["metin"])
        self.assertIn("zincirde 🧵", sayfalar[0]["metin"])
        
        # Son sayfa kurumsal kapanış olmalı
        self.assertIn("🤝", sayfalar[-1]["metin"])
        self.assertIn("kaydedin", sayfalar[-1]["metin"])
        
        # Bütün 15 sayfa karakter limitinde olmalı
        for i, s in enumerate(sayfalar):
            self.assertLessEqual(len(s["metin"]), 480, f"Sayfa {i+1} sınırı aştı: {len(s['metin'])}")

    # 7. TIKTOK TASLAK (INBOX DRAFT) BAŞARILI DURUM YÖNETİMİ
    def test_tiktok_inbox_draft_bilgi_olarak_islenir(self):
        """TikTok unaudited client olduğunda taslak moduna geçmeli ve bu durum HATA değil BILGI olarak kaydedilmelidir."""
        from src.yayin.kanallar import tt
        
        b = baglam.YayinBaglami(
            istek=hedef.istek_olustur("haber", "777", "tiktok"),
            haber={"id": 777, "manset": "Örnek Haber", "kategori": "GENEL"},
            baslik="Örnek Haber",
            caption="Örnek Açıklama",
        )
        b.public_urller = ["https://cdn.example.com/p1.jpg"]
        mock_ilerleme = MagicMock()

        # TikTok foto_yayinla taslak_mi=True dönüyor
        with patch("src.tiktok.foto_yayinla", return_value={"durum": True, "publish_id": "draft_789", "taslak_mi": True, "mod": "inbox_draft"}):
            ks = tt.yayinla(b, mock_ilerleme)
            
            # Etiket ve durum denetimi
            self.assertEqual(ks.kanal, "tiktok")
            self.assertEqual(ks.etiket, "📥 Taslak Yüklendi")
            self.assertEqual(len(ks.satirlar), 1)
            # Hata olmamalı, BILGI seviyesinde olmalı
            self.assertEqual(ks.satirlar[0].durum, sonuc.BILGI)
            self.assertIn("Taslak Olarak Yüklendi", ks.satirlar[0].metin)


if __name__ == "__main__":
    unittest.main()
