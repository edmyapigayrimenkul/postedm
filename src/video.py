"""
video.py — EDM 9:16 Dikey MP4 Video Üretim Motoru
1080x1350 formatındaki slaytlardan Instagram Reels, YouTube Shorts ve TikTok için
1080x1920 çözünürlüğünde dikey video (MP4) üretir.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import List, Optional

import imageio
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from . import config

log = logging.getLogger(__name__)

HEDEF_W = 1080
HEDEF_H = 1920

FONT_MONO = config.yol_al("assets/fonts/IBMPlexMono-Regular.ttf")
FONT_FRAUNCES = config.yol_al("assets/fonts/Fraunces-Variable.ttf")
LOGO_PIN = config.yol_al("assets/logos/pin-sembol.png")


def _cercevele_9_16(kart_img: Image.Image) -> Image.Image:
    """1080x1350 slaytını 1080x1920 tuvale sinematik blur ve marka başlığı ile yerleştirir."""
    w, h = kart_img.size
    if (w, h) == (HEDEF_W, HEDEF_H):
        return kart_img.convert("RGB")

    tuval = Image.new("RGB", (HEDEF_W, HEDEF_H), (18, 19, 22))

    # 1. Arka plan blur
    oran = max(HEDEF_W / w, HEDEF_H / h)
    bg_w, bg_h = int(w * oran), int(h * oran)
    bg = kart_img.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
    sol = (bg_w - HEDEF_W) // 2
    ust = (bg_h - HEDEF_H) // 2
    bg_kirp = bg.crop((sol, ust, sol + HEDEF_W, ust + HEDEF_H))
    bg_blur = bg_kirp.filter(ImageFilter.GaussianBlur(radius=35))

    # Karartma perdesi
    karartma = Image.new("RGB", (HEDEF_W, HEDEF_H), (0, 0, 0))
    bg_son = Image.blend(bg_blur, karartma, 0.45)
    tuval.paste(bg_son, (0, 0))

    # 2. Ana Kartı Merkeze Koy (1080x1350)
    card_y = (HEDEF_H - h) // 2 # 285px
    tuval.paste(kart_img, (0, card_y))

    draw = ImageDraw.Draw(tuval)

    # 3. Üst Marka Başlığı (0 - 285px arası)
    try:
        font_mono = ImageFont.truetype(str(FONT_MONO), 24)
    except Exception:
        font_mono = ImageFont.load_default()

    draw.text((70, 180), "EDM YAPI & GAYRİMENKUL", font=font_mono, fill=(244, 244, 243))
    draw.line([(70, 220), (HEDEF_W - 70, 220)], fill=(240, 0, 13), width=2)

    # 4. Alt Marka İmzası (1635 - 1920px arası)
    draw.line([(70, 1700), (HEDEF_W - 70, 1700)], fill=(80, 80, 85), width=1)
    draw.text((70, 1725), "edmyapigayrimenkul.com · 0536 343 41 97", font=font_mono, fill=(180, 180, 185))

    return tuval


def slaytlardan_video_uret(
    slayt_yollari: List[Path | str],
    cikti_yolu: Optional[Path] = None,
    slayt_suresi_saniye: float = 3.5,
    fps: int = 24,
) -> Optional[Path]:
    """Slayt görsellerini alıp dikey 9:16 MP4 video üretir."""
    if not slayt_yollari:
        return None

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/video_{os.getpid()}.mp4")
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)

    kareler_per_slayt = int(slayt_suresi_saniye * fps)

    try:
        writer = imageio.get_writer(
            str(cikti_yolu),
            fps=fps,
            codec="libx264",
            quality=8,
            pixelformat="yuv420p",
        )

        for yol in slayt_yollari:
            p = Path(yol)
            if not p.exists():
                continue
            kart_img = Image.open(p).convert("RGB")
            tam_kare = _cercevele_9_16(kart_img)
            kare_np = np.array(tam_kare)

            for _ in range(kareler_per_slayt):
                writer.append_data(kare_np)

        writer.close()
        log.info("Dikey video başarıyla üretildi: %s", cikti_yolu)
        return cikti_yolu

    except Exception as e:
        log.error("Video üretimi hatası: %s", e)
        return None
