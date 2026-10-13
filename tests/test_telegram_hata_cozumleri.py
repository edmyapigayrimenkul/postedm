"""
tests/test_telegram_hata_cozumleri.py — Telegram Hata Düzeltmeleri Doğrulama Testleri.
1. _istek ve mesaji_guncelle reply_markup: null filtrelemesi
2. Onay mesajlarında içerik ID (#<id>) varlığı
3. TikTok 401 token yenileme ve hazir_video_yolu fallback desteği
4. hata_bildir son_hata.txt fallback ve ref_id çözümlemesi
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src import db, hata_bildir, telegram_bot, tiktok


class TestTelegramHataCozumleri(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_db = Path(self.tmpdir.name) / "test_hata_cozum.db"
        self.db_patcher = patch("src.db.DB_YOLU", self.tmp_db)
        self.db_patcher.start()
        db.tablolari_olustur()

    def tearDown(self):
        self.db_patcher.stop()
        self.tmpdir.cleanup()

    @patch("src.telegram_bot.requests.post")
    def test_mesaji_guncelle_null_reply_markup_gondermez(self, mock_post):
        """mesaji_guncelle reply_markup=None olduğunda Telegram'a null reply_markup göndermemelidir."""
        mock_resp = MagicMock()
        mock_resp.content = b'{"ok": true, "result": {"message_id": 123}}'
        mock_resp.json.return_value = {"ok": True, "result": {"message_id": 123}}
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        with patch("src.telegram_bot._bot_bilgileri", return_value=("fake_token", "-100123")):
            res = telegram_bot.mesaji_guncelle(123, "Test Güncelleme", reply_markup=None)

        self.assertTrue(res)
        mock_post.assert_called_once()
        gonderilen_json = mock_post.call_args[1]["json"]
        self.assertNotIn("reply_markup", gonderilen_json, "reply_markup=None durumunda JSON'a null reply_markup gitmemelidir")
        self.assertEqual(gonderilen_json["message_id"], 123)
        self.assertEqual(gonderilen_json["text"], "Test Güncelleme")

    def test_haber_onay_metninde_icerik_id_varligi(self):
        """haber_onayina_sun metninde Worker ve kullanıcı için #ID ibaresinin bulunduğu doğrulanır."""
        h_id = db.haber_kaydet(
            kaynak="Test Kaynak",
            orijinal_baslik="Hisseli Tapu Satış Rehberi",
            orijinal_url="https://example.com/hisse",
            onem_puani=9,
            kategori="TAPU",
        )
        db.haber_guncelle(h_id, manset="Hisseli Tapu Satış Rehberi", durum="onay_bekliyor")

        with (
            patch("src.telegram_bot.medya_grubu_gonder"),
            patch("src.telegram_bot.mesaj_gonder") as mock_mesaj,
            patch("src.telegram_bot.upload_image.coklu_gorsel_yukle", return_value=[]),
            patch("src.telegram_bot.make_image.otorite_gonderi_slaytlari_uret", return_value=[]),
            patch("src.db_senkron.hemen_kaydet"),
        ):
            mock_mesaj.return_value = {"message_id": 444}
            res = telegram_bot.haber_onayina_sun(h_id)

        self.assertTrue(res)
        mock_mesaj.assert_called_once()
        gonderilen_metin = mock_mesaj.call_args[0][0]
        self.assertIn(f"(#{h_id})", gonderilen_metin)
        self.assertIn(f"#{h_id}", gonderilen_metin)

    @patch("src.tiktok.token_yenile")
    @patch("src.tiktok.requests.post")
    def test_tiktok_foto_yayinla_401_token_yenileme(self, mock_post, mock_token_yenile):
        """TikTok foto_yayinla 401 aldığında token yenileyip tekrar denemelidir."""
        mock_token_yenile.return_value = "yeni_super_token"

        resp_401 = MagicMock()
        resp_401.status_code = 401
        resp_401.text = '{"error": {"code": "access_token_invalid"}}'

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {"error": {"code": "ok"}, "data": {"publish_id": "pub_999"}}

        mock_post.side_effect = [resp_401, resp_200]

        with (
            patch("src.config.env_al", return_value="eski_token"),
            patch("src.db.ayar_oku", return_value=None),
        ):
            sonuc = tiktok.foto_yayinla(["https://cdn.example.com/1.jpg"], baslik="Test Başlık")

        self.assertTrue(sonuc["durum"])
        self.assertEqual(sonuc["publish_id"], "pub_999")
        mock_token_yenile.assert_called_once()
        self.assertEqual(mock_post.call_count, 2)

    @patch("src.tiktok.video_yukle")
    @patch("src.tiktok.requests.post")
    def test_tiktok_foto_yayinla_hazir_video_fallback(self, mock_post, mock_video_yukle):
        """TikTok fotoğraf API'si kapalıysa veya hata verirse hazır video varsa internetten indirmeden onu kullanmalıdır."""
        resp_fail = MagicMock()
        resp_fail.status_code = 500
        resp_fail.text = "Server error"
        mock_post.return_value = resp_fail

        mock_video_yukle.return_value = {"durum": True, "publish_id": "vid_pub_123", "mod": "direct", "taslak_mi": False}

        fake_video = Path(self.tmpdir.name) / "hazir_reels.mp4"
        fake_video.write_bytes(b"dummy mp4 video bytes")

        with (
            patch("src.config.env_al", return_value="valid_token"),
            patch("src.video.slaytlardan_reels_uret") as mock_uret,
        ):
            sonuc = tiktok.foto_yayinla(
                ["https://cdn.example.com/1.jpg"],
                baslik="Test Başlık",
                hazir_video_yolu=fake_video,
            )

        self.assertTrue(sonuc["durum"])
        self.assertEqual(sonuc["publish_id"], "vid_pub_123")
        mock_uret.assert_not_called()
        mock_video_yukle.assert_called_once_with(fake_video, baslik="Test Başlık", etiketler=None)

    @patch("src.telegram_bot.mesaj_gonder")
    def test_hata_bildir_son_hata_txt_fallback_ve_id_tamamlama(self, mock_gonder):
        """hata_bildir boş hata ve ID durumunda son_hata.txt ve veritabanından teşhis koymalıdır."""
        h_id = db.haber_kaydet(
            kaynak="Test",
            orijinal_baslik="Hata Test Başlığı",
            orijinal_url="https://example.com/hata",
            onem_puani=8,
        )
        db.haber_guncelle(h_id, manset="Hata Test Başlığı", durum="onay_bekliyor")
        # Modülün kendi yolu: test modunda geçici dizin (config.veri_yolu); depodaki data/ klasörüne yazılmaz.
        son_hata_dosyasi = hata_bildir.SON_HATA_YOLU
        son_hata_dosyasi.parent.mkdir(parents=True, exist_ok=True)
        son_hata_dosyasi.write_text("TikTok API token invalid: access_token_invalid", encoding="utf-8")

        mock_gonder.return_value = {"message_id": 888}

        try:
            res = hata_bildir.telegrama_hata_bildir(
                islem_adi="Yayınla",
                istisna=None,
                ek_bilgi="",
                tur="haber",
                ref_id="",
            )
            self.assertTrue(res)
            mock_gonder.assert_called_once()
            gonderilen_metin = mock_gonder.call_args[0][0]
            self.assertIn("TikTok API erişim yetkisinin", gonderilen_metin)
        finally:
            son_hata_dosyasi.unlink(missing_ok=True)

    def test_hata_bildir_meta_checkpoint_teshisi(self):
        """Meta checkpoint (error_subcode 459) hatasında spesifik yönlendirmenin yapıldığını doğrular."""
        hata_raw = (
            '{"error": {"message": "You cannot access the app till you log in to www.facebook.com and follow the instructions given.", '
            '"type": "OAuthException", "code": 190, "error_subcode": 459, '
            '"error_data": "{\\"checkpoint_url\\":\\"https:\\\\/\\\\/www.facebook.com\\"}"}}'
        )
        tani = hata_bildir.hatayi_analiz_et(hata_raw)
        self.assertTrue(tani["tanindi"])
        self.assertIn("checkpoint", tani["ne_oldu"].lower())
        self.assertIn("www.facebook.com", tani["ne_yapilir"])
        self.assertEqual(tani["eylem"], "yeniden_yayinla")

    def test_hata_bildir_youtube_byte_uyusmazligi_teshisi(self):
        """YouTube Content-Range bayt uyuşmazlığı hatasında spesifik yönlendirmenin yapıldığını doğrular."""
        hata_raw = (
            "Video yüklenemedi [400]: Invalid request.  There were 2715152 byte(s) (or more) in the request body.  "
            "There should have been 2713945 byte(s) according to the Content-Range header."
        )
        tani = hata_bildir.hatayi_analiz_et(hata_raw)
        self.assertTrue(tani["tanindi"])
        self.assertIn("youtube", tani["ne_oldu"].lower())
        self.assertIn("bayt", tani["ne_oldu"].lower())
        self.assertIn("Shorts", tani["ne_yapilir"])
        self.assertEqual(tani["eylem"], "yeniden_yayinla")

    def test_haber_puanlama_azami_10_siniri(self):
        """Haber puanının en fazla 10 olacağı ve 10'u aşamayacağı doğrulanır."""
        from src import haber_puanlama
        # Çok sayıda yüksek puanlı kriter içeren haber
        baslik = "Resmi Gazete'de Yayımlandı: Silivri'de İmar ve Tapu Harcı Düzenlemesi Yürürlüğe Girdi"
        ozet = "Yargıtay emsal kararı ve BDDK genelgesi ile kira artış oranı yüzde 25 olarak belirlendi. Başvuru süresi 30 gün."
        d = haber_puanlama.degerlendir(baslik, ozet, yas_saat=2.0)
        self.assertTrue(d.gecti)
        self.assertLessEqual(d.puan, 10, f"Haber puanı 10'u aşmamalıdır, gelen: {d.puan}")
        self.assertGreaterEqual(d.puan, 7)

    def test_icerik_onceki_mesajlarini_temizle_albumu_korur(self):
        """Hatırlatma durumunda tur='haber' temizlendiğinde 'haber_album' mesajlarının korunduğu doğrulanır."""
        h_id = db.haber_kaydet(
            kaynak="Test", orijinal_baslik="Test Başlık", orijinal_url="https://example.com/test",
            orijinal_ozet="Özet", makale_metni="Metin", yayin_tarihi="2026-10-06T00:00:00",
            kategori="S1", onem_puani=8
        )
        # 1 adet albüm mesajı ve 1 adet onay kartı mesajı ekle
        db.onay_istegi_kaydet("haber_album", str(h_id), 8881, 1001)
        db.onay_istegi_kaydet("haber", str(h_id), 8882, 1001)

        with patch("src.telegram_bot.mesaji_sil", return_value=True) as mock_sil:
            silinen = telegram_bot.icerik_onceki_mesajlarini_temizle("haber", h_id)

        # Yalnızca kart silinmeli, albüm silinmemeli
        self.assertEqual(silinen, 1)
        mock_sil.assert_called_once_with(8882)

        # haber_album kaydı hala bekliyor durumunda kalmalı
        kalan_album = db.onay_mesajlarini_getir("haber_album", str(h_id))
        self.assertIn(8881, kalan_album)

    def test_icerik_incele_gonder_gorselli(self):
        """icerik_incele_gonder haberin görseli varsa fotograf_gonder ile göndermelidir."""
        h_id = db.haber_kaydet(
            kaynak="Test", orijinal_baslik="Görselli Haber", orijinal_url="https://example.com/gorsel",
            orijinal_ozet="Görsel özeti", makale_metni="Görsel metni", yayin_tarihi="2026-10-06T00:00:00",
            kategori="S2", onem_puani=9
        )
        db.haber_guncelle(h_id, gorsel_url="https://cdn.example.com/foto.jpg")
        with patch("src.telegram_bot.fotograf_gonder", return_value={"message_id": 999}) as mock_foto:
            res = telegram_bot.icerik_incele_gonder(h_id)
        self.assertTrue(res)
        mock_foto.assert_called_once()
        self.assertEqual(mock_foto.call_args[0][0], "https://cdn.example.com/foto.jpg")


    def test_vaka_rotasyondan_cikarildi_otomatik_calismaz(self):
        """Hukuki vaka analizinin otomatik döngüde veya takvimde yer almadığı doğrulanır."""
        from src import konu_bankasi
        self.assertNotIn("vaka", konu_bankasi.BILGILENDIRICI_FORMATLAR)
        for gun_idx, fmt in konu_bankasi.GUN_FORMATLARI.items():
            self.assertNotEqual(fmt, "vaka", f"Gün {gun_idx} vaka formatı olmamalıdır.")
        for gun_idx, cfg in konu_bankasi.TAKVIM.items():
            self.assertNotEqual(cfg.get("bicim"), "B2", f"Gün {gun_idx} otomatik vaka B2 olmamalıdır.")

    def test_fotograf_gonder_url_indirip_yukler(self):
        """fotograf_gonder HTTP URL aldığında baytları indirip dosya olarak yüklemelidir."""
        mock_resp_img = MagicMock()
        mock_resp_img.status_code = 200
        mock_resp_img.content = b"fake-jpg-content"

        mock_resp_tg = MagicMock()
        mock_resp_tg.status_code = 200
        mock_resp_tg.json.return_value = {"ok": True, "result": {"message_id": 777}}

        with patch("src.telegram_bot._bot_bilgileri", return_value=("fake_tok", "fake_chat")), \
             patch("requests.get", return_value=mock_resp_img) as mock_get, \
             patch("requests.post", return_value=mock_resp_tg) as mock_post:
            res = telegram_bot.fotograf_gonder("https://cdn.example.com/haber.jpg", caption="Haber")
            self.assertIsNotNone(res)
            mock_get.assert_called_once()
            # Post files parametresi taşımalıdır (Telegram'a bayt yüklemesi)
            self.assertIn("files", mock_post.call_args[1])
            self.assertIn("photo", mock_post.call_args[1]["files"])


if __name__ == "__main__":
    unittest.main()
