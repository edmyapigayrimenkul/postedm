"""
tests/test_planli_yayin.py — Planlı yayının veritabanı tarafı (2026-09-26).

Plan Worker'ın KV'sinde, yayını 10 dakikalık Cloudflare cron'u tetikliyor
(tests/worker_planli_yayin.test.mjs). Burada yalnızca zaman içeriğe yazılır:
hatırlatıcı, planı bekleyen içeriğe "onay bekliyor" kartı atıp eski mesajları
silince "⏹ Planı iptal et" düğmesi kayboluyordu.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from scripts import hatirlat, yayinla  # noqa: E402
from src import db  # noqa: E402


class TestPlanIsareti(unittest.TestCase):
    def _yayinla(self, *arg):
        with patch.object(yayinla.sys, "argv", ["yayinla.py", *arg]), \
             patch.object(yayinla.db, "haber_guncelle") as guncelle, \
             patch("src.telegram.istemci.mesaj_gonder") as mesaj:
            yayinla.main()
        return guncelle, mesaj

    def test_planla_zamani_yazar_yayin_yapmaz(self):
        guncelle, mesaj = self._yayinla("--tur", "haber", "--id", "220", "--hedef", "planla",
                                        "--plan-an", "2026-09-26T11:30:00.000Z")
        guncelle.assert_called_once_with(220, planlanan_yayin="2026-09-26T11:30:00+00:00")
        mesaj.assert_not_called()  # gruba "durum koruması" vb. hiçbir mesaj gitmez

    def test_plan_iptal_isareti_siler(self):
        guncelle, _ = self._yayinla("--tur", "haber", "--id", "220", "--hedef", "plan_iptal")
        guncelle.assert_called_once_with(220, planlanan_yayin=None)

    def test_bozuk_zaman_ve_ilan_yazilmaz(self):
        guncelle, _ = self._yayinla("--tur", "haber", "--id", "220", "--hedef", "planla", "--plan-an", "yarın; rm -rf")
        guncelle.assert_not_called()
        guncelle, _ = self._yayinla("--tur", "ilan", "--id", "220", "--hedef", "planla",
                                    "--plan-an", "2026-09-26T11:30:00Z")
        guncelle.assert_not_called()  # ilan kimlikleri başka tabloda

    def test_yayin_plani_temizler(self):
        from tests.yayin_kaynak import yayin_kaynagi
        kaynak = yayin_kaynagi()
        self.assertIn('"planlanan_yayin": None', kaynak)

    def test_sutun_semada(self):
        with db._baglanti_al() as conn:
            kolonlar = [r["name"] for r in conn.execute("PRAGMA table_info(haberler)")]
        self.assertIn("planlanan_yayin", kolonlar)


class TestHatirlaticiPlaniBekler(unittest.TestCase):
    def test_plan_penceresinde_hatirlatilmaz_sonra_yeniden(self):
        simdi = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
        self.assertTrue(hatirlat.planli_yayin_bekliyor({"planlanan_yayin": "2026-09-26T13:00:00+00:00"}, simdi))
        self.assertTrue(hatirlat.planli_yayin_bekliyor({"planlanan_yayin": "2026-09-26T10:00:00+00:00"}, simdi))
        self.assertFalse(hatirlat.planli_yayin_bekliyor({"planlanan_yayin": "2026-09-26T08:30:00+00:00"}, simdi))
        for bos in (None, "", "bozuk"):
            self.assertFalse(hatirlat.planli_yayin_bekliyor({"planlanan_yayin": bos}, simdi))

    def test_plani_bekleyen_icerige_kart_atilmaz(self):
        taze = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        plan = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        bekleyen = [{"id": 51, "manset": "Planlı", "eklenme_tarihi": taze, "hatirlatma_sayisi": 0,
                     "durum": "onay_bekliyor", "planlanan_yayin": plan},
                    {"id": 52, "manset": "Plansız", "eklenme_tarihi": taze, "hatirlatma_sayisi": 0,
                     "durum": "onay_bekliyor", "planlanan_yayin": None}]
        with patch.object(hatirlat.db, "onay_bekleyen_haberleri_getir", return_value=bekleyen), \
             patch.object(hatirlat.db, "hatirlatma_arttir", return_value=1) as arttir, \
             patch("src.telegram.temizlik.icerik_onceki_mesajlarini_temizle") as temizle, \
             patch("src.telegram.istemci.mesaj_gonder"), \
             patch.object(hatirlat.db, "wal_bosalt"):
            hatirlat.main(argv=[])
        self.assertEqual([c.args[0] for c in arttir.call_args_list], [52])
        self.assertNotIn(51, [c.args[1] for c in temizle.call_args_list])


if __name__ == "__main__":
    unittest.main()
