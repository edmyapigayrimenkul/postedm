"""
tests/test_finans_ve_oto_yayin.py — Finans / Bankacılık İçeriği ve Otomatik Yayınlama Testleri
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import konu_bankasi, telegram_bot


class TestFinansVeOtoYayin(unittest.TestCase):

    def test_s5_sutunu_havuzda_mevcut_ve_secilebiliyor(self):
        """Konu bankasında S5 (Finans/Bankacılık) sütunu bulunmalı ve seçilebilmelidir."""
        havuz = konu_bankasi.havuzu_yukle(tazele=True)
        s5_konulari = [k for k in havuz if k.get("sutun") == "S5"]
        self.assertGreaterEqual(len(s5_konulari), 10, "En az 10 adet S5 finans konusu bulunmalıdır.")

        # sonraki_finans_konusu çağrısı geçerli bir konu dönmeli
        konu = konu_bankasi.sonraki_finans_konusu()
        self.assertIsNotNone(konu)
        self.assertIn("kod", konu)
        self.assertTrue(konu["kod"].startswith("S5") or any(w in (konu["baslik"] + konu["aci"]).lower() for w in ["kredi", "faiz", "banka"]))

    def test_finans_otomatik_yayin_akisi(self):
        """oto_yayin=True olduğunda onay beklenmeden doğrudan yayınlama komutu yürütülmeli."""
        dummy_img = KOK / "data/output/test_finans_dummy.jpg"
        dummy_img.parent.mkdir(parents=True, exist_ok=True)
        dummy_img.write_bytes(b"dummy")

        dummy_video = KOK / "data/output/test_finans_video.mp4"
        dummy_video.write_bytes(b"dummy video")

        veri = {
            "baslik": "Konut Kredisi ve BDDK",
            "spot": "Kredi detayları",
            "kategori_kodu": "FINANS_VE_BANKACILIK",
            "caption_instagram": "IG caption",
            "caption_threads": "Threads caption",
            "slaytlar": [{"metin": "1"}],
        }

        with (
            patch("src.generate_text.konudan_uret", return_value=veri),
            patch("src.make_image.otorite_gonderi_slaytlari_uret", return_value=[dummy_img, dummy_img]),
            patch("src.upload_image.coklu_gorsel_yukle", return_value=["https://cdn.example.com/1.jpg", "https://cdn.example.com/2.jpg"]),
            patch("src.video.slaytlardan_reels_uret", return_value=dummy_video),
            patch("src.ses.sesli_video_hazirla", return_value=dummy_video),
            patch("subprocess.run") as mock_subproc,
            patch("src.telegram_bot.mesaj_gonder") as mock_mesaj,
            patch("src.telegram_bot.medya_grubu_gonder") as mock_medya,
            patch("src.telegram_bot.haber_onayina_sun") as mock_onay,
        ):
            mock_subproc.return_value = MagicMock(returncode=0, stdout="Yayın tamamlandı", stderr="")
            sonuc = telegram_bot.finans_icerigi_hazirla_ve_yayinla(oto_yayin=True)
            self.assertTrue(sonuc)

            # Onaya sunulmamalı, doğrudan subprocess yayinla çağrılmalı
            mock_onay.assert_not_called()
            mock_subproc.assert_called_once()
            komut = mock_subproc.call_args.args[0]
            self.assertIn("yayinla.py", komut[1])
            self.assertIn("ig,threads,story,tiktok,facebook,youtube", komut)

            # Telegram'a bilgilendirme mesajı ve albüm gitmeli
            mock_mesaj.assert_called()
            mock_medya.assert_called_once()

        dummy_img.unlink(missing_ok=True)
        dummy_video.unlink(missing_ok=True)

    def test_finans_onayli_akis(self):
        """oto_yayin=False olduğunda haber_onayina_sun çağrılmalı."""
        dummy_img = KOK / "data/output/test_finans_dummy2.jpg"
        dummy_img.parent.mkdir(parents=True, exist_ok=True)
        dummy_img.write_bytes(b"dummy")

        veri = {
            "baslik": "Faiz Oranları",
            "spot": "Spot",
            "kategori_kodu": "FINANS_VE_BANKACILIK",
            "caption_instagram": "IG",
            "caption_threads": "TH",
        }

        with (
            patch("src.generate_text.konudan_uret", return_value=veri),
            patch("src.make_image.otorite_gonderi_slaytlari_uret", return_value=[dummy_img]),
            patch("src.upload_image.coklu_gorsel_yukle", return_value=["https://cdn.example.com/1.jpg"]),
            patch("src.video.slaytlardan_reels_uret", return_value=dummy_img),
            patch("src.ses.sesli_video_hazirla", return_value=dummy_img),
            patch("subprocess.run") as mock_subproc,
            patch("src.telegram_bot.mesaj_gonder"),
            patch("src.telegram_bot.haber_onayina_sun", return_value=True) as mock_onay,
        ):
            sonuc = telegram_bot.finans_icerigi_hazirla_ve_yayinla(oto_yayin=False)
            self.assertTrue(sonuc)
            mock_subproc.assert_not_called()
            mock_onay.assert_called_once()

        dummy_img.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
