"""
src/cizim/kardes.py — Kardeş haber eşleştirme ve alternatif basın fotoğrafları.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from PIL import Image

from .. import config, db
from . import stok

log = logging.getLogger(__name__)

HABER_ALAN_ADLARI = (
    "emlakkulisi.com", "trthaber.com", "aa.com.tr", "ekonomim.com", "dunya.com",
    "haberturk.com", "bloomberght.com", "cnnturk.com", "milliyet.com.tr", "sabah.com.tr",
    "ntv.com.tr", "hurriyet.com.tr", "sozcu.com.tr", "cumhuriyet.com.tr", "t24.com.tr",
    "turkiyegazetesi.com.tr", "haberler.com", "ensonhaber.com",
)

ETKISIZ_KELIMELER = {
    "icin", "olan", "gibi", "kadar", "sonra", "once", "veya", "gore",
    "biri", "yeni", "daha", "cok", "bazi", "tum", "her", "ile", "ve",
    "bir", "bu", "su", "o", "da", "de", "ta", "te", "mi", "mu", "mu",
}


def konu_imzasi(baslik: str) -> Tuple[set[str], set[str]]:
    """Tekrar denetimi ve kardeş haber eşleştirmesi için anahtar kelimeler ve isimler."""
    kelimeler = set()
    for ham in (baslik or "").lower().replace("'", " ").split():
        temiz = "".join(k for k in ham if k.isalnum())
        if len(temiz) >= 4 and temiz not in ETKISIZ_KELIMELER:
            kelimeler.add(temiz)

    isimler = set()
    for ham in (baslik or "").replace("'", " ").split():
        temiz = "".join(k for k in ham if k.isalnum())
        if len(temiz) >= 4 and temiz[:1].isupper() and temiz.lower() not in ETKISIZ_KELIMELER:
            isimler.add(temiz.lower())
    return kelimeler, isimler


def _kardes_sorgula(con, haber_id: Any, k1: set[str], i1: set[str], azami: int) -> List[str]:
    sutunlar = set()
    try:
        bilgi = con.execute("PRAGMA table_info(haberler)").fetchall()
        for b in bilgi:
            sutunlar.add(b[1] if isinstance(b, (tuple, list)) else b["name"])
    except Exception:
        pass
    baslik_col = "orijinal_baslik" if "orijinal_baslik" in sutunlar else ("baslik" if "baslik" in sutunlar else "orijinal_baslik")
    url_col = "orijinal_url" if "orijinal_url" in sutunlar else ("link" if "link" in sutunlar else "orijinal_url")
    foto_col = "gorsel_url" if "gorsel_url" in sutunlar else ("foto_url" if "foto_url" in sutunlar else "gorsel_url")
    tarih_filtre = "eklenme_tarihi > datetime('now', '-3 days')" if "eklenme_tarihi" in sutunlar else "1=1"

    satirlar = con.execute(
        f"""SELECT id, {baslik_col}, {url_col}, {foto_col} FROM haberler
           WHERE id != ? AND COALESCE({url_col}, '') != ''
             AND {tarih_filtre}""",
        (haber_id,),
    ).fetchall()
    esler = []
    for r in satirlar:
        eslesme_dict = isinstance(r, dict) or hasattr(r, "keys")
        b2 = r[baslik_col] if eslesme_dict else r[1]
        link = r[url_col] if eslesme_dict else r[2]
        foto_url = (r[foto_col] if eslesme_dict else r[3]) or ""
        if not link or not str(link).startswith("http"):
            continue
        k2, i2 = konu_imzasi(b2 or "")
        ortak = len(k1 & k2)
        if ortak >= 3 or (ortak >= 2 and (i1 & i2)):
            esler.append((ortak + (1 if foto_url else 0), link))
    esler.sort(key=lambda x: -x[0])
    return [link for _, link in esler if link][:azami]


def kardes_linkler(con, haber: Dict[str, Any], azami: int = 4) -> List[str]:
    """Aynı olayı işleyen veritabanındaki kardeş haber linklerini toplar."""
    baslik = haber.get("orijinal_baslik") or haber.get("baslik") or haber.get("manset") or ""
    if not baslik:
        return []
    k1, i1 = konu_imzasi(baslik)
    haber_id = haber.get("id") or 0
    try:
        if con is not None:
            return _kardes_sorgula(con, haber_id, k1, i1, azami)
        with db._baglanti_al() as yeni_con:
            return _kardes_sorgula(yeni_con, haber_id, k1, i1, azami)
    except Exception as e:
        log.debug("Kardeş haber sorgusu: %s", e)
        return []


def canli_kardes_linkler(baslik: str, haric_link: str = "", azami: int = 5) -> List[str]:
    """Aynı haberin diğer Türk haber sitelerindeki sayfalarını canlı arar."""
    if not baslik or config.test_modu():
        return []
    q = re.sub(r"['\"«»“”‘’:,!?()\[\]\-_/\\.]", " ", baslik)
    kelimeler = [k for k in q.split() if len(k) > 2]
    if not kelimeler:
        return []
    sorgu = " ".join(kelimeler[:6])
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"}
    bulunanlar: List[str] = []
    try:
        r = requests.post("https://html.duckduckgo.com/html/", data={"q": sorgu}, headers=headers, timeout=8)
        if r.status_code == 200:
            corba = BeautifulSoup(r.text, "html.parser")
            for a in corba.select(".result__title a"):
                href = (a.get("href") or "").strip()
                m = re.search(r"uddg=([^&]+)", href)
                if m:
                    href = urllib.parse.unquote(m.group(1))
                if not href.startswith("http") or href == haric_link or href in bulunanlar:
                    continue
                if any(alan in href.lower() for alan in HABER_ALAN_ADLARI):
                    bulunanlar.append(href)
                    if len(bulunanlar) >= azami:
                        break
    except Exception as e:
        log.debug("Canlı kardeş haber arama hatası: %s", e)
    return bulunanlar


def _kaynak_adi_linkten(link: str) -> str:
    m = re.search(r"https?://(?:www\.)?([^/:]+)", link or "")
    if not m:
        return "Basın Kaynağı"
    alan = m.group(1).lower()
    harita = {
        "emlakkulisi.com": "Emlakkulisi", "trthaber.com": "TRT Haber", "aa.com.tr": "Anadolu Ajansı",
        "ekonomim.com": "Ekonomim", "dunya.com": "Dünya", "haberturk.com": "Habertürk",
        "bloomberght.com": "Bloomberg HT", "cnnturk.com": "CNN Türk", "milliyet.com.tr": "Milliyet",
        "sabah.com.tr": "Sabah", "ntv.com.tr": "NTV", "hurriyet.com.tr": "Hürriyet",
    }
    for k, v in harita.items():
        if k in alan:
            return v
    return alan.split(".")[0].capitalize()


def _haber_gorseli_alternatifi(
    haber: Dict[str, Any],
    con=None,
    sira: int = 0,
) -> Tuple[Optional[Image.Image], Optional[str]]:
    """'Başka fotoğraf' ve basın görseli katmanı için kardeş haber / alternatif basın fotoğrafı."""
    from .. import fetch_article, gorsel_kalite
    ana_link = str(haber.get("orijinal_url") or haber.get("link") or haber.get("url") or "").strip()
    baslik = haber.get("orijinal_baslik") or haber.get("baslik") or haber.get("manset") or ""

    aday_linkler: List[str] = []
    for l in kardes_linkler(con, haber, azami=5):
        if l != ana_link and l not in aday_linkler:
            aday_linkler.append(l)
    for l in canli_kardes_linkler(baslik, haric_link=ana_link, azami=5):
        if l != ana_link and l not in aday_linkler:
            aday_linkler.append(l)

    # Kardeş haberlerden sira'dan başlayarak kaliteli HD basın görseli dene
    for link in aday_linkler[max(0, sira):]:
        try:
            url = fetch_article.og_gorseli_cek(link) or ((fetch_article.tum_gorselleri_cek(link) or [None])[0])
            if url:
                foto = stok._foto_indir_veya_ac(url)
                if foto:
                    kaliteli, _ = gorsel_kalite.gorsel_kalite_denetle(foto)
                    if kaliteli:
                        return gorsel_kalite.kristal_netlestir(foto), _kaynak_adi_linkten(link)
        except Exception as e:
            log.debug("Kardeş görsel çekilemedi (%s): %s", link, e)

    # Haberin kendi sayfasındaki diğer gövde fotoğrafları (og:image dışındakiler)
    if ana_link.startswith("http"):
        try:
            tum = fetch_article.tum_gorselleri_cek(ana_link) or []
            for url in tum[1 + max(0, sira):]:
                foto = stok._foto_indir_veya_ac(url)
                if foto:
                    kaliteli, _ = gorsel_kalite.gorsel_kalite_denetle(foto)
                    if kaliteli:
                        return gorsel_kalite.kristal_netlestir(foto), None
        except Exception as e:
            log.debug("Ana sayfa alternatif görsel hatası: %s", e)
    return None, None
