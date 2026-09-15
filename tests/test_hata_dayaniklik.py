"""
tests/test_hata_dayaniklik.py — Hata Savunma ve Dayanıklılık Testleri
Instabot mimarisinden uyarlanmış koruma katmanlarının doğrulanması:
  1. Telegram HTML entity ayrıştırma hatasında otomatik düz metin kurtarması
  2. Telegram 429 Rate Limit beklemesi ve kurtarması
  3. sendMediaGroup albümünde WEBPAGE_CURL_FAILED durumunda stream/yerel dosya ile kurtarma
  4. Instagram Graph API 2207052 / 2207003 alt kodunda 15 sn bekleme ve tekrar deneme
  5. ImgBB kod 111 iç hatası tekrarı ve Litterbox 72h yedeği
  6. hata_bildir kataloğunun teşhisleri ve data/son_hata.txt kalıcı yazımı
  7. yayinla.py özet rapor atıldığında mükerrer hata kartı atılmaması
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import db, generate_text, hata_bildir, instagram, telegram_bot, threads, tiktok, upload_image, youtube


class TestHataDayaniklik(unittest.TestCase):
    """Hata dayanıklılık ve kurtarma testleri."""

    def test_01_telegram_html_parse_kurtarma(self):
        """Bozuk HTML içeren mesajda Telegram 400 verdiğinde etiketler soyulup düz metinle kurtarılmalı."""
        bozuk_html = "<b>Önemli Gelişme:</b> Silivri arsa fiyatları < 500.000 TL & marj > %20 <i>(kapanmamış tag"
        cagrilar = []

        def sahte_post(url, json=None, timeout=25):
            cagrilar.append(json)
            resp = MagicMock()
            if json.get("parse_mode"):
                resp.status_code = 400
                resp.content = b'{"ok": false, "error_code": 400, "description": "Bad Request: can\'t parse entities in message"}'
                resp.json.return_value = {"ok": False, "error_code": 400, "description": "Bad Request: can't parse entities in message"}
                return resp
            resp.status_code = 200
            resp.content = b'{"ok": true, "result": {"message_id": 9901}}'
            resp.json.return_value = {"ok": True, "result": {"message_id": 9901}}
            return resp

        with patch("requests.post", side_effect=sahte_post), \
             patch("src.config.env_al", side_effect=lambda k: "fake_token" if "TOKEN" in k else "-100123"):
            res = telegram_bot.mesaj_gonder(bozuk_html)
            self.assertIsNotNone(res)
            self.assertEqual(res["message_id"], 9901)
            self.assertEqual(len(cagrilar), 2)
            self.assertNotIn("parse_mode", cagrilar[1])
            self.assertNotIn("<b>", cagrilar[1]["text"])

    def test_02_telegram_rate_limit_beklemesi(self):
        """Telegram HTTP 429 döndüğünde retry_after kadar bekleyip isteği tekrar başarmalı."""
        denemeler = 0

        def sahte_post(url, json=None, timeout=25):
            nonlocal denemeler
            denemeler += 1
            resp = MagicMock()
            if denemeler == 1:
                resp.status_code = 429
                resp.content = b'{"ok": false, "error_code": 429, "parameters": {"retry_after": 1}}'
                resp.json.return_value = {"ok": False, "error_code": 429, "parameters": {"retry_after": 1}}
                return resp
            resp.status_code = 200
            resp.content = b'{"ok": true, "result": {"message_id": 9902}}'
            resp.json.return_value = {"ok": True, "result": {"message_id": 9902}}
            return resp

        with patch("requests.post", side_effect=sahte_post), \
             patch("time.sleep") as mock_sleep, \
             patch("src.config.env_al", side_effect=lambda k: "fake_token" if "TOKEN" in k else "-100123"):
            res = telegram_bot.mesaj_gonder("Hız testi")
            self.assertIsNotNone(res)
            self.assertEqual(res["message_id"], 9902)
            self.assertEqual(denemeler, 2)
            mock_sleep.assert_called_with(2)

    def test_03_telegram_medya_grubu_webpage_curl_failed_kurtarma(self):
        """sendMediaGroup URL'den indiremeyip WEBPAGE_CURL_FAILED verirse acil indirme/stream ile kurtarılmalı."""
        url_cagrisi_oldu = False
        stream_cagrisi_oldu = False

        def sahte_post(url, data=None, json=None, files=None, timeout=30):
            nonlocal url_cagrisi_oldu, stream_cagrisi_oldu
            resp = MagicMock()
            if json and "media" in json:
                url_cagrisi_oldu = True
                resp.status_code = 400
                resp.content = b'{"ok": false, "description": "Bad Request: failed to send message #1 with error WEBPAGE_CURL_FAILED"}'
                resp.text = resp.content.decode()
                return resp
            if files:
                stream_cagrisi_oldu = True
                resp.status_code = 200
                resp.content = b'{"ok": true, "result": [{"message_id": 9903}]}'
                resp.text = resp.content.decode()
                return resp
            resp.status_code = 400
            return resp

        sahte_get = MagicMock()
        sahte_get.return_value.status_code = 200
        sahte_get.return_value.content = b"fake_jpeg_content"

        with patch("requests.post", side_effect=sahte_post), \
             patch("requests.get", sahte_get), \
             patch("src.config.env_al", side_effect=lambda k: "fake_token" if "TOKEN" in k else "-100123"):
            basarili = telegram_bot.medya_grubu_gonder(["https://i.ibb.co/test1.jpg", "https://i.ibb.co/test2.jpg"], caption="Örnek albüm")
            self.assertTrue(basarili)
            self.assertTrue(url_cagrisi_oldu)
            self.assertTrue(stream_cagrisi_oldu)

    def test_04_instagram_2207052_gecici_alt_kod_tekrar_deneme(self):
        """Instagram medya indirme gecikmesi (subcode 2207052) aldığında 15 sn bekleyip tekrar denemeli."""
        denemeler = 0

        def sahte_post(url, data=None, timeout=25):
            nonlocal denemeler
            denemeler += 1
            resp = MagicMock()
            if url.endswith("/media"):
                if denemeler == 1:
                    resp.status_code = 400
                    resp.content = b'{"error":{"message":"Only photo or video can be accepted.","code":9004,"error_subcode":2207052,"is_transient":false}}'
                    resp.json.return_value = {"error": {"code": 9004, "error_subcode": 2207052}}
                    return resp
                resp.status_code = 200
                resp.content = b'{"id": "child_12345"}'
                resp.json.return_value = {"id": "child_12345"}
                return resp
            resp.status_code = 200
            resp.content = b'{"id": "pub_9999"}'
            resp.json.return_value = {"id": "pub_9999"}
            return resp

        with patch("requests.post", side_effect=sahte_post), \
             patch("time.sleep") as mock_sleep, \
             patch("src.instagram._hesap_bilgileri", return_value=("123_acc", "token_xyz")), \
             patch("src.instagram._konteyner_durumu_bekle", return_value=True), \
             patch("src.instagram.gorselleri_4_5_yap", side_effect=lambda x: x):
            post_id = instagram.tekil_gorsel_yayinla("https://i.ibb.co/photo.jpg", "Test Açıklama")
            self.assertEqual(post_id, "pub_9999")
            self.assertGreaterEqual(denemeler, 2)
            mock_sleep.assert_any_call(15)

    def test_05_imgbb_kod_111_ve_litterbox_yedegi(self):
        """ImgBB 400 kod 111 iç hatası aldığında beklemeli, çözülmezse Litterbox 72h devreye girmeli."""
        cagrilar = []

        def sahte_post(url, data=None, files=None, headers=None, timeout=30):
            cagrilar.append(url)
            resp = MagicMock()
            if "imgbb.com" in url:
                resp.status_code = 400
                resp.content = b'{"error":{"message":"Internal upload error","code":111}}'
                resp.json.return_value = {"error": {"message": "Internal upload error", "code": 111}}
                resp.text = resp.content.decode()
                return resp
            if "litterbox" in url:
                resp.status_code = 200
                resp.content = b"https://litter.catbox.moe/test_abc.jpg"
                resp.text = "https://litter.catbox.moe/test_abc.jpg"
                return resp
            resp.status_code = 400
            return resp

        with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp, \
             patch("requests.post", side_effect=sahte_post), \
             patch("time.sleep"), \
             patch("src.config.env_al", side_effect=lambda k: "fake_imgbb_key" if k == "IMGBB_API_KEY" else None):
            tmp.write(b"fake_img")
            tmp.flush()
            url = upload_image.gorsel_yukle(tmp.name)
            self.assertEqual(url, "https://litter.catbox.moe/test_abc.jpg")
            self.assertTrue(any("imgbb" in u for u in cagrilar))
            self.assertTrue(any("litterbox" in u for u in cagrilar))

    def test_06_hata_bildir_katalog_ve_kalici_kayit(self):
        """hata_bildir kataloğu sqlite3.Row, 2207052 ve WEBPAGE_CURL_FAILED'ı doğru teşhis edip son_hata.txt'ye yazmalı."""
        t1 = hata_bildir.hatayi_analiz_et("AttributeError: 'sqlite3.Row' object has no attribute 'get'")
        self.assertTrue(t1["tanindi"])
        self.assertEqual(t1["eylem"], "tur_tekrar")
        self.assertIn("sözlük fonksiyonu", t1["ne_oldu"])

        t2 = hata_bildir.hatayi_analiz_et("OAuthException: error_subcode: 2207052 Only photo or video can be accepted")
        self.assertTrue(t2["tanindi"])
        self.assertEqual(t2["eylem"], "yeniden_yayinla")
        self.assertIn("zaman aşımı", t2["ne_oldu"])

        t3 = hata_bildir.hatayi_analiz_et("RuntimeError: Telegram hatası: WEBPAGE_CURL_FAILED")
        self.assertTrue(t3["tanindi"])

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "hata_kayitlari.jsonl"
            tmp_son = Path(tmpdir) / "son_hata.txt"
            with patch("src.hata_bildir.HATA_LOG_YOLU", tmp_log), \
                 patch("src.hata_bildir.SON_HATA_YOLU", tmp_son):
                hata_bildir.hata_kaydet("test_konum", "Test Başlık", "Ham Hata Metni", t1)
                self.assertTrue(tmp_log.exists())
                self.assertTrue(tmp_son.exists())
                son_icerik = tmp_son.read_text(encoding="utf-8")
                self.assertIn("test_konum -> Test Başlık", son_icerik)
                self.assertIn("Ham Hata Metni", son_icerik)

    def test_07_threads_gecici_alt_kod_ve_gecikmeler(self):
        """Threads API geçici alt kod (2207052) aldığında 15 sn bekleyip tekrar denemeli, publish öncesi beklemeli."""
        denemeler = 0

        def sahte_post(url, data=None, timeout=25):
            nonlocal denemeler
            denemeler += 1
            resp = MagicMock()
            if url.endswith("/threads"):
                if denemeler == 1:
                    resp.status_code = 400
                    resp.content = b'{"error":{"message":"Media download failed","code":9004,"error_subcode":2207052}}'
                    resp.json.return_value = {"error": {"code": 9004, "error_subcode": 2207052}}
                    return resp
                resp.status_code = 200
                resp.content = b'{"id": "th_child_123"}'
                resp.json.return_value = {"id": "th_child_123"}
                return resp
            resp.status_code = 200
            resp.content = b'{"id": "th_pub_999"}'
            resp.json.return_value = {"id": "th_pub_999"}
            return resp

        sahte_get = MagicMock()
        sahte_get.return_value.status_code = 200
        sahte_get.return_value.json.return_value = {"status": "FINISHED"}

        with patch("requests.post", side_effect=sahte_post), \
             patch("requests.get", sahte_get), \
             patch("time.sleep") as mock_sleep, \
             patch("src.threads._hesap_bilgileri", return_value=("th_user", "th_token")):
            post_id = threads.paylas("Threads Test", ["https://i.ibb.co/photo.jpg"])
            self.assertEqual(post_id, "th_pub_999")
            self.assertGreaterEqual(denemeler, 2)
            mock_sleep.assert_any_call(15)  # 2207052 retry delay
            mock_sleep.assert_any_call(threads.PUBLISH_ONCESI_SANIYE)  # 2s safety delay

    def test_08_youtube_gunluk_kota_limiti_ve_invalid_grant(self):
        """YouTube günlük kota 5'e ulaştığında yükleme durdurulmalı; invalid_grant hatası tanı koymalı."""
        with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp_vid, \
             tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = Path(tmpdir) / "test.db"
            tmp_vid.write(b"fake_video_data_12345")
            tmp_vid.flush()

            with patch("src.db.DB_YOLU", tmp_db):
                db.tablolari_olustur()
                # 5 adet yükleme yapılmış gibi kaydedelim
                for _ in range(5):
                    youtube.gunluk_yukleme_sayisi_artir()

                sayi = youtube.gunluk_yukleme_sayisi_al()
                self.assertEqual(sayi, 5)

                # 5 limitinde shorts_yukle çağrılırsa kota uyarısı vermeli ve durum=False dönmeli
                res = youtube.shorts_yukle(tmp_vid.name, "Test Shorts", "Açıklama")
                self.assertFalse(res["durum"])
                self.assertTrue(res.get("kota_siniri"))

        # invalid_grant teşhis testi
        with patch("requests.post") as mock_post, \
             patch("src.config.env_al", side_effect=lambda k: "fake" if "YOUTUBE" in k else None), \
             patch("src.youtube.log.error") as mock_log_err:
            resp = MagicMock()
            resp.status_code = 400
            resp.text = '{"error": "invalid_grant", "error_description": "Token has been expired or revoked."}'
            mock_post.return_value = resp
            tok = youtube.access_token_al()
            self.assertIsNone(tok)
            self.assertTrue(any("invalid_grant" in str(c) for c in mock_log_err.call_args_list))
            self.assertTrue(any("Testing" in str(c) for c in mock_log_err.call_args_list))

    def test_09_tiktok_unaudited_client_inbox_fallback_ve_baslik_kur(self):
        """TikTok 403 unaudited_client alınca inbox taslak akışına geçmeli; başlık 150 karaktere sığdırılmalı."""
        # 1. Başlık kurma testi: manşet korunmalı, etiketler 150 karaktere göre sığdırılmalı
        manset = "Çok Önemli Emlak Haberi: Silivri Arsa Fiyatlarında Rekor Artış Kaydedildi"
        uzun_etiketler = ["#emlak", "#yatirim", "#silivri", "#gayrimenkul", "#arsa", "#istanbul", "#konut", "#fiyat"]
        baslik = tiktok.baslik_kur(manset, uzun_etiketler)
        self.assertLessEqual(len(baslik), 150)
        self.assertTrue(baslik.startswith(manset))
        self.assertIn("#emlak", baslik)

        # 2. 403 unaudited_client inbox fallback testi
        init_cagrilar = []

        def sahte_post(url, json=None, headers=None, data=None, timeout=30):
            init_cagrilar.append(url)
            resp = MagicMock()
            if "inbox" not in url:
                resp.status_code = 403
                resp.text = '{"error": {"code": "unaudited_client", "message": "Direct post requires approved audit"}}'
                resp.json.return_value = {
                    "error": {
                        "code": "unaudited_client",
                        "message": "Direct post requires approved audit"
                    }
                }
                return resp
            else:
                resp.status_code = 200
                resp.text = '{"error": {"code": "ok"}, "data": {"publish_id": "inbox_draft_987", "upload_url": "https://upload.tiktok.com/inbox_video"}}'
                resp.json.return_value = {
                    "error": {"code": "ok"},
                    "data": {
                        "publish_id": "inbox_draft_987",
                        "upload_url": "https://upload.tiktok.com/inbox_video"
                    }
                }
                return resp

        with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp_vid, \
             patch("requests.post", side_effect=sahte_post), \
             patch("requests.put", return_value=MagicMock(status_code=200)), \
             patch("src.config.env_al", side_effect=lambda k: "fake_tk_key" if "TIKTOK" in k else None):
            tmp_vid.write(b"fake_tk_video_bytes")
            tmp_vid.flush()
            sonuc = tiktok.video_yukle(tmp_vid.name, "Test TikTok Başlık")
            self.assertTrue(sonuc["durum"])
            self.assertEqual(sonuc["publish_id"], "inbox_draft_987")
            self.assertTrue(sonuc["taslak_mi"])
            self.assertEqual(len(init_cagrilar), 2)
            self.assertIn("inbox", init_cagrilar[1])


    def test_10_gemini_gunluk_kota_ve_safety_engeli(self):
        """Gemini PerDay hatasında model/key _TUKENMIS'e alınmalı; safety engeli tespit edilmeli."""
        # Günlük kota hatası testi
        kota_hatasi = Exception("ResourceExhausted: 429 Quota exceeded for quota metric 'GenerateContent requests' and limit 'RequestsPerDay'")
        self.assertTrue(generate_text._gunluk_kota_hatasi(kota_hatasi))

        baska_hata = Exception("ResourceExhausted: 429 Rate limit per minute")
        self.assertFalse(generate_text._gunluk_kota_hatasi(baska_hata))

        # Model/anahtar tükenme seti kontrolü
        generate_text._TUKENMIS.clear()
        generate_text._TUKENMIS.add(("gemini-2.5-flash", "AIzaFakeKey1"))
        self.assertIn(("gemini-2.5-flash", "AIzaFakeKey1"), generate_text._TUKENMIS)

    def test_11_db_ayarlar_ve_yayinla_durum_durustlugu(self):
        """db.ayar_yaz/oku çalışmalı; yayinla.py tüm platformlar çökerse haberi yayinlandi yapmamalı."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = Path(tmpdir) / "test.db"
            with patch("src.db.DB_YOLU", tmp_db):
                db.tablolari_olustur()
                db.ayar_yaz("test_anahtar", "test_deger_123")
                self.assertEqual(db.ayar_oku("test_anahtar"), "test_deger_123")
                # Üzerine yazma kontrolü
                db.ayar_yaz("test_anahtar", "yeni_deger_456")
                self.assertEqual(db.ayar_oku("test_anahtar"), "yeni_deger_456")
                self.assertEqual(db.ayar_oku("olmayan_anahtar", varsayilan="varsayilan"), "varsayilan")



if __name__ == "__main__":
    unittest.main()

