"""
src/cizim/tipografi.py — Tipografi, glif süzme, Türkçe metin dönüşümleri ve satır sarma motoru.
"""

from __future__ import annotations

import functools
import inspect
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import ImageDraw, ImageFont

from .. import filtre
from . import sabitler

log = logging.getLogger(__name__)

_GORSEL_KARSILIK = str.maketrans({
    "→": "–", "⇒": "–", "➔": "–", "➜": "–", "⟶": "–", "←": "–",
    "●": "•", "■": "•", "▪": "•", "◆": "•", "◾": "•", "◼": "•", "►": "•", "▶": "•",
})
_ORTAK_GLIFLER: Optional[frozenset] = None
_METIN_OLMAYAN_ANAHTAR = ("yol", "url", "dosya", "foto", "gorsel", "resim", "link")


def _ortak_glifler() -> frozenset:
    """Kartlarda kullanılan bütün fontlarda bulunan karakterler (kesişim kümesi)."""
    global _ORTAK_GLIFLER
    if _ORTAK_GLIFLER is None:
        try:
            from fontTools.ttLib import TTFont
            f_yollar = (sabitler.FONT_FRAUNCES, sabitler.FONT_SANS_REGULAR, sabitler.FONT_SANS_MEDIUM,
                        sabitler.FONT_SANS_SEMIBOLD, sabitler.FONT_SANS_BOLD, sabitler.FONT_MONO, sabitler.FONT_MONO_BOLD)
            kumeler = [set(TTFont(str(f), lazy=True).getBestCmap()) for f in f_yollar if Path(f).is_file()]
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
        if ch == "\n" or (ch.isspace() and temiz.append(" ") is None):
            if ch == "\n":
                temiz.append(ch)
        elif unicodedata.category(ch)[0] in ("C", "M") and unicodedata.category(ch) != "Me":
            continue
        elif (glifler and ord(ch) not in glifler) or (not glifler and (ord(ch) > 0xFFFF or unicodedata.category(ch) == "So")):
            continue
        else:
            temiz.append(ch)
    sonuc = "".join(temiz)
    return metin if sonuc == metin else "\n".join(re.sub(r" {2,}", " ", s).strip() for s in sonuc.split("\n"))


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


def tr_ilk_buyuk(metin: str) -> str:
    """İlk harfi Türkçe kurala göre büyütür: str.upper() "ilk"i "Ilk" yapıyordu."""
    if not metin:
        return metin
    return ({"i": "İ", "ı": "I"}.get(metin[0], metin[0].upper())) + metin[1:]


def _kaynak_etiketi(haber: Dict[str, Any]) -> str:
    kaynak = str(haber.get("kaynak") or "").strip()
    return "EDM YAPI & GAYRİMENKUL" if not kaynak or kaynak.startswith("EDM") else f"KAYNAK: {tr_buyuk(kaynak)}"


def _etiketi_sigdir(metin: str, font: ImageFont.FreeTypeFont, azami: int, draw: ImageDraw.ImageDraw) -> str:
    if draw.textbbox((0, 0), metin, font=font)[2] <= azami:
        return metin
    kelimeler = metin.split()
    while kelimeler and draw.textbbox((0, 0), " ".join(kelimeler) + "…", font=font)[2] > azami:
        kelimeler.pop()
    return (" ".join(kelimeler) + "…") if kelimeler else ""


def _is_para_birimi(w: str) -> bool:
    clean = w.strip(".,;:!?*()[]_")
    return clean in sabitler.PARA_BIRIMLERI or any(clean.endswith(p) or clean.startswith(p) for p in sabitler.PARA_BIRIMLERI)


def _is_sayi(w: str) -> bool:
    return re.sub(r"[\.,]", "", w.strip("*_()[]")).isdigit()


def _is_unvan_veya_on_ek(w: str) -> bool:
    if not w:
        return False
    clean = w.lower().strip("*_()[]")
    return clean in sabitler.UNVAN_VE_KISALTMALAR or bool(re.match(r"^\d+\.$", clean))


def _temizle_tipografi(metin: str) -> str:
    """Metindeki kaçış dizilerini (\\n), markdown yıldızlarını (**) ve eksik glifleri temizler."""
    if not metin:
        return ""
    temiz = filtre.markdown_temizle(metin)
    glifler = {
        "➔": "→", "➜": "→", "➤": "→", "👉": "→", "🎯": "◆", "📌": "■",
        "📈": "▲", "📉": "▼", "“": '"', "”": '"', "’": "'", "‘": "'", "…": "...",
    }
    for bozuk, duzgun in glifler.items():
        temiz = temiz.replace(bozuk, duzgun)
    return " ".join(temiz.split())


def _kelimeyi_bol(kelime: str, font: ImageFont.FreeTypeFont, azami_genislik: int, draw: ImageDraw.ImageDraw) -> List[str]:
    parcalar, kalan = [], kelime
    while kalan:
        if draw.textbbox((0, 0), kalan, font=font)[2] <= azami_genislik:
            parcalar.append(kalan)
            break
        dusuk, yuksek = 1, len(kalan)
        while dusuk < yuksek:
            orta = (dusuk + yuksek + 1) // 2
            if draw.textbbox((0, 0), kalan[:orta], font=font)[2] <= azami_genislik:
                dusuk = orta
            else:
                yuksek = orta - 1
        parcalar.append(kalan[:dusuk])
        kalan = kalan[dusuk:]
    return parcalar


def _metin_sar(
    metin: str,
    font: ImageFont.FreeTypeFont,
    azami_genislik: int,
    draw: ImageDraw.ImageDraw,
    kelime_bol: bool = True,
) -> List[str]:
    """Metni piksel genişliğine göre satırlara böler. Akıllı yapışkanlık kuralları uygular."""
    metin = _temizle_tipografi(metin)[:sabitler.AZAMI_SARILACAK]
    if azami_genislik < 8:
        return []
    kelimeler = metin.split()
    satirlar: List[str] = []
    mevcut: List[str] = []

    def ekle_veya_bol(parca: str) -> None:
        nonlocal mevcut
        if draw.textbbox((0, 0), parca, font=font)[2] <= azami_genislik:
            mevcut = [parca]
        elif kelime_bol:
            parcalar = _kelimeyi_bol(parca, font, azami_genislik, draw)
            satirlar.extend(parcalar[:-1])
            mevcut = [parcalar[-1]] if parcalar else []
        else:
            satirlar.append(parca)
            mevcut = []

    for k in kelimeler:
        deneme = " ".join(mevcut + [k])
        if draw.textbbox((0, 0), deneme, font=font)[2] <= azami_genislik:
            mevcut.append(k)
            continue

        tasinanlar: List[str] = []

        # Kural 1: Para / birim sembolü
        if _is_para_birimi(k) and mevcut:
            if (
                len(mevcut) >= 2
                and mevcut[-1].lower().strip("*") in sabitler.BUYUKLUK_KELIMELERI
                and _is_sayi(mevcut[-2])
            ):
                if len(mevcut) > 2:
                    b, s = mevcut.pop(), mevcut.pop()
                    tasinanlar = [s, b]
            elif _is_sayi(mevcut[-1]):
                if len(mevcut) > 1:
                    tasinanlar = [mevcut.pop()]

        # Kural 2: Büyüklük (bin, milyon)
        elif k.lower().strip("*") in sabitler.BUYUKLUK_KELIMELERI and mevcut:
            if _is_sayi(mevcut[-1]) and len(mevcut) > 1:
                tasinanlar = [mevcut.pop()]

        # Kural 3: Unvan / ön ek
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
            for parca in yeni_aday:
                if not mevcut:
                    ekle_veya_bol(parca)
                else:
                    deneme_parca = " ".join(mevcut + [parca])
                    if draw.textbbox((0, 0), deneme_parca, font=font)[2] <= azami_genislik:
                        mevcut.append(parca)
                    else:
                        satirlar.append(" ".join(mevcut))
                        ekle_veya_bol(parca)

    if mevcut:
        satirlar.append(" ".join(mevcut))
    return satirlar
