"""
ses.py — EDM Emlak Fon Müzikleri & Video Arkaplan Sesi Miksleme Modülü

YouTube Shorts ve Facebook Reels videolarına telifsiz, kurumsal, sakin ve
prestijli gayrimenkul fon müziği miksler.
"""

from __future__ import annotations

import logging
import os
import random
import subprocess
from pathlib import Path
from typing import List, Optional

import imageio_ffmpeg

from . import config

log = logging.getLogger(__name__)

SES_DIZINI = config.yol_al("assets/audio")

# Mevcut Telifsiz Emlak Fon Müzikleri Kataloğu
FON_MUZIKLERI = {
    "emlak_klasik": "1_emlak_haber_fonu.mp3",
    "prestij_ambiyans": "2_prestij_gayrimenkul_ambiyans.mp3",
    "kurumsal_lofi": "3_sakin_kurumsal_lofi.mp3",
    "modern_akustik": "4_modern_bulten_akustik.mp3",
}


def ses_listesi() -> List[Path]:
    """Mevcut ses dosyalarının listesini döner."""
    if not SES_DIZINI.exists():
        return []
    dosyalar = (
        sorted(SES_DIZINI.glob("*.mp3"))
        + sorted(SES_DIZINI.glob("*.wav"))
        + sorted(SES_DIZINI.glob("*.m4a"))
    )
    # haber_fon.mp3 ile 1_emlak_haber_fonu aynıysa tekilleştir
    gorulen = set()
    essiz = []
    for d in dosyalar:
        if d.name not in gorulen and not (d.name == "haber_fon.mp3" and any(x.name == "1_emlak_haber_fonu.mp3" for x in dosyalar)):
            essiz.append(d)
            gorulen.add(d.name)
    return essiz


def ses_sec(tercih: Optional[str] = None) -> Optional[Path]:
    """
    Belirtilen veya varsayılan fon müziğini seçer.
    Kullanıcının beğendiği 1_emlak_haber_fonu.mp3 birincil önceliklidir.
    """
    if tercih:
        p = SES_DIZINI / tercih
        if p.exists():
            return p
        if tercih in FON_MUZIKLERI:
            p = SES_DIZINI / FON_MUZIKLERI[tercih]
            if p.exists():
                return p

    # 1. Öncelik: Kullanıcının özel beğendiği klasik emlak haber fonu
    klasik = SES_DIZINI / "1_emlak_haber_fonu.mp3"
    if klasik.exists():
        return klasik
    yedek_klasik = SES_DIZINI / "haber_fon.mp3"
    if yedek_klasik.exists():
        return yedek_klasik

    # 2. Diğer seçenekler arasından seçim yap
    mevcutlar = ses_listesi()
    if mevcutlar:
        return random.choice(mevcutlar)

    return None


def sesli_video_hazirla(
    video_yolu: Path | str,
    ses_dosyasi: Optional[Path | str] = None,
    ses_seviyesi: float = 0.20,
    hedef_yol: Optional[Path | str] = None,
) -> Path:
    """
    YouTube Shorts ve Facebook Reels için videonun arka planına hafif,
    profesyonel emlak fon müziği miksler.

    - Arka plan müziğini sonsuz döngüyle (-stream_loop -1) videonun uzunluğuna uydurur.
    - Açılışta yumuşak fade-in (1 sn), kapanışta yumuşak fade-out (2 sn) uygular.
    - Sesi %20 seviyesine çekerek asla rahatsız etmeyecek kurumsal ambiyans sağlar.
    - -shortest ve +faststart ile kusursuz sosyal medya video çıktısı üretir.
    """
    yol = Path(video_yolu)
    if not yol.exists() or yol.stat().st_size == 0:
        return yol

    if hedef_yol is None:
        cikti_yolu = yol.with_name(f"{yol.stem}_sesli.mp4")
    else:
        cikti_yolu = Path(hedef_yol)

    # Seçilen veya varsayılan fon müziği
    secilen_ses = Path(ses_dosyasi) if ses_dosyasi else ses_sec()

    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

        if secilen_ses and secilen_ses.exists():
            komut = [
                ffmpeg_exe, "-y",
                "-i", str(yol),
                "-stream_loop", "-1", "-i", str(secilen_ses),
                "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-filter:a", f"volume={ses_seviyesi:.2f},afade=t=in:st=0:d=1,afade=t=out:st=12:d=2",
                "-shortest", "-movflags", "+faststart",
                str(cikti_yolu),
            ]
            log.info("Fon müziği miksleniyor: %s (Ses: %s, Seviye: %%%d)", yol.name, secilen_ses.name, int(ses_seviyesi * 100))
        else:
            # Yedek: Sıcak C-Maj7 kurumsal ambiyans akor yatağı üret
            komut = [
                ffmpeg_exe, "-y",
                "-i", str(yol),
                "-f", "lavfi", "-i",
                "aevalsrc=0.015*sin(2*PI*130.81*t)+0.012*sin(2*PI*164.81*t)+0.012*sin(2*PI*196.00*t)+0.010*sin(2*PI*261.63*t):s=44100",
                "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                "-filter:a", "volume=0.22,afade=t=in:st=0:d=1,afade=t=out:st=12:d=2",
                "-shortest", "-movflags", "+faststart",
                str(cikti_yolu),
            ]
            log.info("Özel fon müziği bulunamadı, C-Maj7 sıcak ambiyans fonu üretiliyor.")

        subprocess.run(komut, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if cikti_yolu.exists() and cikti_yolu.stat().st_size > 0:
            log.info("Sesli video başarıyla üretildi: %s (%.2f MB)", cikti_yolu.name, cikti_yolu.stat().st_size / (1024 * 1024))
            return cikti_yolu
    except Exception as e:
        log.warning("Ses miksi başarısız, orijinal video ile devam: %s", e)

    return yol
