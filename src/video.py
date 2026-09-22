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


def _cercevele_9_16(kart_img: Image.Image, genislik: int = HEDEF_W, yukseklik: int = HEDEF_H) -> Image.Image:
    """1080x1350 slayt görselini 1080x1920 (9:16) formatına dönüştürür.

    Instabot standartı: Kartın arkasına sinematik Gaussian blur + koyu perde +
    yumuşak derinlik gölgesi uygulanır. Kart tam merkezde net ve güvenli alanda kalır;
    asla piksel uzatma çizgisi veya yapay renk yırtılması oluşmaz.
    """
    w, h = kart_img.size
    if (w, h) == (genislik, yukseklik):
        return kart_img.convert("RGB")

    card_y = max(0, (yukseklik - h) // 2)  # 285 px

    # Düz zeminli kart kontrolü (Kullanıcı kuralı: Tek renkli zeminlerde kesintisiz uzatma)
    kart_rgb = kart_img.convert("RGB")
    ust_satir = np.array(kart_rgb.crop((0, 0, w, 1)), dtype=np.float32)
    alt_satir = np.array(kart_rgb.crop((0, h - 1, w, h)), dtype=np.float32)
    if float(np.max(np.std(ust_satir, axis=1))) < 4.0 and float(np.max(np.std(alt_satir, axis=1))) < 4.0:
        tuval = Image.new("RGB", (genislik, yukseklik))
        ust_serit = kart_rgb.crop((0, 0, w, 1)).resize((genislik, card_y), Image.Resampling.NEAREST)
        tuval.paste(ust_serit, (0, 0))
        alt_kalan = yukseklik - (card_y + h)
        if alt_kalan > 0:
            alt_serit = kart_rgb.crop((0, h - 1, w, h)).resize((genislik, alt_kalan), Image.Resampling.NEAREST)
            tuval.paste(alt_serit, (0, card_y + h))
        tuval.paste(kart_rgb, (0, card_y))
        return tuval

    # 1. Arka plan: Görüntüyü tüm 1080x1920 alana orantılı büyütüp sinematik blur ve karartma uygula
    oran = max(genislik / w, yukseklik / h)
    bg_w, bg_h = int(w * oran), int(h * oran)
    bg = kart_img.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
    sol = (bg_w - genislik) // 2
    ust = (bg_h - yukseklik) // 2
    bg = bg.crop((sol, ust, sol + genislik, ust + yukseklik))
    bg = bg.filter(ImageFilter.GaussianBlur(35))

    # Koyu perde
    perde = Image.new("RGBA", (genislik, yukseklik), (10, 13, 19, 160))
    bg = Image.alpha_composite(bg.convert("RGBA"), perde)

    # 2. Ana 4:5 kartın arkasına yumuşak derinlik gölgesi
    golge = Image.new("RGBA", (genislik, yukseklik), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(golge)
    gdraw.rectangle([0, card_y - 8, genislik, card_y + h + 8], fill=(0, 0, 0, 180))
    golge = golge.filter(ImageFilter.GaussianBlur(25))
    bg = Image.alpha_composite(bg, golge)

    # 3. Ana 4:5 kartı merkeze yerleştir
    bg.paste(kart_img.convert("RGBA"), (0, card_y))

    return bg.convert("RGB")


def _foto_ac_veya_indir(kaynak: Path | str, deneme_adedi: int = 3) -> Optional[Image.Image]:
    """Görseli yerel dosyadan veya önbellekten açar; yoksa uzak URL'den 3 denemeli olarak indirir."""
    import time
    s = str(kaynak).strip()

    # 1. Önce URL ise upload önbelleğinde yerel karşılığı var mı bak
    yerel = upload_image.yerel_karsiligi(s)
    if yerel and yerel.exists() and yerel.is_file():
        try:
            img = Image.open(yerel)
            return ImageOps.exif_transpose(img).convert("RGB")
        except Exception as e:
            log.warning("Önbellekteki yerel görsel açılamadı (%s): %s", yerel, e)

    # 2. Uzak URL ise indir (Önce hızlı curl, sonra requests fallback)
    if s.startswith("http://") or s.startswith("https://"):
        try:
            c_res = subprocess.run(["curl", "-s", "-f", "-L", "-m", "15", s], capture_output=True)
            if c_res.returncode == 0 and len(c_res.stdout) > 500:
                img = Image.open(io.BytesIO(c_res.stdout))
                return ImageOps.exif_transpose(img).convert("RGB")
        except Exception as ce:
            log.debug("Curl indirme atlandı/başarısız: %s", ce)

        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36", "Connection": "close"}
        for deneme in range(1, deneme_adedi + 1):
            try:
                resp = requests.get(s, headers=headers, timeout=20)
                if resp.status_code == 200 and len(resp.content) > 500:
                    img = Image.open(io.BytesIO(resp.content))
                    return ImageOps.exif_transpose(img).convert("RGB")
            except Exception as e:
                log.warning("Video görseli indirme hatası (%s, deneme %d/%d): %s", s, deneme, deneme_adedi, e)
            if deneme < deneme_adedi:
                time.sleep(1.5 * deneme)
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
def slayt_surelerini_hesapla(
    toplam_slayt: int,
    haber: Optional[dict] = None,
    varsayilan_kapak_suresi: float = 4.2,
) -> List[float]:
    """
    Her slayt için içerik ve kelime yoğunluğuna göre akıllı dinamik süre (saniye) listesi döner.
    (Instabot commit 94bf292 referansı ile EDM formatına uyarlanmıştır)

    * 1. Slayt (Kapak / Kanca): 4.2 saniye (Görseli, kancayı ve 70px dev manşeti algılamak için ideal).
    * 2. ve Sonraki Slaytlar (Detay):
      - Kelime sayısına göre: 4.8s ila 6.2s arasında otomatik ölçeklenir.
      - Ortalama Türkçe sessiz okuma hızına (saniyede ~3-3.5 kelime) göre insani okuma payı bırakılır.
      - Toplam video süresi 15 - 20 saniye bandında tutulur (Reels/Shorts zirve retention süresi).
    """
    if toplam_slayt <= 0:
        return []

    sureler = [varsayilan_kapak_suresi]
    if toplam_slayt == 1:
        return sureler

    detay_maddeleri = []
    if haber and isinstance(haber, dict):
        detay_maddeleri = haber.get("detay_maddeleri") or []
        if not detay_maddeleri and haber.get("detay_metni"):
            try:
                import json
                d = json.loads(haber["detay_metni"]) if isinstance(haber["detay_metni"], str) else haber["detay_metni"]
                if isinstance(d, dict):
                    detay_maddeleri = d.get("detay_maddeleri") or []
            except Exception:
                pass

    kalan_slayt_sayisi = toplam_slayt - 1
    for idx in range(kalan_slayt_sayisi):
        kelime_sayisi = 40  # Varsayılan detay kelime sayısı
        if detay_maddeleri and idx < len(detay_maddeleri):
            m = detay_maddeleri[idx]
            txt = f"{m.get('etiket', '')} {m.get('metin', '')}"
            kelime_sayisi = len(txt.split())

        # Taban 4.5 sn + her 20 kelime için +0.5 sn ek süre (Min 4.8 sn, Maks 6.2 sn)
        hesaplanan = 4.5 + min(1.7, max(0.3, (kelime_sayisi / 20.0) * 0.5))
        sureler.append(round(hesaplanan, 2))

    return sureler


def slaytlardan_video_uret(
    slayt_yollari: List[Path | str],
    cikti_yolu: Optional[Path] = None,
    slayt_suresi_saniye: float = 3.5,
    gecis_suresi_saniye: float = 0.5,
    hedef_sure: Optional[float] = None,
    fps: int = 30,
    slayt_sureleri: Optional[List[float]] = None,
    haber: Optional[dict] = None,
) -> Optional[Path]:
    """
    Slayt görsellerini alıp akıcı Cosine S-Curve crossfade geçişleri ve
    Stereo AAC ses izi ile 1080x1920 MP4 video üretir.

    * hedef_sure verilirse slayt süreleri bu süreye (örn: seslendirme süresi) göre dinamik ayarlanır.
    * hedef_sure yoksa slayt_surelerini_hesapla ile içerik yoğunluğuna göre dinamik insani süreler uygulanır.
    * İlk slaytta (Kapak) kanca etkisi ve okunabilirlik için 4.2 saniye bekleme.
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

    log.info("Dikey video üretimi başlatılıyor: %d slayt -> %s (fps=%d, hedef_sure=%s)", len(slayt_yollari), cikti_yolu, fps, hedef_sure)

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

    toplam_slayt = len(kareler_ham)

    # Eğer hedef süre (örn: ElevenLabs ses süresi) verilmişse slayt süresini dinamik hesapla
    if hedef_sure and hedef_sure > 3.0:
        dinamik_sure = max(2.5, (hedef_sure - 0.5) / max(1, toplam_slayt))
        slayt_suresi_saniye = round(dinamik_sure, 2)
        log.info("Ses süresine göre dinamik slayt süresi belirlendi: %.2f sn (Toplam ses: %.1f sn)", slayt_suresi_saniye, hedef_sure)
        hesaplanan_sureler = [slayt_suresi_saniye] * toplam_slayt
    elif slayt_sureleri and len(slayt_sureleri) == toplam_slayt:
        hesaplanan_sureler = slayt_sureleri
    else:
        hesaplanan_sureler = slayt_surelerini_hesapla(toplam_slayt, haber=haber)
        log.info("İçerik yoğunluğuna göre dinamik süreler belirlendi: %s (Toplam: %.1f sn)", hesaplanan_sureler, sum(hesaplanan_sureler))

    gecis_kare_sayisi = max(1, int(fps * gecis_suresi_saniye)) if toplam_slayt > 1 else 0
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

                # İçerik ve kelime yoğunluğuna göre dinamik hesaplanan kare sayısı
                bu_slayt_suresi = hesaplanan_sureler[idx] if idx < len(hesaplanan_sureler) else slayt_suresi_saniye
                bu_slayt_toplam_kare = max(1, int(fps * bu_slayt_suresi))
                bu_slayt_sabit_kare = max(1, bu_slayt_toplam_kare - gecis_kare_sayisi)

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
    hedef_sure: Optional[float] = None,
    fps: int = 30,
    slayt_sureleri: Optional[List[float]] = None,
    haber: Optional[dict] = None,
) -> Optional[Path]:
    """slaytlardan_video_uret için uyumluluk fonksiyonu (instabot mimarisi)."""
    return slaytlardan_video_uret(
        slayt_yollari=slayt_yollari,
        cikti_yolu=cikti_yolu,
        slayt_suresi_saniye=slayt_suresi,
        gecis_suresi_saniye=gecis_suresi,
        hedef_sure=hedef_sure,
        fps=fps,
        slayt_sureleri=slayt_sureleri,
        haber=haber,
    )

