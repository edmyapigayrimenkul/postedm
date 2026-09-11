"""
instagram.py — Instagram Graph API Yayın Modülü
Tekil görsel, çoklu slayt (Carousel) ve Reels (video) yayınlar.
Instabot mimarisinden uyarlanmıştır.
"""

from __future__ import annotations

import io
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageOps
import requests

from . import config, upload_image

log = logging.getLogger(__name__)

GRAPH_TABAN = "https://graph.facebook.com/v21.0"
CIKTI_KLASORU = Path("data/output")


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


def gorselleri_4_5_yap(gorsel_urlleri: List[str]) -> List[str]:
    """
    Instagram Akış (Feed Carousel & Tekil Post) için görselleri içerik tasarımını bozmadan
    kesin 4:5 (1080x1350) formatına getirir.

    9:16 (1080x1920) slaytlar veya orantısız dikey fotoğraflar dikeyde merkezi 1080x1350
    olarak kırpılır ve yeniden CDN'e yüklenir.
    Görsel zaten 4:5 oranındaysa (en-boy ~0.8) dokunulmaz.
    """
    CIKTI_KLASORU.mkdir(parents=True, exist_ok=True)
    yeni_urller = []

    for i, u in enumerate(gorsel_urlleri):
        try:
            im = None
            dosya_adi = None

            # 1. Doğrudan yerel dosya yolu verilmiş olabilir mi?
            p = Path(str(u))
            if p.exists() and p.is_file():
                with Image.open(p) as _img:
                    im = ImageOps.exif_transpose(_img).convert("RGB")
                dosya_adi = p.stem
            elif isinstance(u, str) and (u.startswith("http://") or u.startswith("https://")):
                # 2. Upload önbelleğinde yerel karşılığı var mı?
                yerel = upload_image.yerel_karsiligi(u)
                if yerel and yerel.exists() and yerel.is_file():
                    with Image.open(yerel) as _img:
                        im = ImageOps.exif_transpose(_img).convert("RGB")
                    dosya_adi = yerel.stem
                else:
                    # 3. CIKTI_KLASORU altında aynı isimli dosya var mı?
                    temiz_ad = u.split("?")[0].split("/")[-1]
                    yerel_dosya = CIKTI_KLASORU / temiz_ad
                    if yerel_dosya.exists():
                        with Image.open(yerel_dosya) as _img:
                            im = ImageOps.exif_transpose(_img).convert("RGB")
                        dosya_adi = yerel_dosya.stem
                    else:
                        # 4. Uzak URL'den indir
                        headers = {"User-Agent": "Mozilla/5.0"}
                        r = requests.get(u, headers=headers, timeout=25)
                        r.raise_for_status()
                        with Image.open(io.BytesIO(r.content)) as _img:
                            im = ImageOps.exif_transpose(_img).convert("RGB")
                        dosya_adi = Path(temiz_ad).stem if temiz_ad else f"feed_{int(time.time())}_{i}"

            if im is None:
                yeni_urller.append(u)
                continue

            w, h = im.size
            # Zaten 4:5 (en-boy oranı ~0.8) ise dokunma
            if abs((w / h) - (4 / 5)) < 0.03:
                yeni_urller.append(u)
                continue

            # 9:16 veya 4:5'ten daha uzun dikey görsel ise merkezi 4:5 kırp
            if h > w * 1.25:
                target_h = int(w * 1350 / 1080)
                crop_y = (h - target_h) // 2
                cropped = im.crop((0, crop_y, w, crop_y + target_h))

                if cropped.mode in ("RGBA", "P"):
                    cropped = cropped.convert("RGB")

                hedef_dosya = CIKTI_KLASORU / f"{dosya_adi}_4_5.jpg"
                cropped.save(hedef_dosya, "JPEG", quality=95, optimize=True)

                yuklenen_url = upload_image.gorsel_yukle(hedef_dosya)
                if yuklenen_url:
                    log.info("Instagram Feed için görsel 4:5 formatına kırpıldı ve yüklendi: %s -> %s", dosya_adi, yuklenen_url)
                    yeni_urller.append(yuklenen_url)
                    continue

            # Kırpma gerekmediyse veya yüklenemediyse orijinali koru
            yeni_urller.append(u)

        except Exception as e:
            log.warning("Görsel 4:5 dönüştürme hatası (%s): %s — orijinal URL kullanılıyor", u, e)
            yeni_urller.append(u)

    return yeni_urller


def tekil_gorsel_yayinla(gorsel_url: str, caption: str) -> Optional[str]:
    """Tek bir görseli Instagram'da paylaşır (4:5 format güvencesiyle)."""
    hesap_id, token = _hesap_bilgileri()
    if not hesap_id or not token:
        log.warning("Instagram hesap bilgileri eksik (.env kontrol edin).")
        return None

    # 4:5 format güvencesi
    gorsel_url = gorselleri_4_5_yap([gorsel_url])[0]

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
    """Birden fazla slaytı kaydırmalı (Carousel) post olarak paylaşır (4:5 format güvencesiyle)."""
    hesap_id, token = _hesap_bilgileri()
    if not hesap_id or not token:
        log.warning("Instagram hesap bilgileri eksik.")
        return None

    # 4:5 format güvencesi
    gorsel_urlleri = gorselleri_4_5_yap(gorsel_urlleri)

    if len(gorsel_urlleri) < 2:
        return tekil_gorsel_yayinla(gorsel_urlleri[0], caption)

    # 1. Her görsel için alt öğe oluştur (is_carousel_item=true)
    cocuk_idler = []
    for g_url in gorsel_urlleri[:10]:  # Instagram Carousel azami 10
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


def reels_yayinla(
    video_url: str,
    caption: str,
    kapak_url: Optional[str] = None,
    share_to_feed: bool = True,
) -> Optional[str]:
    """
    Instagram Reels olarak video yayınlar, Instagram post id'sini döner.
    media_type="REELS", video_url ve caption ile video container oluşturulur.
    share_to_feed="true" ile ana akışta da görünür.
    """
    hesap_id, token = _hesap_bilgileri()
    if not hesap_id or not token:
        log.warning("Instagram hesap bilgileri eksik.")
        return None

    url = f"{GRAPH_TABAN}/{hesap_id}/media"
    payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": "true" if share_to_feed else "false",
        "access_token": token,
    }
    if kapak_url:
        payload["cover_url"] = kapak_url

    try:
        resp = requests.post(url, data=payload, timeout=35)
        if resp.status_code != 200:
            log.error("Reels container oluşturma hatası: %s", resp.text)
            return None
        creation_id = resp.json().get("id")
    except Exception as e:
        log.error("Reels konteyner isteği hatası: %s", e)
        return None

    # Reels işlenmesi Meta tarafında 30-120 sn sürebilir
    log.info("Reels videosu Meta sunucularında işleniyor (container: %s)...", creation_id)
    if not _konteyner_durumu_bekle(creation_id, token, max_bekleme=180):
        log.error("Reels konteyneri zamanında hazır olmadı: %s", creation_id)
        return None

    return _yayina_al(creation_id, hesap_id, token)

