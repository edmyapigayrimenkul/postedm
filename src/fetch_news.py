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

from . import config, db, fetch_article, haber_puanlama

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


def _baslik_anahtari(baslik: str) -> str:
    """Yakın kopyaları yakalamak için başlığı normalleştirir.

    Emlak kaynakları aynı haberi güncelleyerek yeniden yayımlıyor:
    "TOKİ kiralık konut başvuruları 2 gün sonra başlıyor" ve
    "... 3 gün sonra başlıyor" ayrı kayıtlar olarak giriyordu.
    """
    t = baslik.lower()
    t = re.sub(r"\d+", "#", t)                      # sayılar normalleşir
    t = re.sub(r"[^a-zçğıöşü#\s]", " ", t)
    kelimeler = [k for k in t.split() if len(k) > 2]
    return " ".join(sorted(set(kelimeler))[:12])


def _yakin_kopya_mi(baslik: str, gorulenler: set) -> bool:
    anahtar = _baslik_anahtari(baslik)
    if anahtar in gorulenler:
        return True
    gorulenler.add(anahtar)
    return False


def _og_gorsel_cek(url: str) -> Optional[str]:
    """Haber sayfasından og:image meta etiketini okur (yedek yöntem)."""
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


def _besle_ayristir(icerik: bytes) -> BeautifulSoup:
    """RSS/Atom beslemesini ayrıştırır; lxml yoksa yerleşik ayrıştırıcıya düşer.

    `BeautifulSoup(..., "xml")` lxml gerektiriyor ve lxml requirements.txt'te
    yoktu. Yerelde kurulu olduğu için fark edilmedi; GitHub Actions'ta 8 Eylül'den
    beri HER kaynak "Couldn't find a tree builder" hatasıyla düşüyordu ve haber
    akışı üretimde hiç çalışmamıştı.

    lxml artık bağımlılıklarda, ama tek bir eksik paketin tüm haber akışını
    sessizce durdurmasına bir daha izin vermemek için yedek yol da bırakıldı.
    """
    try:
        return BeautifulSoup(icerik, "xml")
    except Exception as e:
        log.warning("XML ayrıştırıcı kullanılamadı (%s); html.parser'a düşülüyor", e)
        return BeautifulSoup(icerik, "html.parser")


def rss_tara() -> List[Dict[str, Any]]:
    """Tüm yapılandırılmış RSS kaynaklarını tarar, yeni ve alakalı haberleri kaydeder."""
    kaynaklar = config.ayar_al("haberler.kaynaklar", [])
    max_yas_saat = config.ayar_al("haberler.haber_yasi_saat", 36)
    bulunan_haberler = []
    gorulen_basliklar: set = set()   # kaynaklar arası yakın kopya denetimi

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

            soup = _besle_ayristir(resp.content)
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

                # Değerlendirme: reklamı ve konu dışını ele, sütuna oturt, puanla
                degerlendirme = haber_puanlama.degerlendir(baslik, ozet, _saat_farki_saat(tarih_str))
                if not degerlendirme.gecti:
                    log.debug("Elendi (%s): %s", degerlendirme.red_sebebi, baslik[:60])
                    continue

                if _yakin_kopya_mi(baslik, gorulen_basliklar):
                    log.debug("Yakın kopya atlandı: %s", baslik[:60])
                    continue

                # Derinlik: Haberin tam metnini ve yüksek kaliteli kapak görselini çek
                makale_metni = fetch_article.makale_metni_cek(haber_url, baslik)
                gorsel_url = fetch_article.og_gorseli_cek(haber_url) or _og_gorsel_cek(haber_url)

                # Tam metinle yeniden puanla — başlık yanıltıcı olabiliyor
                if makale_metni:
                    tam = haber_puanlama.degerlendir(baslik, makale_metni, _saat_farki_saat(tarih_str))
                    if tam.gecti:
                        degerlendirme = tam

                # Kaynak ağırlığı puana EKLENMİYOR; yalnızca eşitlik bozucu.
                # Eski formül (agirlik + sinyal) kaynağın prestijini içeriğin
                # önüne geçiriyordu: aynı Yargıtay kararı AA'dan geçip
                # Hürriyet'ten eleniyordu.
                onem_puani = degerlendirme.puan
                sutun = degerlendirme.sutun
                rehber_mi = degerlendirme.rehber_mi

                haber_id = db.haber_kaydet(
                    kaynak=ad,
                    orijinal_baslik=baslik,
                    orijinal_url=haber_url,
                    orijinal_ozet=ozet,
                    makale_metni=makale_metni or "",
                    yayin_tarihi=tarih_str,
                    kategori=("rehber" if rehber_mi else (sutun or "emlak")),
                    onem_puani=onem_puani,
                )

                if gorsel_url and haber_id:
                    db.haber_guncelle(haber_id, gorsel_url=gorsel_url)

                log.info("Bulundu [ID %d | %s | %s]: %s",
                         haber_id, degerlendirme.ozet(),
                         "konu adayı" if rehber_mi else "haber", baslik[:50])
                bulunan_haberler.append({
                    "id": haber_id,
                    "baslik": baslik,
                    "kaynak": ad,
                    "url": haber_url,
                    "onem_puani": onem_puani,
                    "gorsel_url": gorsel_url,
                    "sutun": sutun,
                    "rehber_mi": rehber_mi,
                })


        except Exception as e:
            log.error("RSS kaynağı taranırken hata (%s): %s", url, e)

    return bulunan_haberler
