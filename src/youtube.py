"""
youtube.py — YouTube Data API v3 üzerinden 9:16 Shorts Video Yükleyici
Instabot / Daily Brief mimarisinden uyarlanmıştır.

Dikey (1080x1920) emlak ve haber videolarını YouTube Shorts olarak yayınlar.

ÖNEMLİ SAHA TECRÜBELERİ (instabot bulguları):
1. Günlük Kota Tavanı: YouTube Data API ücretsiz kotası 10.000 birim/gündür. 1 video yüklemesi
   1600 birim harcar. Günde azami 5 video (8000 birim) tavanı konularak kota tükenmesi önlenir.
2. invalid_grant & Testing Modu: Google Cloud Console OAuth ekranı "Testing" durumundaysa
   refresh token tam 7 günde bir ölür. Kalıcı çözüm konsolda "Publish App" yapmaktır.
3. Sessiz Video: Tamamen sessiz videolar algoritmaların ikincil transcode kuyruğuna düşüp
   gecikmelere yol açabilir; hafif bir ambiyans fon miksi eklenir.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from . import config, db

log = logging.getLogger(__name__)

YOUTUBE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_UPLOAD_URL = (
    "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
)
YOUTUBE_GUNLUK_AZAMI_VIDEO = 5


def gunluk_yukleme_sayisi_al() -> int:
    """Bugün YouTube'a başarıyla yüklenmiş Shorts videosu sayısını döner."""
    bugun = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    anahtar = f"youtube_gunluk_sayac_{bugun}"
    deger = db.ayar_oku(anahtar, 0)
    try:
        return int(deger)
    except (ValueError, TypeError):
        return 0


def gunluk_yukleme_sayisi_artir() -> None:
    """Bugünkü YouTube yükleme sayacını 1 artırır."""
    bugun = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    anahtar = f"youtube_gunluk_sayac_{bugun}"
    mevcut = gunluk_yukleme_sayisi_al()
    db.ayar_yaz(anahtar, str(mevcut + 1))


def youtube_icin_sesli_video_hazirla(video_yolu: Path | str) -> Path:
    """
    YouTube Shorts için: Videoya arka planda telifsiz, rahatsız etmeyen
    hafif bir emlak fon müziği miksler.
    """
    from . import ses
    return ses.sesli_video_hazirla(video_yolu, ses_seviyesi=0.20)



def access_token_al() -> Optional[str]:
    """YOUTUBE_REFRESH_TOKEN ile yeni bir Google OAuth2 Access Token alır."""
    client_id = (config.env_al("YOUTUBE_CLIENT_ID") or "").strip().strip("'\"")
    client_secret = (config.env_al("YOUTUBE_CLIENT_SECRET") or "").strip().strip("'\"")
    refresh_token = (config.env_al("YOUTUBE_REFRESH_TOKEN") or "").strip().strip("'\"")

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

        cevap_metni = res.text
        if "invalid_grant" in cevap_metni:
            log.error(
                "YouTube refresh token geçersiz (invalid_grant: %s). Google Cloud Console OAuth Consent Screen 'Testing' modunda ise jeton 7 günde iptal edilir; 'Publish App' (In production) yapılmalıdır. CID=%s*** (Uzunluk=%d), Token=***%s (Uzunluk=%d)",
                cevap_metni[:150],
                client_id[:6] if client_id else "",
                len(client_id),
                refresh_token[-4:] if refresh_token else "",
                len(refresh_token),
            )
        else:
            log.warning("YouTube token yenileme başarısız (%s): %s", res.status_code, cevap_metni[:200])
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
        return {"durum": False, "hata": f"Video dosyası bulunamadı veya boş: {yol}"}

    # 1. Günlük YouTube Kota Denetimi (Maksimum 5 video / gün = 8000 birim)
    yuklenen_bugun = gunluk_yukleme_sayisi_al()
    if yuklenen_bugun >= YOUTUBE_GUNLUK_AZAMI_VIDEO:
        log.warning(
            "YouTube günlük kota koruması: bugün zaten %d video yüklendi. Kota aşımını önlemek için atlanıyor.",
            yuklenen_bugun,
        )
        return {
            "durum": False,
            "hata": f"YouTube günlük kota sınırına ({yuklenen_bugun}/{YOUTUBE_GUNLUK_AZAMI_VIDEO} video) ulaşıldı. Shorts atlandı.",
            "kota_siniri": True,
        }

    token = access_token_al()
    if not token:
        return {"durum": False, "hata": "YouTube erişim jetonu alınamadı."}

    # Shorts Başlık & Açıklama Optimizasyonu (Emlak Ofisi Kimliği)
    # Hukuk bürosu jargonu yerine gayrimenkul & tapu & emlak odaklı dil
    temiz_baslik = baslik.strip()
    hukuk_degisimleri = {
        "Hukuk Bürosu": "Emlak Ofisi",
        "hukuk bürosu": "emlak ofisi",
        "Hukuki Danışmanlık": "Gayrimenkul Danışmanlığı",
        "hukuki danışmanlık": "gayrimenkul danışmanlığı",
        "Hukuk Bülteni": "Emlak Bülteni",
        "hukuk bülteni": "emlak bülteni",
        "Hukuk Rehberi": "Tapu & Emlak Rehberi",
        "hukuk rehberi": "tapu & emlak rehberi",
        "Hukuki Vaka": "Saha & Tapu Analizi",
        "hukuki vaka": "saha & tapu analizi",
    }
    for eski, yeni in hukuk_degisimleri.items():
        temiz_baslik = temiz_baslik.replace(eski, yeni)

    if "#Shorts" not in temiz_baslik and "#shorts" not in temiz_baslik:
        if len(temiz_baslik) <= 90:
            temiz_baslik = f"{temiz_baslik} #Shorts"

    imza = "\n\nEDM Yapı & Gayrimenkul · Güvenilir Emlak & Yatırım Danışmanlığı\n0536 343 41 97 · edmyapigayrimenkul.com\n\n#Shorts #Emlak #Gayrimenkul #Silivri #Yatırım"
    if not aciklama:
        aciklama = f"{temiz_baslik}{imza}"
    else:
        for eski, yeni in hukuk_degisimleri.items():
            aciklama = aciklama.replace(eski, yeni)
        if "edmyapigayrimenkul.com" not in aciklama:
            aciklama = f"{aciklama.strip()}{imza}"

    sabit_etiketler = ["Shorts", "Emlak", "Gayrimenkul", "Silivri", "Arsa", "Konut", "Yatırım", "EDM Yapı", "Tapu", "İmar"]
    # Hukuk bürosu algısı oluşturabilecek etiketleri filtrele
    filtrelenmis_etiketler = [
        t for t in (etiketler or [])
        if not any(yasak in t.lower() for yasak in ["hukuk", "avukat", "dava", "adliye", "baro"])
    ]
    tags = list(set(filtrelenmis_etiketler + sabit_etiketler))

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

    # Ses miksi dene
    yuklenecek_yol = youtube_icin_sesli_video_hazirla(yol)

    headers_init = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": "video/mp4",
        "X-Upload-Content-Length": str(yuklenecek_yol.stat().st_size),
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

        # 2. Binary Video Yüklemesi (3 denemeli)
        for deneme in range(1, 4):
            try:
                with open(yuklenecek_yol, "rb") as f_video:
                    headers_upload = {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "video/mp4",
                        "Content-Length": str(yuklenecek_yol.stat().st_size),
                    }
                    r_up = requests.put(upload_url, headers=headers_upload, data=f_video, timeout=120)

                if r_up.status_code in (200, 201):
                    veri = r_up.json()
                    vid_id = veri.get("id")
                    video_url = f"https://youtube.com/shorts/{vid_id}"
                    log.info("YouTube Shorts yayını başarılı! URL: %s", video_url)
                    gunluk_yukleme_sayisi_artir()
                    return {"durum": True, "video_id": vid_id, "url": video_url}

                if r_up.status_code in (500, 502, 503, 504):
                    log.warning("YouTube video yükleme geçici hata [%d], tekrar deneniyor", r_up.status_code)
                    continue

                return {"durum": False, "hata": f"Video yüklenemedi [{r_up.status_code}]: {r_up.text[:200]}"}
            except requests.RequestException as e:
                log.warning("YouTube upload bağlantı hatası (deneme %d): %s", deneme, e)

        return {"durum": False, "hata": "YouTube video yükleme denemeleri tükendi."}
    except Exception as e:
        log.error("YouTube Shorts yükleme istisnası: %s", e)
        return {"durum": False, "hata": str(e)}
