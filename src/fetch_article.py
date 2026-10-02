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
    parcalar = []
    for eleman in oge.find_all(["p", "h2", "h3", "h4", "li"]):
        txt = eleman.get_text(" ", strip=True)
        if len(txt) > 25:
            parcalar.append(txt)
    return " ".join(parcalar)


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


from . import filtre


def _kucult(metin: str) -> str:
    """Türkçe İ ve I harflerini gözeterek küçültür."""
    return filtre.kucult(metin)


TURKCE_STOPWORDS = {
    "bir", "ve", "ile", "bu", "da", "de", "ne", "en", "icin", "için",
    "gibi", "daha", "kadar", "sonra", "once", "önce", "cok", "çok",
    "var", "yok", "her", "ise", "olan", "olarak", "diye", "son", "yeni",
    "ancak", "ayrıca", "ayrica", "bazi", "bazı", "tum", "tüm", "bunu",
    "buna", "bunun", "yada", "veya",
}


def _turkce_kok(kelime: str) -> str:
    """Türkçe kelimelerin yaygın çekim ve yapım eklerini temizleyerek kök/gövde tahmin eder."""
    k = _kucult(kelime)
    for ek in (
        "lerinden", "larindan", "lerinden", "larından",
        "lerinin", "larinin", "lerinin", "larının",
        "lerine", "larina", "lerine", "larına",
        "lerini", "larini", "lerini", "larını",
        "lerde", "larda", "lerden", "lardan",
        "leriyle", "lariyla", "leriyle", "larıyla",
        "sinden", "sindan", "sunden", "sundan",
        "sinde", "sinda", "sunde", "sunda",
        "sine", "sina", "sune", "suna",
        "sini", "sini", "sunu", "sünü",
        "inden", "indan", "unden", "undan",
        "lerin", "larin", "lerin", "ların",
        "nin", "nın", "nün", "nun",
        "den", "dan", "ten", "tan",
        "de", "da", "te", "ta",
        "ye", "ya", "yi", "yı", "yu", "yü",
        "in", "ın", "ün", "un",
        "e", "a", "i", "ı", "u", "ü",
        "ler", "lar", "lik", "lık", "luk", "lük",
        "siz", "sız", "suz", "süz",
        "yor", "di", "dı", "du", "dü", "ti", "tı", "tu", "tü",
        "miş", "mış", "muş", "müş", "ecek", "acak",
    ):
        if len(k) - len(ek) >= 3 and k.endswith(ek):
            k = k[:-len(ek)]
            break
    return k


def _baslikla_ilgili_mi(metin: str, baslik: str) -> bool:
    """
    Çektiğimiz metin gerçekten BU haberin metni mi?
    Ölçüt: başlıktaki anlamlı kelimelerin en az üçte biri metinde geçmeli.
    Türkçe eklemeli yapıyı (örn. 'motorine' -> 'motorin') ve 3 harfli kritik
    kelimeleri ('zam', 'ev', 'kat', 'arsa', 'kira') destekler.
    """
    if not baslik:
        return True

    govde = _kucult(metin)
    ham_kelimeler = re.findall(r"\w+", _kucult(baslik))
    kelimeler = [k for k in ham_kelimeler if len(k) >= 3 and k not in TURKCE_STOPWORDS]
    if len(kelimeler) < 2:
        return True

    govde_kelimeleri = set(re.findall(r"\w+", govde))
    govde_kokleri = {_turkce_kok(w) for w in govde_kelimeleri}

    eslesen = 0
    for k in kelimeler:
        kok = _turkce_kok(k)
        if (
            k in govde_kelimeleri
            or kok in govde_kelimeleri
            or kok in govde_kokleri
            or any(gw.startswith(kok) for gw in govde_kelimeleri if len(kok) >= 4)
            or any(k.startswith(gw) for gw in govde_kelimeleri if len(gw) >= 4)
        ):
            eslesen += 1

    return eslesen >= max(2, len(kelimeler) // 3)


def _capadan_topla(soup: BeautifulSoup, baslik: Optional[str] = None) -> Optional[str]:
    """
    Haberin kendi başlığını (h1/h2) çapa alıp gövdeyi bulur.
    _paragraflardan_topla yöntemi sayfanın altındaki yasal uyarı/feragatnameyi
    seçip alaka kapısından elendiğinde, bu yöntem başlığın hemen ardından gelen
    paragrafları toplayarak gövdeyi kurtarır.
    """
    h1 = soup.find(["h1", "h2"])
    if h1 is None:
        return None

    for p in h1.find_all_next("p"):
        metin_p = p.get_text(" ", strip=True)
        if len(metin_p) < 35:
            continue
        kutu = p.parent
        if kutu is None:
            return None
        metin = _paragraf_metni(kutu)
        if len(metin) < ASGARI_UZUNLUK and kutu.parent is not None:
            ustu = _paragraf_metni(kutu.parent)
            if len(ustu) > len(metin):
                metin = ustu
        return metin.strip() if len(metin) >= ASGARI_UZUNLUK else None
    return None


_KUYRUK_KESIN = re.compile(
    r"(sayfada yer alan bilgiler tavsiye niteli[gğ]i ta[sş][ıi]may[ıi]p"
    r"|yat[ıi]r[ıi]m dan[ıi][sş]manl[ıi][gğ][ıi] kapsam[ıi]nda de[gğ]ildir"
    r"|\bt[uü]m yorumlar\b|\byorum yaz\b|\bokur yorumlar[ıi]\b"
    r"|izinsiz ve kaynak g[oö]sterilmeden)",
    re.IGNORECASE,
)

_KUYRUK_ZAYIF = re.compile(
    r"(ilgili haberler|di[gğ]er haberler|bunlar da ilgin"
    r"|bizi takip edin|abone ol)",
    re.IGNORECASE,
)

_KUYRUK_ASGARI_KALAN = 300


def kuyrugu_kes(metin: str | None) -> str:
    """
    Gövdenin sonundaki okur yorumu / sayfa altı şablonunu ve yasal uyarıları atar.
    İki kademeli: kesin işaretler her yerde, zayıf işaretler yalnızca
    metnin son yarısında kesiyor.
    """
    m = (metin or "").strip()
    if len(m) < 400:
        return m

    adaylar = []
    e = _KUYRUK_KESIN.search(m)
    if e:
        adaylar.append(e)
    esik = int(len(m) * 0.55)
    for z in _KUYRUK_ZAYIF.finditer(m):
        if z.start() >= esik:
            adaylar.append(z)
            break
    if not adaylar:
        return m

    eslesme = min(adaylar, key=lambda x: x.start())
    kesilen = m[: eslesme.start()].strip()
    if len(kesilen) < _KUYRUK_ASGARI_KALAN:
        return m
    if len(m) - len(kesilen) > 50:
        log.info("gövde kuyruğu kesildi: %d karakter atıldı (%r)",
                 len(m) - len(kesilen), eslesme.group(0)[:40])
    return kesilen


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

    for uretici in (_jsonld_articlebody, _paragraflardan_topla, _capadan_topla):
        try:
            aday = uretici(soup)
            if aday and len(aday) >= ASGARI_UZUNLUK:
                if baslik and not _baslikla_ilgili_mi(aday, baslik):
                    continue
                # Okur yorumu ve sayfa altı şablonlarını temizle
                aday = kuyrugu_kes(aday)
                if len(aday) < ASGARI_UZUNLUK:
                    continue
                # Fazla boşlukları temizle ve sınırla
                temiz = re.sub(r"\s+", " ", aday).strip()
                return temiz[:AZAMI_UZUNLUK]
        except Exception as e:
            log.debug("Gövde çıkarıcı hatası: %s", e)

    return None


YASAK_DESENLER = [
    "avatar", "author", "yazar", "logo", "banner_ad", "pixel",
    "tracker", "tracking", "spacer", "placeholder", "icon", ".svg", ".gif",
    "share-button", "default_image", "no-image", "-150x150", "-300x",
    "-thumb", "small_thumb", "widget", "advert/documents", "ilan.memurlar",
    "kamuilan", "documents", "tablo", "dilekce", "ahaber2.png", "logo-text",
    "/site/v2/i/", "channel_logo", "site_logo", "doubleclick", "googleads",
    "analytics", "facebook.com/tr"
]


def _gecerli_url_mi(u: str) -> bool:
    if not u or not isinstance(u, str):
        return False
    u_low = u.lower()
    if any(p in u_low for p in YASAK_DESENLER):
        return False
    return u.startswith("http://") or u.startswith("https://") or u.startswith("//")


def _temiz_url(u: str) -> str:
    """Thumbnail veya küçük boyut parametreli URL'leri orijinal tam boy HD görsele dönüştürür."""
    u = u.strip()
    if u.startswith("//"):
        u = "https:" + u
    if "donanimhaber.com" in u and "path=" in u:
        m = re.search(r"path=(https?://[^\&]+)", u)
        if m:
            u = m.group(1)
        u = re.sub(r"\d+x\d+_", "", u)
    # Anadolu Ajansı (AA) thumbs_ öneklerini kaldırarak ham 5K/4K görsele ulaş
    if "aa.com.tr" in u and "thumbs_" in u:
        u = re.sub(r"thumbs_[a-z0-9_]+_", "", u)
    # NTV / Milliyet / Hürriyet / Sözcü / Habertürk küçültme parametrelerini kaldır
    if any(d in u for d in ("ntv.com.tr", "hurriyet.com.tr", "milliyet.com.tr", "sozcu.com.tr", "haberturk.com")) and "?" in u:
        u = u.split("?")[0]
    # TRT boyut kalıplarını temizle / 1920x1080'e yükselt
    if "trt.com.tr" in u or "trthaber" in u:
        u = re.sub(r"_(?:640x360|800x450|1280x720)", "_1920x1080", u)
    # WordPress vb. thumbnail uzantılarını orijinaline çevir (örn: resim-300x200.jpg -> resim.jpg)
    u = re.sub(r"-\d{3,4}x\d{3,4}(\.[a-zA-Z]{3,4})$", r"\1", u)
    return u


def hd_gorsel_url_coz(url_veya_link: str) -> Optional[str]:
    """Herhangi bir görsel veya makale URL'sinden doğrudan en yüksek çözünürlüklü temiz görseli döner."""
    if not url_veya_link:
        return None
    u = url_veya_link.strip()
    if any(u.lower().endswith(uz) for uz in (".jpg", ".jpeg", ".png", ".webp")):
        return _temiz_url(u)
    return og_gorseli_cek(u)


def olay_baglami_cek(baslik: str, zaman_asimi: int = 10) -> Optional[str]:
    """Haber başlığından kritik arama veya görsel bağlamını çıkarır."""
    if not baslik:
        return None
    ham_kelimeler = re.findall(r"\w+", baslik)
    anlamlilar = [k for k in ham_kelimeler if len(k) >= 3 and _kucult(k) not in TURKCE_STOPWORDS]
    return " ".join(anlamlilar[:6]) if anlamlilar else None


def og_gorseli_cek(link: str, zaman_asimi: int = 15) -> Optional[str]:
    """
    Haber sayfasından en kaliteli görsel URL'ini döner:
    1. og:image / twitter:image
    2. schema.org JSON-LD 'image' alanı
    3. figure/article içi öne çıkan görsel
    Thumbnail ve küçültme parametrelerini otomatik temizler, HD orijinaline ulaşır.
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
            if _gecerli_url_mi(u):
                tam_u = urllib.parse.urljoin(link, u)
                return _temiz_url(tam_u)

    # 2. JSON-LD Image
    for etiket in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not etiket.string:
            continue
        try:
            veri = json.loads(etiket.string)
            adaylar = veri.get("@graph") if isinstance(veri, dict) and "@graph" in veri else ([veri] if isinstance(veri, dict) else veri)
            for aday in (adaylar or []):
                if not isinstance(aday, dict):
                    continue
                tip = str(aday.get("@type", "")).lower()
                if tip in ("organization", "newsmediaorganization", "website", "person"):
                    continue
                img = aday.get("image")
                if isinstance(img, str) and _gecerli_url_mi(img):
                    return _temiz_url(urllib.parse.urljoin(link, img))
                elif isinstance(img, dict) and img.get("url") and _gecerli_url_mi(img["url"]):
                    return _temiz_url(urllib.parse.urljoin(link, img["url"]))
                elif isinstance(img, list) and len(img) > 0:
                    for eleman in img:
                        if isinstance(eleman, str) and _gecerli_url_mi(eleman):
                            return _temiz_url(urllib.parse.urljoin(link, eleman))
        except Exception:
            continue

    # 3. Makale içi görsel
    for secici in ("article img", ".post-content img", ".entry-content img", "figure img", "main figure img"):
        img = soup.select_one(secici)
        if img:
            src = img.get("src") or img.get("data-src") or ""
            if _gecerli_url_mi(src):
                return _temiz_url(urllib.parse.urljoin(link, src))

    return None


def tum_gorselleri_cek(link: str, zaman_asimi: int = 15) -> List[str]:
    """
    Haber sayfasındaki tüm geçerli içerik görsellerini sıralı ve tekil liste olarak döner.
    Web sitesi makalesi ve alternatif slayt görselleri için kullanılır.
    Reklam, sayaç, 1x1 piksel ve ikonları eler.
    """
    resp = _sayfayi_getir(link, zaman_asimi)
    if resp is None:
        return []

    try:
        soup = BeautifulSoup(resp.content, "html.parser")
    except Exception:
        return []

    gorseller: List[str] = []
    gorulen: set[str] = set()

    def _ekle(raw_url: str):
        if not raw_url or not _gecerli_url_mi(raw_url):
            return
        u = _temiz_url(urllib.parse.urljoin(link, raw_url.strip()))
        if u not in gorulen:
            gorulen.add(u)
            gorseller.append(u)

    # 1. OpenGraph / Twitter meta
    for ozellik in ("og:image", "twitter:image", "twitter:image:src"):
        meta = soup.find("meta", property=ozellik) or soup.find("meta", attrs={"name": ozellik})
        if meta and meta.get("content"):
            _ekle(meta["content"])

    # 2. JSON-LD Images
    for etiket in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not etiket.string:
            continue
        try:
            veri = json.loads(etiket.string)
            if isinstance(veri, dict):
                g = veri.get("image")
                if isinstance(g, str):
                    _ekle(g)
                elif isinstance(g, dict) and g.get("url"):
                    _ekle(g["url"])
                elif isinstance(g, list):
                    for item in g:
                        if isinstance(item, str):
                            _ekle(item)
                        elif isinstance(item, dict) and item.get("url"):
                            _ekle(item["url"])
        except Exception:
            continue

    # 3. Makale içi img etiketleri
    for secici in ("article img", ".content img", ".post-content img", ".entry-content img", "figure img", "main img"):
        for img in soup.select(secici):
            src = img.get("src") or img.get("data-src") or img.get("data-original")
            if src:
                _ekle(src)

    return gorseller
