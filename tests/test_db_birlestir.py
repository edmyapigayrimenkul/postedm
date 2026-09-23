"""
tests/test_db_birlestir.py — data/edm.db satır düzeyinde üç yönlü birleştirme.

Her senaryo gerçek bir olaydan: geçmişte db_senkron ikili dosyayı "--theirs" ile
seçiyordu ve 143 DB commit'inin 6'sında kayıt geri gitti (19fc02f: 28 haber
silindi; bb72440 ve 9143b0a: yayınlanmış bir içerik "yayınlanmamış"a döndü).
"""

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from src import db_birlestir  # noqa: E402

SEMA = """
CREATE TABLE haberler (id INTEGER PRIMARY KEY AUTOINCREMENT, manset TEXT, durum TEXT,
                       instagram_post_id TEXT, threads_post_id TEXT);
CREATE TABLE onay_istekleri (id INTEGER PRIMARY KEY AUTOINCREMENT, tur TEXT, referans_id TEXT, durum TEXT);
CREATE TABLE ayarlar (anahtar TEXT PRIMARY KEY, deger TEXT);
"""


class TestUcYonluBirlestirme(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.taban = self.d / "o.db"
        c = sqlite3.connect(self.taban)
        c.executescript(SEMA)
        c.executemany("INSERT INTO haberler (id, manset, durum) VALUES (?, ?, ?)",
                      [(i, f"haber {i}", "onay_bekliyor") for i in range(1, 6)])
        c.execute("INSERT INTO ayarlar VALUES ('son_format', 'sozluk')")
        c.commit(); c.close()
        self.a = self.d / "a.db"; shutil.copy2(self.taban, self.a)
        self.b = self.d / "b.db"; shutil.copy2(self.taban, self.b)
        self.sonuc = self.d / "s.db"

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _yaz(self, yol, sql, *params):
        c = sqlite3.connect(yol); c.execute(sql, params); c.commit(); c.close()

    def _oku(self, sql, *params):
        c = sqlite3.connect(self.sonuc); r = c.execute(sql, params).fetchall(); c.close(); return r

    def _birlestir(self):
        return db_birlestir.birlestir(self.taban, self.a, self.b, self.sonuc)

    def test_iki_taraftaki_bagimsiz_eklemeler_korunur(self):
        self._yaz(self.a, "INSERT INTO haberler (id, manset, durum) VALUES (6, 'uzak', 'yeni')")
        self._yaz(self.b, "INSERT INTO haberler (id, manset, durum) VALUES (7, 'yerel', 'yeni')")
        self._birlestir()
        self.assertEqual([r[0] for r in self._oku("SELECT id FROM haberler ORDER BY id")], [1, 2, 3, 4, 5, 6, 7])

    def test_bayat_taraf_kayit_silemez_19fc02f(self):
        """Uzak 28 yeni haber üretti; bayat yerel kopya onları hiç görmedi. Hepsi kalmalı."""
        c = sqlite3.connect(self.a)
        c.executemany("INSERT INTO haberler (id, manset, durum) VALUES (?, ?, 'yeni')",
                      [(i, f"yeni {i}") for i in range(6, 34)])
        c.commit(); c.close()
        self._yaz(self.b, "UPDATE ayarlar SET deger='vaka' WHERE anahtar='son_format'")
        self._birlestir()
        self.assertEqual(self._oku("SELECT COUNT(*) FROM haberler")[0][0], 33)
        self.assertEqual(self._oku("SELECT deger FROM ayarlar")[0][0], "vaka")

    def test_yayinlanmis_icerik_yayinlanmamisa_donmez(self):
        self._yaz(self.a, "UPDATE haberler SET durum='yayinlandi', instagram_post_id='ig1' WHERE id=3")
        self._yaz(self.b, "UPDATE haberler SET durum='iptal' WHERE id=3")
        rapor = self._birlestir()
        self.assertEqual(self._oku("SELECT durum, instagram_post_id FROM haberler WHERE id=3")[0], ("yayinlandi", "ig1"))
        self.assertTrue(rapor.cakisma)

    def test_farkli_sutun_guncellemeleri_birlesir(self):
        self._yaz(self.a, "UPDATE haberler SET instagram_post_id='ig2' WHERE id=2")
        self._yaz(self.b, "UPDATE haberler SET threads_post_id='th2' WHERE id=2")
        self._birlestir()
        self.assertEqual(self._oku("SELECT instagram_post_id, threads_post_id FROM haberler WHERE id=2")[0], ("ig2", "th2"))

    def test_dolu_kimlik_bosla_ezilmez(self):
        self._yaz(self.a, "UPDATE haberler SET instagram_post_id='ig4' WHERE id=4")
        self._yaz(self.b, "UPDATE haberler SET instagram_post_id=NULL, manset='x' WHERE id=4")
        # b tabanda NULL olan sütunu NULL bıraktı (değiştirmedi) — a'nınki kalmalı
        self._birlestir()
        self.assertEqual(self._oku("SELECT instagram_post_id FROM haberler WHERE id=4")[0][0], "ig4")

    def test_ayni_numarali_iki_farkli_haber_yeniden_numaralanir(self):
        self._yaz(self.a, "INSERT INTO haberler (id, manset, durum) VALUES (6, 'uzaktaki 6', 'onay_bekliyor')")
        self._yaz(self.b, "INSERT INTO haberler (id, manset, durum) VALUES (6, 'yereldeki 6', 'onay_bekliyor')")
        self._yaz(self.b, "INSERT INTO onay_istekleri (id, tur, referans_id, durum) VALUES (1, 'haber', '6', 'bekliyor')")
        rapor = self._birlestir()
        satirlar = dict(self._oku("SELECT manset, id FROM haberler WHERE id >= 6"))
        self.assertEqual(satirlar["uzaktaki 6"], 6)
        yeni = satirlar["yereldeki 6"]
        self.assertEqual(yeni, 7)
        # yerelin onay isteği yeni numarayı gösteriyor
        self.assertEqual(self._oku("SELECT referans_id FROM onay_istekleri")[0][0], "7")
        self.assertEqual(rapor.yeniden_numaralanan["haberler"], {6: 7})

    def test_ayni_satiri_iki_taraf_ayni_eklediyse_tek_kalir(self):
        for yol in (self.a, self.b):
            self._yaz(yol, "INSERT INTO haberler (id, manset, durum) VALUES (6, 'aynı', 'yeni')")
        self._birlestir()
        self.assertEqual(self._oku("SELECT COUNT(*) FROM haberler WHERE id=6")[0][0], 1)

    def test_temizlik_silmesi_uygulanir(self):
        self._yaz(self.b, "DELETE FROM haberler WHERE id=5")
        self._birlestir()
        self.assertEqual(self._oku("SELECT COUNT(*) FROM haberler WHERE id=5")[0][0], 0)

    def test_yayina_girmis_kayit_bayat_silmeyle_gitmez(self):
        self._yaz(self.a, "UPDATE haberler SET durum='yayinlandi' WHERE id=5")
        self._yaz(self.b, "DELETE FROM haberler WHERE id=5")
        self._birlestir()
        self.assertEqual(self._oku("SELECT durum FROM haberler WHERE id=5")[0][0], "yayinlandi")

    def test_yeni_sutun_sema_farki(self):
        self._yaz(self.b, "ALTER TABLE haberler ADD COLUMN sutun TEXT")
        self._yaz(self.b, "UPDATE haberler SET sutun='S1' WHERE id=1")
        self._birlestir()
        self.assertEqual(self._oku("SELECT sutun FROM haberler WHERE id=1")[0][0], "S1")

    def test_autoincrement_sayaci_geri_kalmaz(self):
        self._yaz(self.b, "INSERT INTO haberler (manset, durum) VALUES ('oto', 'yeni')")
        self._birlestir()
        c = sqlite3.connect(self.sonuc)
        c.execute("INSERT INTO haberler (manset, durum) VALUES ('sonraki', 'yeni')")
        ids = [r[0] for r in c.execute("SELECT id FROM haberler ORDER BY id")]
        c.close()
        self.assertEqual(len(ids), len(set(ids)))

    def test_taban_yoksa_iki_tarafin_birlesimi(self):
        self._yaz(self.b, "INSERT INTO haberler (id, manset, durum) VALUES (8, 'b', 'yeni')")
        db_birlestir.birlestir(None, self.a, self.b, self.sonuc)
        self.assertEqual(self._oku("SELECT COUNT(*) FROM haberler")[0][0], 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
