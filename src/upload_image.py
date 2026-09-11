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

# Yüklenen dosyaların URL -> yerel yol eşleşmesi.
# Aynı süreçte yüklenen dosyaların video/reels için tekrar internetten indirilmesini engeller.
_YUKLENEN_YEREL: dict[str, str] = {}


def yerel_karsiligi(url: str) -> Optional[Path]:
    """Bu süreçte bu URL'i üretmek için yüklenen yerel dosya (varsa) döner."""
    if not url:
        return None
    yol = _YUKLENEN_YEREL.get(str(url).strip())
    if not yol:
        return None
    p = Path(yol)
    return p if (p.exists() and p.is_file()) else None


def _catbox_yukle(dosya_yolu: Path, deneme_adedi: int = 3) -> Optional[str]:
    """Yedek barındırıcı catbox.moe'ya yükler (3 denemeli ve tam User-Agent ile)."""
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    for deneme in range(1, deneme_adedi + 1):
        try:
            with open(dosya_yolu, "rb") as f:
                resp = requests.post(
                    CATBOX_URL,
                    data={"reqtype": "fileupload"},
                    files={"fileToUpload": (dosya_yolu.name, f, "image/jpeg")},
                    headers=headers,
                    timeout=30,
                )
                if resp.status_code == 200 and resp.text.startswith("https://"):
                    url = resp.text.strip()
                    _YUKLENEN_YEREL[url] = str(dosya_yolu.resolve())
                    log.info("Catbox yüklemesi başarılı: %s", url)
                    return url
                log.warning("Catbox yanıt hatası [%d, deneme %d/%d]: %s", resp.status_code, deneme, deneme_adedi, resp.text[:120])
        except Exception as e:
            log.warning("Catbox yükleme istisnası (deneme %d/%d): %s", deneme, deneme_adedi, e)
        if deneme < deneme_adedi:
            time.sleep(2 * deneme)
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
                        _YUKLENEN_YEREL[url] = str(p.resolve())
                        log.info("ImgBB yüklemesi başarılı: %s", url)
                        return url
                time.sleep(2 * (deneme + 1))
        except Exception as e:
            log.warning("ImgBB yükleme hatası: %s", e)

    # Yedek barındırıcı: Catbox
    log.info("ImgBB yerine Catbox devreye giriyor...")
    url = _catbox_yukle(p)
    if url:
        _YUKLENEN_YEREL[url] = str(p.resolve())
    return url


def coklu_gorsel_yukle(dosya_yollari: List[Path | str]) -> List[str]:
    """Birden fazla slaytı sırayla yükler."""
    urller = []
    for y in dosya_yollari:
        url = gorsel_yukle(y)
        if url:
            urller.append(url)
        time.sleep(0.5)
    return urller


def video_yukle(dosya_yolu: Path | str, zaman_asimi: int = 90) -> Optional[str]:
    """
    MP4 video dosyasını barındırıcıya yükleyip herkese açık HTTPS URL döner.
    Instagram Reels / Video Graph API'si için kullanılır.
    """
    p = Path(dosya_yolu)
    if not p.exists() or p.stat().st_size == 0:
        log.error("Video dosyası bulunamadı veya boş: %s", p)
        return None

    # 1. uguu.se (Hızlı, Instagram / Meta sunucuları doğrudan indirebiliyor)
    try:
        with open(p, "rb") as f:
            cevap = requests.post(
                "https://uguu.se/upload",
                files={"files[]": (p.name, f, "video/mp4")},
                timeout=zaman_asimi,
            )
        if cevap.status_code == 200:
            veri = cevap.json()
            url = (veri.get("files") or [{}])[0].get("url")
            if url:
                _YUKLENEN_YEREL[url] = str(p.resolve())
                log.info("Video uguu'ya başarıyla yüklendi: %s", url)
                return url
    except Exception as e:
        log.warning("Video uguu'ya yüklenemedi: %s", e)

    # 2. litterbox.catbox.moe (72 saatlik geçici dosya barındırma)
    try:
        with open(p, "rb") as f:
            cevap = requests.post(
                "https://litterbox.catbox.moe/resources/internals/api.php",
                data={"reqtype": "fileupload", "time": "72h"},
                files={"fileToUpload": (p.name, f, "video/mp4")},
                timeout=zaman_asimi,
            )
        if cevap.status_code == 200 and cevap.text.startswith("http"):
            url = cevap.text.strip()
            _YUKLENEN_YEREL[url] = str(p.resolve())
            log.info("Video litterbox'a başarıyla yüklendi: %s", url)
            return url
    except Exception as e:
        log.warning("Video litterbox'a yüklenemedi: %s", e)

    # 3. catbox.moe
    try:
        with open(p, "rb") as f:
            cevap = requests.post(
                CATBOX_URL,
                data={"reqtype": "fileupload"},
                files={"fileToUpload": (p.name, f, "video/mp4")},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=zaman_asimi,
            )
        if cevap.status_code == 200 and cevap.text.startswith("http"):
            url = cevap.text.strip()
            _YUKLENEN_YEREL[url] = str(p.resolve())
            log.info("Video catbox'a başarıyla yüklendi: %s", url)
            return url
    except Exception as e:
        log.warning("Video catbox'a yüklenemedi: %s", e)

    log.error("Video hiçbir barındırıcıya yüklenemedi (%s)", p.name)
    return None

