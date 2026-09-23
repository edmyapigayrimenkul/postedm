"""tests/test_threads_zincir.py — Threads zinciri kaç parçanın GERÇEKTEN yayınlandığını söyler.

Gerçek olay (#241, 2026-09-23): 6 parçanın 5. ve 6.'sı "hazırlanamadı" ama rapor
"6 parçalı zincir paylaşıldı ✓" dedi; eksik kalanlar kapanış slaytlarıydı.
"""

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import threads  # noqa: E402


class TestZincirSonucu(unittest.TestCase):
    def _calistir(self, hazir_olanlar):
        sayfalar = [{"gorsel_url": f"https://cdn/{i}.jpg", "metin": f"parça {i}"} for i in range(1, 7)]
        sayac = iter(range(1, 100))
        with patch.object(threads, "_hesap_bilgileri", return_value=("u1", "t1")), \
             patch.object(threads, "_konteyner_olustur", side_effect=lambda url, p: f"c{next(sayac)}"), \
             patch.object(threads, "_konteyner_bekle", side_effect=lambda cid, tok: int(cid[1:]) in hazir_olanlar), \
             patch.object(threads, "_yayina_al", side_effect=lambda cid, u, t: f"p{cid[1:]}"), \
             patch.object(threads.time, "sleep"):
            return threads.zincir_paylas_sonuc(sayfalar)

    def test_eksik_parcalar_raporlanir(self):
        s = self._calistir({1, 2, 3, 4})
        self.assertEqual(s["kok_id"], "p1")
        self.assertEqual((s["yayinlanan"], s["toplam"], s["eksik"]), (4, 6, [5, 6]))

    def test_tam_zincir(self):
        s = self._calistir({1, 2, 3, 4, 5, 6})
        self.assertEqual((s["yayinlanan"], s["eksik"]), (6, []))

    def test_geriye_uyumlu_arayuz_kok_kimligi_doner(self):
        with patch.object(threads, "zincir_paylas_sonuc", return_value={"kok_id": "k", "yayinlanan": 1, "toplam": 2, "eksik": [2]}):
            self.assertEqual(threads.zincir_paylas([{}]), "k")


if __name__ == "__main__":
    unittest.main()
