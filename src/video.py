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

    Kullanıcı kuralı: Alt ve üst kısımlarda yapay geçiş, blur veya degrade
    hissiyatı olmamalıdır. Kartın üst rengi en tepeye (y=0), alt rengi ise
    en alta (y=1920) kesintisiz ve aynı tonda devam eder.
    """
    w, h = kart_img.size
    if (w, h) == (HEDEF_W, HEDEF_H):
        return kart_img.convert("RGB")

    kart_rgb = kart_img.convert("RGB")
    card_y = max(0, (HEDEF_H - h) // 2)

    tuval = Image.new("RGB", (HEDEF_W, HEDEF_H))

    # 1. Üst kısım: Kartın en üst satırını yukarıya doğru kesintisiz uzat (0 .. card_y)
    ust_serit = kart_rgb.crop((0, 0, w, 1)).resize((HEDEF_W, card_y), Image.Resampling.NEAREST)
    tuval.paste(ust_serit, (0, 0))

    # 2. Alt kısım: Kartın en alt satırını aşağıya doğru kesintisiz uzat (card_y + h .. 1920)
    alt_y = card_y + h
    alt_kalan = HEDEF_H - alt_y
    if alt_kalan > 0:
        alt_serit = kart_rgb.crop((0, h - 1, w, h)).resize((HEDEF_W, alt_kalan), Image.Resampling.NEAREST)
        tuval.paste(alt_serit, (0, alt_y))

    # 3. 4:5 Görseli Merkeze Sıfır Geçiş Maskesi ile Kesintisiz Yerleştir
    tuval.paste(kart_rgb, (0, card_y))

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

