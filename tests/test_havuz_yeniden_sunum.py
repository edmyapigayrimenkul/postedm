"""
tests/test_havuz_yeniden_sunum.py — onaylanmayan içerik 1 günde HAVUZA döner, hazır olduğu için YENİDEN ÜRETİLMEZ, başka bir gün tekrar önerilir (2026-10-13)

Kullanıcı kararı: "1 gün boyunca yayınlamadıysam havuza dönsün; daha önceden hazırlandığı için tekrar oluşturulmasın; başka bir gün tekrar önerilir."
Akış: `scripts/hatirlat.py` (sessiz kuyruk bakımı) 1 günü dolduran hazır içeriği `durum='havuzda'` yapar → aynı formatın bir sonraki turu
(`uretim.konu_bankasindan_hazirla` / `hizli_icerik_uret`) `havuz.havuzdan_sun` ile onu MODEL ÇAĞRILMADAN yeniden onaya sunar.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from scripts import hatirlat  # noqa: E402
from src import db, konu_bankasi  # noqa: E402
from src.telegram.akislar import havuz, uretim  # noqa: E402


def _ekle(format_turu="b1", durum="havuzda", yas_gun=2.0, kaynak="EDM Konu Bankası // S1-950", detay='{"manset_vurgu": "x"}', manset="Hazır Manşet") -> int:
    eklenme = (datetime.now(timezone.utc) - timedelta(days=yas_gun)).isoformat()
    with db._baglanti_al() as conn:
        cur = conn.execute(
            "INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, eklenme_tarihi, manset, detay_metni, durum) VALUES (?, 'b', ?, ?, ?, ?, ?)",
            (kaynak, f"test://havuz/{uuid.uuid4()}", eklenme, manset, detay, durum),
        )
        hid = cur.lastrowid
        conn.commit()
    if format_turu:
        konu_bankasi.tabloyu_kur()
        with db._baglanti_al() as conn:
            conn.execute("INSERT INTO konu_gecmisi (konu_kodu, kullanim_tarihi, haber_id, sonuc) VALUES (?, ?, ?, ?)",
                         ("S1-950", datetime.now(timezone.utc).isoformat(), hid, f"uretildi:{format_turu}"))
            conn.commit()
    return hid


class Temel(unittest.TestCase):
    def setUp(self):
        self.idler: list[int] = []
        konu_bankasi.tabloyu_kur()
        with db._baglanti_al() as conn:   # test DB'si geçici kopya: önceki testlerden kalan havuz kayıtları sonucu etkilemesin
            conn.execute("UPDATE haberler SET durum = 'zaman_asimi' WHERE durum = 'havuzda'")
            conn.commit()

    def tearDown(self):
        with db._baglanti_al() as conn:
            for hid in self.idler:
                conn.execute("DELETE FROM konu_gecmisi WHERE haber_id = ?", (hid,))
                conn.execute("DELETE FROM onay_istekleri WHERE referans_id = ?", (str(hid),))
                conn.execute("DELETE FROM haberler WHERE id = ?", (hid,))
            conn.commit()

    def ekle(self, **kw) -> int:
        hid = _ekle(**kw)
        self.idler.append(hid)
        return hid


class TestHavuzSorgulari(Temel):
    def test_format_gecmisten_okunur(self):
        hid = self.ekle(format_turu="nedir_dogrusu")
        self.assertEqual(konu_bankasi.icerik_formati(hid), "nedir_dogrusu")

    def test_havuza_alinabilir_yalniz_hazir_konu_bankasi_icerigi(self):
        hazir = db.haber_getir(self.ekle())
        self.assertTrue(konu_bankasi.havuza_alinabilir_mi(hazir))
        for neden, haber in {
            "haber kaynaklı (bayatlar)": db.haber_getir(self.ekle(kaynak="Hürriyet Emlak")),
            "metni yok": db.haber_getir(self.ekle(detay=None)),
            "manşeti yok": db.haber_getir(self.ekle(manset=None)),
            "sözlük kartı (ucuz, yeniden kurulur)": db.haber_getir(self.ekle(format_turu="sozluk")),
            "finans": db.haber_getir(self.ekle(format_turu="finans")),
            "format bilinmiyor": db.haber_getir(self.ekle(format_turu=None)),
        }.items():
            with self.subTest(neden):
                self.assertFalse(konu_bankasi.havuza_alinabilir_mi(haber))

    def test_en_eski_hazir_icerik_ve_format_eslemesi(self):
        yeni = self.ekle(yas_gun=1)
        eski = self.ekle(yas_gun=3)
        baska = self.ekle(format_turu="vaka", yas_gun=9)
        self.assertEqual(konu_bankasi.havuzdaki_hazir_icerik("b1")["id"], min(yeni, eski))      # id sırası = üretim sırası
        self.assertEqual(konu_bankasi.havuzdaki_hazir_icerik("b2")["id"], min(yeni, eski), "b2/b3… 'b1'e eşlenir")
        self.assertEqual(konu_bankasi.havuzdaki_hazir_icerik("vaka")["id"], baska)

    def test_havuzda_olmayan_ve_havuz_disi_formatlar_donmez(self):
        self.ekle(durum="onay_bekliyor")
        self.ekle(durum="zaman_asimi")
        self.ekle(format_turu="sozluk")
        self.assertIsNone(konu_bankasi.havuzdaki_hazir_icerik("b1"))
        for fmt in ("sozluk", "finans", "reels", "haber", "", None):
            with self.subTest(fmt=fmt):
                self.assertIsNone(konu_bankasi.havuzdaki_hazir_icerik(fmt))


class TestHavuzdanSun(Temel):
    def test_havuzdaki_icerik_model_cagrilmadan_yeniden_sunulur(self):
        hid = self.ekle()
        with mock.patch("src.telegram.akislar.onay.haber_onayina_sun", return_value=True) as onay, \
             mock.patch("src.generate_text.konudan_uret", side_effect=AssertionError("MODEL ÇAĞRILMAMALI")), \
             mock.patch("src.generate_text.haber_metinleri_uret", side_effect=AssertionError("MODEL ÇAĞRILMAMALI")):
            self.assertTrue(havuz.havuzdan_sun("b1"))
        onay.assert_called_once_with(hid)
        self.assertEqual(db.haber_getir(hid)["durum"], "yeni", "onay akışı durumu 'onay_bekliyor' yapar; öncesinde havuz işareti kalkmalı")

    def test_havuz_bossa_none(self):
        self.assertIsNone(havuz.havuzdan_sun("b1"))

    def test_yeniden_sunum_kapidan_gecemezse_arsivlenir_konu_iade_edilir_none_doner(self):
        hid = self.ekle()
        with mock.patch("src.telegram.akislar.onay.haber_onayina_sun", return_value=False):
            self.assertIsNone(havuz.havuzdan_sun("b1"), "None = çağıran taze içerik üretsin, gün boş geçmesin")
        self.assertEqual(db.haber_getir(hid)["durum"], "zaman_asimi")
        with db._baglanti_al() as conn:
            sonuclar = [r[0] for r in conn.execute("SELECT sonuc FROM konu_gecmisi WHERE haber_id = ?", (hid,))]
        self.assertEqual(sonuclar, ["hata"], "konu havuza dönmeli (bozuk içerik yerine ileride taze içerik üretilsin)")


class TestUretimHavuzuOnceler(Temel):
    def test_b1_gunluk_tur_once_havuza_bakar_model_cagirmaz(self):
        hid = self.ekle()
        with mock.patch("src.telegram.akislar.onay.haber_onayina_sun", return_value=True) as onay, \
             mock.patch("src.konu_bankasi.sonraki_konu", side_effect=AssertionError("yeni konu seçilmemeli")), \
             mock.patch("src.generate_text.konudan_uret", side_effect=AssertionError("MODEL ÇAĞRILMAMALI")), \
             mock.patch("src.telegram.istemci.mesaj_gonder"):
            self.assertTrue(uretim.konu_bankasindan_hazirla())
        onay.assert_called_once_with(hid)

    def test_havuz_bossa_yeni_icerik_uretilir(self):
        with mock.patch("src.konu_bankasi.sonraki_konu", return_value=None) as sec, mock.patch("src.telegram.istemci.mesaj_gonder"):
            self.assertFalse(uretim.konu_bankasindan_hazirla())
        sec.assert_called_once()

    def test_kapidan_gecemeyen_havuz_icerigi_yerine_taze_uretim_denenir(self):
        self.ekle()
        with mock.patch("src.telegram.akislar.onay.haber_onayina_sun", return_value=False), \
             mock.patch("src.konu_bankasi.sonraki_konu", return_value=None) as sec, mock.patch("src.telegram.istemci.mesaj_gonder"):
            uretim.konu_bankasindan_hazirla()
        sec.assert_called_once()   # havuz içeriği düştü → aynı turda taze konu seçimine geçildi

    def test_diger_formatlar_da_kendi_havuzundan_beslenir(self):
        hid = self.ekle(format_turu="nedir_dogrusu")
        with mock.patch("src.telegram.akislar.onay.haber_onayina_sun", return_value=True) as onay, \
             mock.patch("src.konu_bankasi.sonraki_konu", side_effect=AssertionError("yeni konu seçilmemeli")), \
             mock.patch("src.telegram.istemci.mesaj_gonder"):
            self.assertTrue(uretim.hizli_icerik_uret(format_turu="nedir_dogrusu"))
        onay.assert_called_once_with(hid)

    def test_baska_formatin_havuzu_karismaz(self):
        self.ekle(format_turu="vaka")
        with mock.patch("src.telegram.akislar.onay.haber_onayina_sun") as onay, \
             mock.patch("src.konu_bankasi.sonraki_konu", return_value=None) as sec, mock.patch("src.telegram.istemci.mesaj_gonder"):
            self.assertFalse(uretim.hizli_icerik_uret(format_turu="net_cevap"))
        onay.assert_not_called()
        sec.assert_called_once()


class TestUcdanUca(Temel):
    def test_onaysiz_kalan_icerik_havuza_girer_sonraki_turda_ayni_numarayla_geri_gelir(self):
        """1 günü dolduran içerik: sessizce havuza → aynı format sonraki tur → AYNI içerik numarası, model yok."""
        hid = self.ekle(durum="onay_bekliyor", yas_gun=1.2)
        gercek_getir = db.onay_bekleyen_haberleri_getir   # `hatirlat.db` ile aynı modül: yamadan ÖNCE sakla (yoksa sonsuz özyineleme)
        with mock.patch.object(hatirlat.db, "onay_bekleyen_haberleri_getir",
                               side_effect=lambda limit=5: [h for h in gercek_getir(limit=500) if h["id"] == hid]), \
             mock.patch("src.telegram.istemci.mesaj_gonder") as mesaj, \
             mock.patch("src.telegram.temizlik.icerik_onceki_mesajlarini_temizle"), \
             mock.patch.object(hatirlat.db, "wal_bosalt"):
            hatirlat.main(argv=[])
        self.assertEqual(db.haber_getir(hid)["durum"], "havuzda")
        mesaj.assert_not_called()
        with mock.patch("src.telegram.akislar.onay.haber_onayina_sun", return_value=True) as onay, \
             mock.patch("src.generate_text.konudan_uret", side_effect=AssertionError("MODEL ÇAĞRILMAMALI")), \
             mock.patch("src.telegram.istemci.mesaj_gonder"):
            self.assertTrue(uretim.konu_bankasindan_hazirla())
        onay.assert_called_once_with(hid)

    def test_havuzdaki_icerik_14_gunde_temizlenir_sinirsiz_birikmez(self):
        eski = self.ekle(yas_gun=20)
        taze = self.ekle(yas_gun=2)
        db.eski_kayitlari_temizle(gun=14)
        self.assertIsNone(db.haber_getir(eski), "14 günden eski havuz içeriği silinir (havuz sınırsız büyümez)")
        self.assertIsNotNone(db.haber_getir(taze))

    def test_havuzdan_yeniden_sunulan_icerik_hemen_havuza_donmez_24_saat_bekler(self):
        """Havuzdan tekrar sunulan içerik 3 gün önce eklenmiş olsa dahi Telegram'a yeni sunulduğunda
        kuyruk bakımı onu 3.5 saatte silip tekrar havuza almaz; 24 saati doldurana kadar bekletir (2026-10-14 olayı)."""
        # 1. 3 gün önce eklenmiş içerik
        hid = self.ekle(durum="onay_bekliyor", yas_gun=3.0)
        # 2. 3.5 saat önce Telegram onayına sunulmuş aktif onay isteği
        sunum_zamani = (datetime.now(timezone.utc) - timedelta(hours=3.5)).isoformat()
        with db._baglanti_al() as conn:
            conn.execute(
                "INSERT INTO onay_istekleri (tur, referans_id, telegram_mesaj_id, durum, olusturma_tarihi) VALUES ('haber', ?, 12345, 'bekliyor', ?)",
                (str(hid), sunum_zamani),
            )
            conn.commit()

        # 3. bekleme süresi 3 gün (~4320 dk) değil, ~210 dk çıkmalı
        haber = next(h for h in db.onay_bekleyen_haberleri_getir(limit=500) if h["id"] == hid)
        dakika = hatirlat.bekleme_suresi_dakika(haber)
        self.assertIsNotNone(dakika)
        self.assertAlmostEqual(dakika, 210, delta=5)

        # 4. Kuyruk bakımı çalıştığında içerik havuza çekilmemeli, onayda kalmalı
        gercek_getir = db.onay_bekleyen_haberleri_getir
        with mock.patch.object(hatirlat.db, "onay_bekleyen_haberleri_getir",
                               side_effect=lambda limit=5: [h for h in gercek_getir(limit=500) if h["id"] == hid]), \
             mock.patch("src.telegram.temizlik.icerik_onceki_mesajlarini_temizle") as temizle, \
             mock.patch.object(hatirlat.db, "wal_bosalt"):
            hatirlat.main(argv=[])
        self.assertEqual(db.haber_getir(hid)["durum"], "onay_bekliyor")
        temizle.assert_not_called()

        # 5. Onay isteği 25 saat eskiyse zaman aşımına uğramalı ve havuza dönmeli
        eski_sunum = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        with db._baglanti_al() as conn:
            conn.execute(
                "UPDATE onay_istekleri SET olusturma_tarihi = ? WHERE referans_id = ?",
                (eski_sunum, str(hid)),
            )
            conn.commit()
        with mock.patch.object(hatirlat.db, "onay_bekleyen_haberleri_getir",
                               side_effect=lambda limit=5: [h for h in gercek_getir(limit=500) if h["id"] == hid]), \
             mock.patch("src.telegram.temizlik.icerik_onceki_mesajlarini_temizle"), \
             mock.patch.object(hatirlat.db, "wal_bosalt"):
            hatirlat.main(argv=[])
        self.assertEqual(db.haber_getir(hid)["durum"], "havuzda")


if __name__ == "__main__":
    unittest.main(verbosity=2)
