"""
tests/test_telegram_paketi.py — src/telegram/ paketinin yapı kuralları (Faz 2, 2026-10-13).

Davranışın bütünü tests/test_telegram_altin.py'de donduruldu; burada paketin mimari sözleşmeleri sınanır
(bkz. ARCHITECTURE.md §2): dosya boyutu, yukarı bağımlılık yok, kardeş işlevler modül üzerinden çağrılır.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import ast
import sys
import unittest
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

PAKET = KOK / "src" / "telegram"


def _moduller():
    return sorted(p for p in PAKET.rglob("*.py") if p.name != "__init__.py")


class TestTelegramPaketYapisi(unittest.TestCase):
    def test_hicbir_modul_dev_degil(self):
        buyuk = [f"{y.relative_to(KOK)}: {y.read_text(encoding='utf-8').count(chr(10))} satır"
                 for y in _moduller() if y.read_text(encoding="utf-8").count("\n") > 250]
        self.assertFalse(buyuk, f"Bölünmesi gereken modüller: {buyuk}")

    def test_paket_telegram_bot_a_bagimli_degil(self):
        """Bağımlılık yalnız aşağı akar: telegram_bot paketi içeri alır, paket telegram_bot'u bilmez."""
        ihlal = []
        for y in _moduller():
            for n in ast.walk(ast.parse(y.read_text(encoding="utf-8"))):
                adlar = []
                if isinstance(n, ast.ImportFrom):
                    adlar = [n.module or ""] + [a.name for a in n.names]
                elif isinstance(n, ast.Import):
                    adlar = [a.name for a in n.names]
                if any(a.split(".")[-1] == "telegram_bot" for a in adlar):
                    ihlal.append(f"{y.relative_to(KOK)}:{n.lineno}")
        self.assertFalse(ihlal, f"src/telegram telegram_bot'u içe aktarıyor: {ihlal}")

    def test_kardes_islevler_modul_uzerinden_cagrilir(self):
        """`from .istemci import mesaji_sil` yok, `from . import istemci` var: testlerin yaması her yerde geçsin (ARCHITECTURE.md §2 kural 4)."""
        ihlal = []
        for y in _moduller():
            for n in ast.walk(ast.parse(y.read_text(encoding="utf-8"))):
                if isinstance(n, ast.ImportFrom) and n.level == 1 and n.module:
                    ihlal.append(f"{y.relative_to(KOK)}:{n.lineno} from .{n.module} import ...")
        self.assertFalse(ihlal, f"Kardeş modülden ad alma yasak: {ihlal}")

    def test_eski_adlar_telegram_bot_tan_erisilebilir(self):
        """22 kaynak ve 31 test dosyası bu adlarla çağırıyor; taşınınca kaybolmamalı."""
        from src import telegram_bot
        for ad in ("mesaj_gonder", "mesaji_sil", "mesaji_guncelle", "menuyu_degistir", "aciklama_metni_kutusu",
                   "fotograf_gonder", "video_gonder", "medya_grubu_gonder", "slaytlari_gonder",
                   "son_medya_grubu_mesaj_idleri", "icerik_onceki_mesajlarini_temizle", "son_mesajlari_sil",
                   "_bot_bilgileri", "_istek", "TELEGRAM_API_URL"):
            self.assertTrue(hasattr(telegram_bot, ad), ad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
