"""
yayin/videolar.py — Dikey (9:16) video ve fon müziği/seslendirme hazırlığı (YouTube Shorts, Facebook Reels, TikTok, Reels teslimi).

⚠️ INSTABOT STANDARDI: ONAYLANAN GÖRSEL YAYINA ÇIKAN GÖRSEL OLMALI. Video, kullanıcının Telegram'da görüp onayladığı slaytlardan
derlenir; çalıştırıcıda slaytlar sıfırdan üretilmez (aksi halde Pexels'ten bambaşka stok görsel çekebilir).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

from .. import ses, video
from .baglam import YayinBaglami
from .sonuc import BILGI, Satir

log = logging.getLogger(__name__)


def _uret(b: YayinBaglami, slaytlar, veri=None):
    """Düz yayında sessiz video (fon müziği sonradan eklenir); sesli yayında kapak seslendirmesi + kapanış çağrısı."""
    if b.ses_modu:
        return ses.anlatimli_video_uret(slaytlar, veri=veri, muzik=(b.ses_modu == "muzikli"), sonuc=b.ses_sonucu)
    return video.slaytlardan_reels_uret(slaytlar, haber=veri)


def _kayitli_video(b: YayinBaglami) -> Optional[Path]:
    """Onay anında derlenmiş video taze ise o (seslendirmesiz); slaytlardan eskiyse yeniden üretilir."""
    if not (b.haber and b.haber.get("video_yolu") and not b.ses_modu):  # onaydaki video seslendirmesiz
        return None
    vy = Path(b.haber["video_yolu"])
    if not (vy.exists() and vy.stat().st_size > 0):
        return None
    # Tazelik kontrolü: Video, onaylanan slaytlardan eski mi?
    slayt_mtimes = [Path(p).stat().st_mtime for p in b.slayt_yollari if Path(p).exists()]
    if slayt_mtimes and vy.stat().st_mtime < max(slayt_mtimes):
        log.warning("Kayıtlı video dosyası (%s) slaytlardan eski; onaylı slaytlara göre yeniden üretilecek.", vy.name)
        return None
    return vy


def _dikey_slaytlar(b: YayinBaglami) -> List[str]:
    """1. Öncelik: tam ekran native 9:16 slaytlar (1080x1920). Video asla 4:5 kırpılmış ve tepesi boş bırakılmış zeminle üretilmez."""
    from .. import make_image, yeni_formatlar
    detay = b.detay
    ref_id = b.ref_id
    fmt = detay.get("format_turu") if isinstance(detay, dict) else None
    dikey: List[str] = []
    if detay and isinstance(detay, dict):
        try:
            if fmt in ("dailybrief", "haber", "haber_dailybrief") or detay.get("bicim") in ("haber", "B5"):
                uretim = yeni_formatlar.slaytlari_uret(detay, format_turu="dailybrief", cikti_onek=f"reels_{ref_id}", olcu="story")
                if uretim:
                    dikey = [str(p) for p in uretim[:3]]
            elif fmt in ("sozluk", "sozluk_uret"):
                uretim = yeni_formatlar.slaytlari_uret(detay, format_turu="sozluk", cikti_onek=f"reels_{ref_id}", olcu="story")
                if uretim:
                    dikey = [str(p) for p in uretim]
            elif fmt in ("nedir_dogrusu", "net_cevap", "vaka"):
                uretim = yeni_formatlar.slaytlari_uret(detay, format_turu=fmt, cikti_onek=f"reels_{ref_id}", olcu="story")
                if uretim:
                    dikey = [str(uretim[0]), str(uretim[1]), str(uretim[-1])] if len(uretim) > 3 else [str(p) for p in uretim]
            elif detay.get("bicim") in ("B1", "B2", "B3", "B4") or not fmt or fmt == "otorite":
                detay_reels = dict(detay)
                detay_reels["_video_modu"] = True
                uretim = make_image.otorite_gonderi_slaytlari_uret(detay_reels, cikti_onek=f"reels_{ref_id}", olcu="story")
                if uretim:
                    # 3 kilit slayt: Kapak + Özet/Detay + Kapanış CTA (Asla 7 slayt boca edilmez)
                    dikey = [str(uretim[0]), str(uretim[1]), str(uretim[-1])] if len(uretim) > 3 else [str(p) for p in uretim]
        except Exception as de:  # noqa: BLE001
            log.warning("Native 9:16 dikey slayt üretimi başarısız: %s", de)
    return dikey


def _video_derle(b: YayinBaglami) -> Optional[Path]:
    from .. import make_image
    haber, detay = b.haber, b.detay
    haber_bilgi = {**(haber if isinstance(haber, dict) else {}), **(detay if isinstance(detay, dict) else {})}
    v_yolu: Optional[Path] = None

    # 1. Öncelik: tam ekran native 9:16 slaytlar
    b.dikey_slaytlar = _dikey_slaytlar(b)
    if b.dikey_slaytlar and all(Path(p).exists() for p in b.dikey_slaytlar):
        try:
            log.info("Native 9:16 slaytlardan (%d adet) dikey video derleniyor...", len(b.dikey_slaytlar))
            v_yolu = _uret(b, b.dikey_slaytlar, haber_bilgi)
        except Exception as ve:  # noqa: BLE001
            log.warning("Native 9:16 slaytlardan video üretilemedi: %s", ve)

    # 2. Öncelik: İlan postu
    if (not v_yolu or not v_yolu.exists()) and b.tur == "ilan" and b.ilan:
        try:
            ik1 = make_image.ilan_kapak_slayti_ciz(b.ilan)
            ik2 = make_image.ilan_detay_slayti_ciz(b.ilan)
            ik3 = make_image.ilan_kapanis_slayti_ciz(b.ilan)
            v_yolu = _uret(b, [str(ik1), str(ik2), str(ik3)])
        except Exception as ve:  # noqa: BLE001
            log.warning("İlan slaytlarından video üretilemedi: %s", ve)

    # 3. Son Çare Fallback: Yalnızca native 9:16 üretilemezse mevcut onaylı slaytları kullan (en fazla 3 slayt)
    if not v_yolu or not v_yolu.exists():
        kaynak_slaytlar: List[str] = []
        if b.public_urller and len(b.public_urller) > 0:
            kaynak_slaytlar = [str(u) for u in b.public_urller]
        elif haber and haber.get("slayt_urlleri"):
            try:
                db_urller = json.loads(haber["slayt_urlleri"])
                if isinstance(db_urller, list) and len(db_urller) > 0:
                    kaynak_slaytlar = [str(u) for u in db_urller]
            except Exception:  # noqa: BLE001
                pass
        if not kaynak_slaytlar and b.slayt_yollari and any(Path(p).exists() for p in b.slayt_yollari):
            kaynak_slaytlar = [str(p) for p in b.slayt_yollari if Path(p).exists()]

        if kaynak_slaytlar:
            if len(kaynak_slaytlar) > 3:
                kaynak_slaytlar = [kaynak_slaytlar[0], kaynak_slaytlar[1], kaynak_slaytlar[-1]]
            try:
                log.info("Fallback onaylı slaytlardan (%d adet) video derleniyor...", len(kaynak_slaytlar))
                v_yolu = _uret(b, kaynak_slaytlar, haber_bilgi)
            except Exception as ve:  # noqa: BLE001
                log.warning("Fallback onaylı slaytlardan video üretilemedi: %s", ve)
    return v_yolu


def hazirla(b: YayinBaglami) -> List[Satir]:
    """Video gerekiyorsa üretir (`b.v_yolu`, `b.sesli_video_yolu`, `b.dikey_slaytlar`); rapora eklenecek seslendirme notunu döner."""
    if not b.video_lazim:
        return []

    log.info("Dikey video ve fon müziği hazırlanıyor (Shorts, Reels & Telegram video çıktısı)...")
    b.v_yolu = _kayitli_video(b)

    if not b.v_yolu or not b.v_yolu.exists():
        b.v_yolu = _video_derle(b)

    if b.v_yolu and b.v_yolu.exists():
        try:
            # Sesli videoda ("_sesli") dokunulmaz; "fon müziksiz"de müzik eklenmez
            b.sesli_video_yolu = ses.sesli_video_hazirla(b.v_yolu, ses_seviyesi=0.20, muzik=(b.ses_modu != "muziksiz"))
        except Exception as se:  # noqa: BLE001
            log.warning("Fon müziği mikslenemedi: %s", se)
            b.sesli_video_yolu = b.v_yolu

    # Seslendirme durumu raporu
    notlar: List[Satir] = []
    kip = "fon müziksiz" if b.ses_modu == "muziksiz" else "fon müzikli"
    if b.ses_sonucu.get("anlatim"):
        notlar.append(Satir(f"🎙️ <b>Seslendirme ({kip}):</b> Eklendi (Alex)", BILGI))
    elif b.ses_modu:
        notlar.append(Satir("⚠️ <b>Seslendirme:</b> Üretilemedi (ElevenLabs anahtarı/kotası) — videolar seslendirmesiz çıktı", BILGI))
    return notlar
