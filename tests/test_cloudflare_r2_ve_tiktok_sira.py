"""
tests/test_cloudflare_r2_ve_tiktok_sira.py — Cloudflare R2 CDN ve TikTok Öncelikli Paylaşım Sıralaması Testleri
"""

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import datetime
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from scripts import yayinla
from src import upload_image


class TestCloudflareR2VeTikTokSira(unittest.TestCase):

    def setUp(self):
        from PIL import Image
        self.dummy_img = KOK / "data/output/test_r2_img.jpg"
        self.dummy_img.parent.mkdir(parents=True, exist_ok=True)
        im = Image.new("RGB", (100, 100), color="red")
        im.save(self.dummy_img, "JPEG")

        self.dummy_vid = KOK / "data/output/test_r2_vid.mp4"
        self.dummy_vid.write_bytes(b"dummy video data")

        # Kanal yönlendirmesi testi; yayın kapısının kendisi test_sifir_tolerans'ta
        self._kapi = patch("src.telegram.akislar.kapi.yayin_kapisi", return_value=(True, []))
        self._kapi.start()

    def tearDown(self):
        self._kapi.stop()
        self.dummy_img.unlink(missing_ok=True)
        self.dummy_vid.unlink(missing_ok=True)

    def test_r2_bilgileri_envden_ve_varsayilanlardan_okuma(self):
        """R2 bilgileri ortam değişkenlerinden doğru okunmalı, varsayılan domain/bucket uygulanmalı."""
        with patch.dict("os.environ", {
            "R2_ACCOUNT_ID": "acc123",
            "R2_ACCESS_KEY_ID": "key123",
            "R2_SECRET_ACCESS_KEY": "sec123",
            "R2_BUCKET_NAME": "test-bucket",
            "R2_PUBLIC_DOMAIN": "media.edmyapigayrimenkul.com",
        }):
            bilgi = upload_image._r2_bilgileri()
            self.assertIsNotNone(bilgi)
            acc, key, sec, bucket, domain = bilgi
            self.assertEqual(acc, "acc123")
            self.assertEqual(key, "key123")
            self.assertEqual(sec, "sec123")
            self.assertEqual(bucket, "test-bucket")
            self.assertEqual(domain, "media.edmyapigayrimenkul.com")

    def test_r2ye_yukle_sigv4_imza_ve_put_istegi(self):
        """r2ye_yukle S3 SigV4 imzasıyla PUT isteği göndermeli ve custom domain URL dönmeli."""
        with patch.dict("os.environ", {
            "R2_ACCOUNT_ID": "10fbe7ac62f1739209bbe9cd0a6752f8",
            "R2_ACCESS_KEY_ID": "fake_key",
            "R2_SECRET_ACCESS_KEY": "fake_secret",
            "R2_BUCKET_NAME": "edm-media",
            "R2_PUBLIC_DOMAIN": "media.edmyapigayrimenkul.com",
        }), patch("requests.put") as mock_put:
            mock_put.return_value = MagicMock(status_code=200, text="")

            sonuc = upload_image.r2ye_yukle(self.dummy_img, alt_klasor="sosyal")
            self.assertIn("https://media.edmyapigayrimenkul.com/sosyal/", sonuc["url"])

            mock_put.assert_called_once()
            args, kwargs = mock_put.call_args
            self.assertIn("10fbe7ac62f1739209bbe9cd0a6752f8.r2.cloudflarestorage.com/edm-media/sosyal/", args[0])
            headers = kwargs["headers"]
            self.assertIn("AWS4-HMAC-SHA256 Credential=fake_key", headers["Authorization"])
            self.assertIn("x-amz-content-sha256", headers)

    def test_gorsel_yukle_r2_onceligi_ve_basarili_donus(self):
        """gorsel_yukle R2 yapılandırıldığında öncelikle R2'ye yüklemeli."""
        with patch.object(upload_image, "_r2_bilgileri", return_value=("acc", "key", "sec", "bkt", "media.edmyapigayrimenkul.com")), \
             patch.object(upload_image, "r2ye_yukle", return_value={"url": "https://media.edmyapigayrimenkul.com/sosyal/test.jpg"}) as mock_r2, \
             patch.object(upload_image, "_imgbb_anahtarlari") as mock_imgbb:
            url = upload_image.gorsel_yukle(self.dummy_img)
            self.assertEqual(url, "https://media.edmyapigayrimenkul.com/sosyal/test.jpg")
            mock_r2.assert_called_once()
            mock_imgbb.assert_not_called()

    def test_gorsel_yukle_r2_hatasinda_imgbb_yedegine_gecis(self):
        """R2 başarısız olduğunda sessizce ImgBB / yedek zincirine geçmeli."""
        with patch.object(upload_image, "_r2_bilgileri", return_value=("acc", "key", "sec", "bkt", "media.edmyapigayrimenkul.com")), \
             patch.object(upload_image, "r2ye_yukle", side_effect=RuntimeError("R2 baglanti hatasi")), \
             patch.object(upload_image, "_imgbb_anahtarlari", return_value=["key1"]), \
             patch("requests.post") as mock_post:
            resp = MagicMock(status_code=200)
            resp.json.return_value = {"data": {"url": "https://i.ibb.co/test.jpg"}}
            mock_post.return_value = resp

            url = upload_image.gorsel_yukle(self.dummy_img)
            self.assertEqual(url, "https://i.ibb.co/test.jpg")
            mock_post.assert_called_once()

    def test_video_yukle_r2_onceligi_ve_basarili_donus(self):
        """video_yukle R2 yapılandırıldığında öncelikle R2'ye video klasörüne yüklemeli."""
        with patch.object(upload_image, "_r2_bilgileri", return_value=("acc", "key", "sec", "bkt", "media.edmyapigayrimenkul.com")), \
             patch.object(upload_image, "r2ye_yukle", return_value={"url": "https://media.edmyapigayrimenkul.com/video/test.mp4"}) as mock_r2:
            url = upload_image.video_yukle(self.dummy_vid)
            self.assertEqual(url, "https://media.edmyapigayrimenkul.com/video/test.mp4")
            mock_r2.assert_called_once()

    def test_tiktok_instagramdan_once_yayinlanmali(self):
        """Yayınlama sürecinde TikTok (Kanal 1) Instagram'dan (Kanal 2) önce çalıştırılmalı."""
        haber = {
            "id": 999,
            "manset": "TikTok Öncelik Testi",
            "ig_caption": "Açıklama",
            "detay_metni": json.dumps({"giris": "test"}),
            "slayt_yollari": json.dumps([str(self.dummy_img), str(self.dummy_img)]),
            "slayt_urlleri": json.dumps(["https://media.edmyapigayrimenkul.com/1.jpg", "https://media.edmyapigayrimenkul.com/2.jpg"]),
        }

        manager = MagicMock()

        def sahte_tt(*args, **kwargs):
            manager.tiktok()
            return {"durum": True, "publish_id": "tt123"}

        def sahte_ig(*args, **kwargs):
            manager.instagram()
            return "ig123"

        with (
            patch.object(yayinla.sys, "argv", ["yayinla.py", "--tur", "haber", "--id", "999", "--hedef", "tt,ig"]),
            patch.object(yayinla.db, "haber_getir", return_value=haber),
            patch.object(yayinla.db, "haber_guncelle"),
            patch.object(yayinla.db, "onay_istegi_sonuclandir"),
            patch.object(yayinla.tiktok, "foto_yayinla", side_effect=sahte_tt),
            patch.object(yayinla.instagram, "carousel_yayinla", side_effect=sahte_ig),
            patch("src.telegram.istemci.mesaj_gonder"),
            patch("src.telegram.istemci._istek"),  # canlı durum/sonuç mesajları da istemciden geçer: ağ kapısı kapalı
        ):
            yayinla.main()

            # TikTok ilk, Instagram ikinci çağrılmış olmalı
            cagrilar = manager.mock_calls
            self.assertEqual(cagrilar, [call.tiktok(), call.instagram()])


if __name__ == "__main__":
    unittest.main()
