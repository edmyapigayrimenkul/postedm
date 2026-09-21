"""
facebook.py — Meta Graph API ile Facebook Sayfası Paylaşım Modülü
Instabot / Daily Brief mimarisinden uyarlanmıştır.

EDM Yapı & Gayrimenkul Facebook sayfasına tekli, çoklu (albüm) post
veya Facebook Story yayınlar.

ÖNEMLİ SAHA TECRÜBELERİ (instabot bulguları):
1. Facebook ikincil kanaldır; patlarsa Instagram postu yayında kalmalıdır.
2. Geçici 500/502/504 ve 429 hatalarında backoff ile 3 deneme yapılmalıdır.
3. Açıklama metinlerindeki markdown (**) işaretleri Facebook feed'inde temizlenmelidir.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from . import config, filtre

log = logging.getLogger(__name__)

GRAPH_API_URL = "https://graph.facebook.com/v21.0"
GECICI_HATALAR = {429, 500, 502, 503, 504}


def _page_bilgileri() -> tuple[str, str]:
    token = config.env_al("INSTAGRAM_ACCESS_TOKEN")
    page_id = (config.env_al("FACEBOOK_PAGE_ID") or "145361567360773").strip()
    return token, page_id


def _istek(yontem: str, yol: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
    """Facebook Graph API isteğini geçici hatalara karşı tekrarlı olarak yürütür."""
    token, _ = _page_bilgileri()
    if not token:
        log.warning("Facebook erişim tokeni bulunamadı.")
        return None

    url = f"{GRAPH_API_URL}{yol}"
    params = kwargs.get("params", {})
    data = kwargs.get("data", {})
    if yontem.upper() == "GET":
        params["access_token"] = token
        kwargs["params"] = params
    else:
        data["access_token"] = token
        kwargs["data"] = data

    timeout = kwargs.pop("timeout", 30)

    for deneme in range(1, 4):
        try:
            if yontem.upper() == "GET":
                res = requests.get(url, params=params, timeout=timeout)
            elif yontem.upper() == "DELETE":
                res = requests.delete(url, params=params, timeout=timeout)
            else:
                res = requests.post(url, data=data, timeout=timeout)

            if res.status_code == 200:
                return res.json()

            if res.status_code in GECICI_HATALAR:
                log.warning("Facebook geçici HTTP %d hatası (%s), %d sn bekleniyor (deneme %d/3)", res.status_code, yol, deneme * 2, deneme)
                time.sleep(deneme * 2)
                continue

            log.error("Facebook API hatası [%d] (%s): %s", res.status_code, yol, res.text[:200])
            break
        except requests.RequestException as e:
            log.warning("Facebook ağ hatası (%s, deneme %d/3): %s", yol, deneme, e)
            time.sleep(deneme * 2)

    return None


def paylas(caption: str, gorsel_urlleri: List[str]) -> Optional[str]:
    """Facebook sayfasında tekli veya çoklu görsel (albüm) paylaşır."""
    token, page_id = _page_bilgileri()
    if not token:
        log.warning("Facebook erişim tokeni bulunamadı.")
        return None

    if not gorsel_urlleri:
        log.warning("Paylaşılacak görsel URL'si yok.")
        return None

    temiz_caption = filtre.markdown_temizle(caption)

    try:
        # Tek görsel ise doğrudan photos endpointine gönder
        if len(gorsel_urlleri) == 1:
            res = _istek(
                "POST",
                f"/{page_id}/photos",
                data={"url": gorsel_urlleri[0], "caption": temiz_caption},
            )
            if res:
                post_id = res.get("id") or res.get("post_id")
                log.info("Facebook tekil gönderisi paylaşıldı: %s", post_id)
                return post_id
            return None

        # Çoklu görsel (Albüm): Görselleri taslak yükleyip feed'e bağla
        photo_ids = []
        for g_url in gorsel_urlleri:
            u_res = _istek(
                "POST",
                f"/{page_id}/photos",
                data={"url": g_url, "published": "false"},
            )
            if u_res and u_res.get("id"):
                photo_ids.append(u_res["id"])
            else:
                log.warning("Facebook görsel taslak yükleme başarısız: %s", g_url)

        if not photo_ids:
            log.error("Facebook'a hiçbir görsel taslağı yüklenemedi.")
            return None

        feed_data: Dict[str, Any] = {"message": temiz_caption}
        for idx, pid in enumerate(photo_ids):
            feed_data[f"attached_media[{idx}]"] = json.dumps({"media_fbid": pid})

        res = _istek("POST", f"/{page_id}/feed", data=feed_data)
        if res and res.get("id"):
            post_id = res["id"]
            log.info("Facebook albüm gönderisi paylaşıldı: %s", post_id)
            return post_id

        log.error("Facebook feed albüm paylaşımı başarısız.")
    except Exception as e:
        log.error("Facebook paylaşım istisnası: %s", e)

    return None


def story_yayinla(gorsel_url: str) -> Optional[str]:
    """
    Facebook sayfa story'si paylaşır.
    İki aşamalıdır: Önce published=false ile yüklenir, ardından /photo_stories'e bağlanır.
    """
    token, page_id = _page_bilgileri()
    if not token:
        return None

    try:
        # 1. Aşama: Görseli yükle
        d = _istek("POST", f"/{page_id}/photos", data={"url": gorsel_url, "published": "false"})
        if not d or not d.get("id"):
            log.warning("Facebook story görseli yüklenemedi")
            return None
        foto_id = d["id"]

        # 2. Aşama: Story olarak yayınla
        d_story = _istek("POST", f"/{page_id}/photo_stories", data={"photo_id": foto_id})
        if d_story and d_story.get("post_id"):
            log.info("Facebook Story paylaşıldı: %s", d_story["post_id"])
            return d_story["post_id"]
    except Exception as e:
        log.warning("Facebook Story yayınlama hatası: %s", e)

    return None


def video_yayinla(video_yolu: Path | str, description: str = "") -> Optional[str]:
    """
    Facebook sayfasında MP4 video (Reels) yayınlar.
    Meta Graph API /{page_id}/videos endpointine multipart/form-data ile yükleme yapar.
    """
    token, page_id = _page_bilgileri()
    if not token:
        log.warning("Facebook erişim tokeni bulunamadı.")
        return None

    from . import ses
    yol = ses.sesli_video_hazirla(video_yolu, ses_seviyesi=0.20)
    if not yol.exists():
        log.warning("Facebook'a yüklenecek video dosyası bulunamadı: %s", yol)
        return None

    temiz_desc = filtre.markdown_temizle(description)
    url = f"{GRAPH_API_URL}/{page_id}/videos"

    for deneme in range(1, 4):
        try:
            with open(yol, "rb") as f:
                res = requests.post(
                    url,
                    data={"access_token": token, "description": temiz_desc},
                    files={"source": f},
                    timeout=120,
                )
            if res.status_code == 200:
                vid_id = res.json().get("id")
                log.info("Facebook video/reels yayını başarılı: %s", vid_id)
                return vid_id

            if res.status_code in GECICI_HATALAR:
                time.sleep(deneme * 5)
                continue

            log.error("Facebook video yükleme hatası [%d]: %s", res.status_code, res.text[:200])
            break
        except requests.RequestException as e:
            log.warning("Facebook video ağ hatası (deneme %d): %s", deneme, e)
            time.sleep(deneme * 5)

    return None


def post_baglantisi(post_id: str) -> str:
    """Facebook post bağlantısı — Telegram sonucunda göstermek için."""
    if not post_id:
        return ""
    return f"https://www.facebook.com/{post_id}"


def reels_baglantisi(video_id: str) -> str:
    """Facebook Reel doğrudan bağlantısı — Telegram sonucunda göstermek için."""
    if not video_id:
        return ""
    return f"https://www.facebook.com/reel/{video_id}"
