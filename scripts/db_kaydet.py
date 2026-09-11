"""
scripts/db_kaydet.py — EDM veritabanını GitHub'a güvenli şekilde commit ve push eder.
Workflow'ların sonunda çağrılır.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from src import db_senkron

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Veritabanını GitHub'a kaydet")
    ap.add_argument("etiket", help="commit mesajı etiketi")
    ap.add_argument("--ek", nargs="*", default=[], help="veritabanı dışında eklenecek ek dosya yolları")
    args = ap.parse_args()

    damga = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    tamam = db_senkron.hemen_kaydet(f"{args.etiket} ({damga}) [skip ci]", ek_yollar=args.ek)

    if not tamam:
        print("✗ Veritabanı push EDİLEMEDİ", file=sys.stderr)
        return 1
    print("✓ Veritabanı başarıyla kaydedildi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
