#!/usr/bin/env python3
"""
scripts/git_kancalari_kur.py — Bu klonda veritabanı güvenliğini kurar.

İki şey yapar (ikisi de yalnızca bu klonun .git/ dizinine yazar):

1. data/edm.db için satır düzeyinde birleştirme sürücüsü (merge.edmdb).
   Kurulu değilse git ikili çakışmada bir tarafı bütünüyle seçer.

2. pre-commit kancası: data/edm.db KOD commit'ine giremez.
   Geçmişteki 6 veri geri sarmasının hepsi, yereldeki bayat veritabanının bir
   kod commit'iyle birlikte üretime gitmesiydi (ör. 19fc02f: 28 haber kaydı
   silindi). Veritabanını yalnızca db_senkron commit'ler; o da
   POSTEDM_DB_COMMIT=1 ile işaretler.

Yeni bir klonda bir kez çalıştır:  python3 scripts/git_kancalari_kur.py
"""

from __future__ import annotations

import stat
import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent

KANCA = """#!/bin/sh
# postedm — scripts/git_kancalari_kur.py tarafından kuruldu.
# data/edm.db yalnızca db_senkron commit'lerine girer (POSTEDM_DB_COMMIT=1).
if [ "$POSTEDM_DB_COMMIT" = "1" ]; then
  exit 0
fi
if git diff --cached --name-only | grep -qx 'data/edm.db'; then
  echo "✗ data/edm.db bu commit'e giremez." >&2
  echo "  Yereldeki veritabanı kopyası bayat olabilir; kodla birlikte gitmesi" >&2
  echo "  üretimdeki kayıtları geri sarar (geçmişte 6 kez oldu)." >&2
  echo "  Çıkarmak için:  git restore --staged data/edm.db" >&2
  exit 1
fi
exit 0
"""


def main() -> int:
    def git(*a: str) -> None:
        subprocess.run(["git", *a], cwd=KOK, check=True)

    git("config", "merge.edmdb.name", "EDM veritabanı satır düzeyinde birleştirme")
    git("config", "merge.edmdb.driver", f'"{sys.executable}" scripts/db_birlestir.py %O %A %B')

    kanca = KOK / ".git" / "hooks" / "pre-commit"
    if kanca.exists() and "postedm" not in kanca.read_text(encoding="utf-8", errors="ignore"):
        print(f"! {kanca} zaten var ve başka bir kancaya ait; dokunulmadı.", file=sys.stderr)
        return 1
    kanca.write_text(KANCA, encoding="utf-8")
    kanca.chmod(kanca.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print("✓ merge.edmdb sürücüsü ve pre-commit kancası kuruldu")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
