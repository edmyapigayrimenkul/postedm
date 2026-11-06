"""
tests/test_otorite_stres_ve_sabotaj.py — Otorite İçerikleri (5 Format × 10 Alan) Kapsamlı Stres ve Sabotaj Testi.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")

import unittest
from pathlib import Path
from scripts.otorite_stres_testi import KONU_HAVUZU, OtoriteDenetci, veri_hazirla


class TestOtoriteStresVeSabotaj(unittest.TestCase):
    """5 temel format (b1, nedir_dogrusu, vaka, net_cevap, sozluk) için stres ve kalite testleri."""

    @classmethod
    def setUpClass(cls):
        cls.denetci = OtoriteDenetci()
        cls.formatlar = ["b1", "nedir_dogrusu", "vaka", "net_cevap", "sozluk"]

    def test_on_farkli_hukuki_alan_tanimli(self):
        """10 farklı hukuki & gayrimenkul alanı ve 20 konu tanımlı olmalı."""
        self.assertEqual(len(KONU_HAVUZU), 20)
        alanlar = {k["alan"] for k in KONU_HAVUZU}
        self.assertGreaterEqual(len(alanlar), 10)
        self.assertIn("Şufa & Hisseli Tapu", alanlar)
        self.assertIn("Kira Tahliye & İhtiyaç", alanlar)
        self.assertIn("Arsa, İmar, Ruhsat & Tiny House", alanlar)
        self.assertIn("Tarla, Kadastro, İfraz & Tevhid", alanlar)
        self.assertIn("Tapu Harcı, Düşük Bedel & Beyan", alanlar)
        self.assertIn("Kaparo, Bağlanma Parası & Satış Vaadi", alanlar)
        self.assertIn("Kat Mülkiyeti, Ortak Alan & Aidat", alanlar)
        self.assertIn("Gayrimenkul Finansı, İpotek & Ekspertiz", alanlar)
        self.assertIn("Miras Taksimi & Ortaklığın Giderilmesi", alanlar)

    def test_b1_risk_dosyasi_stres_ve_sabotaj(self):
        """B1 formatında 20 içerik tüm eksenlerde hatasız geçmeli."""
        for konu in KONU_HAVUZU:
            veri = veri_hazirla(konu, "b1")
            rapor = self.denetci.denetle(veri, "b1", konu)
            self.assertTrue(rapor["basarili"], f"B1 başarısız [{konu['id']}]: {rapor['hatalar']}")
            self.assertEqual(rapor["puanlar"]["3_tasarim"], 10)
            self.assertEqual(rapor["puanlar"]["4_hukuk"], 10)
            self.assertEqual(rapor["puanlar"]["7_sabotaj"], 10)

    def test_nedir_dogrusu_reels_ve_gonderi_stres(self):
        """Nedir Doğrusu formatında 20 içerik hem 4:5 hem 9:16 hatasız çizilmeli."""
        for konu in KONU_HAVUZU:
            veri = veri_hazirla(konu, "nedir_dogrusu")
            rapor = self.denetci.denetle(veri, "nedir_dogrusu", konu)
            self.assertTrue(rapor["basarili"], f"Nedir Doğrusu başarısız [{konu['id']}]: {rapor['hatalar']}")
            self.assertEqual(rapor["puanlar"]["5_kanca"], 10)
            self.assertEqual(rapor["puanlar"]["6_ses"], 10)

    def test_vaka_storytelling_reels_stres(self):
        """Örnek Olay / Vaka formatında 20 içerik hikaye akışı ve mevzuatla hatasız geçmeli."""
        for konu in KONU_HAVUZU:
            veri = veri_hazirla(konu, "vaka")
            rapor = self.denetci.denetle(veri, "vaka", konu)
            self.assertTrue(rapor["basarili"], f"Vaka başarısız [{konu['id']}]: {rapor['hatalar']}")
            self.assertEqual(rapor["puanlar"]["1_mantik"], 10)
            self.assertEqual(rapor["puanlar"]["4_hukuk"], 10)

    def test_net_cevap_rehberi_stres(self):
        """Net Cevap formatında 20 içerik soru-cevap netliğiyle hatasız geçmeli."""
        for konu in KONU_HAVUZU:
            veri = veri_hazirla(konu, "net_cevap")
            rapor = self.denetci.denetle(veri, "net_cevap", konu)
            self.assertTrue(rapor["basarili"], f"Net Cevap başarısız [{konu['id']}]: {rapor['hatalar']}")

    def test_sozluk_karti_stres(self):
        """Sözlük formatında 20 kart sakin editoryal tasarımla hatasız geçmeli."""
        for konu in KONU_HAVUZU:
            veri = veri_hazirla(konu, "sozluk")
            rapor = self.denetci.denetle(veri, "sozluk", konu)
            self.assertTrue(rapor["basarili"], f"Sözlük başarısız [{konu['id']}]: {rapor['hatalar']}")

    def test_secenek_a_reels_slot_rotasyonu_ve_katmanlar_arasi_uyum(self):
        """Seçenek A: REELS_FORMATLAR (nedir_dogrusu ⇄ vaka) döngüsü ve 9:16 video/story katman uyumu."""
        import tempfile
        from unittest.mock import patch
        from PIL import Image
        from src import db, konu_bankasi, telegram_bot
        from src.yayin import baglam, icerik, videolar
        from src.yayin.kanallar import story

        with tempfile.TemporaryDirectory() as tmp:
            with patch("src.db.DB_YOLU", Path(tmp) / "reels_slot.db"):
                db.tablolari_olustur()
                dongu = []
                for _ in range(4):
                    f = konu_bankasi.siradaki_reels_format()
                    dongu.append(f)
                    konu_bankasi.reels_format_kaydet(f)
                self.assertEqual(dongu, ["nedir_dogrusu", "vaka", "nedir_dogrusu", "vaka"])

                with patch("src.telegram.akislar.reels.reels_hazirla_ve_sun", return_value=True) as mock_reels:
                    ok = telegram_bot.slot_icerigi_hazirla_ve_sun(slot="reels", oto_yayin=False)
                    self.assertTrue(ok)
                    mock_reels.assert_called_once_with(format_turu="nedir_dogrusu", oto_yayin=False)

        # Katmanlar arası: format_turu='reels' + bicim='nedir_dogrusu' / 'vaka' olduğunda 9:16 dikey slayt ve Story kapağı üretimi
        for alt_bicim in ("nedir_dogrusu", "vaka"):
            ham = veri_hazirla(KONU_HAVUZU[0], alt_bicim)
            reels_veri = {**ham, "bicim": alt_bicim, "format_turu": "reels"}

            istek = baglam.Istek(tur="reels", ref_id="9991", hedef="reels,yt,ses_muzikli", hedefler={"reels", "yt", "ses_muzikli"})
            b = baglam.YayinBaglami(istek=istek)
            b.detay = reels_veri
            dikey = videolar._dikey_slaytlar(b)
            self.assertEqual(len(dikey), 3, f"{alt_bicim}: Reels için 3 kilit 9:16 slayt üretilmeli")
            with Image.open(dikey[0]) as im:
                self.assertEqual(im.size, (1080, 1920))

            st_kapak = story.story_kapagi_uret(reels_veri, {"id": 9991}, 9991, "reels")
            self.assertIsNotNone(st_kapak)
            with Image.open(st_kapak) as sim:
                self.assertEqual(sim.size, (1080, 1920))

            besleme_onarim = icerik.slaytlari_detaydan_ciz(reels_veri, 9991)
            self.assertGreaterEqual(len(besleme_onarim), 3)
            with Image.open(besleme_onarim[0]) as bim:
                self.assertEqual(bim.size, (1080, 1350))


if __name__ == "__main__":
    unittest.main()
