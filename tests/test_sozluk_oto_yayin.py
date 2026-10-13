"""Sözlük günlük otomatik yayın ve raporlama test paketi.

Test edilenler:
1. sozluk_oto_yayin_acik_mi() çevre değişkeni ve DB ayarı desteği.
2. hazirla.py CLI argümanlarının (--slot sozluk, --format sozluk, --oto-yayin) aktarımı.
3. sozluk_karti_hazirla_ve_sun() içinde oto_yayin parametresinin haber_onayina_sun'a iletilmesi.
4. _oto_yayinla() fonksiyonunda sözlük kartı için YouTube filtresi (video hatası önleme) ve görsel raporlama.
5. .github/workflows/hazirla.yml içindeki 12:30 TR (09:30 UTC) cron zamanlaması ve runner mantığı.
"""

import os

os.environ.setdefault("POSTEDM_TEST_MODU", "1")

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import yaml

from src import db, telegram_bot


class TestSozlukOtoYayin(unittest.TestCase):

    def setUp(self):
        self.eski_env = os.environ.get("SOZLUK_OTO_YAYIN")
        if "SOZLUK_OTO_YAYIN" in os.environ:
            del os.environ["SOZLUK_OTO_YAYIN"]

    def tearDown(self):
        if self.eski_env is not None:
            os.environ["SOZLUK_OTO_YAYIN"] = self.eski_env
        elif "SOZLUK_OTO_YAYIN" in os.environ:
            del os.environ["SOZLUK_OTO_YAYIN"]

    def test_sozluk_oto_yayin_acik_mi_env(self):
        """SOZLUK_OTO_YAYIN=1 iken fonksiyon True dönmeli."""
        with patch.object(db, "ayar_oku", return_value=None):
            os.environ["SOZLUK_OTO_YAYIN"] = "1"
            self.assertTrue(telegram_bot.sozluk_oto_yayin_acik_mi())

            os.environ["SOZLUK_OTO_YAYIN"] = "true"
            self.assertTrue(telegram_bot.sozluk_oto_yayin_acik_mi())

            os.environ["SOZLUK_OTO_YAYIN"] = "0"
            self.assertFalse(telegram_bot.sozluk_oto_yayin_acik_mi())

    def test_sozluk_oto_yayin_acik_mi_db(self):
        """DB'de sozluk_oto_yayin='1' iken ortam değişkeni olmasa bile True dönmeli."""
        with patch.object(db, "ayar_oku", side_effect=lambda k: "1" if k == "sozluk_oto_yayin" else None):
            self.assertTrue(telegram_bot.sozluk_oto_yayin_acik_mi())

        with patch.object(db, "ayar_oku", return_value="0"):
            self.assertFalse(telegram_bot.sozluk_oto_yayin_acik_mi())

    def test_oto_yayinla_sozluk_gorsel_ve_hedef_filtresi(self):
        """Sözlük için YouTube video kanalı elenmeli, görsel Telegram'a zengin başlıkla iletilmeli."""
        haber = {
            "id": 999,
            "manset": "ZİLYETLİK NEDİR?",
            "detay_metni": '{"format_turu": "sozluk", "terim": "ZİLYETLİK"}',
            "kaynak": "EDM Sözlük Kartı // SZ-001",
        }
        slaytlar = ["/tmp/sozluk_slayt_1.jpg"]

        with patch("src.telegram.album.medya_grubu_gonder") as mock_medya, \
             patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = "POSTEDM_SONUC=OK"
            mock_run.return_value = mock_proc

            basarili = telegram_bot._oto_yayinla(haber_id=999, slayt_yollari=slaytlar, haber=haber)
            self.assertTrue(basarili)

            # 1. Medya grubu gönderim kontrolü (görsel Telegram'a düşmeli)
            mock_medya.assert_called_once()
            caption = mock_medya.call_args[1].get("caption", "")
            self.assertIn("EDM EMLAK SÖZLÜĞÜ // OTOMATİK YAYIN", caption)
            self.assertIn("#999", caption)
            self.assertIn("ZİLYETLİK NEDİR?", caption)

            # 2. Komut ve hedef kontrolü (YouTube olmamalı, IG/Threads/Story/TikTok/FB olmalı)
            mock_run.assert_called_once()
            komut = mock_run.call_args[0][0]
            hedef_idx = komut.index("--hedef") + 1
            hedef_str = komut[hedef_idx]

            self.assertNotIn("youtube", hedef_str)
            self.assertIn("ig", hedef_str)
            self.assertIn("threads", hedef_str)
            self.assertIn("story", hedef_str)

    def test_sozluk_karti_hazirla_ve_sun_oto_yayin_iletme(self):
        """oto_yayin=True parametresi verildiğinde haber_onayina_sun'a oto_yayin=True gitmeli."""
        sahte_kart = {
            "kod": "SZ-001",
            "terim": "ZİLYETLİK",
            "kategori_kodu": "hukuk",
            "kategori": "HUKUK",
            "tanim": "Fiili hakimiyet",
            "puf": ["Önemli"],
            "mevzuat": "TMK md. 973",
            "dayanak_alintisi": "zilyetlik",
        }

        with patch("src.telegram.akislar.sozluk._sozluk_karti_sec", return_value=(sahte_kart, True)), \
             patch("src.telegram.ayarlar.bot_duraklatildi_mi", return_value=(False, "")), \
             patch("src.db.ayar_oku", return_value="2020-01-01"), \
             patch("src.db._baglanti_al") as mock_conn, \
             patch("src.konu_bankasi.kullanildi_isaretle"), \
             patch("src.telegram.istemci.mesaj_gonder"), \
             patch("src.telegram.akislar.onay.haber_onayina_sun", return_value=True) as mock_onay:

            # Cursor mock
            cursor = MagicMock()
            cursor.lastrowid = 123
            conn_inst = MagicMock()
            conn_inst.execute.return_value = cursor
            mock_conn.return_value.__enter__.return_value = conn_inst

            sonuc = telegram_bot.sozluk_karti_hazirla_ve_sun(oto_yayin=True)
            self.assertTrue(sonuc)

            # haber_onayina_sun çağrısında oto_yayin=True olduğunu doğrula
            mock_onay.assert_called_once_with(123, oto_yayin=True)

    def test_workflow_hazirla_yml_sozluk_zamanlama_ve_adim(self):
        """.github/workflows/hazirla.yml dosyasında 12:30 TR cron'u ve --oto-yayin bayrağı olmalı."""
        yml_yolu = Path(__file__).resolve().parent.parent / ".github/workflows/hazirla.yml"
        self.assertTrue(yml_yolu.exists(), "hazirla.yml bulunamadı")

        metin = yml_yolu.read_text(encoding="utf-8")
        parsed = yaml.safe_load(metin)

        on_block = parsed.get("on") or parsed.get(True) or {}
        schedules = [s.get("cron") for s in on_block.get("schedule", []) if "cron" in s]
        self.assertIn("30 9 * * *", schedules, "hazirla.yml içinde 30 9 * * * (12:30 TR) cron'u eksik!")

        # 2. Çalıştırma adımı kontrolü
        self.assertIn("30 9 * * *", metin)
        # --oto-yayin yalnız zamanlanmış koşuda eklenir (elle tetiklenen sözlük onay kartıyla düşer): davranış tests/test_hazirla_yml_elle_tetik.py'de gerçek kabukla sınanır
        self.assertIn('OTO="--oto-yayin"', metin)
        self.assertIn('[ "$ZAMANLANMIS" = "true" ]', metin)
        self.assertIn("python scripts/hazirla.py --slot sozluk $OTO", metin)


if __name__ == "__main__":
    unittest.main()
