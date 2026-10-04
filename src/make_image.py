"""
make_image.py — EDM Marka Paftası Görsel Motoru (V2 - Ultra Premium & Kanca Etkisi)
Pillow ile 1080x1350 (4:5 dikey) formatında kurumsal kimlik standartlarına
tam uyumlu, yüksek dönüşümlü Haber ve İlan slaytları üretir.
"""

from __future__ import annotations

import functools
import inspect
import io
import json
import logging
import math
import os
import re
import textwrap
import time
import unicodedata
from pathlib import Path
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Tuple

import qrcode
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from . import config, db, fetch_listings, filtre, upload_image

log = logging.getLogger(__name__)

# Tuval boyutları (Instagram & Threads 4:5 Dikey Oranı)
GENISLIK = 1080
YUKSEKLIK = 1350

# Renk Paleti (EDM Marka Rehberi & Web Sitesi)
RENK_KIRMIZI = (240, 0, 13)       # #f0000d (İmza EDM Kırmızısı)
RENK_KIRMIZI_DERIN = (196, 3, 15) # #c4030f
RENK_MUREKKEP = (18, 19, 22)      # #121316 (Derin Mürekkep Siyahı)
RENK_MUREKKEP_2 = (26, 28, 33)    # #1a1c21 (İkincil Koyu Zemin)
RENK_MUREKKEP_3 = (36, 39, 45)    # #24272d (Kutu Çerçeve Rengi)
RENK_KAGIT = (246, 246, 244)      # #f6f6f4 (Sıcak Pafta Kağıdı)
RENK_KAGIT_KUTU = (255, 255, 255) # #ffffff (Beyaz Kart)
RENK_KIREC = (228, 228, 225)      # #e4e4e1 (Açık Çerçeve & Kutu)
RENK_KURSUN = (138, 139, 143)     # #8a8b8f (Teknik Rölöve & Metadata)
RENK_KURSUN_ACIK = (218, 222, 230)# #dadee6 (Gövde Metinleri)
RENK_CIZGI = (214, 214, 211)      # #d6d6d3 (Kılavuz Çizgiler)
RENK_CIZGI_ACIK = (220, 220, 216) # #dededa (Açık Pafta Çizgisi)
RENK_CIZGI_KOYU = (45, 48, 56)    # Koyu zemin ayrım çizgisi
RENK_BEYAZ = (255, 255, 255)
RENK_YESIL = (34, 197, 94)        # Yeşil onay/savunma rengi
RENK_METIN_GOVDE = (245, 247, 250)    # Kristal netliğinde, yüksek kontrastlı gövde rengi
RENK_KIRMIZI_CANLI = (255, 59, 48)   # #ff3b30 (Koyu zeminde parlayan canlı mercan kırmızısı)
RENK_KIRMIZI_VURGU = (255, 45, 55)   # #ff2d37 (Manşetlerde difüzyon gölgesiyle parlayan kırmızı)
# Uzman notu kartı: eskiden amber (#eab308) — marka dışıydı. Çubuk kırmızı, etiket kireç.
RENK_UZMAN_CUBUK = RENK_KIRMIZI
RENK_UZMAN_ETIKET = (228, 228, 225)


# Doğrulanmış Türkçe Destekli Font Yolları
FONT_FRAUNCES = config.yol_al("assets/fonts/Fraunces.ttf")
# Gövde: IBM Plex Sans (2026-09-25; önceden Plus Jakarta Sans). Kurumsal kimliğin
# ve web sitesinin gövde fontu, rakamlardaki Plex Mono ile aynı aile; Türkçe
# gövde metninde daha açık ve okunaklı. Statik ağırlıklar tam glifli
# IBMPlexSans[wdth,wght].ttf'den üretildi — IBMPlexSans-Variable.ttf yalnızca
# Latin alt kümesi, ğ ş İ ₺ içermiyor.
FONT_SANS = config.yol_al("assets/fonts/IBMPlexSans-Medium.ttf")
FONT_SANS_REGULAR = config.yol_al("assets/fonts/IBMPlexSans-Regular.ttf")
FONT_SANS_MEDIUM = config.yol_al("assets/fonts/IBMPlexSans-Medium.ttf")
FONT_SANS_SEMIBOLD = config.yol_al("assets/fonts/IBMPlexSans-SemiBold.ttf")
FONT_SANS_BOLD = config.yol_al("assets/fonts/IBMPlexSans-Bold.ttf")
FONT_INTER_MEDIUM = config.yol_al("assets/fonts/Inter-Medium.ttf")
FONT_INTER_BOLD = config.yol_al("assets/fonts/Inter-Bold.ttf")
FONT_MONO = config.yol_al("assets/fonts/IBMPlexMono.ttf")
FONT_MONO_BOLD = config.yol_al("assets/fonts/IBMPlexMono-Bold.ttf")

# Logo ve Amblem Yolları
LOGO_AMBLEM = config.yol_al("assets/logos/amblem.png")
LOGO_YATAY = config.yol_al("assets/logos/logo-yatay.png")
LOGO_YATAY_ACIK = config.yol_al("assets/logos/logo-yatay-acik.png")
LOGO_YATAY_BEYAZ = config.yol_al("assets/logos/logo-yatay-beyaz.png")
LOGO_SLOGAN = config.yol_al("assets/logos/slogan.png")
LOGO_PIN = config.yol_al("assets/logos/pin-sembol.png")


class EksikIcerik(ValueError):
    """Formatın zorunlu alanı modelden gelmedi.

    Eskiden boş alan koddaki genel bir cümleyle doldurulurdu; #157'de ekspertiz
    konusuna "Yargıtay yerleşik içtihatları uyarınca…" diye sabit bir hüküm
    basıldı. Uydurmak yerine üretim durur.
    """


class TasmaHatasi(EksikIcerik):
    """Metin, okunabilir en küçük puntoda bile ayrılan alana sığmadı.

    Eskiden sığmayan metin kutunun altına girer (#243 sözlük: tanımın son iki
    satırı "Yatırımcı için önemi" kutusunun arkasında kaldı), tuvalden taşar
    (kapak manşeti) ya da sessizce kırpılırdı (kapak spotu 4 satırda kesiliyordu).
    Artık üretim durur; metin bütçesi (generate_text.BUTCE) bunu önlemeye çalışır.
    """


# ---------------------------------------------------------------------------
# Görsel metin süzgeci
# ---------------------------------------------------------------------------
# Kart fontlarında olmayan karakter kutu (□) olarak basılır ve taşma denetimi
# bunu görmez: kutu da yer kaplar. Model emoji üretebiliyor ("✅ Tapuyu kontrol
# edin"), panelden yapıştırılan metin görünmez karakter (U+200B) ya da satırı
# ters çeviren yön işareti (U+202E) taşıyabiliyor. IBM Plex Sans'a geçince hook
# etiketindeki "●" da kutuya dönmüştü. Süzgeç çizicinin GİRDİSİNİN KOPYASINA
# uygulanır: aynı verideki caption'ın emojisi yerinde kalır.
_GORSEL_KARSILIK = str.maketrans({
    "→": "–", "⇒": "–", "➔": "–", "➜": "–", "⟶": "–", "←": "–",
    "●": "•", "■": "•", "▪": "•", "◆": "•", "◾": "•", "◼": "•", "►": "•", "▶": "•",
})
_ORTAK_GLIFLER: Optional[frozenset] = None
# Yol ve adres metin değil: süzgeç "~" ya da çift boşluk taşıyan bir dosya yolunu bozardı
_METIN_OLMAYAN_ANAHTAR = ("yol", "url", "dosya", "foto", "gorsel", "resim", "link")


def _ortak_glifler() -> frozenset:
    """Kartlarda kullanılan bütün fontlarda bulunan karakterler.

    Birleşim değil kesişim: bir alan hangi fontla çizilecekse çizilsin kutu
    çıkmamalı (ör. "→" Plex Sans'ta var, Fraunces'ta yok).
    """
    global _ORTAK_GLIFLER
    if _ORTAK_GLIFLER is None:
        try:
            from fontTools.ttLib import TTFont
            kumeler = [set(TTFont(str(f), lazy=True).getBestCmap())
                       for f in (FONT_FRAUNCES, FONT_SANS_REGULAR, FONT_SANS_MEDIUM, FONT_SANS_SEMIBOLD,
                                 FONT_SANS_BOLD, FONT_MONO, FONT_MONO_BOLD) if Path(f).is_file()]
            _ORTAK_GLIFLER = frozenset(set.intersection(*kumeler)) if kumeler else frozenset()
        except Exception as e:
            log.warning("Font karakter haritası okunamadı, kaba süzgece düşüldü: %s", e)
            _ORTAK_GLIFLER = frozenset()
    return _ORTAK_GLIFLER


def gorsel_metni(metin: str) -> str:
    """Kartta kutu (□) basılacak karakterleri ayıklar; dokunulmayan metin aynen döner."""
    glifler = _ortak_glifler()
    aday = unicodedata.normalize("NFC", metin.translate(_GORSEL_KARSILIK))
    temiz = []
    for ch in aday:
        if ch == "\n":
            temiz.append(ch)
        elif ch.isspace():
            temiz.append(" ")
        elif unicodedata.category(ch)[0] == "C":
            continue  # görünmez biçim/denetim karakteri: U+200B, U+202E, U+FEFF…
        elif unicodedata.category(ch) == "Mn":
            # NFC'den sonra kalan birleştirici işaret sahipsizdir: Türkçe harflerin
            # hepsinin hazır biçimi var. "İ".lower() → "i̇" noktayı ikiler; U+202E
            # silinince arkasındaki U+0307 noktanın üstünde yüzüyordu.
            continue
        elif glifler and ord(ch) not in glifler:
            continue
        elif not glifler and (ord(ch) > 0xFFFF or unicodedata.category(ch) == "So"):
            continue
        else:
            temiz.append(ch)
    sonuc = "".join(temiz)
    if sonuc == metin:
        return metin
    # "✅ Tapu" → " Tapu": ayıklanan karakterin bıraktığı boşluk satırı kaydırmasın
    return "\n".join(re.sub(r" {2,}", " ", s).strip() for s in sonuc.split("\n"))


def gorsel_verisi_temizle(veri: Any, _anahtar: str = "") -> Any:
    """Çizicinin girdisinin, bütün metinleri süzülmüş KOPYASI."""
    if isinstance(veri, str):
        if any(p in _anahtar.lower() for p in _METIN_OLMAYAN_ANAHTAR) or veri.startswith(("/", "http://", "https://")):
            return veri
        return gorsel_metni(veri)
    if isinstance(veri, dict):
        return {a: gorsel_verisi_temizle(d, str(a)) for a, d in veri.items()}
    if isinstance(veri, (list, tuple)):
        return type(veri)(gorsel_verisi_temizle(d, _anahtar) for d in veri)
    return veri


def _gorsel_girdisi(fonk):
    """Çizim giriş noktasının ilk bağımsız değişkenini süzülmüş kopyayla değiştirir."""
    ad = next(iter(inspect.signature(fonk).parameters))

    @functools.wraps(fonk)
    def sar(*args, **kwargs):
        if args:
            args = (gorsel_verisi_temizle(args[0]),) + args[1:]
        elif ad in kwargs:
            kwargs[ad] = gorsel_verisi_temizle(kwargs[ad])
        return fonk(*args, **kwargs)
    return sar


def tr_buyuk(metin: str) -> str:
    """Türkçe büyük harf: str.upper() "Silivri"yi "SILIVRI" yapıyordu."""
    return (metin or "").replace("i", "İ").replace("ı", "I").upper()


def _kaynak_etiketi(haber: Dict[str, Any]) -> str:
    """Kaynak yoksa etiket de yok: eskiden "KAYNAK: SEKTÖREL BÜLTEN" basılıyordu —
    var olmayan bir kaynak iddiası."""
    kaynak = str(haber.get("kaynak") or "").strip()
    if not kaynak or kaynak.startswith("EDM"):
        return "EDM YAPI & GAYRİMENKUL"
    return f"KAYNAK: {tr_buyuk(kaynak)}"


def _etiketi_sigdir(metin: str, font: ImageFont.FreeTypeFont, azami: int, draw: ImageDraw.ImageDraw) -> str:
    """Tek satırlık META etiketi (kaynak, foto atfı) genişliğe sığdırır; gerekirse
    kelime sınırında "…" ile kısaltır. Yalnızca etiketler için — içerik asla kısaltılmaz."""
    if draw.textbbox((0, 0), metin, font=font)[2] <= azami:
        return metin
    kelimeler = metin.split()
    while kelimeler and draw.textbbox((0, 0), " ".join(kelimeler) + "…", font=font)[2] > azami:
        kelimeler.pop()
    return (" ".join(kelimeler) + "…") if kelimeler else ""


def tr_ilk_buyuk(metin: str) -> str:
    """İlk harfi Türkçe kurala göre büyütür: str.upper() "ilk"i "Ilk" yapıyordu."""
    if not metin:
        return metin
    ilk = metin[0]
    buyuk = {"i": "İ", "ı": "I"}.get(ilk, ilk.upper())
    return buyuk + metin[1:]


def _font_yukle(yol: Path, boyut: int) -> ImageFont.FreeTypeFont:
    """TTF fontunu belirtilen boyutta yükler."""
    try:
        if yol.exists():
            return ImageFont.truetype(str(yol), boyut)
    except Exception as e:
        log.warning("Font yükleme hatası (%s, %d): %s", yol, boyut, e)
    return ImageFont.load_default()


def _font(punto: int, eksenler: Optional[List[float]] = None) -> ImageFont.FreeTypeFont:
    """Instabot uyumluluk köprüsü: punto ve opsiyonel eksenlerle font yükler."""
    return _font_yukle(FONT_SANS, punto)


def kanal_ikonlari_bas(
    gorsel: Image.Image,
    ayarlar: Any = None,
    y_merkez: int = 1800,
    renk: Tuple[int, int, int] = (150, 160, 180),
) -> Image.Image:
    """Slaytın alt bilgisine sosyal kanal ikonlarını veya marka metnini basar."""
    return gorsel


BUYUKLUK_KELIMELERI = {"bin", "milyon", "milyar", "trilyon"}
PARA_BIRIMLERI = {"₺", "$", "€", "£"}
UNVAN_VE_KISALTMALAR = {
    "dr.", "doç.", "prof.", "av.", "md.", "no.", "sf.", "vb.", "cad.", "sok.", "mah.", "apt.", "bl.",
}


def _is_para_birimi(w: str) -> bool:
    clean = w.strip(".,;:!?*()[]_")
    return clean in PARA_BIRIMLERI or any(clean.endswith(p) or clean.startswith(p) for p in PARA_BIRIMLERI)


def _is_sayi(w: str) -> bool:
    clean = re.sub(r"[\.,]", "", w.strip("*_()[]"))
    return clean.isdigit()


def _is_unvan_veya_on_ek(w: str) -> bool:
    if not w:
        return False
    clean = w.lower().strip("*_()[]")
    if clean in UNVAN_VE_KISALTMALAR:
        return True
    if re.match(r"^\d+\.$", clean):
        return True
    return False


def _temizle_tipografi(metin: str) -> str:
    """Metindeki kaçış dizilerini (\\n), markdown yıldızlarını (**) ve eksik glifleri temizler."""
    if not metin:
        return ""
    # filtre modülünden tipografi standartlarını ve markdown temizliğini uygula
    temiz = filtre.markdown_temizle(metin)
    # Inter ve Fraunces fontunda bulunmayan ve .notdef (boş kutu) basan glifleri güvenli alternatiflerle değiştir
    glifler = {
        "➔": "→",
        "➜": "→",
        "➤": "→",
        "👉": "→",
        "🎯": "◆",
        "📌": "■",
        "📈": "▲",
        "📉": "▼",
        "“": '"',
        "”": '"',
        "’": "'",
        "‘": "'",
        "…": "...",
    }
    for bozuk, duzgun in glifler.items():
        temiz = temiz.replace(bozuk, duzgun)
    return " ".join(temiz.split())


# Hiçbir slayt 600 karakterden fazlasını gösteremiyor; bunun ötesi yalnızca
# ölçüm maliyeti. Sınır, bozuk girdinin (ör. 1 MB'lık tek alan) çizimi
# kilitlemesini önler.
AZAMI_SARILACAK = 4000


def _kelimeyi_bol(
    kelime: str, font: ImageFont.FreeTypeFont, azami_genislik: int, draw: ImageDraw.ImageDraw
) -> List[str]:
    """Kutuya sığmayan tek kelimeyi karakter sınırından böler.

    Türkçe'de "Muvaffakiyetsizleştiricileştiriveremeyebileceklerimizden..." gibi
    kelimeler ve model çıktısındaki bitişik dizeler kutudan taşıyordu: boşluk
    olmadığı için sarma algoritması bölecek yer bulamıyor, satırı olduğu gibi
    basıyordu. Stres testinde kapanış manşetinin sağ kenardan çıkması buydu.
    """
    parcalar: List[str] = []
    kalan = kelime

    def _genislik(p: str) -> int:
        return draw.textbbox((0, 0), p, font=font)[2]

    while kalan:
        if _genislik(kalan) <= azami_genislik:
            parcalar.append(kalan)
            break
        # Sığan en uzun ön eki ikili aramayla bul. Karakter karakter ölçmek
        # 4000 karakterlik bozuk girdide tek slaytı saniyelere çıkarıyordu
        # (stres testi: devasa_paragraf — 12,7 sn).
        dusuk, yuksek = 1, len(kalan)
        while dusuk < yuksek:
            orta = (dusuk + yuksek + 1) // 2
            if _genislik(kalan[:orta]) <= azami_genislik:
                dusuk = orta
            else:
                yuksek = orta - 1
        parcalar.append(kalan[:dusuk])
        kalan = kalan[dusuk:]
    return parcalar


def _metin_sar(metin: str, font: ImageFont.FreeTypeFont, azami_genislik: int, draw: ImageDraw.ImageDraw) -> List[str]:
    """
    Metni piksel genişliğine göre satırlara böler. Sığmayan kelimeyi de böler.
    ₺ gibi para birimlerinin önceki rakamdan ve unvanların sonraki kelimeden
    kopmasını engelleyen akıllı yapışkanlık (glue) kurallarını uygular.
    """
    metin = _temizle_tipografi(metin)[:AZAMI_SARILACAK]
    if azami_genislik < 8:
        return []
    kelimeler = metin.split()
    satirlar: List[str] = []
    mevcut: List[str] = []

    for k in kelimeler:
        deneme = " ".join(mevcut + [k])
        if draw.textbbox((0, 0), deneme, font=font)[2] <= azami_genislik:
            mevcut.append(k)
            continue

        tasinanlar: List[str] = []

        # Kural 1: Para / birim sembolü taşıyorsa önceki rakamı ve büyüklüğü beraberinde çeksin
        if _is_para_birimi(k) and mevcut:
            if (
                len(mevcut) >= 2
                and mevcut[-1].lower().strip("*") in BUYUKLUK_KELIMELERI
                and _is_sayi(mevcut[-2])
            ):
                if len(mevcut) > 2:
                    b = mevcut.pop()
                    s = mevcut.pop()
                    tasinanlar = [s, b]
            elif _is_sayi(mevcut[-1]):
                if len(mevcut) > 1:
                    tasinanlar = [mevcut.pop()]

        # Kural 2: Büyüklük (bin, milyon) taşıyorsa önceki sayıyı çeksin
        elif k.lower().strip("*") in BUYUKLUK_KELIMELERI and mevcut:
            if _is_sayi(mevcut[-1]) and len(mevcut) > 1:
                tasinanlar = [mevcut.pop()]

        # Kural 3: Satır sonunda unvan/ön ek kaldıysa (Doç., Dr., No., 14.), yeni satıra taşınsın
        elif mevcut:
            while len(mevcut) > 1 and _is_unvan_veya_on_ek(mevcut[-1]):
                tasinanlar.insert(0, mevcut.pop())

        if mevcut:
            satirlar.append(" ".join(mevcut))
            mevcut = []

        yeni_aday = tasinanlar + [k]
        yeni_str = " ".join(yeni_aday)

        if draw.textbbox((0, 0), yeni_str, font=font)[2] <= azami_genislik:
            mevcut = yeni_aday
        else:
            # Eğer taşınanlarla birlikte sığmıyorsa parça parça ele al
            for parca in yeni_aday:
                if not mevcut:
                    if draw.textbbox((0, 0), parca, font=font)[2] <= azami_genislik:
                        mevcut = [parca]
                    else:
                        parcalar = _kelimeyi_bol(parca, font, azami_genislik, draw)
                        satirlar.extend(parcalar[:-1])
                        mevcut = [parcalar[-1]] if parcalar else []
                else:
                    deneme_parca = " ".join(mevcut + [parca])
                    if draw.textbbox((0, 0), deneme_parca, font=font)[2] <= azami_genislik:
                        mevcut.append(parca)
                    else:
                        satirlar.append(" ".join(mevcut))
                        if draw.textbbox((0, 0), parca, font=font)[2] <= azami_genislik:
                            mevcut = [parca]
                        else:
                            parcalar = _kelimeyi_bol(parca, font, azami_genislik, draw)
                            satirlar.extend(parcalar[:-1])
                            mevcut = [parcalar[-1]] if parcalar else []

    if mevcut:
        satirlar.append(" ".join(mevcut))
    return satirlar


_basarisiz_gorsel_urlleri: set[str] = set()

def _foto_indir_veya_ac(foto_url_veya_yol: str, deneme_adedi: int = 2) -> Optional[Image.Image]:
    """
    URL veya yerel dosyadan görseli açar:
    1. Upload önbelleğinde yerel dosya varsa doğrudan diskten okur.
    2. Uzak URL ise 2 denemeli ve artan bekleme ile çeker.
    3. 404/403 gibi kesin hatalarda derhal durur ve başarısız URL'yi önbelleğe alıp diğer slaytları bekletmez.
    4. EXIF yön matrisini (ImageOps.exif_transpose) otomatik uygular; asla yan veya ters dönmez.
    """
    if not foto_url_veya_yol:
        return None

    s = str(foto_url_veya_yol).strip()
    if s in _basarisiz_gorsel_urlleri:
        return None

    # 1. Upload önbelleğinde yerel dosya var mı?
    yerel = upload_image.yerel_karsiligi(s)
    if yerel and yerel.exists() and yerel.is_file():
        try:
            with Image.open(yerel) as img:
                return ImageOps.exif_transpose(img).convert("RGB")
        except Exception as e:
            log.warning("Önbellekteki görsel açılamadı (%s): %s", yerel, e)

    # 2. Uzak URL ise indir
    if s.startswith("http://") or s.startswith("https://"):
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        for deneme in range(1, deneme_adedi + 1):
            try:
                resp = requests.get(s, headers=headers, timeout=8)
                if resp.status_code == 200:
                    with Image.open(io.BytesIO(resp.content)) as img:
                        return ImageOps.exif_transpose(img).convert("RGB")
                log.warning("Görsel indirme HTTP %d (deneme %d/%d): %s", resp.status_code, deneme, deneme_adedi, s)
                if resp.status_code in (404, 410, 403):
                    _basarisiz_gorsel_urlleri.add(s)
                    break
            except Exception as e:
                log.warning("Görsel indirme hatası (%s, deneme %d/%d): %s", s, deneme, deneme_adedi, e)
            if deneme < deneme_adedi:
                time.sleep(1)
        _basarisiz_gorsel_urlleri.add(s)
        return None

    # 3. Yerel dosya
    try:
        p = Path(s)
        if p.exists() and p.is_file():
            with Image.open(p) as img:
                return ImageOps.exif_transpose(img).convert("RGB")
    except Exception as e:
        log.warning("Yerel görsel açılamadı (%s): %s", s, e)

    return None


ETKISIZ_KELIMELER = {
    "icin", "olan", "gibi", "kadar", "sonra", "once", "veya", "gore",
    "biri", "yeni", "daha", "cok", "bazi", "tum", "her", "ile", "ve",
    "bir", "bu", "su", "o", "da", "de", "ta", "te", "mi", "mu", "mu",
}


def konu_imzasi(baslik: str) -> Tuple[set[str], set[str]]:
    """Tekrar denetimi ve kardeş haber eşleştirmesi için (anahtar kelimeler, özel isimler)."""
    kelimeler = set()
    for ham in (baslik or "").lower().replace("'", " ").split():
        temiz = "".join(k for k in ham if k.isalnum())
        if len(temiz) >= 4 and temiz not in ETKISIZ_KELIMELER:
            kelimeler.add(temiz)

    isimler = set()
    for ham in (baslik or "").replace("'", " ").split():
        temiz = "".join(k for k in ham if k.isalnum())
        if len(temiz) >= 4 and temiz[:1].isupper():
            kucuk = temiz.lower()
            if kucuk not in ETKISIZ_KELIMELER:
                isimler.add(kucuk)
    return kelimeler, isimler


def kardes_linkler(con, haber: Dict[str, Any], azami: int = 3) -> List[str]:
    """
    Aynı olayı işleyen diğer haber kayıtlarının linkleri.
    Son 2 günün haberlerinden konu imzası ve ortak kelimelerle HD basın fotoğraflarını toplar.
    """
    if con is None:
        try:
            con = db.baglanti_al()
        except Exception:
            return []

    baslik = haber.get("baslik") or haber.get("orijinal_baslik") or haber.get("manset") or ""
    if not baslik:
        return []

    k1, i1 = konu_imzasi(baslik)
    haber_id = haber.get("id") or 0

    try:
        satirlar = con.execute(
            """SELECT id, baslik, link, foto_url FROM haberler
               WHERE id != ? AND COALESCE(link, '') != ''
                 AND eklenme_tarihi > datetime('now', '-2 days')""",
            (haber_id,),
        ).fetchall()
    except Exception as e:
        log.debug("Kardeş haber sorgusu: %s", e)
        return []

    esler = []
    for r in satirlar:
        b2 = r["baslik"] if isinstance(r, dict) or hasattr(r, "keys") else r[1]
        link = r["link"] if isinstance(r, dict) or hasattr(r, "keys") else r[2]
        foto_url = (r["foto_url"] if isinstance(r, dict) or hasattr(r, "keys") else r[3]) or ""
        k2, i2 = konu_imzasi(b2 or "")
        ortak = len(k1 & k2)
        if ortak >= 3 or (ortak >= 2 and (i1 & i2)):
            esler.append((ortak, link, foto_url))

    esler.sort(key=lambda x: -x[0])
    linkler = [link for _, link, _ in esler if link][:azami]
    if linkler:
        log.info("Aynı olayın %d ek kardeş kaynağı bulundu (haber #%s)", len(linkler), haber_id)
    return linkler


def _haber_gorseli_alternatifi(
    haber: Dict[str, Any],
    con=None,
    sira: int = 0,
) -> Tuple[Optional[Image.Image], Optional[str]]:
    """
    'Başka fotoğraf' için SIRADAKİ haber görseli veya kardeş haber basın fotoğrafı.
    Sıra: Ana haber linki -> Kardeş 1 -> Kardeş 2 -> Kardeş 3.
    """
    from . import fetch_article, gorsel_kalite
    aday_linkler = []
    ana_link = haber.get("link") or haber.get("orijinal_url") or haber.get("url")
    if ana_link:
        aday_linkler.append(ana_link)
    aday_linkler.extend(kardes_linkler(con, haber))

    if sira < len(aday_linkler):
        link = aday_linkler[sira]
        try:
            url = fetch_article.og_gorseli_cek(link)
            if not url:
                ek_gorseller = fetch_article.tum_gorselleri_cek(link)
                if ek_gorseller:
                    url = ek_gorseller[0]
            if url:
                foto = _foto_indir_veya_ac(url)
                if foto:
                    kaliteli, sebep = gorsel_kalite.gorsel_kalite_denetle(foto)
                    if kaliteli:
                        return gorsel_kalite.kristal_netlestir(foto), f"Basın Kaynağı ({link[:30]}…)"
        except Exception as e:
            log.debug("Kardeş görsel çekilemedi (%s): %s", link, e)

    return None, None


def _sigdir_font(
    metin: str,
    font_yolu: Path,
    baslangic_boyut: int,
    min_boyut: int,
    azami_w: int,
    max_satir: int,
    draw: ImageDraw.ImageDraw,
) -> Tuple[ImageFont.FreeTypeFont, List[str]]:
    """Metni belirtilen azami genişlik ve maksimum satır sayısına sığdırmak için font boyutunu dinamik küçültür."""
    boyut = baslangic_boyut
    while boyut >= min_boyut:
        f = _font_yukle(font_yolu, boyut)
        satirlar = _metin_sar(metin, f, azami_w, draw)
        if len(satirlar) <= max_satir:
            return f, satirlar
        boyut -= 2
    f = _font_yukle(font_yolu, min_boyut)
    satirlar = _metin_sar(metin, f, azami_w, draw)
    return f, satirlar[:max_satir]


def _govde_sigdir(
    metin: str,
    font_yolu: Path,
    baslangic_boyut: int,
    min_boyut: int,
    azami_w: int,
    azami_satir: int,
    draw: ImageDraw.ImageDraw,
) -> Tuple[ImageFont.FreeTypeFont, List[str]]:
    """Gövde metnini KIRPMADAN sığdırır: satır sayısı aşılırsa font küçültülür.

    `_sigdir_font` ile farkı, min boyutta bile sığmayan metni kesmek yerine olduğu
    gibi döndürmesi. Çağıran taraf kutuyu büyütebilir. Sessiz kırpma bu projede
    "cümlenin ortasında biten kart" hatasını üretti; bir daha üretmesin.
    """
    boyut = baslangic_boyut
    while boyut >= min_boyut:
        f = _font_yukle(font_yolu, boyut)
        satirlar = _metin_sar(metin, f, azami_w, draw)
        if len(satirlar) <= azami_satir:
            return f, satirlar
        boyut -= 1
    f = _font_yukle(font_yolu, min_boyut)
    return f, _metin_sar(metin, f, azami_w, draw)


def _ek_dolgu_hesapla(
    yukseklikler: List[int],
    ust: int,
    alt: int,
    asgari_bosluk: int = 18,
    azami_ek: int = 72,
) -> int:
    """Kart başına eklenecek iç dolguyu döner.

    İçerik kısa olduğunda kartları olduğu gibi bırakıp yığını ortalamak,
    başlık ile ilk kart arasında kopukluk yaratıyor. Artan alanı önce kartların
    içine vermek 4:5 kareyi doğal doldurur — tasarımcının yapacağı şey bu.
    """
    if not yukseklikler:
        return 0
    n = len(yukseklikler)
    artan = (alt - ust) - sum(yukseklikler) - ((n - 1) * asgari_bosluk)
    if artan <= 0:
        return 0
    return min(azami_ek, artan // n)


def _dikey_dagit(
    ust: int,
    alt: int,
    yukseklikler: List[int],
    asgari_bosluk: int = 18,
    azami_bosluk: int = 56,
) -> List[int]:
    """Blokları [ust, alt] aralığına dağıtır ve her birinin Y konumunu döner.

    Artan boşluk önce bloklar arasına (azami_bosluk'a kadar) verilir, kalanı
    yığını dikeyde ortalar. Sabit yükseklikli kartlar karenin alt dörtte birini
    boş bırakıyordu; ölçüp dağıtınca o boşluk kompozisyonun parçası oluyor.
    """
    if not yukseklikler:
        return []
    n = len(yukseklikler)
    alan = alt - ust
    toplam = sum(yukseklikler)
    aralik_sayisi = max(n - 1, 0)

    artan = alan - toplam - (aralik_sayisi * asgari_bosluk)
    bosluk = asgari_bosluk
    if artan > 0 and aralik_sayisi:
        bosluk = min(azami_bosluk, asgari_bosluk + artan // aralik_sayisi)

    kullanilan = toplam + (aralik_sayisi * bosluk)
    y = ust + max(0, (alan - kullanilan) // 2)

    konumlar = []
    for h in yukseklikler:
        konumlar.append(y)
        y += h + bosluk
    return konumlar


def _logo_yerlestir(
    canvas: Image.Image,
    beyaz: bool = True,
    x: Optional[int] = None,
    y: int = 55,
    lw: int = 285,
    golge: bool = True,
    kirmizi_zemin: bool = False,
) -> None:
    """Pürüzsüz Alpha Composite ve difüzyon gölge ile EDM logosunu tuvale yerleştirir.

    Kırmızı zeminlerde kırmızı harflerin arka planda kaybolmasını engellemek için
    monokrom saf beyaz logo (LOGO_YATAY_BEYAZ) kullanılır.
    """
    if kirmizi_zemin and LOGO_YATAY_BEYAZ.exists():
        logo_yolu = LOGO_YATAY_BEYAZ
    else:
        logo_yolu = LOGO_YATAY_ACIK if beyaz else LOGO_YATAY

    if logo_yolu.exists():
        try:
            logo = Image.open(logo_yolu).convert("RGBA")
            lh = int(logo.height * (lw / logo.width))
            logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)
            if x is None:
                x = GENISLIK - 70 - lw
            c_rgba = canvas.convert("RGBA")

            # Difüzyon Gölge Katmanı (Her zeminde %100 kristal okunurluk ve derinlik)
            if golge:
                pad = 22
                s_w, s_h = lw + (2 * pad), lh + (2 * pad)
                golge_katman = Image.new("RGBA", (s_w, s_h), (0, 0, 0, 0))

                alfa = logo.split()[3]
                if kirmizi_zemin:
                    # Kırmızı zeminde saf beyaz logo için Seçenek B doğal difüzyon gölgesi
                    kara_logo = Image.new("RGBA", (lw, lh), (0, 0, 0, 200))
                    kara_logo.putalpha(alfa)
                    golge_katman.paste(kara_logo, (pad, pad + 3), kara_logo)
                    golge_katman = golge_katman.filter(ImageFilter.GaussianBlur(7))
                    c_rgba.paste(golge_katman, (x - pad, y - pad), golge_katman)
                elif beyaz:
                    # Koyu/fotoğraf zemin için doğal difüzyon gölgesi (ağır kapsül kutusu kaldırıldı)
                    kara_logo = Image.new("RGBA", (lw, lh), (0, 0, 0, 170))
                    kara_logo.putalpha(alfa)
                    golge_katman.paste(kara_logo, (pad, pad + 3), kara_logo)
                    golge_katman = golge_katman.filter(ImageFilter.GaussianBlur(7))
                    c_rgba.paste(golge_katman, (x - pad, y - pad), golge_katman)
                else:
                    # Açık tonlu / kağıt zeminlerde abartı veya kirli gölgeye gerek yok (net, pürüzsüz vektör görünümü)
                    pass

            c_rgba.paste(logo, (x, y), logo)
            canvas.paste(c_rgba.convert("RGB"), (0, 0))
        except Exception as e:
            log.warning("Logo yerleştirme hatası: %s", e)


def _difuzyon_golgeli_metin(
    canvas: Image.Image,
    satirlar_ve_renkler: List[Tuple[str, Tuple[int, int, int]]],
    x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    satir_araligi: int = 66,
    golge_radius: int = 8,
    golge_alfa: int = 140,
) -> int:
    """Metin arkasına yumuşak Gaussian Blur difüzyon gölgesi basarak kristal netlik sağlar."""
    golge = Image.new("RGBA", (GENISLIK, YUKSEKLIK), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(golge)

    curr_y = y
    for satir, _ in satirlar_ve_renkler:
        g_draw.text((x, curr_y + 3), satir, font=font, fill=(0, 0, 0, golge_alfa))
        curr_y += satir_araligi

    golge = golge.filter(ImageFilter.GaussianBlur(golge_radius))
    c_rgba = canvas.convert("RGBA")
    c_rgba.paste(golge, (0, 0), golge)
    canvas.paste(c_rgba.convert("RGB"), (0, 0))

    draw = ImageDraw.Draw(canvas)
    curr_y = y
    for satir, renk in satirlar_ve_renkler:
        draw.text((x, curr_y), satir, font=font, fill=renk)
        curr_y += satir_araligi

    return curr_y


# Kategori bazlı zengin görsel havuzu (her içerikte farklı ve çarpıcı mimari / arsa atmosferi)
# Havuzlar dosya ADINA göre değil, fotoğrafın GÖRÜNEN içeriğine göre (2026-09-25
# gözden geçirme). Adlar yanıltıcıydı: "arsa_parsel_aerial" havuzlu villa,
# "arsa_suburb_plot" orman tavanı, "arsa_villa_land" bulut üstü dağlar,
# "bina_residential_balcony" yosunlu orman, "bina_architecture_highrise" villa.
# Konuyla ilgisi olmayanlar (dağ, orman) ve üzerinde başka markanın logosu olan
# "insaat_modern_structure" rotasyondan çıkarıldı. Havuz küçük; asıl çeşitlilik
# PEXELS_API_KEY ile konuya özel aramadan ya da ofisin kendi Trakya fotoğraflarından gelir.
ARKA_PLAN_HAVUZU = {
    "ARSA": [
        "arsa_aerial_green.jpg",        # buğday tarlası, gün batımı
        "arsa_green_drone.jpg",         # çiftlik ambarı ve tarla
        "arsa_plow_field.jpg",          # yakın plan ekili alan
        "arsa_suburban_parsel.jpg",     # havadan müstakil evler / parseller
    ],
    "KONUT": [
        "villa_modern_pool.jpg",
        "villa_luxury_dusk.jpg",
        "villa_minimal_white.jpg",
        "villa_estate_garden.jpg",
        "clean_modern_villa.jpg",
        "icmekan_minimal_living.jpg",   # adı iç mekân ama müstakil ev cephesi
        "arsa_suburban_parsel.jpg",
    ],
    "BINA": [
        "bina_modern_glass.jpg",        # apartman cephesi
        "bina_facade_dusk.jpg",         # çok katlı binalar
        "arsa_suburban_parsel.jpg",     # yerleşim dokusu
    ],
    "ICMEKAN": [
        "icmekan_luxury_penthouse.jpg",
        "icmekan_modern_lounge.jpg",
        "clean_interior.jpg",
        "clean_architecture.jpg",
        "villa_estate_contemporary.jpg",
    ],
    "INSAAT": [
        "bina_modern_glass.jpg",
        "bina_facade_dusk.jpg",
    ],
}


# Kapak fotoğrafı KONUNUN kelimelerine göre seçilir; kategori kodu yalnızca yedek.
# 2026-09-25: "Arsa mı konut mu" (YATIRIM) kapağına duvar çerçeveli iç mekân,
# #141'de tarla konusuna salon fotoğrafı düşmüştü. Sıra önemli: ilk eşleşen kazanır.
KONU_HAVUZLARI: List[Tuple[Tuple[str, ...], str]] = [
    (("kentsel dönüşüm", "riskli yapı"), "INSAAT"),
    (("tarla", "arsa", "imar", "ifraz", "parsel", "tarım", "zilyet", "tapusuz", "tiny house", "prefabrik", "bağ evi", "kadastro"), "ARSA"),
    (("inşaat", "müteahhit", "kat karşılığı", "ruhsat", "iskân", "iskan", "yapı kullanma"), "INSAAT"),
    (("kira", "kiracı", "ev sahibi", "tahliye", "depozito", "aidat", "apartman", "kat mülkiyeti", "site yönetimi"), "BINA"),
    (("kredi", "faiz", "banka", "dask", "ekspertiz", "vergi", "yatırım", "değer artış"), "BINA"),
    (("tapu", "önalım", "şufa", "miras", "hisse", "kaparo", "harç", "vekâlet", "satış"), "KONUT"),
]
# Pexels sorgusu (anahtar tanımlıysa): havuzla aynı konu, çok daha geniş seçenek
PEXELS_SORGULARI = {
    "ARSA": "aerial view farmland fields drone",
    "INSAAT": "residential construction site building crane",
    "BINA": "apartment building facade city",
    "KONUT": "residential house exterior neighborhood",
}


def _konu_havuzu(konu_metni: Optional[str], kategori_kodu: Optional[str]) -> str:
    kucuk = (konu_metni or "").replace("İ", "i").replace("I", "ı").lower()
    for kelimeler, havuz in KONU_HAVUZLARI:
        if any(k in kucuk for k in kelimeler):
            return havuz
    kat = (kategori_kodu or "").upper()
    if "ARSA" in kat or "IMAR" in kat or "PARSEL" in kat or "TARLA" in kat:
        return "ARSA"
    if "INSAAT" in kat or "KENTSEL" in kat or "DONUSUM" in kat or "PROJE" in kat:
        return "INSAAT"
    if any(k in kat for k in ("KIRACI", "EV_SAHIBI", "SITE", "APARTMAN", "YATIRIM", "FINANS", "VERGI", "DEGERLEME")):
        # Finans/yatırım eskiden iç mekân havuzuna gidiyordu; konuyla ilgisizdi
        return "BINA"
    return "KONUT"


def _konu_stok_fotografi(havuz: str, tohum: Optional[Any]) -> Optional[Image.Image]:
    """Pexels anahtarı varsa konuya özel dikey fotoğraf (yoksa None; yerel havuz kullanılır)."""
    if config.test_modu() or not config.env_al("PEXELS_API_KEY"):
        return None
    try:
        from . import fetch_stock
        yol = fetch_stock.stok_fotografi_ara(PEXELS_SORGULARI.get(havuz, PEXELS_SORGULARI["KONUT"]),
                                             tohum=str(tohum) if tohum is not None else None)
        if yol and Path(yol).exists():
            return ImageOps.fit(Image.open(yol).convert("RGB"), (GENISLIK, YUKSEKLIK), Image.Resampling.LANCZOS)
    except Exception as e:
        log.warning("Konu stok fotoğrafı alınamadı, yerel havuza dönülüyor: %s", e)
    return None


def _temiz_arkaplan_al(
    kategori_kodu: Optional[str] = None,
    ozel_url_veya_yol: Optional[str] = None,
    tohum: Optional[Any] = None,
    haric_tut: Optional[List[str]] = None,
    konu_metni: Optional[str] = None,
) -> Image.Image:
    """Kategoriye en uygun yüksek çözünürlüklü temiz mimari görseli yükler veya koyu zemin üretir.

    Tekrarlayan aynı görsel sorununu kalıcı olarak önlemek için:
    1. Son paylaşılan 10 görsel veritabanından okunur ve adaylardan elenir.
    2. Kalan adaylar arasından tohum (MD5) veya zaman bazlı seçim yapılır.
    3. Seçilen görsel son kullanılanlar listesine kaydedilir.
    """
    if ozel_url_veya_yol:
        foto = _foto_indir_veya_ac(ozel_url_veya_yol)
        if foto:
            return ImageOps.fit(foto, (GENISLIK, YUKSEKLIK), Image.Resampling.LANCZOS)

    havuz_adi = _konu_havuzu(konu_metni, kategori_kodu)
    if konu_metni is not None:
        stok = _konu_stok_fotografi(havuz_adi, tohum)
        if stok is not None:
            return stok
    havuz = list(ARKA_PLAN_HAVUZU[havuz_adi])

    # Son kullanılanları oku
    son_kullanilan = []
    try:
        raw = db.ayar_oku("son_arkaplanlar")
        if raw:
            son_kullanilan = json.loads(raw)
            if not isinstance(son_kullanilan, list):
                son_kullanilan = []
    except Exception:
        son_kullanilan = []

    if haric_tut:
        son_kullanilan.extend(haric_tut)

    # Havuzdaki mevcut dosyaları kontrol et
    mevcut_havuz = [b_ad for b_ad in havuz if config.yol_al(f"assets/backgrounds/{b_ad}").exists()]
    if not mevcut_havuz:
        mevcut_havuz = havuz

    # Son kullanılanları hariç tut
    adaylar = [ad for ad in mevcut_havuz if ad not in son_kullanilan]
    if not adaylar:
        # Havuz dolduysa son 2 hariç tekrar aç
        adaylar = [ad for ad in mevcut_havuz if ad not in son_kullanilan[-2:]]
    if not adaylar:
        adaylar = mevcut_havuz

    # Tohum varsa kararlı MD5 hash ile seç
    import hashlib
    if tohum is not None:
        idx = int(hashlib.md5(str(tohum).encode("utf-8")).hexdigest(), 16) % len(adaylar)
    else:
        import time
        idx = int(time.time() * 1000) % len(adaylar)

    secilen_ad = adaylar[idx]

    # Son kullanılanlara ekle ve max 10 sakla
    try:
        yeni_liste = [ad for ad in son_kullanilan if ad != secilen_ad] + [secilen_ad]
        db.ayar_yaz("son_arkaplanlar", json.dumps(yeni_liste[-10:]))
    except Exception:
        pass

    yerel_bg = config.yol_al(f"assets/backgrounds/{secilen_ad}")
    if yerel_bg.exists():
        try:
            img = Image.open(yerel_bg).convert("RGB")
            return ImageOps.fit(img, (GENISLIK, YUKSEKLIK), Image.Resampling.LANCZOS)
        except Exception as e:
            log.warning("Arka plan yüklenemedi: %s", e)

    # Yedek prestij koyu tuval
    return Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_MUREKKEP)


def _filigran_uygula(canvas: Image.Image, acik_zemin: bool = False) -> Image.Image:
    """Her slaytın arka planına zarif, silik (%3.5 - %4.5) marka filigranı ekler."""
    try:
        if not LOGO_AMBLEM.exists() or LOGO_AMBLEM.stat().st_size == 0:
            return canvas
        amblem = Image.open(LOGO_AMBLEM).convert("RGBA")
        w_size = max(200, min(500, int(canvas.width * 0.46)))
        h_size = int(w_size * amblem.height / max(1, amblem.width))
        amblem = amblem.resize((w_size, h_size), Image.Resampling.LANCZOS)

        alfa_oran = 0.035 if acik_zemin else 0.045
        r, g, b, a = amblem.split()
        base = Image.new("RGB", amblem.size, (40, 45, 55) if acik_zemin else (255, 255, 255))
        a_faded = a.point(lambda p: int(p * alfa_oran))
        base.putalpha(a_faded)

        # Yerleşim: Sağ alt köşe (alt barın hemen üstünde ve kenar içinde)
        pos_x = canvas.width - w_size - 65
        pos_y = canvas.height - h_size - int(canvas.height * 0.12)

        c_rgba = canvas.convert("RGBA")
        c_rgba.alpha_composite(base, (pos_x, pos_y))
        return c_rgba.convert("RGB")
    except Exception as e:
        log.warning("Filigran uygulanamadı: %s", e)
        return canvas


def _rozet_ciz(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    metin: str,
    bg_color=RENK_KIRMIZI,
    fg_color=RENK_BEYAZ,
    border_color=None,
    font_boyut: int = 19,
    max_w: Optional[int] = None,
) -> int:
    """Teknik mono rozet çizer ve kapladığı genişliği piksel cinsinden döndürür.

    Dinamik kutucuk boyutu, güvenli kenar payı (safe area), dikey ortalama
    ve aşırı uzun metinlerde taşmayı önleyici font küçültme/kırpma sağlar.
    """
    if metin is None:
        return 0
    metin = _temizle_tipografi(str(metin)).strip()
    if not metin:
        return 0

    if max_w is None:
        max_w = max(100, GENISLIK - x - 70)

    pad_x = 20
    pad_y = 8

    cur_boyut = font_boyut
    font = _font_yukle(FONT_MONO_BOLD, cur_boyut)
    bbox = draw.textbbox((0, 0), metin, font=font)
    w = bbox[2] - bbox[0]

    # Kutunun tuvali veya max_w sınırını aşmasını dinamik önle
    while (w + (pad_x * 2) > max_w) and cur_boyut > 11:
        cur_boyut -= 2
        font = _font_yukle(FONT_MONO_BOLD, cur_boyut)
        bbox = draw.textbbox((0, 0), metin, font=font)
        w = bbox[2] - bbox[0]

    if w + (pad_x * 2) > max_w:
        kesim = max(3, int(max_w / max(1, (cur_boyut * 0.7))))
        metin = metin[:kesim].rstrip() + "…"
        bbox = draw.textbbox((0, 0), metin, font=font)
        w = bbox[2] - bbox[0]

    h = bbox[3] - bbox[1]
    bw = min(max_w, w + (pad_x * 2))
    bh = h + (pad_y * 2)

    draw.rounded_rectangle(
        [(x, y), (x + bw, y + bh)],
        radius=6,
        fill=bg_color,
        outline=border_color,
    )
    # Metni dikeyde ve yatayda tam safe area içinde KESİN matematiksel ortala
    tx = x + (bw - w) / 2 - bbox[0]
    ty = y + (bh - h) / 2 - bbox[1]
    draw.text((tx, ty), metin, font=font, fill=fg_color)
    return bw


def _arti_isareti_ciz(draw: ImageDraw.ImageDraw, x: int, y: int, renk=RENK_KURSUN, boyut=12):
    """Rölöve ve imar paftası köşe artı işaretini çizer."""
    r = boyut // 2
    draw.line([(x - r, y), (x + r, y)], fill=renk, width=1)
    draw.line([(x, y - r), (x, y + r)], fill=renk, width=1)


def _vektor_ikon_uret(
    ad: str,
    boyut: int,
    renk: Tuple[int, int, int] = (255, 255, 255),
    bg_renk: Optional[Tuple[int, int, int]] = None,
) -> Image.Image:
    """256x256 normalize süper-örnekleme ile matematiksel antialiased vektör ikon üretir.
    Desteklenenler: 'bookmark', 'mail', 'web', 'phone', 'pin', 'share', 'check'
    """
    canvas_size = 256
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rgba = (*renk, 255)

    if bg_renk is not None:
        d.ellipse([(0, 0), (canvas_size - 1, canvas_size - 1)], fill=(*bg_renk, 255))

    if ad == "bookmark":
        # Şık çentikli kurdele
        x0, y0, x1, y1 = 52, 24, 204, 232
        notch = 56
        pts = [(x0, y0), (x1, y0), (x1, y1), (128, y1 - notch), (x0, y1)]
        d.polygon(pts, fill=rgba)

    elif ad == "phone":
        # Modern akıllı telefon
        x0, y0, x1, y1 = 64, 24, 192, 232
        d.rounded_rectangle([(x0, y0), (x1, y1)], radius=32, outline=rgba, width=18)
        # Hoparlör çentiği
        d.line([(106, 52), (150, 52)], fill=rgba, width=12)
        # Alt çentik / ana ekran çizgisi
        d.line([(110, 208), (146, 208)], fill=rgba, width=12)

    elif ad == "mail":
        # Posta zarfı
        x0, y0, x1, y1 = 28, 52, 228, 204
        d.rounded_rectangle([(x0, y0), (x1, y1)], radius=22, outline=rgba, width=18)
        d.line([(38, 60), (128, 140)], fill=rgba, width=18)
        d.line([(128, 140), (218, 60)], fill=rgba, width=18)

    elif ad == "web":
        # Küre (Globe)
        d.ellipse([(28, 28), (228, 228)], outline=rgba, width=18)
        d.line([(28, 128), (228, 128)], fill=rgba, width=18)
        d.ellipse([(80, 28), (176, 228)], outline=rgba, width=18)
        d.line([(128, 28), (128, 228)], fill=rgba, width=18)

    elif ad == "pin":
        # Harita pini
        cx, cy = 128, 100
        r = 64
        d.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=rgba)
        pts = [(cx - r, cy + 12), (cx + r, cy + 12), (cx, 236)]
        d.polygon(pts, fill=rgba)
        inner_r = 26
        delik_renk = (18, 20, 26, 255) if bg_renk is None else (*bg_renk, 255)
        d.ellipse([(cx - inner_r, cy - inner_r), (cx + inner_r, cy + inner_r)], fill=delik_renk)

    elif ad == "share":
        # Paylaşım oku
        d.line([(68, 188), (188, 68)], fill=rgba, width=18)
        d.line([(116, 68), (188, 68), (188, 140)], fill=rgba, width=18)

    elif ad == "check":
        d.line([(48, 128), (108, 188), (208, 68)], fill=rgba, width=22)

    elif ad == "comment":
        # Şık konuşma balonu
        d.rounded_rectangle([(28, 36), (228, 184)], radius=40, fill=rgba)
        pts = [(64, 176), (36, 234), (112, 184)]
        d.polygon(pts, fill=rgba)
        for cx in [84, 128, 172]:
            d.ellipse([(cx - 11, 110 - 11), (cx + 11, 110 + 11)], fill=(255, 255, 255, 255))

    elif ad == "follow":
        # Takip et (kullanıcı + artı)
        d.ellipse([(70, 24), (150, 104)], fill=rgba)
        d.chord([(36, 124), (184, 236)], start=180, end=0, fill=rgba)
        px, py = 196, 76
        pw, pl = 8, 28
        d.rectangle([(px - pw//2, py - pl//2), (px + pw//2, py + pl//2)], fill=rgba)
        d.rectangle([(px - pl//2, py - pw//2), (px + pl//2, py + pw//2)], fill=rgba)

    return img.resize((boyut, boyut), Image.Resampling.LANCZOS)



def _edm_pin_al(boyut: int = 34) -> Image.Image:
    """EDM'in resmi kırmızı pin sembolünü döndürür."""
    if LOGO_PIN.exists():
        try:
            pin = Image.open(LOGO_PIN).convert("RGBA")
            h = boyut
            w = int(pin.width * (h / pin.height))
            return pin.resize((w, h), Image.Resampling.LANCZOS)
        except Exception as e:
            # Sessizce geçmiyoruz: marka varlığı yüklenemezse slayt
            # MARKASIZ üretilir ve kimse fark etmez.
            log.warning("pin sembolü yüklenemedi, slayt onsuz üretiliyor: %s", e)
    return _vektor_ikon_uret("pin", boyut, RENK_KIRMIZI_CANLI)



# =========================================================================
# 1. İLAN SLAYTI ÜRETİCİLERİ (TEK TIKLA PORTFÖY PAYLAŞIMI)
# =========================================================================


@_gorsel_girdisi
def ilan_kapak_slayti_ciz(ilan: Dict[str, Any], cikti_yolu: Optional[Path] = None) -> Path:
    """İlanın 1. slaytı (Kanca / Hero Kapak): Devasa fotoğraf, şık serif manşet ve fiyat."""
    img = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_MUREKKEP)
    draw = ImageDraw.Draw(img)

    # 1. Fotoğrafları Al
    gorseller = ilan.get("gorseller")
    if not gorseller:
        try:
            gorseller = json.loads(ilan.get("gorseller_json") or "[]")
        except Exception:
            gorseller = []

    foto = _foto_indir_veya_ac(gorseller[0]) if gorseller else None
    if foto:
        # Fotoğrafı 1080x920 alanına şık kırp
        foto_kirpilmis = ImageOps.fit(foto, (GENISLIK, 920), Image.Resampling.LANCZOS)
        img.paste(foto_kirpilmis, (0, 0))

        # Alttan yukarıya doğru derin sinematik gradyan perde (y=500'den y=920'ye)
        perde = Image.new("RGBA", (GENISLIK, 420), (0, 0, 0, 0))
        p_draw = ImageDraw.Draw(perde)
        for i in range(420):
            alfa = int(255 * (i / 420) ** 1.3)
            p_draw.line([(0, i), (GENISLIK, i)], fill=(18, 19, 22, min(alfa, 255)))
        img.paste(perde, (0, 500), perde)
    else:
        # Fotoğraf yoksa prestijli geometrik koyu zemin
        draw.rectangle([(0, 0), (GENISLIK, 920)], fill=RENK_MUREKKEP_2)

    # 2. Üst Bar: Sol üst rozet, sağ üst EDM Açık Logo
    kenar_bosluk = 65
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)

    islem_degeri = str(ilan.get("islem") or "satilik").lower()
    islem = {
        "satilik": "SATILIK",
        "kiralik": "KİRALIK",
        "gunluk-kiralik": "GÜNLÜK KİRALIK",
        "sezonluk-kiralik": "SEZONLUK KİRALIK",
        "devren-satilik": "DEVREN SATILIK",
        "devren-kiralik": "DEVREN KİRALIK",
    }.get(islem_degeri, islem_degeri.replace("-", " ").upper())
    tip = (ilan.get("tip") or "Gayrimenkul").upper()
    rozet_metni = f"{islem} {tip}"
    _rozet_ciz(draw, kenar_bosluk, 55, rozet_metni, bg_color=RENK_KIRMIZI, font_boyut=20)

    # Sağ üst logo (logo-yatay-acik.png)
    if LOGO_YATAY_ACIK.exists():
        try:
            logo = Image.open(LOGO_YATAY_ACIK).convert("RGBA")
            lw = 240
            lh = int(logo.height * (lw / logo.width))
            logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)
            img.paste(logo, (GENISLIK - kenar_bosluk - lw, 52), logo)
        except Exception as e:
            # Sessizce geçmiyoruz: marka varlığı yüklenemezse slayt
            # MARKASIZ üretilir ve kimse fark etmez.
            log.warning("logo (açık) yüklenemedi, slayt onsuz üretiliyor: %s", e)

    # 3. Rölöve Ayrım Çizgisi & Köşe Artı İşaretleri (y=830)
    panel_y = 830
    draw.line([(kenar_bosluk, panel_y), (GENISLIK - kenar_bosluk, panel_y)], fill=RENK_CIZGI_KOYU, width=1)
    _arti_isareti_ciz(draw, kenar_bosluk, panel_y, renk=RENK_KIRMIZI, boyut=14)
    _arti_isareti_ciz(draw, GENISLIK - kenar_bosluk, panel_y, renk=RENK_KIRMIZI, boyut=14)

    # 4. Lokasyon & İlan No (Mono Metadata)
    ilce = (ilan.get("ilce") or "SİLİVRİ").upper()
    mahalle = (ilan.get("mahalle") or "").upper()
    lokasyon_yazi = f"{ilce} · {mahalle}  //  PORTFÖY NO: #{ilan.get('id', '')}"
    font_mono_lok = _font_yukle(FONT_MONO, 20)
    draw.text((kenar_bosluk, panel_y + 24), lokasyon_yazi, font=font_mono_lok, fill=RENK_KURSUN)

    # 5. Büyük Başlık (Fraunces Serif — Zarafet ve Kanca)
    baslik = ilan.get("baslik", "").strip()
    font_baslik = _font_yukle(FONT_FRAUNCES, 46)
    baslik_satirlari = _metin_sar(baslik, font_baslik, kullanilabilir_w, draw)
    by = panel_y + 64
    for satir in baslik_satirlari[:2]:
        draw.text((kenar_bosluk, by), satir, font=font_baslik, fill=RENK_KAGIT)
        by += 54

    # 6. Devasa Fiyat & Vurgu (Fraunces Serif)
    fiyat_ham = float(ilan.get("fiyat") or 0)
    para_simgesi = {"TRY": "₺", "USD": "$", "EUR": "€", "GBP": "£"}.get(
        str(ilan.get("para_birimi") or "TRY").upper(),
        str(ilan.get("para_birimi") or "TRY"),
    )
    donem = (
        " / Gün" if islem_degeri == "gunluk-kiralik"
        else " / Sezon" if islem_degeri == "sezonluk-kiralik"
        else " / Ay" if islem_degeri == "kiralik"
        else ""
    )
    fiyat_metni = f"{int(fiyat_ham):,} {para_simgesi}{donem}".replace(",", ".")

    fiyat_y = by + 20
    font_fiyat_etiket = _font_yukle(FONT_MONO, 18)
    draw.text((kenar_bosluk, fiyat_y), "GÜNCEL FİYAT", font=font_fiyat_etiket, fill=RENK_KIRMIZI)

    font_fiyat = _font_yukle(FONT_FRAUNCES, 58)
    draw.text((kenar_bosluk, fiyat_y + 24), fiyat_metni, font=font_fiyat, fill=RENK_KAGIT)

    # 7. Teknik Metrikler Şeridi (m², Oda, vb.)
    metrik_y = YUKSEKLIK - 145
    draw.line([(kenar_bosluk, metrik_y), (GENISLIK - kenar_bosluk, metrik_y)], fill=RENK_CIZGI_KOYU, width=1)

    m2 = ilan.get("m2")
    oda = ilan.get("oda")
    parcalar = []
    if m2:
        parcalar.append(f"{int(m2):,} m²".replace(",", "."))
    if oda:
        parcalar.append(str(oda))
    parcalar.append("SİLİVRİ BÖLGE UZMANLIĞI")

    font_metrik = _font_yukle(FONT_MONO, 22)
    draw.text((kenar_bosluk, metrik_y + 22), "  |  ".join(parcalar), font=font_metrik, fill=RENK_KURSUN)

    # Sağ Altta Kaydırma İşareti (Hook CTA)
    font_kaydir = _font_yukle(FONT_MONO_BOLD, 20)
    kaydir_metni = "01 / 03 >"
    bbox_k = draw.textbbox((0, 0), kaydir_metni, font=font_kaydir)
    kw = bbox_k[2] - bbox_k[0]
    draw.text((GENISLIK - kenar_bosluk - kw, metrik_y + 22), kaydir_metni, font=font_kaydir, fill=RENK_KIRMIZI)

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/ilan_kapak_{ilan.get('id')}.jpg")
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    img.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


@_gorsel_girdisi
def ilan_detay_slayti_ciz(ilan: Dict[str, Any], cikti_yolu: Optional[Path] = None) -> Path:
    """İlanın 2. slaytı (Mimari Detaylar & Yaşam Alanı): Çift fotoğraf kolajı + 4 avantaj."""
    img = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_MUREKKEP)
    draw = ImageDraw.Draw(img)

    kenar_bosluk = 65
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)

    # 1. Üst Bar
    font_ust = _font_yukle(FONT_MONO, 20)
    draw.text((kenar_bosluk, 60), "PORTFÖY DETAYLARI // SİLİVRİ", font=font_ust, fill=RENK_KURSUN)

    if LOGO_YATAY_ACIK.exists():
        try:
            logo = Image.open(LOGO_YATAY_ACIK).convert("RGBA")
            lw = 200
            lh = int(logo.height * (lw / logo.width))
            logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)
            img.paste(logo, (GENISLIK - kenar_bosluk - lw, 52), logo)
        except Exception as e:
            # Sessizce geçmiyoruz: marka varlığı yüklenemezse slayt
            # MARKASIZ üretilir ve kimse fark etmez.
            log.warning("logo (açık) yüklenemedi, slayt onsuz üretiliyor: %s", e)

    draw.line([(kenar_bosluk, 105), (GENISLIK - kenar_bosluk, 105)], fill=RENK_CIZGI_KOYU, width=1)

    # 2. Fotoğraf Kolajı (2. ve 3. fotoğraflar yan yana)
    gorseller = ilan.get("gorseller")
    if not gorseller:
        try:
            gorseller = json.loads(ilan.get("gorseller_json") or "[]")
        except Exception:
            gorseller = []

    foto_w = (kullanilabilir_w - 20) // 2
    foto_h = 440
    y_foto = 135

    f1 = _foto_indir_veya_ac(gorseller[1]) if len(gorseller) > 1 else None
    f2 = _foto_indir_veya_ac(gorseller[2]) if len(gorseller) > 2 else None

    if f1:
        c1 = ImageOps.fit(f1, (foto_w, foto_h), Image.Resampling.LANCZOS)
        img.paste(c1, (kenar_bosluk, y_foto))
        draw.rectangle([(kenar_bosluk, y_foto), (kenar_bosluk + foto_w, y_foto + foto_h)], outline=RENK_CIZGI_KOYU, width=1)
    else:
        draw.rectangle([(kenar_bosluk, y_foto), (kenar_bosluk + foto_w, y_foto + foto_h)], fill=RENK_MUREKKEP_2)

    if f2:
        c2 = ImageOps.fit(f2, (foto_w, foto_h), Image.Resampling.LANCZOS)
        img.paste(c2, (kenar_bosluk + foto_w + 20, y_foto))
        draw.rectangle([(kenar_bosluk + foto_w + 20, y_foto), (kenar_bosluk + kullanilabilir_w, y_foto + foto_h)], outline=RENK_CIZGI_KOYU, width=1)
    else:
        draw.rectangle([(kenar_bosluk + foto_w + 20, y_foto), (kenar_bosluk + kullanilabilir_w, y_foto + foto_h)], fill=RENK_MUREKKEP_2)

    # 3. Mülk Nitelikleri & Avantaj Kutuları (4 Maddelik Pafta)
    y_kutu = 620
    font_sec_baslik = _font_yukle(FONT_FRAUNCES, 34)
    draw.text((kenar_bosluk, y_kutu), "Öne Çıkan Nitelikler", font=font_sec_baslik, fill=RENK_KAGIT)

    try:
        ozellikler = json.loads(ilan.get("ozellikler_json") or "{}")
    except Exception:
        ozellikler = {}
    gercek_bilgiler = []
    if ilan.get("m2"):
        gercek_bilgiler.append(("Alan", f"{int(float(ilan['m2'])):,} m² ilan alanı".replace(",", ".")))
    if ilan.get("oda"):
        gercek_bilgiler.append(("Oda Bilgisi", str(ilan["oda"])))
    if ilan.get("tip"):
        gercek_bilgiler.append(("Mülk Türü", str(ilan["tip"]).replace("-", " ").title()))
    for anahtar, deger in ozellikler.items():
        if deger and len(gercek_bilgiler) < 4:
            gercek_bilgiler.append((str(anahtar)[:32], str(deger)[:72]))
    if len(gercek_bilgiler) < 4:
        konum = " · ".join(x for x in [ilan.get("mahalle"), ilan.get("ilce")] if x)
        if konum:
            gercek_bilgiler.append(("Konum", konum))
    yedek_bilgiler = [
        ("Güncel İlan", f"Ayrıntılar için portföy no #{ilan.get('id', '')}"),
        ("Bölge Uzmanlığı", "Silivri ve Trakya saha deneyimi"),
        ("Doğrudan İletişim", "Güncel durum ve randevu için ofisimizle görüşün"),
        ("EDM Portföyü", "Güncel ayrıntılar ilan sayfasında"),
    ]
    for yedek in yedek_bilgiler:
        if len(gercek_bilgiler) >= 4:
            break
        gercek_bilgiler.append(yedek)
    maddeler = [
        (f"{sira:02d}", baslik, aciklama)
        for sira, (baslik, aciklama) in enumerate(gercek_bilgiler[:4], start=1)
    ]

    ky = y_kutu + 60
    font_no = _font_yukle(FONT_MONO_BOLD, 22)
    font_mb = _font_yukle(FONT_FRAUNCES, 24)
    font_mt = _font_yukle(FONT_SANS, 19)

    for no, bas, aciklama in maddeler:
        # Sol kırmızı numara
        draw.text((kenar_bosluk, ky), no, font=font_no, fill=RENK_KIRMIZI)
        # Başlık
        draw.text((kenar_bosluk + 55, ky - 2), bas, font=font_mb, fill=RENK_KAGIT)
        # Açıklama
        draw.text((kenar_bosluk + 55, ky + 30), aciklama, font=font_mt, fill=RENK_KURSUN)
        # Alt ayrım çizgisi
        draw.line([(kenar_bosluk + 55, ky + 72), (GENISLIK - kenar_bosluk, ky + 72)], fill=RENK_CIZGI_KOYU, width=1)
        ky += 95

    # 4. Alt Bilgi
    alt_y = YUKSEKLIK - 110
    draw.line([(kenar_bosluk, alt_y), (GENISLIK - kenar_bosluk, alt_y)], fill=RENK_CIZGI_KOYU, width=1)
    draw.text((kenar_bosluk, alt_y + 25), "EDM YAPI & GAYRİMENKUL // SİLİVRİ", font=_font_yukle(FONT_MONO, 20), fill=RENK_KURSUN)
    draw.text((GENISLIK - kenar_bosluk - 100, alt_y + 25), "02 / 03 >", font=_font_yukle(FONT_MONO_BOLD, 20), fill=RENK_KIRMIZI)

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/ilan_detay_{ilan.get('id')}.jpg")
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    img.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


@_gorsel_girdisi
def ilan_kapanis_slayti_ciz(ilan: Dict[str, Any], cikti_yolu: Optional[Path] = None) -> Path:
    """İlanın 3. slaytı (Yatırım Danışmanı & İletişim Kartı): Sıcak kağıt, güven veren kurumsal kimlik."""
    img = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_KAGIT)
    draw = ImageDraw.Draw(img)

    kenar_bosluk = 80
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)

    # 1. Üst Şerit
    draw.line([(kenar_bosluk, 90), (GENISLIK - kenar_bosluk, 90)], fill=RENK_CIZGI, width=1)
    font_mono_ust = _font_yukle(FONT_MONO, 22)
    draw.text((kenar_bosluk, 55), "EDM YAPI & GAYRİMENKUL // İLETİŞİM", font=font_mono_ust, fill=RENK_KURSUN)

    # 2. Vurucu Başlık (Fraunces Serif)
    font_baslik = _font_yukle(FONT_FRAUNCES, 62)
    draw.text((kenar_bosluk, 200), "Detaylı bilgi ve", font=font_baslik, fill=RENK_MUREKKEP)
    draw.text((kenar_bosluk, 280), "yerinde sunum için.", font=font_baslik, fill=RENK_KIRMIZI)

    # Açıklama
    font_aciklama = _font_yukle(FONT_SANS, 28)
    draw.text(
        (kenar_bosluk, 385),
        "Portföyümüzdeki bu gayrimenkulün tapu, imar ve güncel piyasa\nkoşullarını yerinde birlikte değerlendirelim.",
        font=font_aciklama,
        fill=RENK_MUREKKEP,
    )

    # 3. Danışman Kartı (Beyaz Lüks Kutu)
    kutu_y = 520
    draw.rectangle([(kenar_bosluk, kutu_y), (GENISLIK - kenar_bosluk, kutu_y + 390)], fill=RENK_BEYAZ, outline=RENK_CIZGI)
    draw.rectangle([(kenar_bosluk, kutu_y), (kenar_bosluk + 8, kutu_y + 390)], fill=RENK_KIRMIZI)

    font_danisman_etiket = _font_yukle(FONT_MONO_BOLD, 22)
    draw.text((kenar_bosluk + 45, kutu_y + 40), "YATIRIM DANIŞMANINIZ", font=font_danisman_etiket, fill=RENK_KIRMIZI)

    danisman_adi = "Doğukan Özdoğan"
    d_raw = str(ilan.get("danisman", "")).lower()
    if "metin" in d_raw:
        danisman_adi = "Metin Özdoğan"
    elif "ercan" in d_raw:
        danisman_adi = "Ercan Taşdemirler"
    elif "basri" in d_raw:
        danisman_adi = "Basri Çelik"

    font_danisman_ad = _font_yukle(FONT_FRAUNCES, 48)
    draw.text((kenar_bosluk + 45, kutu_y + 85), danisman_adi, font=font_danisman_ad, fill=RENK_MUREKKEP)

    font_tel = _font_yukle(FONT_MONO_BOLD, 40)
    draw.text((kenar_bosluk + 45, kutu_y + 170), "0 212 727 2955", font=font_tel, fill=RENK_MUREKKEP)

    draw.line([(kenar_bosluk + 45, kutu_y + 245), (GENISLIK - kenar_bosluk - 45, kutu_y + 245)], fill=RENK_CIZGI, width=1)

    font_adres = _font_yukle(FONT_SANS, 24)
    draw.text((kenar_bosluk + 45, kutu_y + 270), "Alibey Mah. Albay Yunus Dirik Cad. No: 58/A, Silivri", font=font_adres, fill=RENK_KURSUN)
    draw.text((kenar_bosluk + 45, kutu_y + 315), "info@edmyapigayrimenkul.com · edmyapigayrimenkul.com", font=font_adres, fill=RENK_MUREKKEP)

    # 4. Alt Logo (Normal Yatay Logo)
    if LOGO_YATAY.exists():
        try:
            logo = Image.open(LOGO_YATAY).convert("RGBA")
            lw = 380
            lh = int(logo.height * (lw / logo.width))
            logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)
            img.paste(logo, (kenar_bosluk, YUKSEKLIK - 240), logo)
        except Exception as e:
            # Sessizce geçmiyoruz: marka varlığı yüklenemezse slayt
            # MARKASIZ üretilir ve kimse fark etmez.
            log.warning("logo (koyu) yüklenemedi, slayt onsuz üretiliyor: %s", e)

    font_slogan = _font_yukle(FONT_MONO, 20)
    draw.text((kenar_bosluk, YUKSEKLIK - 90), "EDM YAPI & GAYRİMENKUL · YATIRIM ORTAĞINIZ", font=font_slogan, fill=RENK_KURSUN)

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/ilan_kapanis_{ilan.get('id')}.jpg")
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    img.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


# =========================================================================
# 2. OTORİTE & HABER SLAYTI ÜRETİCİLERİ (DİNAMİK ŞABLON MOTORU)
# =========================================================================


# =========================================================================
# DİZGİ KATMANI — Kutusuz, Tek Fikirli Slaytlar
#
# Eski iç slaytlar bir karede iki dolu kart + kaydet şeridi taşıyordu: ~60 kelime,
# çerçeveli kutular, 28px gövde. Akışta okunmuyordu. Yeni kurallar:
#   - Kutu yok. Hiyerarşi tipografiyle ve sol vurgu çizgisiyle kurulur
#   - Gövde 36-40px (eskiden 28-29px)
#   - Bir karede tek fikir; içerik uzunsa slayt sayısı artar (karma mimari)
#   - "Kaydet" çağrısı yalnızca kapanış slaytında
# =========================================================================

# Zemin varyantları. Amaç dekorasyon değil ANLAM ve KONTRAST:
#   murekkep → nötr, adım ve açıklama slaytları
#   kagit    → aydınlık, "doğrusu / çözüm" slaytları. Koyu akıştan sonra nefes aldırır
#   kirmizi  → yalnızca kritik uyarı. Carousel başına EN FAZLA BİR kez
#
# Marka oranı %70 nötr / %25 mürekkep / %5 kırmızı olduğu için kırmızı zemin
# tam sayfa kullanıldığında oranı hızla bozar; planlayıcı bunu tek slaytla sınırlar.
ZEMINLER: Dict[str, Dict[str, Any]] = {
    "murekkep": {
        "zemin": RENK_MUREKKEP,
        "ana": RENK_BEYAZ,
        "govde": RENK_KURSUN_ACIK,
        "vurgu": RENK_KIRMIZI_CANLI,
        "silik": RENK_KURSUN,
        "cizgi": RENK_CIZGI_KOYU,
        "rozet_bg": RENK_MUREKKEP_2,
        "rozet_fg": RENK_BEYAZ,
        "logo_beyaz": True,
    },
    "kagit": {
        "zemin": RENK_KAGIT,
        "ana": RENK_MUREKKEP,
        "govde": (58, 60, 66),
        # Kırmızı açık zeminde kontrastı 4,4:1 — yalnızca 18px üstü metinde
        # kullanılır. Gövde metninde asla vurgu rengi kullanma.
        "vurgu": RENK_KIRMIZI_DERIN,
        "silik": (122, 124, 130),
        "cizgi": RENK_CIZGI,
        "rozet_bg": RENK_MUREKKEP,
        "rozet_fg": RENK_BEYAZ,
        "logo_beyaz": False,
    },
    "kirmizi": {
        "zemin": RENK_KIRMIZI_DERIN,
        "ana": RENK_BEYAZ,
        "govde": (255, 228, 230),
        "vurgu": RENK_BEYAZ,
        "silik": (255, 190, 195),
        "cizgi": (232, 90, 100),
        "rozet_bg": RENK_MUREKKEP,
        "rozet_fg": RENK_BEYAZ,
        "logo_beyaz": True,
        # Kırmızı zeminde kırmızı difüzyon gölgesi leke gibi görünüyor
        "logo_golge": False,
    },
}

# İçerik dikeyde ortalanır ama optik denge için merkezden bir miktar yukarı
# alınır: tam ortalanan blok dikey karede aşağı kaymış görünür.
OPTIK_KALDIRMA = 26

# Desteklenen tuval ölçüleri.
TUVAL_OLCULERI: Dict[str, Tuple[int, int]] = {
    "besleme": (1080, 1350),   # 4:5 — Instagram/Facebook carousel
    "story": (1080, 1920),     # 9:16 — Reels, Shorts, TikTok, Story
    "yatay": (1920, 1080),     # 16:9 — YouTube video, web banner, TV ekranı
    "16_9": (1920, 1080),
}


@contextmanager
def tuval(olcu: Any) -> Iterator[Tuple[int, int]]:
    """Çizim boyutunu geçici olarak değiştirir.

    Bu modülün tamamı GENISLIK/YUKSEKLIK modül değişkenlerine dayanıyor; her
    fonksiyona boyut parametresi geçirmek 900 satırı dolaşmak demekti. Bağlam
    yöneticisi ölçüyü kuşatır ve `finally` ile HER DURUMDA geri alır — çizim
    ortasında istisna çıksa bile sonraki çağrı doğru boyutta başlar.

    Tek iş parçacıklı cron ve CLI için güvenli; eşzamanlı çizim yapılacaksa
    bu yaklaşım süreç başına izole edilmeli.

        with tuval("story"):
            slayt_tek_fikir(...)
    """
    global GENISLIK, YUKSEKLIK
    if isinstance(olcu, str):
        if olcu not in TUVAL_OLCULERI:
            raise ValueError(
                f"Bilinmeyen tuval ölçüsü: {olcu!r}. Seçenekler: {sorted(TUVAL_OLCULERI)}"
            )
        en, boy = TUVAL_OLCULERI[olcu]
    else:
        en, boy = olcu
        if not (320 <= int(en) <= 4096 and 320 <= int(boy) <= 4096):
            raise ValueError(f"Tuval ölçüsü makul aralıkta değil: {en}x{boy}")
        en, boy = int(en), int(boy)

    onceki = (GENISLIK, YUKSEKLIK)
    GENISLIK, YUKSEKLIK = en, boy
    try:
        yield (en, boy)
    finally:
        GENISLIK, YUKSEKLIK = onceki


def _yerlesim() -> Dict[str, int]:
    """Geçerli tuval boyutundan yerleşim sınırlarını türetir.

    Sabit sayılar yerine türetme, tek bir çizim kodunun hem 4:5 besleme, hem
    9:16 dikey story hem de 16:9 yatay üretmesini sağlıyor.
    """
    if YUKSEKLIK >= 1700:
        # 9:16 Dikey — Meta Story/Reels güvenli alanı: üstte profil & X butonu (250px), altta mesaj barı (250px)
        kenar = max(48, round(GENISLIK * 0.072))
        kronik_ust, ust, icerik_alt_payi, bar_payi = 260, 390, 260, 240
    elif GENISLIK > YUKSEKLIK:
        # 16:9 Yatay (1920x1080) — ferah genişlik, daha alçak yükseklik
        kenar = max(60, round(GENISLIK * 0.055))
        kronik_ust, ust, icerik_alt_payi, bar_payi = 50, 175, 120, 85
    else:
        # 4:5 Dikey Besleme (1080x1350)
        kenar = max(48, round(GENISLIK * 0.072))
        kronik_ust, ust, icerik_alt_payi, bar_payi = 62, 212, 135, 100

    alt_bar = YUKSEKLIK - bar_payi
    icerik_alt = YUKSEKLIK - icerik_alt_payi
    return {
        "kenar": kenar,
        "kronik_ust": kronik_ust,   # rozet ve logonun üst hizası
        "ust": ust,                 # içerik alanının başlangıcı
        "alt": icerik_alt,
        "alt_bar": alt_bar,
        # Kapak manşeti ve tek fikirli slaytların ortak taban çizgisi
        "taban": icerik_alt - (40 if YUKSEKLIK >= 1700 else 95),
    }


def _rozet_kirp(metin: Any, azami: int) -> str:
    """Rozet metnini kelime sınırında kısaltır.

    Ham dilimleme kelimeyi ortadan kesiyordu ("...emeyebilec"); şeritte yarım
    kelime görmek metnin bozuk olduğu izlenimi veriyor.
    """
    temiz = _temizle_tipografi("" if metin is None else str(metin))
    if len(temiz) <= azami:
        return temiz
    kesik = temiz[:azami - 1]
    bosluk = kesik.rfind(" ")
    if bosluk >= azami // 2:
        kesik = kesik[:bosluk]
    return kesik.rstrip(" ,.;:/-") + "…"


def _zemin_uret(zemin_adi: str = "murekkep", olcu: str = "besleme") -> Image.Image:
    """Belirtilen ölçü ve zemin temasına göre boş RGB tuval üretir."""
    p = ZEMINLER.get(zemin_adi, ZEMINLER["murekkep"])
    w, h = TUVAL_OLCULERI.get(olcu, (GENISLIK, YUKSEKLIK))
    return Image.new("RGB", (w, h), p["zemin"])


def _slayt_cercevesi(
    zemin_adi: str,
    rozet: str,
    alt_metin: str,
    sayfa: str,
) -> Tuple[Image.Image, ImageDraw.ImageDraw, Dict[str, Any]]:
    """Tüm iç slaytların ortak çerçevesini çizer: zemin, rozet, logo, alt bar.

    İçerik alanını `_yerlesim()["ust"]` ile `["alt"]` arasında boş bırakır;
    çağıran fonksiyon orayı doldurur.
    """
    yer = _yerlesim()
    kenar = yer["kenar"]
    p = ZEMINLER.get(zemin_adi, ZEMINLER["murekkep"])
    canvas = Image.new("RGB", (GENISLIK, YUKSEKLIK), p["zemin"])
    canvas = _filigran_uygula(canvas, acik_zemin=(zemin_adi == "kagit"))
    draw = ImageDraw.Draw(canvas)

    ku = yer["kronik_ust"]
    _rozet_ciz(draw, kenar, ku, _rozet_kirp(rozet, 44),
               bg_color=p["rozet_bg"], fg_color=p["rozet_fg"], font_boyut=20)
    _logo_yerlestir(
        canvas,
        beyaz=p["logo_beyaz"],
        y=ku - 5,
        lw=285,  # Her sayfada tam olarak aynı ikon boyutu (kullanıcı direktifi)
        golge=True,
        kirmizi_zemin=(zemin_adi == "kirmizi"),
    )

    alt_y = yer["alt_bar"]
    draw.line([(kenar, alt_y), (GENISLIK - kenar, alt_y)], fill=p["cizgi"], width=1)
    draw.text((kenar, alt_y + 26), _temizle_tipografi(alt_metin),
              font=_font_yukle(FONT_MONO, 19), fill=p["silik"])
    if sayfa and str(sayfa).strip():
        sf = _font_yukle(FONT_MONO_BOLD, 19)
        sw = draw.textbbox((0, 0), sayfa, font=sf)[2]
        draw.text((GENISLIK - kenar - sw, alt_y + 26), sayfa, font=sf, fill=p["vurgu"])

    return canvas, draw, p


def _fikir_blogu_olc(
    draw: ImageDraw.ImageDraw,
    etiket: str,
    baslik: str,
    govde: str,
    genislik: int,
    baslik_punto: int = 52,
    govde_punto: int = 38,
) -> Dict[str, Any]:
    """Bir "fikir" bloğunun fontlarını ve toplam yüksekliğini hesaplar.

    Kutu olmadığı için blok yüksekliği tamamen metinden gelir; ölçmeden
    yerleştirmek dikey dengeyi bozar.
    """
    b_font, b_satirlar = _govde_sigdir(baslik, FONT_SANS_BOLD, baslik_punto, 38, genislik, 3, draw)
    g_font, g_satirlar = _govde_sigdir(govde, FONT_SANS_MEDIUM, govde_punto, 29, genislik, 6, draw)

    b_aralik = int(b_font.size * 1.22)
    g_aralik = int(g_font.size * 1.42)

    h = 0
    if etiket:
        h += 46           # rozet yüksekliği + altındaki pay
    h += len(b_satirlar) * b_aralik
    h += 18               # başlık-gövde arası
    h += len(g_satirlar) * g_aralik

    return {
        "etiket": etiket, "b_font": b_font, "b_satirlar": b_satirlar, "b_aralik": b_aralik,
        "g_font": g_font, "g_satirlar": g_satirlar, "g_aralik": g_aralik, "h": h,
    }


def _blogu_sigdir(olcu: Dict[str, Any], azami_yukseklik: int) -> Dict[str, Any]:
    """Ölçülmüş bloğu verilen yüksekliğe kilitler.

    Sığdırma puntoyu zaten küçültüyor ama 10 kat uzunlukta içerikte bu yetmiyor
    ve blok alt bara giriyordu — gövde metni alt şerit yazısının üstüne biniyordu.
    Böyle bir girdide kesmek tek makul sonuç: üst üste binmiş metin, kesilmiş
    metinden daha kötü. Son satıra "…" konur ki kesildiği belli olsun.

    Bütçeler uygulandığında (ICERIK-SISTEMI.md §5) bu yol hiç çalışmaz.
    """
    if olcu["h"] <= azami_yukseklik or not olcu["g_satirlar"]:
        return olcu

    fazla = olcu["h"] - azami_yukseklik
    dusecek = min(len(olcu["g_satirlar"]), -(-fazla // olcu["g_aralik"]))
    kalan = olcu["g_satirlar"][:max(0, len(olcu["g_satirlar"]) - dusecek)]
    if kalan:
        kalan[-1] = kalan[-1].rstrip(" ,.;:") + "…"

    olcu = dict(olcu)
    olcu["g_satirlar"] = kalan
    olcu["h"] = olcu["h"] - (dusecek * olcu["g_aralik"])
    return olcu


def _fikir_blogu_ciz(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    olcu: Dict[str, Any],
    x: int,
    y: int,
    p: Dict[str, Any],
    vurgu_cizgisi: Optional[Tuple[int, int, int]] = None,
    etiket_bg: Optional[Tuple[int, int, int]] = None,
) -> int:
    """Ölçülmüş fikir bloğunu çizer ve bittiği Y'yi döner."""
    metin_x = x
    if vurgu_cizgisi:
        # Kutu yerine sol vurgu çizgisi: aynı gruplama işini kalabalık yapmadan görür
        draw.rounded_rectangle([(x, y), (x + 6, y + olcu["h"])], radius=3, fill=vurgu_cizgisi)
        metin_x = x + 34

    cy = y
    if olcu["etiket"]:
        _rozet_ciz(draw, metin_x, cy, olcu["etiket"][:44],
                   bg_color=etiket_bg or p["rozet_bg"], fg_color=RENK_BEYAZ, font_boyut=18)
        cy += 46

    for satir in olcu["b_satirlar"]:
        draw.text((metin_x, cy), satir, font=olcu["b_font"], fill=p["ana"])
        cy += olcu["b_aralik"]

    cy += 18
    for satir in olcu["g_satirlar"]:
        draw.text((metin_x, cy), satir, font=olcu["g_font"], fill=p["govde"])
        cy += olcu["g_aralik"]

    return cy


def _adim_numarasi(ham: Any) -> str:
    """Adım numarasını iki haneye indirger.

    Model bazen "01" yerine "Adım 1" veya boş değer gönderiyor. 150 punto
    Fraunces ile çizilen bu alan hiç sınırlanmıyordu ve uzun bir değer kareyi
    sağdan taşırıyordu (stres testi: turkce_glif_yuku / gecersiz_deger).
    """
    metin = "" if ham is None else str(ham)
    rakamlar = "".join(ch for ch in metin if ch.isdigit())
    if rakamlar:
        return rakamlar[:2].zfill(2)
    return "01"


def slayt_tek_fikir(
    zemin_adi: str,
    rozet: str,
    etiket: str,
    baslik: str,
    govde: str,
    alt_metin: str,
    sayfa: str,
    cikti_yolu: Path,
    vurgu_cizgili: bool = True,
) -> Path:
    """Bir karede TEK fikir. Büyük tipografi, geniş boşluk, kutu yok."""
    canvas, draw, p = _slayt_cercevesi(zemin_adi, rozet, alt_metin, sayfa)
    yer = _yerlesim()
    kenar = yer["kenar"]
    genislik = GENISLIK - (2 * kenar) - (40 if vurgu_cizgili else 0)

    baslik_punto = 74 if YUKSEKLIK >= 1700 else 66
    govde_punto = 42 if YUKSEKLIK >= 1700 else 40
    olcu = _fikir_blogu_olc(draw, etiket, baslik, govde, genislik,
                            baslik_punto=baslik_punto, govde_punto=govde_punto)
    olcu = _blogu_sigdir(olcu, yer["alt"] - yer["ust"])
    if YUKSEKLIK >= 1700:
        alan = yer["alt"] - yer["ust"]
        y = yer["ust"] + max(0, (alan - olcu["h"]) // 2 - (OPTIK_KALDIRMA + 20))
    else:
        y = max(yer["ust"], yer["taban"] - olcu["h"])

    _fikir_blogu_ciz(canvas, draw, olcu, kenar, y, p,
                     vurgu_cizgisi=p["vurgu"] if vurgu_cizgili else None,
                     etiket_bg=p["rozet_bg"])

    cikti_yolu = Path(cikti_yolu)
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


def slayt_ikili_fikir(
    zemin_adi: str,
    rozet: str,
    fikirler: List[Dict[str, str]],
    alt_metin: str,
    sayfa: str,
    cikti_yolu: Path,
) -> Path:
    """İki fikir tek karede — yalnızca metin kısa olduğunda (karma mimari).

    Ayrım kutuyla değil, aradaki ince çizgi ve sol vurgu renkleriyle yapılır.
    """
    canvas, draw, p = _slayt_cercevesi(zemin_adi, rozet, alt_metin, sayfa)
    yer = _yerlesim()
    kenar = yer["kenar"]
    genislik = GENISLIK - (2 * kenar) - 40

    olculer = [
        _fikir_blogu_olc(draw, f.get("etiket", ""), f.get("baslik", ""), f.get("govde", ""),
                         genislik, baslik_punto=54, govde_punto=36)
        for f in fikirler
    ]
    AYRAC = 54
    alan = yer["alt"] - yer["ust"] - (AYRAC * (len(olculer) - 1))
    if olculer:
        olculer = [_blogu_sigdir(o, alan // len(olculer)) for o in olculer]
    toplam = sum(o["h"] for o in olculer) + (AYRAC * (len(olculer) - 1))
    y = yer["ust"] + max(0, ((yer["alt"] - yer["ust"]) - toplam) // 2 - OPTIK_KALDIRMA)

    for i, (olcu, fikir) in enumerate(zip(olculer, fikirler)):
        kirmizi_mi = fikir.get("renk") == "kirmizi"
        cizgi = p["vurgu"] if kirmizi_mi else (RENK_YESIL if zemin_adi != "kagit" else (22, 120, 58))
        etiket_bg = (176, 16, 26) if kirmizi_mi else (20, 118, 56)
        son_y = _fikir_blogu_ciz(canvas, draw, olcu, kenar, y, p,
                                 vurgu_cizgisi=cizgi, etiket_bg=etiket_bg)
        if i < len(olculer) - 1:
            ay = son_y + (AYRAC // 2)
            draw.line([(kenar, ay), (GENISLIK - kenar, ay)], fill=p["cizgi"], width=1)
        y = son_y + AYRAC

    cikti_yolu = Path(cikti_yolu)
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


def slayt_adim(
    zemin_adi: str,
    rozet: str,
    no: str,
    baslik: str,
    govde: str,
    toplam_adim: int,
    alt_metin: str,
    sayfa: str,
    cikti_yolu: Path,
    onemli_not: Optional[str] = None,
) -> Path:
    """Tek adım, tam sayfa. Dinamik ilerleme çubuğu (progress track), devasa numara
    ve isteğe bağlı sade önemli not kutusu ile tasarlanmıştır."""
    canvas, draw, p = _slayt_cercevesi(zemin_adi, rozet, alt_metin, sayfa)

    yer = _yerlesim()
    kenar = yer["kenar"]
    genislik = GENISLIK - (2 * kenar)

    # 1. Güvenli Adım ve İlerleme Çubuğu Hesabı (Sıfıra bölünme ve uç değer korumalı)
    try:
        toplam_adim_guvenli = max(1, min(20, int(toplam_adim) if str(toplam_adim).strip().lstrip("-").isdigit() else 3))
    except Exception:
        toplam_adim_guvenli = 3

    no_str = _adim_numarasi(no)
    try:
        mevcut_no = max(1, min(toplam_adim_guvenli, int(no_str) if no_str.isdigit() else 1))
    except Exception:
        mevcut_no = 1

    bar_y = yer["ust"] - 30
    seg_gap = 12 if toplam_adim_guvenli <= 6 else 6
    seg_w = max(4, (genislik - (seg_gap * (toplam_adim_guvenli - 1))) // toplam_adim_guvenli)
    for s_idx in range(toplam_adim_guvenli):
        sx = kenar + s_idx * (seg_w + seg_gap)
        c = p["vurgu"] if s_idx < mevcut_no else (55, 62, 78)
        draw.rounded_rectangle([(sx, bar_y), (sx + seg_w, bar_y + 6)], radius=3, fill=c)

    # 2. Devasa Numara ve İçerik
    n_font = _font_yukle(FONT_FRAUNCES, 150)
    no_gosterim = f"0{mevcut_no}"[-2:]

    not_metni = _temizle_tipografi(str(onemli_not or "")).strip()
    ek_alan = 150 if not_metni else 0

    baslik_punto = 70 if YUKSEKLIK >= 1700 else 64
    govde_punto = 42 if YUKSEKLIK >= 1700 else 40
    olcu = _fikir_blogu_olc(draw, "", baslik, govde, genislik, baslik_punto=baslik_punto, govde_punto=govde_punto)
    n_yuk = 150
    olcu = _blogu_sigdir(olcu, yer["alt"] - yer["ust"] - n_yuk - 26 - ek_alan)
    toplam = n_yuk + 26 + olcu["h"] + ek_alan
    if YUKSEKLIK >= 1700:
        alan = yer["alt"] - yer["ust"]
        y = yer["ust"] + max(0, (alan - toplam) // 2 - OPTIK_KALDIRMA)
    else:
        y = max(yer["ust"], yer["taban"] - toplam)

    draw.text((kenar, y - 30), no_gosterim, font=n_font, fill=p["vurgu"])
    kf = _font_yukle(FONT_MONO_BOLD, 20)
    nw = draw.textbbox((0, 0), no_gosterim, font=n_font)[2]
    draw.text((kenar + nw + 22, y + 46), f"/ {str(toplam_adim_guvenli).zfill(2)} ADIM", font=kf, fill=p["silik"])

    son_y = _fikir_blogu_ciz(canvas, draw, olcu, kenar, y + n_yuk + 26, p, vurgu_cizgisi=None)

    # 3. Sade "ÖNEMLİ NOT:" Kutusu
    if not_metni:
        tip_y = son_y + 36
        tip_h = 115
        if tip_y + tip_h < yer["alt_bar"] - 8:
            draw.rounded_rectangle([(kenar, tip_y), (kenar + genislik, tip_y + tip_h)], radius=10, fill=(18, 22, 30), outline=(42, 48, 62), width=1)
            draw.rounded_rectangle([(kenar, tip_y), (kenar + 5, tip_y + tip_h)], radius=2, fill=p["vurgu"])
            draw.text((kenar + 22, tip_y + 18), "ÖNEMLİ NOT:", font=_font_yukle(FONT_MONO_BOLD, 17), fill=p["vurgu"])
            ty = tip_y + 48
            f_tip = _font_yukle(FONT_SANS_MEDIUM, 23)
            for s in _metin_sar(not_metni, f_tip, genislik - 44, draw)[:2]:
                draw.text((kenar + 22, ty), s, font=f_tip, fill=(215, 220, 230))
                ty += 32

    cikti_yolu = Path(cikti_yolu)
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


def slayt_adimlar_toplu(
    zemin_adi: str,
    rozet: str,
    maddeler: List[Dict[str, Any]],
    alt_metin: str,
    sayfa: str,
    cikti_yolu: Path,
) -> Path:
    """Adımların tamamı tek karede — yalnızca hepsi kısaysa (karma mimari)."""
    canvas, draw, p = _slayt_cercevesi(zemin_adi, rozet, alt_metin, sayfa)
    yer = _yerlesim()
    kenar = yer["kenar"]

    # 1. Progress Bar (Adım İlerleme Çubuğu)
    toplam_m = max(1, len(maddeler))
    bar_y = yer["ust"] - 30
    seg_gap = 12 if toplam_m <= 6 else 6
    seg_w = max(4, (GENISLIK - (2 * kenar) - (seg_gap * (toplam_m - 1))) // toplam_m)
    for s_idx in range(toplam_m):
        sx = kenar + s_idx * (seg_w + seg_gap)
        draw.rounded_rectangle([(sx, bar_y), (sx + seg_w, bar_y + 6)], radius=3, fill=p["vurgu"])

    n_font = _font_yukle(FONT_FRAUNCES, 60)
    en_genis_no = max(
        draw.textbbox((0, 0), _adim_numarasi(m.get("no")), font=n_font)[2]
        for m in maddeler
    )
    no_alan = en_genis_no + 26
    genislik = GENISLIK - (2 * kenar) - no_alan

    olculer = [
        _fikir_blogu_olc(draw, "", m.get("baslik", ""), m.get("aciklama", ""),
                         genislik, baslik_punto=48, govde_punto=34)
        for m in maddeler
    ]
    ARALIK = 46
    alan = yer["alt"] - yer["ust"] - (ARALIK * (len(olculer) - 1))
    if olculer:
        olculer = [_blogu_sigdir(o, alan // len(olculer)) for o in olculer]
    toplam = sum(o["h"] for o in olculer) + (ARALIK * (len(olculer) - 1))
    y = yer["ust"] + max(0, ((yer["alt"] - yer["ust"]) - toplam) // 2 - OPTIK_KALDIRMA)

    for m, olcu in zip(maddeler, olculer):
        no = _adim_numarasi(m.get("no"))
        draw.text((kenar, y - 6), no, font=n_font, fill=p["vurgu"])
        _fikir_blogu_ciz(canvas, draw, olcu, kenar + no_alan, y, p, vurgu_cizgisi=None)
        y += olcu["h"] + ARALIK

    cikti_yolu = Path(cikti_yolu)
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


def _sayfa_etiketi(veri: Dict[str, Any], sira: int) -> str:
    """Slayt sayacını gerçek slayt sayısından üretir.
    Dikey video (Reels/Shorts/Story) formatında 'KAYDIRIN' veya sayaç yazılmaz.
    """
    olcu = str(veri.get("olcu") or "").lower()
    if YUKSEKLIK >= 1700 or olcu in ("story", "reels", "shorts", "dikey") or veri.get("_video_modu"):
        return ""
    toplam = veri.get("_toplam_slayt") or 4
    etiket = f"{str(sira).zfill(2)} / {str(toplam).zfill(2)}"
    return etiket if sira >= toplam else f"{etiket}  ›  KAYDIRIN"


@_gorsel_girdisi
def otorite_slayt_1_kapak(veri: Dict[str, Any], cikti_yolu: Optional[Path] = None) -> Path:
    """Otorite / Haber 1. Slaytı (Hero Hook Kapak):
    Metin uzunluğuna göre dinamik perdesi, difüzyon gölgesi ve iki tonlu manşetiyle
    0.8 saniyede durduran kanca kapak üretir.
    """
    kenar_bosluk = 70
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)

    # 1. Arka Plan
    kategori_kodu = veri.get("kategori_kodu") or veri.get("kategori", "HUKUK")
    foto_url = veri.get("gorsel_url") or veri.get("foto_url")
    tohum = veri.get("manset") or veri.get("manset_vurgu") or veri.get("id") or veri.get("orijinal_baslik")
    if veri.get("saf_editoryal"):
        canvas = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_MUREKKEP)
    else:
        haric = [veri.get("onceki_foto")] if veri.get("foto_degistir") and veri.get("onceki_foto") else None
        konu_metni = " ".join(str(veri.get(k) or "") for k in ("manset_parca_1", "manset_vurgu", "manset_parca_2", "manset", "spot", "rozet_metni"))
        canvas = _temiz_arkaplan_al(kategori_kodu, foto_url, tohum=tohum, haric_tut=haric, konu_metni=konu_metni)

    # 2. Manşet ve Başlık Verisini Analiz Et
    manset_ham = veri.get("manset", "")
    manset_p1 = veri.get("manset_parca_1")
    manset_vurgu = veri.get("manset_vurgu")
    manset_p2 = veri.get("manset_parca_2")

    dummy_img = Image.new("RGB", (10, 10))
    dummy_draw = ImageDraw.Draw(dummy_img)

    p1_str = tr_ilk_buyuk(_temizle_tipografi(str(manset_p1)).strip()) if manset_p1 else ""
    vurgu_str = _temizle_tipografi(str(manset_vurgu)).strip().replace("i", "İ").replace("ı", "I").upper() if manset_vurgu else ""
    p2_str = tr_ilk_buyuk(_temizle_tipografi(str(manset_p2)).strip()) if manset_p2 else ""

    if not (p1_str or vurgu_str or p2_str) and manset_ham:
        ham_satirlar = [s.strip() for s in str(manset_ham).split("\n") if s.strip()]
        if len(ham_satirlar) == 1:
            p1_str = ham_satirlar[0]
        elif len(ham_satirlar) == 2:
            p1_str = ham_satirlar[0]
            vurgu_str = ham_satirlar[1].upper()
        else:
            p1_str = ham_satirlar[0]
            vurgu_str = ham_satirlar[1].upper()
            p2_str = " ".join(ham_satirlar[2:])

    # Tipografik Hiyerarşi ve Kapsül Ölçüleri:
    pad_x = 22
    pad_y = 12
    gap_v = 16

    olcum = " ".join(str(p) for p in (p1_str, vurgu_str, p2_str) if p)
    uzunluk = len(olcum)
    if uzunluk <= 30:
        font_boyut = 96
    elif uzunluk <= 55:
        font_boyut = 88
    else:
        font_boyut = 80

    # Kırmızı vurgu kutusunun veya uzun manşet satırlarının tuvalden taşmasını önle
    while font_boyut > 56:
        f_test = _font_yukle(FONT_SANS_BOLD, font_boyut)
        fits = True
        if vurgu_str:
            bbv_t = dummy_draw.textbbox((0, 0), vurgu_str, font=f_test)
            if (bbv_t[2] - bbv_t[0]) + (2 * pad_x) > kullanilabilir_w:
                fits = False
        if p1_str:
            bb1_t = dummy_draw.textbbox((0, 0), p1_str, font=f_test)
            if (bb1_t[2] - bb1_t[0]) > kullanilabilir_w:
                fits = False
        if p2_str:
            bb2_t = dummy_draw.textbbox((0, 0), p2_str, font=f_test)
            if (bb2_t[2] - bb2_t[0]) > kullanilabilir_w:
                fits = False
        if fits:
            break
        font_boyut -= 2

    font_manset = _font_yukle(FONT_SANS_BOLD, font_boyut)

    # Manşet satırları: her parça en küçük puntoda da tek satıra sığmıyorsa
    # KIRILIR (eskiden tek satır halinde tuvalin dışına çiziliyordu; stres
    # testinde x=3870'e kadar). Vurgu kapsülü de satır satır kapsüle bölünür.
    manset_satirlari: List[Tuple[str, bool]] = []
    if p1_str:
        manset_satirlari += [(s, False) for s in _metin_sar(p1_str, font_manset, kullanilabilir_w, dummy_draw)]
    if vurgu_str:
        manset_satirlari += [(s, True) for s in _metin_sar(vurgu_str, font_manset, kullanilabilir_w - 2 * pad_x, dummy_draw)]
    if p2_str:
        manset_satirlari += [(s, False) for s in _metin_sar(p2_str, font_manset, kullanilabilir_w, dummy_draw)]
    if len(manset_satirlari) > 5:
        raise TasmaHatasi(f"Kapak manşeti {len(manset_satirlari)} satıra çıktı ({len(olcum)} karakter)")

    # Tutarlı satır ritmi: bütün satırlar aynı mürekkep yüksekliğiyle ölçülür
    ref = dummy_draw.textbbox((0, 0), "ÇĞİÖŞÜ ağy", font=font_manset)
    ref_ust, satir_h = ref[1], ref[3] - ref[1]
    vref = dummy_draw.textbbox((0, 0), "ÇĞİÖŞÜ", font=font_manset)
    v_ink_h = vref[3] - vref[1]
    box_h = v_ink_h + (2 * pad_y)
    h_baslik = sum((box_h if v else satir_h) for _, v in manset_satirlari) + gap_v * max(0, len(manset_satirlari) - 1)

    # 3. Spot: sığan en büyük punto (36 → 28, en fazla 5 satır). Eskiden 36px'te
    # 4 satırdan sonrası SESSİZCE kesiliyordu.
    spot_ham = veri.get("spot") or veri.get("slayt_1_spot") or veri.get("detay_metni", "")
    spot_satirlari: List[str] = []
    spot_satir_h = 50
    font_spot = _font_yukle(FONT_SANS_MEDIUM, 36)
    if str(spot_ham or "").strip():
        for punto in (36, 34, 32, 30, 28):
            font_spot = _font_yukle(FONT_SANS_MEDIUM, punto)
            spot_satirlari = _metin_sar(spot_ham, font_spot, kullanilabilir_w - 60, dummy_draw)
            spot_satir_h = int(punto * 1.39)
            if len(spot_satirlari) <= (4 if punto > 32 else 5):
                break
        else:
            raise TasmaHatasi(f"Kapak spotu {len(str(spot_ham))} karakter; 28px'te bile 5 satırı aşıyor")

    h_spot_box = (len(spot_satirlari) * spot_satir_h) + 34 if spot_satirlari else 0

    # 4. Kusursuz Alt-Yukarı Dengeleme (Negatif Alan & Mesafe Yönetimi)
    alt_y = _yerlesim()["alt_bar"] - 5
    spot_end = alt_y - 35
    sy = spot_end - h_spot_box if spot_satirlari else spot_end
    by = sy - 35 - h_baslik
    if by < _yerlesim()["kronik_ust"] + 110:
        raise TasmaHatasi("Kapak manşeti ve spot üst rozete dayanıyor")

    # 5. Dinamik Karartma Perdesi
    serit_basi = max(180, by - (160 if YUKSEKLIK >= 1700 else 140))
    serit_tam = by + 220
    PANEL_ALFA = 185

    perde = Image.new("RGBA", (GENISLIK, YUKSEKLIK), (0, 0, 0, 0))
    p_draw = ImageDraw.Draw(perde)

    # Üst hafif vignette (doğal atmosfer, gökyüzünü karartmadan logo ve rozeti öne çıkarır)
    vignette_h = 240 if YUKSEKLIK >= 1700 else 200
    for y in range(vignette_h):
        alfa = int(75 * ((vignette_h - y) / vignette_h) ** 1.8)
        p_draw.line([(0, y), (GENISLIK, y)], fill=(8, 10, 14, alfa))

    # Alt derin karartma (manşet ve spot metinlerinin okunabilirliği için)
    azami_alfa = 240 if YUKSEKLIK >= 1700 else 252
    for y in range(serit_basi, YUKSEKLIK):
        if y < by:
            oran = (y - serit_basi) / max(1, by - serit_basi)
            alfa = int(PANEL_ALFA * (oran ** 1.15))
        elif y < serit_tam:
            oran = (y - by) / max(1, serit_tam - by)
            alfa = int(PANEL_ALFA + (azami_alfa - PANEL_ALFA) * (oran ** 0.85))
        else:
            alfa = azami_alfa
        p_draw.line([(0, y), (GENISLIK, y)], fill=(10, 12, 16, min(alfa, 255)))

    c_rgba = canvas.convert("RGBA")
    c_rgba.paste(perde, (0, 0), perde)
    canvas = c_rgba.convert("RGB")
    draw = ImageDraw.Draw(canvas)

    # 6. Üst Bar (Rozet + Logo - Diğer sayfalarla tam birebir aynı hiza ve boyut)
    rozet_metin = _rozet_kirp(veri.get("rozet_metni") or "EDM ANALİZ // GAYRİMENKUL", 46)
    ku = _yerlesim()["kronik_ust"]
    _rozet_ciz(draw, kenar_bosluk, ku, rozet_metin, bg_color=RENK_KIRMIZI, fg_color=RENK_BEYAZ, font_boyut=20)
    _logo_yerlestir(canvas, beyaz=True, y=ku - 5, lw=285, golge=True)

    # (7. Kapaktaki boş/gereksiz 'KAYNAK:' satırı ve gri çizgi dikkat dağıttığı için kaldırıldı)

    # 8. Manşet ve Vurgu Kapsülü (EDM imza kırmızı kapsül, beyaz metin, optik ortalama)
    curr_y = by
    for metin, vurgu_mu in manset_satirlari:
        if not vurgu_mu:
            _difuzyon_golgeli_metin(canvas, [(metin, RENK_BEYAZ)], kenar_bosluk, curr_y - ref_ust, font_manset)
            curr_y += satir_h + gap_v
            continue
        bbv = dummy_draw.textbbox((0, 0), metin, font=font_manset)
        v_ink_w = bbv[2] - bbv[0]
        box_w = v_ink_w + (2 * pad_x)
        box_y = curr_y
        box_x = kenar_bosluk - pad_x

        c_rgba = canvas.convert("RGBA")
        kapsul_overlay = Image.new("RGBA", (GENISLIK, YUKSEKLIK), (0, 0, 0, 0))
        ko_draw = ImageDraw.Draw(kapsul_overlay)
        ko_draw.rounded_rectangle(
            [(box_x, box_y), (box_x + box_w, box_y + box_h)],
            radius=10,
            fill=(*RENK_KIRMIZI, 255),
        )
        c_rgba.alpha_composite(kapsul_overlay)
        canvas = c_rgba.convert("RGB")
        draw = ImageDraw.Draw(canvas)

        # Metin kapsülün tam ortasında (mürekkep kutusuna göre)
        tx = box_x + (box_w - v_ink_w) / 2 - bbv[0]
        ty = box_y + (box_h - v_ink_h) / 2 - vref[1]
        draw.text((tx, ty), metin, font=font_manset, fill=RENK_BEYAZ)
        curr_y = box_y + box_h + gap_v

    # 9. Spot Metin ve Okunurluk Kalkanı (Glassmorphic Reading Card)
    if spot_satirlari:
        spot_card = Image.new("RGBA", (kullanilabilir_w, h_spot_box), (14, 18, 26, 220))
        sc_draw = ImageDraw.Draw(spot_card)
        sc_draw.rounded_rectangle([(0, 0), (kullanilabilir_w - 1, h_spot_box - 1)], radius=8, outline=(65, 75, 95, 190), width=1)
        # Sol kırmızı vurgu çizgisi (İmza EDM Kırmızısı)
        sc_draw.rounded_rectangle([(0, 0), (6, h_spot_box - 1)], radius=3, fill=(*RENK_KIRMIZI, 255))
        curr_ty = 18
        for sl in spot_satirlari:
            sc_draw.text((26, curr_ty), sl, font=font_spot, fill=RENK_METIN_GOVDE)
            curr_ty += spot_satir_h

        c_rgba = canvas.convert("RGBA")
        c_rgba.paste(spot_card, (kenar_bosluk, sy), spot_card)
        canvas = c_rgba.convert("RGB")
        draw = ImageDraw.Draw(canvas)

    # 10. Alt Bilgi Barı
    draw.line([(kenar_bosluk, alt_y), (GENISLIK - kenar_bosluk, alt_y)], fill=(55, 62, 75), width=1)
    draw.text((kenar_bosluk, alt_y + 22), "EDM YAPI & GAYRİMENKUL // BÜLTEN", font=_font_yukle(FONT_MONO_BOLD, 21), fill=RENK_KURSUN)
    kapak_etiket = _sayfa_etiketi(veri, 1)
    if kapak_etiket and str(kapak_etiket).strip():
        ke_w = draw.textbbox((0, 0), kapak_etiket, font=_font_yukle(FONT_MONO_BOLD, 18))[2]
        _rozet_ciz(draw, GENISLIK - kenar_bosluk - ke_w - 38, alt_y + 12, kapak_etiket, bg_color=RENK_KIRMIZI, fg_color=RENK_BEYAZ, font_boyut=18)

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/otorite_01_kapak_{os.getpid()}.jpg")
    else:
        cikti_yolu = Path(cikti_yolu)
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


def otorite_slayt_2_detay(veri: Dict[str, Any], cikti_yolu: Optional[Path] = None) -> Path:
    """Otorite 2. Slaytı (Problem Analizi veya İkili Kıyaslama Kartları):
    Ev Sahibi vs Kiracı, Doğru vs Yanlış veya Mevzuat Çıkmazını kartlarla açıklar.
    """
    kenar_bosluk = 70
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)

    kategori_kodu = veri.get("kategori_kodu") or veri.get("kategori", "GENEL")
    tohum = veri.get("manset") or veri.get("id") or veri.get("orijinal_baslik")
    canvas = _temiz_arkaplan_al(kategori_kodu, tohum=tohum)

    # Koyu sinematik perde
    karartma = Image.new("RGBA", (GENISLIK, YUKSEKLIK), (10, 12, 16, 190))
    c_rgba = canvas.convert("RGBA")
    c_rgba.paste(karartma, (0, 0), karartma)
    canvas = c_rgba.convert("RGB")
    draw = ImageDraw.Draw(canvas)

    # 1. Üst Bar
    rozet = veri.get("rozet_metni") or "SEKTÖREL ANALİZ // HUKUK & UYGULAMA"
    _rozet_ciz(draw, kenar_bosluk, 60, rozet, bg_color=RENK_MUREKKEP_2, fg_color=RENK_BEYAZ, border_color=RENK_CIZGI_KOYU)
    _logo_yerlestir(canvas, beyaz=True, y=55, lw=285)

    # 2. Bölüm Manşeti
    detay_veri = veri.get("slayt_2_detay") or {}
    baslik_1 = detay_veri.get("baslik_satir_1") or ""
    baslik_vurgu = detay_veri.get("baslik_vurgu") or ""

    satirlar = [
        (baslik_1, RENK_BEYAZ),
        (baslik_vurgu, RENK_KIRMIZI_CANLI),
    ]
    _difuzyon_golgeli_metin(canvas, satirlar, kenar_bosluk, 140, _font_yukle(FONT_SANS_BOLD, 52), satir_araligi=64)

    # 3. İki Kartlı Yapı (Varsa kart_1 & kart_2, yoksa standart problem kutuları)
    # Kart yoksa boş kalır. Eskiden her konuya kira/tahliye taahhütnamesi
    # hakkında sabit iki kart (biri "Yargıtay … hükümsüz sayabilmektedir") basılıyordu.
    k1 = detay_veri.get("kart_1") or {}
    k2 = detay_veri.get("kart_2") or {}

    # Kart Boyutları & Fontlar (Önemli adımlar ekranlarıyla tam uyumlu modern Sans tipografi)
    font_kart_baslik = _font_yukle(FONT_SANS_BOLD, 38)

    KART_UST_PAY = 20      # rozetin üstü
    KART_BASLIK_Y = 64     # kart içi başlık konumu
    KART_GOVDE_Y = 114     # kart içi gövde başlangıcı
    KART_ALT_PAY = 24

    def _kart_olc(kart: Dict[str, Any]) -> Dict[str, Any]:
        """Kartın gövde metnini sığdırır ve gerçek yüksekliğini hesaplar."""
        font, satirlar = _govde_sigdir(
            kart.get("aciklama", ""), FONT_SANS_MEDIUM,
            baslangic_boyut=32, min_boyut=26,
            azami_w=kullanilabilir_w - 60, azami_satir=5, draw=draw,
        )
        satir_araligi = font.size + 10
        yukseklik = KART_GOVDE_Y + (len(satirlar) * satir_araligi) + KART_ALT_PAY
        return {"kart": kart, "font": font, "satirlar": satirlar,
                "satir_araligi": satir_araligi, "h": yukseklik}

    olculer = [_kart_olc(k1), _kart_olc(k2)]

    # "Kaydet & Sakla" şeridi de dağıtıma dahil — altta ölü alan bırakmasın
    SAVE_H = 120
    ust_sinir = 275
    alt_sinir = YUKSEKLIK - 130

    # Artan alan önce kartların içine, sonra aralara dağıtılır
    ek_dolgu = _ek_dolgu_hesapla(
        [o["h"] for o in olculer] + [SAVE_H], ust_sinir, alt_sinir,
        asgari_bosluk=18, azami_ek=64,
    )
    for o in olculer:
        o["h"] += ek_dolgu
        o["govde_kaydirma"] = ek_dolgu // 2

    konumlar = _dikey_dagit(
        ust_sinir, alt_sinir,
        [o["h"] for o in olculer] + [SAVE_H],
        asgari_bosluk=18, azami_bosluk=44,
    )

    c_rgba = canvas.convert("RGBA")

    for olcu, ky in zip(olculer, konumlar):
        kart = olcu["kart"]
        k_h = olcu["h"]
        kart_img = Image.new("RGBA", (kullanilabilir_w, k_h), (18, 22, 32, 245))
        kd = ImageDraw.Draw(kart_img)
        kd.rounded_rectangle([(0, 0), (kullanilabilir_w - 1, k_h - 1)], radius=10, outline=(65, 75, 95, 255), width=1)

        kirmizi_mi = (kart.get("renk") == "kirmizi")
        sol_renk = (*RENK_KIRMIZI_CANLI, 255) if kirmizi_mi else (*RENK_YESIL, 255)
        kd.rounded_rectangle([(0, 0), (7, k_h - 1)], radius=4, fill=sol_renk)

        etiket = kart.get("etiket", "").replace("[", "").replace("]", "").strip()
        rozet_bg = (180, 15, 25) if kirmizi_mi else (20, 130, 60)
        _rozet_ciz(kd, 28, KART_UST_PAY, etiket, bg_color=rozet_bg, fg_color=RENK_BEYAZ, font_boyut=17)

        # Başlık da kırpılmaz; sığmıyorsa küçülür
        b_font, b_satirlar = _govde_sigdir(
            kart.get("baslik", ""), FONT_SANS_BOLD, 34, 27,
            kullanilabilir_w - 60, 1, kd,
        )
        kd.text((28, KART_BASLIK_Y), b_satirlar[0] if b_satirlar else "", font=b_font, fill=RENK_BEYAZ)

        gy = KART_GOVDE_Y + olcu.get("govde_kaydirma", 0)
        for satir in olcu["satirlar"]:
            kd.text((28, gy), satir, font=olcu["font"], fill=RENK_METIN_GOVDE)
            gy += olcu["satir_araligi"]

        c_rgba.paste(kart_img, (kenar_bosluk, ky), kart_img)

    # 4. Apple Glassmorphic "Kaydet & Sakla" Widget'ı
    save_y = konumlar[-1]
    save_h = SAVE_H
    save_box = Image.new("RGBA", (kullanilabilir_w, save_h), (22, 26, 38, 240))
    sb_draw = ImageDraw.Draw(save_box)
    sb_draw.rounded_rectangle([(0, 0), (kullanilabilir_w - 1, save_h - 1)], radius=12, outline=(70, 80, 105, 220), width=1)

    # Sol Bookmark Dairesi
    icon_cx, icon_cy = 56, save_h // 2
    sb_draw.ellipse([(icon_cx - 28, icon_cy - 28), (icon_cx + 28, icon_cy + 28)], fill=(*RENK_KIRMIZI_CANLI, 255))
    b_icon = _vektor_ikon_uret("bookmark", 30, (255, 255, 255))
    save_box.paste(b_icon, (icon_cx - 15, icon_cy - 15), b_icon)

    # Sağ Metinler (Saygın ve Kurumsal Arşiv Dili)
    tx = 106
    sb_draw.text((tx, 28), "HUKUKİ MEVZUAT KAYDI  //  EDM ARŞİVİ", font=_font_yukle(FONT_MONO_BOLD, 20), fill=RENK_KIRMIZI_CANLI)
    kaydet_metni = (veri.get("slayt_4_cta") or {}).get("kaydet_metni") or "Hukuki haklarınızı korumak adına bu rehberi arşivinize ekleyin."
    kf, ks = _govde_sigdir(kaydet_metni, FONT_SANS_MEDIUM, 24, 19, kullanilabilir_w - tx - 30, 1, sb_draw)
    sb_draw.text((tx, 60), ks[0] if ks else "", font=kf, fill=RENK_BEYAZ)

    c_rgba.paste(save_box, (kenar_bosluk, save_y), save_box)
    canvas = c_rgba.convert("RGB")
    draw = ImageDraw.Draw(canvas)

    # 5. Alt Bar
    alt_y = YUKSEKLIK - 105
    draw.line([(kenar_bosluk, alt_y), (GENISLIK - kenar_bosluk, alt_y)], fill=RENK_CIZGI_KOYU, width=1)
    draw.text((kenar_bosluk, alt_y + 24), "EDM YAPI & GAYRİMENKUL // HUKUK BÜLTENİ", font=_font_yukle(FONT_MONO, 19), fill=RENK_KURSUN)
    d_etiket = _sayfa_etiketi(veri, 2)
    de_w = draw.textbbox((0, 0), d_etiket, font=_font_yukle(FONT_MONO_BOLD, 17))[2]
    _rozet_ciz(draw, GENISLIK - kenar_bosluk - de_w - 36, alt_y + 14, d_etiket, bg_color=RENK_KIRMIZI_CANLI, fg_color=RENK_BEYAZ, font_boyut=17)

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/otorite_02_detay_{os.getpid()}.jpg")
    else:
        cikti_yolu = Path(cikti_yolu)
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


def _finansal_tablo_ciz(veri: Dict[str, Any], cozum_veri: Dict[str, Any], cikti_yolu: Optional[Path]) -> Path:
    """Karşılaştırma tablosu (B2): iki kolon, satır satır aynı ölçüt.

    2026-09-25: satır yükseklikleri ÖLÇÜLÜR, hücre değerleri satır kırar. Eskiden
    her satır 77px sabitti, değer tek satır basılıyordu ve uzun değer komşu
    kolona biniyordu. Ayrıca veri yoksa kod KENDİ rakamlarını basıyordu
    ("18.000 TL", "%80 - %130 (Gelişim aksı)", "otoban aksındaki arsalar her
    zaman daha yüksek getiri sağlamıştır") — uydurma veri. Artık üretim durur.
    """
    kenar_bosluk = 70
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)
    col_w = (kullanilabilir_w - 20) // 2
    hucre_w = col_w - 40

    def _ciftler(ham: Any) -> List[Tuple[str, str]]:
        sonuc = []
        for oge in ham if isinstance(ham, (list, tuple)) else []:
            if isinstance(oge, (list, tuple)) and len(oge) >= 2:
                sonuc.append((_metin(oge[0]), _metin(oge[1])))
            elif isinstance(oge, dict):
                sonuc.append((_metin(oge.get("olcut") or oge.get("baslik")), _metin(oge.get("deger") or oge.get("aciklama"))))
            elif oge is not None and _metin(oge):
                sonuc.append(("", _metin(oge)))
        return [(b, v) for b, v in sonuc if b or v]

    sol = _ciftler(cozum_veri.get("sol_kolon_veriler"))
    sag = _ciftler(cozum_veri.get("sag_kolon_veriler"))
    if not sol or not sag:
        raise EksikIcerik("Karşılaştırma tablosu: kolon verisi üretilmedi")
    not_metin = _metin(cozum_veri.get("stratejist_notu"))

    canvas = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_MUREKKEP)
    draw = ImageDraw.Draw(canvas)
    _rozet_ciz(draw, kenar_bosluk, 60, _rozet_kirp(veri.get("rozet_metni") or "KARŞILAŞTIRMA", 44), bg_color=RENK_KIRMIZI)
    _logo_yerlestir(canvas, beyaz=True, y=55, lw=285)

    # Başlık: iki satır, sığan en büyük punto
    y = 135
    for metin, renk in ((_metin(cozum_veri.get("baslik_ust")), RENK_BEYAZ),
                        (_metin(cozum_veri.get("baslik_vurgu")), RENK_KIRMIZI_CANLI)):
        if not metin:
            continue
        for punto in range(52, 35, -2):
            f = _font_yukle(FONT_SANS_BOLD, punto)
            if draw.textbbox((0, 0), metin, font=f)[2] <= kullanilabilir_w:
                break
        else:
            raise TasmaHatasi(f"Tablo başlığı sığmadı: {metin[:40]}")
        draw.text((kenar_bosluk, y), metin, font=f, fill=renk)
        y += 63
    alt_baslik = _metin(cozum_veri.get("alt_baslik"))
    if alt_baslik:
        ab_font, ab_satirlar = _govde_sigdir(alt_baslik, FONT_SANS_MEDIUM, 26, 22, kullanilabilir_w, 2, draw)
        if len(_metin_sar(alt_baslik, ab_font, kullanilabilir_w, draw)) > 2:
            raise TasmaHatasi("Tablo alt başlığı iki satırı aşıyor")
        y += 10
        for satir in ab_satirlar:   # eskiden yalnızca ilk satır çiziliyordu
            draw.text((kenar_bosluk, y), satir, font=ab_font, fill=RENK_METIN_GOVDE)
            y += 34
    tablo_y = y + 20

    alt_y = YUKSEKLIK - 105
    not_font = _font_yukle(FONT_SANS_MEDIUM, 26)
    not_satirlar = _metin_sar(not_metin, not_font, kullanilabilir_w - 60, draw) if not_metin else []
    not_h = (65 + len(not_satirlar) * 38 + 22) if not_satirlar else 0

    # Satır ölçümü: aynı ölçütün iki kolondaki yüksekliği eşitlenir
    def olc(punto_deger: int):
        f_bas = _font_yukle(FONT_MONO, 18)
        f_val = _font_yukle(FONT_SANS_BOLD, punto_deger)
        satir_h_val = int(punto_deger * 1.3)
        satirlar = []
        for i in range(max(len(sol), len(sag))):
            hucreler = []
            for kolon in (sol, sag):
                bas, val = kolon[i] if i < len(kolon) else ("", "")
                b_sat = _metin_sar(bas, f_bas, hucre_w, draw) if bas else []
                v_sat = _metin_sar(val, f_val, hucre_w, draw) if val else []
                hucreler.append((b_sat, v_sat))
            yuk = max(len(b) * 24 + (4 if b else 0) + len(v) * satir_h_val for b, v in hucreler) + 26
            satirlar.append((hucreler, yuk))
        return f_bas, f_val, satir_h_val, satirlar

    tablo_alt_sinir = alt_y - 30 - (not_h + 30 if not_h else 0)
    for punto_deger in (25, 24, 23, 22):
        f_bas, f_val, satir_h_val, satirlar = olc(punto_deger)
        tablo_h = 80 + sum(yuk for _, yuk in satirlar)
        if tablo_y + tablo_h <= tablo_alt_sinir:
            break
    else:
        raise TasmaHatasi(f"Karşılaştırma tablosu sığmadı ({len(sol)} satır, not {len(not_metin)} karakter)")

    x_kolonlar = (kenar_bosluk, kenar_bosluk + col_w + 20)
    basliklar = (_rozet_kirp(cozum_veri.get("sol_kolon_baslik") or "", 30), _rozet_kirp(cozum_veri.get("sag_kolon_baslik") or "", 30))
    bas_renk = ((30, 35, 46), RENK_KIRMIZI_DERIN)
    for k, x in enumerate(x_kolonlar):
        draw.rounded_rectangle([(x, tablo_y), (x + col_w, tablo_y + tablo_h)], radius=10, fill=RENK_MUREKKEP_2, outline=RENK_CIZGI_KOYU)
        draw.rounded_rectangle([(x, tablo_y), (x + col_w, tablo_y + 60)], radius=10, fill=bas_renk[k])
        draw.text((x + 20, tablo_y + 18), basliklar[k], font=_font_yukle(FONT_MONO_BOLD, 18), fill=RENK_BEYAZ)

    ky = tablo_y + 80
    for sira, (hucreler, yuk) in enumerate(satirlar):
        for k, (b_sat, v_sat) in enumerate(hucreler):
            x = x_kolonlar[k] + 20
            yy = ky
            for s in b_sat:
                draw.text((x, yy), s, font=f_bas, fill=RENK_KURSUN)
                yy += 24
            yy += 4 if b_sat else 0
            for s in v_sat:
                draw.text((x, yy), s, font=f_val, fill=RENK_BEYAZ)
                yy += satir_h_val
            if sira < len(satirlar) - 1:
                draw.line([(x, ky + yuk - 12), (x_kolonlar[k] + col_w - 20, ky + yuk - 12)], fill=RENK_CIZGI_KOYU, width=1)
        ky += yuk

    if not_satirlar:
        sonuc_y = tablo_y + tablo_h + 30
        draw.rounded_rectangle([(kenar_bosluk, sonuc_y), (GENISLIK - kenar_bosluk, sonuc_y + not_h)], radius=10, fill=(24, 28, 40), outline=RENK_KIRMIZI_CANLI)
        draw.text((kenar_bosluk + 30, sonuc_y + 24), "STRATEJİST NOTU:", font=_font_yukle(FONT_MONO_BOLD, 19), fill=RENK_KIRMIZI_CANLI)
        for idx, s in enumerate(not_satirlar):
            draw.text((kenar_bosluk + 30, sonuc_y + 65 + (idx * 38)), s, font=not_font, fill=RENK_METIN_GOVDE)

    draw.line([(kenar_bosluk, alt_y), (GENISLIK - kenar_bosluk, alt_y)], fill=RENK_CIZGI_KOYU, width=1)
    draw.text((kenar_bosluk, alt_y + 24), "EDM YAPI & GAYRİMENKUL // KARŞILAŞTIRMA", font=_font_yukle(FONT_MONO, 19), fill=RENK_KURSUN)
    c_etiket = _sayfa_etiketi(veri, veri.get("_slayt_sirasi", 3))
    ce_w = draw.textbbox((0, 0), c_etiket, font=_font_yukle(FONT_MONO_BOLD, 17))[2]
    _rozet_ciz(draw, GENISLIK - kenar_bosluk - ce_w - 36, alt_y + 14, c_etiket, bg_color=RENK_KIRMIZI_CANLI, fg_color=RENK_BEYAZ, font_boyut=17)

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/tablo_{os.getpid()}_{int(time.time())}.jpg")
    Path(cikti_yolu).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return Path(cikti_yolu)


def otorite_slayt_3_cozum(veri: Dict[str, Any], cikti_yolu: Optional[Path] = None) -> Path:
    """Otorite 3. Slaytı (Çözüm Yol Haritası, Finansal Tablo veya Resmi Pafta):
    Türe göre dinamik adapte olur (adim_adim_rehber, finansal_tablo, pafta_parametreleri).
    """
    kenar_bosluk = 70
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)

    cozum_veri = veri.get("slayt_3_cozum") or {}
    tip = cozum_veri.get("tip", "adim_adim_rehber")

    # -------------------------------------------------------------
    # A) FİNANSAL TABLO MODU (Konut vs Arsa, Amortisman)
    # -------------------------------------------------------------
    if tip == "finansal_tablo":
        return _finansal_tablo_ciz(veri, cozum_veri, cikti_yolu)

    # -------------------------------------------------------------
    # B) ADIM ADIM REHBER MODU (Varsayılan: 3 veya 4 Madde)
    # -------------------------------------------------------------
    else:
        canvas = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_MUREKKEP)
        draw = ImageDraw.Draw(canvas)

        _rozet_ciz(draw, kenar_bosluk, 60, veri.get("rozet_metni", "HUKUK & TAPU REHBERİ // ADIM ADIM KORUNMA"), bg_color=RENK_MUREKKEP_2, fg_color=RENK_BEYAZ, border_color=RENK_CIZGI_KOYU)
        _logo_yerlestir(canvas, beyaz=True, y=55, lw=285)
        draw.line([(kenar_bosluk, 105), (GENISLIK - kenar_bosluk, 105)], fill=RENK_CIZGI_KOYU, width=1)

        # Yedek başlık konuya özgü olmamalı (eskisi her konuya "Şufa davasından korunmak" yazıyordu)
        baslik_ust = cozum_veri.get("baslik_ust") or ""
        baslik_vurgu = cozum_veri.get("baslik_vurgu") or "Atılacak adımlar"
        satirlar_ust = _metin_sar(baslik_ust, _font_yukle(FONT_SANS_BOLD, 46), kullanilabilir_w, draw)
        by = 135
        for su in satirlar_ust:
            draw.text((kenar_bosluk, by), su, font=_font_yukle(FONT_SANS_BOLD, 46), fill=RENK_BEYAZ)
            by += 58
        draw.text((kenar_bosluk, by), baslik_vurgu, font=_font_yukle(FONT_SANS_BOLD, 46), fill=RENK_KIRMIZI_CANLI)
        by += 68

        # Adım yoksa adım da yok. Eskiden sabit üç adım basılıyordu; üçüncüsü
        # ("bedeli düşük gösterirseniz hissedarlar o bedelle mülkü alabilir")
        # 7571 sayılı Kanunla (24.12.2025) yanlış hâle geldi: önalımda bedel artık rayiç değer.
        maddeler = cozum_veri.get("maddeler") or []

        # Adım kartları da ölçülüp dağıtılır (Önemli adımlar ekranlarıyla aynı Sans tipografi)
        font_adim_baslik = _font_yukle(FONT_SANS_BOLD, 38)
        f_no = _font_yukle(FONT_MONO_BOLD, 22)

        ADIM_GOVDE_Y = 74
        ADIM_ALT_PAY = 26

        olculer = []
        for m in maddeler:
            font, satirlar = _govde_sigdir(
                m.get("aciklama", ""), FONT_SANS_MEDIUM,
                baslangic_boyut=30, min_boyut=24,
                azami_w=kullanilabilir_w - 75, azami_satir=4, draw=draw,
            )
            satir_araligi = font.size + 12
            olculer.append({
                "madde": m, "font": font, "satirlar": satirlar,
                "satir_araligi": satir_araligi,
                "h": ADIM_GOVDE_Y + (len(satirlar) * satir_araligi) + ADIM_ALT_PAY,
            })

        ek_dolgu = _ek_dolgu_hesapla(
            [o["h"] for o in olculer], by, YUKSEKLIK - 130,
            asgari_bosluk=20, azami_ek=72,
        )
        for o in olculer:
            o["h"] += ek_dolgu
            o["govde_kaydirma"] = ek_dolgu // 2

        konumlar = _dikey_dagit(
            by, YUKSEKLIK - 130,
            [o["h"] for o in olculer],
            asgari_bosluk=20, azami_bosluk=52,
        )

        for olcu, my in zip(olculer, konumlar):
            m = olcu["madde"]
            kart_h = olcu["h"]
            no = str(m.get("no", "01")).zfill(2)

            draw.rounded_rectangle([(kenar_bosluk, my), (GENISLIK - kenar_bosluk, my + kart_h)], radius=10, fill=RENK_MUREKKEP_2, outline=(65, 75, 95))
            draw.rounded_rectangle([(kenar_bosluk, my), (kenar_bosluk + 7, my + kart_h)], radius=4, fill=RENK_KIRMIZI_CANLI)

            # Dairesel Solid Adım Rozeti (Maksimum Kontrast)
            cx, cy = kenar_bosluk + 52, my + 38
            draw.ellipse([(cx - 24, cy - 24), (cx + 24, cy + 24)], fill=RENK_KIRMIZI_CANLI)
            bbox = draw.textbbox((0, 0), no, font=f_no)
            nw, nh = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text((cx - (nw // 2), cy - (nh // 2) - 2), no, font=f_no, fill=RENK_BEYAZ)

            b_font, b_satirlar = _govde_sigdir(
                m.get("baslik", ""), FONT_SANS_BOLD, 33, 26,
                GENISLIK - kenar_bosluk - (cx + 38) - 30, 1, draw,
            )
            draw.text((cx + 38, my + 21), b_satirlar[0] if b_satirlar else "", font=b_font, fill=RENK_BEYAZ)

            ay = my + ADIM_GOVDE_Y + olcu.get("govde_kaydirma", 0)
            for satir in olcu["satirlar"]:
                draw.text((kenar_bosluk + 35, ay), satir, font=olcu["font"], fill=RENK_METIN_GOVDE)
                ay += olcu["satir_araligi"]

        alt_y = YUKSEKLIK - 105
        draw.line([(kenar_bosluk, alt_y), (GENISLIK - kenar_bosluk, alt_y)], fill=RENK_CIZGI_KOYU, width=1)
        draw.text((kenar_bosluk, alt_y + 24), "EDM YAPI & GAYRİMENKUL // DANIŞMANLIK", font=_font_yukle(FONT_MONO, 19), fill=RENK_KURSUN)
        c_etiket = _sayfa_etiketi(veri, veri.get("_slayt_sirasi", 3))
        ce_w = draw.textbbox((0, 0), c_etiket, font=_font_yukle(FONT_MONO_BOLD, 17))[2]
        _rozet_ciz(draw, GENISLIK - kenar_bosluk - ce_w - 36, alt_y + 14, c_etiket, bg_color=RENK_KIRMIZI_CANLI, fg_color=RENK_BEYAZ, font_boyut=17)

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/otorite_03_cozum_{os.getpid()}.jpg")
    else:
        cikti_yolu = Path(cikti_yolu)
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


def slayt_kapanis(veri: Dict[str, Any], sayfa: str, cikti_yolu: Optional[Path] = None) -> Path:
    """Kapanış slaytı — Dinamik Stil Seçimli Prestij Mimarisi:
    Config veya veri sözlüğünden belirlenen stile göre (kartvizit, kitap_afis, split_screen,
    mimari_pafta, kurucu_mektubu, paspartu_fotograf, dikey_tipografi, iletisim_terminali,
    dev_numara, resmi_muhur, editoryal) 10 radikal tasarım konseptinden birini çizer.
    """
    from src.kapanis_stilleri import kapanis_ciz
    stil = veri.get("kapanis_stili") or config.ayar_al("tasarim.kapanis_stili", "kartvizit")
    return kapanis_ciz(stil, veri, sayfa, cikti_yolu)



def otorite_slayt_4_kapanis(veri: Dict[str, Any], cikti_yolu: Optional[Path] = None) -> Path:
    """Otorite 4. Slaytı (Lüks ve Sade Executive VIP Danışmanlık Kartı):
    Sıfır karmaşa, yüksek negatif alan, ferah tipografi ve Apple Dark Glass
    tek birleşik VIP kart mimarisiyle tasarlanmış prestij kapanışı.
    """
    kenar_bosluk = 70
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)

    # 1. Arka Plan & Derin Sinematik Karartma
    canvas = _temiz_arkaplan_al("DANISMANLIK")
    perde = Image.new("RGBA", (GENISLIK, YUKSEKLIK), (0, 0, 0, 0))
    p_draw = ImageDraw.Draw(perde)

    # Üst hafif vignette (logo ve rozet parlaması)
    for y in range(250):
        alfa = int(160 * ((250 - y) / 250) ** 1.5)
        p_draw.line([(0, y), (GENISLIK, y)], fill=(8, 10, 14, alfa))

    # Gövde ve alt koyu lüks perde
    for y in range(220, YUKSEKLIK):
        if y < 460:
            alfa = int(250 * ((y - 220) / 240) ** 1.2)
        else:
            alfa = 252
        p_draw.line([(0, y), (GENISLIK, y)], fill=(12, 14, 20, min(alfa, 255)))

    c_rgba = canvas.convert("RGBA")
    c_rgba.paste(perde, (0, 0), perde)
    canvas = c_rgba.convert("RGB")
    draw = ImageDraw.Draw(canvas)

    cta_veri = veri.get("slayt_4_cta") or {}

    # 2. Üst Bar (Rozet + Difüzyon Gölgeli Logo)
    _rozet_ciz(draw, kenar_bosluk, 60, "EDM DANIŞMANLIK // ÇÖZÜM ORTAĞINIZ", bg_color=RENK_KIRMIZI, fg_color=RENK_BEYAZ)
    _logo_yerlestir(canvas, beyaz=True, y=55, lw=285, golge=True)
    draw.line([(kenar_bosluk, 108), (GENISLIK - kenar_bosluk, 108)], fill=RENK_CIZGI_KOYU, width=1)

    # 3. Vurucu Başlık & Açıklama (Ferah ve Elit)
    slogan_1 = cta_veri.get("slogan_parca_1") or "Gayrimenkul Kararlarınızı"
    slogan_2 = cta_veri.get("slogan_vurgu") or "BİLGİ VE GÜVENE DAYANDIRIN."

    dummy_img = Image.new("RGB", (10, 10))
    dummy_draw = ImageDraw.Draw(dummy_img)
    f_slogan = _font_yukle(FONT_FRAUNCES, 48)

    s1_satirlar = _metin_sar(slogan_1, f_slogan, kullanilabilir_w, dummy_draw)
    s2_satirlar = _metin_sar(slogan_2, f_slogan, kullanilabilir_w, dummy_draw)

    slogan_satirlari: List[Tuple[str, Tuple[int, int, int]]] = (
        [(s, RENK_BEYAZ) for s in s1_satirlar] + [(s, RENK_KIRMIZI_CANLI) for s in s2_satirlar]
    )
    curr_sy = _difuzyon_golgeli_metin(canvas, slogan_satirlari, kenar_bosluk, 138, f_slogan, satir_araligi=62)

    draw = ImageDraw.Draw(canvas)
    aciklama = cta_veri.get("aciklama") or (
        "Silivri ve Trakya genelinde mülk alım, satım, tapu ve değerleme süreçlerinizde yanınızdayız."
    )
    ay = curr_sy + 14
    font_aciklama = _font_yukle(FONT_SANS_MEDIUM, 26)
    for s in _metin_sar(aciklama, font_aciklama, kullanilabilir_w, draw)[:2]:
        draw.text((kenar_bosluk, ay), s, font=font_aciklama, fill=RENK_METIN_GOVDE)
        ay += 38

    # 4. TEK BİRLEŞİK EXECUTIVE İLETİŞİM KARTI (Apple Dark Glass — 750px)
    kutu_y = max(330, ay + 22)
    k_h = 750
    card_img = Image.new("RGBA", (kullanilabilir_w, k_h), (18, 22, 32, 248))
    card_draw = ImageDraw.Draw(card_img)
    card_draw.rounded_rectangle([(0, 0), (kullanilabilir_w - 1, k_h - 1)], radius=16, outline=(65, 75, 100, 255), width=1)
    card_draw.rounded_rectangle([(0, 0), (7, k_h - 1)], radius=4, fill=(*RENK_KIRMIZI_CANLI, 255))

    # --- BÖLÜM 1: DOĞRUDAN DANIŞMANLIK HATTI (Hero Focal Point) ---
    _rozet_ciz(
        card_draw,
        36,
        28,
        "DOĞRUDAN DANIŞMANLIK HATTI  //  7/24 BİLGİ",
        bg_color=(38, 20, 26),
        fg_color=RENK_BEYAZ,
        border_color=(*RENK_KIRMIZI_CANLI, 255),
        font_boyut=16,
    )

    # Telefon Dairesi & İkonu
    p_cx, p_cy = 76, 126
    card_draw.ellipse([(p_cx - 34, p_cy - 34), (p_cx + 34, p_cy + 34)], fill=(32, 38, 52, 255), outline=(*RENK_KIRMIZI_CANLI, 200), width=1)
    p_icon = _vektor_ikon_uret("phone", 36, (255, 255, 255))
    card_img.paste(p_icon, (p_cx - 18, p_cy - 18), p_icon)

    # Numara ve Açıklama
    card_draw.text((128, 96), "0 212 727 2955", font=_font_yukle(FONT_MONO_BOLD, 52), fill=RENK_BEYAZ)
    card_draw.text((128, 156), "Ön görüşme ve ücretsiz değerleme analizi için doğrudan arayabilirsiniz.", font=_font_yukle(FONT_SANS_MEDIUM, 23), fill=RENK_KURSUN)

    # Ayrım Çizgisi 1
    card_draw.line([(36, 212), (kullanilabilir_w - 36, 212)], fill=(45, 52, 70, 255), width=1)

    # --- BÖLÜM 2: İKİLİ IZGARA (Merkez Ofis & Dijital Kanallar) ---
    # Sol Sütun: Silivri Merkez Ofis
    pin_img = _edm_pin_al(34)
    card_img.paste(pin_img, (36, 238), pin_img)
    card_draw.text((78, 236), "SİLİVRİ MERKEZ OFİS", font=_font_yukle(FONT_MONO_BOLD, 17), fill=RENK_KIRMIZI_CANLI)
    card_draw.text((36, 280), "Albay Yunus Dirik Cad. No: 58/A", font=_font_yukle(FONT_SANS_SEMIBOLD, 24), fill=RENK_BEYAZ)
    card_draw.text((36, 314), "Alibey Mah. Kılıç Apt., Silivri / İstanbul", font=_font_yukle(FONT_SANS_MEDIUM, 22), fill=RENK_KURSUN)

    _rozet_ciz(
        card_draw,
        36,
        364,
        "OFİS DAVETİ  //  HAFTANIN 7 GÜNÜ KAHVEYE BEKLERİZ",
        bg_color=(28, 32, 44),
        fg_color=RENK_BEYAZ,
        border_color=(60, 70, 90),
        font_boyut=15,
    )
    card_draw.text((36, 412), "Gayrimenkul kararlarınızı ofisimizde değerlendirin.", font=_font_yukle(FONT_SANS_MEDIUM, 21), fill=RENK_KURSUN)

    # Dikey Ayırıcı Çizgi
    card_draw.line([(480, 230), (480, 480)], fill=(45, 52, 70, 255), width=1)

    # Sağ Sütun: Dijital Platformlar & Sosyal Medya
    w_icon = _vektor_ikon_uret("web", 28, (255, 255, 255))
    card_img.paste(w_icon, (516, 238), w_icon)
    card_draw.text((554, 236), "RESMİ WEB PLATFORMU", font=_font_yukle(FONT_MONO_BOLD, 16), fill=RENK_KIRMIZI_CANLI)
    card_draw.text((554, 262), "edmyapigayrimenkul.com", font=_font_yukle(FONT_SANS_SEMIBOLD, 23), fill=RENK_BEYAZ)

    m_icon = _vektor_ikon_uret("mail", 28, (255, 255, 255))
    card_img.paste(m_icon, (516, 318), m_icon)
    card_draw.text((554, 316), "KURUMSAL E-POSTA", font=_font_yukle(FONT_MONO_BOLD, 16), fill=RENK_KIRMIZI_CANLI)
    card_draw.text((554, 342), "info@edmyapigayrimenkul.com", font=_font_yukle(FONT_SANS_SEMIBOLD, 22), fill=RENK_BEYAZ)

    card_draw.text((554, 404), "@edmyapigayrimenkul", font=_font_yukle(FONT_MONO_BOLD, 18), fill=RENK_BEYAZ)
    card_draw.text((554, 430), "Instagram · Threads · TikTok · YouTube", font=_font_yukle(FONT_MONO, 15), fill=(130, 140, 160))

    # Ayrım Çizgisi 2
    card_draw.line([(36, 505), (kullanilabilir_w - 36, 505)], fill=(45, 52, 70, 255), width=1)

    # --- BÖLÜM 3: KART İÇİ SAYGIN ARŞİV VE GÜVEN ALANI ---
    inner_box_y = 530
    inner_box_h = 185
    card_draw.rounded_rectangle([(36, inner_box_y), (kullanilabilir_w - 36, inner_box_y + inner_box_h)], radius=12, fill=(24, 28, 40, 255), outline=(55, 65, 85, 255))

    # Sol Kırmızı Bookmark İkonu
    b_cx, b_cy = 76, inner_box_y + (inner_box_h // 2)
    card_draw.ellipse([(b_cx - 24, b_cy - 24), (b_cx + 24, b_cy + 24)], fill=(*RENK_KIRMIZI_CANLI, 255))
    b_icon = _vektor_ikon_uret("bookmark", 26, (255, 255, 255))
    card_img.paste(b_icon, (b_cx - 13, b_cy - 13), b_icon)

    tx = 118
    card_draw.text((tx, inner_box_y + 24), "HUKUKİ MEVZUAT VE GAYRİMENKUL ARŞİVİ", font=_font_yukle(FONT_MONO_BOLD, 18), fill=RENK_KIRMIZI_CANLI)
    card_draw.text((tx, inner_box_y + 56), "İhtiyaç anında hızlıca başvurmak için bu rehberi kaydedebilirsiniz.", font=_font_yukle(FONT_SANS_MEDIUM, 23), fill=RENK_BEYAZ)
    card_draw.text((tx, inner_box_y + 92), "Silivri ve Trakya genelinde 15 yılı aşkın saha uzmanlığı ve güvenli işlem garantisi.", font=_font_yukle(FONT_SANS_MEDIUM, 20), fill=RENK_KURSUN)
    card_draw.text((tx, inner_box_y + 128), "EDM YAPI & GAYRİMENKUL  //  YATIRIM ORTAĞINIZ", font=_font_yukle(FONT_MONO_BOLD, 16), fill=(*RENK_KIRMIZI_CANLI, 220))

    # Hukuk içerikli kategorilerde sorumluluk notu zorunlu (ICERIK-SISTEMI.md §7.4).
    # Genel bilgilendirme ile bağlayıcı hukuki görüş arasındaki farkı belirtmek,
    # takipçiyi de ofisi de korur.
    if (veri.get("kategori_kodu") or "") in ("TAPU_VE_HUKUK", "EV_SAHIBI_VE_KIRACI", "ARSA_IMAR_VE_TINY_HOUSE"):
        card_draw.text(
            (tx, inner_box_y + 158),
            "Bu içerik genel bilgilendirmedir; bağlayıcı hukuki görüş için avukatınıza danışın.",
            font=_font_yukle(FONT_SANS_MEDIUM, 17), fill=(126, 134, 152),
        )

    c_rgba = canvas.convert("RGBA")
    c_rgba.paste(card_img, (kenar_bosluk, kutu_y), card_img)
    canvas = c_rgba.convert("RGB")
    draw = ImageDraw.Draw(canvas)

    # 5. Alt Bilgi Barı (Slayt 1, 2, 3 ile Birebir Uyumlu)
    alt_y = YUKSEKLIK - 105
    draw.line([(kenar_bosluk, alt_y), (GENISLIK - kenar_bosluk, alt_y)], fill=RENK_CIZGI_KOYU, width=1)
    draw.text((kenar_bosluk, alt_y + 24), "EDM YAPI & GAYRİMENKUL // DANIŞMANLIK & İLETİŞİM", font=_font_yukle(FONT_MONO, 19), fill=RENK_KURSUN)
    # Slayt sayısı karma mimaride 4 ile 7 arasında değişiyor; sabit "04 / 04" yanlış olurdu
    toplam_slayt = veri.get("_toplam_slayt", 4)
    sayfa_etiketi = f"{str(toplam_slayt).zfill(2)} / {str(toplam_slayt).zfill(2)}  ›  İLETİŞİM"
    sw = draw.textbbox((0, 0), sayfa_etiketi, font=_font_yukle(FONT_MONO_BOLD, 17))[2]
    _rozet_ciz(draw, GENISLIK - kenar_bosluk - sw - 36, alt_y + 14, sayfa_etiketi, bg_color=RENK_KIRMIZI_CANLI, fg_color=RENK_BEYAZ, font_boyut=17)

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/otorite_04_kapanis_{os.getpid()}.jpg")
    else:
        cikti_yolu = Path(cikti_yolu)
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu



# =========================================================================
# GİRDİ NORMALLEŞTİRME
#
# Çizim katmanı modelden gelen JSON'a güveniyordu ve sabotaj testi dört ayrı
# çökme sınıfı ortaya çıkardı: metin beklenen yerde sayı (`len()` hatası),
# liste/sözlük (`.upper()` hatası), `slayt_2_detay` yerine liste (`.get()` hatası).
# Model bunları gerçekten üretebiliyor.
#
# Çözüm her çizim satırına isinstance serpmek değil, tek bir kapıda şekli
# garanti altına almak. Buradan sonra çizim kodu tiplerine güvenebilir.
# =========================================================================

# Doğrudan metin beklenen üst düzey alanlar
_METIN_ALANLARI = (
    "rozet_metni", "yasal_dayanak", "manset", "manset_parca_1", "manset_vurgu",
    "manset_parca_2", "spot", "soru", "kategori_kodu", "bicim", "kaynak",
    "gorsel_url", "foto_url", "caption_instagram", "caption_facebook", "caption_threads",
)


def _metin(deger: Any) -> str:
    """Herhangi bir değeri güvenli bir metne çevirir.

    Liste birleştirilir (model bazen paragrafları dizi olarak veriyor), sözlük
    ve diğer karmaşık tipler atılır: yarım serileştirilmiş bir sözlüğü karede
    göstermek bozuk metin basmaktan daha kötü.
    """
    if deger is None:
        return ""
    if isinstance(deger, str):
        return deger
    if isinstance(deger, bool):
        return ""
    if isinstance(deger, (int, float)):
        return str(deger)
    if isinstance(deger, (list, tuple)):
        return " ".join(_metin(x) for x in deger if not isinstance(x, (dict, list, tuple))).strip()
    return ""


def _sozluk(deger: Any) -> Dict[str, Any]:
    return deger if isinstance(deger, dict) else {}


def _kart_normalize(ham: Any) -> Dict[str, Any]:
    k = _sozluk(ham)
    return {
        "etiket": _metin(k.get("etiket")),
        "renk": _metin(k.get("renk")) or "kirmizi",
        "baslik": _metin(k.get("baslik")),
        "aciklama": _metin(k.get("aciklama")),
    }


def veriyi_normalize_et(ham: Any) -> Dict[str, Any]:
    """Model çıktısını çizim katmanının beklediği şekle sokar.

    Bozuk alanı düşürür, eksik alanı boş bırakır — hiçbir durumda istisna
    fırlatmaz. Cron gözetimsiz çalıştığı için tek bozuk alan o günün
    paylaşımını düşürmemeli.
    """
    v = _sozluk(ham)
    veri: Dict[str, Any] = {a: _metin(v.get(a)) for a in _METIN_ALANLARI}

    onem = v.get("onem_puani")
    veri["onem_puani"] = onem if isinstance(onem, (int, float)) and not isinstance(onem, bool) else 8

    detay = _sozluk(v.get("slayt_2_detay"))
    ham_kartlar = detay.get("kartlar")
    kartlar = []
    if isinstance(ham_kartlar, (list, tuple)):
        for k in ham_kartlar:
            kn = _kart_normalize(k)
            if kn.get("baslik"):
                kartlar.append(kn)

    k1 = _kart_normalize(detay.get("kart_1"))
    k2 = _kart_normalize(detay.get("kart_2"))

    if not kartlar:
        for k in (k1, k2):
            if k.get("baslik"):
                kartlar.append(k)

    if not k1.get("baslik") and len(kartlar) >= 1:
        k1 = kartlar[0]
    if not k2.get("baslik") and len(kartlar) >= 2:
        k2 = kartlar[1]

    veri["slayt_2_detay"] = {
        "baslik_satir_1": _metin(detay.get("baslik_satir_1")),
        "baslik_vurgu": _metin(detay.get("baslik_vurgu")),
        "kart_1": k1,
        "kart_2": k2,
        "kartlar": kartlar,
    }

    cozum = _sozluk(v.get("slayt_3_cozum"))
    ham_maddeler = cozum.get("maddeler")
    maddeler = []
    if isinstance(ham_maddeler, (list, tuple)):
        for i, m in enumerate(ham_maddeler, start=1):
            md = _sozluk(m)
            baslik = _metin(md.get("baslik"))
            if not baslik:
                continue          # başlıksız madde çizilemez, atlanır
            maddeler.append({
                "no": _adim_numarasi(md.get("no") if md.get("no") not in (None, "") else i),
                "baslik": baslik,
                "aciklama": _metin(md.get("aciklama")),
            })

    def _kolon(ham_kolon: Any) -> List[Tuple[str, str]]:
        if not isinstance(ham_kolon, (list, tuple)):
            return []
        cikti = []
        for satir in ham_kolon:
            if isinstance(satir, (list, tuple)) and len(satir) >= 2:
                cikti.append((_metin(satir[0]), _metin(satir[1])))
            elif isinstance(satir, dict):
                anahtarlar = list(satir.items())
                if anahtarlar:
                    cikti.append((_metin(anahtarlar[0][0]), _metin(anahtarlar[0][1])))
        return cikti[:5]

    veri["slayt_3_cozum"] = {
        "tip": _metin(cozum.get("tip")) or "adim_adim_rehber",
        "baslik_ust": _metin(cozum.get("baslik_ust")),
        "baslik_vurgu": _metin(cozum.get("baslik_vurgu")),
        "alt_baslik": _metin(cozum.get("alt_baslik")),
        "maddeler": maddeler,
        "sol_kolon_baslik": _metin(cozum.get("sol_kolon_baslik")),
        "sag_kolon_baslik": _metin(cozum.get("sag_kolon_baslik")),
        "sol_kolon_veriler": _kolon(cozum.get("sol_kolon_veriler")),
        "sag_kolon_veriler": _kolon(cozum.get("sag_kolon_veriler")),
        "stratejist_notu": _metin(cozum.get("stratejist_notu")),
    }

    cta = _sozluk(v.get("slayt_4_cta"))
    veri["slayt_4_cta"] = {
        "slogan_parca_1": _metin(cta.get("slogan_parca_1")),
        "slogan_vurgu": _metin(cta.get("slogan_vurgu")),
        "aciklama": _metin(cta.get("aciklama")),
        "kaydet_metni": _metin(cta.get("kaydet_metni")),
    }

    # Görsel kontrol anahtarları: Telegram'daki "Saf editoryal", "Başka fotoğraf",
    # "Stok fotoğraf" düğmeleri bunları yazar. Normalize eskiden yalnızca metin
    # alanlarını tutuyordu; düğmelerin carousel kapağına HİÇ etkisi yoktu.
    for anahtar in ("saf_editoryal", "foto_degistir"):
        if v.get(anahtar) is True:
            veri[anahtar] = True
    for anahtar in ("onceki_foto", "foto_kaynak", "kapanis_stili", "konu_kodu"):
        if _metin(v.get(anahtar)):
            veri[anahtar] = _metin(v.get(anahtar))
    return veri


# Karma mimari eşikleri: içerik bu uzunlukların altındaysa tek karede toplanır,
# üstündeyse slayta bölünür. Değerler ICERIK-SISTEMI.md §5 bütçelerinden türedi —
# iki fikir tek karede toplandığında her birine ~140 karakter düşüyor ki bu
# 34px puntoyla rahat okunan sınır.
ESIK_IKILI_FIKIR = 290   # kart_1 + kart_2 açıklama toplamı
ESIK_ADIM_TOPLU = 330    # tüm adım açıklamalarının toplamı


def _slayt_plani(veri: Dict[str, Any]) -> List[Dict[str, Any]]:
    """İçerik yoğunluğuna göre slayt dizisini planlar (3 ↔ 8 slayt).

    Kısa içerikte akışı uzatmak, uzun içerikte kareyi tıkamak kadar kötü.
    Karar metnin gerçek uzunluğundan ve kart/adım sayısından dinamik verilir.
    """
    plan: List[Dict[str, Any]] = [{"tur": "kapak"}]

    detay = veri.get("slayt_2_detay") or {}
    kartlar = detay.get("kartlar")
    if isinstance(kartlar, (list, tuple)) and kartlar:
        fikirler = [k for k in kartlar if isinstance(k, dict) and k.get("baslik")]
    else:
        k1, k2 = detay.get("kart_1"), detay.get("kart_2")
        fikirler = [k for k in (k1, k2) if isinstance(k, dict) and k.get("baslik")]

    if fikirler:
        yogunluk = sum(len(k.get("aciklama", "")) for k in fikirler)
        if len(fikirler) == 2 and yogunluk <= ESIK_IKILI_FIKIR:
            plan.append({"tur": "ikili_fikir", "fikirler": fikirler, "zemin": "murekkep"})
        else:
            # 1, 2 (uzun), 3 veya 4 kart: her biri bağımsız tek_fikir slaytına açılır.
            # İlk kart veya kırmızı renkli olanlar kırmızı zeminde, diğerleri açık kağıtta.
            for i, k in enumerate(fikirler):
                renk = k.get("renk", "")
                if renk == "kirmizi":
                    zemin = "kirmizi"
                elif renk in ("yesil", "beyaz"):
                    zemin = "kagit"
                else:
                    zemin = "kirmizi" if i == 0 else "kagit"
                plan.append({
                    "tur": "tek_fikir", "fikir": k,
                    "zemin": zemin,
                })

    cozum = veri.get("slayt_3_cozum") or {}
    maddeler = [m for m in (cozum.get("maddeler") or []) if isinstance(m, dict) and m.get("baslik")]
    if cozum.get("tip") == "finansal_tablo":
        plan.append({"tur": "finansal_tablo"})
    elif maddeler:
        # Önemli adımların her biri kendi bağımsız ekranına (slayt_adim) açılır;
        # her birinde dinamik progress bar, devasa numara ve önemli not kutusu yer alır.
        for m in maddeler:
            plan.append({"tur": "adim", "madde": m, "toplam": len(maddeler), "zemin": "murekkep"})

    plan.append({"tur": "kapanis"})
    return plan


@_gorsel_girdisi
def otorite_gonderi_slaytlari_uret(
    veri: Dict[str, Any],
    cikti_onek: Optional[str] = None,
    olcu: Any = "besleme",
) -> List[Path]:
    """Carousel görsellerini üretir. Slayt sayısı içeriğe göre 4 ile 7 arasında değişir.

    `olcu`: "besleme" (1080x1350, Instagram carousel) veya "story"
    (1080x1920, Reels/Shorts/TikTok). Aynı içerik iki formatta da üretilebilir;
    yerleşim `_yerlesim()` ile tuvalden türetilir.
    """
    normal = veriyi_normalize_et(veri)
    if not any(normal.get(k) for k in ("manset_parca_1", "manset_vurgu", "manset_parca_2", "manset")):
        # Boş veriyle kapak + kapanış "çizilip" onaya düşüyordu
        raise EksikIcerik("Carousel: manşet üretilmedi")
    with tuval(olcu):
        return _gonderi_slaytlarini_ciz(normal, cikti_onek)


def _gonderi_slaytlarini_ciz(veri: Dict[str, Any], cikti_onek: Optional[str]) -> List[Path]:
    onek = cikti_onek or f"gonderi_{os.getpid()}"
    plan = _slayt_plani(veri)
    toplam = len(plan)
    rozet = veri.get("rozet_metni") or "EDM ANALİZ // GAYRİMENKUL"
    alt_metin = "EDM YAPI & GAYRİMENKUL // BÜLTEN"

    yollar: List[Path] = []
    for i, adim in enumerate(plan, start=1):
        if YUKSEKLIK >= 1700 or veri.get("_video_modu"):
            sayfa = ""
        else:
            sayfa = f"{str(i).zfill(2)} / {str(toplam).zfill(2)}"
            if i < toplam and YUKSEKLIK != 1920 and GENISLIK != 1920:
                sayfa += "  ›"
        yol = config.yol_al(f"data/output/{onek}_{str(i).zfill(2)}_{adim['tur']}.jpg")
        tur = adim["tur"]

        veri["_toplam_slayt"] = toplam
        veri["_slayt_sirasi"] = i

        if tur == "kapak":
            yollar.append(otorite_slayt_1_kapak(veri, yol))

        elif tur == "ikili_fikir":
            yollar.append(slayt_ikili_fikir(
                adim["zemin"], rozet,
                [{"etiket": f.get("etiket", ""), "baslik": f.get("baslik", ""),
                  "govde": f.get("aciklama", ""), "renk": f.get("renk", "")}
                 for f in adim["fikirler"]],
                alt_metin, sayfa, yol,
            ))

        elif tur == "tek_fikir":
            f = adim["fikir"]
            yollar.append(slayt_tek_fikir(
                adim["zemin"], rozet, f.get("etiket", ""), f.get("baslik", ""),
                f.get("aciklama", ""), alt_metin, sayfa, yol,
            ))

        elif tur == "adimlar_toplu":
            yollar.append(slayt_adimlar_toplu(
                adim["zemin"], veri.get("slayt_3_cozum", {}).get("baslik_vurgu") or rozet,
                adim["maddeler"], "EDM YAPI & GAYRİMENKUL // DANIŞMANLIK", sayfa, yol,
            ))

        elif tur == "adim":
            m = adim["madde"]
            yollar.append(slayt_adim(
                adim["zemin"], veri.get("slayt_3_cozum", {}).get("baslik_vurgu") or rozet,
                m.get("no", "01"), m.get("baslik", ""), m.get("aciklama", ""),
                adim["toplam"], "EDM YAPI & GAYRİMENKUL // DANIŞMANLIK", sayfa, yol,
            ))

        elif tur == "finansal_tablo":
            yollar.append(otorite_slayt_3_cozum(veri, yol))

        elif tur == "kapanis":
            veri["_toplam_slayt"] = toplam
            yollar.append(slayt_kapanis(veri, sayfa, yol))

    return yollar


# Geriye Dönük Uyumluluk Sarmalayıcıları (Eski kodlar için)
def haber_slayti_1_ciz(manset: str, spot: str, kaynak: str, tarih: str, foto_url: Optional[str] = None, cikti_yolu: Optional[Path] = None) -> Path:
    veri = {
        "manset": manset,
        "spot": spot,
        "kaynak": kaynak,
        "yasal_dayanak": f"KAYNAK: {kaynak.upper()} // TARİH: {tarih[:10] if tarih else ''}",
        "gorsel_url": foto_url,
    }
    return otorite_slayt_1_kapak(veri, cikti_yolu)


def haber_slayti_2_ciz(manset: str, maddeler: List[str], cikti_yolu: Optional[Path] = None) -> Path:
    veri = {
        "slayt_3_cozum": {
            "tip": "adim_adim_rehber",
            "baslik_ust": "Sektörel Değerlendirme ve",
            "baslik_vurgu": "PİYASA ÇIKARIMLARI",
            "maddeler": [
                {"no": f"0{idx}", "baslik": f"Önemli Not #{idx}", "aciklama": m}
                for idx, m in enumerate(maddeler[:3], start=1)
            ],
        }
    }
    return otorite_slayt_3_cozum(veri, cikti_yolu)


def haber_kapanis_slayti_ciz(cikti_yolu: Optional[Path] = None) -> Path:
    return slayt_kapanis({}, "03 / 03", cikti_yolu)


# =========================================================================
# INSTABOT DAILYBRIEF HABER TASARIMI PARİTESİ (EDM EDİTORYAL FORMATI)
# =========================================================================

def _perde_maskesi_smoothstep(genislik: int, yukseklik: int, bas: int, son: int) -> Image.Image:
    """Instabot standardı: Fotoğraftan koyu zemine pürüzsüz geçiş maskesi."""
    seritler = []
    fark = max(1, son - bas)
    for y in range(yukseklik):
        if y <= bas:
            v = 0
        elif y >= son:
            v = 255
        else:
            t = (y - bas) / fark
            v = int(255 * (t * t * (3 - 2 * t)))  # smoothstep
        seritler.append(v)
    serit = Image.new("L", (1, yukseklik))
    serit.putdata(seritler)
    return serit.resize((genislik, yukseklik), Image.BILINEAR)


@_gorsel_girdisi
def haber_dailybrief_slayti_ciz(
    haber: Dict[str, Any],
    foto_yolu: Optional[Path | str] = None,
    cikti_yolu: Optional[Path] = None,
    olcu: str = "besleme",
    sayfa_no: Optional[str] = None,
) -> Path:
    """
    Instabot (DailyBrief) mimarisi paritesi:
    Gerçek/stok haber fotoğrafı + kademeli okuma perdesi + Fraunces manşet +
    IBM Plex Sans özet + EDM kurumsal kimliği ile yüksek dönüşümlü haber kartı.

    4:5 Güvenli Alan & 9:16 Uyumu (Kullanıcı Kuralı):
    - Logo boyutu diğer tüm EDM formatlarıyla (Sözlük, Nedir Doğrusu, Vaka Analizi, Net Cevap)
      birebir aynı dev ve prestijli boyutta (lw=285) sağ üstte yer alır.
    - Sol üstte kurumsal kırmızı hap rozet (_rozet_ciz) yer alır.
    - Besleme (1080x1350) modunda içerik tam 4:5 tuvaline göre dizilir (y_ofset = 0).
    - Story/Reels (1080x1920) modunda arka plan fotoğrafı tüm 1080x1920 tuvalini kaplarken,
      tüm içerik elemanları (rozet, logo, manşet, spot, alt bar) dikeyde 4:5 güvenli merkezinde
      (y_ofset = (1920 - 1350) // 2 = 285) konumlanır.
    - Bu sayede 9:16 görsel Instagram akışında veya profil ızgarasında 4:5 olarak kırpıldığında
      hiçbir metin veya logo kesilmez; Story/Reels tam ekranda ise üst ve alt Instagram
      arayüz butonlarına asla çarpmaz.
    """
    if isinstance(haber, dict):
        dm = haber.get("detay_metni")
        if dm and isinstance(dm, str) and dm.strip().startswith("{"):
            try:
                import json
                parsed = json.loads(dm)
                if isinstance(parsed, dict):
                    haber = {**parsed, **haber}
                    if parsed.get("kanca") and not haber.get("kanca"):
                        haber["kanca"] = parsed["kanca"]
            except Exception:
                pass

    with tuval(olcu):
        genislik = GENISLIK
        yukseklik = YUKSEKLIK
        kenar = 70
        kullanilabilir_w = genislik - (2 * kenar)

        # Dikey Story (9:16) ve Besleme (4:5) güvenli alanları
        dikey_story = yukseklik >= 1700
        if dikey_story:
            ust_y = 260  # Meta 9:16 Story güvenli alanı: Instagram profil avatarı ve X butonunun altında kalır
            alt_y = yukseklik - 250  # 1670 px (Instagram mesaj/yanıt barı güvenli alanı)
        else:
            ust_y = 62
            alt_y = 1250

        if cikti_yolu is None:
            cikti_yolu = config.yol_al(f"data/output/haber_dailybrief_{os.getpid()}_{int(time.time())}.jpg")
        else:
            cikti_yolu = Path(cikti_yolu)
        cikti_yolu.parent.mkdir(parents=True, exist_ok=True)

        # 1. Arka Plan Fotoğrafını Hazırla
        bg_img: Optional[Image.Image] = None
        foto_kaynak = haber.get("foto_kaynak")

        # 1.0. Önceden belirlenmiş/önbelleğe alınmış fotoğraf veya haberin orijinal görseli (URL veya yerel dosya)
        secilen_fp = foto_yolu or haber.get("foto_yolu") or haber.get("gorsel_yolu") or haber.get("gorsel_url")
        if secilen_fp:
            try:
                foto_ham = _foto_indir_veya_ac(str(secilen_fp))
                if foto_ham:
                    from . import gorsel_kalite
                    bg_img = gorsel_kalite.kristal_netlestir(foto_ham)
                    # Diske sabitle ki sonraki slaytlar ve 9:16 video her zaman AYNI görseli kullansın!
                    try:
                        c_dir = cikti_yolu.parent if cikti_yolu else config.yol_al("data/output/gonderiler")
                        c_dir.mkdir(parents=True, exist_ok=True)
                        h_id = haber.get("id") or os.getpid()
                        cache_p = c_dir / f"haber_foto_{h_id}.jpg"
                        if not cache_p.exists():
                            bg_img.save(cache_p, "JPEG", quality=95)
                        haber["foto_yolu"] = str(cache_p)
                        haber["gorsel_yolu"] = str(cache_p)
                    except Exception as ce:
                        log.debug("Haber görseli diske sabitlenemedi: %s", ce)
                    log.info("Haberin orijinal görseli başarıyla yüklendi ve kilitlendi: %s", str(secilen_fp)[:60])
            except Exception as pe:
                log.warning("Haber görseli açılamadı (%s): %s", secilen_fp, pe)

        # 1.1. Görsel bulunamadıysa doğrudan haberin orijinal web sayfasından çek
        if not bg_img:
            makale_link = haber.get("orijinal_url") or haber.get("link") or haber.get("url")
            if makale_link and str(makale_link).startswith("http"):
                try:
                    from . import fetch_article, gorsel_kalite
                    og_u = fetch_article.og_gorseli_cek(makale_link)
                    if not og_u:
                        tum_u = fetch_article.tum_gorselleri_cek(makale_link)
                        if tum_u:
                            og_u = tum_u[0]
                    if og_u:
                        foto_og = _foto_indir_veya_ac(og_u)
                        if foto_og:
                            bg_img = gorsel_kalite.kristal_netlestir(foto_og)
                            haber["gorsel_url"] = og_u
                            log.info("Haberin web sayfasından görsel temin edildi: %s", og_u[:60])
                except Exception as oe:
                    log.debug("Orijinal web linkinden görsel çekilemedi: %s", oe)

        # Kardeş haber görsel havuzu (instabot paritesi): Fotoğraf yoksa veya kalitesizse kardeş haberleri tara
        if not bg_img:
            try:
                sira = int(haber.get("foto_sira") or 0)
                alt_foto, alt_kaynak = _haber_gorseli_alternatifi(haber, sira=sira)
                if alt_foto:
                    bg_img = alt_foto
                    if alt_kaynak:
                        haber["foto_atif"] = alt_kaynak
                    log.info("Kardeş haber havuzundan HD görsel kullanılıyor (%s).", alt_kaynak)
            except Exception as ke:
                log.debug("Kardeş haber havuzu hatası: %s", ke)

        # Fotoğraf yoksa veya kalitesizse: Pexels API'den emlak stok görseli ara
        if not bg_img:
            try:
                from . import fetch_stock, gorsel_kalite
                kat = haber.get("kategori") or haber.get("kategori_kodu") or "SEKTOREL_HABER_VE_ANALIZ"
                baslik_ham = (haber.get("orijinal_baslik") or haber.get("manset") or haber.get("baslik") or "").lower()
                if any(w in baslik_ham for w in ("arsa", "arazi", "tarla", "parsel", "hazine", "milli emlak", "çatalca", "silivri")):
                    arama_sorgu = "real estate land field plot aerial"
                elif any(w in baslik_ham for w in ("kira", "kiracı", "tahliye", "ev sahibi", "daire", "konut")):
                    arama_sorgu = "modern apartment house keys interior real estate"
                elif any(w in baslik_ham for w in ("toki", "sosyal konut", "inşaat", "şantiye", "proje", "kentsel dönüşüm")):
                    arama_sorgu = "modern residential buildings construction architecture"
                else:
                    arama_sorgu = "modern luxury architecture real estate villa"
                stok_p = fetch_stock.stok_fotografi_ara(arama_sorgu, kategori_kodu=kat)
                if stok_p and stok_p.exists():
                    stok_img = ImageOps.exif_transpose(Image.open(stok_p)).convert("RGB")
                    bg_img = gorsel_kalite.kristal_netlestir(stok_img)
                    # KİLİTLE: 4:5 gönderi ve 9:16 video/story her zaman AYNI görseli kullansın
                    haber["foto_yolu"] = str(stok_p)
                    haber["gorsel_yolu"] = str(stok_p)
            except Exception as se:
                log.warning("Stok fotoğraf aranamadı: %s", se)

        # Fotoğraf ölçeklendir veya şık koyu pafta zemini üret
        if bg_img:
            bg_w, bg_h = bg_img.size
            oran = max(genislik / bg_w, yukseklik / bg_h)
            yeni_w = int(bg_w * oran)
            yeni_h = int(bg_h * oran)
            bg_olcekli = bg_img.resize((yeni_w, yeni_h), Image.Resampling.LANCZOS)

            # Fotoğrafı tuvalin tam merkezine odakla (hem 4:5 hem 9:16'da dikişsiz, yekpare ve kusursuz odak)
            kirp_x = max(0, (yeni_w - genislik) // 2)
            kirp_y = max(0, (yeni_h - yukseklik) // 2)
            bg_kirp = bg_olcekli.crop((kirp_x, kirp_y, kirp_x + genislik, kirp_y + yukseklik))

            canvas = Image.new("RGB", (genislik, yukseklik), RENK_MUREKKEP)
            canvas.paste(bg_kirp, (0, 0))
        else:
            # Yedek zemin: Derin mimari pafta zemini
            canvas = _zemin_uret("murekkep", olcu=olcu)

        # Filigranı uygula
        canvas = _filigran_uygula(canvas, acik_zemin=False)
        draw = ImageDraw.Draw(canvas)

        # 2. Üst Bar: Sol üstte Kırmızı Rozet, Sağ üstte Dev EDM Logosu (lw=285)
        logo_w = 285
        logo_x = genislik - kenar - logo_w
        _logo_yerlestir(
            canvas,
            beyaz=True,
            x=logo_x,
            y=ust_y - 5,
            lw=logo_w,
            golge=True,
            kirmizi_zemin=False,
        )
        draw = ImageDraw.Draw(canvas)

        from .yeni_formatlar import kategori_temizle
        kategori_adi = kategori_temizle(haber.get("kategori") or haber.get("kategori_kodu")).upper()
        rozet_txt = f"EDM GÜNDEM // {kategori_adi}"
        azami_rozet_w = logo_x - kenar - 30
        _rozet_ciz(
            draw,
            kenar,
            ust_y,
            rozet_txt,
            bg_color=RENK_KIRMIZI,
            fg_color=RENK_BEYAZ,
            font_boyut=20,
            max_w=azami_rozet_w,
        )

        # 3. Metin Alanı: Alttan yukarıya doğru hesaplama
        manset_raw = haber.get("manset") or haber.get("baslik") or "Gündem Özeti"
        spot_raw = haber.get("spot") or haber.get("ozet") or ""

        # Spot metni formatlama (İri, okunaklı editoryal açıklayıcı başlık)
        spot_temiz = _temizle_tipografi(spot_raw)
        punto_spot = 34 if dikey_story else 32
        font_spot = _font_yukle(FONT_SANS, punto_spot)
        spot_satirlari = _metin_sar(spot_temiz, font_spot, kullanilabilir_w, draw) if spot_temiz else []
        while len(spot_satirlari) > 4 and punto_spot > 24:
            punto_spot -= 2
            font_spot = _font_yukle(FONT_SANS, punto_spot)
            spot_satirlari = _metin_sar(spot_temiz, font_spot, kullanilabilir_w, draw)
        spot_satirlari = spot_satirlari[:4]
        spot_lh = int(punto_spot * (1.40 if dikey_story else 1.36))
        spot_h = len(spot_satirlari) * spot_lh

        # Manşet metni formatlama (Fraunces — Dev Editoryal Manşet)
        manset_temiz = _temizle_tipografi(manset_raw)
        punto_manset = 74 if dikey_story else 68
        font_manset = _font_yukle(FONT_FRAUNCES, punto_manset)
        manset_satirlari = _metin_sar(manset_temiz, font_manset, kullanilabilir_w, draw)
        while len(manset_satirlari) > 3 and punto_manset > 46:
            punto_manset -= 2
            font_manset = _font_yukle(FONT_FRAUNCES, punto_manset)
            manset_satirlari = _metin_sar(manset_temiz, font_manset, kullanilabilir_w, draw)
        manset_satirlari = manset_satirlari[:3]

        manset_lh = int(punto_manset * (1.20 if dikey_story else 1.18))
        manset_h = len(manset_satirlari) * manset_lh

        # Pozisyonlama: Alt çizginin üzerinden yukarıya doğru yerleştirme
        spot_ust_y = alt_y - (34 if dikey_story else 28) - spot_h
        manset_ust_y = spot_ust_y - ((28 if dikey_story else 22) if spot_h > 0 else 0) - manset_h

        # 3.1. Kademeli okuma perdesi (Yazı ve kanca hizasına göre dinamik perde)
        if bg_img:
            perde_bas = max(220 if dikey_story else 320, manset_ust_y - (160 if dikey_story else 130))
            perde_son = min(alt_y, manset_ust_y + int(manset_h * 0.80))
            maske = _perde_maskesi_smoothstep(genislik, yukseklik, perde_bas, perde_son)
            koyu_zemin = Image.new("RGB", (genislik, yukseklik), RENK_MUREKKEP)
            canvas = Image.composite(koyu_zemin, canvas, maske)

            # Üst atmosfer vignette (gökyüzünü karartmadan rozet ve logonun kristal kontrastını artırır)
            top_vignette = Image.new("RGBA", (genislik, yukseklik), (0, 0, 0, 0))
            tv_draw = ImageDraw.Draw(top_vignette)
            vignette_son = ust_y + 110
            for vy in range(vignette_son):
                alfa = int(80 * ((vignette_son - vy) / vignette_son) ** 1.6)
                tv_draw.line([(0, vy), (genislik, vy)], fill=(10, 12, 16, alfa))
            canvas = Image.alpha_composite(canvas.convert("RGBA"), top_vignette).convert("RGB")
            draw = ImageDraw.Draw(canvas)

        # 3.2. Editoryal Kanca (Hook) Entegrasyonu (instabot referansı)
        try:
            from . import hook_motoru
            canvas = hook_motoru.hook_uygula(
                canvas=canvas,
                haber=haber,
                manset_ust_y=manset_ust_y,
                ust_y=ust_y,
                olcu=olcu,
            )
            draw = ImageDraw.Draw(canvas)
        except Exception as he:
            log.warning("Hook çiziminde hata (devam ediliyor): %s", he)

        # Difüzyon Gölgesi (Manşet arkasına)
        golge = Image.new("RGBA", (genislik, yukseklik), (0, 0, 0, 0))
        golge_draw = ImageDraw.Draw(golge)
        curr_y = manset_ust_y
        for sat in manset_satirlari:
            golge_draw.text((kenar, curr_y + 4), sat, font=font_manset, fill=(0, 0, 0, 240))
            curr_y += manset_lh
        golge = golge.filter(ImageFilter.GaussianBlur(14))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), golge).convert("RGB")
        draw = ImageDraw.Draw(canvas)

        # Manşet Çizimi
        curr_y = manset_ust_y
        for sat in manset_satirlari:
            draw.text((kenar, curr_y), sat, font=font_manset, fill=RENK_BEYAZ)
            curr_y += manset_lh

        # Spot Çizimi (Büyük & Ferah)
        curr_y = spot_ust_y
        for sat in spot_satirlari:
            draw.text((kenar, curr_y), sat, font=font_spot, fill=RENK_METIN_GOVDE)
            curr_y += spot_lh

        # 4. Alt Taban Barı: İnce mimari çizgi + Kaynak ve Slogan / Sayfa
        draw.line([(kenar, alt_y), (genislik - kenar, alt_y)], fill=RENK_CIZGI_KOYU, width=1)

        kaynak_txt = _kaynak_etiketi(haber)
        foto_atif = (haber.get("foto_atif") or "").strip()
        if foto_atif:
            kaynak_txt = f"{kaynak_txt}  ·  {tr_buyuk(foto_atif)}"
        font_alt = _font_yukle(FONT_MONO, 17)

        if sayfa_no:
            sag_txt = f"{sayfa_no}  ›  KAYDIRIN" if "01" in sayfa_no and olcu == "besleme" and "KAYDIRIN" not in sayfa_no else sayfa_no
        else:
            sag_txt = "@edmyapigayrimenkul · Yatırım Ortağınız"
        bbox_s = draw.textbbox((0, 0), sag_txt, font=font_alt)
        s_w = bbox_s[2] - bbox_s[0]

        # Eski döngü 20 karakterde duruyordu; o noktada hâlâ geniş olan etiket taşıyordu
        kaynak_txt = _etiketi_sigdir(kaynak_txt, font_alt, genislik - (2 * kenar) - s_w - 30, draw)

        draw.text((kenar, alt_y + 20), kaynak_txt, font=font_alt, fill=RENK_KURSUN)
        draw.text((genislik - kenar - s_w, alt_y + 20), sag_txt, font=font_alt, fill=RENK_KURSUN_ACIK if "›" in sag_txt else RENK_KURSUN)

        # Dosyayı kaydet
        canvas.save(cikti_yolu, "JPEG", quality=95)
        log.info("DailyBrief haber slaytı üretildi: %s (%dx%d, olcu=%s)", cikti_yolu.name, genislik, yukseklik, olcu)
        return cikti_yolu


def haber_detay_maddelerini_ayikla(haber: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Haber verisinden editoryal Smart Brevity detay maddelerini normalize edilmiş liste olarak ayıklar."""
    if isinstance(haber, dict):
        dm = haber.get("detay_metni")
        if dm and isinstance(dm, str) and dm.strip().startswith("{"):
            try:
                parsed = json.loads(dm)
                if isinstance(parsed, dict):
                    for k, v in parsed.items():
                        if k not in haber or haber[k] is None:
                            haber[k] = v
            except Exception:
                pass

    maddeler = haber.get("detay_maddeleri") or haber.get("maddeler") or []
    if not maddeler:
        # 1. Öncelik: Haberin gerçek analizi (Ne Oldu + Bölgesel/Sektörel Etki)
        if isinstance(haber.get("slayt_2_detay"), dict):
            s2 = haber["slayt_2_detay"]
            k1 = s2.get("kart_1")
            k2 = s2.get("kart_2")
            if k1 and k2:
                etiket_1 = k1.get("etiket") or k1.get("baslik") or "GÜNCEL GELİŞME"
                metin_1 = k1.get("aciklama") or k1.get("metin") or ""
                etiket_2 = k2.get("etiket") or k2.get("baslik") or "BÖLGESEL & SEKTÖREL ETKİ"
                metin_2 = k2.get("aciklama") or k2.get("metin") or ""
                if metin_1 and metin_2:
                    maddeler = [
                        {"etiket": etiket_1.upper(), "metin": metin_1, "renk": "kirmizi"},
                        {"etiket": etiket_2.upper(), "metin": metin_2, "renk": "kirec"},
                    ]
        # 2. Öncelik: Eğer slayt_2_detay yoksa slayt_3_cozum maddeleri
        if not maddeler:
            s3 = haber.get("slayt_3_cozum")
            if isinstance(s3, dict) and s3.get("maddeler"):
                renk_sira = ["kirmizi", "kirec", "kirec", "kirec", "kirec"]
                maddeler = [
                    {
                        "etiket": m.get("baslik", "DETAY").upper(),
                        "metin": m.get("aciklama", ""),
                        "renk": renk_sira[i % len(renk_sira)],
                    }
                    for i, m in enumerate(s3.get("maddeler", []))
                ]
    if not maddeler:
        detay_ham = haber.get("detay") or haber.get("detay_metni") or haber.get("spot") or haber.get("orijinal_ozet") or ""
        if isinstance(detay_ham, str) and not detay_ham.strip().startswith("{"):
            cumleler = [c.strip() for c in re.split(r"(?<=[.!?])\s+", detay_ham) if len(c.strip()) > 8]
            parcalar = cumleler[:4]
            maddeler = [
                {"etiket": f"AYRINTI {i:02d}", "metin": c, "renk": "kirmizi" if i == 1 else "kirec"}
                for i, c in enumerate(parcalar, start=1)
            ]

    varsayilan_etiketler = [f"AYRINTI {i:02d}" for i in range(1, 5)]
    # Marka paleti: kırmızı yalnızca ilk vurguda, gerisi kireç. Turkuaz, yeşil ve
    # amber marka dışıydı (kurumsal kimlik: %70 nötr / %25 mürekkep / %5 kırmızı).
    KIREC = (228, 228, 225)
    renk_sozlugu = {
        "kirmizi": (240, 0, 13),
        "kirec": KIREC,
        "turkuaz": KIREC,
        "yesil": KIREC,
        "amber": KIREC,
        "sari": KIREC,
    }
    varsayilan_renk_listesi = [(240, 0, 13), KIREC, KIREC, KIREC]

    temiz = []
    for idx, m in enumerate(maddeler):
        if isinstance(m, dict):
            e = m.get("etiket") or m.get("baslik") or varsayilan_etiketler[idx % len(varsayilan_etiketler)]
            t = m.get("metin") or m.get("aciklama") or m.get("govde") or ""
            r_val = m.get("renk")
            if isinstance(r_val, tuple) and len(r_val) == 3:
                r = r_val
            else:
                r = renk_sozlugu.get(str(r_val).lower(), varsayilan_renk_listesi[idx % len(varsayilan_renk_listesi)])
        else:
            m_str = str(m).strip()
            if ":" in m_str:
                e_part, t_part = m_str.split(":", 1)
                e = e_part.strip().upper()
                t = t_part.strip()
            else:
                e = varsayilan_etiketler[idx % len(varsayilan_etiketler)]
                t = m_str
            r = varsayilan_renk_listesi[idx % len(varsayilan_renk_listesi)]
        temiz.append({"etiket": str(e).upper(), "metin": str(t).strip(), "renk": r})
    return temiz


def dailybrief_slayt_sayisi_belirle(
    haber: Dict[str, Any],
    maddeler: Optional[List[Dict[str, Any]]] = None,
) -> int:
    """
    Haberin kapsamına göre dinamik slayt sayısı belirler (Seçenek 2):
    - Açıkça belirtilmişse (slayt_sayisi=2 veya 3) onu kullanır.
    - 3 ve üzeri madde varsa -> 3 slayt (Kapak + 2 Teknik Detay + Yasal Takvim/Uzman Stratejisi)
    - 2 madde varsa:
        Eğer maddeler teknik açıdan zenginse (parsel, imar, ada, askı, emsal, kanun, resmi gazete vb. içeriyorsa
        veya toplam metin uzunluğu >= 130 karakterse) -> 3 slayt (Maddeler 2 sayfaya ferahça dağıtılır)
        Kısa ve özet maddeler ise -> 2 slayt
    - 0 veya 1 madde varsa:
        Detay metni / spot uzunluğu incelenir: >= 200 karakter veya 3+ cümle ise -> 3 slayt
        Kısa özet haber ise -> 2 slayt
    """
    if haber.get("slayt_sayisi") in (2, 3):
        return int(haber["slayt_sayisi"])

    if maddeler is None:
        maddeler = haber_detay_maddelerini_ayikla(haber)

    sayi = len(maddeler)
    if sayi >= 3:
        return 3

    if sayi == 2:
        toplam_uzunluk = sum(len(m.get("metin", "")) for m in maddeler)
        anahtar_kelimeler = ["parsel", "ada", "imar", "askı", "kaks", "emsal", "yargıtay", "kanun", "madde", "resmi gazete", "ruhsat", "iskan"]
        tum_metin = " ".join(m.get("metin", "") + " " + m.get("etiket", "") for m in maddeler).lower()
        has_anahtar = any(k in tum_metin for k in anahtar_kelimeler)
        if toplam_uzunluk >= 130 or has_anahtar:
            return 3
        return 2

    detay_ham = (haber.get("detay") or haber.get("detay_metni") or haber.get("orijinal_ozet") or haber.get("spot") or "").strip()
    if len(detay_ham) >= 200:
        return 3
    return 2


def haber_dailybrief_detay_slayti_ciz(
    haber: Dict[str, Any],
    foto_yolu: Optional[Path | str] = None,
    cikti_yolu: Optional[Path] = None,
    olcu: str = "besleme",
    sayfa_no: str = "02 / 02",
    maddeler: Optional[List[Dict[str, Any]]] = None,
    ust_etiket: Optional[str] = None,
    goster_uzman_notu: bool = True,
    asgari_punto: int = 28,
) -> Path:
    """
    DailyBrief Haber Detay Slaytı (Ayrıntılar & EDM Uzman Analizi):
    Instabot Smart Brevity mimarisi paritesi:
    - 1. slaytın spotuyla birebir aynı gövde fontuyla (IBM Plex Sans).
    - Haberin kritik detayları: Kapsanan alanlar/parseller, imar/yapılaşma koşulları, askı süresi ve yasal haklar.
    - Her maddenin solunda mimari dikey renk çentiği (Accent Notch).
    - İsteğe bağlı EDM Uzman Değerlendirmesi & Yatırımcı Tavsiyesi kartı (goster_uzman_notu=True).
    - 4:5 tuvaline göre hizalı, 9:16 Story/Reels ile tam güvenli alan uyumlu.
    """
    # Uzman notu yalnızca içerikte varsa çizilir. Eskiden yoksa her habere
    # "askı panolarından kontrol edin; itiraz süresini kaçırmayın" basılıyordu —
    # haber imarla ilgili olmasa da.
    uzman_notu = (haber.get("uzman_notu") or haber.get("cikarilacak_ders") or haber.get("stratejist_notu") or "").strip()
    if not uzman_notu and isinstance(haber.get("slayt_4_cta"), dict):
        uzman_notu = str(haber["slayt_4_cta"].get("aciklama", "")).strip()
    if uzman_notu:
        uzman_notu = re.sub(r"^(?:EDM\s+)?(?:Uzman\s+)?(?:Değerlendirmesi|Analizi|Notu|Stratejisi)\s*:\s*", "", uzman_notu, flags=re.IGNORECASE).strip()
    if not uzman_notu:
        goster_uzman_notu = False

    with tuval(olcu):
        genislik = GENISLIK
        yukseklik = YUKSEKLIK
        kenar = 70
        kullanilabilir_w = genislik - (2 * kenar)

        # Dikey Story (9:16) ve Besleme (4:5) güvenli alanları
        dikey_story = yukseklik >= 1700
        if dikey_story:
            ust_y = 260  # Meta 9:16 Story güvenli alanı: Instagram profil avatarı ve X butonunun altında kalır
            alt_y = yukseklik - 250  # 1670 px (Instagram mesaj/yanıt barı güvenli alanı)
        else:
            ust_y = 62
            alt_y = 1250

        if cikti_yolu is None:
            cikti_yolu = config.yol_al(f"data/output/haber_dailybrief_detay_{os.getpid()}_{int(time.time())}.jpg")
        else:
            cikti_yolu = Path(cikti_yolu)
        cikti_yolu.parent.mkdir(parents=True, exist_ok=True)

        # 1. Arka Plan Hazırla: Derin koyu pafta zemini veya fotoğraflı derin perde
        bg_img: Optional[Image.Image] = None
        if foto_yolu:
            fp = Path(foto_yolu)
            if fp.exists() and fp.is_file():
                try:
                    bg_img = ImageOps.exif_transpose(Image.open(fp)).convert("RGB")
                except Exception as fe:
                    log.warning("Detay slaytı arka plan fotoğrafı açılamadı: %s", fe)

        if bg_img:
            bg_w, bg_h = bg_img.size
            oran = max(genislik / bg_w, yukseklik / bg_h)
            yeni_w = int(bg_w * oran)
            yeni_h = int(bg_h * oran)
            bg_olcekli = bg_img.resize((yeni_w, yeni_h), Image.Resampling.LANCZOS)
            kirp_x = max(0, (yeni_w - genislik) // 2)
            kirp_y = max(0, (yeni_h - yukseklik) // 2)
            bg_kirp = bg_olcekli.crop((kirp_x, kirp_y, kirp_x + genislik, kirp_y + yukseklik))
            bg_kirp = bg_kirp.filter(ImageFilter.GaussianBlur(30))

            canvas = Image.new("RGB", (genislik, yukseklik), RENK_MUREKKEP)
            canvas.paste(bg_kirp, (0, 0))

            # Detay slaytında yazının %100 okunması için derin cam perde (alpha overlay)
            perde = Image.new("RGBA", (genislik, yukseklik), (10, 13, 19, 242))
            canvas = Image.alpha_composite(canvas.convert("RGBA"), perde).convert("RGB")
        else:
            canvas = _zemin_uret("murekkep", olcu=olcu)

        canvas = _filigran_uygula(canvas, acik_zemin=False)
        draw = ImageDraw.Draw(canvas)

        # 2. Üst Bar: Sol üstte zarif editoryal etiket, Sağ üstte Dev EDM Logosu (lw=285)
        logo_w = 285
        logo_x = genislik - kenar - logo_w
        _logo_yerlestir(
            canvas,
            beyaz=True,
            x=logo_x,
            y=ust_y - 5,
            lw=logo_w,
            golge=True,
            kirmizi_zemin=False,
        )
        draw = ImageDraw.Draw(canvas)

        if not ust_etiket:
            # Üst etiket içerik türü İDDİA ETMEZ: eskiden her habere "TEKNİK PLAN", "MEVZUAT",
            # "YASAL SÜREÇ" yazılıyordu — haber öyle bir şey içermese de.
            ust_etiket = "// HABERİN AYRINTILARI"

        font_top_etiket = _font_yukle(FONT_MONO_BOLD, 21)

        # 3. İçerik Detayları — hepsi (eskiden [:3] ile dördüncü madde düşüyordu)
        temiz_maddeler = maddeler if maddeler is not None else haber_detay_maddelerini_ayikla(haber)

        # 4-5. Ölçerek yerleşim: başlangıç puntosu madde sayısından, sığmazsa 28px'e
        # kadar küçülür. Eskiden madde metni [:3]/[:4] satırda SESSİZCE kesiliyordu.
        n = len(temiz_maddeler)
        if dikey_story:
            bas_govde = (46 if n <= 1 else 42 if n == 2 else 38) if not goster_uzman_notu else (44 if n <= 1 else 40 if n == 2 else 36)
            uzman_bas = 40 if n <= 1 else (36 if n == 2 else 34)
            y_kursur = ust_y + 105
        else:
            bas_govde = (42 if n <= 1 else 38 if n == 2 else 34) if not goster_uzman_notu else (40 if n <= 1 else 36 if n == 2 else 32)
            uzman_bas = 38 if n <= 1 else (34 if n == 2 else 32)
            y_kursur = ust_y + 85
        yerlesim_bulundu = False
        # Rahatlık eşiği başlangıç puntosunu aşamaz (uzman notlu 3 maddede başlangıç 32)
        for govde_p in range(bas_govde, min(asgari_punto, bas_govde) - 1, -2):
            etiket_p = govde_p + 6
            font_madde_etiket = _font_yukle(FONT_SANS_BOLD, etiket_p)
            font_madde_govde = _font_yukle(FONT_SANS, govde_p)
            lh_govde = int(govde_p * (1.44 if dikey_story else 1.42))
            lh_etiket = int(etiket_p * 1.18)
            if goster_uzman_notu:
                uzman_p = min(uzman_bas, govde_p + 2)
                font_uzman_etiket = _font_yukle(FONT_MONO_BOLD, 24 if dikey_story else 22)
                font_uzman_govde = _font_yukle(FONT_SANS_BOLD, uzman_p)
                uzman_lh = int(uzman_p * (1.42 if dikey_story else 1.4))
                pad_y = 30 if dikey_story else 24
                uzman_satirlari = _metin_sar(_temizle_tipografi(uzman_notu), font_uzman_govde, kullanilabilir_w - 60, draw)
                uzman_kart_h = pad_y + (30 if dikey_story else 26) + 14 + (len(uzman_satirlari) * uzman_lh) + pad_y
                uzman_kart_y = alt_y - (35 if dikey_story else 25) - uzman_kart_h
                kalan_h = (uzman_kart_y - (38 if dikey_story else 30)) - y_kursur
            else:
                uzman_kart_h = 0
                uzman_kart_y = alt_y - (35 if dikey_story else 25)
                kalan_h = (alt_y - (35 if dikey_story else 25)) - y_kursur

            maddeler_olculu = []
            for m in temiz_maddeler:
                etiket_satirlari = _metin_sar(_temizle_tipografi(m["etiket"]), font_madde_etiket, kullanilabilir_w - 38, draw)
                satirlar_m = _metin_sar(_temizle_tipografi(m["metin"]), font_madde_govde, kullanilabilir_w - 38, draw)
                h_etiket = len(etiket_satirlari) * lh_etiket
                maddeler_olculu.append({
                    "etiket_satirlari": etiket_satirlari,
                    "satirlar": satirlar_m,
                    "renk": m["renk"],
                    "h_etiket": h_etiket,
                    "h": h_etiket + (16 if dikey_story else 14) + (len(satirlar_m) * lh_govde),
                })
            if sum(mo["h"] for mo in maddeler_olculu) + (45 if dikey_story else 35) * max(0, n - 1) <= kalan_h:
                yerlesim_bulundu = True
                break
        if not yerlesim_bulundu:
            raise TasmaHatasi(f"Haber detay slaytına sığmadı ({n} madde)")

        # Üst etiket ölçüm GEÇTİKTEN sonra çizilir: başarısız deneme tuvale hiçbir şey çizmez
        draw.text((kenar, ust_y + 12), ust_etiket, font=font_top_etiket, fill=RENK_KURSUN_ACIK)
        draw.line([(kenar, ust_y + 60), (genislik - kenar, ust_y + 60)], fill=RENK_CIZGI_KOYU, width=1)

        madde_sayisi = max(1, n)
        toplam_madde_h = sum(mo["h"] for mo in maddeler_olculu)
        bosluk = (kalan_h - toplam_madde_h) // max(1, len(maddeler_olculu) - 1)
        max_bosluk = (140 if not goster_uzman_notu else 100) if dikey_story else (90 if not goster_uzman_notu else 75)
        min_bosluk = 45 if dikey_story else 35
        bosluk = max(min_bosluk, min(max_bosluk, bosluk))

        toplam_blok_h = toplam_madde_h + (bosluk * max(0, madde_sayisi - 1))
        curr_m_y = y_kursur + max(0, (kalan_h - toplam_blok_h) // 2)

        # Maddeleri Çiz (Açık, ferah ve güçlü mimari akış)
        notch_w = (12 if dikey_story else 10) if (not goster_uzman_notu or len(temiz_maddeler) <= 1) else (10 if dikey_story else 8)
        notch_pad = 36 if dikey_story else (32 if notch_w >= 10 else 28)
        for mo in maddeler_olculu:
            m_h = mo["h"]
            draw.rounded_rectangle([kenar, curr_m_y + 3, kenar + notch_w, curr_m_y + m_h - 4], radius=4, fill=mo["renk"])
            ey = curr_m_y
            for es in mo["etiket_satirlari"]:
                draw.text((kenar + notch_pad, ey), es, font=font_madde_etiket, fill=mo["renk"])
                ey += lh_etiket

            gy = curr_m_y + mo["h_etiket"] + 12
            for s in mo["satirlar"]:
                draw.text((kenar + notch_pad, gy), s, font=font_madde_govde, fill=RENK_METIN_GOVDE)
                gy += lh_govde

            curr_m_y += m_h + bosluk

        # 6. EDM Uzman Değerlendirmesi Kartı Çizimi (goster_uzman_notu=True ise)
        if goster_uzman_notu:
            draw.rounded_rectangle([(kenar, uzman_kart_y), (genislik - kenar, uzman_kart_y + uzman_kart_h)], radius=14, fill=(20, 24, 34), outline=(55, 65, 85), width=1)
            draw.rounded_rectangle([(kenar, uzman_kart_y), (kenar + 8, uzman_kart_y + uzman_kart_h)], radius=3, fill=RENK_UZMAN_CUBUK)
            draw.text((kenar + 28, uzman_kart_y + pad_y), "// EDM DEĞERLENDİRMESİ:", font=font_uzman_etiket, fill=RENK_UZMAN_ETIKET)

            uy = uzman_kart_y + pad_y + 26 + 14
            for s in uzman_satirlari:
                draw.text((kenar + 28, uy), s, font=font_uzman_govde, fill=RENK_BEYAZ)
                uy += uzman_lh

        # 7. Alt Taban Barı: İnce mimari çizgi + Kaynak ve Slogan / Sayfa
        draw.line([(kenar, alt_y), (genislik - kenar, alt_y)], fill=RENK_CIZGI_KOYU, width=1)

        font_alt = _font_yukle(FONT_MONO, 17)
        bbox_s = draw.textbbox((0, 0), sayfa_no, font=font_alt)
        s_w = bbox_s[2] - bbox_s[0]
        # Kaynak etiketi sayfa numarasına binmesin (uzun kaynak adı üstüne biniyordu)
        kaynak_txt = _etiketi_sigdir(_kaynak_etiketi(haber), font_alt, genislik - 2 * kenar - s_w - 30, draw)
        draw.text((kenar, alt_y + 20), kaynak_txt, font=font_alt, fill=RENK_KURSUN)
        draw.text((genislik - kenar - s_w, alt_y + 20), sayfa_no, font=font_alt, fill=RENK_KURSUN_ACIK if "›" in sayfa_no else RENK_KURSUN)

        # Dosyayı kaydet
        canvas.save(cikti_yolu, "JPEG", quality=95)
        log.info("DailyBrief haber detay slaytı üretildi: %s (%dx%d, olcu=%s)", cikti_yolu.name, genislik, yukseklik, olcu)
        return cikti_yolu


def _sayfalari_dengeli_bol(
    maddeler: List[Dict[str, Any]],
    sayfa_sayisi: int = 2,
    has_uzman_notu_son_sayfa: bool = True,
) -> List[List[Dict[str, Any]]]:
    """
    Instabot c148a2a standardı: Maddeleri detay sayfaları arasında varyansı
    minimize ederek ve yetim blok kalmasını önleyerek dengeli biçimde paylaştırır.
    Açgözlü yaklaşımın 2. sayfayı tıkış tıkış doldurup 3. sayfada tek satır bırakmasını engeller.
    """
    if not maddeler:
        return [[] for _ in range(sayfa_sayisi)]
    n = len(maddeler)
    if sayfa_sayisi <= 1 or n <= 1:
        return [maddeler]

    if sayfa_sayisi == 2:
        uzman_agirligi = 90 if has_uzman_notu_son_sayfa else 0
        en_iyi_cut = 1
        en_iyi_fark = float("inf")

        for cut in range(1, n):
            p1 = maddeler[:cut]
            p2 = maddeler[cut:]
            h1 = sum(len(m.get("metin", "")) + 40 for m in p1)
            h2 = sum(len(m.get("metin", "")) + 40 for m in p2) + uzman_agirligi
            fark = abs(h1 - h2)
            if fark < en_iyi_fark:
                en_iyi_fark = fark
                en_iyi_cut = cut

        return [maddeler[:en_iyi_cut], maddeler[en_iyi_cut:]]

    import itertools
    en_iyi_bolum = None
    en_iyi_skor = float("inf")
    k = sayfa_sayisi
    for cuts in itertools.combinations(range(1, n), k - 1):
        idx = [0] + list(cuts) + [n]
        parts = [maddeler[idx[i]:idx[i + 1]] for i in range(k)]
        heights = []
        for i, p in enumerate(parts):
            h = sum(len(m.get("metin", "")) + 40 for m in p)
            if i == k - 1 and has_uzman_notu_son_sayfa:
                h += 90
            heights.append(h)

        h_avg = sum(heights) / k
        var_cost = sum((h - h_avg) ** 2 for h in heights)
        diff_cost = (max(heights) - min(heights)) * 50
        bos_ceza = sum(100000 for p in parts if len(p) == 0)
        skor = var_cost + diff_cost + bos_ceza
        if skor < en_iyi_skor:
            en_iyi_skor = skor
            en_iyi_bolum = parts

    return en_iyi_bolum if en_iyi_bolum is not None else [maddeler[:n//2], maddeler[n//2:]]


def _haber_slayt_ust_etiketi(bolum: List[Dict[str, Any]], slayt_no: int, toplam_slayt: int) -> str:
    """Detay slaytı için içerikle uyumlu, editoryal üst etiket üretir."""
    metinler = " ".join(
        (str(m.get("etiket", "")) + " " + str(m.get("metin", ""))) for m in bolum
    ).upper()

    if any(k in metinler for k in ("BÖLGESEL", "PİYASA", "FİYAT", "TRAKYA", "SİLİVRİ", "ÇATALCA", "EMSAL", "ETKİ")):
        return "// BÖLGESEL PİYASAYA ETKİSİ VE ANALİZ"
    if any(k in metinler for k in ("RİSK", "HUKUK", "ŞART", "BAŞVURU", "TEMİNAT", "DİKKAT", "HAKLAR", "İTİRAZ")):
        return "// BAŞVURU ŞARTLARI VE DİKKAT EDİLECEKLER"
    if any(k in metinler for k in ("RESMİ", "İHALE", "DUYURU", "GELİŞME", "PROJE", "PARSEL", "METREKARE")):
        return "// RESMİ GELİŞME VE İHALE DETAYLARI"

    # Varsayılan editoryal hiyerarşi
    if slayt_no == 2:
        return "// HABERİN AYRINTILARI"
    elif slayt_no == 3 and slayt_no == toplam_slayt:
        return "// PİYASA ANALİZİ VE DEĞERLENDİRME"
    elif slayt_no == 3:
        return "// PİYASAYA VE BÖLGEYE ETKİSİ"
    elif slayt_no == 4:
        return "// DİKKAT EDİLECEK RİSKLER VE SÜREÇ"
    return "// HABERİN AYRINTILARI"


@_gorsel_girdisi
def haber_dailybrief_slaytlari_uret(
    haber: Dict[str, Any],
    cikti_dizini: Optional[Path] = None,
    cikti_onek: str = "dailybrief",
    olcu: str = "besleme",
    foto_yolu: Optional[Path | str] = None,
) -> List[Path]:
    """
    EDM Gündem // Haber Bülteni Çok Slaytlı Carousel Üreticisi:
    - Kapak: Gazetecilik usulü doğal manşet + 2-3 cümlelik editoryal spot + kurumsal kimlik.
    - Detay Slaytları: Haberin kapsamına göre dinamik 2-3-4 slayt (ferah, 34-40px punto, sol mimari çentik).
    - Kapanış: EDM Uzman Değerlendirmesi & Yatırımcı Stratejisi kutusu.
    """
    if cikti_dizini is None:
        cikti_dizini = config.yol_al("data/output/gonderiler")
    cikti_dizini = Path(cikti_dizini)
    cikti_dizini.mkdir(parents=True, exist_ok=True)

    if isinstance(haber, dict):
        dm = haber.get("detay_metni")
        if dm and isinstance(dm, str) and dm.strip().startswith("{"):
            try:
                parsed = json.loads(dm)
                if isinstance(parsed, dict):
                    for k, v in parsed.items():
                        if k not in haber or haber[k] is None:
                            haber[k] = v
            except Exception:
                pass

    if not haber.get("manset"):
        m1 = haber.get("manset_parca_1", "")
        mv = haber.get("manset_vurgu", "")
        m2 = haber.get("manset_parca_2", "")
        haber["manset"] = f"{m1} {mv} {m2}".strip() or haber.get("orijinal_baslik", "")
    if not str(haber.get("manset") or "").strip():
        haber["manset"] = str(haber.get("orijinal_baslik") or haber.get("baslik") or "").strip()
    if not str(haber.get("manset") or "").strip():
        raise EksikIcerik("Haber: manşet yok")

    if not haber.get("spot"):
        haber["spot"] = haber.get("orijinal_ozet") or haber.get("ozet") or ""

    fp = foto_yolu or haber.get("foto_yolu") or haber.get("gorsel_yolu") or haber.get("gorsel_url")
    maddeler = haber_detay_maddelerini_ayikla(haber)
    uzman_var = bool((haber.get("uzman_notu") or haber.get("cikarilacak_ders") or haber.get("stratejist_notu") or "").strip()
                     or (isinstance(haber.get("slayt_4_cta"), dict) and str(haber["slayt_4_cta"].get("aciklama") or "").strip()))

    p1 = cikti_dizini / f"{cikti_onek}_dailybrief_s1.jpg"
    if not maddeler and not uzman_var:
        haber_dailybrief_slayti_ciz(haber=haber, foto_yolu=fp, cikti_yolu=p1, olcu=olcu, sayfa_no="01 / 01")
        return [p1]

    istenen = haber.get("slayt_sayisi")
    if istenen in (2, 3, 4):
        denenecek = [int(istenen) - 1]
    else:
        n_maddeler = len(maddeler)
        toplam_metin_len = sum(len(str(m.get("metin", ""))) for m in maddeler)
        if n_maddeler >= 5:
            denenecek = [3, 2, 4]
        elif n_maddeler >= 4:
            denenecek = [2, 3, 1]
        elif n_maddeler == 3:
            # Uzun/zengin maddeler (toplam > 240 karakter) 2 detay slaytına yayılır; kısa maddeler tek detay slaytında kalır
            if toplam_metin_len > 240:
                denenecek = [2, 3, 1]
            else:
                denenecek = [1, 2]
        elif n_maddeler == 2:
            if toplam_metin_len > 240 and uzman_var:
                denenecek = [2, 1]
            else:
                denenecek = [1, 2]
        else:
            denenecek = [1]

    for detay_sayisi in denenecek:
        # Az slayt tercihi yalnızca metin rahat okunurken (≥34px); son deneme 28px'e iner
        asgari = 28 if detay_sayisi == denenecek[-1] else 34
        if detay_sayisi > 1 and len(maddeler) < detay_sayisi:
            continue
        bolumler = [maddeler] if detay_sayisi == 1 else _sayfalari_dengeli_bol(maddeler, sayfa_sayisi=detay_sayisi, has_uzman_notu_son_sayfa=uzman_var)
        toplam = 1 + detay_sayisi
        yollar = []
        try:
            for i, bolum in enumerate(bolumler, start=2):
                son_mu = i == toplam
                yol = cikti_dizini / f"{cikti_onek}_dailybrief_s{i}.jpg"
                sayfa = f"{i:02d} / {toplam:02d}" + ("" if son_mu else "  ›  KAYDIRIN")
                etiket = _haber_slayt_ust_etiketi(bolum, i, toplam)
                haber_dailybrief_detay_slayti_ciz(
                    haber=haber, foto_yolu=fp, cikti_yolu=yol, olcu=olcu, sayfa_no=sayfa, maddeler=bolum,
                    ust_etiket=etiket,
                    goster_uzman_notu=son_mu,
                    asgari_punto=asgari,
                )
                yollar.append(yol)
        except TasmaHatasi:
            for y in yollar:
                Path(y).unlink(missing_ok=True)
            continue
        haber_dailybrief_slayti_ciz(haber=haber, foto_yolu=fp, cikti_yolu=p1, olcu=olcu, sayfa_no=f"01 / {toplam:02d}")
        log.info("DailyBrief %d slayt üretildi", toplam)
        return [p1] + yollar
    raise TasmaHatasi(f"Haber {len(maddeler)} madde; üç detay slaytına da sığmadı")



