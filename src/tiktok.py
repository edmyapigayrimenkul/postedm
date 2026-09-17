"""
tiktok.py — TikTok Content Posting API v2 üzerinden 9:16 Dikey Video Yükleyici
Instabot / Daily Brief mimarisinden uyarlanmıştır.

Dikey emlak ve haber videolarını TikTok hesabında paylaşır.

ÖNEMLİ SAHA TECRÜBELERİ (instabot bulguları):
1. App Audit & Unaudited Client (HTTP 403): TikTok App Audit onayından geçmemiş uygulamalar
   yalnızca gizli hesaplara doğrudan video paylaşabilir. Herkese açık hesaplarda doğrudan
   paylaşım 'unaudited_client_can_only_post_to_private_accounts' hatası verir.
   Bu durumda sistem otomatik olarak Inbox Draft (gelen kutusu taslağı) moduna geçerek
   videoyu taslak olarak yükler ve süreci kurtarır.
2. 150 Karakter Başlık Sınırı: TikTok başlık limiti 150 karakterdir. Manşet asla kesilmez;
   taşma durumunda sondaki hashtag'ler kırpılır.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from . import config, db, filtre

log = logging.getLogger(__name__)

TIKTOK_OAUTH_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
TIKTOK_INBOX_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"


def token_yenile() -> Optional[str]:
    """TIKTOK_REFRESH_TOKEN ile yeni bir 24 saatlik Access Token alır."""
    client_key = config.env_al("TIKTOK_CLIENT_KEY") or db.ayar_oku("tiktok_client_key")
    client_secret = config.env_al("TIKTOK_CLIENT_SECRET") or db.ayar_oku("tiktok_client_secret")
    refresh_token = config.env_al("TIKTOK_REFRESH_TOKEN") or db.ayar_oku("tiktok_refresh_token")

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
            yeni_token = veri["access_token"]
            yeni_refresh = veri.get("refresh_token")
            os.environ["TIKTOK_ACCESS_TOKEN"] = yeni_token

            # DB ve .env güncelle
            db.ayar_yaz("tiktok_access_token", yeni_token)
            if yeni_refresh:
                os.environ["TIKTOK_REFRESH_TOKEN"] = yeni_refresh
                db.ayar_yaz("tiktok_refresh_token", yeni_refresh)

            try:
                from . import refresh_token as rt
                rt.env_guncelle("TIKTOK_ACCESS_TOKEN", yeni_token)
                if yeni_refresh:
                    rt.env_guncelle("TIKTOK_REFRESH_TOKEN", yeni_refresh)
            except Exception:
                pass

            log.info("TikTok erişim jetonu başarıyla yenilendi.")
            return yeni_token
        log.warning("TikTok token yenileme başarısız: %s", r.text[:200])
    except Exception as e:
        log.warning("TikTok token hatası: %s", e)
    return None


def _etiket_anahtari(etiket: str) -> str:
    """Türkçe İ ve I harflerini gözeterek etiket anahtarı üretir."""
    return etiket.strip().replace("I", "ı").replace("İ", "i").lower()


def baslik_kur(baslik: str, etiketler: Optional[List[str]] = None) -> str:
    """
    TikTok için en fazla 150 karakterlik açıklama kurar.
    Manşet ASLA kesilmez; sığmayan etiketler sondan kırpılır.
    """
    temiz_baslik = filtre.markdown_temizle(baslik).strip()
    sabitler = ["#EDMYapı", "#Emlak", "#Silivri", "#keşfet"]
    tum_etiketler = []
    gorulen = set()

    for et in (etiketler or []) + sabitler:
        et_temiz = et.strip()
        anahtar = _etiket_anahtari(et_temiz)
        if et_temiz and anahtar not in gorulen:
            tum_etiketler.append(et_temiz)
            gorulen.add(anahtar)

    secilen_etiketler: List[str] = []
    for et in tum_etiketler:
        aday = f"{temiz_baslik} {' '.join(secilen_etiketler + [et])}".strip()
        if len(aday) <= 150:
            secilen_etiketler.append(et)
        else:
            break

    if secilen_etiketler:
        return f"{temiz_baslik} {' '.join(secilen_etiketler)}".strip()
    return temiz_baslik[:150]


def video_yukle(
    video_yolu: Path | str,
    baslik: str,
    etiketler: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """1080x1920 MP4 videosunu TikTok'a yükler (Doğrudan veya Taslak olarak)."""
    yol = Path(video_yolu)
    if not yol.exists() or yol.stat().st_size == 0:
        return {"durum": False, "hata": f"Video dosyası bulunamadı veya boş: {yol}"}

    token = config.env_al("TIKTOK_ACCESS_TOKEN") or db.ayar_oku("tiktok_access_token") or token_yenile()
    if not token:
        return {"durum": False, "hata": "TikTok erişim jetonu alınamadı."}

    dosya_boyutu = yol.stat().st_size
    tam_baslik = baslik_kur(baslik, etiketler)

    # 1. Aşama: Doğrudan yayını dene
    mod = "direct"
    init_url = TIKTOK_INIT_URL
    init_payload: Dict[str, Any] = {
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
            init_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            data=json.dumps(init_payload),
            timeout=20,
        )

        # 401 durumunda token süresi dolmuş olabilir (24 saatlik ömür) — otomatik yenile ve tekrar dene
        if init_res.status_code == 401 or (init_res.status_code != 200 and "token" in init_res.text.lower()):
            log.warning("TikTok erişim jetonu geçersiz veya süresi dolmuş (HTTP %d). Otomatik yenileniyor...", init_res.status_code)
            yeni_tok = token_yenile()
            if yeni_tok:
                token = yeni_tok
                init_res = requests.post(
                    init_url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json; charset=UTF-8",
                    },
                    data=json.dumps(init_payload),
                    timeout=20,
                )

        # Unaudited client durumunda (HTTP 403) Inbox Draft fallback devreye girer
        if init_res.status_code == 403 or "unaudited_client" in init_res.text:
            log.warning("TikTok App Audit kısıtı (unaudited_client): Gelen kutusu taslağı (Inbox Draft) moduna geçiliyor.")
            mod = "inbox_draft"
            init_url = TIKTOK_INBOX_INIT_URL
            init_payload = {
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": dosya_boyutu,
                    "chunk_size": dosya_boyutu,
                    "total_chunk_count": 1,
                }
            }
            init_res = requests.post(
                init_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json; charset=UTF-8",
                },
                data=json.dumps(init_payload),
                timeout=20,
            )

        init_data = init_res.json()
        if init_res.status_code != 200 or init_data.get("error", {}).get("code") != "ok":
            return {"durum": False, "hata": f"TikTok init hatası [{init_res.status_code}]: {init_res.text[:200]}"}

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
            log.info("TikTok video yüklemesi başarılı (%s)! Publish ID: %s", mod, publish_id)
            return {
                "durum": True,
                "publish_id": publish_id,
                "mod": mod,
                "taslak_mi": (mod == "inbox_draft"),
            }
        else:
            return {"durum": False, "hata": f"TikTok upload hatası [{up_res.status_code}]: {up_res.text[:200]}"}
    except Exception as e:
        log.error("TikTok video yükleme istisnası: %s", e)
        return {"durum": False, "hata": str(e)}
