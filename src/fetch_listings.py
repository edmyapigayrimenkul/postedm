"""
fetch_listings.py — EDM Ofis İlanları Okuyucu & Senkronizasyon Modülü
site/data/listings.json dosyasını okuyup SQLite'a senkronize eder.
Telegram'dan tek tıkla paylaşım için ilanları sunar.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config, db

log = logging.getLogger(__name__)


def listings_json_yolu() -> Path:
    kaynak = config.ayar_al("ilanlar.kaynak_dosya", "../site/data/listings.json")
    return (config.KOK_DIZIN / kaynak).resolve()


def portfoyu_senkronize_et() -> int:
    """site/data/listings.json dosyasını okuyup veritabanını günceller."""
    dosya = listings_json_yolu()
    if not dosya.exists():
        log.warning("listings.json dosyası bulunamadı: %s", dosya)
        return 0

    try:
        with open(dosya, "r", encoding="utf-8") as f:
            veri = json.load(f)
    except Exception as e:
        log.error("listings.json okunurken hata: %s", e)
        return 0

    ilanlar = veri.get("ilanlar", [])
    sayac = 0
    for item in ilanlar:
        db.ilan_kaydet_veya_guncelle(item)
        sayac += 1

    log.info("%d adet ilan veritabanına senkronize edildi.", sayac)
    return sayac


def aktif_ilanlar(limit: int = 20) -> List[Dict[str, Any]]:
    """Henüz paylaşılmamış veya en az paylaşılmış aktif ilanları listeler."""
    return db.aktif_ilanlari_getir(limit=limit)


def ilan_detay(ilan_id: str) -> Optional[Dict[str, Any]]:
    """Belirli bir ilanın detayını getirir."""
    return db.ilan_getir(ilan_id)


def ilan_fiyat_bicimlendir(fiyat: float, para_birimi: str = "TRY") -> str:
    """Emlak paftası için temiz ve net fiyat metni üretir (örn: 25 mn ₺, 850 bin ₺)."""
    if not fiyat or fiyat <= 0:
        return "Fiyat Belirtilmedi"
    
    simge = "₺" if para_birimi == "TRY" else ("$" if para_birimi == "USD" else "€")

    if fiyat >= 1_000_000:
        milyon = fiyat / 1_000_000
        if milyon == int(milyon):
            return f"{int(milyon)} mn {simge}"
        return f"{milyon:.1f}".replace(".", ",") + f" mn {simge}"
    elif fiyat >= 1_000:
        bin_tl = fiyat / 1_000
        if bin_tl == int(bin_tl):
            return f"{int(bin_tl)} bin {simge}"
        return f"{bin_tl:.1f}".replace(".", ",") + f" bin {simge}"
    else:
        return f"{int(fiyat):,} {simge}".replace(",", ".")
