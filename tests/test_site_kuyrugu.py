"""Site ilan kuyruğunun dış platformlara çıkmadan çalışan sözleşme testleri."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

KOK = Path(__file__).resolve().parent.parent
BETIK_YOLU = KOK / "scripts" / "site_kuyrugunu_isle.py"
OZELLIK = importlib.util.spec_from_file_location("site_kuyrugunu_isle", BETIK_YOLU)
assert OZELLIK and OZELLIK.loader
site_kuyrugu = importlib.util.module_from_spec(OZELLIK)
OZELLIK.loader.exec_module(site_kuyrugu)

YAYIN_BETIK_YOLU = KOK / "scripts" / "yayinla.py"
YAYIN_OZELLIGI = importlib.util.spec_from_file_location("yayinla", YAYIN_BETIK_YOLU)
assert YAYIN_OZELLIGI and YAYIN_OZELLIGI.loader
yayinla = importlib.util.module_from_spec(YAYIN_OZELLIGI)
YAYIN_OZELLIGI.loader.exec_module(yayinla)

from src import db


class TestSiteKuyrugu(unittest.TestCase):
    def test_anahtar_olmadan_api_acilmaz(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "OIDC"):
                site_kuyrugu._ayarlar()

    def test_bos_kuyruk_204_ile_sessizce_biter(self) -> None:
        cevap = Mock(status_code=204)
        with patch.dict(os.environ, {"EDM_SITE_API_ANAHTARI": "test-anahtari"}, clear=True):
            with patch.object(site_kuyrugu.requests, "get", return_value=cevap) as istek:
                self.assertIsNone(site_kuyrugu.siradaki_isi_al())
        self.assertEqual(istek.call_args.kwargs["headers"]["X-Postedm-Anahtari"], "test-anahtari")

    def test_github_actions_oidc_jetonu_kisa_omurlu_kimlik_olarak_kullanilir(self) -> None:
        oidc = Mock()
        oidc.json.return_value = {"value": "github-oidc-jetonu"}
        site_kuyrugu._OIDC_JETONU = None
        with patch.dict(os.environ, {
            "ACTIONS_ID_TOKEN_REQUEST_URL": "https://token.actions.example/id",
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "runner-istek-jetonu",
        }, clear=True):
            with patch.object(site_kuyrugu.requests, "get", return_value=oidc) as istek:
                _, basliklar = site_kuyrugu._ayarlar()
        self.assertEqual(basliklar, {"Authorization": "Bearer github-oidc-jetonu"})
        self.assertEqual(istek.call_args.kwargs["params"]["audience"], "edm-postedm-site")

    def test_basarili_is_guncel_ilani_kaydeder_ve_sonucu_yazar(self) -> None:
        is_kaydi = {
            "kuyrukId": 42,
            "platformlar": ["ig", "facebook"],
            "ilan": {"id": "elle-test", "baslik": "Sezonluk Yazlık"},
        }
        with (
            patch.object(site_kuyrugu, "siradaki_isi_al", return_value=is_kaydi),
            patch.object(site_kuyrugu.db, "ilan_kaydet_veya_guncelle") as kaydet,
            patch.object(site_kuyrugu.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="tamam", stderr="")) as calistir,
            patch.object(site_kuyrugu, "sonucu_yaz") as sonuc,
        ):
            self.assertEqual(site_kuyrugu.main(), 0)

        kaydet.assert_called_once_with(is_kaydi["ilan"])
        komut = calistir.call_args.args[0]
        self.assertIn("ig,facebook", komut)
        self.assertIn("--yeniden-ciz", komut)
        sonuc.assert_called_once_with(42, "yayinlandi", sonuc="tamam")

    def test_yayin_hatasi_d1e_geri_yazilir(self) -> None:
        is_kaydi = {
            "kuyrukId": 9,
            "platformlar": ["youtube"],
            "ilan": {"id": "elle-hata", "baslik": "Test"},
        }
        with (
            patch.object(site_kuyrugu, "siradaki_isi_al", return_value=is_kaydi),
            patch.object(site_kuyrugu.db, "ilan_kaydet_veya_guncelle"),
            patch.object(site_kuyrugu.subprocess, "run", return_value=SimpleNamespace(returncode=3, stdout="", stderr="yükleme başarısız")),
            patch.object(site_kuyrugu, "sonucu_yaz") as sonuc,
        ):
            self.assertEqual(site_kuyrugu.main(), 3)

        sonuc.assert_called_once_with(
            9,
            "hata",
            sonuc="yükleme başarısız",
            hata="Yayın komutu 3 koduyla bitti.",
        )

    def test_kuru_calisma_isi_sahiplenir_ama_dis_platformu_cagirmaz(self) -> None:
        is_kaydi = {
            "kuyrukId": 43,
            "platformlar": ["ig", "threads"],
            "ilan": {"id": "elle-kuru", "baslik": "Kuru test", "fiyat": 12500000, "gorseller": ["1.jpg", "2.jpg"]},
        }
        with (
            patch.object(site_kuyrugu, "siradaki_isi_al", return_value=is_kaydi),
            patch.object(site_kuyrugu.db, "ilan_kaydet_veya_guncelle") as kaydet,
            patch.object(site_kuyrugu.subprocess, "run") as calistir,
            patch.object(site_kuyrugu, "sonucu_yaz") as sonuc,
        ):
            self.assertEqual(site_kuyrugu.main(kuru_calisma=True), 0)
        kaydet.assert_called_once_with(is_kaydi["ilan"])
        calistir.assert_not_called()
        self.assertEqual(sonuc.call_args.args[:2], (43, "kuru"))
        rapor = json.loads(sonuc.call_args.kwargs["sonuc"])
        self.assertEqual(rapor["fotografSayisi"], 2)
        self.assertFalse(rapor["disPlatformCagrisi"])

    def test_platformu_olmayan_is_yayinlanmaz(self) -> None:
        is_kaydi = {"kuyrukId": 7, "platformlar": [], "ilan": {"id": "elle-bos"}}
        with (
            patch.object(site_kuyrugu, "siradaki_isi_al", return_value=is_kaydi),
            patch.object(site_kuyrugu, "sonucu_yaz") as sonuc,
            patch.object(site_kuyrugu.subprocess, "run") as calistir,
        ):
            self.assertEqual(site_kuyrugu.main(), 1)
        sonuc.assert_called_once_with(7, "hata", hata="Kuyrukta platform seçimi yok.")
        calistir.assert_not_called()

    def test_yerel_kayit_hatasi_da_kuyruga_geri_bildirilir(self) -> None:
        is_kaydi = {
            "kuyrukId": 12,
            "platformlar": ["threads"],
            "ilan": {"id": "elle-db-hata", "baslik": "Test"},
        }
        with (
            patch.object(site_kuyrugu, "siradaki_isi_al", return_value=is_kaydi),
            patch.object(site_kuyrugu.db, "ilan_kaydet_veya_guncelle", side_effect=ValueError("bozuk veri")),
            patch.object(site_kuyrugu, "sonucu_yaz") as sonuc,
        ):
            with self.assertRaisesRegex(ValueError, "bozuk veri"):
                site_kuyrugu.main()
        sonuc.assert_called_once_with(12, "hata", hata="ValueError: bozuk veri")

    def test_null_fiyat_ve_m2_sqlite_kaydini_bozmaz(self) -> None:
        eski_yol = db.DB_YOLU
        with tempfile.TemporaryDirectory() as gecici:
            try:
                db.DB_YOLU = Path(gecici) / "kuyruk.db"
                db.tablolari_olustur()
                db.ilan_kaydet_veya_guncelle({
                    "id": "elle-null",
                    "baslik": "Fiyatı görüşmede",
                    "fiyat": None,
                    "m2": None,
                    "ozellikler": {},
                    "gorseller": [],
                })
                kayit = db.ilan_getir("elle-null")
                self.assertIsNotNone(kayit)
                self.assertEqual(kayit["fiyat"], 0)
                self.assertEqual(kayit["m2"], 0)
            finally:
                db.DB_YOLU = eski_yol

    def test_bir_platform_patlayinca_diger_platform_yine_islenir(self) -> None:
        with tempfile.TemporaryDirectory() as gecici:
            yollar = []
            for ad in ("kapak.jpg", "detay.jpg", "kapanis.jpg"):
                yol = Path(gecici) / ad
                yol.write_bytes(b"test")
                yollar.append(yol)
            ilan = {"id": "elle-kismi", "baslik": "Kısmi yayın testi", "kaynak_url": "https://example.com/ilan"}
            dummy_video = Path(gecici) / "video.mp4"
            dummy_video.write_bytes(b"dummy video")
            with (
                patch.object(yayinla.sys, "argv", ["yayinla.py", "--tur", "ilan", "--id", "elle-kismi", "--hedef", "ig,facebook", "--yeniden-ciz"]),
                patch.object(yayinla.db, "ilan_getir", return_value=ilan),
                patch("src.make_image.ilan_kapak_slayti_ciz", return_value=yollar[0]),
                patch("src.make_image.ilan_detay_slayti_ciz", return_value=yollar[1]),
                patch("src.make_image.ilan_kapanis_slayti_ciz", return_value=yollar[2]),
                patch.object(yayinla.upload_image, "coklu_gorsel_yukle", return_value=["https://cdn.example.com/1.jpg"]),
                patch.object(yayinla.instagram, "carousel_yayinla", side_effect=RuntimeError("Instagram kapalı")),
                patch.object(yayinla.video, "slaytlardan_reels_uret", return_value=dummy_video),
                patch.object(yayinla.ses, "sesli_video_hazirla", return_value=dummy_video),
                patch.object(yayinla.facebook, "video_yayinla", return_value="fb-123") as facebook_video,
                patch.object(yayinla.telegram_bot, "mesaj_gonder"),
                patch.object(yayinla.db, "ilan_paylasildi_isaretle") as isaretle,
            ):
                with self.assertRaisesRegex(RuntimeError, "Bir veya daha fazla"):
                    yayinla.main()
            facebook_video.assert_called_once()
            isaretle.assert_called_once_with("elle-kismi")


if __name__ == "__main__":
    unittest.main()
