"""
upload_image.py — Görsel Yükleyici
Üretilen kartları imgbb (ve yedek olarak catbox.moe)'a yükleyip
Instagram ve Threads API için gerekli public URL'leri alır.
"""

from __future__ import annotations

import base64
import logging
import os
import time
from pathlib import Path
from typing import List, Optional

import requests
from dotenv import load_dotenv

from . import config

log = logging.getLogger(__name__)

IMGBB_URL = "https://api.imgbb.com/1/upload"
CATBOX_URL = "https://catbox.moe/user/api.php"


def _catbox_yukle(dosya_yolu: Path) -> Optional[str]:
    """Yedek barındırıcı catbox.moe'ya yükler."""
    try:
        with open(dosya_yolu, "rb") as f:
            resp = requests.post(
                CATBOX_URL,
                data={"reqtype": "fileupload"},
                files={"fileToUpload": (dosya_yolu.name, f, "image/jpeg")},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30,
            )
            if resp.status_code == 200 and resp.text.startswith("https://"):
                url = resp.text.strip()
                log.info("Catbox yüklemesi başarılı: %s", url)
                return url
    except Exception as e:
        log.warning("Catbox yükleme hatası: %s", e)
    return None


def gorsel_yukle(dosya_yolu: Path | str, son_kullanma_saniye: int = 172800) -> Optional[str]:
    """Görseli yükler ve public URL döner (imgbb -> catbox fallback)."""
    p = Path(dosya_yolu)
    if not p.exists():
        log.error("Yüklenecek dosya bulunamadı: %s", dosya_yolu)
        return None

    api_key = config.env_al("IMGBB_API_KEY")
    if api_key:
        try:
            with open(p, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")

            payload = {
                "key": api_key.split(",")[0].strip(),
                "image": b64,
                "expiration": son_kullanma_saniye,
            }

            for deneme in range(3):
                resp = requests.post(IMGBB_URL, data=payload, timeout=30)
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    url = data.get("image", {}).get("url") or data.get("url")
                    if url:
                        log.info("ImgBB yüklemesi başarılı: %s", url)
                        return url
                time.sleep(2 * (deneme + 1))
        except Exception as e:
            log.warning("ImgBB yükleme hatası: %s", e)

    # Yedek barındırıcı: Catbox
    log.info("ImgBB yerine Catbox devreye giriyor...")
    return _catbox_yukle(p)


def coklu_gorsel_yukle(dosya_yollari: List[Path | str]) -> List[str]:
    """Birden fazla slaytı sırayla yükler."""
    urller = []
    for y in dosya_yollari:
        url = gorsel_yukle(y)
        if url:
            urller.append(url)
        time.sleep(0.5)
    return urller
