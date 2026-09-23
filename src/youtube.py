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

from . import config, db, filtre

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
    Eğer video zaten sesliyse (_sesli) mükerrer mikslenmez.
    """
    p = Path(video_yolu)
    if "_sesli" in p.stem or p.name.endswith("_sesli.mp4"):
        return p
    from . import ses
    return ses.sesli_video_hazirla(video_yolu, ses_seviyesi=0.20)



def projeleri_getir() -> List[Dict[str, Any]]:
    """Tanımlı YouTube projelerini (Client ID, Secret, Refresh Token) döner."""
    projeler = []
    # 1. Ana Proje
    c1 = (config.env_al("YOUTUBE_CLIENT_ID") or "").strip().strip("'\"")
    s1 = (config.env_al("YOUTUBE_CLIENT_SECRET") or "").strip().strip("'\"")
    r1 = (config.env_al("YOUTUBE_REFRESH_TOKEN") or "").strip().strip("'\"")
    if c1 and s1 and r1:
        projeler.append({"proje_no": 1, "client_id": c1, "client_secret": s1, "refresh_token": r1})

    # 2. Yedek Proje (2. Google Cloud Projesi - Kota Failover)
    c2 = (config.env_al("YOUTUBE_CLIENT_ID_2") or "").strip().strip("'\"")
    s2 = (config.env_al("YOUTUBE_CLIENT_SECRET_2") or "").strip().strip("'\"")
    r2 = (config.env_al("YOUTUBE_REFRESH_TOKEN_2") or "").strip().strip("'\"")
    if c2 and s2 and r2:
        projeler.append({"proje_no": 2, "client_id": c2, "client_secret": s2, "refresh_token": r2})

    return projeler


def azami_gunluk_video() -> int:
    """Mevcut YouTube proje sayısına göre günlük azami video kotasını döner (proje başına 5 video)."""
    p_sayisi = len(projeleri_getir())
    return max(5, p_sayisi * 5)


def access_token_al(proje_no: Optional[int] = None) -> Optional[str]:
    """Belirtilen YouTube projesi veya ilk uygun proje için taze bir OAuth2 Access Token alır."""
    projeler = projeleri_getir()
    if not projeler:
        log.warning("YouTube API kimlik bilgileri eksik (CLIENT_ID / SECRET / REFRESH_TOKEN).")
        return None

    secilenler = [p for p in projeler if p["proje_no"] == proje_no] if proje_no else projeler
    for p in secilenler:
        try:
            data = {
                "client_id": p["client_id"],
                "client_secret": p["client_secret"],
                "refresh_token": p["refresh_token"],
                "grant_type": "refresh_token",
            }
            res = requests.post(YOUTUBE_TOKEN_URL, data=data, timeout=12)
            if res.status_code == 200:
                token = res.json().get("access_token")
                if token:
                    return token

            cevap_metni = res.text
            if "invalid_grant" in cevap_metni:
                log.error(
                    "YouTube Proje %d refresh token geçersiz (invalid_grant: %s). Google Cloud Console OAuth Consent Screen 'Testing' modunda ise jeton 7 günde iptal edilir; 'Publish App' (In production) yapılmalıdır.",
                    p["proje_no"],
                    cevap_metni[:150],
                )
            else:
                log.warning("YouTube Proje %d token yenileme başarısız (%s): %s", p["proje_no"], res.status_code, cevap_metni[:200])
        except Exception as e:
            log.warning("YouTube Proje %d token alma hatası: %s", p["proje_no"], e)
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

    # 1. Günlük YouTube Kota Denetimi (Mevcut proje sayısına göre dinamik)
    yuklenen_bugun = gunluk_yukleme_sayisi_al()
    azami_video = azami_gunluk_video()
    if yuklenen_bugun >= azami_video:
        log.warning(
            "YouTube günlük kota koruması: bugün zaten %d video yüklendi (azami: %d). Kota aşımını önlemek için atlanıyor.",
            yuklenen_bugun,
            azami_video,
        )
        return {
            "durum": False,
            "hata": f"YouTube günlük kota sınırına ({yuklenen_bugun}/{azami_video} video) ulaşıldı. Shorts atlandı.",
            "kota_siniri": True,
        }

    projeler = projeleri_getir()
    if not projeler:
        return {"durum": False, "hata": "YouTube API kimlik bilgileri eksik veya tanımlanmamış."}

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
        if not any(yasak in filtre.kucult(t) for yasak in ["hukuk", "avukat", "dava", "adliye", "baro"])
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
    yuklenecek_yol = Path(youtube_icin_sesli_video_hazirla(yol))
    if not yuklenecek_yol.exists() or yuklenecek_yol.stat().st_size == 0:
        return {"durum": False, "hata": f"Yüklenecek video dosyası bulunamadı veya boş: {yuklenecek_yol}"}

    # Dosyayı tek seferde belleğe oku (Böylece bayt boyutu sabitlenir, Content-Length / Content-Range sapması imkansız olur)
    video_bayt = yuklenecek_yol.read_bytes()
    toplam_boyut = len(video_bayt)
    if toplam_boyut == 0:
        return {"durum": False, "hata": "YouTube yüklenecek video dosyası boş."}

    # Proje öncelik sırası: Bugün 5'ten fazla video yüklendiyse 2. projeyi ilk sıraya al
    sirali_projeler = list(projeler)
    if len(sirali_projeler) > 1 and yuklenen_bugun >= 5:
        sirali_projeler.reverse()

    son_hata = ""
    for idx, p in enumerate(sirali_projeler, 1):
        token = access_token_al(p["proje_no"])
        if not token:
            son_hata = f"Proje {p['proje_no']} erişim jetonu alınamadı."
            continue

        headers_init = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(toplam_boyut),
        }

        try:
            r_init = requests.post(
                YOUTUBE_UPLOAD_URL,
                headers=headers_init,
                data=json.dumps(meta_payload),
                timeout=20,
            )
            if r_init.status_code != 200 or "Location" not in r_init.headers:
                hata_metni = r_init.text
                log.warning("YouTube Proje %d upload başlatılamadı (%s): %s", p["proje_no"], r_init.status_code, hata_metni[:200])
                if "quotaExceeded" in hata_metni or "exceeded your quota" in hata_metni or r_init.status_code == 403:
                    son_hata = f"Proje {p['proje_no']} kotası aşıldı ({r_init.status_code})"
                    if idx < len(sirali_projeler):
                        log.info("YouTube Proje %d kotası doldu, Proje %d deneniyor...", p["proje_no"], sirali_projeler[idx]["proje_no"])
                        continue
                son_hata = f"Upload başlatılamadı ({r_init.status_code}): {hata_metni[:150]}"
                if idx < len(sirali_projeler):
                    continue
                return {"durum": False, "hata": son_hata}

            upload_url = r_init.headers["Location"]

            # 2. Binary Video Yüklemesi (3 denemeli)
            yukleme_basarili = False
            for deneme in range(1, 4):
                try:
                    headers_upload = {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "video/mp4",
                        "Content-Length": str(toplam_boyut),
                        "Content-Range": f"bytes 0-{toplam_boyut - 1}/{toplam_boyut}",
                    }
                    r_up = requests.put(upload_url, headers=headers_upload, data=video_bayt, timeout=120)

                    if r_up.status_code in (200, 201):
                        veri = r_up.json()
                        vid_id = veri.get("id")
                        video_url = f"https://youtube.com/shorts/{vid_id}"
                        log.info("YouTube Shorts yayını başarılı (Proje %d)! URL: %s", p["proje_no"], video_url)
                        gunluk_yukleme_sayisi_artir()
                        return {"durum": True, "video_id": vid_id, "url": video_url, "proje": p["proje_no"]}

                    if r_up.status_code in (500, 502, 503, 504):
                        log.warning("YouTube Proje %d video yükleme geçici hata [%d], tekrar deneniyor", p["proje_no"], r_up.status_code)
                        continue

                    son_hata = f"Video yüklenemedi [{r_up.status_code}]: {r_up.text[:200]}"
                    break
                except requests.RequestException as e:
                    log.warning("YouTube Proje %d upload bağlantı hatası (deneme %d): %s", p["proje_no"], deneme, e)

            if idx < len(sirali_projeler):
                continue
            return {"durum": False, "hata": son_hata or "YouTube video yükleme denemeleri tükendi."}
        except Exception as e:
            log.error("YouTube Shorts Proje %d istisnası: %s", p["proje_no"], e)
            son_hata = str(e)
            if idx < len(sirali_projeler):
                continue
            return {"durum": False, "hata": son_hata}

    return {"durum": False, "hata": son_hata or "Hiçbir YouTube projesi ile video yüklenemedi."}
