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

LOGO_PIN = config.yol_al("assets/logos/pin-sembol.png")


def _cercevele_9_16(kart_img: Image.Image, genislik: int = HEDEF_W, yukseklik: int = HEDEF_H) -> Image.Image:
    """1080x1350 slayt görselini 1080x1920 (9:16) formatına dönüştürür.

    Instabot standartı:
    - Düz/yekpare zeminli kartlarda (Sözlük, Nedir Doğrusu, Vaka vb.) üst kenar medyan rengiyle y=0'a,
      alt kenar medyan rengiyle y=1920'ye kadar pürüzsüz uzatılır; asla 1px sündürme çizgisi veya yapay blur oluşmaz.
    - Fotoğraflı kartlarda arkaya derin difüzyon blur (GaussianBlur 75) + %86 koyu EDM mürekkep perdesi
      uygulanır. Kartın üzerindeki kırmızı rozet ve logolar asla arkada hayalet leke olarak görünmez.
    - Fotoğrafın üst kenarı yumuşak alfa geçişiyle (feathering) zemine dikişsiz kaynaşır.
    """
    w, h = kart_img.size
    if (w, h) == (genislik, yukseklik):
        return kart_img.convert("RGB")

    card_y = max(0, (yukseklik - h) // 2)  # 285 px

    kart_rgb = kart_img.convert("RGB")
    ust_satir = np.array(kart_rgb.crop((0, 0, w, 1)), dtype=np.float32)
    alt_satir = np.array(kart_rgb.crop((0, h - 1, w, h)), dtype=np.float32)
    ust_std = float(np.max(np.std(ust_satir, axis=1)))
    alt_std = float(np.max(np.std(alt_satir, axis=1)))

    # A. Tamamen düz/yekpare zeminli kart kontrolü (Kullanıcı Kuralı)
    if ust_std < 4.0 and alt_std < 4.0:
        ust_renk = tuple(int(round(c)) for c in np.mean(ust_satir[0], axis=0))
        alt_renk = tuple(int(round(c)) for c in np.mean(alt_satir[0], axis=0))
        tuval = Image.new("RGB", (genislik, yukseklik), ust_renk)
        draw = ImageDraw.Draw(tuval)
        draw.rectangle([0, card_y + h, genislik, yukseklik], fill=alt_renk)
        tuval.paste(kart_rgb, (0, card_y))
        return tuval

    # B. Fotoğraflı veya hibrit zemin: Sinematik derin difüzyon + kurumsal perde
    oran = max(genislik / w, yukseklik / h)
    bg_w, bg_h = int(w * oran), int(h * oran)
    bg = kart_rgb.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
    sol = (bg_w - genislik) // 2
    ust = (bg_h - yukseklik) // 2
    bg = bg.crop((sol, ust, sol + genislik, ust + yukseklik))
    bg = bg.filter(ImageFilter.GaussianBlur(35))

    # Yumuşak kurumsal perde (fotoğrafın estetiğini boğmadan kontrast sağlar)
    perde = Image.new("RGBA", (genislik, yukseklik), (15, 18, 24, 130))
    bg = Image.alpha_composite(bg.convert("RGBA"), perde)

    # Alt kenar düz renk ise (örn: Dailybrief haber kapaklarındaki siyah alt bant), aşağıya yekpare uzat
    if alt_std < 4.0:
        alt_renk = tuple(int(round(c)) for c in np.mean(alt_satir[0], axis=0))
        bdraw = ImageDraw.Draw(bg)
        bdraw.rectangle([0, card_y + h, genislik, yukseklik], fill=alt_renk + (255,))

    # Üst kenar düz renk ise yukarıya yekpare uzat
    if ust_std < 4.0:
        ust_renk = tuple(int(round(c)) for c in np.mean(ust_satir[0], axis=0))
        udraw = ImageDraw.Draw(bg)
        udraw.rectangle([0, 0, genislik, card_y], fill=ust_renk + (255,))

    # Kartı yerleştirmeden önce üst kenara yumuşak geçiş maskesi
    kart_rgba = kart_rgb.convert("RGBA")
    if ust_std >= 4.0:
        mask = Image.new("L", (w, h), 255)
        mdraw = ImageDraw.Draw(mask)
        fade_len = 20
        for i in range(fade_len):
            alpha = int(255 * (i / float(fade_len)))
            mdraw.line([(0, i), (w, i)], fill=alpha)
        kart_rgba.putalpha(mask)

    bg.paste(kart_rgba, (0, card_y), kart_rgba)
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
# Kullanıcı kararı 2026-09-29: Detay slaytları çok uzun bekliyordu; Reels ve Shorts
# temposuna uygun akıcı, dinamik süreler (3.2 - 5.5 sn).
OKUMA_HIZI_KELIME_SN = 5.0            # telefonda hızlı okuma
DETAY_ASGARI_SN, DETAY_AZAMI_SN = 3.2, 5.5
GECIS_SN = 0.5
_SLAYT_METNI = ("detay_maddeleri", "uzman_notu", "detay_yazisi", "neden_onemli", "sana_etkisi", "sirada_ne_var", "alinti", "cikarilacak_ders", "stratejist_notu", "olay_detay",
                "yargitay_hukmu", "puf_maddeleri", "maddeler", "adimlar", "altin_kural", "tavsiye", "tavsiye_metin")
_SAYILMAYAN = ("renk", "no", "tip", "ikon", "etiket_rengi")


def _detay_kelime_sayisi(veri: Optional[dict]) -> int:
    """Kapak DIŞINDAKİ slaytlarda yazan metnin kelime sayısı (kapak ve caption alanları sayılmaz)."""
    if not isinstance(veri, dict):
        return 0
    if isinstance(veri.get("detay_metni"), str):
        try:
            import json
            ic = json.loads(veri["detay_metni"])
            if isinstance(ic, dict):
                veri = {**ic, **{k: v for k, v in veri.items() if k != "detay_metni"}}
        except ValueError:
            pass
    toplam = 0

    def say(d) -> None:
        nonlocal toplam
        if isinstance(d, str):
            toplam += len(d.split())
        elif isinstance(d, dict):
            for a, v in d.items():
                if a not in _SAYILMAYAN:
                    say(v)
        elif isinstance(d, (list, tuple)):
            for v in d:
                say(v)

    for anahtar, deger in veri.items():
        if anahtar in _SLAYT_METNI or str(anahtar).startswith("slayt_"):
            say(deger)
    return toplam


def slayt_surelerini_hesapla(
    toplam_slayt: int,
    haber: Optional[dict] = None,
    varsayilan_kapak_suresi: float = 4.2,
    kapak_konusma_suresi: float = 0.0,
) -> List[float]:
    """Slayt başına ekranda kalma süresi (saniye).

    * Kapak: seslendirme varsa ses bitene kadar (+ nefes ve geçiş payı), yoksa 4,2 sn.
    * Diğerleri: Reels temposuna uygun akıcı okuma süresi (3.2 - 5.5 sn arası).
    """
    if toplam_slayt <= 0:
        return []
    kapak = varsayilan_kapak_suresi
    if kapak_konusma_suresi > 0:
        kapak = max(kapak, round(0.4 + kapak_konusma_suresi + 0.8 + GECIS_SN, 2))
    sureler = [kapak]
    if toplam_slayt == 1:
        return sureler
    kelime = _detay_kelime_sayisi(haber)
    slayt_basi = kelime / (toplam_slayt - 1) if kelime else 15
    sure = round(min(DETAY_AZAMI_SN, max(DETAY_ASGARI_SN, 1.0 + slayt_basi / OKUMA_HIZI_KELIME_SN)), 2)
    return sureler + [sure] * (toplam_slayt - 1)


KEN_BURNS_ORAN: float = 0.016  # Yavaş, sinematik ve asil Ken Burns yakınlaşma oranı (%1.6 - belgesel standardı)


def _ken_burns_kare(
    img: Image.Image,
    t_orani: float,
    oran: float = KEN_BURNS_ORAN,
    mod: str = "in",
) -> np.ndarray:
    """Tek bir kare için yavaş, sinematik Ken Burns (zoom-in / zoom-out) çerçevesi üretir."""
    w, h = img.size
    t_orani = max(0.0, min(1.0, float(t_orani)))
    if mod == "in":
        scale = 1.0 + oran * t_orani
    else:
        scale = (1.0 + oran) - oran * t_orani

    if abs(scale - 1.0) < 1e-5:
        return np.array(img, dtype=np.float32)

    new_w = int(w * scale)
    new_h = int(h * scale)
    zoomed = img.resize((new_w, new_h), Image.Resampling.BILINEAR)
    sol = (new_w - w) // 2
    ust = (new_h - h) // 2
    kirp = zoomed.crop((sol, ust, sol + w, ust + h))
    return np.array(kirp, dtype=np.float32)


def slaytlardan_video_uret(
    slayt_yollari: List[Path | str],
    cikti_yolu: Optional[Path] = None,
    slayt_suresi_saniye: float = 3.5,
    gecis_suresi_saniye: float = 0.5,
    hedef_sure: Optional[float] = None,
    fps: int = 30,
    slayt_sureleri: Optional[List[float]] = None,
    haber: Optional[dict] = None,
    ken_burns_orani: float = KEN_BURNS_ORAN,
) -> Optional[Path]:
    """
    Slayt görsellerini alıp akıcı Cosine S-Curve crossfade geçişleri,
    yavaş sinematik Ken Burns hareketi ve Stereo AAC ses izi ile 1080x1920 MP4 video üretir.

    * hedef_sure verilirse slayt süreleri bu süreye (örn: seslendirme süresi) göre dinamik ayarlanır.
    * hedef_sure yoksa slayt_surelerini_hesapla ile içerik yoğunluğuna göre dinamik insani süreler uygulanır.
    * İlk slaytta (Kapak) kanca etkisi ve okunabilirlik için 4.2 saniye bekleme.
    * S-Curve yumuşak kararma geçişleri (titremesiz).
    * Yavaş, gözü yormayan %1.6 Ken Burns sinematik yaklaşma/uzaklaşma (belgesel standardı).
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

    log.info("Dikey video üretimi başlatılıyor: %d slayt -> %s (fps=%d, hedef_sure=%s, ken_burns=%.3f)", len(slayt_yollari), cikti_yolu, fps, hedef_sure, ken_burns_orani)

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

        toplam_slayt = len(kareler_ham)
        if toplam_slayt == 1:
            # Tek sayfalık görsel için sinematik yavaş zoom; en az 6,5 sn, seslendirme
            # varsa ses bitene kadar (sözlük kartında ses 6,5 sn'de kesiliyordu)
            tek_img = kareler_ham[0]
            toplam_kare_tek = int(fps * max(6.5, hesaplanan_sureler[0] if hesaplanan_sureler else 0))
            for k in range(toplam_kare_tek):
                t = k / float(toplam_kare_tek)
                frame = _ken_burns_kare(tek_img, t, oran=ken_burns_orani, mod="in")
                writer.append_data(np.clip(frame, 0, 255).astype(np.uint8))
        else:
            ken_burns_modlar = ["in", "out"]
            for idx in range(toplam_slayt):
                cur_img = kareler_ham[idx]
                next_img = kareler_ham[(idx + 1) % toplam_slayt] if idx < toplam_slayt - 1 else None
                mod = ken_burns_modlar[idx % len(ken_burns_modlar)]
                next_mod = ken_burns_modlar[(idx + 1) % len(ken_burns_modlar)]

                # İçerik ve kelime yoğunluğuna göre dinamik hesaplanan kare sayısı
                bu_slayt_suresi = hesaplanan_sureler[idx] if idx < len(hesaplanan_sureler) else slayt_suresi_saniye
                bu_slayt_toplam_kare = max(1, int(fps * bu_slayt_suresi))
                bu_slayt_sabit_kare = max(1, bu_slayt_toplam_kare - gecis_kare_sayisi) if next_img else bu_slayt_toplam_kare

                # A. Sabit & Ken Burns hareketi aşaması
                if ken_burns_orani > 0:
                    for f in range(bu_slayt_sabit_kare):
                        t = f / float(bu_slayt_toplam_kare)
                        frame = _ken_burns_kare(cur_img, t, oran=ken_burns_orani, mod=mod)
                        writer.append_data(np.clip(frame, 0, 255).astype(np.uint8))
                else:
                    arr_uint8 = np.clip(np.array(cur_img, dtype=np.float32), 0, 255).astype(np.uint8)
                    for _ in range(bu_slayt_sabit_kare):
                        writer.append_data(arr_uint8)

                # B. Cosine S-Curve Crossfade Geçiş Aşaması (Ken Burns akarken geçiş)
                if gecis_kare_sayisi > 0 and next_img:
                    next_sure = hesaplanan_sureler[idx + 1] if idx + 1 < len(hesaplanan_sureler) else slayt_suresi_saniye
                    next_toplam_kare = max(1, int(fps * next_sure))
                    for f in range(gecis_kare_sayisi):
                        if ken_burns_orani > 0:
                            global_t = (bu_slayt_sabit_kare + f) / float(bu_slayt_toplam_kare)
                            cur_frame = _ken_burns_kare(cur_img, global_t, oran=ken_burns_orani, mod=mod)
                            next_t = f / float(next_toplam_kare)
                            next_frame = _ken_burns_kare(next_img, next_t, oran=ken_burns_orani, mod=next_mod)
                        else:
                            cur_frame = np.array(cur_img, dtype=np.float32)
                            next_frame = np.array(next_img, dtype=np.float32)

                        alpha = 0.5 * (1.0 - math.cos(math.pi * ((f + 1) / float(gecis_kare_sayisi))))
                        gecis_arr = (1.0 - alpha) * cur_frame + alpha * next_frame
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
    ken_burns_orani: float = KEN_BURNS_ORAN,
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
        ken_burns_orani=ken_burns_orani,
    )

