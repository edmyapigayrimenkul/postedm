"""
linkedin.py — LinkedIn API v2 / REST API ile Kurumsal Paylaşım Modülü.
EDM Yapı & Gayrimenkul B2B / Yatırımcı Otorite Paylaşımları için özelleştirilmiştir.

Desteklenen Paylaşım Biçimleri:
1. Profesyonel Metin + Bağlantı Paylaşımı (UGC / Share)
2. Tekil Görsel Paylaşımı
3. Çoklu Görsel / Carousel Belge (PDF) Paylaşımı (LinkedIn'de en yüksek etkileşimi alan format)
"""

from __future__ import annotations

import io
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from PIL import Image

from . import config, filtre, haber_alanlari

log = logging.getLogger(__name__)

LINKEDIN_REST_BASE = "https://api.linkedin.com/rest"
LINKEDIN_V2_BASE = "https://api.linkedin.com/v2"
LINKEDIN_VERSION = "202602"
GECICI_HATALAR = {429, 500, 502, 503, 504}

def _hesap_bilgileri() -> Tuple[str, str]:
    """(access_token, organization_urn) döner. Kesinlikle yalnızca kurumsal şirket sayfası kullanılır."""
    token = (config.env_al("LINKEDIN_ACCESS_TOKEN") or "").strip()
    org = (config.env_al("LINKEDIN_ORGANIZATION_URN") or "").strip()

    if org and not org.startswith("urn:li:"):
        org = f"urn:li:organization:{org}"

    return token, org


def kullanilabilir_mi() -> bool:
    """LinkedIn kurumsal entegrasyonu için gerekli token ve şirket URN'i var mı?"""
    token, org = _hesap_bilgileri()
    return bool(token and org and org.startswith("urn:li:organization:"))


def linkedin_metni_hazirla(veri: Dict[str, Any], manset: Optional[str] = None) -> str:
    """
    LinkedIn platformunun profesyonel ve B2B yatırımcı kitlesine özel
    editoryal metin üretir.
    """
    if not isinstance(veri, dict):
        return ""

    baslik = manset or veri.get("manset") or veri.get("baslik") or ""
    kanca = veri.get("kanca") or veri.get("hook") or ""
    spot = veri.get("spot") or veri.get("ozet") or ""

    if not baslik and not kanca and not spot:
        return ""

    detay_maddeleri = veri.get("detay_maddeleri") or []
    uzman_notu = haber_alanlari.sana_etkisi(veri)
    paragraflar = haber_alanlari.detay_paragraflari(veri, kalin=False) if veri.get("detay_yazisi") else []

    parcalar = []

    # 1. Başlık & Kanca
    if kanca:
        kanca_temiz = kanca.replace("//", "·").strip()
        parcalar.append(f"📌 {kanca_temiz.upper()}")
    if baslik:
        parcalar.append(f"{baslik.strip()}\n")

    # 2. Giriş & Editoryal Spot
    if spot:
        parcalar.append(f"{spot.strip()}\n")

    # 3a. Detay (Instabot şeması): paragraflar
    if paragraflar:
        parcalar.extend(f"{p}\n" for p in paragraflar)
        soz, sahibi = haber_alanlari.alinti(veri)
        if soz:
            parcalar.append(f"“{soz}”" + (f" — {sahibi}" if sahibi else "") + "\n")

    # 3b. Resmi Veriler & Detay Maddeleri (Haber şeması: maddeli döküm)
    if detay_maddeleri and not paragraflar:
        parcalar.append("📊 ÖNE ÇIKAN VERİLER VE ANALİZ:")
        for idx, dm in enumerate(detay_maddeleri, 1):
            if isinstance(dm, dict):
                etiket = dm.get("etiket", "")
                etiket_temiz = etiket.split("//")[-1].strip() if "//" in etiket else etiket.strip()
                metin = dm.get("metin", "").strip()
                if etiket_temiz and metin:
                    parcalar.append(f"• {etiket_temiz}: {metin}")
                elif metin:
                    parcalar.append(f"• {metin}")
            elif isinstance(dm, str):
                parcalar.append(f"• {dm.strip()}")
        parcalar.append("")

    # 3c. Otorite Şeması (B1/B3/B4 & Sözlük): Analiz Kartları ve Çözüm Adımları
    if not paragraflar and not detay_maddeleri:
        s2 = veri.get("slayt_2_detay") if isinstance(veri.get("slayt_2_detay"), dict) else {}
        s3 = veri.get("slayt_3_cozum") if isinstance(veri.get("slayt_3_cozum"), dict) else {}
        puf_maddeleri = veri.get("puf_maddeleri") or []
        if s2 or s3 or puf_maddeleri:
            parcalar.append("📋 HUKUKİ ANALİZ VE ÇÖZÜM ADIMLARI:")
            if "kart_1" in s2 and isinstance(s2["kart_1"], dict):
                parcalar.append(f"• ⚠️ Risk/Hata: {s2['kart_1'].get('baslik', '')} — {s2['kart_1'].get('aciklama', '')}")
            if "kart_2" in s2 and isinstance(s2["kart_2"], dict):
                parcalar.append(f"• ⚖️ Yasal Kural: {s2['kart_2'].get('baslik', '')} — {s2['kart_2'].get('aciklama', '')}")
            for m in s3.get("maddeler", []):
                if isinstance(m, dict):
                    parcalar.append(f"• ✅ {m.get('baslik', 'Uygulama')}: {m.get('aciklama', '')}")
                else:
                    parcalar.append(f"• ✅ {str(m)}")
            for pm in puf_maddeleri:
                parcalar.append(f"• 💡 Püf Noktası: {str(pm).strip()}")
            parcalar.append("")

    # 4. Yasal Dayanak & Mevzuat Çerçevesi
    yasal_dayanak = veri.get("yasal_dayanak") or veri.get("mevzuat") or (veri.get("_brief") or {}).get("mevzuat")
    if yasal_dayanak and str(yasal_dayanak).strip():
        parcalar.append(f"⚖️ MEVZUAT VE YASAL DAYANAK:\n{str(yasal_dayanak).strip()}\n")

    # 5. EDM Uzman Notu
    if uzman_notu:
        if veri.get("uzman_notu") and not veri.get("sana_etkisi"):
            parcalar.append(f"🏢 UZMAN DEĞERLENDİRMESİ:\n{uzman_notu.strip()}\n")   # eski şema
        else:
            parcalar.append(f"🏢 BÖLGESEL PİYASA DEĞERLENDİRMESİ:\n{uzman_notu.strip()}\n")

    # 5. İletişim & CTA
    parcalar.append(
        "🤝 Silivri, Çatalca ve Trakya bölgesindeki arsa, tarla ve ticari gayrimenkul "
        "yatırımlarınızda güncel mevzuat ve yerinde ekspertiz için EDM Yapı & Gayrimenkul "
        "olarak yanınızdayız."
    )
    parcalar.append("📞 0212 727 29 55 · edmyapigayrimenkul.com")

    # 6. Profesyonel Hashtag'ler
    parcalar.append("\n#GayrimenkulYatırımı #Arsa #İmarMevzuatı #Silivri #Trakya #EDMYapıGayrimenkul #MilliEmlak")

    metin = "\n".join(parcalar).strip()
    return filtre.markdown_temizle(metin)


def _gorseli_yukle_ve_kaydet(dosya_veya_url: Path | str, token: str, author: str) -> Optional[str]:
    """LinkedIn Assets / Images API ile görseli yükler ve image URN döner."""
    if not author.startswith("urn:li:organization:"):
        log.warning("LinkedIn görsel yükleme yalnızca kurumsal şirket sayfası adına yapılabilir.")
        return None

    try:
        # Görsel verisini al
        if str(dosya_veya_url).startswith("http"):
            res = requests.get(str(dosya_veya_url), timeout=20)
            if res.status_code != 200:
                return None
            ham = res.content
        else:
            p = Path(dosya_veya_url)
            if not p.exists():
                return None
            ham = p.read_bytes()

        # 1. Upload kaydı başlat (Initialize Upload)
        init_url = f"{LINKEDIN_REST_BASE}/images?action=initializeUpload"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "LinkedIn-Version": LINKEDIN_VERSION,
            "X-Restli-Protocol-Version": "2.0.0",
        }
        init_payload = {
            "initializeUploadRequest": {
                "owner": author
            }
        }
        r_init = requests.post(init_url, headers=headers, json=init_payload, timeout=20)
        if r_init.status_code not in (200, 201):
            log.warning("LinkedIn initializeUpload başarısız [%d]: %s", r_init.status_code, r_init.text[:120])
            return None

        data = r_init.json().get("value", {})
        upload_url = data.get("uploadUrl")
        image_urn = data.get("image")
        if not upload_url or not image_urn:
            return None

        # 2. İkili veriyi PUT ile yükle
        put_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "image/jpeg",
        }
        r_put = requests.put(upload_url, headers=put_headers, data=ham, timeout=30)
        if r_put.status_code in (200, 201, 204):
            log.info("LinkedIn görsel yükleme başarılı: %s", image_urn)
            return image_urn
        log.warning("LinkedIn PUT upload başarısız [%d]", r_put.status_code)
    except Exception as e:
        log.warning("LinkedIn görsel yükleme istisnası: %s", e)
    return None


def paylas(
    metin: str,
    gorsel_urlleri: Optional[List[str]] = None,
    dosya_yollari: Optional[List[str | Path]] = None,
) -> Optional[str]:
    """
    LinkedIn üzerinde profesyonel gönderi yayınlar.
    Görsel varsa görselli gönderi, yoksa salt metin paylaşımı yapar.
    """
    token, author = _hesap_bilgileri()
    if not token or not author:
        log.warning("LinkedIn kimlik bilgileri eksik (LINKEDIN_ACCESS_TOKEN veya LINKEDIN_ORGANIZATION_URN).")
        return None

    if not author.startswith("urn:li:organization:"):
        log.warning("LinkedIn paylaşımı yalnızca kurumsal sayfa (urn:li:organization:) adına yapılabilir.")
        return None

    temiz_metin = filtre.markdown_temizle(metin)
    if not temiz_metin:
        log.warning("LinkedIn için paylaşılacak metin boş.")
        return None

    # Görselleri yükle
    aday_gorseller = dosya_yollari or gorsel_urlleri or []
    image_urns = []
    if aday_gorseller:
        for aday in aday_gorseller[:9]:  # LinkedIn en fazla 9 görsel kabul eder
            urn = _gorseli_yukle_ve_kaydet(aday, token, author)
            if urn:
                image_urns.append(urn)

    # Posts API URL ve Header
    post_url = f"{LINKEDIN_REST_BASE}/posts"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "LinkedIn-Version": LINKEDIN_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }

    payload: Dict[str, Any] = {
        "author": author,
        "commentary": temiz_metin,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": []
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False
    }

    # Medya ekle (Tekil veya Çoklu Görsel)
    if len(image_urns) == 1:
        payload["content"] = {
            "media": {
                "id": image_urns[0],
                "altText": "EDM Yapı & Gayrimenkul Analizi"
            }
        }
    elif len(image_urns) > 1:
        payload["content"] = {
            "multiImage": {
                "images": [{"id": urn, "altText": f"EDM Slayt {idx}"} for idx, urn in enumerate(image_urns, 1)]
            }
        }

    for deneme in range(1, 4):
        try:
            r = requests.post(post_url, headers=headers, json=payload, timeout=30)
            if r.status_code in (200, 201):
                post_id = r.headers.get("x-restli-id") or r.headers.get("x-linkedin-id") or "basarili"
                log.info("LinkedIn yayını başarılı! ID: %s", post_id)
                return post_id

            if r.status_code in GECICI_HATALAR:
                log.warning("LinkedIn geçici HTTP %d hatası, %d sn bekleniyor (deneme %d/3)", r.status_code, deneme * 2, deneme)
                time.sleep(deneme * 2)
                continue

            log.error("LinkedIn API paylaşım hatası [%d]: %s", r.status_code, r.text[:200])
            break
        except requests.RequestException as e:
            log.warning("LinkedIn ağ hatası (deneme %d/3): %s", deneme, e)
            time.sleep(deneme * 2)

    return None
