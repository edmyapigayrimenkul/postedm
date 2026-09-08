"""
facebook.py — Meta Graph API ile Facebook Sayfası Paylaşım Modülü
EDM Yapı & Gayrimenkul Facebook sayfasına (145361567360773) tekli veya
çoklu (albüm) post yayınlar.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import requests

from . import config

log = logging.getLogger(__name__)

GRAPH_API_URL = "https://graph.facebook.com/v21.0"


def _page_bilgileri() -> tuple[str, str]:
    token = config.env_al("INSTAGRAM_ACCESS_TOKEN")
    page_id = config.env_al("FACEBOOK_PAGE_ID", "145361567360773")
    return token, page_id


def paylas(caption: str, gorsel_urlleri: List[str]) -> Optional[str]:
    """Facebook sayfasında tekli veya çoklu görsel (albüm) paylaşır."""
    token, page_id = _page_bilgileri()
    if not token:
        log.warning("Facebook erişim tokeni bulunamadı.")
        return None

    if not gorsel_urlleri:
        log.warning("Paylaşılacak görsel URL'si yok.")
        return None

    try:
        # Tek görsel ise doğrudan photos endpointine gönder
        if len(gorsel_urlleri) == 1:
            url = f"{GRAPH_API_URL}/{page_id}/photos"
            data = {
                "url": gorsel_urlleri[0],
                "caption": caption,
                "access_token": token,
            }
            res = requests.post(url, data=data, timeout=25)
            if res.status_code == 200:
                post_id = res.json().get("id") or res.json().get("post_id")
                log.info("Facebook gönderisi paylaşıldı: %s", post_id)
                return post_id
            log.error("Facebook paylaşım hatası: %s", res.text)
            return None

        # Çoklu görsel (Albüm): Görselleri taslak yükleyip feed'e bağla
        photo_ids = []
        for g_url in gorsel_urlleri:
            u_res = requests.post(
                f"{GRAPH_API_URL}/{page_id}/photos",
                data={"url": g_url, "published": "false", "access_token": token},
                timeout=25,
            )
            if u_res.status_code == 200:
                pid = u_res.json().get("id")
                if pid:
                    photo_ids.append(pid)
            else:
                log.warning("Facebook görsel taslak yükleme hatası: %s", u_res.text)

        if not photo_ids:
            log.error("Facebook'a hiçbir görsel yüklenemedi.")
            return None

        feed_url = f"{GRAPH_API_URL}/{page_id}/feed"
        feed_data = {
            "message": caption,
            "access_token": token,
        }
        for idx, pid in enumerate(photo_ids):
            feed_data[f"attached_media[{idx}]"] = json.dumps({"media_fbid": pid})

        res = requests.post(feed_url, data=feed_data, timeout=25)
        if res.status_code == 200:
            post_id = res.json().get("id")
            log.info("Facebook çoklu görsel gönderisi paylaşıldı: %s", post_id)
            return post_id
        log.error("Facebook feed paylaşım hatası: %s", res.text)

    except Exception as e:
        log.error("Facebook paylaşım istisnası: %s", e)

    return None
