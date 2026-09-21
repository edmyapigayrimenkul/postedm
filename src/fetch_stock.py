"""
src/fetch_stock.py — Pexels API ile Telifsiz Emlak & Mimari Stok Görsel Motoru

Haberler ve editoryal içerikler için yüksek çözünürlüklü, dikey (portrait)
gayrimenkul, arsa, tapu, konut ve mimari fotoğrafları temin eder.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Optional

import requests
from PIL import Image, ImageOps

from . import config

log = logging.getLogger(__name__)

API_URL = "https://api.pexels.com/v1/search"
TIMEOUT = 25

VARSAYILAN_TERIMLER = {
    "TAPU_VE_HUKUK": "legal document contract signing real estate deed",
    "ARSA_VE_IMAR": "land plot field agriculture real estate construction plan",
    "KIRACI_VE_EV_SAHIBI": "modern apartment interior keys house rent",
    "KONUT_FINANSMANI": "real estate investment modern villa currency",
    "KENTSEL_DONUSUM": "modern urban architecture building construction",
}


def stok_fotografi_ara(
    sorgu: str,
    kategori_kodu: Optional[str] = None,
    cikti_yolu: Optional[Path] = None,
) -> Optional[Path]:
    """
    Pexels API'den dikey (portrait) telifsiz fotoğraf arar ve diske kaydeder.
    """
    api_key = config.env_al("PEXELS_API_KEY")
    if not api_key:
        log.warning("PEXELS_API_KEY bulunamadı, stok görsel arama atlanıyor.")
        return None

    # Sorguyu zenginleştir
    arama_metni = sorgu.strip()
    if kategori_kodu and kategori_kodu in VARSAYILAN_TERIMLER:
        arama_metni = f"{arama_metni} {VARSAYILAN_TERIMLER[kategori_kodu]}"
    if not arama_metni:
        arama_metni = "real estate architecture land property"

    headers = {"Authorization": api_key}
    params = {
        "query": arama_metni,
        "orientation": "portrait",
        "per_page": 5,
        "locale": "en-US",
    }

    try:
        resp = requests.get(API_URL, headers=headers, params=params, timeout=TIMEOUT)
        if resp.status_code != 200:
            log.warning("Pexels API yanıt vermedi [%d]: %s", resp.status_code, resp.text[:120])
            return None

        veri = resp.json()
        photos = veri.get("photos", [])
        if not photos:
            # Fallback genel arama
            params["query"] = "modern architecture real estate luxury home"
            resp2 = requests.get(API_URL, headers=headers, params=params, timeout=TIMEOUT)
            if resp2.status_code == 200:
                photos = resp2.json().get("photos", [])

        if not photos:
            log.info("Pexels'te uygun fotoğraf bulunamadı.")
            return None

        # İlk adayı al (large2x veya portrait kalitesi)
        secilen = photos[0]
        src_dict = secilen.get("src", {})
        foto_url = src_dict.get("large2x") or src_dict.get("portrait") or src_dict.get("large")
        if not foto_url:
            return None

        # Fotoğrafı indir
        f_resp = requests.get(foto_url, timeout=TIMEOUT)
        if f_resp.status_code == 200 and len(f_resp.content) > 5000:
            img = Image.open(io.BytesIO(f_resp.content))
            img = ImageOps.exif_transpose(img).convert("RGB")

            if cikti_yolu is None:
                foto_id = secilen.get("id", "stock")
                cikti_yolu = config.yol_al(f"data/output/pexels_{foto_id}.jpg")
            else:
                cikti_yolu = Path(cikti_yolu)

            cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
            img.save(cikti_yolu, "JPEG", quality=92)
            log.info("Pexels stok fotoğrafı indirildi: %s (%dx%d)", cikti_yolu.name, img.width, img.height)
            return cikti_yolu
    except Exception as e:
        log.warning("Pexels fotoğraf indirme hatası: %s", e)

    return None
