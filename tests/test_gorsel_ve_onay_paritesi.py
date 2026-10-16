"""
tests/test_gorsel_ve_onay_paritesi.py — Haber Dışı Tüm İçeriklerin Görsel ve Onay Kartı Parite Testleri.

Tüm içerik türleri (sözlük, nedir doğrusu, vaka, net cevap, reels, ilan, otorite vb.):
1. Görsel olarak (medya grubu / fotoğraf) Telegram'a gönderilir.
2. Kart metni haberle birebir aynı yapıda (Kategori, Dayanak, Manşet, Önem Puanı, İçerik No, <pre><code>caption</code></pre>, onay sorusu) üretilir.
3. Alt menü haberle birebir aynı interaktif yapıda (ana_menu: kanal butonları, yayınla, ses, manuel paket, foto, metin, slayt, ertele, iptal, çöpe at) üretilir.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import db, telegram_bot


class TestGorselVeOnayParitesi(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_db = Path(self.tmpdir.name) / "test_parite.db"
        self.db_patcher = patch("src.db.DB_YOLU", self.tmp_db)
        self.db_patcher.start()
        db.tablolari_olustur()

    def tearDown(self):
        self.db_patcher.stop()
        self.tmpdir.cleanup()

    @patch("src.telegram.medya_istek.fotograf_gonder")
    def test_medya_grubu_tekil_gorselde_fotograf_gonderir(self, mock_foto):
        """Telegram sendMediaGroup min 2 istediği için tekil slayt (sözlük) fotograf_gonder'e yönlendirilmeli."""
        mock_foto.return_value = {"message_id": 777}
        with patch("src.telegram.istemci._bot_bilgileri", return_value=("token123", "-100123")):
            res = telegram_bot.medya_grubu_gonder(["/tmp/tek_slayt.jpg"], caption="Test Caption")
            self.assertEqual(res, [777])
            mock_foto.assert_called_once_with("/tmp/tek_slayt.jpg", caption="Test Caption")

    @patch("src.telegram.istemci.mesaj_gonder")
    @patch("src.telegram.album.medya_grubu_gonder")
    @patch("src.yeni_formatlar.slaytlari_uret")
    def test_sozluk_onay_karti_ve_buton_paritesi(self, mock_slaytlar, mock_medya, mock_mesaj):
        """Sözlük içeriği görsel üretip haberle birebir aynı metin ve buton yapısıyla onaya sunulmalı."""
        mock_slaytlar.return_value = [Path(self.tmpdir.name) / "sozluk_01.jpg"]
        mock_medya.return_value = [801]
        mock_mesaj.return_value = {"message_id": 802}

        detay = {
            "format_turu": "sozluk",
            "terim": "İNTİFA HAKKI",
            "tanim_metni": "Bir gayrimenkulden tam yararlanma hakkı.",
            "puf_maddeleri": ["Kişiye sıkı sıkıya bağlıdır.", "Devredilemez."],
            "manset": "İNTİFA HAKKI",
            "yasal_dayanak": "4721 sayılı Türk Medeni Kanunu md. 794",
            "_brief": {"mevzuat": "4721 sayılı Türk Medeni Kanunu md. 794"},
        }
        with db._baglanti_al() as conn:
            cur = conn.execute(
                """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, eklenme_tarihi,
                                         onem_puani, kategori, manset, detay_metni, durum)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'yeni')""",
                ("EDM Sözlük", "İNTİFA HAKKI", "edm://sozluk/1", "2026-10-03T00:00:00Z",
                 8, "TAPU_VE_HUKUK", "İNTİFA HAKKI NEDİR?", json.dumps(detay))
            )
            haber_id = cur.lastrowid
            conn.commit()

        with patch("src.telegram.istemci._bot_bilgileri", return_value=("tok", "-100")):
            ok = telegram_bot._haber_onayina_sun(haber_id)
            self.assertTrue(ok)

        # 1. Medya albümü / fotoğraf görseli gönderildi
        mock_medya.assert_called_once()
        self.assertIn("GAYRİMENKUL SÖZLÜĞÜ", mock_medya.call_args[1]["caption"])

        # 2. Onay mesajı yapısı haberle birebir aynı
        msg_text = mock_mesaj.call_args[0][0]
        self.assertIn("📖 <b>GAYRİMENKUL SÖZLÜĞÜ ONAY BEKLİYOR (#", msg_text)
        self.assertIn("<b>Kategori:</b> GAYRİMENKUL SÖZLÜĞÜ", msg_text)
        self.assertIn("<b>Dayanak:</b> 4721 sayılı Türk Medeni Kanunu md. 794", msg_text)
        self.assertIn("<b>Manşet:</b> İNTİFA HAKKI NEDİR?", msg_text)
        self.assertIn("<b>Önem Puanı:</b> 8/10", msg_text)
        self.assertIn(f"<b>İçerik No:</b> #{haber_id}", msg_text)
        self.assertIn("<pre><code>", msg_text)
        self.assertIn("Bu içeriği onaylıyor musunuz?", msg_text)

        # 3. Buton yapısı haberle birebir aynı ana_menu
        markup = mock_mesaj.call_args[1]["reply_markup"]["inline_keyboard"]
        btn_callbacks = [b["callback_data"] for row in markup for b in row]
        self.assertIn("kanal:ig", btn_callbacks)
        self.assertIn("kanal:story", btn_callbacks)
        self.assertIn("yayin_menu:1", btn_callbacks)
        self.assertIn("ses_menu:1", btn_callbacks)
        self.assertIn("manuel_paket", btn_callbacks)
        self.assertIn("foto_menu:1", btn_callbacks)
        self.assertIn("metin_menu:1", btn_callbacks)
        self.assertIn("slayt_menu:1", btn_callbacks)
        self.assertNotIn("ertele", btn_callbacks)
        self.assertIn("iptal", btn_callbacks)
        self.assertIn("cope_at", btn_callbacks)

    @patch("src.telegram.istemci.mesaj_gonder")
    @patch("src.telegram.album.medya_grubu_gonder")
    @patch("src.yeni_formatlar.slaytlari_uret")
    def test_nedir_dogrusu_onay_karti_paritesi(self, mock_slaytlar, mock_medya, mock_mesaj):
        """Nedir Doğrusu formatı görsel üretip standart onay kartı ve buton yapısını kullanmalı."""
        mock_slaytlar.return_value = [Path(self.tmpdir.name) / "nd_01.jpg", Path(self.tmpdir.name) / "nd_02.jpg"]
        mock_medya.return_value = [811, 812]
        mock_mesaj.return_value = {"message_id": 813}

        detay = {
            "format_turu": "nedir_dogrusu",
            "yanlis_metin": "Hisseli tapu satılamaz.",
            "dogru_metin": "Hisseli tapuda pay satışı noter bildirimiyle yapılabilir.",
            "manset": "HİSSELİ TAPU SATILIR MI?",
            "yasal_dayanak": "4721 sayılı TMK md. 732",
            "_brief": {"mevzuat": "4721 sayılı TMK md. 732"},
        }
        with db._baglanti_al() as conn:
            cur = conn.execute(
                """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, eklenme_tarihi,
                                         onem_puani, kategori, manset, detay_metni, durum)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'yeni')""",
                ("EDM Doğrulama", "Hisseli Tapu", "edm://dogrusu/1", "2026-10-03T00:00:00Z",
                 9, "TAPU_VE_HUKUK", "HİSSELİ TAPU SATILIR MI?", json.dumps(detay))
            )
            haber_id = cur.lastrowid
            conn.commit()

        with patch("src.telegram.istemci._bot_bilgileri", return_value=("tok", "-100")):
            ok = telegram_bot._haber_onayina_sun(haber_id)
            self.assertTrue(ok)

        msg_text = mock_mesaj.call_args[0][0]
        self.assertIn("⚖️ <b>NEDİR DOĞRUSU İÇERİĞİ ONAY BEKLİYOR (#", msg_text)
        self.assertIn("<b>Kategori:</b> NEDİR DOĞRUSU?", msg_text)
        self.assertIn("<b>Dayanak:</b> 4721 sayılı TMK md. 732", msg_text)
        self.assertIn("<b>Önem Puanı:</b> 9/10", msg_text)

    @patch("src.telegram.istemci.mesaj_gonder")
    @patch("src.telegram.album.medya_grubu_gonder")
    @patch("src.yeni_formatlar.slaytlari_uret")
    def test_vaka_analizi_onay_karti_paritesi(self, mock_slaytlar, mock_medya, mock_mesaj):
        """Vaka analizi formatı görsel üretip standart onay kartı ve buton yapısını kullanmalı."""
        mock_slaytlar.return_value = [Path(self.tmpdir.name) / "vaka_01.jpg", Path(self.tmpdir.name) / "vaka_02.jpg"]
        mock_medya.return_value = [821, 822]
        mock_mesaj.return_value = {"message_id": 823}

        detay = {
            "format_turu": "vaka",
            "manset": "ŞUFA DAVASINDA KRİTİK SÜRE",
            "yasal_dayanak": "Yargıtay Hukuk Genel Kurulu 2024/112 E.",
        }
        with db._baglanti_al() as conn:
            cur = conn.execute(
                """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, eklenme_tarihi,
                                         onem_puani, kategori, manset, detay_metni, durum)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'yeni')""",
                ("EDM Hukuk", "Şufa Davası", "edm://vaka/1", "2026-10-03T00:00:00Z",
                 9, "TAPU_VE_HUKUK", "ŞUFA DAVASINDA KRİTİK SÜRE", json.dumps(detay))
            )
            haber_id = cur.lastrowid
            conn.commit()

        with patch("src.telegram.istemci._bot_bilgileri", return_value=("tok", "-100")):
            ok = telegram_bot._haber_onayina_sun(haber_id)
            self.assertTrue(ok)

        msg_text = mock_mesaj.call_args[0][0]
        self.assertIn("📂 <b>VAKA ANALİZİ ONAY BEKLİYOR (#", msg_text)
        self.assertIn("<b>Kategori:</b> HUKUKİ VAKA ANALİZİ", msg_text)

    @patch("src.telegram.istemci.mesaj_gonder")
    @patch("src.telegram.album.medya_grubu_gonder")
    @patch("src.yeni_formatlar.slaytlari_uret")
    def test_reels_onay_karti_ve_buton_paritesi(self, mock_slaytlar, mock_medya, mock_mesaj):
        """Reels 9:16 formatı görsel slayt üretip haberle birebir aynı yapıda onay kartı ve reels kanallarıyla sunulmalı."""
        mock_slaytlar.return_value = [Path(self.tmpdir.name) / f"reels_{i}.jpg" for i in range(1, 6)]
        mock_medya.return_value = [901, 902, 903, 904, 905]
        mock_mesaj.return_value = {"message_id": 906}

        detay = {
            "format_turu": "reels",
            "manset": "TAPU ALIRKEN BUNU YAPMAYIN",
            "yasal_dayanak": "EDM Hukuk Masası",
        }
        with db._baglanti_al() as conn:
            cur = conn.execute(
                """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, eklenme_tarihi,
                                         onem_puani, kategori, manset, detay_metni, durum)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'yeni')""",
                ("EDM Reels", "Tapu Uyarısı", "edm://reels/1", "2026-10-03T00:00:00Z",
                 8, "REELS", "TAPU ALIRKEN BUNU YAPMAYIN", json.dumps(detay))
            )
            haber_id = cur.lastrowid
            conn.commit()

        with patch("src.telegram.istemci._bot_bilgileri", return_value=("tok", "-100")):
            ok = telegram_bot._haber_onayina_sun(haber_id)
            self.assertTrue(ok)

        # Görsel albüm iletildi
        mock_medya.assert_called_once()
        self.assertIn("REELS SLAYTLARI", mock_medya.call_args[1]["caption"])

        # Kart metni haber standartlarında
        msg_text = mock_mesaj.call_args[0][0]
        self.assertIn("🎬 <b>GÜNCEL REELS İÇERİĞİ ONAY BEKLİYOR (#", msg_text)
        self.assertIn("<b>Kategori:</b> REELS &amp; VİDEO (9:16)", msg_text)
        self.assertIn("<b>Manşet:</b> TAPU ALIRKEN BUNU YAPMAYIN", msg_text)
        self.assertIn(f"<b>İçerik No:</b> #{haber_id}", msg_text)

        # Butonlar ana_menu formatında ve varsayılan reels kanalları açık
        markup = mock_mesaj.call_args[1]["reply_markup"]["inline_keyboard"]
        btn_texts = [b["text"] for row in markup for b in row]
        self.assertTrue(any("Reels" in t and "✅" in t for t in btn_texts))  # Reels seçili
        self.assertTrue(any("IG" in t and "⬜" in t for t in btn_texts))  # IG besleme kapalı

    @patch("src.telegram.istemci.mesaj_gonder")
    @patch("src.telegram.album.medya_grubu_gonder")
    @patch("src.make_image.ilan_kapak_slayti_ciz")
    @patch("src.make_image.ilan_detay_slayti_ciz")
    @patch("src.make_image.ilan_kapanis_slayti_ciz")
    def test_ilan_onay_karti_ve_ana_menu_paritesi(self, mock_k3, mock_k2, mock_k1, mock_medya, mock_mesaj):
        """Portföy ilanı 3'lü carousel üretip haberle birebir aynı metin ve ana_menu butonlarıyla sunulmalı."""
        mock_k1.return_value = Path(self.tmpdir.name) / "ilan_01.jpg"
        mock_k2.return_value = Path(self.tmpdir.name) / "ilan_02.jpg"
        mock_k3.return_value = Path(self.tmpdir.name) / "ilan_03.jpg"
        mock_medya.return_value = [951, 952, 953]
        mock_mesaj.return_value = {"message_id": 954}

        with db._baglanti_al() as conn:
            conn.execute(
                """INSERT INTO ilanlar (id, baslik, tip, ilce, mahalle, fiyat, para_birimi, durum)
                   VALUES ('101', 'Silivri Çanta 500m2 İmarlı Arsa', 'Arsa', 'Silivri', 'Çanta', 2500000, 'TRY', 'aktif')"""
            )
            conn.commit()

        with patch("src.telegram.istemci._bot_bilgileri", return_value=("tok", "-100")):
            ok = telegram_bot.ilan_postunu_hazirla_ve_sor("101")
            self.assertTrue(ok)

        # 1. 3'lü carousel albüm olarak gönderildi
        mock_medya.assert_called_once()
        self.assertIn("İLAN CAROUSEL", mock_medya.call_args[1]["caption"])

        # 2. Onay mesajı haberle birebir aynı yapıda
        msg_text = mock_mesaj.call_args[0][0]
        self.assertIn("🏡 <b>PORTFÖY İLANI ONAY BEKLİYOR (#101)</b>", msg_text)
        self.assertIn("<b>Kategori:</b> PORTFÖY İLANI", msg_text)
        self.assertIn("<b>Dayanak:</b> Silivri / Çanta · 2,5 mn ₺", msg_text)
        self.assertIn("<b>Manşet:</b> Silivri Çanta 500m2 İmarlı Arsa", msg_text)
        self.assertIn("<b>Önem Puanı:</b> 10/10", msg_text)
        self.assertIn("<b>İçerik No:</b> #101", msg_text)
        self.assertIn("<pre><code>", msg_text)
        self.assertIn("Bu içeriği onaylıyor musunuz?", msg_text)

        # 3. Butonlar haberle aynı ana_menu
        markup = mock_mesaj.call_args[1]["reply_markup"]["inline_keyboard"]
        btn_callbacks = [b["callback_data"] for row in markup for b in row]
        self.assertIn("kanal:ig", btn_callbacks)
        self.assertIn("yayin_menu:3", btn_callbacks)
        self.assertIn("ses_menu:3", btn_callbacks)
        self.assertIn("manuel_paket", btn_callbacks)
        self.assertNotIn("ertele", btn_callbacks)
        self.assertIn("iptal", btn_callbacks)
        self.assertIn("cope_at", btn_callbacks)


if __name__ == "__main__":
    unittest.main()
