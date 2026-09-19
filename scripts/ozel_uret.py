#!/usr/bin/env python3
"""
scripts/ozel_uret.py — CLI Entrypoint for /link and /ozel Content Generation
GitHub Actions dispatch veya terminalden çağrılır:
  python scripts/ozel_uret.py --tur link --url "https://..."
  python scripts/ozel_uret.py --tur ozel --metin "Tarla alırken..."
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import ozel_icerik, telegram_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("ozel_uret")


def main():
    parser = argparse.ArgumentParser(description="Dış Kaynaklı Özel İçerik Üretimi")
    parser.add_argument("--tur", choices=["link", "ozel", "arastir", "dosya"], required=True, help="link, ozel, arastir veya dosya")
    parser.add_argument("--url", default="", help="Taranacak web sitesi / haber linki")
    parser.add_argument("--metin", default="", help="Özel konu / duyuru / soru metni")
    args = parser.parse_args()

    if args.tur == "link":
        url = args.url.strip()
        if not url.startswith("http"):
            telegram_bot.mesaj_gonder("⚠️ Geçersiz URL. Lütfen http:// veya https:// ile başlayan bir link girin.")
            sys.exit(1)
        haber_id = ozel_icerik.linkten_icerik_uret(url)
        if not haber_id:
            sys.exit(1)
        log.info("Linkten içerik başarıyla üretildi: #%d", haber_id)

    elif args.tur == "ozel":
        metin = args.metin.strip()
        if len(metin) < 5:
            telegram_bot.mesaj_gonder("⚠️ Çok kısa konu metni. Lütfen konuyu veya sorunuzu detaylandırın.")
            sys.exit(1)
        haber_id = ozel_icerik.konudan_ozel_icerik_uret(metin)
        if not haber_id:
            sys.exit(1)
        log.info("Özel konudan içerik başarıyla üretildi: #%d", haber_id)

    elif args.tur == "arastir":
        metin = args.metin.strip()
        if len(metin) < 3:
            telegram_bot.mesaj_gonder("⚠️ Lütfen araştırmak istediğiniz konuyu girin:\n<code>/arastir tapu harcı muafiyeti</code>")
            sys.exit(1)
        haber_id = ozel_icerik.arastir_icerik_uret(metin)
        if not haber_id:
            sys.exit(1)
        log.info("Araştırma içeriği başarıyla üretildi: #%d", haber_id)

    elif args.tur == "dosya":
        metin = args.metin.strip()
        if len(metin) < 3:
            telegram_bot.mesaj_gonder("⚠️ Lütfen dosya konusunu girin:\n<code>/dosya Kentsel Dönüşüm Süreci</code>")
            sys.exit(1)
        haber_id = ozel_icerik.dosya_icerik_uret(metin)
        if not haber_id:
            sys.exit(1)
        log.info("Dosya içeriği başarıyla üretildi: #%d", haber_id)


if __name__ == "__main__":
    main()
