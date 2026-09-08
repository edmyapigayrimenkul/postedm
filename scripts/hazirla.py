#!/usr/bin/env python3
"""
scripts/hazirla.py — EDM Haber ve İlan Hazırlama Komutu
GitHub Actions cron'u veya elle çalıştırılır.
RSS'i tarar, sektörel haberleri seçer, Telegram grubuna onaya sunar.
Ayrıca --ilan-menu parametresiyle portföydeki ilanların seçim menüsünü gruba atar.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Kök dizini sys.path'e ekle
KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import db, fetch_listings, fetch_news, telegram_bot

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="EDM Paylaşım Hazırlayıcı")
    parser.add_argument("--ilan-menu", action="store_true", help="Telegram'a portföy ilan seçim menüsünü gönderir")
    parser.add_argument("--haber-tara", action="store_true", help="RSS kaynaklarını tarar ve yeni haberleri onaya sunar")
    args = parser.parse_args()

    # 1. Portföy senkronizasyonu
    fetch_listings.portfoyu_senkronize_et()

    if args.ilan_menu:
        log.info("Tek tıkla ilan menüsü Telegram'a gönderiliyor...")
        telegram_bot.tek_tikla_ilan_menusu_gonder()
        return

    # Varsayılan: Haberleri tara
    log.info("Emlak ve ekonomi RSS kaynakları taranıyor...")
    yeni_haberler = fetch_news.rss_tara()
    log.info("%d adet yeni alakalı haber bulundu.", len(yeni_haberler))

    bekleyenler = db.bekleyen_haberleri_getir(limit=1)
    if bekleyenler:
        h = bekleyenler[0]
        log.info("Haber onay kuyruğuna alınıyor: #%d - %s", h["id"], h["orijinal_baslik"])
        telegram_bot.haber_onayina_sun(h["id"])
    else:
        log.info("Onaya sunulacak yeni haber bulunamadı.")


if __name__ == "__main__":
    main()
