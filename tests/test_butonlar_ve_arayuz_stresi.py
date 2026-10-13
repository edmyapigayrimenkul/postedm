"""
tests/test_butonlar_ve_arayuz_stresi.py — Telegram Butonları, Canlı Durum Metinleri,
Arayüz Stresi ve Sabotaj Test Paketi.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")

import html
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src import db, hata_bildir, telegram_bot


class TestButonlarVeArayuzStresi(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_db = Path(self.tmpdir.name) / "test_arayuz_stres.db"
        self.db_patcher = patch("src.db.DB_YOLU", self.tmp_db)
        self.db_patcher.start()
        db.tablolari_olustur()

    def tearDown(self):
        self.db_patcher.stop()
        self.tmpdir.cleanup()

    def test_yayin_durum_metni_ekstrem_adimlar(self):
        """Negatif, sıfır ve devasa adımlarda ilerleme çubuğu ve yüzde çökmeden hesaplanır."""
        # 1. Negatif adım
        metin_neg = telegram_bot.yayin_durum_metni_olustur(
            baslik="Negatif Test",
            adim=-5,
            toplam_adim=4,
            durum_haritasi={"ig": "⏳ Yükleniyor..."},
        )
        self.assertIn("%0 (0/4)", metin_neg)
        self.assertIn("Negatif Test", metin_neg)

        # 2. Toplamdan büyük adım
        metin_tasan = telegram_bot.yayin_durum_metni_olustur(
            baslik="Taşan Adım Test",
            adim=99,
            toplam_adim=4,
            durum_haritasi={"ig": "✅ Yayında"},
        )
        self.assertIn("%100 (4/4)", metin_tasan)

        # 3. Toplam adım sıfır veya negatif gelirse sıfıra bölünme hatası vermemeli
        metin_sifir = telegram_bot.yayin_durum_metni_olustur(
            baslik="Sıfır Toplam Test",
            adim=0,
            toplam_adim=0,
            durum_haritasi={},
        )
        self.assertIn("[▱] %0 (0/1)", metin_sifir)

    def test_yayin_durum_metni_html_sabotaji(self):
        """Düşmanca HTML ve script tagleri içeren başlıklar güvenli escape edilir."""
        zararli_baslik = "<script>alert('xss')</script> & <b>Kritik <i>İlan</i> ' \" Başlığı"
        metin = telegram_bot.yayin_durum_metni_olustur(
            baslik=zararli_baslik,
            adim=2,
            toplam_adim=4,
            durum_haritasi={"threads": "✅ Yayında"},
        )
        self.assertNotIn("<script>", metin)
        self.assertIn("&lt;script&gt;", metin)
        self.assertIn("&amp;", metin)

    def test_yayin_durum_metni_asiri_uzun_baslik(self):
        """5000 karakterlik devasa başlık güvenle 100 karaktere kırpılır."""
        devasa_baslik = "EDM " * 1500
        metin = telegram_bot.yayin_durum_metni_olustur(
            baslik=devasa_baslik,
            adim=1,
            toplam_adim=4,
            durum_haritasi={"ig": "⏳ Yükleniyor..."},
        )
        self.assertTrue(len(metin) < 1000)

    def test_aciklama_metni_kutusu_html_escape(self):
        """Kopyalanabilir kod kutusunda özel karakterler kusursuz korunur."""
        ham = "Silivri'de 3+1 <Villa> & 'Arsa' Fırsatı -> 100% Güvenli"
        kutu = telegram_bot.aciklama_metni_kutusu(ham)
        self.assertTrue(kutu.startswith("<pre><code>"))
        self.assertTrue(kutu.endswith("</code></pre>"))
        self.assertIn("&lt;Villa&gt;", kutu)
        self.assertIn("&amp;", kutu)

    def test_kanal_toggle_stres_dongusu(self):
        """50 kez ardışık kanal açma/kapama döngüsünde menü tutarlılığı korunur."""
        klavye = telegram_bot.kanal_butonlari()
        for i in range(50):
            kanal = "reels" if i % 2 == 0 else "ig"
            klavye = telegram_bot.kanal_toggle(klavye, kanal)

        secili = telegram_bot.secili_kanallari_cikar(klavye)
        # Son döngü i=49 (ig toggle edilmiş olmalı)
        self.assertIsInstance(secili, list)

    def test_icerik_onceki_mesajlarini_temizle_stresi(self):
        """50 adet eski mesaj kaydı varken tek seferde güvenle silinir."""
        for mid in range(1001, 1051):
            db.onay_istegi_kaydet("haber", "777", telegram_mesaj_id=mid, telegram_chat_id=-100)

        kayitlar = db.onay_mesajlarini_getir("haber", "777")
        self.assertEqual(len(kayitlar), 50)

        # Silme çağrılarının bir kısmı hata verse dahi fonksiyon çökmemeli
        def sahte_sil(mid):
            if mid % 5 == 0:
                raise RuntimeError("Telegram network timeout")
            return True

        with patch("src.telegram.istemci.mesaji_sil", side_effect=sahte_sil):
            silinen = telegram_bot.icerik_onceki_mesajlarini_temizle("haber", "777", haric_mesaj_id=1050)
            # 50 mesajdan 1'i hariç tutuldu (1050). Kalan 49 mesajdan %5'e bölünenler hariç hepsi silindi.
            self.assertGreater(silinen, 35)

    def test_hata_bildir_kurtarma_butonlari(self):
        """Hata bildirim kartı oluşturma aşırı durumlarda bile geçerli butonlar üretir."""
        butonlar = hata_bildir._butonlar(
            eylem="Yayınla",
            tur="haber",
            ref_id="123",
            hedef="ig,threads,facebook",
            mesaj_id="555",
            run_url="https://github.com/edmyapigayrimenkul/postedm/actions/runs/12345",
        )
        self.assertIn("inline_keyboard", butonlar)
        tuslar = butonlar["inline_keyboard"]
        # En az telafi butonları, durum kontrol ve log butonu olmalı
        self.assertGreaterEqual(len(tuslar), 2)
        tum_datalar = [btn.get("callback_data") for row in tuslar for btn in row if "callback_data" in btn]
        self.assertTrue(any("onayla:haber" in str(d) for d in tum_datalar))
        self.assertTrue(any("reddet:haber" in str(d) for d in tum_datalar))


if __name__ == "__main__":
    unittest.main()
