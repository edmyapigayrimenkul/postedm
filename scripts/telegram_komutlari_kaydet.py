#!/usr/bin/env python3
"""
scripts/telegram_komutlari_kaydet.py — Telegram bot komutlarını setMyCommands ile Telegram API'sine kaydeder.

Kullanım:
    python scripts/telegram_komutlari_kaydet.py
    python scripts/telegram_komutlari_kaydet.py --kuru
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import requests

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("telegram_komutlar")

BOT_KOMUTLARI = [
    {"command": "gonderi", "description": "Günün konusundan onaylı post hazırla"},
    {"command": "reels", "description": "9:16 dikey video ve metin üret"},
    {"command": "sozluk", "description": "Gayrimenkul sözlüğü kartı üret"},
    {"command": "dogrusu", "description": "Nedir Doğrusu karşılaştırma kartı"},
    {"command": "vaka", "description": "Hukuki vaka analizi carouseli"},
    {"command": "soru", "description": "Net Cevap rehberi kartı üret"},
    {"command": "haber", "description": "Sektörel haber önerilerini tara"},
    {"command": "ilanlar", "description": "Portföy ilan menüsünü aç"},
    {"command": "panel", "description": "İnteraktif kontrol merkezini aç"},
    {"command": "planlar", "description": "Bekleyen planlı yayınları yönet"},
    {"command": "durum", "description": "Yayın takvimi ve bot durumu"},
    {"command": "rapor", "description": "Sistem, bulut ve AI kota tablosu"},
    {"command": "havuz", "description": "Konu bankası havuz durumu"},
    {"command": "ayar", "description": "Çalışma ve kanal ayarları"},
    {"command": "durdur", "description": "Otomatik akışı duraklat"},
    {"command": "devam", "description": "Akışı tekrar devam ettir"},
    {"command": "yardim", "description": "Kullanım kılavuzu ve komutlar"},
]


def komutlari_kaydet(kuru: bool = False) -> bool:
    token = config.env_al("TELEGRAM_BOT_TOKEN")
    if not token or kuru:
        log.info("Komut listesi (%d adet komut):\n%s", len(BOT_KOMUTLARI), json.dumps(BOT_KOMUTLARI, ensure_ascii=False, indent=2))
        if not token:
            log.warning("TELEGRAM_BOT_TOKEN tanımlı değil, ağ çağrısı atlandı.")
            return False
        log.info("Kuru mod: ağ çağrısı atlandı.")
        return True

    url = f"https://api.telegram.org/bot{token}/setMyCommands"
    try:
        resp = requests.post(url, json={"commands": BOT_KOMUTLARI}, timeout=10)
        veri = resp.json()
        if veri.get("ok"):
            log.info("✅ Telegram komutları başarıyla kaydedildi (%d adet).", len(BOT_KOMUTLARI))
            return True
        log.error("Telegram API hatası: %s", veri)
        return False
    except Exception as e:
        log.error("İstek başarısız: %s", e)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram bot komutlarını kaydet")
    parser.add_argument("--kuru", action="store_true", help="Ağa istek atmadan komutları listeler")
    args = parser.parse_args()
    ok = komutlari_kaydet(kuru=args.kuru)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
