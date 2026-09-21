"""
config.py — EDM Sosyal Medya Botu Ayar Yükleyicisi
config.yaml ve .env dosyalarını yükler, yolları ve sabitleri hazırlar.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

KOK_DIZIN = Path(__file__).resolve().parent.parent

# .env dosyasını yükle
ENV_YOLU = KOK_DIZIN / ".env"
load_dotenv(ENV_YOLU)

CONFIG_YOLU = KOK_DIZIN / "config.yaml"


def _ayarlari_yukle() -> Dict[str, Any]:
    if not CONFIG_YOLU.exists():
        return {}
    with open(CONFIG_YOLU, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


AYARLAR = _ayarlari_yukle()


def ayar_al(anahtar_yolu: str, varsayilan: Any = None) -> Any:
    """Nokta notasyonu ile ayar getirir (Örn: 'tasarim.renkler.kirmizi')."""
    parcalar = anahtar_yolu.split(".")
    mevcut = AYARLAR
    for p in parcalar:
        if isinstance(mevcut, dict) and p in mevcut:
            mevcut = mevcut[p]
        else:
            return varsayilan
    return mevcut


def env_al(anahtar: str, varsayilan: str = "") -> str:
    """Çevre değişkenini döndürür. Tanımsız veya boş string ise varsayılana düşer."""
    deger = os.getenv(anahtar)
    if deger is None or (isinstance(deger, str) and deger.strip() == "" and varsayilan != ""):
        return varsayilan
    return deger or ""


def yol_al(goreli_yol: str) -> Path:
    """Proje köküne göre mutlak Path döndürür."""
    return KOK_DIZIN / goreli_yol
