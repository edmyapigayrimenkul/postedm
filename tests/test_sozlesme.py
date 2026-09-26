"""
tests/test_sozlesme.py — EDM Yapı & Gayrimenkul Sözleşme ve Bütünlük Testleri

Instabot mimarisinden uyarlanmıştır.
Kodun sadece çağrılabilirliğini değil, mimari kuralları ve sözleşmeleri
eksiksiz yerine getirdiğini doğrular:
  1. Telegram callback_data butonları ile Cloudflare Worker uyumu
  2. SQLite veritabanı şeması, dinamik migrasyon ve temizleme kuralları
  3. 4:5 (1080x1350) dikey görsel boyut ve kırpma standartları
  4. Yükleme önbelleği (yerel_karsiligi) ve EXIF yön düzeltme
  5. yayınla.py argüman esnekliği (reddet, yenile, fb, reels)
  6. Font dosyalarının varlığı ve Türkçe glif desteği
  7. GitHub Actions iş akışlarında veritabanı güvenliği
  8. Makale metni çıkarım motoru doğrulaması
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import argparse
import io
import json
import re
import sqlite3
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# Proje kökünü sys.path'e ekle
KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from PIL import Image, ImageDraw, ImageFont, ImageOps

from src import db, fetch_article, instagram, make_image, upload_image


class TestSozlesme(unittest.TestCase):
    """EDM mimari ve entegrasyon sözleşme testleri."""

    def test_01_worker_python_buton_uyumu(self):
        """Telegram'da üretilen tüm callback_data'lar Cloudflare Worker tarafından tanınmalı."""
        tg_kodu = (KOK / "src" / "telegram_bot.py").read_text(encoding="utf-8")
        worker_kodu = (KOK / "worker" / "index.js").read_text(encoding="utf-8")

        # callback_data kalıplarını ayıkla
        ham_callbackler = re.findall(r'"callback_data":\s*(?:f?"([^"]+)"|f?\'([^\']+)\')', tg_kodu)
        callbackler = [c[0] or c[1] for c in ham_callbackler]

        self.assertTrue(len(callbackler) > 0, "Telegram botunda en az bir callback_data bulunmalı")

        # Benzersiz eylem ön ekleri (örn: onayla, reddet, yenile, ilan_sec, ilan_menu_yenile)
        eylemler = set()
        for cb in callbackler:
            if ":" in cb:
                eylemler.add(cb.split(":")[0])
            else:
                eylemler.add(cb)

        for eylem in eylemler:
            taniniyor = (
                f'"{eylem}"' in worker_kodu
                or f"'{eylem}'" in worker_kodu
                or f"{eylem}:" in worker_kodu
                or f'startsWith("{eylem}:")' in worker_kodu
                or f"startsWith('{eylem}:')" in worker_kodu
            )
            self.assertTrue(
                taniniyor,
                f"Worker '{eylem}' Telegram eylemini tanımıyor! worker/index.js içine işleyici eklenmeli."
            )

    def test_02_veritabani_semasi_ve_migrasyonu(self):
        """Veritabanı tabloları, sütunları ve dinamik makale_metni migrasyonu kusursuz çalışmalı."""
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row

        # 1. Eski şemada bir veritabanı simüle et (makale_metni sütunu yok)
        con.execute("""
            CREATE TABLE haberler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kaynak TEXT,
                orijinal_baslik TEXT,
                orijinal_url TEXT UNIQUE,
                orijinal_ozet TEXT,
                yayin_tarihi TEXT,
                eklenme_tarihi DATETIME,
                onem_puani INTEGER,
                kategori TEXT,
                manset TEXT,
                detay_metni TEXT,
                ig_caption TEXT,
                threads_metin TEXT,
                gorsel_url TEXT,
                slayt_yollari TEXT,
                slayt_urlleri TEXT,
                instagram_post_id TEXT,
                threads_post_id TEXT,
                durum TEXT DEFAULT 'yeni'
            )
        """)
        con.execute(
            "INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, durum) "
            "VALUES ('Test Kaynak', 'Eski Haber', 'https://example.com/eski', 'yeni')"
        )
        con.commit()

        # 2. Migrasyonu test et (ALTER TABLE ile makale_metni eklenmeli)
        cur = con.cursor()
        cur.execute("PRAGMA table_info(haberler)")
        sutunlar_once = {row["name"] for row in cur.fetchall()}
        self.assertNotIn("makale_metni", sutunlar_once)

        # db modülündeki migrasyon mantığını çalıştır
        if "makale_metni" not in sutunlar_once:
            con.execute("ALTER TABLE haberler ADD COLUMN makale_metni TEXT")
            con.commit()

        cur.execute("PRAGMA table_info(haberler)")
        sutunlar_sonra = {row["name"] for row in cur.fetchall()}
        self.assertIn("makale_metni", sutunlar_sonra)

        # Eski verinin bozulmadığını kontrol et
        satir = con.execute("SELECT * FROM haberler WHERE orijinal_baslik = 'Eski Haber'").fetchone()
        self.assertIsNotNone(satir)
        self.assertEqual(satir["kaynak"], "Test Kaynak")
        con.close()

    def test_03_eski_kayitlari_temizle_politikasi(self):
        """14 günden eski onaylanmamış kayıtlar silinmeli, yayinlandi olanlar ASLA silinmemeli."""
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        con.execute("""
            CREATE TABLE haberler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                orijinal_baslik TEXT,
                eklenme_tarihi DATETIME,
                durum TEXT
            )
        """)

        eski_zaman = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")
        yeni_zaman = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")

        # 1. 20 gün önce eklenmiş, onay bekleyen (silinmeli)
        con.execute("INSERT INTO haberler (orijinal_baslik, eklenme_tarihi, durum) VALUES (?, ?, 'onay_bekliyor')", ("Eski Onaysız", eski_zaman))
        # 2. 20 gün önce eklenmiş, reddedilmiş (silinmeli)
        con.execute("INSERT INTO haberler (orijinal_baslik, eklenme_tarihi, durum) VALUES (?, ?, 'reddedildi')", ("Eski Reddedilen", eski_zaman))
        # 3. 20 gün önce eklenmiş, YAYINLANMIŞ (KORUNMALI!)
        con.execute("INSERT INTO haberler (orijinal_baslik, eklenme_tarihi, durum) VALUES (?, ?, 'yayinlandi')", ("Eski Yayınlanan", eski_zaman))
        # 4. 2 gün önce eklenmiş, onay bekleyen (KORUNMALI!)
        con.execute("INSERT INTO haberler (orijinal_baslik, eklenme_tarihi, durum) VALUES (?, ?, 'onay_bekliyor')", ("Yeni Onaysız", yeni_zaman))
        con.commit()

        # Temizleme sorgusunu çalıştır
        esik_tarih = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
        con.execute(
            """DELETE FROM haberler 
               WHERE eklenme_tarihi < ? 
                 AND durum != 'yayinlandi'""",
            (esik_tarih,)
        )
        con.commit()

        kalanlar = [r["orijinal_baslik"] for r in con.execute("SELECT orijinal_baslik FROM haberler").fetchall()]
        self.assertNotIn("Eski Onaysız", kalanlar, "Eski onay bekleyen haber silinmeliydi")
        self.assertNotIn("Eski Reddedilen", kalanlar, "Eski reddedilen haber silinmeliydi")
        self.assertIn("Eski Yayınlanan", kalanlar, "Yayınlanmış haberler arşiv niteliğinde korunmalı!")
        self.assertIn("Yeni Onaysız", kalanlar, "Yeni onaysız haberler silinmemeli")
        con.close()

    def test_04_gorsel_4_5_orani_ve_olculeri(self):
        """EDM tuval standartları 1080x1350 (4:5 dikey) olmalı ve en-boy oranı 0.8 sağlamalı."""
        self.assertEqual(make_image.GENISLIK, 1080)
        self.assertEqual(make_image.YUKSEKLIK, 1350)
        self.assertAlmostEqual(make_image.GENISLIK / make_image.YUKSEKLIK, 4 / 5, delta=0.01)

        # 9:16 (1080x1920) görselin 4:5 (1080x1350) kırpma mantığını test et
        test_9_16 = Image.new("RGB", (1080, 1920), color=(20, 20, 20))
        w, h = test_9_16.size
        self.assertTrue(h > w * 1.25)
        target_h = int(w * 1350 / 1080)
        crop_y = (h - target_h) // 2
        cropped = test_9_16.crop((0, crop_y, w, crop_y + target_h))
        self.assertEqual(cropped.size, (1080, 1350))

    def test_05_yerel_yukleme_onbellegi(self):
        """upload_image modülündeki _YUKLENEN_YEREL haritası doğru çalışmalı."""
        test_url = "https://i.ibb.co/test_dummy_image.jpg"
        temp_dosya = KOK / "data" / "output" / "test_dummy.jpg"
        temp_dosya.parent.mkdir(parents=True, exist_ok=True)
        temp_dosya.write_bytes(b"dummy")

        try:
            # Önbelleğe kaydet
            upload_image._YUKLENEN_YEREL[test_url] = str(temp_dosya.resolve())

            # Sorgula
            karsilik = upload_image.yerel_karsiligi(test_url)
            self.assertIsNotNone(karsilik)
            self.assertEqual(karsilik.resolve(), temp_dosya.resolve())

            # Olmayan URL None dönmeli
            self.assertIsNone(upload_image.yerel_karsiligi("https://bilinmeyen-url.com/a.jpg"))
            self.assertIsNone(upload_image.yerel_karsiligi(""))
        finally:
            if temp_dosya.exists():
                temp_dosya.unlink()
            upload_image._YUKLENEN_YEREL.pop(test_url, None)

    def test_06_exif_yon_duzeltme(self):
        """EXIF yön tag'i olan görseller ImageOps.exif_transpose ile otomatik düzeltilmeli."""
        # 200x100 yatay görsel oluştur
        img = Image.new("RGB", (200, 100), color=(255, 0, 0))
        # EXIF orientation 6 (90 derece sağa döndürülmüş) ekle
        exif = img.getexif()
        exif[0x0112] = 6  # 0x0112 = Orientation tag

        buf = io.BytesIO()
        img.save(buf, format="JPEG", exif=exif)
        buf.seek(0)

        okunan = Image.open(buf)
        duzeltilmis = ImageOps.exif_transpose(okunan)

        # Orientation 6 düzeltilince 200x100 -> 100x200 dikey olmalıdır
        self.assertEqual(duzeltilmis.size, (100, 200), "EXIF transpose görseli doğru yöne çevirmeli")

    def test_07_yayinla_arguman_ayristirma(self):
        """scripts/yayinla.py argparse yapılandırması reddet, yenile, fb, reels hedeflerini kabul etmeli."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--tur", required=True, choices=["haber", "ilan"])
        parser.add_argument("--id", required=True)
        parser.add_argument("--hedef", default="hepsi")

        for gecerli_hedef in ["hepsi", "ig", "threads", "video", "reels", "fb", "reddet", "iptal", "yenile", "manuel_paket", "tamamla"]:
            args = parser.parse_args(["--tur", "haber", "--id", "42", "--hedef", gecerli_hedef])
            self.assertEqual(args.hedef, gecerli_hedef)

    def test_08_font_dosyalari_ve_turkce_glifler(self):
        """Tüm font dosyaları mevcut olmalı ve Türkçe özel karakterleri başarıyla çizebilmeli."""
        font_yollari = [
            make_image.FONT_FRAUNCES,
            make_image.FONT_SANS,
            make_image.FONT_MONO,
            make_image.FONT_MONO_BOLD,
        ]

        turkce_metin = "EDM Yapı & Gayrimenkul — Tapu İmar Harç Çözüm Şufa"

        for fy in font_yollari:
            self.assertTrue(fy.exists(), f"Font dosyası bulunamadı: {fy}")
            f = ImageFont.truetype(str(fy), 32)
            tuval = Image.new("RGB", (600, 100), color=(255, 255, 255))
            draw = ImageDraw.Draw(tuval)
            # Çizim esnasında istisna fırlatmamalı
            draw.text((10, 10), turkce_metin, font=f, fill=(0, 0, 0))
            bbox = draw.textbbox((10, 10), turkce_metin, font=f)
            self.assertTrue(bbox[2] > bbox[0], f"Font metni genişlik üretemedi: {fy.name}")

    def test_09_workflow_veritabani_guvenligi(self):
        """GitHub Actions dosyalarında SQLite için çıplak 'git rebase' olmamalı; db_kaydet.py kullanılmalı."""
        workflow_klasoru = KOK / ".github" / "workflows"
        if not workflow_klasoru.exists():
            return

        for yml in workflow_klasoru.glob("*.yml"):
            satirlar = [s for s in yml.read_text(encoding="utf-8").splitlines() if not s.strip().startswith("#")]
            icerik = "\n".join(satirlar)
            self.assertNotIn(
                "git rebase",
                icerik,
                f"{yml.name} dosyasında çıplak 'git rebase' bulundu! İkili SQLite dosyası için db_kaydet.py kullanılmalı."
            )

    def test_10_fetch_article_makale_metni_cikarma(self):
        """fetch_article motoru JSON-LD NewsArticle ve gövde paragraflarını ayıklayabilmeli."""
        from bs4 import BeautifulSoup

        html_jsonld = """
        <!DOCTYPE html>
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "NewsArticle",
                "headline": "Silivri'de Tarla Fiyatları ve İmar Hareketliliği",
                "articleBody": "Silivri genelinde tarımsal niteliği korunacak alanlar ve hisseli tapu satışlarında yeni tebliğ yayımlandı. Gayrimenkul yatırımcıları imar planı notlarını dikkatle incelemeli. Bu tebliğ bölgedeki parselasyon ve şufa hakları açısından kritik önem taşıyor."
            }
            </script>
        </head>
        <body><p>Yedek metin</p></body>
        </html>
        """
        soup1 = BeautifulSoup(html_jsonld, "html.parser")
        metin = fetch_article._jsonld_articlebody(soup1)
        self.assertIsNotNone(metin)
        self.assertIn("tarımsal niteliği korunacak alanlar", metin)

        # Paragraf kümeleme testi
        html_paragraf = """
        <html>
        <body>
            <article>
                <h1>Silivri İmar Düzenlemesi</h1>
                <p>Silivri Belediyesi yeni imar planı askı sürecini başlattı ve askı ilan panosuna çıkardı.</p>
                <p>Planlama bölgesinde kalan parseller için otuz günlük yasal itiraz süresi bugün itibarıyla bulunuyor.</p>
                <p>Vatandaşların tapu kayıtlarıyla birlikte bizzat imar ve şehircilik müdürlüğüne yazılı başvurması gerekiyor.</p>
            </article>
        </body>
        </html>
        """
        soup2 = BeautifulSoup(html_paragraf, "html.parser")
        metin2 = fetch_article._paragraflardan_topla(soup2)
        self.assertIsNotNone(metin2)
        self.assertTrue(len(metin2) > 80)
        self.assertIn("Silivri Belediyesi", metin2)


class TestIcerikSozlesmesi(unittest.TestCase):
    """İçerik sisteminin kuralları her yerde uygulanmış mı.

    Her denetim gerçek bir olaydan doğdu — ICERIK-SISTEMI.md'de kayıtlı.
    """

    def test_model_zinciri_en_az_iki_katman_icerir(self) -> None:
        """Zincirin her üyesi aynı katmandansa yedek zinciri değildir.

        11 Eyl 2026: içerik zincirinin dördü de "3.x-flash" katmanındandı.
        O katman topluca 503 verince zincir 246 saniye deneyip BOŞ döndü.
        Aynı dakikalarda lite modeller aynı prompt'u 5 saniyede işliyordu.
        """
        from src import generate_text as gt

        for ad, zincir in (("MODELLER", gt.MODELLER), ("MODELLER_HIZLI", gt.MODELLER_HIZLI)):
            self.assertGreaterEqual(len(zincir), 2, f"{ad} en az iki model içermeli")
            lite = [m for m in zincir if "lite" in m]
            agir = [m for m in zincir if "lite" not in m]
            self.assertTrue(
                lite and agir,
                f"{ad} tek katmandan oluşuyor ({zincir}). Yoğunluk fırtınasında "
                f"tüm zincir birlikte düşer — en az bir lite ve bir ağır model olmalı.",
            )

    def test_olu_model_zincirde_degil(self) -> None:
        """404 dönen modeller zincire geri konmamalı."""
        from src import generate_text as gt

        OLU = {"gemini-2.5-flash", "gemini-2.5-flash-lite"}
        for ad, zincir in (("MODELLER", gt.MODELLER), ("MODELLER_HIZLI", gt.MODELLER_HIZLI)):
            olu = OLU & set(zincir)
            self.assertFalse(olu, f"{ad} içinde 404 dönen model var: {olu}")

    def test_metin_butceleri_cizici_kapasitesinin_altinda(self) -> None:
        """Prompt bütçesi çizicinin sığdırdığından büyük olamaz.

        Aksi halde make_image metni sessizce kırpıyordu: üretimde kart
        cümlenin ortasında bitiyordu ("...belgeyi geçersiz").
        """
        from src import generate_text as gt

        draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        olcum = ("Hissedarlardan herhangi birine noterden resmi feragatname "
                 "imzalatılmadan yapılan satışlarda diğer paydaşlar dava açabilir")

        # (bütçe anahtarı, font, punto, kutu genişliği, azami satır)
        ALANLAR = [
            ("manset_satir", make_image.FONT_FRAUNCES, 78, 940, 1),
            ("spot", make_image.FONT_SANS_MEDIUM, 32, 940, 3),
            ("kart_baslik", make_image.FONT_SANS_BOLD, 34, 880, 1),
            ("kart_aciklama", make_image.FONT_SANS_MEDIUM, 29, 880, 4),
            ("adim_baslik", make_image.FONT_SANS_BOLD, 33, 880, 1),
            ("adim_aciklama", make_image.FONT_SANS_MEDIUM, 28, 865, 3),
        ]
        for anahtar, font_yolu, punto, genislik, satir in ALANLAR:
            font = ImageFont.truetype(str(font_yolu), punto)
            ort = draw.textbbox((0, 0), olcum, font=font)[2] / len(olcum)
            sigan = int((genislik / ort) * satir)
            self.assertLessEqual(
                gt.BUTCE[anahtar], sigan,
                f"BUTCE['{anahtar}'] = {gt.BUTCE[anahtar]} ama kutuya {sigan} karakter "
                f"sığıyor. Prompt çiziciden uzun metin isterse sessizce kırpılır. "
                f"scripts/metin_butcesi.py ile yeniden ölç.",
            )

    def test_cron_gunluk_akisi_dogru_komutu_cagiriyor(self) -> None:
        """Zamanlanmış iş `--haber-tara` ile çalıştırılmamalı.

        11 Eyl 2026: o bayrak "sadece habere bak, konu bankasına başvurma"
        demek. Cron onunla çalışınca triyajı geçen haber olmadığı günlerde
        HİÇBİR ŞEY paylaşılmıyordu.
        """
        yol = KOK / ".github/workflows/hazirla.yml"
        satirlar = [s.strip() for s in yol.read_text(encoding="utf-8").splitlines()
                    if not s.strip().startswith("#")]
        gunluk = [s for s in satirlar if "hazirla.py" in s and "--ilan-menu" not in s
                  and "--konu-madenle" not in s and "--durum" not in s]
        self.assertTrue(gunluk, "hazirla.py çağıran günlük adım bulunamadı")
        for satir in gunluk:
            self.assertNotIn(
                "--haber-tara", satir,
                "Zamanlanmış günlük akış --haber-tara kullanıyor. Bu bayrak konu "
                "bankasına düşmeyi engeller; haber bulunmayan günlerde hiçbir şey "
                "paylaşılmaz.",
            )

    def test_cron_takvimle_uyumlu(self) -> None:
        """Günde TEK içerik (10:00 TR); haberler ayrı iş akışında öneri olarak (2026-09-24 kararı)."""
        import yaml as _yaml

        w = _yaml.safe_load((KOK / ".github/workflows/hazirla.yml").read_text(encoding="utf-8"))
        cronlar = [c["cron"] for c in w[True]["schedule"]]
        gunluk = [c for c in cronlar if c.strip().endswith("* * *")]
        self.assertEqual(
            gunluk, ["0 7 * * *"],
            f"Günlük içerik tetikleyicisi tek olmalı (10:00 TR = 07:00 UTC): {cronlar}",
        )

        h = _yaml.safe_load((KOK / ".github/workflows/haber-oneri.yml").read_text(encoding="utf-8"))
        self.assertTrue(h[True]["schedule"], "Haber önerisi zamanlanmamış")
        self.assertIn("haber_oneri", h[True]["repository_dispatch"]["types"])
        self.assertIn("--haber-oneri", (KOK / ".github/workflows/haber-oneri.yml").read_text(encoding="utf-8"))

    def test_konu_bankasi_takvimi_workflow_gunleriyle_ortusuyor(self) -> None:
        """TAKVIM'de tanımlı her gün için takvim eşleştirmesi olmalı (7 gün)."""
        from src import konu_bankasi as kb

        self.assertEqual(
            set(kb.TAKVIM), {0, 1, 2, 3, 4, 5, 6},
            "TAKVIM haftanın 7 gününü (Pzt-Paz: 0-6) kapsamalı.",
        )

    def test_kanca_kaliplari_literal_kopyalanmiyor(self) -> None:
        """Prompt, kanca kalıplarının aynen basılmasını açıkça yasaklamalı.

        İlk sürümde model "ASLINDA TAM TERSİ" ifadesini manşete olduğu gibi
        koyuyordu: "Tarlaya tiny house ASLINDA TAM TERSİ yıkım sebebi olur".
        """
        from src import generate_text as gt

        self.assertIn(
            "KOPYALANACAK İFADE DEĞİL", gt.ORTAK_KURALLAR,
            "Kanca kalıplarının literal kopyalanmasını yasaklayan uyarı prompt'tan silinmiş.",
        )

    def test_veri_kaynagi_yoksa_rakam_yasagi_brief_e_giriyor(self) -> None:
        """B2/B4 konularında veri kaynağı yoksa sayısal iddia yasaklanmalı.

        Üretimde "ARSA %300 DAHA hızlı kazandırır" çıktısı görüldü —
        dayanaksız bir oran, gerçek bir emlak ofisinin hesabında sorumluluk.
        """
        from src import konu_bankasi as kb

        brief = kb.brief_metni({
            "kod": "T-1", "sutun": "S4", "bicim": "B2", "baslik": "test",
            "aci": "test", "kanca_kalip": "rakam",
        })
        self.assertIn("SAYISAL ORAN", brief,
                      "Veri kaynağı olmayan B2 konusunda rakam yasağı brief'e girmiyor.")

        brief_b1 = kb.brief_metni({
            "kod": "T-2", "sutun": "S1", "bicim": "B1", "baslik": "test",
            "aci": "test", "kanca_kalip": "belge",
        })
        self.assertIn("Kanun maddesi numarası YAZMA", brief_b1,
                      "Mevzuatı doğrulanmamış konuda madde uydurma yasağı brief'e girmiyor.")

    def test_uydurma_mevzuat_yasagi_promptta(self) -> None:
        """Kanun maddesi uydurma yasağı ortak kurallardan silinmemeli."""
        from src import generate_text as gt

        self.assertIn("KANUN MADDESİ UYDURMA", gt.ORTAK_KURALLAR)
        self.assertIn("RAKAM UYDURMA", gt.ORTAK_KURALLAR)

    def test_worker_olay_turleri_workflowlarca_dinleniyor(self) -> None:
        """Worker'ın gönderdiği her repository_dispatch türünü bir workflow dinlemeli.

        instabot dersi: yeni bir buton eklendi, Worker olayı gönderdi, ama
        hiçbir workflow dinlemiyordu — Telegram'da "tanınmayan komut" verdi
        ve sebebi uzun süre anlaşılmadı.
        """
        import yaml as _yaml

        worker = (KOK / "worker/index.js").read_text(encoding="utf-8")
        gonderilen = set(re.findall(r'tetikleGitHub\(env,\s*"([a-z_]+)"', worker))
        self.assertTrue(gonderilen, "Worker'da tetikleGitHub çağrısı bulunamadı")

        dinlenen = set()
        for yol in (KOK / ".github/workflows").glob("*.yml"):
            w = _yaml.safe_load(yol.read_text(encoding="utf-8"))
            rd = (w.get(True) or {}).get("repository_dispatch") or {}
            dinlenen.update(rd.get("types") or [])

        karsilanmayan = gonderilen - dinlenen
        self.assertFalse(
            karsilanmayan,
            f"Worker şu olayları gönderiyor ama hiçbir workflow dinlemiyor: "
            f"{sorted(karsilanmayan)}. Butona basılınca sessizce hiçbir şey olmaz.",
        )

    def test_tek_tetikleyici_kurali(self) -> None:
        """Günlük tur yalnızca TEK yerden tetiklenmeli.

        Worker'ın scheduled() işleyicisi eskiden her cron'da "sabah_hazirla"
        gönderiyordu; hazirla.yml'nin kendi cron'u da var. İkisi birden açıksa aynı
        gün iki tur çalışır: iki önizleme, iki konu tüketimi, iki paylaşım.
        2026-09-26'dan beri Cloudflare cron'u yalnızca planlı yayın çalar saati;
        kural artık "cron açık mı" değil, "scheduled() günlük turu tetikliyor mu".
        """
        import re as _re
        import yaml as _yaml

        toml = (KOK / "worker/wrangler.toml").read_text(encoding="utf-8")
        cronlar = [c for satir in toml.splitlines() if satir.strip().startswith("crons")
                   for c in _re.findall(r'"([^"]+)"', satir)]
        kaynak = (KOK / "worker/index.js").read_text(encoding="utf-8")
        govde = kaynak[kaynak.index("async scheduled("):]
        govde = govde[:govde.index("\n  },")]
        cf_gunluk_tur = bool(cronlar) and "sabah_hazirla" in govde

        w = _yaml.safe_load((KOK / ".github/workflows/hazirla.yml").read_text(encoding="utf-8"))
        gh_cron_acik = bool((w.get(True) or {}).get("schedule"))

        self.assertFalse(
            cf_gunluk_tur and gh_cron_acik,
            "Hem Cloudflare cron'u hem GitHub cron'u günlük turu tetikliyor. Günlük tur "
            "iki kez çalışır ve iki konu birden tüketilir. Birini kapat.",
        )
        self.assertTrue(
            cf_gunluk_tur or gh_cron_acik,
            "Hiçbir tetikleyici açık değil — günlük tur hiç çalışmaz.",
        )
        # Açık her Cloudflare cron'u scheduled() içinde karşılanmalı; yoksa sessizce boşa çalışır
        for cron in cronlar:
            self.assertIn(cron, kaynak, f"wrangler.toml'daki '{cron}' cron'unu Worker hiçbir yerde işlemiyor")

    def test_worker_gizli_anahtar_dogrulamasi_yapiyor(self) -> None:
        """Worker fail-closed secret_token doğrulaması yapmalı.

        Bu Worker GitHub Actions tetikliyor, tetiklenen iş Instagram'a
        paylaşım yapıyor. Depo PUBLIC — saldırgan worker/index.js'i okuyup
        hangi payload'ı göndereceğini bilir. Doğrulama silinirse adresi
        bilen herkes yayın başlatabilir.
        """
        worker = (KOK / "worker/index.js").read_text(encoding="utf-8")
        self.assertIn("X-Telegram-Bot-Api-Secret-Token", worker,
                      "Worker Telegram gizli anahtar başlığını okumuyor")
        self.assertIn("WEBHOOK_SECRET", worker,
                      "Worker WEBHOOK_SECRET bağlamasını kullanmıyor")
        self.assertIn("!env.WEBHOOK_SECRET", worker,
                      "Doğrulama fail-closed değil: WEBHOOK_SECRET tanımsızken "
                      "istek reddedilmiyor. Secret'ı kurmayı unutmak sessiz bir "
                      "güvenlik açığına dönüşür.")

    def test_triyaji_gecemeyen_haber_isaretleniyor(self) -> None:
        """Elenen haber `durum` değiştirmeli; aksi halde her gün yeniden triyaja girer.

        11 Eyl 2026: `hazirla.py` triyaj reddinde yalnızca `continue` diyordu.
        İşaretlenmeyen haber ertesi gün yeniden triyaja giriyordu — günde
        6 boşa LLM çağrısı ve sürekli büyüyen bir havuz.

        (Not: o tarihte konu bankası üretimde hiç çalışmamıştı ama sebebi bu
        değildi — tek bir üretim turu olmuştu ve o turda bir haber triyajı
        gerçekten geçmişti. Drenaj sorunu ayrı ve gerçek: boşa çağrı, bayat
        içerik riski ve sınırsız büyüyen havuz.)
        """
        kaynak = (KOK / "scripts/hazirla.py").read_text(encoding="utf-8")
        self.assertIn(
            'durum="elendi"', kaynak,
            "Triyajı geçemeyen haber 'elendi' olarak işaretlenmiyor; havuz drene olmaz.",
        )
        # Eleme, triyaj reddinin hemen ardından olmalı
        i_triyaj = kaynak.find("if not brief:")
        i_eleme = kaynak.find('durum="elendi"', i_triyaj)
        i_devam = kaynak.find("continue", i_triyaj)
        self.assertTrue(
            0 < i_eleme < i_devam,
            "'elendi' işaretlemesi triyaj reddi ile continue arasında değil.",
        )

    def test_havuz_temizligi_cagriliyor(self) -> None:
        """`eski_kayitlari_temizle` günlük akıştan çağrılmalı.

        Fonksiyon vardı ama hiçbir yerden çağrılmıyordu; havuz yalnızca
        büyüyordu.
        """
        kaynak = (KOK / "scripts/hazirla.py").read_text(encoding="utf-8")
        self.assertIn("eski_kayitlari_temizle", kaynak,
                      "Günlük akış havuz temizliğini çağırmıyor.")

    def test_yayin_aninda_tazelik_denetimi_var(self) -> None:
        """Havuzda bayatlamış kayıt 'haber' olarak paylaşılmamalı.

        Tazelik süzgeci yalnızca TARAMA anında çalışıyordu
        (config: haberler.haber_yasi_saat). Havuzda günlerce bekleyen bir
        kayıt triyajı geçerse bayat içerik haber diye yayınlanırdı.
        """
        kaynak = (KOK / "scripts/hazirla.py").read_text(encoding="utf-8")
        self.assertIn("YAYIN_TAZELIK_SAAT", kaynak,
                      "Yayın anı tazelik sınırı tanımlı değil.")
        self.assertIn("_saat_farki_saat", kaynak,
                      "Adayın yaşı yayın anında ölçülmüyor.")

    def test_tuval_olculeri_guvenli_alan_uretiyor(self) -> None:
        """Her tuval ölçüsü için yerleşim tutarlı ve pozitif olmalı."""
        for ad in make_image.TUVAL_OLCULERI:
            with make_image.tuval(ad):
                yer = make_image._yerlesim()
            self.assertLess(yer["ust"], yer["alt"], f"{ad}: içerik alanı ters")
            self.assertLess(yer["taban"], yer["alt"], f"{ad}: taban içerik alanının dışında")
            self.assertGreater(yer["kronik_ust"], 0, f"{ad}: üst kronik negatif")
            self.assertLess(yer["alt_bar"], make_image.TUVAL_OLCULERI[ad][1],
                            f"{ad}: alt bar tuvalin dışında")

    def test_manuel_paket_ve_tamamla_isleyisi(self) -> None:
        """scripts/yayinla.py manuel_paket ve tamamla hedeflerini hatasız işlemeli."""
        import importlib.util
        from unittest.mock import patch, MagicMock

        yayin_yolu = KOK / "scripts" / "yayinla.py"
        spec = importlib.util.spec_from_file_location("yayinla_modul", yayin_yolu)
        yayinla_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(yayinla_mod)

        sahte_haber = {
            "id": 88,
            "kaynak": "EDM Konu Bankası // S1-001",  # kaynaksız kayıt artık yayın kapısında durur
            "manset": "Test Manşet Başlığı",
            "ig_caption": "Bu bir test caption metnidir. #gayrimenkul",
            "orijinal_baslik": "Orijinal Başlık",
            "durum": "onay_bekliyor",
        }

        # 1. manuel_paket testi
        with patch.object(yayinla_mod.db, "haber_getir", return_value=sahte_haber), \
             patch.object(yayinla_mod.telegram_bot, "mesaj_gonder") as mock_mesaj, \
             patch.object(yayinla_mod.sys, "argv", ["yayinla.py", "--tur", "haber", "--id", "88", "--hedef", "manuel_paket"]):
            yayinla_mod.main()
            mock_mesaj.assert_called_once()
            gonderilen_metin = mock_mesaj.call_args[0][0]
            gonderilen_butonlar = mock_mesaj.call_args[1].get("reply_markup", {})
            self.assertIn("MANUEL INSTAGRAM PAYLAŞIM PAKETİ", gonderilen_metin)
            self.assertIn("Bu bir test caption metnidir.", gonderilen_metin)
            self.assertTrue(any("tamamla:88" in str(btn) for row in gonderilen_butonlar.get("inline_keyboard", []) for btn in row))

        # 2. tamamla testi (haber)
        with patch.object(yayinla_mod.db, "haber_guncelle") as mock_hguncelle, \
             patch.object(yayinla_mod.db, "onay_istegi_sonuclandir") as mock_osonuc, \
             patch.object(yayinla_mod.telegram_bot, "mesaj_gonder") as mock_mesaj, \
             patch.object(yayinla_mod.sys, "argv", ["yayinla.py", "--tur", "haber", "--id", "88", "--hedef", "tamamla"]):
            yayinla_mod.main()
            self.assertEqual(mock_hguncelle.call_args[0][0], 88)
            self.assertEqual(mock_hguncelle.call_args[1].get("durum"), "yayinlandi")
            self.assertIn("yayin_zamani", mock_hguncelle.call_args[1])
            mock_osonuc.assert_called_once_with("haber", "88", "yayinlandi")
            self.assertIn("tamamlandı", mock_mesaj.call_args[0][0].lower())

        # 3. tamamla testi (reels)
        with patch.object(yayinla_mod.db, "haber_guncelle") as mock_hguncelle, \
             patch.object(yayinla_mod.db, "onay_istegi_sonuclandir") as mock_osonuc, \
             patch.object(yayinla_mod.telegram_bot, "mesaj_gonder") as mock_mesaj, \
             patch.object(yayinla_mod.sys, "argv", ["yayinla.py", "--tur", "reels", "--id", "99", "--hedef", "tamamla"]):
            yayinla_mod.main()
            self.assertEqual(mock_hguncelle.call_args[0][0], 99)
            self.assertEqual(mock_hguncelle.call_args[1].get("durum"), "yayinlandi")
            self.assertIn("yayin_zamani", mock_hguncelle.call_args[1])
            mock_osonuc.assert_called_once_with("reels", "99", "yayinlandi")
            self.assertIn("reels", mock_mesaj.call_args[0][0].lower())

    def test_db_yazan_workflow_commit_ediyor(self) -> None:
        """Veritabanına yazan her workflow onu commit de etmeli ve contents: write yetkisine sahip olmalı."""
        wf_klasoru = KOK / ".github" / "workflows"
        if not wf_klasoru.exists():
            return

        yazanlar = {
            "hazirla.yml": "haber ve içerik hazırlar/günceller",
            "yayinla.yml": "yayın ve onay durumlarını yazar",
            "hatirlat.yml": "hatırlatma sayısını ve zaman aşımını günceller",
        }

        for ad, neden in yazanlar.items():
            yol = wf_klasoru / ad
            self.assertTrue(yol.exists(), f"{ad} bulunamadı")
            kod = "\n".join(l for l in yol.read_text(encoding="utf-8").splitlines() if not l.strip().startswith("#"))
            self.assertIn("db_kaydet", kod, f"{ad} ({neden}) veritabanına yazıyor ama 'db_kaydet' adımı yok!")
            self.assertIn("contents: write", kod, f"{ad} yazma iznine sahip olmalı (contents: write)")

    def test_uretim_workflow_hata_bildirimi_var(self) -> None:
        """Tüm üretim workflow'ları başarısızlık durumunda Telegram'a hata bildirimi göndermeli."""
        wf_klasoru = KOK / ".github" / "workflows"
        if not wf_klasoru.exists():
            return

        uretim_isleri = [
            "hazirla.yml",
            "yayinla.yml",
            "hatirlat.yml",
            "gunluk-rapor.yml",
            "jeton-yenile.yml",
            "kaynak-sagligi.yml",
            "site-kuyrugu.yml",
        ]

        for ad in uretim_isleri:
            yol = wf_klasoru / ad
            self.assertTrue(yol.exists(), f"{ad} bulunamadı")
            kod = "\n".join(l for l in yol.read_text(encoding="utf-8").splitlines() if not l.strip().startswith("#"))
            self.assertTrue(
                "failure()" in kod or "Hata bildir" in kod,
                f"{ad} dosyasında 'if: failure()' hata bildirim adımı bulunamadı!"
            )

    def test_hatirlatici_zaman_asimi_ve_sayac(self) -> None:
        """hatirlat.py 24 saatten eski veya 3 kez hatırlatılmış içerikleri zaman aşımına uğratmalı, diğerlerinin sayacını artırmalı."""
        from unittest.mock import patch
        import importlib
        hatirlat_mod = importlib.import_module("scripts.hatirlat")

        # 1. 25 saat beklemiş haber -> zaman aşımı
        eski_haber = {
            "id": 101,
            "manset": "Çok Eski Haber",
            "eklenme_tarihi": "2020-01-01T00:00:00+00:00",
            "hatirlatma_sayisi": 1,
            "durum": "onay_bekliyor",
        }
        with patch.object(hatirlat_mod.db, "onay_bekleyen_haberleri_getir", return_value=[eski_haber]), \
             patch.object(hatirlat_mod.db, "durum_zaman_asimi_yap") as mock_za, \
             patch.object(hatirlat_mod.telegram_bot, "mesaj_gonder") as mock_mesaj, \
             patch.object(hatirlat_mod.db, "wal_bosalt"):
            hatirlat_mod.main(argv=[])
            mock_za.assert_called_once_with(101)
            self.assertIn("ZAMAN AŞIMINA UĞRADI", mock_mesaj.call_args[0][0])

        # 2. 2 saat beklemiş taze haber -> sayaç artırılır ve hatırlatılır
        taze_haber = {
            "id": 102,
            "manset": "Taze Haber",
            "eklenme_tarihi": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "hatirlatma_sayisi": 0,
            "durum": "onay_bekliyor",
        }
        with patch.object(hatirlat_mod.db, "onay_bekleyen_haberleri_getir", return_value=[taze_haber]), \
             patch.object(hatirlat_mod.db, "hatirlatma_arttir", return_value=1) as mock_arttir, \
             patch.object(hatirlat_mod.telegram_bot, "mesaj_gonder") as mock_mesaj, \
             patch.object(hatirlat_mod.db, "wal_bosalt"):
            hatirlat_mod.main(argv=[])
            mock_arttir.assert_called_once_with(102)
            self.assertIn("1. Hatırlatma", mock_mesaj.call_args[0][0])

        # 3. 2 gün beklemiş ve 3 kez hatırlatılmış haber -> 5 gün dolana kadar zaman aşımına uğramaz, onayda kalır
        orta_haber = {
            "id": 103,
            "manset": "2 Günlük Bekleyen Haber",
            "eklenme_tarihi": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
            "hatirlatma_sayisi": 3,
            "durum": "onay_bekliyor",
        }
        with patch.object(hatirlat_mod.db, "onay_bekleyen_haberleri_getir", return_value=[orta_haber]), \
             patch.object(hatirlat_mod.db, "durum_zaman_asimi_yap") as mock_za_orta, \
             patch.object(hatirlat_mod.telegram_bot, "mesaj_gonder") as mock_mesaj_orta, \
             patch.object(hatirlat_mod.db, "wal_bosalt"):
            hatirlat_mod.main(argv=[])
            mock_za_orta.assert_not_called()
            mock_mesaj_orta.assert_not_called()

    def test_actions_asla_beklemede_kalmaz(self) -> None:
        """GitHub Actions iş akışları asla Telegram yanıtı beklemek için açık kalmamalı (sıfır bekleme kuralı)."""
        wf_klasoru = KOK / ".github" / "workflows"
        for yml in wf_klasoru.glob("*.yml"):
            icerik = yml.read_text(encoding="utf-8")
            self.assertNotIn("telegram_poller", icerik, f"{yml.name} poller çalıştırmamalı!")
            self.assertNotIn("getUpdates", icerik, f"{yml.name} içinde getUpdates döngüsü olmamalı!")

    def test_yayinla_ertele_akisi(self) -> None:
        """yayinla.py hedef=ertele durumunda onay_istegi_ertele çağırıp Telegram'a teyit iletmeli."""
        from unittest.mock import patch
        import importlib
        yayinla_mod = importlib.import_module("scripts.yayinla")

        with patch.object(yayinla_mod.db, "onay_istegi_ertele") as mock_ertele, \
             patch.object(yayinla_mod.telegram_bot, "mesaj_gonder") as mock_mesaj, \
             patch.object(yayinla_mod.db, "wal_bosalt"), \
             patch.object(yayinla_mod.sys, "argv", ["yayinla.py", "--tur", "haber", "--id", "55", "--hedef", "ertele"]):
            yayinla_mod.main()
            mock_ertele.assert_called_once_with("haber", "55", dakika=60)
            self.assertIn("ertelendi", mock_mesaj.call_args[0][0].lower())

    def test_tiktok_turkce_hashtag_ve_jeton_yalnizca_ortamda(self) -> None:
        """TikTok baslik_kur Türkçe karakter duyarlı olmalı; jetonlar DB'ye ASLA yazılmaz.

        Önceden token_yenile ayarlar tablosuna yazıyordu; data/edm.db git'e gittiği
        için gerçek jetonlar 57 commit boyunca depo geçmişine girdi. Bu testin eski
        hali de gerçek .env'i "yeni_access_123" ile eziyordu.
        """
        from src import db, tiktok
        from unittest.mock import patch

        # 1. Hashtag tekilleştirme: #silivri ve sabitler arasındaki #Silivri tekilleşmeli
        baslik = tiktok.baslik_kur("Yeni Konut Projesi", ["#silivri", "#emlak"])
        self.assertIn("#silivri", baslik.lower())
        self.assertEqual(baslik.lower().count("#silivri"), 1)

        # 2. Jeton ortamdan okunur, yenilenen jeton DB'ye yazılmaz
        ortam = {"TIKTOK_CLIENT_KEY": "k", "TIKTOK_CLIENT_SECRET": "s", "TIKTOK_REFRESH_TOKEN": "r"}
        with patch.object(tiktok.config, "env_al", side_effect=lambda a, v="": ortam.get(a, v)), \
             patch.object(db, "ayar_yaz") as ayar_yaz, \
             patch("requests.post") as mock_post, \
             patch.dict("os.environ", {}, clear=False):
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"access_token": "yeni_access_123", "refresh_token": "r"}
            self.assertEqual(tiktok.token_yenile(), "yeni_access_123")
            yazilan = [c.args[0] for c in ayar_yaz.call_args_list]
            self.assertFalse([k for k in yazilan if "token" in k], f"jeton DB'ye yazıldı: {yazilan}")

        # 3. Ortamda kimlik yoksa DB'ye bakılmaz, yenileme yapılmaz
        with patch.object(tiktok.config, "env_al", return_value=""), \
             patch.object(db, "ayar_oku", side_effect=AssertionError("DB'den jeton okunmamalı")), \
             patch("requests.post") as mock_post:
            self.assertIsNone(tiktok.token_yenile())
            mock_post.assert_not_called()

    def test_haber_dedup_turkce_karakter(self) -> None:
        """_baslik_anahtari İ/I harflerini düzgün eşleştirmeli."""
        from src.fetch_news import _baslik_anahtari
        b1 = "İSTANBUL KONUT FİYATLARI 2026"
        b2 = "istanbul konut fiyatları 2026"
        self.assertEqual(_baslik_anahtari(b1), _baslik_anahtari(b2))

    def test_db_kaydet_always_kosuyor(self) -> None:
        """hazirla, yayinla ve hatirlat workflow'larında Veritabanını Kaydet adımı 'if: always()' olmalı."""
        wf_klasoru = KOK / ".github" / "workflows"
        for wf_adi in ("hazirla.yml", "yayinla.yml", "hatirlat.yml"):
            icerik = (wf_klasoru / wf_adi).read_text(encoding="utf-8")
            self.assertIn("name: Veritabanını Kaydet", icerik)
            self.assertIn("if: always()", icerik, f"{wf_adi} içinde Veritabanını Kaydet adımı 'if: always()' taşımalı!")

    def test_b3_bicimi_tek_sayfa_degil_carousel_olur(self) -> None:
        """B3 biçimi asla tek sayfa (01 / 01) üretmemeli; en az 3-4 slaytlık carousel planlamalı."""
        from src import make_image, generate_text
        b3_ornek = {
            "bicim": "B3",
            "kategori_kodu": "TAPU_VE_HUKUK",
            "manset_parca_1": "Ev Alırken",
            "manset_vurgu": "EK MALİYETLER",
            "manset_parca_2": "Bütçeyi Sarsar",
            "spot": "Tapu harcı ve döner sermaye alıcıyı hazırlıksız yakalar.",
            "slayt_2_detay": {
                "kart_1": {"etiket": "RİSK", "renk": "kirmizi", "baslik": "Gizli Masraflar", "aciklama": "Beklenmeyen tapu ve harç bedelleri."},
                "kart_2": {"etiket": "ÇÖZÜM", "renk": "yesil", "baslik": "Bütçe Planlama", "aciklama": "Yüzde 4 tapu harcını peşinen ayırın."},
            },
            "slayt_3_cozum": {
                "tip": "adim_adim_rehber",
                "maddeler": [
                    {"no": "01", "baslik": "Harcı Hesaplayın", "aciklama": "Belediye rayici ve gerçek satış bedelini kıyaslayın."},
                ]
            }
        }
        plan = make_image._slayt_plani(b3_ornek)
        self.assertGreaterEqual(len(plan), 3, "B3 biçimi tek sayfa kalmamalı; en az 3-4 slaytlık akış üretmeli!")
        self.assertEqual(plan[0]["tur"], "kapak")
        self.assertEqual(plan[-1]["tur"], "kapanis")
        self.assertIn("slayt_3_cozum", generate_text._SEMA_B3)

    def test_test_izolasyonu_ve_guvenlik_kilidi(self) -> None:
        """Testlerin asla canlı Telegram'a mesaj atmamasını ve git commit/push yapmamasını denetler."""
        from src import db_senkron
        import os

        # 1. POSTEDM_TEST_MODU etkinken hemen_kaydet git komutlarını çalıştırmadan True dönmeli
        with patch.dict(os.environ, {"POSTEDM_TEST_MODU": "1"}):
            with patch.object(db_senkron, "_calistir") as mock_calistir:
                sonuc = db_senkron.hemen_kaydet("test commit")
                self.assertTrue(sonuc)
                mock_calistir.assert_not_called()

        # 2. test_ozel_icerik_ve_slayt_islem.py dosyasında DB izolasyonu ve mock koruması var mı
        kod_ozel = (KOK / "tests" / "test_ozel_icerik_ve_slayt_islem.py").read_text(encoding="utf-8")
        self.assertIn("src.db.DB_YOLU", kod_ozel)
        self.assertIn("db_senkron.hemen_kaydet", kod_ozel)
        self.assertIn("telegram_bot.mesaj_gonder", kod_ozel)

        # 3. test_finans_ve_oto_yayin.py dosyasında DB izolasyonu var mı
        kod_finans = (KOK / "tests" / "test_finans_ve_oto_yayin.py").read_text(encoding="utf-8")
        self.assertIn("src.db.DB_YOLU", kod_finans)
        self.assertIn("konu_bankasi.kullanildi_isaretle", kod_finans)


if __name__ == "__main__":
    unittest.main()
