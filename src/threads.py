"""
threads.py — Meta Threads API Yayın Modülü
Metin, tekil görsel ve çoklu slayt (Carousel) paylaşımları yapar.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from . import config

log = logging.getLogger(__name__)

THREADS_TABAN = "https://graph.threads.net/v1.0"


def _hesap_bilgileri() -> Tuple[str, str]:
    token = config.env_al("THREADS_ACCESS_TOKEN")
    kullanici_id = config.env_al("THREADS_USER_ID")
    return kullanici_id, token


def _konteyner_bekle(creation_id: str, access_token: str, max_bekleme: int = 60) -> bool:
    url = f"{THREADS_TABAN}/{creation_id}"
    params = {"fields": "status", "access_token": access_token}

    baslangic = time.time()
    while time.time() - baslangic < max_bekleme:
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                durum = resp.json().get("status")
                if durum == "FINISHED":
                    return True
                elif durum == "ERROR":
                    log.error("Threads konteyner hatası: %s", resp.text)
                    return False
        except Exception as e:
            log.warning("Threads durum sorgulama hatası: %s", e)
        time.sleep(3)
    return False


def _yayina_al(creation_id: str, kullanici_id: str, access_token: str) -> Optional[str]:
    url = f"{THREADS_TABAN}/{kullanici_id}/threads_publish"
    payload = {"creation_id": creation_id, "access_token": access_token}

    for deneme in range(3):
        try:
            resp = requests.post(url, data=payload, timeout=25)
            if resp.status_code == 200:
                post_id = resp.json().get("id")
                log.info("Threads yayını başarılı! ID: %s", post_id)
                return post_id
            log.warning("Threads yayınlama denemesi %d başarısız: %s", deneme + 1, resp.text)
            time.sleep(3)
        except Exception as e:
            log.error("Threads yayınlama hatası: %s", e)
            time.sleep(3)
    return None


def paylas(metin: str, gorsel_urlleri: Optional[List[str]] = None) -> Optional[str]:
    """Threads'te paylaşım yapar (Salt metin, tek görsel veya çoklu slayt)."""
    kullanici_id, token = _hesap_bilgileri()
    if not kullanici_id or not token:
        log.warning("Threads kimlik bilgileri eksik (.env kontrol edin).")
        return None

    url = f"{THREADS_TABAN}/{kullanici_id}/threads"

    # 1. Salt Metin Paylaşımı
    if not gorsel_urlleri:
        payload = {"media_type": "TEXT", "text": metin, "access_token": token}
        resp = requests.post(url, data=payload, timeout=25)
        if resp.status_code == 200:
            creation_id = resp.json().get("id")
            return _yayina_al(creation_id, kullanici_id, token)
        return None

    # 2. Tek Görsel
    if len(gorsel_urlleri) == 1:
        payload = {
            "media_type": "IMAGE",
            "image_url": gorsel_urlleri[0],
            "text": metin,
            "access_token": token,
        }
        resp = requests.post(url, data=payload, timeout=25)
        if resp.status_code == 200:
            creation_id = resp.json().get("id")
            if _konteyner_bekle(creation_id, token):
                return _yayina_al(creation_id, kullanici_id, token)
        return None

    # 3. Carousel (Çoklu Slayt)
    cocuk_idler = []
    for g_url in gorsel_urlleri[:10]:
        payload = {
            "media_type": "IMAGE",
            "image_url": g_url,
            "is_carousel_item": "true",
            "access_token": token,
        }
        resp = requests.post(url, data=payload, timeout=25)
        if resp.status_code == 200:
            cocuk_idler.append(resp.json().get("id"))
        time.sleep(1)

    if len(cocuk_idler) < 2:
        return None

    payload = {
        "media_type": "CAROUSEL",
        "children": ",".join(cocuk_idler),
        "text": metin,
        "access_token": token,
    }
    resp = requests.post(url, data=payload, timeout=30)
    if resp.status_code == 200:
        creation_id = resp.json().get("id")
        if _konteyner_bekle(creation_id, token):
            return _yayina_al(creation_id, kullanici_id, token)

    return None
