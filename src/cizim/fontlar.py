"""
src/cizim/fontlar.py — Font yükleme, metin sığdırma ve dikey yerleşim yardımcıları.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional, Tuple

from PIL import ImageDraw, ImageFont

from . import sabitler, tipografi

log = logging.getLogger(__name__)


def _font_yukle(yol: Path, boyut: int) -> ImageFont.FreeTypeFont:
    """TTF fontunu belirtilen boyutta yükler."""
    try:
        if Path(yol).exists():
            return ImageFont.truetype(str(yol), boyut)
    except Exception as e:
        log.warning("Font yükleme hatası (%s, %d): %s", yol, boyut, e)
    return ImageFont.load_default()


def _font(punto: int, eksenler: Optional[List[float]] = None) -> ImageFont.FreeTypeFont:
    """Instabot uyumluluk köprüsü: punto ve opsiyonel eksenlerle font yükler."""
    return _font_yukle(sabitler.FONT_SANS, punto)


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
        satirlar = tipografi._metin_sar(metin, f, azami_w, draw)
        if len(satirlar) <= max_satir:
            return f, satirlar
        boyut -= 2
    f = _font_yukle(font_yolu, min_boyut)
    satirlar = tipografi._metin_sar(metin, f, azami_w, draw)
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
    """Gövde metnini KIRPMADAN sığdırır: satır sayısı aşılırsa font küçültülür."""
    boyut = baslangic_boyut
    while boyut >= min_boyut:
        f = _font_yukle(font_yolu, boyut)
        satirlar = tipografi._metin_sar(metin, f, azami_w, draw, kelime_bol=False)
        if len(satirlar) <= azami_satir and all(draw.textbbox((0, 0), s, font=f)[2] <= azami_w for s in satirlar):
            return f, satirlar
        boyut -= 1
    f = _font_yukle(font_yolu, min_boyut)
    return f, tipografi._metin_sar(metin, f, azami_w, draw, kelime_bol=True)


def _ek_dolgu_hesapla(
    yukseklikler: List[int],
    ust: int,
    alt: int,
    asgari_bosluk: int = 18,
    azami_ek: int = 72,
) -> int:
    """Kart başına eklenecek iç dolguyu döner."""
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
    """Blokları [ust, alt] aralığına dağıtır ve her birinin Y konumunu döner."""
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
