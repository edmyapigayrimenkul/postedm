"""
src/telegram/durum_metni.py — Canlı yayın durumu: kanal etiketleri, ilerleme çubuğu metni ve onay mesajının canlı güncellenmesi.

Katman 3 (etki): metni kurar, `istemci.mesaji_guncelle` ile Telegram'daki onay kartını düzenler.
"""

from __future__ import annotations

import html
import logging
import time
from typing import Dict, Optional


from . import istemci

log = logging.getLogger(__name__)


KANAL_ETIKETLERI = {
    "instagram": "Instagram Akış (4:5)",
    "ig": "Instagram Akış (4:5)",
    "instagram_story": "Instagram Story",
    "story": "Instagram Story",
    "facebook_story": "Facebook Story",
    "reels": "Instagram Reels (9:16)",
    "facebook_reels": "Facebook Reels",
    "facebook": "Facebook (Gönderi)",
    "threads": "Threads (@edmyapigayrimenkul)",
    "youtube": "YouTube Shorts",
    "shorts": "YouTube Shorts",
    "tiktok": "TikTok (@edmyapigayrimenkul)",
    "tt": "TikTok (@edmyapigayrimenkul)",
    "linkedin": "LinkedIn (@edmyapigayrimenkul)",
    "li": "LinkedIn (@edmyapigayrimenkul)",
}


def yayin_durum_metni_olustur(
    baslik: str,
    adim: int,
    toplam_adim: int,
    durum_haritasi: Dict[str, str],
    baslangic_ts: float = 0.0,
    is_telafi: bool = False,
) -> str:
    """
    Canlı paralel yayın ilerleme metnini ve platform durum listesini oluşturur.
    Instabot standardında: Her kanalın durumunu (⏳ Yükleniyor... / ✅ Yayında / ❌ Hata / ⏱️ Sırada) ve
    canlı ilerleme çubuğunu ([▰▰▱▱] %50) gösterir.
    """
    toplam = max(1, toplam_adim)
    ad = max(0, min(adim, toplam))
    dolu = "▰" * ad
    bos = "▱" * (toplam - ad)
    yuzde = int((ad / toplam) * 100)
    bar = f"<code>[{dolu}{bos}] %{yuzde} ({ad}/{toplam})</code>"

    tamamlandi = (ad == toplam and all(v not in ("⏱️ Sırada", "⏳ Yükleniyor...") for v in durum_haritasi.values()))

    if is_telafi:
        baslik_satiri = "⏳ <b>TELAFİ DAĞITIMI SÜRÜYOR...</b>"
    elif tamamlandi:
        baslik_satiri = "✅ <b>TÜM PLATFORMLARA AKTARIM TAMAMLANDI!</b>"
    else:
        baslik_satiri = "⏳ <b>YAYIN DAĞITIMI SÜRÜYOR (Paralel Motor)...</b>"

    satirlar = [baslik_satiri]
    if baslik:
        satirlar.append(f"📌 <b>{html.escape(baslik[:100])}</b>")
    satirlar.append("")
    satirlar.append(bar)
    satirlar.append("")
    satirlar.append("📱 <b>Platform Durumları:</b>")

    for k, durum in durum_haritasi.items():
        isim = KANAL_ETIKETLERI.get(k, k.upper())
        satirlar.append(f"• <b>{isim}:</b> {durum}")

    if baslangic_ts > 0:
        gecen = time.time() - baslangic_ts
        if tamamlandi:
            satirlar.append(f"\n⏱️ <i>Toplam Dağıtım Süresi: {gecen:.1f} sn • Tebrikler! 🎉</i>")
        else:
            satirlar.append(f"\n⏱️ <i>Geçen Süre: {gecen:.1f} sn</i>")

    return "\n".join(satirlar)


def canli_yayin_durumu_guncelle(
    mesaj_id: Optional[int],
    baslik: str,
    adim: int,
    toplam_adim: int,
    durum_haritasi: Dict[str, str],
    baslangic_ts: float = 0.0,
    is_telafi: bool = False,
) -> bool:
    """Paralel dağıtım sırasında onay mesajını anlık platform durumları ve ilerleme çubuğuyla canlı günceller."""
    if not mesaj_id:
        return False
    metin = yayin_durum_metni_olustur(
        baslik=baslik,
        adim=adim,
        toplam_adim=toplam_adim,
        durum_haritasi=durum_haritasi,
        baslangic_ts=baslangic_ts,
        is_telafi=is_telafi,
    )
    return istemci.mesaji_guncelle(mesaj_id, metin)
