#!/usr/bin/env python3
"""Site D1 kuyruğundan bir ilan alır, yayınlar ve sonucu siteye geri yazar."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import requests

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def _ayarlar() -> tuple[str, str]:
    adres = os.environ.get(
        "EDM_SITE_KUYRUK_URL",
        "https://edmyapigayrimenkul.com/api/postedm/kuyruk",
    ).strip()
    anahtar = os.environ.get("EDM_SITE_API_ANAHTARI", "").strip()
    if not anahtar:
        raise RuntimeError("EDM_SITE_API_ANAHTARI tanımlı değil.")
    return adres, anahtar


def siradaki_isi_al() -> Optional[Dict[str, Any]]:
    adres, anahtar = _ayarlar()
    cevap = requests.get(adres, headers={"X-Postedm-Anahtari": anahtar}, timeout=30)
    if cevap.status_code == 204:
        return None
    cevap.raise_for_status()
    return cevap.json()


def sonucu_yaz(kuyruk_id: int, durum: str, sonuc: str = "", hata: str = "") -> None:
    adres, anahtar = _ayarlar()
    cevap = requests.post(
        adres,
        headers={"X-Postedm-Anahtari": anahtar, "Content-Type": "application/json"},
        json={"kuyrukId": kuyruk_id, "durum": durum, "sonuc": sonuc, "hata": hata},
        timeout=30,
    )
    cevap.raise_for_status()


def main() -> int:
    is_kaydi = siradaki_isi_al()
    if not is_kaydi:
        log.info("Sosyal paylaşım kuyruğu boş.")
        return 0

    kuyruk_id = int(is_kaydi["kuyrukId"])
    ilan = is_kaydi["ilan"]
    platformlar = [str(p) for p in is_kaydi.get("platformlar", []) if p]
    if not platformlar:
        sonucu_yaz(kuyruk_id, "hata", hata="Kuyrukta platform seçimi yok.")
        return 1

    hedef = ",".join(platformlar)
    komut = [
        sys.executable,
        str(KOK / "scripts/yayinla.py"),
        "--tur",
        "ilan",
        "--id",
        str(ilan["id"]),
        "--hedef",
        hedef,
        "--yeniden-ciz",
    ]
    try:
        # Site API'sinden gelen bu anlık görüntü yayın komutunun tek veri kaynağıdır.
        # Böylece depodaki eski listings.json fiyatı veya pasif ilan kullanılamaz.
        db.ilan_kaydet_veya_guncelle(ilan)
        calisma = subprocess.run(komut, cwd=KOK, capture_output=True, text=True, timeout=45 * 60)
        cikti = "\n".join(x for x in [calisma.stdout.strip(), calisma.stderr.strip()] if x)
        if calisma.returncode == 0:
            sonucu_yaz(kuyruk_id, "yayinlandi", sonuc=cikti[-3500:])
            log.info("Paylaşım #%s tamamlandı: %s", kuyruk_id, hedef)
            return 0
        sonucu_yaz(kuyruk_id, "hata", sonuc=cikti[-3500:], hata=f"Yayın komutu {calisma.returncode} koduyla bitti.")
        return calisma.returncode or 1
    except Exception as hata:
        sonucu_yaz(kuyruk_id, "hata", hata=f"{type(hata).__name__}: {hata}")
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as hata:
        log.exception("Site kuyruğu işlenemedi: %s", hata)
        raise SystemExit(1)
