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

GECICI_HATALAR = {429, 500, 502, 503, 504}
# Instagram Graph API geçici alt hata kodları:
# 2207003: Medyanın indirilmesi çok uzun sürüyor (Timeout)
# 2207032: Medya geçici olarak işlenemedi
# 2207052: Only photo or video can be accepted (Medya indirme başarısız / geçici erişim gecikmesi)
# Instagram 'is_transient: false' dese dahi bu hatalar karşı tarafın anlık durumundan kaynaklıdır ve geçicidir.
GECICI_ALT_KODLAR = {2207003, 2207032, 2207052}
MEDYA_BEKLEME_SANIYE = 15
MEDYA_AZAMI_DENEME = 6


def _alt_kod(cevap: requests.Response) -> Optional[int]:
    """Graph API hata cevabından `error_subcode`'u çıkarır."""
    try:
        return cevap.json().get("error", {}).get("error_subcode")
    except Exception:
        return None


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

    # 1. Konteyner oluştur (Geçici alt kod ve ağ hatası korumalı)
    url = f"{GRAPH_TABAN}/{hesap_id}/media"
    payload = {
        "image_url": gorsel_url,
        "caption": caption,
        "access_token": token,
    }

    creation_id = None
    for deneme in range(1, MEDYA_AZAMI_DENEME + 1):
        try:
            resp = requests.post(url, data=payload, timeout=30)
            if resp.status_code == 200:
                creation_id = resp.json().get("id")
                break

            subcode = _alt_kod(resp)
            if subcode in GECICI_ALT_KODLAR:
                log.warning(
                    "Instagram medya indirme gecikmesi (subcode %s, %s sn bekleniyor, deneme %d/%d): %s",
                    subcode, MEDYA_BEKLEME_SANIYE, deneme, MEDYA_AZAMI_DENEME, gorsel_url,
                )
                time.sleep(MEDYA_BEKLEME_SANIYE)
                continue

            if resp.status_code in GECICI_HATALAR:
                time.sleep(3 * deneme)
                continue

            log.error("Instagram tekil konteyner hatası [%d]: %s", resp.status_code, resp.text)
            break
        except Exception as e:
            log.warning("Instagram tekil konteyner ağ istisnası (deneme %d/%d): %s", deneme, MEDYA_AZAMI_DENEME, e)
            time.sleep(3 * deneme)

    if not creation_id:
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

    # 1. Her görsel için alt öğe oluştur (is_carousel_item=true, geçici medya gecikmesi korumalı)
    cocuk_idler = []
    for g_url in gorsel_urlleri[:10]:  # Instagram Carousel azami 10
        payload = {
            "image_url": g_url,
            "is_carousel_item": "true",
            "access_token": token,
        }
        child_id = None
        for deneme in range(1, MEDYA_AZAMI_DENEME + 1):
            try:
                resp = requests.post(f"{GRAPH_TABAN}/{hesap_id}/media", data=payload, timeout=25)
                if resp.status_code == 200:
                    child_id = resp.json().get("id")
                    break

                subcode = _alt_kod(resp)
                if subcode in GECICI_ALT_KODLAR:
                    log.warning(
                        "Instagram medya indirme gecikmesi (subcode %s, %s sn bekleniyor, deneme %d/%d): %s",
                        subcode, MEDYA_BEKLEME_SANIYE, deneme, MEDYA_AZAMI_DENEME, g_url,
                    )
                    time.sleep(MEDYA_BEKLEME_SANIYE)
                    continue

                if resp.status_code in GECICI_HATALAR:
                    time.sleep(3 * deneme)
                    continue

                log.error("Carousel alt öğe hatası (%s): %s", g_url, resp.text)
                break
            except Exception as e:
                log.warning("Carousel alt öğe isteği hatası (%s, deneme %d/%d): %s", g_url, deneme, MEDYA_AZAMI_DENEME, e)
                time.sleep(3 * deneme)

        if child_id:
            cocuk_idler.append(child_id)
        else:
            log.error("Carousel alt öğesi üretilemedi: %s", g_url)

        time.sleep(1)

    if len(cocuk_idler) < 2:
        log.error("Carousel için yeterli alt öğe üretilemedi (%d/%d başarılı).", len(cocuk_idler), len(gorsel_urlleri))
        return None

    # 2. Ana Carousel konteyneri oluştur
    payload = {
        "media_type": "CAROUSEL",
        "children": ",".join(cocuk_idler),
        "caption": caption,
        "access_token": token,
    }

    creation_id = None
    for deneme in range(1, 4):
        try:
            resp = requests.post(f"{GRAPH_TABAN}/{hesap_id}/media", data=payload, timeout=30)
            if resp.status_code == 200:
                creation_id = resp.json().get("id")
                break
            log.warning("Carousel ana konteyner denemesi %d başarısız: %s", deneme, resp.text)
            time.sleep(3 * deneme)
        except Exception as e:
            log.warning("Carousel ana konteyner istek hatası (%d/3): %s", deneme, e)
            time.sleep(3 * deneme)

    if not creation_id:
        log.error("Carousel ana konteyneri oluşturulamadı.")
        return None

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

    creation_id = None
    for deneme in range(1, MEDYA_AZAMI_DENEME + 1):
        try:
            resp = requests.post(url, data=payload, timeout=35)
            if resp.status_code == 200:
                creation_id = resp.json().get("id")
                break

            subcode = _alt_kod(resp)
            if subcode in GECICI_ALT_KODLAR:
                log.warning("Reels video indirme gecikmesi (subcode %s, %s sn bekleniyor): %s", subcode, MEDYA_BEKLEME_SANIYE, video_url)
                time.sleep(MEDYA_BEKLEME_SANIYE)
                continue

            if resp.status_code in GECICI_HATALAR:
                time.sleep(3 * deneme)
                continue

            log.error("Reels container oluşturma hatası: %s", resp.text)
            break
        except Exception as e:
            log.warning("Reels konteyner istek hatası (deneme %d/%d): %s", deneme, MEDYA_AZAMI_DENEME, e)
            time.sleep(3 * deneme)

    if not creation_id:
        return None

    # Reels işlenmesi Meta tarafında 30-120 sn sürebilir
    log.info("Reels videosu Meta sunucularında işleniyor (container: %s)...", creation_id)
    if not _konteyner_durumu_bekle(creation_id, token, max_bekleme=180):
        log.error("Reels konteyneri zamanında hazır olmadı: %s", creation_id)
        return None

    return _yayina_al(creation_id, hesap_id, token)


def story_yayinla(gorsel_url: str) -> Optional[str]:
    """
    Instagram Story olarak 9:16 dikey görsel yayınlar.
    Instagram Graph API media_type="STORIES" kullanır.
    """
    hesap_id, token = _hesap_bilgileri()
    if not hesap_id or not token:
        log.warning("Instagram hesap bilgileri eksik.")
        return None

    url = f"{GRAPH_TABAN}/{hesap_id}/media"
    payload = {
        "image_url": gorsel_url,
        "media_type": "STORIES",
        "access_token": token,
    }

    creation_id = None
    for deneme in range(1, MEDYA_AZAMI_DENEME + 1):
        try:
            resp = requests.post(url, data=payload, timeout=30)
            if resp.status_code == 200:
                creation_id = resp.json().get("id")
                break

            subcode = _alt_kod(resp)
            if subcode in GECICI_ALT_KODLAR:
                log.warning(
                    "Instagram Story indirme gecikmesi (subcode %s, %s sn bekleniyor): %s",
                    subcode, MEDYA_BEKLEME_SANIYE, gorsel_url,
                )
                time.sleep(MEDYA_BEKLEME_SANIYE)
                continue

            if resp.status_code in GECICI_HATALAR:
                time.sleep(3 * deneme)
                continue

            log.error("Instagram story konteyner hatası [%d]: %s", resp.status_code, resp.text)
            break
        except Exception as e:
            log.warning("Instagram story konteyner hatası (deneme %d/%d): %s", deneme, MEDYA_AZAMI_DENEME, e)
            time.sleep(3 * deneme)

    if not creation_id:
        return None

    if not _konteyner_durumu_bekle(creation_id, token, max_bekleme=60):
        return None

    return _yayina_al(creation_id, hesap_id, token)


def medya_metrikleri_al(medya_id: str) -> Optional[Dict[str, Any]]:
    """
    Instagram Graph API üzerinden bir medyanın (post/carousel/reels)
    erişim, kaydetme, paylaşım, beğeni ve yorum verilerini çeker.

    Ölçülemeyen değer 0 DEĞİL None döner. Önceki sürüm insights hatasını DEBUG'da
    yutup 0 yazıyordu; jetonda instagram_manage_insights izni hiç olmadığı için
    ilk günden beri her postun erişimi "0" kaydedildi ve ölçüm kördü.
    Hata nedeni sonuc["insights_hata"]'da taşınır.
    """
    hesap_id, token = _hesap_bilgileri()
    if not token or not medya_id:
        return None

    sonuc: Dict[str, Any] = {
        "likes": None,
        "comments": None,
        "reach": None,
        "saved": None,
        "shares": None,
        "impressions": None,
        "media_type": "",
        "insights_hata": None,
    }

    # 1. Temel post alanları (likes, comments, media_type)
    url_temel = f"{GRAPH_TABAN}/{medya_id}"
    params_temel = {
        "fields": "id,like_count,comments_count,media_type,timestamp",
        "access_token": token,
    }

    try:
        r_temel = requests.get(url_temel, params=params_temel, timeout=12)
        if r_temel.status_code == 200:
            veri = r_temel.json()
            sonuc["likes"] = veri.get("like_count", 0)
            sonuc["comments"] = veri.get("comments_count", 0)
            sonuc["media_type"] = veri.get("media_type", "")
        else:
            log.warning("Instagram temel post verisi alınamadı [%d]: %s", r_temel.status_code, r_temel.text[:200])
    except Exception as e:
        log.warning("Instagram temel post sorgu hatası (%s): %s", medya_id, e)

    # 2. Insights metrikleri. "shares" önceden hiç istenmiyordu (hep 0 kaldı).
    #    Bir medya türü bir metriği desteklemezse API tüm isteği reddeder;
    #    o durumda daha dar küme denenir.
    url_insights = f"{GRAPH_TABAN}/{medya_id}/insights"
    try:
        r_ins = None
        for metrik in ("reach,saved,shares,total_interactions", "reach,saved"):
            r_ins = requests.get(url_insights, params={"metric": metrik, "access_token": token}, timeout=12)
            hata = (r_ins.json().get("error") or {}) if r_ins.status_code != 200 else {}
            if r_ins.status_code == 200 or hata.get("code") != 100:
                break
        if r_ins.status_code == 200:
            data = r_ins.json().get("data", [])
            for item in data:
                m_name = item.get("name")
                m_val = 0
                values = item.get("values", [])
                if values and isinstance(values, list):
                    m_val = values[0].get("value", 0)
                elif "value" in item:
                    m_val = item.get("value", 0)

                if m_name == "reach":
                    sonuc["reach"] = m_val
                elif m_name == "saved":
                    sonuc["saved"] = m_val
                elif m_name == "shares":
                    sonuc["shares"] = m_val
                elif m_name == "impressions":
                    sonuc["impressions"] = m_val
        else:
            hata = (r_ins.json().get("error") or {}) if r_ins is not None else {}
            if hata.get("code") == 10:
                sonuc["insights_hata"] = "izin_yok"
                log.warning(
                    "Instagram insights İZNİ YOK (#10): jetonda instagram_manage_insights "
                    "olmadan erişim/kayıt/paylaşım ölçülemez. Medya %s", medya_id,
                )
            else:
                sonuc["insights_hata"] = f"http_{r_ins.status_code}"
                log.warning("Instagram insights alınamadı [%d]: %s", r_ins.status_code, r_ins.text[:200])
    except Exception as e:
        sonuc["insights_hata"] = type(e).__name__
        log.warning("Instagram insights sorgu hatası (%s): %s", medya_id, e)

    return sonuc


