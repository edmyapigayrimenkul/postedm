"""
src/cizim/fikir.py — Kutusuz, Tek ve İkili Fikir Slaytı Çizimleri
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw

from .sabitler import (
    FONT_SANS_BOLD,
    FONT_SANS_MEDIUM,
    GENISLIK,
    OPTIK_KALDIRMA,
    RENK_BEYAZ,
    RENK_YESIL,
    YUKSEKLIK,
)
from .fontlar import _govde_sigdir
from .tuval import _yerlesim
from .bilesenler import _rozet_ciz, _slayt_cercevesi

log = logging.getLogger(__name__)


def _fikir_blogu_olc(
    draw: ImageDraw.ImageDraw,
    etiket: str,
    baslik: str,
    govde: str,
    genislik: int,
    baslik_punto: int = 52,
    govde_punto: int = 38,
) -> Dict[str, Any]:
    """Bir 'fikir' bloğunun fontlarını ve toplam yüksekliğini hesaplar."""
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
    """Ölçülmüş bloğu verilen yüksekliğe kilitler."""
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
    """Adım numarasını iki haneye indirger."""
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
    """İki fikir tek karede — yalnızca metin kısa olduğunda (karma mimari)."""
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
