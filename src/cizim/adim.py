"""
src/cizim/adim.py — Adım Slaytları (Tek Adım ve Toplu Adımlar) Çizimleri
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw

from .sabitler import (
    FONT_FRAUNCES,
    FONT_MONO_BOLD,
    FONT_SANS_MEDIUM,
    GENISLIK,
    OPTIK_KALDIRMA,
    YUKSEKLIK,
)
from .fontlar import _font_yukle
from .tipografi import _metin_sar, _temizle_tipografi
from .tuval import _yerlesim
from .bilesenler import _slayt_cercevesi
from .fikir import _adim_numarasi, _blogu_sigdir, _fikir_blogu_ciz, _fikir_blogu_olc

log = logging.getLogger(__name__)

ADIM_IRI_GOVDE = 110     # karakter
ADIM_IRI_BASLIK = 34


def adim_iri_mi(maddeler: List[Dict[str, Any]]) -> bool:
    """Kümenin TÜM adımları kısaysa True."""
    adimlar = [m for m in (maddeler or []) if isinstance(m, dict)]
    return bool(adimlar) and all(
        len(str(m.get("aciklama") or "").strip()) <= ADIM_IRI_GOVDE
        and len(str(m.get("baslik") or "").strip()) <= ADIM_IRI_BASLIK
        for m in adimlar
    )


def _adim_olcusu(draw: ImageDraw.ImageDraw, baslik: str, govde: str, iri: bool, ek_alan: int = 0):
    """Bir adımın metin bloğu: (ölçü, numara yüksekliği, toplam blok yüksekliği)."""
    yer = _yerlesim()
    genislik = GENISLIK - (2 * yer["kenar"])
    n_yuk = 190 if iri else 150
    baslik_punto = 70 if YUKSEKLIK >= 1700 else 64
    govde_punto = 42 if YUKSEKLIK >= 1700 else 40
    if iri:
        baslik_punto, govde_punto = baslik_punto + 14, govde_punto + 10
    olcu = _fikir_blogu_olc(draw, "", baslik, govde, genislik, baslik_punto=baslik_punto, govde_punto=govde_punto)
    olcu = _blogu_sigdir(olcu, yer["alt"] - yer["ust"] - n_yuk - 26 - ek_alan)
    return olcu, n_yuk, n_yuk + 26 + olcu["h"] + ek_alan


def adim_blok_yuksekligi(maddeler: List[Dict[str, Any]], iri: bool) -> int:
    """Kümedeki en uzun adım bloğunun yüksekliği."""
    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    return max((_adim_olcusu(draw, str(m.get("baslik") or ""), str(m.get("aciklama") or ""), iri)[2]
                for m in maddeler if isinstance(m, dict)), default=0)


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
    iri: bool = False,
    hiza_yuksekligi: int = 0,
) -> Path:
    """Tek adım, tam sayfa."""
    canvas, draw, p = _slayt_cercevesi(zemin_adi, rozet, alt_metin, sayfa)

    yer = _yerlesim()
    kenar = yer["kenar"]
    genislik = GENISLIK - (2 * kenar)

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

    not_metni = _temizle_tipografi(str(onemli_not or "")).strip()
    ek_alan = 150 if not_metni else 0
    olcu, n_yuk, toplam = _adim_olcusu(draw, baslik, govde, iri, ek_alan)
    n_font = _font_yukle(FONT_FRAUNCES, n_yuk)
    no_gosterim = f"0{mevcut_no}"[-2:]
    hiza = max(toplam, hiza_yuksekligi)
    if YUKSEKLIK >= 1700:
        alan = yer["alt"] - yer["ust"]
        y = yer["ust"] + max(0, (alan - hiza) // 2 - OPTIK_KALDIRMA)
    else:
        y = max(yer["ust"], yer["taban"] - hiza)

    draw.text((kenar, y - int(30 * n_yuk / 150)), no_gosterim, font=n_font, fill=p["vurgu"])
    kf = _font_yukle(FONT_MONO_BOLD, 20)
    nw = draw.textbbox((0, 0), no_gosterim, font=n_font)[2]
    draw.text((kenar + nw + 22, y + int(46 * n_yuk / 150)), f"/ {str(toplam_adim_guvenli).zfill(2)} ADIM", font=kf, fill=p["silik"])

    son_y = _fikir_blogu_ciz(canvas, draw, olcu, kenar, y + n_yuk + 26, p, vurgu_cizgisi=None)

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
