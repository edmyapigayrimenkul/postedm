"""
tests/test_onay_kuyrugu_ve_iade.py — onay kuyruğu zaman aşımı ve konunun havuza iadesi (2026-10-12 denetimi)

Bulgular:
  · hatirlat.py yalnızca en yeni 5 bekleyen içeriğe bakıyordu; daha eskiler 5 günlük zaman aşımına hiç girmiyordu
    (üretimde 14 içerik, en eskisi 27 Eylül'den beri bekliyordu).
  · "Pas geç / Çöpe at" mesajı "konu havuza iade edildi" diyordu ama konu üretim anında tüketilmişti ve geri
    verilmiyordu; üstelik her durumda yeni bir B1 üretiliyordu (sözlük kartı reddi de karusel doğuruyordu).
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import importlib.util
import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import db, konu_bankasi  # noqa: E402
from scripts import hatirlat  # noqa: E402


def _haber_ekle(kaynak="EDM Konu Bankası // S1-901", durum="onay_bekliyor", yas_gun=0.0, **ek) -> int:
    eklenme = (datetime.now(timezone.utc) - timedelta(days=yas_gun)).isoformat()
    with db._baglanti_al() as conn:
        cur = conn.execute(
            "INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, eklenme_tarihi, manset, durum) "
            "VALUES (?, 'b', ?, ?, ?, ?)",
            (kaynak, f"test://iade/{uuid.uuid4()}", eklenme, f"Manşet {yas_gun}", durum),
        )
        hid = cur.lastrowid
        for k, v in ek.items():
            conn.execute(f"UPDATE haberler SET {k} = ? WHERE id = ?", (v, hid))
        conn.commit()
    return hid


def _gecmis_ekle(kod: str, haber_id: int, sonuc="uretildi:b1") -> None:
    konu_bankasi.tabloyu_kur()
    with db._baglanti_al() as conn:
        conn.execute("INSERT INTO konu_gecmisi (konu_kodu, kullanim_tarihi, haber_id, sonuc) VALUES (?, ?, ?, ?)",
                     (kod, datetime.now(timezone.utc).isoformat(), haber_id, sonuc))
        conn.commit()


def _gecmis_sonuc(haber_id: int) -> list:
    with db._baglanti_al() as conn:
        return [r[0] for r in conn.execute("SELECT sonuc FROM konu_gecmisi WHERE haber_id = ? ORDER BY id", (haber_id,))]


class TestKonuIadesi(unittest.TestCase):
    def setUp(self):
        self.idler = []

    def tearDown(self):
        with db._baglanti_al() as conn:
            for hid in self.idler:
                conn.execute("DELETE FROM konu_gecmisi WHERE haber_id = ?", (hid,))
                conn.execute("DELETE FROM haberler WHERE id = ?", (hid,))
            conn.commit()

    def _hazirla(self, kod="S1-901", **kw) -> int:
        hid = _haber_ekle(**kw)
        self.idler.append(hid)
        _gecmis_ekle(kod, hid)
        return hid

    def test_yayinlanmayan_icerigin_konusu_hataya_cevrilir_silinmez(self):
        hid = self._hazirla()
        self.assertEqual(konu_bankasi.konuyu_havuza_iade_et(hid), 1)
        self.assertEqual(_gecmis_sonuc(hid), ["hata"])  # satır duruyor: birleştirme sürücüsü güncellemeyi taşır

    def test_iade_ikinci_kez_etkisiz(self):
        hid = self._hazirla()
        konu_bankasi.konuyu_havuza_iade_et(hid)
        self.assertEqual(konu_bankasi.konuyu_havuza_iade_et(hid), 0)

    def test_yayindaki_icerik_iade_edilmez(self):
        hid = self._hazirla(durum="yayinlandi", instagram_post_id="ig1")
        self.assertEqual(konu_bankasi.konuyu_havuza_iade_et(hid), 0)
        self.assertEqual(_gecmis_sonuc(hid), ["uretildi:b1"])

    def test_iade_edilen_konu_uc_gun_sonra_yeniden_secilebilir(self):
        """`hata` kaydı yalnız HATA_BEKLEME_GUNU boyunca konuyu kapalı tutar (kesinti konuyu yakmaz kuralı)."""
        hid = self._hazirla(kod="S1-902")
        konu_bankasi.konuyu_havuza_iade_et(hid)
        self.assertIn("S1-902", konu_bankasi._kullanim_gecmisi())  # ilk 3 gün hemen yeniden seçilmez
        eski = (datetime.now(timezone.utc) - timedelta(days=konu_bankasi.HATA_BEKLEME_GUNU + 1)).isoformat()
        with db._baglanti_al() as conn:
            conn.execute("UPDATE konu_gecmisi SET kullanim_tarihi = ? WHERE haber_id = ?", (eski, hid))
            conn.commit()
        self.assertNotIn("S1-902", konu_bankasi._kullanim_gecmisi())


class TestZamanAsimiTumKuyruk(unittest.TestCase):
    def setUp(self):
        self.idler = []
        # Test DB'si üretimin kopyası: gerçek bekleyen kayıtlar da var. Yalnız bu testin kayıtlarını görelim.
        self._gercek_getir = db.onay_bekleyen_haberleri_getir
        self._filtre = mock.patch.object(
            hatirlat.db, "onay_bekleyen_haberleri_getir",
            side_effect=lambda limit=5: [h for h in self._gercek_getir(limit=500) if h["id"] in self.idler][:limit],
        )
        self._filtre.start()

    def tearDown(self):
        self._filtre.stop()
        with db._baglanti_al() as conn:
            for hid in self.idler:
                conn.execute("DELETE FROM konu_gecmisi WHERE haber_id = ?", (hid,))
                conn.execute("DELETE FROM onay_istekleri WHERE referans_id = ?", (str(hid),))
                conn.execute("DELETE FROM haberler WHERE id = ?", (hid,))
            conn.commit()

    def _ekle(self, **kw) -> int:
        hid = _haber_ekle(**kw)
        self.idler.append(hid)
        return hid

    def test_bes_gunu_dolduran_hepsi_arsive_alinir_sadece_yeniler_hatirlatilir(self):
        eskiler = [self._ekle(yas_gun=6 + i) for i in range(7)]       # 7 eski: eskiden 5. sıradan sonrası hiç görülmüyordu
        yeniler = [self._ekle(yas_gun=0.2), self._ekle(yas_gun=0.1)]  # 1 saatten genç değil, ama taze
        for hid in eskiler:
            _gecmis_ekle("S1-903", hid)
        with mock.patch("src.telegram.istemci.mesaj_gonder") as mesaj, \
             mock.patch("src.telegram.temizlik.icerik_onceki_mesajlarini_temizle"), \
             mock.patch("src.telegram.istemci._bot_bilgileri", return_value=("t", "1")), \
             mock.patch.object(hatirlat.db, "wal_bosalt"):
            hatirlat.main(argv=[])
        for hid in eskiler:
            self.assertEqual(db.haber_getir(hid)["durum"], "zaman_asimi", hid)
            self.assertEqual(_gecmis_sonuc(hid), ["hata"], "zaman aşımına düşenin konusu havuza dönmeli")
        for hid in yeniler:
            self.assertEqual(db.haber_getir(hid)["durum"], "onay_bekliyor", hid)
        # Yedi zaman aşımı TEK özet mesajdır (eskiden her biri ayrı mesajdı)
        ozetler = [c.args[0] for c in mesaj.call_args_list if "ZAMAN AŞIMINA UĞRADI" in c.args[0]]
        self.assertEqual(len(ozetler), 1)
        self.assertIn("7 içerik", ozetler[0])

    def test_tek_icerik_eski_mesaj_bicimini_korur(self):
        hid = self._ekle(yas_gun=8)
        with mock.patch("src.telegram.istemci.mesaj_gonder") as mesaj, \
             mock.patch.object(hatirlat.db, "wal_bosalt"):
            hatirlat.main(argv=[])
        self.assertEqual(db.haber_getir(hid)["durum"], "zaman_asimi")
        self.assertIn("Başlık:", mesaj.call_args_list[0].args[0])

    def test_plan_penceresindeki_icerik_zaman_asimina_girmez(self):
        plan = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        hid = self._ekle(yas_gun=9, planlanan_yayin=plan)
        with mock.patch("src.telegram.istemci.mesaj_gonder"), mock.patch.object(hatirlat.db, "wal_bosalt"):
            hatirlat.main(argv=[])
        self.assertEqual(db.haber_getir(hid)["durum"], "onay_bekliyor")


class TestAtlaVeCopeAt(unittest.TestCase):
    """scripts/yayinla.py gerçekten çağrılır; ağ ve Telegram sahte."""

    def setUp(self):
        spec = importlib.util.spec_from_file_location("yayinla_iade_modul", KOK / "scripts" / "yayinla.py")
        self.yayinla = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.yayinla)
        self.idler = []

    def tearDown(self):
        with db._baglanti_al() as conn:
            for hid in self.idler:
                conn.execute("DELETE FROM konu_gecmisi WHERE haber_id = ?", (hid,))
                conn.execute("DELETE FROM onay_istekleri WHERE referans_id = ?", (str(hid),))
                conn.execute("DELETE FROM haberler WHERE id = ?", (hid,))
            conn.commit()

    def _calistir(self, hedef, kaynak):
        hid = _haber_ekle(kaynak=kaynak)
        self.idler.append(hid)
        _gecmis_ekle("S1-904", hid)
        with mock.patch.object(sys, "argv", ["yayinla.py", "--tur", "haber", "--id", str(hid), "--hedef", hedef]), \
             mock.patch("src.telegram.istemci.mesaj_gonder") as mesaj, \
             mock.patch("src.telegram.akislar.uretim.konu_bankasindan_hazirla") as yeni_uret:
            self.yayinla.main()
        return hid, mesaj, yeni_uret

    def test_cope_at_konuyu_iade_eder_ve_konu_bankasi_icin_yenisini_uretir(self):
        hid, mesaj, yeni_uret = self._calistir("cope_at", "EDM Konu Bankası // S1-904")
        self.assertEqual(db.haber_getir(hid)["durum"], "iptal")
        self.assertEqual(_gecmis_sonuc(hid), ["hata"])
        yeni_uret.assert_called_once()
        metin = mesaj.call_args_list[0].args[0]
        self.assertIn("gün sonra yeniden sıraya girer", metin)
        self.assertIn("Sıradaki içerik hazırlanıyor", metin)

    def test_reddet_sozluk_kartinda_karusel_uretmez(self):
        hid, mesaj, yeni_uret = self._calistir("reddet", "EDM Sözlük Kartı // SZ-904")
        self.assertEqual(db.haber_getir(hid)["durum"], "iptal")
        yeni_uret.assert_not_called()
        self.assertNotIn("Sıradaki içerik hazırlanıyor", mesaj.call_args_list[0].args[0])

    def test_reddet_haber_onerisinde_karusel_uretmez(self):
        _, _, yeni_uret = self._calistir("reddet", "Emlakkulisi")
        yeni_uret.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
