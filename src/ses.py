"""
ses.py — EDM Emlak Fon Müzikleri & Video Arkaplan Sesi Miksleme Modülü

YouTube Shorts ve Facebook Reels videolarına telifsiz, kurumsal, sakin ve
prestijli gayrimenkul fon müziği miksler.
"""

from __future__ import annotations

import logging
import os
import random
import re
import subprocess
import time
from pathlib import Path
from typing import List, Optional

import imageio_ffmpeg
import requests

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

DEFAULT_ELEVENLABS_VOICE_ID = "J17lijyP1BHYcM7ld0Rg"  # Adam (Tok, vakur ve prestijli kurumsal Türkçe ses)


def ses_suresi_ogren(ses_yolu: Path | str) -> float:
    """FFmpeg ile ses dosyasının süresini (saniye cinsinden) okur."""
    p = Path(ses_yolu)
    if not p.exists() or p.stat().st_size == 0:
        return 0.0
    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        res = subprocess.run(
            [ffmpeg_exe, "-i", str(p)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", res.stderr)
        if m:
            saat, dakika, saniye = m.groups()
            return int(saat) * 3600 + int(dakika) * 60 + float(saniye)
    except Exception as e:
        log.warning("Ses süresi okunamadı (%s): %s", p, e)
    return 0.0


def metin_seslendir(
    metin: str,
    ses_id: Optional[str] = None,
    cikti_yolu: Optional[Path] = None,
    hiz: float = 1.0,
) -> Optional[Path]:
    """
    ElevenLabs Multilingual v2 ile metni Türkçe doğal insan sesine dönüştürür.
    Adam (tok ve kurumsal erkek sesi) kullanılır.
    """
    api_key = config.env_al("ELEVENLABS_API_KEY")
    if not api_key:
        log.warning("ELEVENLABS_API_KEY bulunamadı, seslendirme atlanıyor.")
        return None

    temiz_metin = metin.strip()
    # Markdown, semboller ve fazla boşlukları temizle
    temiz_metin = re.sub(r"[*_#`~\[\]()]", "", temiz_metin)
    temiz_metin = " ".join(temiz_metin.split())
    if not temiz_metin:
        return None

    el_voice_id = ses_id or config.env_al("ELEVENLABS_VOICE_ID") or DEFAULT_ELEVENLABS_VOICE_ID
    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/ses_{os.getpid()}_{int(time.time())}.mp3")
    cikti_yolu = Path(cikti_yolu)
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{el_voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "text": temiz_metin,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.60,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
            "speed": hiz,
        },
        "language_code": "tr",
    }

    for deneme in range(1, 4):
        try:
            log.info("🎙️ ElevenLabs TTS çağrılıyor (Deneme %d/3) [Voice: %s]: %s...", deneme, el_voice_id, temiz_metin[:45])
            resp = requests.post(url, headers=headers, json=payload, timeout=45)
            if resp.status_code == 200:
                raw_audio = resp.content
                if len(raw_audio) > 500:
                    cikti_yolu.write_bytes(raw_audio)
                    sure = ses_suresi_ogren(cikti_yolu)
                    log.info("ElevenLabs sesi üretildi: %s (%.1f sn, %d bayt)", cikti_yolu.name, sure, len(raw_audio))
                    return cikti_yolu
            else:
                log.warning("ElevenLabs API Hatası (Deneme %d/3) [%d]: %s", deneme, resp.status_code, resp.text[:120])
                if resp.status_code in (401, 402):
                    # Yetki veya kota aşımı durumunda beklemeden çık
                    break
        except Exception as e:
            log.warning("ElevenLabs ağ/istek istisnası (Deneme %d/3): %s", deneme, e)

        if deneme < 3:
            time.sleep(1.5 * deneme)

    return None


def sesli_video_hazirla(
    video_yolu: Path | str,
    ses_dosyasi: Optional[Path | str] = None,
    konusma_sesi: Optional[Path | str] = None,
    ses_seviyesi: float = 0.14,
    hedef_yol: Optional[Path | str] = None,
) -> Path:
    """
    Videoya ElevenLabs seslendirmesi ve/veya kurumsal fon müziği miksler.

    - konusma_sesi varsa: Konuşma sesi önde (%100), kurumsal fon müziği arkada (%14) mikslenir.
    - konusma_sesi yoksa: Yalnızca kurumsal fon müziği (%20) mikslenir.
    - Açılış/kapanış fade efektleri ve faststart moov atomu ile optimize edilir.
    """
    yol = Path(video_yolu)
    if not yol.exists() or yol.stat().st_size == 0:
        return yol

    if hedef_yol is None:
        cikti_yolu = yol.with_name(f"{yol.stem}_sesli.mp4")
    else:
        cikti_yolu = Path(hedef_yol)

    secilen_muzik = Path(ses_dosyasi) if ses_dosyasi else ses_sec()
    secilen_konusma = Path(konusma_sesi) if konusma_sesi and Path(konusma_sesi).exists() else None

    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

        if secilen_konusma and secilen_muzik and secilen_muzik.exists():
            # 1. ÇİFT KANAL: Konuşma sesi (Voiceover) + Arka plan kurumsal fon müziği (Ducking)
            komut = [
                ffmpeg_exe, "-y",
                "-i", str(yol),
                "-i", str(secilen_konusma),
                "-stream_loop", "-1", "-i", str(secilen_muzik),
                "-filter_complex",
                f"[1:a]volume=1.0[v];[2:a]volume={ses_seviyesi:.2f}[m];[v][m]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", "-movflags", "+faststart",
                str(cikti_yolu),
            ]
            log.info("Çift kanal ses miksleniyor: Voiceover (%s) + Müzik (%s, %% %d)", secilen_konusma.name, secilen_muzik.name, int(ses_seviyesi * 100))
        elif secilen_konusma:
            # 2. Yalnızca Konuşma Sesi
            komut = [
                ffmpeg_exe, "-y",
                "-i", str(yol),
                "-i", str(secilen_konusma),
                "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", "-movflags", "+faststart",
                str(cikti_yolu),
            ]
            log.info("Yalnızca konuşma sesi ekleniyor: %s", secilen_konusma.name)
        elif secilen_muzik and secilen_muzik.exists():
            # 3. Yalnızca Fon Müziği (Klasik Mod)
            muzik_seviye = 0.20
            komut = [
                ffmpeg_exe, "-y",
                "-i", str(yol),
                "-stream_loop", "-1", "-i", str(secilen_muzik),
                "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-filter:a", f"volume={muzik_seviye:.2f},afade=t=in:st=0:d=1,afade=t=out:st=12:d=2",
                "-shortest", "-movflags", "+faststart",
                str(cikti_yolu),
            ]
            log.info("Fon müziği miksleniyor: %s (Ses: %s, Seviye: %%%d)", yol.name, secilen_muzik.name, int(muzik_seviye * 100))
        else:
            # 4. Yedek: C-Maj7 kurumsal ambiyans akoru
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

