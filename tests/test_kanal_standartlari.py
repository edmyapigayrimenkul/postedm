"""
tests/test_kanal_standartlari.py — Kanala Özel Standart Boyut, Video ve Ses Doğrulama Testleri

Kullanıcı İstekleri:
1. Her kanala standart tanımlı formatta paylaşım yapılır.
2. Instagram & TikTok: Reels seçilmediği sürece Carousel (tek sayfaysa Tekil Resim).
3. Reels seçilirse: IG ve TT video (Reels) olarak gider.
4. Story: Her zaman 9:16 Story formatında Instagram ve Facebook Story'ye iletilir.
5. Threads: Her zaman 4:5 fotoğraf ve zincir yapısında.
6. Facebook: Her zaman Reels (video) ve arkaplan sesli.
7. YouTube: Her zaman Shorts (video) ve arkaplan sesli.
"""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from scripts import yayinla
from src import db


class TestKanalStandartlari(unittest.TestCase):

    def setUp(self):
        from PIL import Image
        self.dummy_video = KOK / "data/output/test_mock_video.mp4"
        self.dummy_video.parent.mkdir(parents=True, exist_ok=True)
        self.dummy_video.write_bytes(b"dummy video content")

        self.dummy_img = KOK / "data/output/test_mock_img.jpg"
        im = Image.new("RGB", (100, 100), color="blue")
        im.save(self.dummy_img, "JPEG")

    def tearDown(self):
        self.dummy_video.unlink(missing_ok=True)
        self.dummy_img.unlink(missing_ok=True)

    def test_coklu_slayt_standart_akis(self):
        """Reels seçilmediğinde: IG ve TT carousel, FB ve YT video(sesli), Story story, Threads zincir."""
        haber = {
            "id": 888,
            "manset": "Test Çoklu Slayt",
            "ig_caption": "Test açıklama",
            "detay_metni": json.dumps({"giris": "a"}),
            "slayt_yollari": json.dumps([str(self.dummy_img), str(self.dummy_img)]),
            "slayt_urlleri": json.dumps(["https://cdn.com/1.jpg", "https://cdn.com/2.jpg"]),
        }
        with (
            patch.object(yayinla.sys, "argv", ["yayinla.py", "--tur", "haber", "--id", "888", "--hedef", "hepsi"]),
            patch.object(yayinla.db, "haber_getir", return_value=haber),
            patch.object(yayinla.db, "haber_guncelle"),
            patch.object(yayinla.db, "onay_istegi_sonuclandir"),
            patch.object(yayinla.upload_image, "gorsel_yukle", return_value="https://cdn.example.com/story.jpg"),
            patch.object(yayinla.instagram, "carousel_yayinla", return_value="ig-c123") as ig_carousel,
            patch.object(yayinla.instagram, "tekil_gorsel_yayinla") as ig_tekil,
            patch.object(yayinla.instagram, "story_yayinla", return_value="ig-s123") as ig_story,
            patch.object(yayinla.tiktok, "foto_yayinla", return_value={"durum": True, "publish_id": "tt-p123"}) as tt_foto,
            patch.object(yayinla.threads, "zincir_paylas", return_value="th-z123") as th_zincir,
            patch.object(yayinla.video, "slaytlardan_reels_uret", return_value=self.dummy_video),
            patch.object(yayinla.ses, "sesli_video_hazirla", return_value=self.dummy_video) as ses_hazirla,
            patch.object(yayinla.facebook, "video_yayinla", return_value="fb-v123") as fb_video,
            patch.object(yayinla.facebook, "story_yayinla", return_value="fb-s123") as fb_story,
            patch.object(yayinla.youtube, "shorts_yukle", return_value={"durum": True, "url": "https://youtu.be/x"}) as yt_shorts,
            patch.object(yayinla.telegram_bot, "mesaj_gonder"),
        ):
            yayinla.main()

            # 1. Instagram carousel gitmeli, tekil çağrılmamalı
            ig_carousel.assert_called_once()
            ig_tekil.assert_not_called()

            # 2. TikTok fotoğraf carousel gitmeli
            tt_foto.assert_called_once()

            # 3. Threads zincir paylaşımı gitmeli
            th_zincir.assert_called_once()

            # 4. Story Instagram ve Facebook'a gitmeli
            ig_story.assert_called_once()
            fb_story.assert_called_once()

            # 5. Facebook her zaman Reels (video) gitmeli
            fb_video.assert_called_once()

            # 6. YouTube Shorts her zaman gitmeli
            yt_shorts.assert_called_once()

            # 7. Video için fon sesi mikslenmeli
            ses_hazirla.assert_called()

    def test_tek_sayfa_standart_akis(self):
        """Tek sayfa olduğunda: IG ve TT tekil resim, FB ve YT yine video(sesli)."""
        haber = {
            "id": 889,
            "manset": "Test Tek Sayfa",
            "ig_caption": "Tek sayfa açıklama",
            "detay_metni": json.dumps({"giris": "tek"}),
            "slayt_yollari": json.dumps([str(self.dummy_img)]),
            "slayt_urlleri": json.dumps(["https://cdn.com/tek.jpg"]),
        }
        with (
            patch.object(yayinla.sys, "argv", ["yayinla.py", "--tur", "haber", "--id", "889", "--hedef", "hepsi"]),
            patch.object(yayinla.db, "haber_getir", return_value=haber),
            patch.object(yayinla.db, "haber_guncelle"),
            patch.object(yayinla.db, "onay_istegi_sonuclandir"),
            patch.object(yayinla.upload_image, "gorsel_yukle", return_value="https://cdn.example.com/story.jpg"),
            patch.object(yayinla.instagram, "tekil_gorsel_yayinla", return_value="ig-tek-123") as ig_tekil,
            patch.object(yayinla.instagram, "carousel_yayinla") as ig_carousel,
            patch.object(yayinla.instagram, "story_yayinla", return_value="ig-s-tek") as ig_story,
            patch.object(yayinla.tiktok, "foto_yayinla", return_value={"durum": True, "publish_id": "tt-tek-123"}) as tt_foto,
            patch.object(yayinla.threads, "paylas", return_value="th-tek-123") as th_paylas,
            patch.object(yayinla.video, "slaytlardan_reels_uret", return_value=self.dummy_video),
            patch.object(yayinla.ses, "sesli_video_hazirla", return_value=self.dummy_video),
            patch.object(yayinla.facebook, "video_yayinla", return_value="fb-v-tek") as fb_video,
            patch.object(yayinla.facebook, "story_yayinla", return_value="fb-s-tek") as fb_story,
            patch.object(yayinla.youtube, "shorts_yukle", return_value={"durum": True, "url": "https://youtu.be/y"}) as yt_shorts,
            patch.object(yayinla.telegram_bot, "mesaj_gonder"),
        ):
            yayinla.main()

            # IG tekil resim gitmeli
            ig_tekil.assert_called_once()
            ig_carousel.assert_not_called()

            # TikTok foto gitmeli
            tt_foto.assert_called_once()

            # Threads tekil paylaşım gitmeli
            th_paylas.assert_called_once()

            # Story Instagram ve Facebook'a gitmeli
            ig_story.assert_called_once()
            fb_story.assert_called_once()

            # FB ve YT tek sayfada da video olarak devam etmeli
            fb_video.assert_called_once()
            yt_shorts.assert_called_once()

    def test_reels_secildiginde_ig_ve_tt_video_olur(self):
        """Reels seçildiğinde: IG reels teslim edilir ve TT video yüklenir."""
        haber = {
            "id": 890,
            "manset": "Test Reels Modu",
            "ig_caption": "Reels açıklama",
            "detay_metni": json.dumps({"giris": "reels"}),
            "slayt_yollari": json.dumps(["data/output/s1.jpg", "data/output/s2.jpg"]),
            "slayt_urlleri": json.dumps(["https://cdn.com/1.jpg", "https://cdn.com/2.jpg"]),
        }
        with (
            patch.object(yayinla.sys, "argv", ["yayinla.py", "--tur", "haber", "--id", "890", "--hedef", "reels,tiktok,facebook,youtube"]),
            patch.object(yayinla.db, "haber_getir", return_value=haber),
            patch.object(yayinla.db, "haber_guncelle"),
            patch.object(yayinla.db, "onay_istegi_sonuclandir"),
            patch.object(yayinla.instagram, "carousel_yayinla") as ig_carousel,
            patch.object(yayinla.instagram, "tekil_gorsel_yayinla") as ig_tekil,
            patch.object(yayinla.telegram_bot, "video_gonder") as tg_video,
            patch.object(yayinla.tiktok, "video_yukle", return_value={"durum": True, "publish_id": "tt-vid-123"}) as tt_video,
            patch.object(yayinla.tiktok, "foto_yayinla") as tt_foto,
            patch.object(yayinla.video, "slaytlardan_reels_uret", return_value=self.dummy_video),
            patch.object(yayinla.ses, "sesli_video_hazirla", return_value=self.dummy_video),
            patch.object(yayinla.facebook, "video_yayinla", return_value="fb-v-reels") as fb_video,
            patch.object(yayinla.youtube, "shorts_yukle", return_value={"durum": True, "url": "https://youtu.be/z"}) as yt_shorts,
            patch.object(yayinla.telegram_bot, "mesaj_gonder"),
        ):
            yayinla.main()

            # IG Carousel ve tekil çağrılmamalı, Reels videosu Telegram'a teslim edilmeli
            ig_carousel.assert_not_called()
            ig_tekil.assert_not_called()
            tg_video.assert_called_once()

            # TikTok fotoğraf değil video yüklenmeli
            tt_foto.assert_not_called()
            tt_video.assert_called_once()

            # FB ve YT video gitmeli
            fb_video.assert_called_once()
            yt_shorts.assert_called_once()


if __name__ == "__main__":
    unittest.main()
