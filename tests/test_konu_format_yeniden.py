"""
tests/test_konu_format_yeniden.py — Format başına konu kullanımı (2026-10-07).

Bir konu kullanılınca 120 gün kilitleniyordu; bakir konu ~26 günde tükenecekti. Aynı doğrulanmış konu
başka formatta (sözlük, nedir doğrusu, net cevap…) farklı bir içeriktir: bakir konu bitince konu,
bu formatta DAHA ÖNCE kullanılmadıysa ve son kullanımdan beri 21 gün geçtiyse yeniden kullanılır.
Format `konu_gecmisi.sonuc`ta `uretildi:<format>` olarak taşınır (şema değişmedi).
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src import db, konu_bankasi as kb


def _gun_once(gun: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=gun)).isoformat()


def _konu(kod: str, sutun: str = "S1", dayanakli: bool = True) -> dict:
    """Sözlük yalnız kanun alıntısı olan konudan yazılır (bkz. sonraki_konu); fikstür varsayılan olarak onu taşır."""
    konu = {"kod": kod, "sutun": sutun, "bicim": "B1", "baslik": f"Konu {kod}", "aci": "a", "kanca_kalip": "k"}
    if dayanakli:
        konu["dayanak_alintisi"] = "Kanun metninden birebir alıntı."
    return konu


class _Ortam(unittest.TestCase):
    """Havuz, geçmiş ve format geçmişini sahte verir; seçim mantığı yalın sınanır."""

    def _sec(self, havuz, gecmis, fgecmis, *, format_turu=None, sutun="S1", engelli=(), **kw):
        with patch.object(kb, "havuzu_yukle", return_value=havuz), \
             patch.object(kb, "_kullanim_gecmisi", return_value=gecmis), \
             patch.object(kb, "_format_gecmisi", return_value=fgecmis), \
             patch.object(kb, "_engellenen_konular", return_value=set(engelli)), \
             patch.object(kb, "_son_kullanilan_sutunlar", return_value=[]), \
             patch.object(kb, "tabloyu_kur"):
            return kb.sonraki_konu(sutun=sutun, format_turu=format_turu, **kw)


class TestFormatAdi(unittest.TestCase):
    def test_b_serisi_tek_formata_iner(self):
        for ad in ("b1", "B2", "b3", "B4", "b5", "otorite", "", None):
            self.assertEqual(kb.format_adi(ad), "b1", ad)

    def test_diger_formatlar_ayri_kalir(self):
        self.assertEqual(kb.format_adi("sozluk"), "sozluk")
        self.assertEqual(kb.format_adi("Nedir_Dogrusu"), "nedir_dogrusu")
        self.assertEqual(kb.format_adi("net_cevap"), "net_cevap")
        self.assertEqual(kb.format_adi("reels"), "reels")
        self.assertEqual(kb.format_adi("finans"), "finans")
        self.assertNotEqual(kb.format_adi("vaka"), kb.format_adi("b1"))


class TestSecim(_Ortam):
    def test_bakir_konu_varken_yeniden_kullanim_devreye_girmez(self):
        havuz = [_konu("A"), _konu("B")]
        gecmis = {"A": _gun_once(40)}  # A 40 gün önce kullanıldı, B bakir
        for _ in range(20):
            self.assertEqual(self._sec(havuz, gecmis, {("A", "b1"): gecmis["A"]}, format_turu="sozluk")["kod"], "B")

    def test_bakir_bitince_baska_formatta_kullanilmis_konu_yeniden_gelir(self):
        havuz = [_konu("A")]
        gecmis = {"A": _gun_once(30)}
        secim = self._sec(havuz, gecmis, {("A", "b1"): gecmis["A"]}, format_turu="sozluk")
        self.assertEqual(secim["kod"], "A")

    def test_ayni_formatta_ikinci_kez_gelmez(self):
        havuz = [_konu("A")]
        gecmis = {"A": _gun_once(30)}
        self.assertIsNone(self._sec(havuz, gecmis, {("A", "sozluk"): gecmis["A"]}, format_turu="sozluk"))

    def test_bekleme_suresi_dolmadan_gelmez(self):
        havuz = [_konu("A")]
        gecmis = {"A": _gun_once(kb.YENIDEN_KULLANIM_BEKLEME_GUN - 5)}
        self.assertIsNone(self._sec(havuz, gecmis, {("A", "b1"): gecmis["A"]}, format_turu="sozluk"))

    def test_engelli_konu_asla_yeniden_gelmez(self):
        havuz = [_konu("A")]
        gecmis = {"A": _gun_once(60)}
        self.assertIsNone(self._sec(havuz, gecmis, {("A", "b1"): gecmis["A"]}, format_turu="sozluk", engelli=["A"]))

    def test_istenen_sutun_ve_en_uzun_dinlenen_oncelikli(self):
        havuz = [_konu("A", "S2"), _konu("B", "S1"), _konu("C", "S1")]
        gecmis = {"A": _gun_once(90), "B": _gun_once(30), "C": _gun_once(60)}
        fg = {(k, "b1"): v for k, v in gecmis.items()}
        self.assertEqual(self._sec(havuz, gecmis, fg, format_turu="sozluk", sutun="S1")["kod"], "C")

    def test_sozluk_dayanak_alintisi_olmayan_konuyu_secmez(self):
        """Modelin kanundan yazdığı sözlük ince yanlışlar taşıyordu (2026-10-08): alıntısız konu sözlüğe girmez."""
        havuz = [_konu("A", dayanakli=False)]
        self.assertIsNone(self._sec(havuz, {}, {}, format_turu="sozluk"))

    def test_dayanak_alintisi_aranmasi_yalniz_sozluge_ozgudur(self):
        havuz = [_konu("A", dayanakli=False)]
        self.assertEqual(self._sec(havuz, {}, {}, format_turu="b1")["kod"], "A")
        self.assertEqual(self._sec(havuz, {}, {}, format_turu="net_cevap")["kod"], "A")

    def test_sozluk_alintili_konuyu_alintisizdan_ayirir(self):
        havuz = [_konu("A", dayanakli=False), _konu("B")]
        for _ in range(20):
            self.assertEqual(self._sec(havuz, {}, {}, format_turu="sozluk")["kod"], "B")

    def test_format_verilmezse_b1_sayilir(self):
        havuz = [_konu("A")]
        gecmis = {"A": _gun_once(30)}
        self.assertIsNone(self._sec(havuz, gecmis, {("A", "b1"): gecmis["A"]}))           # b1 zaten kullanılmış
        self.assertEqual(self._sec(havuz, gecmis, {("A", "sozluk"): gecmis["A"]})["kod"], "A")

    def test_120_gun_kademesi_hala_calisir(self):
        havuz = [_konu("A")]
        gecmis = {"A": _gun_once(130)}
        # Aynı formatta kullanılmış ama 120 günü doldurmuş: eski davranış korunur
        self.assertEqual(self._sec(havuz, gecmis, {("A", "sozluk"): gecmis["A"]}, format_turu="sozluk")["kod"], "A")


class TestKayit(unittest.TestCase):
    KOD = "TEST-FORMAT-YENIDEN"

    def setUp(self):
        kb.tabloyu_kur()
        self.haberler: list = []
        self._temizle()

    def tearDown(self):
        self._temizle()

    def _temizle(self):
        with db._baglanti_al() as conn:
            conn.execute("DELETE FROM konu_gecmisi WHERE konu_kodu = ?", (self.KOD,))
            for hid in getattr(self, "haberler", []):
                conn.execute("DELETE FROM haberler WHERE id = ?", (hid,))
            conn.commit()

    def _sonuclar(self):
        with db._baglanti_al() as conn:
            return [r["sonuc"] for r in conn.execute(
                "SELECT sonuc FROM konu_gecmisi WHERE konu_kodu = ? ORDER BY id", (self.KOD,))]

    def test_format_sonuc_alanina_yazilir_ve_geri_okunur(self):
        kb.kullanildi_isaretle(self.KOD, format_turu="Nedir_Dogrusu")
        self.assertEqual(self._sonuclar(), ["uretildi:nedir_dogrusu"])
        self.assertIn((self.KOD, "nedir_dogrusu"), kb._format_gecmisi())
        self.assertNotIn((self.KOD, "b1"), kb._format_gecmisi())

    def test_formatsiz_eski_kayit_b1_sayilir(self):
        kb.kullanildi_isaretle(self.KOD)
        self.assertEqual(self._sonuclar(), ["uretildi"])
        self.assertIn((self.KOD, "b1"), kb._format_gecmisi())

    def _haber_ekle(self, detay_metni: str) -> int:
        with db._baglanti_al() as conn:
            cur = conn.execute(
                """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, eklenme_tarihi, detay_metni, durum)
                   VALUES (?, ?, ?, ?, ?, 'yeni')""",
                (f"EDM Konu Bankası // {self.KOD}", "t", f"edm://konu/{self.KOD}/{detay_metni[:8]}", _gun_once(1), detay_metni),
            )
            conn.commit()
            self.haberler.append(cur.lastrowid)
            return cur.lastrowid

    def test_eski_kayit_formatini_bagli_haberden_okur(self):
        # 2026-10-07 öncesi kayıtlarda sonuc yalnız 'uretildi'; format haberin detay_metni'nde duruyor
        hid = self._haber_ekle('{"format_turu": "nedir_dogrusu"}')
        kb.kullanildi_isaretle(self.KOD, haber_id=hid)
        fg = kb._format_gecmisi()
        self.assertIn((self.KOD, "nedir_dogrusu"), fg)
        self.assertNotIn((self.KOD, "b1"), fg)

    def test_bozuk_ya_da_bos_detay_metni_b1_sayilir(self):
        kb.kullanildi_isaretle(self.KOD, haber_id=self._haber_ekle("bu json degil"))
        self.assertIn((self.KOD, "b1"), kb._format_gecmisi())

    def test_hata_ve_cope_at_format_gecmisine_girmez(self):
        kb.kullanildi_isaretle(self.KOD, sonuc="hata", format_turu="sozluk")
        kb.kullanildi_isaretle(self.KOD, sonuc="cope_at", format_turu="sozluk")
        self.assertEqual(self._sonuclar(), ["hata", "cope_at"])  # hata/çöpe format eki yazılmaz
        self.assertNotIn((self.KOD, "sozluk"), kb._format_gecmisi())

    def test_eski_gecmis_okuyanlar_bozulmaz(self):
        kb.kullanildi_isaretle(self.KOD, format_turu="sozluk")
        self.assertIn(self.KOD, kb._kullanim_gecmisi())      # `!= 'hata'` okuyucusu
        self.assertNotIn(self.KOD, kb._engellenen_konular())  # `IN ('cope_at','engellendi')` okuyucusu


class TestDurumOzeti(unittest.TestCase):
    def test_engelli_bakir_konu_ufku_sisirmez(self):
        havuz = [_konu("A"), _konu("B"), _konu("C")]
        with patch.object(kb, "havuzu_yukle", return_value=havuz), \
             patch.object(kb, "_kullanim_gecmisi", return_value={}), \
             patch.object(kb, "_format_gecmisi", return_value={}), \
             patch.object(kb, "_engellenen_konular", return_value={"C"}), \
             patch.object(kb, "tabloyu_kur"):
            ozet = kb.durum_ozeti()
        self.assertEqual(ozet["bakir"], 2)
        self.assertEqual(ozet["engelli_bakir"], 1)
        self.assertIn("format_yeniden_kullanilabilir", ozet)


if __name__ == "__main__":
    unittest.main()
