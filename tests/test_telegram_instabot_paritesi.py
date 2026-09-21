"""
tests/test_telegram_instabot_paritesi.py — Instabot Seviyesi Butonlar, Canlı Yayın Takibi,
Açıklama Metni Kutusu, Reels Video Gönderimi ve Kesintisiz 9:16 Çerçeveleme Testleri.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import db, telegram_bot, video


class TestTelegramInstabotParitesi(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_db = Path(self.tmpdir.name) / "test_instabot_parite.db"
        self.db_patcher = patch("src.db.DB_YOLU", self.tmp_db)
        self.db_patcher.start()
        db.tablolari_olustur()

    def tearDown(self):
        self.db_patcher.stop()
        self.tmpdir.cleanup()

    def test_aciklama_metni_kutusu_pre_code_format(self):
        """Açıklama metninin Telegram tek dokunuşla kopyalanabilir <pre><code> bloğu ürettiği doğrulanır."""
        raw_text = "EDM Yapı Gayrimenkul\nTapu Harcı & Miras Rehberi 2026\n#emlak #tapu"
        kutu = telegram_bot.aciklama_metni_kutusu(raw_text)
        self.assertIn("📝 <b>Açıklama Metni (Kopyalamak için dokunun):</b>", kutu)
        self.assertIn("<pre><code>", kutu)
        self.assertIn("</code></pre>", kutu)
        self.assertIn("EDM Yapı Gayrimenkul", kutu)

    def test_kanal_toggle_ve_secili_kanallari_cikar(self):
        """Kanal toggle ve aktif kanalları çıkarma mekanizması test edilir."""
        # Başlangıç klavyesi (varsayılan: reels kapalı, ig açık)
        klavye = telegram_bot.kanal_butonlari()
        secili = telegram_bot.secili_kanallari_cikar(klavye)
        self.assertIn("ig", secili)
        self.assertIn("story", secili)
        self.assertNotIn("reels", secili)

        # Reels'i aç (toggle) -> Kural gereği IG otomatik deaktif olmalıdır
        yeni_klavye = telegram_bot.kanal_toggle(klavye, "reels")
        secili_sonra = telegram_bot.secili_kanallari_cikar(yeni_klavye)
        self.assertIn("reels", secili_sonra)
        self.assertNotIn("ig", secili_sonra)

        # IG'yi tekrar aç (toggle) -> Kural gereği Reels otomatik deaktif olmalıdır
        yeni_klavye_2 = telegram_bot.kanal_toggle(yeni_klavye, "ig")
        secili_sonra_2 = telegram_bot.secili_kanallari_cikar(yeni_klavye_2)
        self.assertIn("ig", secili_sonra_2)
        self.assertNotIn("reels", secili_sonra_2)

    @patch("src.telegram_bot._istek")
    def test_menuyu_degistir(self, mock_istek):
        """editMessageReplyMarkup çağrısının metne dokunmadan menüyü değiştirdiği doğrulanır."""
        mock_istek.return_value = {"message_id": 12345}
        yeni_menu = {"inline_keyboard": [[{"text": "Test", "callback_data": "test"}]]}
        sonuc = telegram_bot.menuyu_degistir(12345, yeni_menu)
        self.assertTrue(sonuc)
        mock_istek.assert_called_once_with(
            "editMessageReplyMarkup",
            message_id=12345,
            reply_markup=yeni_menu,
        )

    def test_yayin_durum_metni_ve_progress_bar(self):
        """Canlı yayın durumu metni, Instabot progress bar formatı ([▰▰▱▱] %50) ve platform durumları doğrulanır."""
        durum_haritasi = {
            "instagram": "✅ Yayında",
            "threads": "⏳ Yükleniyor...",
            "facebook": "⏱️ Sırada",
            "reels": "⏱️ Sırada",
        }
        metin = telegram_bot.yayin_durum_metni_olustur(
            baslik="Hisseli Tapu Satışı Rehberi",
            adim=1,
            toplam_adim=4,
            durum_haritasi=durum_haritasi,
            baslangic_ts=100.0,
            is_telafi=False,
        )
        self.assertIn("⏳ <b>YAYIN DAĞITIMI SÜRÜYOR", metin)
        self.assertIn("<code>[▰▱▱▱] %25 (1/4)</code>", metin)
        self.assertIn("• <b>Instagram Akış (4:5):</b> ✅ Yayında", metin)
        self.assertIn("• <b>Threads (@edmyapigayrimenkul):</b> ⏳ Yükleniyor...", metin)
        self.assertIn("• <b>Facebook (Gönderi):</b> ⏱️ Sırada", metin)
        self.assertIn("• <b>Instagram Reels (9:16):</b> ⏱️ Sırada", metin)

    @patch("src.telegram_bot.mesaji_guncelle")
    def test_canli_yayin_durumu_guncelle(self, mock_guncelle):
        """canli_yayin_durumu_guncelle fonksiyonunun onay mesajını anında güncellediği doğrulanır."""
        mock_guncelle.return_value = True
        durum_haritasi = {"instagram": "✅ Yayında", "reels": "✅ Yayında"}
        sonuc = telegram_bot.canli_yayin_durumu_guncelle(
            mesaj_id=987,
            baslik="Test",
            adim=2,
            toplam_adim=2,
            durum_haritasi=durum_haritasi,
        )
        self.assertTrue(sonuc)
        mock_guncelle.assert_called_once()
        guncellenen_metin = mock_guncelle.call_args[0][1]
        self.assertIn("[▰▰] %100 (2/2)", guncellenen_metin)
        self.assertIn("✅ <b>TÜM PLATFORMLARA AKTARIM TAMAMLANDI!</b>", guncellenen_metin)

    @patch("src.telegram_bot.mesaji_guncelle")
    @patch("src.telegram_bot.mesaj_gonder")
    def test_sonucu_yaz(self, mock_gonder, mock_guncelle):
        """Yayın sonucu yazılırken hem onay mesajının güncellendiği hem de bildir=True ise yeni mesaj atıldığı test edilir."""
        mock_guncelle.return_value = True
        mock_gonder.return_value = {"message_id": 999}
        markup = {"inline_keyboard": [[{"text": "📸 Instagram'da Gör", "url": "https://instagram.com/p/123"}]]}

        sonuc = telegram_bot.sonucu_yaz(
            mesaj_id=555,
            metin="🎉 <b>YAYIN BAŞARIYLA TAMAMLANDI</b>",
            bildir=True,
            reply_markup=markup,
        )
        self.assertTrue(sonuc)
        mock_guncelle.assert_called_once_with(555, "🎉 <b>YAYIN BAŞARIYLA TAMAMLANDI</b>", reply_markup=markup)
        mock_gonder.assert_called_once_with("🎉 <b>YAYIN BAŞARIYLA TAMAMLANDI</b>", reply_markup=markup)

    def test_kesintisiz_9_16_cerceveleme_kurali(self):
        """
        Kullanıcı Kuralı Testi:
        9:16 formatında alt ve üst kısımlarda yapay geçiş, blur, vignette veya karartma perdesi olmamalı;
        üst renk kesintisiz y=0'a, alt renk ise kesintisiz y=1920'ye kadar aynı tonda uzatılmalıdır.
        """
        # 1080x1350 boyutunda, üst yarısı bordo (114, 24, 39), alt yarısı beyaz (255, 255, 255) kart
        w, h = 1080, 1350
        kart = Image.new("RGB", (w, h), (255, 255, 255))
        for x in range(w):
            for y in range(400):
                kart.putpixel((x, y), (114, 24, 39))

        cerceveli = video._cercevele_9_16(kart)
        self.assertEqual(cerceveli.size, (1080, 1920))

        # En üst satırlar (y=0, y=50, y=284) kartın en üst satırının (114, 24, 39) birebir kopyası olmalı
        # Karartma, blur veya solma olmamalı!
        for test_y in [0, 50, 150, 280]:
            pixel = cerceveli.getpixel((540, test_y))
            self.assertEqual(pixel, (114, 24, 39), f"y={test_y} noktasında renk bozulmuş: {pixel}")

        # En alt satırlar (y=1635 .. 1919) kartın en alt satırının (255, 255, 255) birebir kopyası olmalı
        for test_y in [1635, 1750, 1919]:
            pixel = cerceveli.getpixel((540, test_y))
            self.assertEqual(pixel, (255, 255, 255), f"y={test_y} noktasında alt renk bozulmuş: {pixel}")

    def test_poller_ve_worker_tum_butonlar_kapsami(self):
        """Poller ve Worker'ın tüm instabot menü ve buton aksiyonlarını desteklediği doğrulanır."""
        poller_py = (KOK / "scripts/telegram_poller.py").read_text(encoding="utf-8")
        worker_js = (KOK / "worker/index.js").read_text(encoding="utf-8")

        zorunlu_aksiyonlar = [
            "kanal:",
            "yayin_menu:",
            "foto_menu:",
            "metin_menu:",
            "slayt_menu:",
            "format_uygula:",
            "yayinla",
            "yayinla_sonra:",
            "manuel_paket",
            "foto_gercek",
            "foto_stok",
            "foto_ai",
            "foto_editoryal",
            "metin_ozetle",
            "metin_detaylandir",
            "metin_yenile",
            "ertele",
            "iptal",
            "cope_at",
            "retry_kanal:",
        ]

        for aksiyon in zorunlu_aksiyonlar:
            self.assertIn(aksiyon, poller_py, f"Poller eksik aksiyon: {aksiyon}")
            self.assertIn(aksiyon, worker_js, f"Worker eksik aksiyon: {aksiyon}")


if __name__ == "__main__":
    unittest.main()
