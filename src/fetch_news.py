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
    t = baslik.replace("I", "ı").replace("İ", "i").lower()
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


# ----------------------------------------------------------------------
# Instabot Paritesi: Bozuk Bayt Onarımı, TRT Haber & SEO Elemesi
# ----------------------------------------------------------------------

TRT_TABAN = "https://www.trthaber.com/"

SEO_VE_COP_DESENLERI = [
    r"^rüyada",
    r"ne anlama gelir",
    r"falda.*görmek",
    r"burç.*yorum",
    r"şifremi unuttum",
    r"kim elendi",
    r"kim kazandı",
    r"sınav sonuçları",
    r"hava durumu",
    r"namaz vakti",
    r"dizi.*fragman",
    r"reyting sonuçları",
    r"canlı maç",
    r"hangi kanalda",
    r"altın fiyatları.*son durum",
    r"dolar kaç tl",
    r"euro kaç tl",
    r"borsa.*günü.*tamamladı",
    r"hisse senedi",
    r"kripto",
    r"bitcoin",
]


def baslik_elenmeli(baslik: str) -> Optional[str]:
    """Başlık SEO çöpü veya konu dışı magazin/asayiş mi? Eşleşen deseni döner."""
    if not baslik:
        return "boş başlık"
    for desen in SEO_VE_COP_DESENLERI:
        try:
            if re.search(desen, baslik, re.IGNORECASE):
                return desen
        except re.error:
            continue
    return None


def _bozuk_baytlari_onar(xml_bytes: bytes) -> bytes:
    """
    Bazı siteler feed'ini UTF-8 ilan edip geçersiz baytlar içerir.
    Bozuk baytları değiştirip XML'in tamamının çökmesini engeller.
    """
    kodlama = "utf-8"
    eslesme = re.search(rb"""encoding=["']([\w-]+)["']""", xml_bytes[:200])
    if eslesme:
        kodlama = eslesme.group(1).decode("ascii", errors="replace")

    try:
        metin = xml_bytes.decode(kodlama, errors="replace")
    except LookupError:
        metin = xml_bytes.decode("utf-8", errors="replace")

    metin = re.sub(r"""encoding=["'][\w-]+["']""", 'encoding="utf-8"', metin, count=1)
    return metin.encode("utf-8")


def _trt_ayristir(girdiler) -> List[Dict[str, Any]]:
    """TRT'nin xml_mobile beslemesini ayrıştırır ve göreli linkleri tam linke dönüştürür."""
    sonuc = []
    for g in girdiler:
        baslik_elem = g.find("haber_manset") or g.find("title")
        baslik = baslik_elem.text.strip() if (baslik_elem is not None and baslik_elem.text) else ""
        link_elem = g.find("haber_link") or g.find("link")
        link = link_elem.text.strip() if (link_elem is not None and link_elem.text) else ""
        if not baslik or not link:
            continue
        if not link.startswith("http"):
            link = TRT_TABAN + link.lstrip("/")
        
        ozet_elem = g.find("haber_aciklama") or g.find("description")
        ozet = ""
        if ozet_elem is not None and ozet_elem.text:
            ozet = BeautifulSoup(ozet_elem.text, "html.parser").get_text().strip()

        tarih_elem = g.find("haber_tarihi") or g.find("pubDate")
        tarih_str = _tarih_coz(tarih_elem.text if (tarih_elem is not None and tarih_elem.text) else "")

        sonuc.append({
            "baslik": " ".join(baslik.split()),
            "url": link,
            "ozet": ozet,
            "yayin_tarihi": tarih_str,
        })
    return sonuc


def _besle_ayristir(icerik: bytes) -> BeautifulSoup:
    """RSS/Atom beslemesini ayrıştırır; bozuk bayt onarımı ve lxml fallback içerir."""
    try:
        return BeautifulSoup(icerik, "xml")
    except Exception:
        pass
    try:
        onarılan = _bozuk_baytlari_onar(icerik)
        return BeautifulSoup(onarılan, "xml")
    except Exception as e:
        log.warning("XML ayrıştırıcı kullanılamadı (%s); html.parser'a düşülüyor", e)
        return BeautifulSoup(icerik, "html.parser")


def feed_ayristir(icerik: bytes) -> List[Dict[str, Any]]:
    """Ham baytları standart haber sözlüğü listesine çevirir (TRT, RSS 2.0 ve Atom uyumlu)."""
    soup = _besle_ayristir(icerik)
    
    # TRT mobil XML formatı kontrolü
    trt_haberler = soup.find_all("haber")
    if trt_haberler and soup.find("haberler"):
        return _trt_ayristir(trt_haberler)

    items = soup.find_all("item")
    if not items:
        items = soup.find_all("entry")

    sonuc = []
    for item in items:
        link_elem = item.find("link")
        haber_url = ""
        if link_elem:
            haber_url = link_elem.text.strip() if link_elem.text else link_elem.get("href", "")
        
        baslik_elem = item.find("title")
        baslik = baslik_elem.text.strip() if baslik_elem else ""

        ozet_elem = item.find("description") or item.find("summary")
        ozet = ""
        if ozet_elem:
            ozet = BeautifulSoup(ozet_elem.text, "html.parser").get_text().strip()

        tarih_elem = item.find("pubDate") or item.find("published") or item.find("updated")
        tarih_str = _tarih_coz(tarih_elem.text if tarih_elem else "")

        if baslik and haber_url:
            sonuc.append({
                "baslik": baslik,
                "url": haber_url,
                "ozet": ozet,
                "yayin_tarihi": tarih_str,
            })
    return sonuc


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

            ogeler = feed_ayristir(resp.content)
            for oge in ogeler:
                haber_url = oge.get("url", "")
                if not haber_url or db.haber_ekle_mi(haber_url):
                    continue

                baslik = oge.get("baslik", "").strip()
                ozet = oge.get("ozet", "").strip()
                tarih_str = oge.get("yayin_tarihi") or datetime.now(timezone.utc).isoformat()

                # 1. SEO çöpü ve konu dışı elemesi
                cop_nedeni = baslik_elenmeli(baslik)
                if cop_nedeni:
                    log.debug("SEO/Çöp başlık elendi (%s): %s", cop_nedeni, baslik[:60])
                    continue

                # 2. Yaş kontrolü
                if _saat_farki_saat(tarih_str) > max_yas_saat:
                    continue

                # 3. Değerlendirme: reklamı ve konu dışını ele, sütuna oturt, puanla
                degerlendirme = haber_puanlama.degerlendir(baslik, ozet, _saat_farki_saat(tarih_str))
                if not degerlendirme.gecti:
                    log.debug("Elendi (%s): %s", degerlendirme.red_sebebi, baslik[:60])
                    continue

                if _yakin_kopya_mi(baslik, gorulen_basliklar):
                    log.debug("Yakın kopya atlandı: %s", baslik[:60])
                    continue

                # 4. Derinlik: Haberin tam metnini ve yüksek kaliteli kapak görselini çek
                makale_metni = fetch_article.makale_metni_cek(haber_url, baslik)
                gorsel_url = fetch_article.og_gorseli_cek(haber_url) or _og_gorsel_cek(haber_url)

                # Tam metinle yeniden puanla — başlık yanıltıcı olabiliyor
                if makale_metni:
                    tam = haber_puanlama.degerlendir(baslik, makale_metni, _saat_farki_saat(tarih_str))
                    if tam.gecti:
                        degerlendirme = tam
                    else:
                        log.debug("Tam metinle elendi (%s): %s", tam.red_sebebi, baslik[:60])
                        continue

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
