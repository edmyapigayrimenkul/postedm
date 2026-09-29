"""
tests/test_ses_elevenlabs.py — ElevenLabs AI Seslendirme ve Çift Kanal Ses Miksleme Testleri
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src import ses, video


class TestSesElevenLabs(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    @patch("src.ses.requests.post")
    @patch("src.ses.config.env_al")
    def test_metin_seslendir_basarili(self, mock_env, mock_post):
        """ElevenLabs API başarılı olduğunda ses dosyasını yazar ve döndürür."""
        mock_env.side_effect = lambda k: "fake_el_key" if k == "ELEVENLABS_API_KEY" else None

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.content = b"fake mp3 audio content" * 50  # > 500 byte
        mock_post.return_value = fake_resp

        cikti = self.tmp_path / "test_adam.mp3"
        with patch("src.ses.ses_suresi_ogren", return_value=14.5):
            res = ses.metin_seslendir("Hisseli tapuda feragatname yoksa payınız gider.", cikti_yolu=cikti)

        self.assertIsNotNone(res)
        self.assertTrue(cikti.exists())
        self.assertEqual(cikti.read_bytes(), fake_resp.content)
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args[1]["headers"]["xi-api-key"], "fake_el_key")

    @patch("src.ses.config.env_al", return_value=None)
    def test_metin_seslendir_api_key_yok(self, mock_env):
        """ELEVENLABS_API_KEY tanımlı değilse None döner ve çökmez."""
        res = ses.metin_seslendir("Herhangi bir metin")
        self.assertIsNone(res)

    @patch("src.ses.requests.post")
    @patch("src.ses.config.env_al")
    def test_metin_seslendir_401_kota_hata_yonetimi(self, mock_env, mock_post):
        """401/402 kota veya yetki hatasında boşuna döngüde beklemeden None döner."""
        mock_env.side_effect = lambda k: "fake_el_key" if k == "ELEVENLABS_API_KEY" else None

        fake_resp = MagicMock()
        fake_resp.status_code = 402
        fake_resp.text = "Quota exceeded"
        mock_post.return_value = fake_resp

        cikti = self.tmp_path / "test_fail.mp3"
        res = ses.metin_seslendir("Hisseli tapu", cikti_yolu=cikti)
        self.assertIsNone(res)
        # 402 durumunda break yaptığı için yalnızca 1 kere çağrılmalı
        self.assertEqual(mock_post.call_count, 1)

    @patch("src.ses.subprocess.run")
    def test_sesli_video_hazirla_cift_kanal(self, mock_run):
        """Hem voiceover hem fon müziği verildiğinde amix ile çift kanal mikslemeli."""
        dummy_video = self.tmp_path / "video.mp4"
        dummy_video.write_bytes(b"dummy video")

        dummy_voice = self.tmp_path / "voice.mp3"
        dummy_voice.write_bytes(b"dummy voice")

        dummy_music = self.tmp_path / "music.mp3"
        dummy_music.write_bytes(b"dummy music")

        res = ses.sesli_video_hazirla(
            video_yolu=dummy_video,
            ses_dosyasi=dummy_music,
            konusma_sesi=dummy_voice,
            ses_seviyesi=0.14,
        )
        self.assertIsNotNone(res)
        mock_run.assert_called_once()
        komut = mock_run.call_args[0][0]
        # Komutta amix filtresi ve ducking seviyesi bulunmalı
        self.assertIn("-filter_complex", komut)
        komut_str = " ".join(komut)
        self.assertIn("amix=inputs=2", komut_str)
        self.assertIn("volume=0.14", komut_str)

    @patch("src.ses.subprocess.run")
    def test_sesli_video_hazirla_sadece_muzik(self, mock_run):
        """Konuşma sesi olmadığında klasik tekli fon müziği mikslenmeli."""
        dummy_video = self.tmp_path / "video.mp4"
        dummy_video.write_bytes(b"dummy video")

        dummy_music = self.tmp_path / "music.mp3"
        dummy_music.write_bytes(b"dummy music")

        res = ses.sesli_video_hazirla(
            video_yolu=dummy_video,
            ses_dosyasi=dummy_music,
            konusma_sesi=None,
        )
        self.assertIsNotNone(res)
        mock_run.assert_called_once()
        komut = mock_run.call_args[0][0]
        self.assertIn("-filter:a", komut)
        komut_str = " ".join(komut)
        self.assertIn("volume=0.20", komut_str)

    @patch("src.video.imageio.get_writer")
    @patch("src.video._foto_ac_veya_indir")
    def test_video_hedef_sure_dinamik_slayt(self, mock_foto, mock_writer):
        """hedef_sure parametresi verildiğinde slayt süreleri dinamik hesaplanmalı."""
        from PIL import Image
        mock_foto.return_value = Image.new("RGB", (1080, 1920), color="red")

        cikti = self.tmp_path / "hedef_test.mp4"
        raw_cikti = self.tmp_path / "hedef_test_raw.mp4"
        raw_cikti.write_bytes(b"dummy raw")

        def sahte_sub(*args, **kwargs):
            cikti.write_bytes(b"dummy final video")
            return MagicMock()

        with patch("src.video.subprocess.run", side_effect=sahte_sub):
            res = video.slaytlardan_video_uret(
                slayt_yollari=["s1.jpg", "s2.jpg", "s3.jpg"],
                cikti_yolu=cikti,
                hedef_sure=15.0,  # 15 saniyelik seslendirme
            )

        self.assertIsNotNone(res)
        self.assertEqual(res, cikti)
        mock_writer.assert_called_once()

    def test_slayt_surelerini_hesapla(self):
        """Instabot commit 94bf292 standardı: İçerik ve kelime yoğunluğuna göre dinamik slayt süreleri."""
        from src.video import slayt_surelerini_hesapla

        # 1. Tek slayt için varsayılan kapak süresi
        s1 = slayt_surelerini_hesapla(1)
        self.assertEqual(s1, [4.2])

        # 2. 3 slayt için kapak (4.2) + 2 detay slaytı
        h = {
            "detay_maddeleri": [
                {"etiket": "PARSELLER", "metin": "Selimpaşa D-100 kuzey aksı ve Ortaköy gelişim koridorundaki 142 ada ve 85 parsel doğrudan etkileniyor."},
                {"etiket": "EMSALLER", "metin": "Konut ve ticaret alanlarında KAKS 0.60 olarak güncellendi."},
            ]
        }
        s3 = slayt_surelerini_hesapla(3, haber=h)
        self.assertEqual(len(s3), 3)
        self.assertEqual(s3[0], 4.2)
        # Detay slaytları 3.2 ile 5.5 sn arasında olmalı
        self.assertTrue(3.2 <= s3[1] <= 5.5)
        self.assertTrue(3.2 <= s3[2] <= 5.5)
        # Toplam süre algoritmanın zirve retention penceresinde (10-20 sn) olmalı
        self.assertTrue(10.0 <= sum(s3) <= 20.0)


    def test_ken_burns_yavas_oran_ve_kare_olcekleri(self):
        """Ken Burns yavaşlatma testi (%1.6 oran ve çerçeve boyut koruma)."""
        from PIL import Image
        import numpy as np

        # 1. Oran %1.6 olmalı
        self.assertEqual(video.KEN_BURNS_ORAN, 0.016)

        img = Image.new("RGB", (100, 200), color=(10, 20, 30))

        # 2. t=0 için mod="in" ölçek 1.0 -> boyut ve pikseller korunmalı
        kare_0 = video._ken_burns_kare(img, 0.0, oran=0.016, mod="in")
        self.assertEqual(kare_0.shape, (200, 100, 3))
        self.assertEqual(int(kare_0[100, 50, 0]), 10)

        # 3. t=1 için mod="in" ölçek 1.016 -> boyut (200, 100, 3) olarak kırpılmalı
        kare_1 = video._ken_burns_kare(img, 1.0, oran=0.016, mod="in")
        self.assertEqual(kare_1.shape, (200, 100, 3))

        # 4. mod="out" t=0'da maksimum zoom (1.016), t=1'de minimum (1.0)
        kare_out_0 = video._ken_burns_kare(img, 0.0, oran=0.016, mod="out")
        kare_out_1 = video._ken_burns_kare(img, 1.0, oran=0.016, mod="out")
        self.assertEqual(kare_out_0.shape, (200, 100, 3))
        self.assertEqual(kare_out_1.shape, (200, 100, 3))

    @patch("src.video.slaytlardan_video_uret")
    def test_slaytlardan_reels_uret_ken_burns_iletir(self, mock_video_uret):
        """slaytlardan_reels_uret çağrısı ken_burns_orani parametresini iletmeli."""
        video.slaytlardan_reels_uret(["s1.jpg"], ken_burns_orani=0.02)
        mock_video_uret.assert_called_once()
        self.assertEqual(mock_video_uret.call_args[1]["ken_burns_orani"], 0.02)


if __name__ == "__main__":
    unittest.main()

