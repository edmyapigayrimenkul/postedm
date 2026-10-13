"""
config.py — EDM Sosyal Medya Botu Ayar Yükleyicisi
config.yaml ve .env dosyalarını yükler, yolları ve sabitleri hazırlar.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

KOK_DIZIN = Path(__file__).resolve().parent.parent


def test_modu() -> bool:
    """tests/ paketi ve doğrudan çalıştırılan test dosyaları bunu "1" yapar."""
    return os.environ.get("POSTEDM_TEST_MODU") == "1"


def _test_calisma_dizini() -> Path:
    yol = Path(tempfile.gettempdir()) / f"postedm-test-{os.getpid()}"
    yol.mkdir(parents=True, exist_ok=True)
    return yol


# TEST İZOLASYONU (2026-09-23): testler eskiden gerçek .env'i yüklüyor ve gerçek
# data/edm.db'ye yazıyordu. Sonuç: yerelde test koşmak TikTok token'larını
# "yeni_access_123" ile ezdi; üretim DB'sine 60 sahte "yayinlandi" satırı ve
# 21 sahte metrik (reach=1420) sızdı. Test modunda gerçek .env YÜKLENMEZ —
# mock'lanmamış bir çağrı canlı API'ye gerçek token'la gidemez; yerel test
# ortamı CI ile (orada .env yok) aynı olur. DB ve .env yazımları geçici kopyaya.
if test_modu():
    ENV_YOLU = _test_calisma_dizini() / ".env"
    ENV_YOLU.touch(exist_ok=True)
else:
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


def db_yolu() -> Path:
    """Üretimde data/edm.db; test modunda onun süreç başına geçici kopyası.

    Kopya (boş şema değil) seçildi: bazı testler mevcut konu geçmişine ve
    ayarlara dayanıyor. Önemli olan yazımların üretime dokunmaması.
    """
    gercek = yol_al("data/edm.db")
    if not test_modu():
        return gercek
    kopya = _test_calisma_dizini() / "edm.db"
    if not kopya.exists() and gercek.exists():
        shutil.copy2(gercek, kopya)
    return kopya


def veri_yolu(ad: str) -> Path:
    """`data/<ad>` yolu; test modunda süreç başına geçici dizin.

    Hata günlüğü ve yayın raporu işareti eskiden göreli `Path("data")` ile yazılıyordu: testler depodaki
    `data/` klasörüne dosya sızdırıyordu (test izolasyonu, MEMORY §7.3). DB ve .env zaten böyle ayrılıyordu."""
    if test_modu():
        klasor = _test_calisma_dizini() / "data"
        klasor.mkdir(parents=True, exist_ok=True)
        return klasor / ad
    return yol_al("data") / ad
