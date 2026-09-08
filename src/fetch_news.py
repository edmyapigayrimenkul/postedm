"""
fetch_news.py — Emlak ve Gayrimenkul RSS Kaynakları Okuyucusu
Sektör, ekonomi ve yerel emlak haberlerini çeker, anahtar kelimelere göre süzer ve kaydeder.
"""

from __future__ import annotations

import email.utils
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import urllib.parse

import requests
from bs4 import BeautifulSoup

from . import config, db

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


def _saat_farki_saat(yayin_tarihi_str: str) -> float:
    """Yayın tarihi ile şimdiki zaman arasındaki farkı saat cinsinden döner."""
    try:
        dt = datetime.fromisoformat(yayin_tarihi_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
    except Exception:
        return 0.0


def _tarih_coz(tarih_metni: str) -> str:
    """RFC-822 veya ISO tarihini UTC ISO-8601'e çevirir."""
    if not tarih_metni:
        return datetime.now(timezone.utc).isoformat()
    try:
        zaman_tup = email.utils.parsedate_tz(tarih_metni)
        if zaman_tup:
            ts = email.utils.mktime_tz(zaman_tup)
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except Exception:
        pass
    try:
        return datetime.fromisoformat(tarih_metni).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def _emlak_alakali_mi(baslik: str, ozet: str) -> bool:
    """Haberin emlak, konut, arsa, tapu, imar veya Trakya ile ilgili olup olmadığını inceler."""
    metin = f"{baslik} {ozet}".lower()
    anahtarlar = config.ayar_al("haberler.anahtar_kelimeler", [])
    for k in anahtarlar:
        k_lower = k.lower().strip()
        # Kelime sınırı ile ara (örn: 'kira' kelimesi 'tahliye' içinde yanlış eşleşmesin)
        desen = r'(?:\b|_)' + re.escape(k_lower) + r'(?:\b|_)'
        if re.search(desen, metin):
            return True
    return False


def _og_gorsel_cek(url: str) -> Optional[str]:
    """Haber sayfasından og:image meta etiketini okur."""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=8)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            og = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"})
            if og and og.get("content"):
                return urllib.parse.urljoin(url, og["content"].strip())
    except Exception as e:
        log.debug("og:image alınamadı (%s): %s", url, e)
    return None


def rss_tara() -> List[Dict[str, Any]]:
    """Tüm yapılandırılmış RSS kaynaklarını tarar, yeni ve alakalı haberleri kaydeder."""
    kaynaklar = config.ayar_al("haberler.kaynaklar", [])
    max_yas_saat = config.ayar_al("haberler.haber_yasi_saat", 36)
    bulunan_haberler = []

    for kaynak in kaynaklar:
        ad = kaynak.get("ad", "Bilinmeyen Kaynak")
        url = kaynak.get("url")
        agirlik = kaynak.get("agirlik", 5)

        if not url:
            continue

        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
            if resp.status_code != 200:
                log.warning("RSS okunamadı [%d]: %s", resp.status_code, url)
                continue

            soup = BeautifulSoup(resp.content, "xml")
            items = soup.find_all("item")
            if not items:
                items = soup.find_all("entry")

            for item in items:
                link_elem = item.find("link")
                haber_url = ""
                if link_elem:
                    haber_url = link_elem.text.strip() if link_elem.text else link_elem.get("href", "")
                
                if not haber_url or db.haber_ekle_mi(haber_url):
                    continue

                baslik_elem = item.find("title")
                baslik = baslik_elem.text.strip() if baslik_elem else ""

                ozet_elem = item.find("description") or item.find("summary")
                ozet = ""
                if ozet_elem:
                    ozet = BeautifulSoup(ozet_elem.text, "html.parser").get_text().strip()

                tarih_elem = item.find("pubDate") or item.find("published") or item.find("updated")
                tarih_str = _tarih_coz(tarih_elem.text if tarih_elem else "")

                # Yaş kontrolü
                if _saat_farki_saat(tarih_str) > max_yas_saat:
                    continue

                # Emlak / Gayrimenkul ilgi kontrolü
                if not _emlak_alakali_mi(baslik, ozet):
                    continue

                # og:image çek
                gorsel_url = _og_gorsel_cek(haber_url)

                # Temel önem puanı hesapla
                onem_puani = agirlik
                if any(x in baslik.lower() for x in ["silivri", "trakya", "arsa", "tarla", "tapu"]):
                    onem_puani += 2

                haber_id = db.haber_kaydet(
                    kaynak=ad,
                    orijinal_baslik=baslik,
                    orijinal_url=haber_url,
                    orijinal_ozet=ozet,
                    yayin_tarihi=tarih_str,
                    kategori="emlak",
                    onem_puani=onem_puani,
                )

                if gorsel_url and haber_id:
                    db.haber_guncelle(haber_id, gorsel_url=gorsel_url)

                log.info("Yeni emlak haberi bulundu [ID %d]: %s", haber_id, baslik[:50])
                bulunan_haberler.append({
                    "id": haber_id,
                    "baslik": baslik,
                    "kaynak": ad,
                    "url": haber_url,
                    "onem_puani": onem_puani,
                    "gorsel_url": gorsel_url,
                })

        except Exception as e:
            log.error("RSS kaynağı taranırken hata (%s): %s", url, e)

    return bulunan_haberler
