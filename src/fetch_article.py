"""
fetch_article.py — Haberin TAM METNİNİ ve Orijinal Görselini Çeker.
Instabot / Daily Brief mimarisinden uyarlanmıştır.

Neden var?
    RSS özetleri çoğu zaman 1-2 cümlelik "devamı sitemizde" teaser'larıdır.
    Model bu kısa özetle baş başa kaldığında aradaki boşluğu yapay cümlelerle
    doldurmak zorunda kalır ("içi boş övgü" veya gerçek dışı iddialar).
    Haber sitesinden asıl metin (JSON-LD veya makale gövdesi) çekildiğinde
    Gemini somut kanun maddeleri, tarihler, imar verileri ve isimlerle konuşur.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
from typing import Optional

from bs4 import BeautifulSoup
import requests

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

AZAMI_UZUNLUK = 10000
ASGARI_UZUNLUK = 180

GEREKSIZ_ETIKETLER = [
    "script", "style", "nav", "header", "footer", "aside",
    "form", "iframe", "noscript", "figcaption", "svg",
]


def _sayfayi_getir(url: str, zaman_asimi: int = 15) -> Optional[requests.Response]:
    """Sayfayı 3 denemeli olarak indirir, kalıcı hatalarda (404, 403 vb.) erken bırakır."""
    for deneme in range(1, 4):
        try:
            r = requests.get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
                timeout=zaman_asimi,
            )
            # Kalıcı hatalar tekrarlanmaz
            if r.status_code in (400, 401, 403, 404, 410, 451):
                log.debug("Kalıcı HTTP hatası [%d]: %s", r.status_code, url)
                return None
            if r.status_code == 200:
                return r
        except requests.RequestException as e:
            if deneme == 3:
                log.warning("Sayfa indirilemedi (%s): %s", url, e)
            time.sleep(1 * deneme)
    return None


def _jsonld_articlebody(soup: BeautifulSoup) -> Optional[str]:
    """Schema.org JSON-LD NewsArticle 'articleBody' verisini okur."""
    for etiket in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not etiket.string:
            continue
        try:
            veri = json.loads(etiket.string)
        except (json.JSONDecodeError, TypeError):
            continue

        adaylar = []
        if isinstance(veri, dict):
            adaylar = veri.get("@graph") if "@graph" in veri else [veri]
        elif isinstance(veri, list):
            adaylar = veri

        for aday in adaylar or []:
            if not isinstance(aday, dict):
                continue
            govde = aday.get("articleBody")
            if govde and isinstance(govde, str) and len(govde) >= ASGARI_UZUNLUK:
                return govde.strip()
    return None


def _paragraf_metni(oge) -> str:
    paragraflar = [p.get_text(" ", strip=True) for p in oge.find_all("p")]
    return " ".join(p for p in paragraflar if len(p) > 35)


def _paragraflardan_topla(soup: BeautifulSoup) -> Optional[str]:
    """HTML hiyerarşisinde en zengin paragraf kümesini daraltarak bulur."""
    adaylar = soup.find_all(["article", "main", "div", "section"])
    if not adaylar:
        return None

    en_iyi = max(adaylar, key=lambda e: len(_paragraf_metni(e)), default=None)
    if not en_iyi:
        return None
    en_iyi_uzunluk = len(_paragraf_metni(en_iyi))
    if en_iyi_uzunluk < ASGARI_UZUNLUK:
        return None

    # Kademe kademe daha dar kapsayıcıya in
    while True:
        daha_dar = None
        for cocuk in en_iyi.find_all(["article", "main", "div", "section"], recursive=False):
            if len(_paragraf_metni(cocuk)) >= en_iyi_uzunluk * 0.88:
                daha_dar = cocuk
                break
        if daha_dar is None:
            break
        en_iyi = daha_dar
        en_iyi_uzunluk = len(_paragraf_metni(en_iyi))

    metin = _paragraf_metni(en_iyi)
    return metin.strip() if len(metin) >= ASGARI_UZUNLUK else None


def _kucult(metin: str) -> str:
    """Türkçe İ ve I harflerini gözeterek küçültür."""
    return metin.replace("İ", "i").replace("I", "ı").lower()


def _baslikla_ilgili_mi(metin: str, baslik: str) -> bool:
    """Çekilen metnin başka bir yan sütun veya reklam değil, haberin kendisi olduğunu teyit eder."""
    if not baslik:
        return True
    govde = _kucult(metin)
    kelimeler = [k for k in re.findall(r"\w+", _kucult(baslik)) if len(k) >= 4]
    if len(kelimeler) < 2:
        return True
    gecen = sum(1 for k in kelimeler if k in govde)
    return gecen >= max(2, len(kelimeler) // 3)


def makale_metni_cek(link: str, baslik: Optional[str] = None, zaman_asimi: int = 15) -> Optional[str]:
    """
    Haber sayfasını indirip gövde metnini (makale metni) döner.
    Hata fırlatmaz, başaramazsa None döner.
    """
    resp = _sayfayi_getir(link, zaman_asimi)
    if resp is None:
        return None

    try:
        soup = BeautifulSoup(resp.content, "html.parser")
    except Exception as e:
        log.warning("Makale HTML ayrıştırılamadı (%s): %s", link, e)
        return None

    for etiket in soup.find_all(GEREKSIZ_ETIKETLER):
        etiket.decompose()

    for uretici in (_jsonld_articlebody, _paragraflardan_topla):
        try:
            aday = uretici(soup)
            if aday and len(aday) >= ASGARI_UZUNLUK:
                if baslik and not _baslikla_ilgili_mi(aday, baslik):
                    continue
                # Fazla boşlukları temizle ve sınırla
                temiz = re.sub(r"\s+", " ", aday).strip()
                return temiz[:AZAMI_UZUNLUK]
        except Exception as e:
            log.debug("Gövde çıkarıcı hatası: %s", e)

    return None


def og_gorseli_cek(link: str, zaman_asimi: int = 15) -> Optional[str]:
    """
    Haber sayfasından en kaliteli görsel URL'ini döner:
    1. og:image / twitter:image
    2. schema.org JSON-LD 'image' alanı
    3. figure/article içi öne çıkan görsel
    """
    resp = _sayfayi_getir(link, zaman_asimi)
    if resp is None:
        return None

    try:
        soup = BeautifulSoup(resp.content, "html.parser")
    except Exception:
        return None

    # 1. OpenGraph / Twitter meta
    for ozellik in ("og:image", "twitter:image", "twitter:image:src"):
        meta = soup.find("meta", property=ozellik) or soup.find("meta", attrs={"name": ozellik})
        if meta and meta.get("content"):
            u = meta["content"].strip()
            if u.startswith("http"):
                return urllib.parse.urljoin(link, u)

    # 2. JSON-LD Image
    for etiket in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not etiket.string:
            continue
        try:
            veri = json.loads(etiket.string)
            if isinstance(veri, dict):
                g = veri.get("image")
                if isinstance(g, str) and g.startswith("http"):
                    return g
                elif isinstance(g, dict) and g.get("url"):
                    return g["url"]
                elif isinstance(g, list) and len(g) > 0 and isinstance(g[0], str):
                    return g[0]
        except Exception:
            continue

    # 3. Makale içi görsel
    for secici in ("article img", ".post-content img", ".entry-content img", "figure img"):
        img = soup.select_one(secici)
        if img and img.get("src") and img["src"].startswith("http"):
            return img["src"]

    return None
