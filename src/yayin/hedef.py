"""
yayin/hedef.py — Hedef bayrakları ve hangi kanalların çalışacağı.

`--hedef` virgülle ayrılmış kanal adlarıdır ("ig,threads,fb", "hepsi", "reels,yt,ses_muzikli"); işlem adları ("reddet", "yenile", ...)
ayrı akıştır (aksiyonlar). Kurallar eski yayinla.py ile BİREBİR aynıdır; yeni kural eklenirse altın çıktı testi yakalar.
"""

from __future__ import annotations

from typing import List

from .. import linkedin, twitter
from .baglam import Istek, YayinBaglami


def linkedin_istendi(hedefler: set) -> bool:
    return ("li" in hedefler or "linkedin" in hedefler) or ("hepsi" in hedefler and linkedin.kullanilabilir_mi())


def twitter_istendi(hedefler: set) -> bool:
    return ("x" in hedefler or "twitter" in hedefler) or ("hepsi" in hedefler and twitter.kullanilabilir_mi())


def bayraklari_belirle(b: YayinBaglami) -> None:
    """Reels/Instagram/ses bayrakları ve video gerekip gerekmediği."""
    hedefler = b.hedefler
    b.reels_modu = ("reels" in hedefler) or (b.tur == "reels")

    b.paylas_reels = ("reels" in hedefler or ("hepsi" in hedefler and b.tur == "reels"))
    b.paylas_ig = ("ig" in hedefler or "instagram" in hedefler or ("hepsi" in hedefler and b.tur != "reels"))
    if b.paylas_reels:
        # Kural: İçerik ya Reels ya da Gönderi olarak atılır. Reels aktifse Instagram Feed (görsel gönderi) deaktif edilir.
        b.paylas_ig = False

    # "🎙️ Sesli Yayınla" (2026-09-26): Worker hedefe ses_muzikli / ses_muziksiz ekler.
    # Seslendirme yalnızca video kanallarına uygulanır ve TikTok'u video kipine alır
    # (fotoğraf karuseli ses taşımaz). Düz "✅ Yayınla" eskisi gibi seslendirmesiz.
    b.ses_modu = "muzikli" if "ses_muzikli" in hedefler else ("muziksiz" if "ses_muziksiz" in hedefler else None)

    b.video_lazim = (
        b.paylas_reels
        or b.hedef_mi("yt", "youtube", "shorts", "video")
        or ((b.reels_modu or b.ses_modu) and b.hedef_mi("fb", "facebook"))
        or ((b.reels_modu or b.ses_modu) and b.hedef_mi("tt", "tiktok"))
    )


def kanal_listesi(b: YayinBaglami) -> List[str]:
    """Çalışacak kanallar, çalışma (ve rapor) sırasıyla.

    ⚠️ X (Twitter) listede YOK ve eskiden de yoktu (işçi yazılmış ama hiçbir hedef onu seçmiyordu); davranış korunuyor."""
    kanallar: List[str] = []
    if b.hedef_mi("tt", "tiktok"):
        kanallar.append("tiktok")
    if b.paylas_reels:
        kanallar.append("reels")
    elif b.paylas_ig:
        kanallar.append("instagram")
    if b.hedef_mi("story"):
        kanallar.append("story")
    if b.hedef_mi("threads", "th"):
        kanallar.append("threads")
    if b.hedef_mi("fb", "facebook"):
        kanallar.append("facebook_reels" if b.reels_modu else "facebook")
    if b.hedef_mi("yt", "youtube", "shorts", "video"):
        kanallar.append("youtube")
    if linkedin_istendi(b.hedefler):
        kanallar.append("linkedin")
    return kanallar


def istek_olustur(tur: str, ref_id: str, hedef_ham: str, mesaj_id=None, yeniden_ciz: bool = False, plan_an=None) -> Istek:
    hedef = hedef_ham.lower()
    hedefler = {parca.strip() for parca in hedef.split(",") if parca.strip()}
    return Istek(tur=tur, ref_id=ref_id, hedef=hedef, hedefler=hedefler, mesaj_id=mesaj_id, yeniden_ciz=yeniden_ciz, plan_an=plan_an)
