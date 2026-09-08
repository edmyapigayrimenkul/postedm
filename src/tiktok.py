"""
tiktok.py — TikTok Content Posting API v2 üzerinden 9:16 Dikey Video Yükleyici
Dikey emlak ve haber videolarını TikTok hesabında paylaşır.
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

TIKTOK_OAUTH_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"


def token_yenile() -> Optional[str]:
    """TIKTOK_REFRESH_TOKEN ile yeni bir Access Token alır."""
    client_key = config.env_al("TIKTOK_CLIENT_KEY")
    client_secret = config.env_al("TIKTOK_CLIENT_SECRET")
    refresh_token = config.env_al("TIKTOK_REFRESH_TOKEN")

    if not client_key or not client_secret or not refresh_token:
        log.warning("TikTok API kimlik bilgileri eksik (CLIENT_KEY / SECRET / REFRESH_TOKEN).")
        return None

    try:
        r = requests.post(
            TIKTOK_OAUTH_TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": client_key,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=15,
        )
        veri = r.json()
        if r.status_code == 200 and "access_token" in veri:
            return veri["access_token"]
        log.warning("TikTok token yenileme başarısız: %s", r.text[:200])
    except Exception as e:
        log.warning("TikTok token hatası: %s", e)
    return None


def video_yukle(
    video_yolu: Path | str,
    baslik: str,
    etiketler: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """1080x1920 MP4 videosunu TikTok'a yükler."""
    yol = Path(video_yolu)
    if not yol.exists() or yol.stat().st_size == 0:
        return {"durum": False, "hata": f"Video dosyası bulunamadı: {yol}"}

    token = config.env_al("TIKTOK_ACCESS_TOKEN") or token_yenile()
    if not token:
        return {"durum": False, "hata": "TikTok erişim jetonu alınamadı."}

    dosya_boyutu = yol.stat().st_size

    # TikTok başlık ve etiketleri birleştir (maksimum 150 karakter)
    sabitler = ["#EDMYapı", "#Emlak", "#Silivri", "#keşfet"]
    tum_etiketler = list(set((etiketler or []) + sabitler))
    etiket_str = " ".join(tum_etiketler)

    kalan_alan = 150 - len(etiket_str) - 2
    kirpilmis_baslik = baslik[:max(10, kalan_alan)].strip()
    tam_baslik = f"{kirpilmis_baslik} {etiket_str}".strip()[:150]

    init_payload = {
        "post_info": {
            "title": tam_baslik,
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "disable_duet": False,
            "disable_stitch": False,
            "disable_comment": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": dosya_boyutu,
            "chunk_size": dosya_boyutu,
            "total_chunk_count": 1,
        },
    }

    try:
        init_res = requests.post(
            TIKTOK_INIT_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            data=json.dumps(init_payload),
            timeout=20,
        )
        init_data = init_res.json()
        if init_res.status_code != 200 or init_data.get("error", {}).get("code") != "ok":
            return {"durum": False, "hata": f"TikTok init hatası: {init_res.text[:200]}"}

        upload_url = init_data["data"]["upload_url"]
        publish_id = init_data["data"]["publish_id"]

        with open(yol, "rb") as vf:
            up_res = requests.put(
                upload_url,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Range": f"bytes 0-{dosya_boyutu - 1}/{dosya_boyutu}",
                    "Content-Length": str(dosya_boyutu),
                },
                data=vf,
                timeout=120,
            )

        if up_res.status_code in (200, 201):
            log.info("TikTok video yüklemesi başarılı! Publish ID: %s", publish_id)
            return {"durum": True, "publish_id": publish_id}
        else:
            return {"durum": False, "hata": f"TikTok upload hatası [{up_res.status_code}]: {up_res.text[:200]}"}

    except Exception as e:
        log.error("TikTok yükleme hatası: %s", e)
        return {"durum": False, "hata": str(e)}
