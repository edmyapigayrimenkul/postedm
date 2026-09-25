"""
tests/test_test_izolasyonu.py — Her test dosyası üretim DB'sini korumalı.

NİYE VAR: `python -m unittest discover tests` dosyaları üst düzey modül olarak
yükler; tests/__init__.py hiç çalışmaz. Test modunu açmayan tek bir dosya,
taklit edilmemiş bir yan etki üzerinden data/edm.db'ye yazar. test_sozlesme.py
böyleydi: hatirlat/yayinla akışındaki mükerrer mesaj temizliği gerçek
onay_istekleri kaydını "silindi"ye, bir öneriyi "elendi"ye çekti ve CI'daki
"Testler data/edm.db'yi değiştirmedi" adımı üç commit boyunca kırmızı kaldı.
Dosyanın içinde "POSTEDM_TEST_MODU" geçmesi yetmiyordu (orada yalnızca bir
patch.dict vardı); bu yüzden metin araması değil, üst düzey atama aranıyor.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import ast
import unittest
from pathlib import Path

TESTLER = Path(__file__).resolve().parent


def _test_modunu_aciyor_mu(dugum: ast.stmt) -> bool:
    """os.environ.setdefault("POSTEDM_TEST_MODU", "1") ya da os.environ[...] = "1"."""
    return "POSTEDM_TEST_MODU" in ast.unparse(dugum) and "patch" not in ast.unparse(dugum)


def _proje_importu_mu(dugum: ast.stmt) -> bool:
    if isinstance(dugum, ast.ImportFrom):
        return (dugum.module or "").split(".")[0] in ("src", "scripts")
    if isinstance(dugum, ast.Import):
        return any(a.name.split(".")[0] in ("src", "scripts") for a in dugum.names)
    return False


class TestIzolasyonu(unittest.TestCase):
    def test_her_dosya_proje_importundan_once_test_modunu_acar(self) -> None:
        eksikler = []
        for yol in sorted(TESTLER.glob("test_*.py")):
            govde = ast.parse(yol.read_text(encoding="utf-8")).body
            acan = next((i for i, d in enumerate(govde) if _test_modunu_aciyor_mu(d)), None)
            ilk_import = next((i for i, d in enumerate(govde) if _proje_importu_mu(d)), len(govde))
            if acan is None or acan > ilk_import:
                eksikler.append(yol.name)
        self.assertEqual(
            eksikler, [],
            "Bu dosyalar src/scripts'i yüklemeden önce test modunu açmıyor; "
            "başına şunu ekleyin: os.environ.setdefault(\"POSTEDM_TEST_MODU\", \"1\")",
        )


if __name__ == "__main__":
    unittest.main()
