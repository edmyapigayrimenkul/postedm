"""
instagram.py — Instagram Graph API Yayın Modülü
Tekil görsel, çoklu slayt (Carousel) ve Reels (video) yayınlar.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from . import config

log = logging.getLogger(__name__)

GRAPH_TABAN = "https://graph.facebook.com/v21.0"


def _hesap_bilgileri() -> Tuple[str, str]:
    token = config.env_al("INSTAGRAM_ACCESS_TOKEN")
    hesap_id = config.env_al("INSTAGRAM_ACCOUNT_ID")
    return hesap_id, token


def _konteyner_durumu_bekle(creation_id: str, access_token: str, max_bekleme: int = 60) -> bool:
    """Yüklenen medyanın işlenmesini bekler (FINISHED durumuna gelene kadar)."""
    url = f"{GRAPH_TABAN}/{creation_id}"
    params = {"fields": "status_code", "access_token": access_token}

    baslangic = time.time()
    while time.time() - baslangic < max_bekleme:
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                durum = resp.json().get("status_code")
                if durum == "FINISHED":
                    return True
                elif durum in ("ERROR", "EXPIRED"):
                    log.error("Konteyner işleme başarısız: %s", resp.text)
                    return False
        except Exception as e:
            log.warning("Durum sorgulama hatası: %s", e)
        time.sleep(3)
    return False


def _yayina_al(creation_id: str, hesap_id: str, access_token: str) -> Optional[str]:
    """Hazır konteyneri yayına alır (media_publish)."""
    url = f"{GRAPH_TABAN}/{hesap_id}/media_publish"
    payload = {"creation_id": creation_id, "access_token": access_token}

    for deneme in range(3):
        try:
            resp = requests.post(url, data=payload, timeout=25)
            if resp.status_code == 200:
                post_id = resp.json().get("id")
                log.info("Instagram yayını başarılı! Post ID: %s", post_id)
                return post_id
            log.warning("Yayınlama denemesi %d başarısız: %s", deneme + 1, resp.text)
            time.sleep(3)
        except Exception as e:
            log.error("Yayınlama isteği hatası: %s", e)
            time.sleep(3)
    return None


def tekil_gorsel_yayinla(gorsel_url: str, caption: str) -> Optional[str]:
    """Tek bir görseli Instagram'da paylaşır."""
    hesap_id, token = _hesap_bilgileri()
    if not hesap_id or not token:
        log.warning("Instagram hesap bilgileri eksik (.env kontrol edin).")
        return None

    # 1. Konteyner oluştur
    url = f"{GRAPH_TABAN}/{hesap_id}/media"
    payload = {
        "image_url": gorsel_url,
        "caption": caption,
        "access_token": token,
    }

    try:
        resp = requests.post(url, data=payload, timeout=30)
        if resp.status_code != 200:
            log.error("Instagram konteyner hatası: %s", resp.text)
            return None
        creation_id = resp.json().get("id")
    except Exception as e:
        log.error("Instagram konteyner isteği hatası: %s", e)
        return None

    # 2. İşlenmesini bekle
    if not _konteyner_durumu_bekle(creation_id, token):
        return None

    # 3. Yayınla
    return _yayina_al(creation_id, hesap_id, token)


def carousel_yayinla(gorsel_urlleri: List[str], caption: str) -> Optional[str]:
    """Birden fazla slaytı kaydırmalı (Carousel) post olarak paylaşır."""
    hesap_id, token = _hesap_bilgileri()
    if not hesap_id or not token:
        log.warning("Instagram hesap bilgileri eksik.")
        return None

    if len(gorsel_urlleri) < 2:
        return tekil_gorsel_yayinla(gorsel_urlleri[0], caption)

    # 1. Her görsel için alt öğe oluştur (is_carousel_item=true)
    cocuk_idler = []
    for g_url in gorsel_urlleri[:10]: # Instagram Carousel azami 10
        payload = {
            "image_url": g_url,
            "is_carousel_item": "true",
            "access_token": token,
        }
        resp = requests.post(f"{GRAPH_TABAN}/{hesap_id}/media", data=payload, timeout=25)
        if resp.status_code == 200:
            cocuk_idler.append(resp.json().get("id"))
        else:
            log.error("Carousel alt öğe hatası (%s): %s", g_url, resp.text)
        time.sleep(1)

    if len(cocuk_idler) < 2:
        log.error("Carousel için yeterli alt öğe üretilemedi.")
        return None

    # 2. Ana Carousel konteyneri oluştur
    payload = {
        "media_type": "CAROUSEL",
        "children": ",".join(cocuk_idler),
        "caption": caption,
        "access_token": token,
    }
    resp = requests.post(f"{GRAPH_TABAN}/{hesap_id}/media", data=payload, timeout=30)
    if resp.status_code != 200:
        log.error("Carousel ana konteyner hatası: %s", resp.text)
        return None

    creation_id = resp.json().get("id")

    # 3. Bekle ve Yayınla
    if not _konteyner_durumu_bekle(creation_id, token):
        return None

    return _yayina_al(creation_id, hesap_id, token)
