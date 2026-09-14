#!/usr/bin/env python3
"""Site D1 kuyruğundan bir ilan alır, yayınlar ve sonucu siteye geri yazar."""

from __future__ import annotations

import argparse
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
OIDC_HEDEF_KITLE = "edm-postedm-site"
_OIDC_JETONU: Optional[str] = None


def _kimlik_basliklari() -> Dict[str, str]:
    """Yerelde ortak anahtarı, GitHub Actions'ta kısa ömürlü OIDC jetonunu kullanır."""
    ortak_anahtar = os.environ.get("EDM_SITE_API_ANAHTARI", "").strip()
    if ortak_anahtar:
        return {"X-Postedm-Anahtari": ortak_anahtar}

    global _OIDC_JETONU
    if not _OIDC_JETONU:
        oidc_adresi = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "").strip()
        oidc_istek_jetonu = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "").strip()
        if not oidc_adresi or not oidc_istek_jetonu:
            raise RuntimeError("EDM_SITE_API_ANAHTARI veya GitHub Actions OIDC kimliği tanımlı değil.")
        cevap = requests.get(
            oidc_adresi,
            headers={"Authorization": f"Bearer {oidc_istek_jetonu}"},
            params={"audience": OIDC_HEDEF_KITLE},
            timeout=30,
        )
        cevap.raise_for_status()
        _OIDC_JETONU = str(cevap.json().get("value") or "").strip()
        if not _OIDC_JETONU:
            raise RuntimeError("GitHub Actions OIDC yanıtında jeton yok.")
    return {"Authorization": f"Bearer {_OIDC_JETONU}"}


def _ayarlar() -> tuple[str, Dict[str, str]]:
    adres = os.environ.get(
        "EDM_SITE_KUYRUK_URL",
        "https://edmyapigayrimenkul.com/api/postedm/kuyruk",
    ).strip()
    return adres, _kimlik_basliklari()


def siradaki_isi_al() -> Optional[Dict[str, Any]]:
    adres, basliklar = _ayarlar()
    cevap = requests.get(adres, headers=basliklar, timeout=30)
    if cevap.status_code == 204:
        return None
    cevap.raise_for_status()
    return cevap.json()


def sonucu_yaz(kuyruk_id: int, durum: str, sonuc: str = "", hata: str = "") -> None:
    adres, kimlik_basliklari = _ayarlar()
    cevap = requests.post(
        adres,
        headers={**kimlik_basliklari, "Content-Type": "application/json"},
        json={"kuyrukId": kuyruk_id, "durum": durum, "sonuc": sonuc, "hata": hata},
        timeout=30,
    )
    cevap.raise_for_status()


def main(kuru_calisma: bool = False) -> int:
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
        if kuru_calisma:
            sonuc = json.dumps({
                "kuruCalisma": True,
                "ilanId": str(ilan["id"]),
                "fiyat": ilan.get("fiyat"),
                "fotografSayisi": len(ilan.get("gorseller") or []),
                "hedefler": platformlar,
                "disPlatformCagrisi": False,
            }, ensure_ascii=False)
            sonucu_yaz(kuyruk_id, "kuru", sonuc=sonuc)
            log.info("Kuru çalışma #%s tamamlandı; dış platform çağrısı yapılmadı.", kuyruk_id)
            return 0
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
    parser = argparse.ArgumentParser(description="Site sosyal paylaşım kuyruğunu işler.")
    parser.add_argument("--kuru-calisma", action="store_true", help="İşi doğrular ve sonuç yazar; sosyal platform çağrısı yapmaz.")
    args = parser.parse_args()
    try:
        raise SystemExit(main(kuru_calisma=args.kuru_calisma))
    except Exception as hata:
        log.exception("Site kuyruğu işlenemedi: %s", hata)
        raise SystemExit(1)
