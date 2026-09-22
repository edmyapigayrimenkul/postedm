"""
fetch_web_image.py — Güncel olaylar ve emlak/mevzuat haberleri için webden yüksek çözünürlüklü (HD/4K) gerçek fotoğraflar çeker.
Instabot / Daily Brief mimarisinden uyarlanmıştır.

Haber sitelerinin kendi og:image'ı düşük çözünürlüklü, kırpık veya taranmış belge/tablo olduğunda;
olayın bizzat gerçekleştiği yeri/projeyi/açıklamayı gösteren gerçek fotoğrafları web üzerinden arar,
çözünürlük, netlik ve filigransızlık filtrelerinden geçirerek slayt motoruna aktarır.
"""

from __future__ import annotations

import html
import io
import json
import logging
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image, ImageOps
import requests

from . import gorsel_kalite

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Görsel aramalarında filtrelenecek istenmeyen anahtar kelimeler
ISTENMEYEN_TERIMLER = (
    "logo", "icon", "cartoon", "vector", "drawing", "caricature",
    "chart", "graph", "diagram", "symbol", "avatar",
    "thumbnail", "poster", "banner", "sticker", "form", "tablo",
    "belge", "ilan", "dilekce", "resmigazete", "document"
)

# Filigran basan ücretli stok siteleri ve taranmış ilan formları
YASAKLI_STOK_SITELERI = (
    "vecteezy", "shutterstock", "gettyimages", "alamy", "dreamstime",
    "istockphoto", "depositphotos", "123rf", "stockphoto", "freepik",
    "watermark", "pond5", "canva", "ilan.memurlar.net", "kamuilan",
    "ilan.gov.tr", "advert/documents"
)


def _ddg_gorsel_ara(sorgu: str) -> List[Dict[str, Any]]:
    """DuckDuckGo Image Search üzerinden yüksek çözünürlüklü görselleri listeler."""
    try:
        s = requests.Session()
        res = s.get(
            "https://duckduckgo.com/",
            params={"q": sorgu},
            headers=HEADERS,
            timeout=10,
        )
        m = re.search(r'vqd=([\d-]+)', res.text) or re.search(r'vqd=\"([\d-]+)\"', res.text)
        if not m:
            m = re.search(r"vqd='([\d-]+)'", res.text) or re.search(r'data-vqd="([\d-]+)"', res.text)
        if not m:
            return []
        vqd = m.group(1)

        r = s.get(
            "https://duckduckgo.com/i.js",
            params={"l": "tr-tr", "o": "json", "q": sorgu, "vqd": vqd, "f": ",,,", "p": "1"},
            headers=HEADERS,
            timeout=10,
        )
        if r.status_code != 200:
            return []
        return r.json().get("results", [])
    except Exception as e:
        log.warning("Web görsel arama hatası (%s): %s", sorgu, e)
        return []


def _bing_gorsel_ara(sorgu: str) -> List[Dict[str, Any]]:
    """Bing Görsel Arama üzerinden yüksek çözünürlüklü basın ve haber fotoğraflarını çeker."""
    try:
        q = urllib.parse.quote(str(sorgu).strip())
        url = f"https://www.bing.com/images/search?q={q}&form=HDRSC2&first=1"
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return []
        matches = re.findall(r'm=\"({[^\"]+})\"', res.text) or re.findall(r'm=(&quot;{[^&]+}&quot;)', res.text)
        sonuclar = []
        for m in matches:
            s = html.unescape(m).strip('\"')
            try:
                d = json.loads(s)
                img_url = (d.get("murl") or "").strip()
                thumb_url = (d.get("turl") or "").strip()
                if img_url and img_url.startswith("http"):
                    sonuclar.append({
                        "image": img_url,
                        "thumbnail": thumb_url,
                        "title": d.get("t") or d.get("desc") or "",
                        "width": d.get("width") or 1200,
                        "height": d.get("height") or 800,
                        "source": "Bing",
                        "url": d.get("purl") or "",
                    })
            except Exception:
                continue
        return sonuclar
    except Exception as e:
        log.warning("Bing görsel arama hatası (%s): %s", sorgu, e)
        return []


# Oturum / tur içi görsel adayı önbelleği
_GORSEL_ADAY_BELLEGI: Dict[str, List[Tuple[Image.Image, Dict[str, Any]]]] = {}


def fotograf_ara(
    sorgular: List[str],
    asgari_genislik: int = 800,
    asgari_yukseklik: int = 450,
    atlanacak: int = 0,
) -> Optional[Tuple[Image.Image, Dict[str, Any]]]:
    """
    Verilen sorgu listesini sırayla arar; 4K/HD çözünürlük ve kristal netlik kriterini
    karşılayan en uygun gerçek fotoğrafı indirir.
    atlanacak parametresine göre sıradaki farklı/alternatif fotoğrafı seçer.
    """
    cache_key = "___".join(s.strip().lower() for s in sorgular if s.strip())
    if cache_key in _GORSEL_ADAY_BELLEGI and _GORSEL_ADAY_BELLEGI[cache_key]:
        havuz = _GORSEL_ADAY_BELLEGI[cache_key]
        secilen_idx = atlanacak % len(havuz)
        log.info("Görsel adayı önbellekten çekildi (atlanacak=%d -> indeks=%d/%d)",
                 atlanacak, secilen_idx, len(havuz))
        return havuz[secilen_idx]

    tum_adaylar = []
    gorulen_urller = set()

    for sorgu in sorgular:
        if not sorgu or not str(sorgu).strip():
            continue
        ham_sonuclar = _bing_gorsel_ara(str(sorgu).strip())
        if not ham_sonuclar:
            ham_sonuclar = _ddg_gorsel_ara(str(sorgu).strip())
        if not ham_sonuclar:
            continue

        for item in ham_sonuclar:
            w = item.get("width", 0)
            h = item.get("height", 0)
            img_url = (item.get("image") or "").strip()
            img_url_l = img_url.lower()
            if not img_url or not img_url.startswith("http") or img_url in gorulen_urller:
                continue

            # Asgari boyut eşiği: 16:9 HD (800x450+) veya kare/portre (600x600+)
            if (w < asgari_genislik or h < asgari_yukseklik) and not (w >= 600 and h >= 600):
                continue

            # Filigranlı stok siteleri ele
            if any(yasak in img_url_l for yasak in YASAKLI_STOK_SITELERI):
                continue

            baslik = (item.get("title") or "").lower()
            if any(yasak in baslik for yasak in ISTENMEYEN_TERIMLER):
                continue

            gorulen_urller.add(img_url)
            tum_adaylar.append(item)

    if not tum_adaylar:
        return None

    # İndirme ve kalite filtresi: geçerli adayları topla (en fazla 10 adet)
    gecerli_adaylar: List[Tuple[Image.Image, Dict[str, Any]]] = []
    for aday in tum_adaylar:
        if len(gecerli_adaylar) >= 10:
            break

        url_listesi = [aday["image"]]
        if aday.get("thumbnail") and aday["thumbnail"] != aday["image"]:
            url_listesi.append(aday["thumbnail"])

        for url in url_listesi:
            try:
                cevap = requests.get(url, headers=HEADERS, timeout=10)
                if cevap.status_code != 200:
                    continue
                ham_boyut_kb = len(cevap.content) / 1024.0
                foto = Image.open(io.BytesIO(cevap.content))
                foto = ImageOps.exif_transpose(foto)
                foto.load()

                # Piksel yoğunluğu, dikey kırpma ölçeği ve Laplacian netlik denetimi
                kaliteli, sebep = gorsel_kalite.gorsel_kalite_denetle(foto, dosya_boyutu_kb=ham_boyut_kb)
                if not kaliteli:
                    log.info("Web görsel adayı elendi (%s): %s", url, sebep)
                    continue

                net_foto = gorsel_kalite.kristal_netlestir(foto.convert("RGB"))
                gecerli_adaylar.append((net_foto, aday))
                log.info("Webden temiz HD basın fotoğrafı onaylandı (%sx%s, %.1f KB): %s",
                         foto.width, foto.height, ham_boyut_kb, url)
                break
            except Exception as e:
                log.debug("Web görseli indirilemedi (%s): %s", url, e)
                continue

    if not gecerli_adaylar:
        return None

    _GORSEL_ADAY_BELLEGI[cache_key] = gecerli_adaylar
    secilen_idx = atlanacak % len(gecerli_adaylar)
    log.info("Web görsel adayı seçildi: %d/%d (atlanacak=%d)",
             secilen_idx + 1, len(gecerli_adaylar), atlanacak)
    return gecerli_adaylar[secilen_idx]


def atif_metni(kayit: Optional[Dict[str, Any]]) -> str:
    """Web aramasından gelen fotoğraf için atıf satırı üretir."""
    if not kayit:
        return ""
    url = (kayit.get("image") or kayit.get("url") or "").strip()
    if not url:
        return ""
    m = re.match(r"https?://(?:www\.)?([^/:]+)", url)
    if not m:
        return ""
    alan = m.group(1).strip()
    if not alan or "." not in alan:
        return ""
    return f"Fotoğraf: {alan}"
