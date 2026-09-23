"""
tests/test_db_senkron_git.py — db_senkron'un gerçek git üzerinde uçtan uca davranışı.

İki runner aynı anda çalışıyor: biri içeriği yayınlıyor (id=3 → yayinlandi),
öbürü bayat kopyayla yeni haber ekliyor. Eski davranışta ikinci push ikili dosyayı
"--theirs" ile seçer ve yayın kaydını silerdi (geçmişte bb72440, 9143b0a).
"""

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from src import config, db, db_senkron  # noqa: E402

KIMLIK = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True,
                          env={**os.environ, **KIMLIK}).stdout


@unittest.skipUnless(shutil.which("git"), "git yok")
class TestDbSenkronGit(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.uzak = self.d / "uzak.git"
        git(self.d, "init", "--bare", "-b", "main", str(self.uzak))
        tohum = self.d / "tohum"
        git(self.d, "clone", str(self.uzak), str(tohum))
        (tohum / "data").mkdir()
        c = sqlite3.connect(tohum / "data/edm.db")
        c.executescript("CREATE TABLE haberler (id INTEGER PRIMARY KEY, manset TEXT, durum TEXT);"
                        "CREATE TABLE ayarlar (anahtar TEXT PRIMARY KEY, deger TEXT);")
        c.executemany("INSERT INTO haberler VALUES (?, ?, 'onay_bekliyor')", [(i, f"h{i}") for i in range(1, 6)])
        c.commit(); c.close()
        git(tohum, "add", "."); git(tohum, "commit", "-m", "tohum"); git(tohum, "push", "origin", "HEAD:main")
        self.x = self.d / "x"; git(self.d, "clone", str(self.uzak), str(self.x))
        self.y = self.d / "y"; git(self.d, "clone", str(self.uzak), str(self.y))

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _runner(self, kok: Path):
        """db_senkron'u verilen klonda, test modu KAPALI çalıştırır."""
        return mock.patch.multiple(
            config, KOK_DIZIN=kok, yol_al=lambda p, k=kok: k / p, test_modu=lambda: False,
        ), mock.patch.object(db, "wal_bosalt", lambda: None)

    def _sql(self, kok, sql):
        c = sqlite3.connect(kok / "data/edm.db"); c.execute(sql); c.commit(); c.close()

    def test_eszamanli_iki_runner_birbirini_ezmez(self):
        a, b = self._runner(self.x)
        with a, b:
            self._sql(self.x, "UPDATE haberler SET durum='yayinlandi' WHERE id=3")
            self.assertTrue(db_senkron.hemen_kaydet("db: x yayinladi"))
        a, b = self._runner(self.y)
        with a, b:
            self._sql(self.y, "INSERT INTO haberler VALUES (6, 'h6', 'onay_bekliyor')")
            self.assertTrue(db_senkron.hemen_kaydet("db: y yeni haber"))

        z = self.d / "z"; git(self.d, "clone", str(self.uzak), str(z))
        c = sqlite3.connect(z / "data/edm.db")
        self.assertEqual(c.execute("SELECT durum FROM haberler WHERE id=3").fetchone()[0], "yayinlandi")
        self.assertEqual(c.execute("SELECT COUNT(*) FROM haberler").fetchone()[0], 6)
        c.close()

    def test_kalici_git_kimligi_yazilmaz(self):
        a, b = self._runner(self.x)
        with a, b:
            self._sql(self.x, "UPDATE haberler SET manset='x' WHERE id=1")
            db_senkron.hemen_kaydet("db: kimlik")
        yerel = subprocess.run(["git", "config", "--local", "user.name"], cwd=self.x, capture_output=True, text=True)
        self.assertEqual(yerel.stdout.strip(), "", "db_senkron klonun git kimliğini kalıcı değiştirmemeli")
        yazar = git(self.x, "log", "-1", "--format=%an")
        self.assertEqual(yazar.strip(), "github-actions[bot]")

    def test_uzaktan_tazele_yerel_degisikligi_kaybetmez(self):
        a, b = self._runner(self.y)
        with a, b:
            self._sql(self.y, "INSERT INTO haberler VALUES (6, 'h6', 'yeni')")
            db_senkron.hemen_kaydet("db: y")
        a, b = self._runner(self.x)
        with a, b:
            self._sql(self.x, "INSERT INTO haberler VALUES (7, 'yerel, kaydedilmemiş', 'yeni')")
            self.assertTrue(db_senkron.uzaktan_tazele())
        c = sqlite3.connect(self.x / "data/edm.db")
        ids = [r[0] for r in c.execute("SELECT id FROM haberler ORDER BY id")]
        c.close()
        self.assertEqual(ids, [1, 2, 3, 4, 5, 6, 7])

    def test_ilgisiz_eski_stash_uygulanmaz(self):
        (self.y / "not.txt").write_text("eski iş")
        git(self.y, "add", "not.txt"); git(self.y, "stash")
        a, b = self._runner(self.x)
        with a, b:
            self._sql(self.x, "UPDATE haberler SET manset='x' WHERE id=2")
            db_senkron.hemen_kaydet("db: x")
        a, b = self._runner(self.y)
        with a, b:
            self._sql(self.y, "UPDATE haberler SET manset='y' WHERE id=4")
            self.assertTrue(db_senkron.hemen_kaydet("db: y"))
        self.assertFalse((self.y / "not.txt").exists(), "eski stash geri uygulanmamalı")
        self.assertIn("eski iş", git(self.y, "stash", "show", "-p", "--include-untracked") + git(self.y, "stash", "list"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
