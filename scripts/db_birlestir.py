#!/usr/bin/env python3
"""
scripts/db_birlestir.py — data/edm.db için git birleştirme sürücüsü.

    git config merge.edmdb.driver "python3 scripts/db_birlestir.py %O %A %B"
    (.gitattributes: data/edm.db merge=edmdb)

İkili SQLite dosyasında git'in tek seçeneği bir tarafı bütünüyle seçmekti; bu da
öbür tarafın tüm değişikliklerini siliyordu. Sürücü satır düzeyinde birleştirir
(src/db_birlestir.py). Hata olursa sıfırdan farklı döner ve git dosyayı çakışmalı
bırakır — sessizce yanlış sonuç yazmaz.

Kurulum: python3 scripts/git_kancalari_kur.py
"""

from __future__ import annotations

import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from src import db_birlestir  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("kullanım: db_birlestir.py TABAN BIZIM(%A) ONLARIN(%B)", file=sys.stderr)
        return 2
    taban, a, b = (Path(p) for p in argv[1:])
    try:
        rapor = db_birlestir.birlestir(taban, a, b, a)
    except Exception as e:
        print(f"edm.db birleştirilemedi: {e}", file=sys.stderr)
        return 1
    print(f"edm.db satır düzeyinde birleştirildi: {rapor.ozet()}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
