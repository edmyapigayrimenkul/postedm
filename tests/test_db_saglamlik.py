import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import db_senkron


class TestDBSaglamlik(unittest.TestCase):
    def test_saglam_veritabani_dogrulanir(self):
        """Mevcut veritabanı quick_check ve header testinden geçmeli."""
        self.assertTrue(db_senkron.veritabani_saglam_mi())

    def test_bozuk_dosyalar_reddedilir(self):
        """0 bayt, sahte dosya veya bozuk başlık taşıyan DB'ler reddedilmeli."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. 0 bayt dosya
            bos = Path(tmpdir) / "bos.db"
            bos.write_bytes(b"")
            self.assertFalse(db_senkron.veritabani_saglam_mi(bos))

            # 2. SQLite başlığı olmayan dosya
            sahte = Path(tmpdir) / "sahte.db"
            sahte.write_bytes(b"Bu bir metin dosyasidir" * 10)
            self.assertFalse(db_senkron.veritabani_saglam_mi(sahte))

            # 3. Var olmayan dosya
            yok = Path(tmpdir) / "yok.db"
            self.assertFalse(db_senkron.veritabani_saglam_mi(yok))


if __name__ == "__main__":
    unittest.main()
