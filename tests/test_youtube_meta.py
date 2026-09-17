"""
tests/test_youtube_meta.py
YouTube metadata ve emlak ofisi kimliği testleri.
"""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src import youtube


class TestYouTubeMeta(unittest.TestCase):
    @patch("src.youtube.access_token_al", return_value="sahte_token")
    @patch("src.youtube.gunluk_yukleme_sayisi_al", return_value=0)
    @patch("src.youtube.gunluk_yukleme_sayisi_artir")
    @patch("src.youtube.youtube_icin_sesli_video_hazirla")
    @patch("requests.post")
    def test_hukuk_kelimesi_arindirma_ve_emlak_etiketleri(self, mock_post, mock_ses, mock_artir, mock_sayi, mock_token):
        mock_ses.return_value = MagicMock(stat=MagicMock(return_value=MagicMock(st_size=1024)))
        mock_init_resp = MagicMock(status_code=200, headers={"Location": "https://upload.url"})
        mock_post.return_value = mock_init_resp

        with patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "stat", return_value=MagicMock(st_size=1024)), \
             patch("builtins.open", MagicMock()), \
             patch("requests.put", return_value=MagicMock(status_code=200, json=lambda: {"id": "vid123"})):
            res = youtube.shorts_yukle(
                "video.mp4",
                baslik="Hukuk Bülteni // Hukuki Danışmanlık",
                aciklama="Hukuki Vaka analizi ve Hukuk Bürosu bilgilendirmesi.",
                etiketler=["Hukuk", "Avukat", "Dava", "Silivri", "Arsa"],
            )

        self.assertTrue(res.get("durum"))
        # post çağrısındaki payload'ı incele
        args, kwargs = mock_post.call_args
        payload = json.loads(kwargs["data"])
        snippet = payload["snippet"]

        # 1. Başlıkta Hukuk Bülteni yerine Emlak Bülteni, Gayrimenkul Danışmanlığı olmalı
        self.assertNotIn("Hukuk Bülteni", snippet["title"])
        self.assertIn("Emlak Bülteni", snippet["title"])

        # 2. Açıklamada Hukuk Bürosu yerine Emlak Ofisi olmalı
        self.assertNotIn("Hukuk Bürosu", snippet["description"])
        self.assertIn("Emlak Ofisi", snippet["description"])
        self.assertIn("EDM Yapı & Gayrimenkul", snippet["description"])

        # 3. Etiketlerde Hukuk, Avukat, Dava silinmiş olmalı; Emlak ve Arsa kalmalı
        tags = snippet["tags"]
        self.assertNotIn("Hukuk", tags)
        self.assertNotIn("Avukat", tags)
        self.assertNotIn("Dava", tags)
        self.assertIn("Emlak", tags)
        self.assertIn("Gayrimenkul", tags)
        self.assertIn("Arsa", tags)


if __name__ == "__main__":
    unittest.main()
