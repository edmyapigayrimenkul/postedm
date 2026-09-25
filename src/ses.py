"""
ses.py — EDM Emlak Fon Müzikleri & Video Arkaplan Sesi Miksleme Modülü

YouTube Shorts ve Facebook Reels videolarına kurumsal, sakin gayrimenkul fon
müziği ve ElevenLabs seslendirmesi miksler.

Not (2026-09-26): assets/audio parçalarının kaynağı ve lisansı depoda kayıtlı
değil; "telifsiz" olduğu doğrulanamadı.
"""

from __future__ import annotations

import logging
import os
import random
import re
import hashlib
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import imageio_ffmpeg
import requests

from . import config, okunus

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

DEFAULT_ELEVENLABS_VOICE_ID = "J17lijyP1BHYcM7ld0Rg"  # Adam — config.yaml'da ses yoksa


def _ses_ayari(anahtar: str, varsayilan: Any = None) -> Any:
    return config.ayar_al(f"seslendirme.{anahtar}", varsayilan)


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
    hiz: Optional[float] = None,
) -> Optional[Path]:
    """Metni ElevenLabs ile seslendirir (ses ve ayarlar config.yaml › seslendirme).

    Metin önce okunus.okunusa_cevir'den geçer: "Hz." hazreti, "1/5000" beş binde
    bir, "KDV" ka de ve okunur. Seçilen ses kütüphaneden kalkmışsa yedek sese
    düşülür; yetki ya da kota hatasında (401/402) beklemeden vazgeçilir.
    """
    api_key = config.env_al("ELEVENLABS_API_KEY")
    if not api_key:
        log.warning("ELEVENLABS_API_KEY bulunamadı, seslendirme atlanıyor.")
        return None

    temiz_metin = okunus.okunusa_cevir(metin or "")
    if not temiz_metin:
        return None

    # ELEVENLABS_VOICE_ID ortam değişkeni bilerek okunmuyor: yereldeki eski değer
    # config.yaml'daki seçimi sessizce geri çeviriyordu. Tek kaynak config.yaml.
    sesler = [s for s in dict.fromkeys([ses_id, _ses_ayari("ses_id"), _ses_ayari("yedek_ses_id"),
                                        DEFAULT_ELEVENLABS_VOICE_ID]) if s]
    ayarlar = dict(_ses_ayari("ayarlar", {}) or {})
    if hiz:
        ayarlar["speed"] = hiz

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/ses_{os.getpid()}_{int(time.time() * 1000)}.mp3")
    cikti_yolu = Path(cikti_yolu)
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)

    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    for el_voice_id in sesler:
        payload = {
            "text": temiz_metin,
            "model_id": _ses_ayari("model", "eleven_multilingual_v2"),
            "voice_settings": ayarlar,
            "language_code": "tr",
        }
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{el_voice_id}"
        for deneme in range(1, 4):
            try:
                log.info("🎙️ ElevenLabs TTS (deneme %d/3) [ses: %s]: %s...", deneme, el_voice_id, temiz_metin[:45])
                resp = requests.post(url, headers=headers, json=payload, timeout=45)
                if resp.status_code == 200 and len(resp.content) > 500:
                    cikti_yolu.write_bytes(resp.content)
                    log.info("ElevenLabs sesi üretildi: %s (%.1f sn)", cikti_yolu.name, ses_suresi_ogren(cikti_yolu))
                    return cikti_yolu
                log.warning("ElevenLabs API hatası (deneme %d/3) [%s]: %s", deneme, resp.status_code, resp.text[:120])
                if resp.status_code in (401, 402):
                    return None  # yetki/kota: başka ses denemek de aynı hatayı alır
                if resp.status_code in (400, 404) and "voice" in resp.text.lower():
                    break  # ses kütüphaneden kalkmış: yedek sese geç
            except Exception as e:
                log.warning("ElevenLabs ağ/istek istisnası (deneme %d/3): %s", deneme, e)
            if deneme < 3:
                time.sleep(1.5 * deneme)
    return None


# ---------------------------------------------------------------------------
# Anlatımlı video (kullanıcı kararı 2026-09-26)
# ---------------------------------------------------------------------------
# Yalnızca KAPAK okunur; madde ve bölüm başlıkları hiçbir modda okunmaz. Son
# slaytta kısa bir kapanış çağrısı. Üç versiyon (yalnız kapak / slayt başına
# tek cümle / bütün metin) dinlenip "yalnız kapak" seçildi.
ANLATIM_ONCESI_SN = 0.4    # slayt açıldıktan sonra sesin başlaması
ANLATIM_SONRASI_SN = 0.8   # ses bittikten sonra geçişe kadar nefes
CAGRI_ARASI_SN = 0.6
_HABER_TURLERI = ("dailybrief", "haber", "haber_dailybrief")


def _ilk(*adaylar: Any) -> str:
    return next((str(a).strip() for a in adaylar if isinstance(a, str) and a.strip()), "")


def _haber_mi(veri: Dict[str, Any]) -> bool:
    return str(veri.get("format_turu") or "").lower() in _HABER_TURLERI or veri.get("bicim") in ("haber", "B5")


def kapak_seslendirme_metni(veri: Optional[Dict[str, Any]]) -> Optional[str]:
    """Kapakta YAZAN metin: çoğu biçimde manşet + spot.

    Başlık/etiket okunmaz. Nedir Doğrusu'nda yalnızca doğrusu okunur: yanlış
    inanış etiketsiz okununca doğru bilgi gibi duyulur (sıfır tolerans).
    """
    if not isinstance(veri, dict):
        return None
    tur = str(veri.get("format_turu") or veri.get("format") or "").lower()
    manset = _ilk(veri.get("manset"), " ".join(
        x for x in (veri.get("manset_parca_1"), veri.get("manset_vurgu"), veri.get("manset_parca_2"))
        if isinstance(x, str) and x.strip()))

    if tur in ("sozluk", "sozluk_uret") or ("terim" in veri and ("tanim_metni" in veri or "tanim" in veri)):
        parcalar = [_ilk(veri.get("terim"), veri.get("manset_vurgu")),
                    _ilk(veri.get("tanim_metni"), veri.get("tanim"), veri.get("spot"))]
    elif tur in ("nedir_dogrusu", "dogrusu", "yaygin_yanlis") or ("yanlis_metin" in veri and "dogru_metin" in veri):
        parcalar = [_ilk(veri.get("dogru_metin"), veri.get("spot"))]
    elif tur in ("net_cevap", "soru", "kim_hakli") or ("soru" in veri and "net_cevap" in veri):
        soru = _ilk(veri.get("soru"))
        parcalar = [soru + ("" if not soru or soru.endswith("?") else "?"),
                    _ilk(veri.get("net_cevap"), " ".join(x for x in (veri.get("manset_vurgu"), veri.get("manset_parca_2"))
                                                         if isinstance(x, str) and x.strip())),
                    _ilk(veri.get("aciklama"), veri.get("spot"))]
    elif tur in ("vaka", "emsal_karar") or ("yargitay_hukmu" in veri and "cikarilacak_ders" in veri):
        parcalar = [manset, _ilk(veri.get("olay_detay"), veri.get("spot"))]
    else:
        parcalar = [manset, _ilk(veri.get("spot"))]

    cumleler: List[str] = []
    for p in parcalar:
        if not p:
            continue
        if p[-1] not in ".?!…":
            p += "."
        if any(p.lower().rstrip(".") in c.lower() for c in cumleler):
            continue  # manşet spotun içinde aynen geçiyorsa iki kez okunmaz
        cumleler.append(p)
    return " ".join(cumleler) or None


def kapanis_cagrisi(veri: Optional[Dict[str, Any]]) -> Optional[str]:
    """Son slaytta okunan çağrı (config.yaml › seslendirme.kapanis_cagrisi)."""
    tur = "haber" if isinstance(veri, dict) and _haber_mi(veri) else "rehber"
    return _ilk(_ses_ayari(f"kapanis_cagrisi.{tur}")) or None


def _onbellekli_seslendir(metin: str) -> Optional[Path]:
    """Kapanış çağrısı her videoda aynı: ses + ayar + metin aynıysa yeniden üretilmez."""
    anahtar = hashlib.md5(repr((_ses_ayari("ses_id"), _ses_ayari("ayarlar"), metin)).encode()).hexdigest()[:16]
    yol = config.yol_al(f"data/output/ses_onbellek/{anahtar}.mp3")
    if yol.exists() and yol.stat().st_size > 500:
        return yol
    return metin_seslendir(metin, cikti_yolu=yol)


def _anlatim_izi(parcalar: List[tuple], toplam_sure: float, cikti: Path) -> Optional[Path]:
    """(ses, başlangıç sn) parçalarını tek, video boyunda bir ize yerleştirir."""
    girdiler: List[str] = []
    zincir: List[str] = []
    for i, (yol, bas) in enumerate(parcalar):
        girdiler += ["-i", str(yol)]
        zincir.append(f"[{i}:a]adelay=delays={int(bas * 1000)}:all=1[a{i}]")
    etiketler = "".join(f"[a{i}]" for i in range(len(parcalar)))
    zincir.append(f"{etiketler}amix=inputs={len(parcalar)}:normalize=0,apad=whole_dur={toplam_sure:.2f}[out]")
    try:
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", *girdiler, "-filter_complex", ";".join(zincir),
                        "-map", "[out]", "-t", f"{toplam_sure:.2f}", "-ar", "44100", "-ac", "2", str(cikti)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return cikti
    except Exception as e:
        log.warning("Anlatım izi kurulamadı, video müzikle çıkacak: %s", e)
        return None


def anlatimli_video_uret(
    slayt_yollari: List[Path | str],
    veri: Optional[Dict[str, Any]] = None,
    cikti_yolu: Optional[Path] = None,
    muzik: bool = True,
    sonuc: Optional[Dict[str, Any]] = None,
) -> Optional[Path]:
    """Onaylanan slaytlardan seslendirmeli 9:16 video ("🎙️ Sesli Yayınla").

    Kapak, okunan metin bitene kadar ekranda kalır; diğer slaytlar okuma süresi
    kadar (video.slayt_surelerini_hesapla). Son slaytta kapanış çağrısı.
    `muzik=False`: fon müziksiz — yalnızca ses. Anahtar yoksa ya da ElevenLabs
    düşerse video seslendirmesiz çıkar; `sonuc["anlatim"]` bunu yayın raporuna taşır.
    """
    from . import video

    if not slayt_yollari:
        return None
    kapak_sesi = cagri_sesi = None
    try:
        metin = kapak_seslendirme_metni(veri)
        kapak_sesi = metin_seslendir(metin) if metin else None
        cagri = kapanis_cagrisi(veri) if kapak_sesi else None
        cagri_sesi = _onbellekli_seslendir(cagri) if cagri else None
    except Exception as e:
        log.warning("Seslendirme üretilemedi, video müzikle çıkacak: %s", e)

    kapak_suresi = ses_suresi_ogren(kapak_sesi) if kapak_sesi else 0.0
    cagri_suresi = ses_suresi_ogren(cagri_sesi) if cagri_sesi else 0.0
    sureler = video.slayt_surelerini_hesapla(len(slayt_yollari), haber=veri, kapak_konusma_suresi=kapak_suresi)

    parcalar: List[tuple] = []
    if kapak_sesi:
        parcalar.append((kapak_sesi, ANLATIM_ONCESI_SN))
    if cagri_sesi:
        # Çağrı son slaytın SONUNA yaslanır: izleyici önce okur, sonra duyar. Tek
        # slaytta (sözlük) kapak sesinin ardından gelir. Slayt yetmiyorsa uzatılır.
        son_bas = sum(sureler[:-1])
        asgari_bas = son_bas + (ANLATIM_ONCESI_SN + kapak_suresi + CAGRI_ARASI_SN if len(sureler) == 1 else CAGRI_ARASI_SN)
        gerekli = asgari_bas - son_bas + cagri_suresi + ANLATIM_SONRASI_SN + video.GECIS_SN
        sureler[-1] = round(max(sureler[-1], gerekli), 2)
        video_sonu = sum(sureler) - video.GECIS_SN  # son slaytın geçiş payı kullanılmıyor
        parcalar.append((cagri_sesi, max(asgari_bas, video_sonu - cagri_suresi - ANLATIM_SONRASI_SN)))

    if sonuc is not None:
        sonuc["anlatim"] = bool(kapak_sesi)
    sessiz = video.slaytlardan_reels_uret(slayt_yollari, cikti_yolu=cikti_yolu, slayt_sureleri=sureler, haber=veri)
    if not sessiz or not Path(sessiz).exists():
        return sessiz
    anlatim = _anlatim_izi(parcalar, sum(sureler), Path(sessiz).with_name(f"{Path(sessiz).stem}_anlatim.wav")) if parcalar else None
    if sonuc is not None:
        sonuc["anlatim"] = bool(anlatim)
    karisik = sesli_video_hazirla(sessiz, konusma_sesi=anlatim, ses_seviyesi=0.14 if anlatim else 0.20, muzik=muzik)
    if karisik and Path(karisik) != Path(sessiz) and Path(karisik).exists():
        # Ara dosyalar: sessiz video ve anlatım izi artık gerekmiyor
        for ara in (Path(sessiz), anlatim):
            if ara:
                Path(ara).unlink(missing_ok=True)
    return karisik


def sesli_video_hazirla(
    video_yolu: Path | str,
    ses_dosyasi: Optional[Path | str] = None,
    konusma_sesi: Optional[Path | str] = None,
    ses_seviyesi: float = 0.14,
    hedef_yol: Optional[Path | str] = None,
    muzik: bool = True,
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
    if yol.stem.endswith("_sesli"):
        # Onayda seslendirilmiş video: Facebook/YouTube yüklemesi yeniden
        # karıştırırsa anlatım silinip yerine yalnız müzik konuyordu.
        return yol
    lufs = _ses_ayari("hedef_lufs", -14)
    ses_duzeyi = f"loudnorm=I={lufs}:TP=-1.5:LRA=11"

    if hedef_yol is None:
        cikti_yolu = yol.with_name(f"{yol.stem}_sesli.mp4")
    else:
        cikti_yolu = Path(hedef_yol)

    secilen_muzik = (Path(ses_dosyasi) if ses_dosyasi else ses_sec()) if muzik else None
    secilen_konusma = Path(konusma_sesi) if konusma_sesi and Path(konusma_sesi).exists() else None
    if not muzik and not secilen_konusma:
        # "Fon müziksiz" seçildi ve ses yok: yedek ambiyans akoru da eklenmez
        return yol

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
                f"[1:a]volume=1.0[v];[2:a]volume={ses_seviyesi:.2f}[m];[v][m]amix=inputs=2:duration=first:dropout_transition=2,{ses_duzeyi}[aout]",
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
                "-map", "0:v", "-map", "1:a", "-af", ses_duzeyi,
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

