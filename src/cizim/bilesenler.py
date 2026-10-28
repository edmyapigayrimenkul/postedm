"""
src/cizim/bilesenler.py — Rozetler, logo yerleştirme, filigran ve slayt çerçevesi.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import fontlar, ikonlar, sabitler, tipografi
from .tuval import _rozet_kirp, _yerlesim

log = logging.getLogger(__name__)

# Geriye dönük uyumluluk için dışa aktarım
_vektor_ikon_uret = ikonlar._vektor_ikon_uret
_edm_pin_al = ikonlar._edm_pin_al


def kanal_ikonlari_bas(
    gorsel: Image.Image,
    ayarlar: Any = None,
    y_merkez: int = 1800,
    renk: Tuple[int, int, int] = (150, 160, 180),
) -> Image.Image:
    """Slaytın alt bilgisine sosyal kanal ikonlarını veya marka metnini basar."""
    return gorsel


def _logo_yerlestir(
    canvas: Image.Image,
    beyaz: bool = True,
    x: Optional[int] = None,
    y: int = 55,
    lw: int = 285,
    golge: bool = True,
    kirmizi_zemin: bool = False,
) -> None:
    """EDM logosunu tuvale difüzyon gölgesiyle yerleştirir."""
    if kirmizi_zemin and sabitler.LOGO_YATAY_BEYAZ.exists():
        logo_yolu = sabitler.LOGO_YATAY_BEYAZ
    else:
        logo_yolu = sabitler.LOGO_YATAY_ACIK if beyaz else sabitler.LOGO_YATAY

    if logo_yolu.exists():
        try:
            logo = Image.open(logo_yolu).convert("RGBA")
            lh = int(logo.height * (lw / logo.width))
            logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)
            if x is None:
                x = sabitler.GENISLIK - 70 - lw
            c_rgba = canvas.convert("RGBA")

            if golge:
                pad = 22
                s_w, s_h = lw + (2 * pad), lh + (2 * pad)
                golge_katman = Image.new("RGBA", (s_w, s_h), (0, 0, 0, 0))
                alfa = logo.split()[3]
                kara_logo = Image.new("RGBA", (lw, lh), (0, 0, 0, 200 if kirmizi_zemin else 170))
                kara_logo.putalpha(alfa)
                golge_katman.paste(kara_logo, (pad, pad + 3), kara_logo)
                golge_katman = golge_katman.filter(ImageFilter.GaussianBlur(7))
                c_rgba.paste(golge_katman, (x - pad, y - pad), golge_katman)

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
    """Metin arkasına Gaussian Blur difüzyon gölgesi basar."""
    golge = Image.new("RGBA", (sabitler.GENISLIK, sabitler.YUKSEKLIK), (0, 0, 0, 0))
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


def _filigran_uygula(canvas: Image.Image, acik_zemin: bool = False) -> Image.Image:
    """Arka plana silik marka filigranı ekler."""
    try:
        if not sabitler.LOGO_AMBLEM.exists() or sabitler.LOGO_AMBLEM.stat().st_size == 0:
            return canvas
        amblem = Image.open(sabitler.LOGO_AMBLEM).convert("RGBA")
        w_size = max(200, min(500, int(canvas.width * 0.46)))
        h_size = int(w_size * amblem.height / max(1, amblem.width))
        amblem = amblem.resize((w_size, h_size), Image.Resampling.LANCZOS)

        alfa_oran = 0.035 if acik_zemin else 0.045
        r, g, b, a = amblem.split()
        base = Image.new("RGB", amblem.size, (40, 45, 55) if acik_zemin else (255, 255, 255))
        a_faded = a.point(lambda p: int(p * alfa_oran))
        base.putalpha(a_faded)

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
    bg_color=sabitler.RENK_KIRMIZI,
    fg_color=sabitler.RENK_BEYAZ,
    border_color=None,
    font_boyut: int = 19,
    max_w: Optional[int] = None,
) -> int:
    """Teknik mono rozet çizer ve genişliği döner."""
    if metin is None:
        return 0
    metin = tipografi._temizle_tipografi(str(metin)).strip()
    if not metin:
        return 0

    if max_w is None:
        max_w = max(100, sabitler.GENISLIK - x - 70)

    pad_x, pad_y = 20, 8
    cur_boyut = font_boyut
    font = fontlar._font_yukle(sabitler.FONT_MONO_BOLD, cur_boyut)
    bbox = draw.textbbox((0, 0), metin, font=font)
    w = bbox[2] - bbox[0]

    while (w + (pad_x * 2) > max_w) and cur_boyut > 11:
        cur_boyut -= 2
        font = fontlar._font_yukle(sabitler.FONT_MONO_BOLD, cur_boyut)
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

    draw.rounded_rectangle([(x, y), (x + bw, y + bh)], radius=6, fill=bg_color, outline=border_color)
    tx = x + (bw - w) / 2 - bbox[0]
    ty = y + (bh - h) / 2 - bbox[1]
    draw.text((tx, ty), metin, font=font, fill=fg_color)
    return bw


def _arti_isareti_ciz(draw: ImageDraw.ImageDraw, x: int, y: int, renk=sabitler.RENK_KURSUN, boyut=12):
    """Rölöve köşe artı işareti."""
    r = boyut // 2
    draw.line([(x - r, y), (x + r, y)], fill=renk, width=1)
    draw.line([(x, y - r), (x, y + r)], fill=renk, width=1)


def _slayt_cercevesi(
    zemin_adi: str,
    rozet: str,
    alt_metin: str,
    sayfa: str,
) -> Tuple[Image.Image, ImageDraw.ImageDraw, Dict[str, Any]]:
    """Tüm iç slaytların ortak çerçevesini çizer."""
    yer = _yerlesim()
    kenar = yer["kenar"]
    p = sabitler.ZEMINLER.get(zemin_adi, sabitler.ZEMINLER["murekkep"])
    canvas = Image.new("RGB", (sabitler.GENISLIK, sabitler.YUKSEKLIK), p["zemin"])
    canvas = _filigran_uygula(canvas, acik_zemin=(zemin_adi == "kagit"))
    draw = ImageDraw.Draw(canvas)

    ku = yer["kronik_ust"]
    _rozet_ciz(draw, kenar, ku, _rozet_kirp(rozet, 44),
               bg_color=p["rozet_bg"], fg_color=p["rozet_fg"], font_boyut=20)
    _logo_yerlestir(
        canvas,
        beyaz=p["logo_beyaz"],
        y=ku - 5,
        lw=285,
        golge=True,
        kirmizi_zemin=(zemin_adi == "kirmizi"),
    )

    alt_y = yer["alt_bar"]
    draw.line([(kenar, alt_y), (sabitler.GENISLIK - kenar, alt_y)], fill=p["cizgi"], width=1)
    draw.text((kenar, alt_y + 26), tipografi._temizle_tipografi(alt_metin),
              font=fontlar._font_yukle(sabitler.FONT_MONO, 19), fill=p["silik"])
    if sayfa and str(sayfa).strip():
        sf = fontlar._font_yukle(sabitler.FONT_MONO_BOLD, 19)
        sw = draw.textbbox((0, 0), sayfa, font=sf)[2]
        draw.text((sabitler.GENISLIK - kenar - sw, alt_y + 26), sayfa, font=sf, fill=p["vurgu"])

    return canvas, draw, p
