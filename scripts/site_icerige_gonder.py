#!/usr/bin/env python3
"""Onaylanmış postEDM haberini EDM sitesine taslak olarak gönderir."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import db, site_icerik

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main(haber_id: int) -> int:
    haber = db.haber_getir(haber_id)
    if not haber:
        raise RuntimeError(f"Haber bulunamadı: #{haber_id}")
    sonuc = site_icerik.site_taslagi_gonder(haber)
    logging.info("Haber #%s site taslağına gönderildi: %s", haber_id, sonuc.get("id"))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="postEDM haberini site taslağına gönderir")
    parser.add_argument("--haber-id", type=int, required=True)
    args = parser.parse_args()
    try:
        raise SystemExit(main(args.haber_id))
    except Exception as hata:
        logging.error("Site taslağı gönderilemedi: %s", hata)
        raise SystemExit(1)
