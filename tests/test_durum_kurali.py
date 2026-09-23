"""
tests/test_durum_kurali.py — İçerik durum geçişleri (src/durum_kurali.py).

Gerçek olay (2026-09-23): #123 DB'de 'iptal' ama Instagram'da canlı; #68
'reddedildi' ama canlı. yayinla.py durumu okumadan yayınlıyor, iptal/reddet
de yayındaki içeriğin durumunu koşulsuz eziyordu.
"""

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import sys
import unittest
from pathlib import Path
from unittest import mock

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from src import db, durum_kurali  # noqa: E402


class TestKurallar(unittest.TestCase):
    def test_kapali_icerik_yayinlanamaz(self):
        for durum in ("iptal", "reddedildi", "kaldirildi", "elendi", "engellendi"):
            self.assertIsNotNone(durum_kurali.yayin_engeli({"id": 1, "durum": durum}), durum)
        for durum in ("onay_bekliyor", "yeni", "hata", "zaman_asimi", "yayinlandi"):
            self.assertIsNone(durum_kurali.yayin_engeli({"id": 1, "durum": durum}), durum)

    def test_yayindaki_icerige_taslak_islemi_uygulanmaz(self):
        self.assertIsNotNone(durum_kurali.taslak_islem_engeli({"id": 1, "durum": "yayinlandi"}, "iptal"))
        # durum geride kalmış olsa da kanal kimliği varsa yayında sayılır
        self.assertIsNotNone(durum_kurali.taslak_islem_engeli({"id": 1, "durum": "iptal", "threads_post_id": "t"}, "yenile"))
        self.assertIsNone(durum_kurali.taslak_islem_engeli({"id": 1, "durum": "onay_bekliyor"}, "iptal"))

    def test_ayni_kanala_ikinci_kez_gonderilmez(self):
        haber = {"instagram_post_id": "ig", "facebook_post_id": "fb"}
        atla = durum_kurali.tekrar_gonderilmeyecekler(haber, ["instagram", "threads", "facebook_reels", "story"])
        self.assertEqual(atla, ["instagram", "facebook_reels"])

    def test_yayindaki_icerik_basarisiz_denemeyle_hataya_dusmez(self):
        self.assertEqual(durum_kurali.sonraki_durum("yayinlandi", False), "yayinlandi")
        self.assertEqual(durum_kurali.sonraki_durum("onay_bekliyor", False), "hata")
        self.assertEqual(durum_kurali.sonraki_durum("onay_bekliyor", True), "yayinlandi")


class TestYayinlaKorumasi(unittest.TestCase):
    """scripts/yayinla.py gerçekten çağrılır; ağ ve Telegram sahte."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("yayinla_modul", KOK / "scripts" / "yayinla.py")
        self.yayinla = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.yayinla)
        db.tablolari_olustur() if hasattr(db, "tablolari_olustur") else None
        with db._baglanti_al() as conn:
            cur = conn.execute(
                "INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, eklenme_tarihi, manset, durum) "
                "VALUES ('birim-testi', 'b', ?, '2026-09-23', 'm', 'onay_bekliyor')",
                (f"test://durum/{id(self)}",),
            )
            self.haber_id = cur.lastrowid
            conn.commit()

    def tearDown(self):
        with db._baglanti_al() as conn:
            conn.execute("DELETE FROM haberler WHERE id = ?", (self.haber_id,))
            conn.commit()

    def _calistir(self, hedef):
        with mock.patch.object(sys, "argv", ["yayinla.py", "--tur", "haber", "--id", str(self.haber_id), "--hedef", hedef]), \
             mock.patch.object(self.yayinla.telegram_bot, "mesaj_gonder") as mesaj, \
             mock.patch.object(self.yayinla.telegram_bot, "konu_bankasindan_hazirla") as yeni_uret, \
             mock.patch.object(self.yayinla.instagram, "carousel_yayinla") as ig_c, \
             mock.patch.object(self.yayinla.instagram, "tekil_gorsel_yayinla") as ig_t:
            self.yayinla.main()
        return mesaj, yeni_uret, ig_c, ig_t

    def test_iptal_edilmis_icerik_eski_butonla_yayinlanmaz_123(self):
        db.haber_guncelle(self.haber_id, durum="iptal")
        mesaj, _, ig_c, ig_t = self._calistir("ig,threads")
        ig_c.assert_not_called(); ig_t.assert_not_called()
        self.assertIn("yayınlanmadı", mesaj.call_args[0][0])

    def test_yayindaki_icerik_atla_ile_ezilmez_ve_yeni_uretim_baslamaz(self):
        db.haber_guncelle(self.haber_id, durum="yayinlandi", instagram_post_id="ig123")
        mesaj, yeni_uret, _, _ = self._calistir("iptal")
        self.assertEqual(db.haber_getir(self.haber_id)["durum"], "yayinlandi")
        yeni_uret.assert_not_called()
        self.assertIn("zaten yayında", mesaj.call_args[0][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
