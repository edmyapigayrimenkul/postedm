"""
tests/test_fetch_news_instabot.py — Instabot Haber Motoru ve DailyBrief Paritesi Testleri

Test kapsamı:
1. Bozuk bayt onarımı (_bozuk_baytlari_onar)
2. TRT Haber özel xml_mobile ayrıştırması (_trt_ayristir)
3. SEO çöpü ve clickbait elemesi (baslik_elenmeli)
4. Katı kategori filtresi (1. ve 2. derece emlak haberleri vs siyaset/magazin/asayiş bloklistesi)
5. DailyBrief haber slayt üretimi (slaytlari_uret format_turu='dailybrief')
"""

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src import fetch_news, haber_puanlama, make_image, yeni_formatlar


class TestFetchNewsInstabot(unittest.TestCase):
    def test_bozuk_baytlari_onar(self):
        """Bozuk non-UTF8 baytlar içeren XML bayt dizisinin başarıyla onarılması."""
        bozuk_xml = b'<?xml version="1.0" encoding="utf-8"?><root><title>Test \x80\xff Hatal\xc4\xb1 Bayt</title></root>'
        onarilan = fetch_news._bozuk_baytlari_onar(bozuk_xml)
        self.assertIsInstance(onarilan, bytes)
        self.assertIn(b"encoding=\"utf-8\"", onarilan)
        metin = onarilan.decode("utf-8", errors="strict")
        self.assertIn("Hatal", metin)

    def test_trt_ayristir_goreli_link_onarimi(self):
        """TRT'nin mobil XML formatında göreli linklerin başına TRT_TABAN eklenmeli."""
        from bs4 import BeautifulSoup
        raw_xml = """<haberler>
            <haber>
                <haber_manset>TCMB konut kredisi faiz oranlarını güncelledi</haber_manset>
                <haber_link>haber/ekonomi/tcmb-faiz-karari-12345.html</haber_link>
                <haber_aciklama>Merkez Bankası konut ve tüketici kredilerine dair yeni tebliğ yayımladı.</haber_aciklama>
                <haber_tarihi>2026-09-21 14:30:00</haber_tarihi>
            </haber>
        </haberler>"""
        soup = BeautifulSoup(raw_xml, "html.parser")
        girdiler = soup.find_all("haber")
        sonuc = fetch_news._trt_ayristir(girdiler)

        self.assertEqual(len(sonuc), 1)
        self.assertEqual(sonuc[0]["baslik"], "TCMB konut kredisi faiz oranlarını güncelledi")
        self.assertTrue(sonuc[0]["url"].startswith("https://www.trthaber.com/haber/ekonomi/"))
        self.assertIn("Merkez Bankası", sonuc[0]["ozet"])

    def test_baslik_elenmeli_seo_ve_cop(self):
        """SEO çöpü, rüya tabiri, burç, asayiş ve magazin clickbait başlıkları elenmeli."""
        cop_basliklar = [
            "Rüyada yeni ev satın almak ne anlama gelir?",
            "Falda anahtar ve tapu görmek neye işarettir?",
            "Koç burcu bugün ne bekliyor? 21 Eylül burç yorumu",
            "Kim elendi? Survivor'da kim elendi son dakika",
            "Altın fiyatları uçuşa geçti! Çeyrek altın son durum",
            "Borsa günü rekor yükselişle tamamladı",
            "Dolar ve Euro kaç TL oldu? 21 Eylül canlı döviz",
            "Bugün hava durumu nasıl olacak?",
        ]
        for baslik in cop_basliklar:
            elendi = fetch_news.baslik_elenmeli(baslik)
            self.assertIsNotNone(elendi, f"Bu başlık elenmeliydi: {baslik}")

    def test_baslik_elenmeli_gercek_emlak_gecmeli(self):
        """Gerçek ve meşru emlak ve mevzuat başlıkları filtreden geçmeli (None dönmeli)."""
        mesru_basliklar = [
            "Yargıtay'dan kiracının tahliyesinde emsal karar: Noter ihtarı şart",
            "Silivri'de 1/5000'lik yeni imar planı askıya çıktı",
            "Hisseli tapularda şufa hakkı nasıl kullanılır? Süre ve şartlar",
            "Kentsel dönüşümde yarısı bizden desteği şartları genişletildi",
            "BDDK'dan ilk konut alacaklara yönelik yeni kredi düzenlemesi",
        ]
        for baslik in mesru_basliklar:
            elendi = fetch_news.baslik_elenmeli(baslik)
            self.assertIsNone(elendi, f"Meşru emlak haberi haksız yere elendi: {baslik}")

    def test_kati_kategori_filtresi_siyaset_ve_magazin_yasak(self):
        """Siyaset, cinayet, asayiş, futbol ve borsa spekülasyonu kesinlikle elenmeli."""
        yasakli_haberler = [
            ("CHP milletvekili seçim açıklaması yaptı", "Genel başkan seçim süreci hakkında konuştu."),
            ("İstanbul'da cinayet ve silahlı çatışma: 2 tutuklu", "Olay yeri inceleme ekipleri operasyon başlattı."),
            ("Fenerbahçe derbi hazırlıklarını tamamladı, transfer bitti", "Süper lig maç kadrosu belli oldu."),
            ("Ünlü şarkıcı ve oyuncu Bodrum'da tatilde", "Magazin dünyasının sevilen çifti görüntülendi."),
        ]
        for baslik, ozet in yasakli_haberler:
            d = haber_puanlama.degerlendir(baslik, ozet)
            self.assertFalse(d.gecti, f"Yasaklı haber süzgeçten geçmemeliydi: {baslik}")
            self.assertEqual(d.red_sebebi, "konu dışı")

    def test_kati_kategori_filtresi_emlak_ve_mevzuat_gecmeli(self):
        """1. ve 2. derece emlak haberleri doğru sütunlara atanmalı ve onay almalı."""
        emlak_haberleri = [
            ("Tapu devirlerinde yeni dönem: Hisseli arazide önalım hakkı", "Yargıtay emsal kararında şerh şartı aradı.", "S1"),
            ("Ev sahipleri ve kiracılar için tahliye taahhütnamesi kararı", "Kira artış oranları ve depozito iadesi.", "S2"),
            ("Silivri ve Çatalca'da tarla alacaklara kritik imar ve ifraz uyarısı", "Parselasyon ve kamulaştırma kararı Resmi Gazete'de.", "S3"),
            ("BDDK ve TCMB'den konut kredisi faiz oranları adımı", "Konut satışları ve metrekare rayiç değer artışı açıklandı.", "S4"),
        ]
        for baslik, ozet, beklenen_sutun in emlak_haberleri:
            d = haber_puanlama.degerlendir(baslik, ozet)
            self.assertTrue(d.gecti, f"Hakiki emlak haberi elenmemeliydi: {baslik} (Red: {d.red_sebebi})")
            self.assertEqual(d.sutun, beklenen_sutun, f"{baslik} için beklenen sütun {beklenen_sutun} idi ancak {d.sutun} geldi.")

    def test_slaytlari_uret_dailybrief_formati(self):
        """slaytlari_uret fonksiyonu format_turu='dailybrief' verildiğinde 2 slayt üretmeli."""
        with tempfile.TemporaryDirectory() as td:
            cikti_dir = Path(td)
            haber_verisi = {
                "manset": "YARGITAY'DAN KİRACI TAHLİYESİNDE EMSAL KARAR",
                "spot": "Tahliye taahhütnamesinde tarih sonradan doldurulmuşsa ispat yükü kiracıya aittir.",
                "kategori": "KİRACI VE EV SAHİBİ",
                "kaynak": "Yargıtay Hukuk Genel Kurulu",
                "format_turu": "dailybrief",
                "uzman_notu": "Kira kontratı yaparken tahliye taahhütnamesini kesinlikle boş imzalamayın.",
            }
            slaytlar = yeni_formatlar.slaytlari_uret(
                haber_verisi,
                cikti_dizini=cikti_dir,
                cikti_onek="test_haber_db",
                format_turu="dailybrief",
            )
            self.assertEqual(len(slaytlar), 2)
            self.assertTrue(slaytlar[0].exists())
            self.assertTrue(slaytlar[1].exists())
            self.assertGreater(slaytlar[0].stat().st_size, 50000)
            self.assertGreater(slaytlar[1].stat().st_size, 50000)


if __name__ == "__main__":
    unittest.main()
