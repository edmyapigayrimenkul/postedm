"""
video.py — EDM 9:16 Dikey MP4 Video Üretim Motoru (Instabot / Reels Standardı)
1080x1350 formatındaki slaytlardan Instagram Reels, YouTube Shorts ve TikTok için
1080x1920 çözünürlüğünde, sinematik geçişli ve stereo AAC ses izli dikey video üretir.
"""

from __future__ import annotations

import io
import logging
import math
import os
import subprocess
from pathlib import Path
from typing import List, Optional

import imageio
import imageio_ffmpeg
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from . import config, upload_image

log = logging.getLogger(__name__)

HEDEF_W = 1080
HEDEF_H = 1920

FONT_MONO = config.yol_al("assets/fonts/IBMPlexMono-Regular.ttf")
FONT_FRAUNCES = config.yol_al("assets/fonts/Fraunces-Variable.ttf")
LOGO_PIN = config.yol_al("assets/logos/pin-sembol.png")


def _cercevele_9_16(kart_img: Image.Image) -> Image.Image:
    """1080x1350 slayt görselini 1080x1920 (9:16) formatına dönüştürür.

    Kart görünümü ve yapay kenarlıklar yerine, dikeyde 140px yumuşak
    degrade geçiş (soft vertical vignette fade) ile sinematik arka plana eritir.
    """
    w, h = kart_img.size
    if (w, h) == (HEDEF_W, HEDEF_H):
        return kart_img.convert("RGB")

    kart_rgb = kart_img.convert("RGB")

    # 1. Arka plan: Orantılı büyütüp sinematik blur ve karartma uygula
    oran = max(HEDEF_W / max(1, w), HEDEF_H / max(1, h))
    bg_w, bg_h = max(HEDEF_W, int(w * oran)), max(HEDEF_H, int(h * oran))
    bg = kart_rgb.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
    sol = max(0, (bg_w - HEDEF_W) // 2)
    ust = max(0, (bg_h - HEDEF_H) // 2)
    bg_kirp = bg.crop((sol, ust, sol + HEDEF_W, ust + HEDEF_H))
    bg_blur = bg_kirp.filter(ImageFilter.GaussianBlur(radius=45))

    # Koyu sinematik perde
    karartma = Image.new("RGB", (HEDEF_W, HEDEF_H), (10, 12, 16))
    tuval = Image.blend(bg_blur, karartma, 0.48)

    # 2. 4:5 Görseli Merkeze Yerleştir — Soft Degrade Fade ile
    card_y = max(0, (HEDEF_H - h) // 2)

    # Alfa Maskesi: Dikeyde ortası %100 opak, üst ve alt kenarlar yumuşak degrade
    mask = Image.new("L", (w, h), 255)
    m_draw = ImageDraw.Draw(mask)
    fade_h = min(140, max(10, h // 4))
    for i in range(fade_h):
        alpha = int(255 * ((i / max(1, fade_h)) ** 1.3))
        m_draw.line([(0, i), (w, i)], fill=alpha)
        m_draw.line([(0, h - 1 - i), (w, h - 1 - i)], fill=alpha)

    # Yumuşak geçişle tuvale yapıştır
    tuval.paste(kart_rgb, (0, card_y), mask)

    return tuval


def _foto_ac_veya_indir(kaynak: Path | str, deneme_adedi: int = 3) -> Optional[Image.Image]:
    """Görseli yerel dosyadan veya önbellekten açar; yoksa uzak URL'den 3 denemeli olarak indirir."""
    import time
    s = str(kaynak)

    # 1. Önce URL ise upload önbelleğinde yerel karşılığı var mı bak
    yerel = upload_image.yerel_karsiligi(s)
    if yerel and yerel.exists() and yerel.is_file():
        try:
            img = Image.open(yerel)
            return ImageOps.exif_transpose(img).convert("RGB")
        except Exception as e:
            log.warning("Önbellekteki yerel görsel açılamadı (%s): %s", yerel, e)

    # 2. Uzak URL ise indir
    if s.startswith("http://") or s.startswith("https://"):
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        for deneme in range(1, deneme_adedi + 1):
            try:
                resp = requests.get(s, headers=headers, timeout=25)
                if resp.status_code == 200:
                    img = Image.open(io.BytesIO(resp.content))
                    return ImageOps.exif_transpose(img).convert("RGB")
            except Exception as e:
                log.warning("Video görseli indirme hatası (%s, deneme %d/%d): %s", s, deneme, deneme_adedi, e)
            if deneme < deneme_adedi:
                time.sleep(2 * deneme)
        return None

    # 3. Yerel dosya yolu ise doğrudan aç
    p = Path(kaynak)
    if p.exists() and p.is_file():
        try:
            img = Image.open(p)
            return ImageOps.exif_transpose(img).convert("RGB")
        except Exception as e:
            log.warning("Yerel görsel açılamadı (%s): %s", p, e)
    return None


def slaytlardan_video_uret(
    slayt_yollari: List[Path | str],
    cikti_yolu: Optional[Path] = None,
    slayt_suresi_saniye: float = 3.5,
    gecis_suresi_saniye: float = 0.5,
    fps: int = 30,
) -> Optional[Path]:
    """
    Slayt görsellerini alıp akıcı Cosine S-Curve crossfade geçişleri ve
    Stereo AAC ses izi ile 1080x1920 MP4 video üretir.

    * İlk slaytta (Kapak) kanca etkisi ve okunabilirlik için +1.0 saniye bekleme.
    * S-Curve yumuşak kararma geçişleri (titremesiz).
    * TikTok, Reels ve Shorts için standart stereo AAC ses kanalı eklenir.
    * Faststart moov atomu ile web ve sosyal medyada anında yüklenme.
    """
    if not slayt_yollari:
        return None

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/video_{os.getpid()}.mp4")
    else:
        cikti_yolu = Path(cikti_yolu)
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)

    log.info("Dikey video üretimi başlatılıyor: %d slayt -> %s (fps=%d)", len(slayt_yollari), cikti_yolu, fps)

    # 1. Tüm görselleri 1080x1920 formatına getir (Yerel dosya veya URL)
    kareler_ham: List[Image.Image] = []
    for yol in slayt_yollari:
        img = _foto_ac_veya_indir(yol)
        if img:
            kareler_ham.append(_cercevele_9_16(img))
        else:
            log.warning("Slayt görseli temin edilemedi: %s", yol)

    if not kareler_ham:
        log.error("Hiçbir slayt görseli yüklenemedi!")
        return None

    # Kare sayıları hesabı
    toplam_kare_slayt = max(1, int(fps * slayt_suresi_saniye))
    gecis_kare_sayisi = max(1, int(fps * gecis_suresi_saniye)) if len(kareler_ham) > 1 else 0
    sabit_kare_sayisi = max(1, toplam_kare_slayt - gecis_kare_sayisi)

    np_kareler = [np.array(img, dtype=np.float32) for img in kareler_ham]

    raw_video_yolu = cikti_yolu.with_name(f"{cikti_yolu.stem}_raw.mp4")

    try:
        writer = imageio.get_writer(
            str(raw_video_yolu),
            fps=fps,
            codec="libx264",
            pixelformat="yuv420p",
            macro_block_size=1,
            quality=9,
            ffmpeg_params=[
                "-crf", "18",
                "-preset", "fast",
                "-g", "60",
                "-keyint_min", "30",
                "-sc_threshold", "0",
                "-movflags", "+faststart",
            ],
        )

        toplam_slayt = len(np_kareler)
        if toplam_slayt == 1:
            # Tek sayfalık görsel için YouTube Shorts ve Facebook Reels'e uygun 6.5 saniyelik sinematik yavaş zoom
            tek_img = kareler_ham[0]
            w_img, h_img = tek_img.size
            toplam_kare_tek = int(fps * 6.5)
            for k in range(toplam_kare_tek):
                scale = 1.0 + 0.035 * (k / float(toplam_kare_tek))
                new_w = int(w_img * scale)
                new_h = int(h_img * scale)
                img_zoomed = tek_img.resize((new_w, new_h), Image.Resampling.BILINEAR)
                sol = (new_w - w_img) // 2
                ust = (new_h - h_img) // 2
                img_kirp = img_zoomed.crop((sol, ust, sol + w_img, ust + h_img))
                writer.append_data(np.array(img_kirp, dtype=np.uint8))
        else:
            for idx in range(toplam_slayt):
                arr_simdiki = np_kareler[idx]
                arr_sonraki = np_kareler[(idx + 1) % toplam_slayt] if toplam_slayt > 1 else None

                # Kapak slaytında (idx == 0) başlığın rahat okunması için +1.0 saniye kanca beklemesi
                bu_slayt_sabit_kare = sabit_kare_sayisi + (int(fps * 1.0) if idx == 0 else 0)

                # A. Sabit Görsel Aşaması
                arr_uint8 = np.clip(arr_simdiki, 0, 255).astype(np.uint8)
                for _ in range(bu_slayt_sabit_kare):
                    writer.append_data(arr_uint8)

                # B. Cosine S-Curve Crossfade Geçiş Aşaması (Yumuşak akıcı geçiş)
                if gecis_kare_sayisi > 0 and arr_sonraki is not None and idx < toplam_slayt - 1:
                    for k in range(gecis_kare_sayisi):
                        t = (k + 1) / float(gecis_kare_sayisi)
                        alpha = 0.5 * (1.0 - math.cos(math.pi * t))
                        gecis_arr = (1.0 - alpha) * arr_simdiki + alpha * arr_sonraki
                        writer.append_data(np.clip(gecis_arr, 0, 255).astype(np.uint8))


        writer.close()

        # 2. Stereo AAC Ses İzi Ekle (Sosyal medya algoritmalarının videoyu bekletmemesi için)
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        komut = [
            ffmpeg_exe, "-y",
            "-i", str(raw_video_yolu),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            "-movflags", "+faststart",
            str(cikti_yolu),
        ]
        res = subprocess.run(komut, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        raw_video_yolu.unlink(missing_ok=True)

        log.info("Dikey video başarıyla üretildi: %s (boyut: %.2f MB)", cikti_yolu, cikti_yolu.stat().st_size / (1024 * 1024))
        return cikti_yolu

    except Exception as e:
        log.error("Video üretimi hatası: %s", e)
        if raw_video_yolu.exists() and not cikti_yolu.exists():
            raw_video_yolu.rename(cikti_yolu)
            return cikti_yolu
        return None


def slaytlardan_reels_uret(
    slayt_yollari: List[Path | str],
    cikti_yolu: Optional[Path] = None,
    slayt_suresi: float = 3.5,
    gecis_suresi: float = 0.5,
    fps: int = 30,
) -> Optional[Path]:
    """slaytlardan_video_uret için uyumluluk fonksiyonu (instabot mimarisi)."""
    return slaytlardan_video_uret(
        slayt_yollari=slayt_yollari,
        cikti_yolu=cikti_yolu,
        slayt_suresi_saniye=slayt_suresi,
        gecis_suresi_saniye=gecis_suresi,
        fps=fps,
    )

