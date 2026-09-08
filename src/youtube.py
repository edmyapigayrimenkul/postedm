"""
youtube.py — YouTube Data API v3 üzerinden 9:16 Shorts Video Yükleyici
Dikey (1080x1920) emlak ve haber videolarını YouTube Shorts olarak yayınlar.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from . import config

log = logging.getLogger(__name__)

YOUTUBE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_UPLOAD_URL = (
    "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
)


def access_token_al() -> Optional[str]:
    """YOUTUBE_REFRESH_TOKEN ile yeni bir Google OAuth2 Access Token alır."""
    client_id = config.env_al("YOUTUBE_CLIENT_ID")
    client_secret = config.env_al("YOUTUBE_CLIENT_SECRET")
    refresh_token = config.env_al("YOUTUBE_REFRESH_TOKEN")

    if not client_id or not client_secret or not refresh_token:
        log.warning("YouTube API kimlik bilgileri eksik (CLIENT_ID / SECRET / REFRESH_TOKEN).")
        return None

    try:
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        res = requests.post(YOUTUBE_TOKEN_URL, data=data, timeout=12)
        if res.status_code == 200:
            return res.json().get("access_token")
        log.warning("YouTube token yenileme başarısız (%s): %s", res.status_code, res.text[:200])
    except Exception as e:
        log.warning("YouTube token alma hatası: %s", e)
    return None


def shorts_yukle(
    video_yolu: Path | str,
    baslik: str,
    aciklama: str = "",
    etiketler: Optional[List[str]] = None,
    gizlilik: str = "public",
) -> Dict[str, Any]:
    """1080x1920 MP4 videosunu YouTube Shorts olarak yükler."""
    yol = Path(video_yolu)
    if not yol.exists() or yol.stat().st_size == 0:
        return {"durum": False, "hata": f"Video dosyası bulunamadı: {yol}"}

    token = access_token_al()
    if not token:
        return {"durum": False, "hata": "YouTube erişim jetonu alınamadı."}

    temiz_baslik = baslik.strip()
    if "#Shorts" not in temiz_baslik and "#shorts" not in temiz_baslik:
        if len(temiz_baslik) <= 90:
            temiz_baslik = f"{temiz_baslik} #Shorts"

    if not aciklama:
        aciklama = f"{baslik}\n\nEDM Yapı & Gayrimenkul · Yatırım Ortağınız\n0536 343 41 97 · edmyapigayrimenkul.com\n\n#Shorts #Emlak #Gayrimenkul #Silivri"

    sabit_etiketler = ["Shorts", "Emlak", "Gayrimenkul", "Silivri", "Arsa", "Yatırım", "EDM Yapı"]
    tags = list(set((etiketler or []) + sabit_etiketler))

    meta_payload = {
        "snippet": {
            "title": temiz_baslik[:100],
            "description": aciklama,
            "tags": tags,
            "categoryId": "22",  # People & Blogs / Guides
            "defaultLanguage": "tr",
        },
        "status": {
            "privacyStatus": gizlilik,
            "selfDeclaredMadeForKids": False,
        },
    }

    headers_init = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": "video/mp4",
        "X-Upload-Content-Length": str(yol.stat().st_size),
    }

    try:
        r_init = requests.post(
            YOUTUBE_UPLOAD_URL,
            headers=headers_init,
            data=json.dumps(meta_payload),
            timeout=20,
        )
        if r_init.status_code != 200 or "Location" not in r_init.headers:
            return {"durum": False, "hata": f"Upload başlatılamadı: {r_init.text[:150]}"}

        upload_url = r_init.headers["Location"]

        # 2. Binary Video Yüklemesi
        with open(yol, "rb") as f_video:
            headers_upload = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "video/mp4",
                "Content-Length": str(yol.stat().st_size),
            }
            r_up = requests.put(upload_url, headers=headers_upload, data=f_video, timeout=120)

        if r_up.status_code in (200, 201):
            veri = r_up.json()
            vid_id = veri.get("id")
            video_url = f"https://youtube.com/shorts/{vid_id}"
            log.info("YouTube Shorts yayını başarılı! URL: %s", video_url)
            return {"durum": True, "video_id": vid_id, "url": video_url}
        else:
            return {"durum": False, "hata": f"Video yüklenemedi [{r_up.status_code}]: {r_up.text[:200]}"}

    except Exception as e:
        log.error("YouTube Shorts yükleme istisnası: %s", e)
        return {"durum": False, "hata": str(e)}
