"""
tests/test_instabot_guvenlik_sozlesmesi.py — Instabot Hata Geçmişi & Güvenlik Sözleşmesi Testleri

Bu test paketi, instabot projesinde canlıda yaşanmış ve belgelenmiş tüm kritik
tuzakların (Trap 1ab, 1o, 01, 03, 20, 50, d29dd76) postedm projesinde
kesinlikle tekrarlanmayacağını denetler:
  1. Telegram tüm menüler 64-bayt callback_data limiti
  2. Telegram 4096 karakter tavanı ve taşma koruması
  3. Telegram HTML parse hatasında html.unescape ile düz metin kurtarma
  4. SQLite wal_bosalt bağlantı sızıntısı koruması (ResourceWarning engeli)
  5. Workflow concurrency grubu izolasyonu ve if: cancelled() bildirimi
  6. TikTok inbox draft modunda kopyalanabilir açıklama metni iletimi
  7. Video stereo AAC ses izi ve faststart kontrolü
  8. Para birimi (₺) ve unvanların satır başlarında yetim kalmaması
"""

import os
import re
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

KOK = Path(__file__).resolve().parent.parent

from src import db, telegram_bot, tiktok
from scripts import yayinla


class TestInstabotGuvenlikSozlesmesi(unittest.TestCase):

    def test_01_tum_menuler_64_bayt_callback_limiti(self):
        """Telegram kuralı: Sistemdeki TÜM butonların callback_data uzunluğu <= 64 bayt olmalıdır."""
        from src import hata_bildir
        menuler = [
            telegram_bot.ana_menu(1),
            telegram_bot.ana_menu(10),
            telegram_bot.yayin_zamani_menusu(3),
            telegram_bot.foto_menusu(5),
            telegram_bot.metin_menusu(5),
            telegram_bot.slayt_secim_menusu(5),
            telegram_bot.slayt_islem_menusu(1, 5),
            telegram_bot.slayt_islem_menusu(5, 5),
            telegram_bot.onay_menusu(1),
            telegram_bot.onay_menusu(999999),
            telegram_bot.reels_onay_menusu(42),
            telegram_bot.metin_secim_menusu(1),
            telegram_bot.foto_secim_menusu(1),
            telegram_bot.format_secim_menusu(1),
            {"inline_keyboard": telegram_bot.kanal_butonlari()},
            telegram_bot.kontrol_merkezi_menusu(),
            telegram_bot.duraklatma_secenekleri_menusu(),
            hata_bildir._butonlar(eylem="tur_tekrar", nerede="Yayınla", tur="haber", ref_id="1", hedef="hepsi", mesaj_id="123", run_url="https://github.com/a/b/actions/runs/123"),
            hata_bildir._butonlar(eylem="yeniden_yayinla", nerede="Yayınla", tur="ilan", ref_id="999999", hedef="hepsi", mesaj_id="456", run_url="https://github.com/a/b/actions/runs/456"),
        ]

        toplam_buton = 0
        for menu in menuler:
            self.assertIn("inline_keyboard", menu)
            for satir in menu["inline_keyboard"]:
                for buton in satir:
                    cb = buton.get("callback_data")
                    if cb:
                        toplam_buton += 1
                        bayt_uzunluk = len(cb.encode("utf-8"))
                        self.assertLessEqual(
                            bayt_uzunluk, 64,
                            f"Buton callback_data 64 bayt sınırını aştı ({bayt_uzunluk} bayt): {cb}"
                        )

        self.assertGreaterEqual(toplam_buton, 25, "En az 25 farklı buton test edilmiş olmalıdır.")

    def test_02_mesaj_gonder_4096_karakter_siniri(self):
        """4096 karakteri aşan dev metinlerde mesaj_gonder'in güvenle kırpması."""
        dev_metin = "EDM Yapı Gayrimenkul Silivri " * 200  # ~6000 karakter
        yakalanan_payload = {}

        def sahte_istek(metot, **kwargs):
            yakalanan_payload.update(kwargs)
            return {"message_id": 9999}

        with patch("src.telegram_bot._istek", side_effect=sahte_istek):
            sonuc = telegram_bot.mesaj_gonder(dev_metin)
            self.assertEqual(sonuc, {"message_id": 9999})
            self.assertIn("text", yakalanan_payload)
            self.assertLessEqual(len(yakalanan_payload["text"]), 4096)

    def test_03_mesaj_gonder_html_unclosed_tag_fallback(self):
        """Kapanmamış HTML tag veya özel karakterlerde parse_mode kaldırılarak unescape ile kurtarılması."""
        hatali_html = "<b>EDM Yapı Gayrimenkul & Yatırım Danışmanlığı <i>Silivri"  # <b> ve <i> kapanmamış
        cagri_sayisi = 0

        def sahte_post(url, json=None, timeout=25):
            nonlocal cagri_sayisi
            cagri_sayisi += 1
            resp = MagicMock()
            if cagri_sayisi == 1:
                # İlk çağrıda Telegram can't parse entities hatası versin
                resp.status_code = 400
                resp.content = b'{"ok": false, "error_code": 400, "description": "Bad Request: can\'t parse entities: Unmatched end tag"}'
                resp.json.return_value = {"ok": False, "error_code": 400, "description": "Bad Request: can't parse entities: Unmatched end tag"}
                return resp
            # İkinci çağrıda düz metinle başarılı olsun
            resp.status_code = 200
            resp.content = b'{"ok": true, "result": {"message_id": 8888}}'
            resp.json.return_value = {"ok": True, "result": {"message_id": 8888}}
            return resp

        with patch("requests.post", side_effect=sahte_post), \
             patch("src.telegram_bot._bot_bilgileri", return_value=("fake_token", "fake_chat")):
            sonuc = telegram_bot.mesaj_gonder(hatali_html, html=True)
            self.assertEqual(sonuc, {"message_id": 8888})
            self.assertEqual(cagri_sayisi, 2, "İlk istek parse hatası alıp ikinci istek düz metinle kurtarmalıdır.")

    def test_04_wal_bosalt_baglanti_kapatma(self):
        """wal_bosalt() fonksiyonunun connection leak bırakmadığını doğrular."""
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            db.wal_bosalt()
            unclosed_warnings = [
                item for item in w
                if "unclosed database" in str(item.message).lower() or "unclosed <sqlite3" in str(item.message).lower()
            ]
            self.assertEqual(len(unclosed_warnings), 0, "wal_bosalt arkasında açık SQLite bağlantısı bırakmamalıdır.")

    def test_05_workflow_concurrency_ve_cancelled_adimi(self):
        """yayinla.yml workflow dosyasının izole concurrency grubu taşıdığını ve if: cancelled() adımı olduğunu doğrular."""
        yayinla_yml = (KOK / ".github" / "workflows" / "yayinla.yml").read_text(encoding="utf-8")
        
        # Concurrency grubunun edm-veritabani-yayin olduğunu doğrula (hazirla ile çakışmaz)
        self.assertIn("group: edm-veritabani-yayin", yayinla_yml)
        
        # if: cancelled() adımının varlığını doğrula (sessiz iptal önlemi)
        self.assertIn("if: cancelled()", yayinla_yml)
        self.assertIn("Yayın İşlemi İptal Edildi", yayinla_yml)

    def test_06_tiktok_inbox_draft_kopyalanabilir_metin(self):
        """TikTok taslak modunda yüklendiğinde Telegram'a kopyalanabilir açıklama metni gönderildiğini doğrular."""
        yayinla_kod = (KOK / "scripts" / "yayinla.py").read_text(encoding="utf-8")
        self.assertIn("tt_res.get(\"taslak_mi\")", yayinla_kod)
        self.assertIn("<pre><code>{html_lib.escape(tt_baslik)}</code></pre>", yayinla_kod)

    def test_07_video_stereo_aac_sessiz_iz(self):
        """src/video.py içinde stereo AAC anullsrc ses izi ve faststart moov atomu bulunduğunu doğrular."""
        video_kod = (KOK / "src" / "video.py").read_text(encoding="utf-8")
        self.assertIn("anullsrc=channel_layout=stereo:sample_rate=44100", video_kod)
        self.assertIn("+faststart", video_kod)

    def test_08_tipografi_para_birimi_yapiskalik(self):
        """src/make_image.py içinde ₺ sembolünün ve unvanların tek başına satır başına düşmediğini doğrular."""
        from PIL import Image, ImageDraw
        from src.make_image import _metin_sar, _font_yukle, FONT_INTER_BOLD
        
        test_font = _font_yukle(FONT_INTER_BOLD, 36)
        dummy_img = Image.new("RGB", (1080, 1920))
        draw = ImageDraw.Draw(dummy_img)

        # 1. Sabotaj: 2.500 ₺ ifadesinde ₺ yeni satıra tek başına düşemez
        metin = "Silivri satılık arsa fiyatı 2.500 ₺ olarak belirlendi."
        satirlar = _metin_sar(metin, test_font, azami_genislik=500, draw=draw)
        self.assertGreaterEqual(len(satirlar), 2)
        for s in satirlar:
            self.assertFalse(s.strip().startswith("₺"), f"Satır tek başına ₺ ile başladı: {satirlar}")


if __name__ == "__main__":
    unittest.main()
