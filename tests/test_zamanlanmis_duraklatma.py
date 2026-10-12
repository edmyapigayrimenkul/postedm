"""
tests/test_zamanlanmis_duraklatma.py — duraklatma zamanlanmış koşuları da durdurur (2026-10-12 denetimi)

Eskiden `--slot`/`--format` bayrağı "elle istek" sayılıp duraklatmayı atlıyordu. 10:00 ve 12:30 cron'ları da
`--slot` ile çalıştığı için bot duraklatılmışken içerik üretiliyor, Gemini kotası ve konu harcanıyordu.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))


def _hazirla_modulu():
    spec = importlib.util.spec_from_file_location("hazirla_duraklatma_modul", KOK / "scripts" / "hazirla.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class TestDuraklatma(unittest.TestCase):
    def setUp(self):
        self.hazirla = _hazirla_modulu()

    def _calistir(self, argv, duraklatildi=True, zamanlanmis=False):
        ortam = {"ZAMANLANMIS": "true" if zamanlanmis else ""}
        tb = self.hazirla.telegram_bot
        with mock.patch.dict(os.environ, ortam), \
             mock.patch.object(sys, "argv", ["hazirla.py", *argv]), \
             mock.patch.object(tb, "bot_duraklatildi_mi", return_value=(duraklatildi, "Süresiz" if duraklatildi else "")), \
             mock.patch.object(tb, "zamanli_slot_bugun_yapildi", return_value=False), \
             mock.patch.object(tb, "zamanli_slot_isaretle"), \
             mock.patch.object(tb, "slot_icerigi_hazirla_ve_sun") as slot, \
             mock.patch.object(tb, "konu_bankasindan_hazirla") as konu, \
             mock.patch.object(tb, "reels_hazirla_ve_sun") as reels, \
             mock.patch.object(self.hazirla.db, "eski_kayitlari_temizle", return_value=0), \
             mock.patch.object(self.hazirla.db, "bayat_haberleri_ayikla", return_value=0):
            self.hazirla.main()
        return slot, konu, reels

    def test_zamanlanmis_slot_duraklatilmisken_calismaz(self):
        slot, _, _ = self._calistir(["--slot", "bilgilendirici"], zamanlanmis=True)
        slot.assert_not_called()

    def test_zamanlanmis_sozluk_slotu_duraklatilmisken_calismaz(self):
        slot, _, _ = self._calistir(["--slot", "sozluk", "--oto-yayin"], zamanlanmis=True)
        slot.assert_not_called()

    def test_elle_tetiklenen_slot_duraklatmayi_asar(self):
        slot, _, _ = self._calistir(["--slot", "bilgilendirici"], zamanlanmis=False)
        slot.assert_called_once()

    def test_duraklatilmamissa_zamanlanmis_slot_calisir(self):
        slot, _, _ = self._calistir(["--slot", "bilgilendirici"], duraklatildi=False, zamanlanmis=True)
        slot.assert_called_once_with(slot="bilgilendirici", oto_yayin=False)

    def test_elle_reels_duraklatmayi_asar_zamanlanmis_asmaz(self):
        _, _, reels = self._calistir(["--reels"], zamanlanmis=False)
        reels.assert_called_once()
        _, _, reels = self._calistir(["--reels"], zamanlanmis=True)
        reels.assert_not_called()

    def test_konu_bayragi_yalniz_konu_bankasindan_uretir(self):
        slot, konu, _ = self._calistir(["--konu"], duraklatildi=False)
        konu.assert_called_once()
        slot.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
