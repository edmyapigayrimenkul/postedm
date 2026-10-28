"""
src/cizim/ikonlar.py — Vektör ikonlar ve EDM pin sembolü.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from PIL import Image, ImageDraw

from . import sabitler

log = logging.getLogger(__name__)


def _vektor_ikon_uret(
    ad: str,
    boyut: int,
    renk: Tuple[int, int, int] = (255, 255, 255),
    bg_renk: Optional[Tuple[int, int, int]] = None,
) -> Image.Image:
    """Matematiksel antialiased vektör ikon üretir."""
    canvas_size = 256
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rgba = (*renk, 255)

    if bg_renk is not None:
        d.ellipse([(0, 0), (canvas_size - 1, canvas_size - 1)], fill=(*bg_renk, 255))

    if ad == "bookmark":
        x0, y0, x1, y1 = 52, 24, 204, 232
        d.polygon([(x0, y0), (x1, y0), (x1, y1), (128, y1 - 56), (x0, y1)], fill=rgba)
    elif ad == "phone":
        d.rounded_rectangle([(64, 24), (192, 232)], radius=32, outline=rgba, width=18)
        d.line([(106, 52), (150, 52)], fill=rgba, width=12)
        d.line([(110, 208), (146, 208)], fill=rgba, width=12)
    elif ad == "mail":
        d.rounded_rectangle([(28, 52), (228, 204)], radius=22, outline=rgba, width=18)
        d.line([(38, 60), (128, 140)], fill=rgba, width=18)
        d.line([(128, 140), (218, 60)], fill=rgba, width=18)
    elif ad == "web":
        d.ellipse([(28, 28), (228, 228)], outline=rgba, width=18)
        d.line([(28, 128), (228, 128)], fill=rgba, width=18)
        d.ellipse([(80, 28), (176, 228)], outline=rgba, width=18)
        d.line([(128, 28), (128, 228)], fill=rgba, width=18)
    elif ad == "pin":
        d.ellipse([(64, 36), (192, 164)], fill=rgba)
        d.polygon([(64, 112), (192, 112), (128, 236)], fill=rgba)
        delik = (18, 20, 26, 255) if bg_renk is None else (*bg_renk, 255)
        d.ellipse([(102, 74), (154, 126)], fill=delik)
    elif ad == "share":
        d.line([(68, 188), (188, 68)], fill=rgba, width=18)
        d.line([(116, 68), (188, 68), (188, 140)], fill=rgba, width=18)
    elif ad == "check":
        d.line([(48, 128), (108, 188), (208, 68)], fill=rgba, width=22)
    elif ad == "comment":
        d.rounded_rectangle([(28, 36), (228, 184)], radius=40, fill=rgba)
        d.polygon([(64, 176), (36, 234), (112, 184)], fill=rgba)
        for cx in [84, 128, 172]:
            d.ellipse([(cx - 11, 99), (cx + 11, 121)], fill=(255, 255, 255, 255))
    elif ad == "follow":
        d.ellipse([(70, 24), (150, 104)], fill=rgba)
        d.chord([(36, 124), (184, 236)], start=180, end=0, fill=rgba)
        d.rectangle([(192, 62), (200, 90)], fill=rgba)
        d.rectangle([(182, 72), (210, 80)], fill=rgba)

    return img.resize((boyut, boyut), Image.Resampling.LANCZOS)


def _edm_pin_al(boyut: int = 34) -> Image.Image:
    """EDM'in resmi kırmızı pin sembolü."""
    if sabitler.LOGO_PIN.exists():
        try:
            pin = Image.open(sabitler.LOGO_PIN).convert("RGBA")
            h = boyut
            w = int(pin.width * (h / pin.height))
            return pin.resize((w, h), Image.Resampling.LANCZOS)
        except Exception as e:
            log.warning("pin sembolü yüklenemedi: %s", e)
    return _vektor_ikon_uret("pin", boyut, sabitler.RENK_KIRMIZI_CANLI)
