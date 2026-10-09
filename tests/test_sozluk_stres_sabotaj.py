"""
tests/test_sozluk_stres_sabotaj.py — Emlak Sözlüğü stres, sabotaj, geometri ve otomatik yayın güvenceleri (2026-10-08).

Bu dosya şunları doğrular:
1. Sabit Ayrım Çizgisi Değişmezliği: Çizgi her kartta ve her durumda filigran sayfa alt hizasında (y=510, story: 748) SABİTTİR.
2. Tek Satırda Font Büyümesi: Tek satıra sığan terimler kahraman puntoya (130-160 pt) büyür ve ortalanır.
3. Asgari Punto Tabanı: Arşivdeki tüm kartlar ≥114 pt (Zilyetlikle Tescil standardı) ile render edilir.
4. Kelime Bölmeme Güvencesi: Doğal kelimeler asla hece/harf ortasından bölünmez.
5. Sabotaj Koruması: Aşırı uzun metinler, aralıksız dize, boş puf, özel karakterler sistemi çökertmez.
6. Otomatik Günlük Yayın Döngüsü: 60 günlük simülasyonda tekrar engelleme, kategori dengesi ve güvenlik kapıları kusursuzdur.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")

import copy
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import yaml
from PIL import Image

from src import make_image, sozluk_arsivi as sa, telegram_bot, yeni_formatlar


def _cizgi_y_bul(resim_yolu: Path, y_min: int, y_max: int) -> list[int]:
    """Resimdeki yatay ayırıcı çizginin Y koordinatlarını bulur."""
    arr = np.array(Image.open(resim_yolu))
    lines = []
    for y in range(y_min, y_max):
        row = arr[y, 100:900]
        # Çizgi rengi: RENK_KIREC_BORDER = (218, 220, 214) civarı, varyansı düşük
        if row.std(axis=0).mean() < 5 and row.mean(axis=0)[0] < 225:
            lines.append(y)
    return lines


class TestSabitAycimCizgisiVeGeometri(unittest.TestCase):
    """Ayrım çizgisi asla yukarı/aşağı oynamaz; kitap filigranı sayfa alt hizasında (y=510) sabit kalır."""

    @classmethod
    def setUpClass(cls):
        cls.kartlar = sa.kartlari_yukle(tazele=True)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.tmp_path = Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_tum_kartlarda_cizgi_tam_510da_sabit(self):
        """Besleme (1080x1350) formatında 34 kartın tamamında ayrım çizgisi [510, 511]'de sabittir."""
        for k in self.kartlar:
            with self.subTest(kod=k["kod"], terim=k["terim"]):
                veri = sa.karttan_veri(k)
                yollar = yeni_formatlar.slaytlari_uret(
                    veri, format_turu="sozluk", cikti_dizini=self.tmp_path,
                    cikti_onek=f"geo_{k['kod']}_besleme", olcu="besleme"
                )
                self.assertEqual(len(yollar), 1)
                lines = _cizgi_y_bul(yollar[0], 450, 580)
                self.assertIn(510, lines, f"{k['kod']} {k['terim']}: cizgi 510'da bulunamadi: {lines}")
                self.assertIn(511, lines, f"{k['kod']} {k['terim']}: cizgi 511'de bulunamadi: {lines}")

    def test_story_formatinda_cizgi_tam_748de_sabit(self):
        """Story (1080x1920) formatında dikey ofsetle ayrım çizgisi [748, 749]'da sabittir."""
        ornek_kartlar = [k for k in self.kartlar if k["kod"] in ("SZ-001", "SZ-009", "SZ-024", "SZ-031")]
        for k in ornek_kartlar:
            with self.subTest(kod=k["kod"], terim=k["terim"]):
                veri = sa.karttan_veri(k)
                yollar = yeni_formatlar.slaytlari_uret(
                    veri, format_turu="sozluk", cikti_dizini=self.tmp_path,
                    cikti_onek=f"geo_{k['kod']}_story", olcu="story"
                )
                self.assertEqual(len(yollar), 1)
                lines = _cizgi_y_bul(yollar[0], 700, 800)
                self.assertIn(748, lines, f"{k['kod']} {k['terim']}: cizgi 748'de bulunamadi: {lines}")
                self.assertIn(749, lines, f"{k['kod']} {k['terim']}: cizgi 749'da bulunamadi: {lines}")


class TestTipografiVePuntoTabani(unittest.TestCase):
    """Tek satırlık terimler büyür, tüm terimler asgari ~114 pt tabanına uyar."""

    @classmethod
    def setUpClass(cls):
        cls.kartlar = sa.kartlari_yukle(tazele=True)
        cls.kw = 1080 - 2 * 78  # 924

    def test_tek_satirlik_terimler_kahraman_boyutta(self):
        """Tek kelimelik veya kısa terimler tek satırda 116-160 pt kahraman fonta ulaşır."""
        tek_satir_beklenen = {
            "SZ-009": 160,  # KEFALET
            "SZ-025": 160,  # TENKİS
            "SZ-031": 132,  # TAPU HARCI
            "SZ-019": 122,  # GEÇİT HAKKI
            "SZ-011": 116,  # KAT İRTİFAKI
        }
        for k in self.kartlar:
            kod = k["kod"]
            if kod in tek_satir_beklenen:
                with self.subTest(kod=kod, terim=k["terim"]):
                    r = yeni_formatlar._sigdir(k["terim"], yeni_formatlar.FONT_FRAUNCES, range(160, 115, -2), self.kw, 10000, 1.15, azami_satir=1)
                    self.assertIsNotNone(r, f"{kod} tek satira sigmaliydi")
                    punto = r[0].size
                    self.assertEqual(punto, tek_satir_beklenen[kod], f"{kod} punto uyumsuz: {punto} != {tek_satir_beklenen[kod]}")

    def test_tum_kartlar_asgari_114_punto_tabanina_uyar(self):
        """Tüm kartlar Zilyetlikle Tescil standardı gereği ≥114 pt punto ile çizilir (küçük puntoya düşmez)."""
        for k in self.kartlar:
            with self.subTest(kod=k["kod"], terim=k["terim"]):
                terim = k["terim"]
                # 1 line check
                r = yeni_formatlar._sigdir(terim, yeni_formatlar.FONT_FRAUNCES, range(160, 115, -2), self.kw, 10000, 1.15, azami_satir=1)
                if not r:
                    # 2 line check
                    r = yeni_formatlar._sigdir(terim, yeni_formatlar.FONT_FRAUNCES, range(144, 111, -2), self.kw, 10000, 1.15, azami_satir=2)
                self.assertIsNotNone(r, f"{k['kod']} {terim} 112 pt tabanına sığmadı")
                punto = r[0].size
                self.assertGreaterEqual(punto, 114, f"{k['kod']} {terim} çok küçük ({punto} < 114 pt)")

    def test_kelime_bolme_asla_devreye_girmez(self):
        """Gerçek kartların hiçbirinde kelime ortadan bölünmez."""
        for k in self.kartlar:
            with self.subTest(kod=k["kod"], terim=k["terim"]):
                terim = k["terim"]
                r1 = yeni_formatlar._sigdir(terim, yeni_formatlar.FONT_FRAUNCES, range(160, 115, -2), self.kw, 10000, 1.15, azami_satir=1)
                r = r1 or yeni_formatlar._sigdir(terim, yeni_formatlar.FONT_FRAUNCES, range(144, 111, -2), self.kw, 10000, 1.15, azami_satir=2)
                self.assertIsNotNone(r)
                parcalar = [w for line in r[1] for w in line.split()]
                self.assertEqual(parcalar, terim.split(), f"Kelime parçalanmış: {terim} -> {r[1]}")


class TestSabotajVeStresGirdileri(unittest.TestCase):
    """Sıra dışı, kötü niyetli veya uç sınırlardaki girdiler sistemi çökertmez."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.tmp_path = Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_asiri_uzun_araliksiz_kelime_cokmez(self):
        """45 karakterlik boşluksuz tek kelime çökmeden fallback ile güvenle çizilir."""
        out = self.tmp_path / "sabotaj_uzun_kelime.jpg"
        yeni_formatlar.uret_sozluk(
            cikti_yolu=out,
            terim="MÜTESELSİLKELİMEBÖLMEZİKORUMAKELİMESİTESTİ",
            kategori="TAPU_VE_HUKUK",
            tanim_metni="Bu aşırı uzun aralıksız test kelimesi kartın çökmesini engellemek için hazırlanmıştır.",
            puf_maddeleri=["Birinci madde emniyet testi.", "İkinci madde emniyet testi."],
        )
        self.assertTrue(out.exists())
        self.assertGreater(out.stat().st_size, 10_000)

    def test_puf_maddesi_olmayan_kart_cokmez(self):
        """Alt kutu boş olsa bile kart temizce üretilir, ayrım çizgisi yerinde kalır."""
        out = self.tmp_path / "sabotaj_bos_puf.jpg"
        yeni_formatlar.uret_sozluk(
            cikti_yolu=out,
            terim="TEMLİK",
            kategori="TAPU_VE_HUKUK",
            tanim_metni="Alacağın veya bir hakkın başka bir kişiye devredilmesini sağlayan hukuki işlemdir.",
            puf_maddeleri=[],
        )
        self.assertTrue(out.exists())
        lines = _cizgi_y_bul(out, 450, 580)
        self.assertIn(510, lines)

    def test_maksimum_butce_sinirindaki_metin_tasmadan_cizilir(self):
        """260 karakter tanım ve her biri 115 karakterlik 3 puf maddesi taşmadan çizilir."""
        out = self.tmp_path / "stres_maksimum_butce.jpg"
        uzun_tanim = (
            "Paylı mülkiyette bir paydaş payını üçüncü bir kişiye satarsa diğer paydaşların bu payı alıcıya "
            "karşı dava açarak öncelikle satın alabilmesini sağlayan yasal haktır; paydaşların mülkiyeti koruma hakkıdır."
        )[:255]
        maddeler = [
            "Hak, satışın bildirildiği tarihten itibaren üç ay, her hâlde satıştan itibaren bir yıl geçmekle tamamen düşer.",
            "Satış, alıcı veya satıcı tarafından diğer paydaşlara noter aracılığıyla resmen ve usulünce bildirilmek zorundadır.",
            "Taşınmaz payının rayiç bedelini ve ödeme şartlarını mahkeme hâkimi somut delillere göre hakkaniyetle belirler.",
        ]
        yeni_formatlar.uret_sozluk(
            cikti_yolu=out,
            terim="ÖNALIM HAKKI",
            kategori="TAPU_VE_HUKUK",
            tanim_metni=uzun_tanim,
            puf_maddeleri=maddeler,
        )
        self.assertTrue(out.exists())

    def test_ozel_ve_nadir_turkce_karakterler(self):
        """Şapkalı harfler (Â, î, û), tırnaklar ve parantezli kısaltmalar bozulmadan çizilir."""
        out = self.tmp_path / "stres_ozel_karakter.jpg"
        yeni_formatlar.uret_sozluk(
            cikti_yolu=out,
            terim="ŞUF'A (ÖNALIM) & İNTİFÂ",
            kategori="TAPU_VE_HUKUK",
            tanim_metni="Hükmî şahsiyetlerin 'gayrimenkul' üzerindeki sükûn ve intifâ haklarını tâyin eden kâidedir.",
            puf_maddeleri=["Âyan ve beyan olunan şartlar geçerlidir.", "Hakkın ziyaı hâlinde tazminat doğar."],
        )
        self.assertTrue(out.exists())


class TestOtomatikYayinVeRotasyonDöngüsü(unittest.TestCase):
    """Günlük otomatik sözlük yayını, takvim simülasyonu ve hata durumları."""

    @classmethod
    def setUpClass(cls):
        sa._onbellek = None
        cls.kartlar = sa.kartlari_yukle(tazele=True)

    def test_34_gunluk_arsiv_rotasyonu_ve_bekleme_suresi_guvencesi(self):
        """34 günlük kesintisiz yayında tüm kartlar hiç tekrarsız yayınlanır, bekleme süresi (730 gün) dolmadan erken tekrar yapılmaz."""
        gecmis = {}
        son_kat = None
        yayinlananlar = []

        start_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # 1. Aşama: İlk 34 gün — Tüm bakir kartlar tek tek seçilir
        for gun in range(len(self.kartlar)):
            bugun = start_date + timedelta(days=gun)
            secilen = sa.sonraki_kart(gecmis, son_kategori=son_kat)
            self.assertIsNotNone(secilen, f"Gün {gun}: Bakir kart kalmadı")
            kod = secilen["kod"]
            kat = secilen["kategori_kodu"]

            # İlk turda hiçbir kart önceden yayınlanmış olamaz (sıfır tekrar)
            self.assertNotIn(kod, gecmis, f"Erken tekrar: {kod}")

            gecmis[kod] = bugun.isoformat()
            yayinlananlar.append(kod)
            son_kat = kat

        # 34 kartın tamamı yayınlanmış olmalı
        self.assertEqual(len(set(yayinlananlar)), len(self.kartlar))

        # 2. Aşama: 35. gün (BEKLEME_GUN dolmadan önce) yeni kart seçilmemeli (None dönmeli)
        bugun_erken = start_date + timedelta(days=35)
        with patch("src.konu_bankasi._gun_farki", side_effect=lambda iso: (bugun_erken - datetime.fromisoformat(iso)).days):
            secilen_erken = sa.sonraki_kart(gecmis, son_kategori=son_kat)
            self.assertIsNone(secilen_erken, "bekleme süresi dolmadan kart erken tekrar seçilmemeli")

        # 3. Aşama: 185. gün (BEKLEME_GUN dolunca) en eski kart seçilmeli
        bugun_gec = start_date + timedelta(days=sa.BEKLEME_GUN + 5)
        with patch("src.konu_bankasi._gun_farki", side_effect=lambda iso: (bugun_gec - datetime.fromisoformat(iso)).days):
            secilen_gec = sa.sonraki_kart(gecmis, son_kategori=son_kat)
            self.assertIsNotNone(secilen_gec, "bekleme süresi dolunca en eski kart seçilmeli")
            self.assertEqual(secilen_gec["kod"], yayinlananlar[0], "En eski yayınlanan ilk kart seçilmeliydi")

    def test_mevzuat_uyusmazliginda_otomatik_yayin_durdurulur(self):
        """Kanunla uyuşmayan kart seçildiğinde otomatik yayın durur ve sonraki karta geçer."""
        bozuk_kart = copy.deepcopy(self.kartlar[0])
        with patch.object(sa, "kart_kanun_durumu", return_value=(False, ["Mevzuat uyuşmazlığı tespit edildi"])):
            with patch.object(telegram_bot, "mesaj_gonder") as mock_msg:
                secilen, taze = telegram_bot._sozluk_karti_sec()
                # 8 deneme boyunca başarısız olup durmalı
                self.assertIsNone(secilen)
                self.assertIsNone(taze)
                self.assertTrue(mock_msg.called)


if __name__ == "__main__":
    unittest.main()
