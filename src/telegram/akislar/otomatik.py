"""
src/telegram/akislar/otomatik.py — Onay beklemeden yayın: `scripts/yayinla.py`yi alt süreç olarak çalıştırır.

Katman 4 (akış). Yayın betiği kanal kanal sonucu Telegram'a kendisi raporlar; betik sonuç üretmeden çökerse False döner
ve çağıran içeriği onaya düşürür (otomatik yol içeriği kaybettirmez).
"""

from __future__ import annotations

import html
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .. import album

log = logging.getLogger(__name__)

KOK = Path(__file__).resolve().parents[3]

# Otomatik yayında kullanılan kanallar: LinkedIn hariç tüm aktif kanallar + ElevenLabs seslendirme (ses_muzikli).
# Kullanıcı kuralı: "facebook da da instaya nasıl atıyosam öyle gitsin; youtube da her zaman içerik seslendirmeli video gidicek shorts olarak"
OTO_YAYIN_HEDEFLERI = "ig,threads,story,tiktok,facebook,youtube,ses_muzikli"
SOZLUK_OTO_YAYIN_HEDEFLERI = "ig,threads,story,tiktok,facebook,youtube,ses_muzikli"
REELS_OTO_YAYIN_HEDEFLERI = "reels,threads,story,tiktok,facebook,youtube,ses_muzikli"


def _oto_yayinla(haber_id: int, slayt_yollari: List[str], haber: Dict[str, Any],
                 slayt_urlleri: Optional[List[str]] = None) -> bool:
    """Onay beklemeden `scripts/yayinla.py` ile yayınlar. Yayın betiği kanal kanal sonucu Telegram'a kendisi
    raporlar ve durumu günceller. Betik hiç sonuç üretmeden çökerse False döner: çağıran içeriği onaya düşürür.
    """
    manset = html.escape(str(haber.get("manset") or haber.get("orijinal_baslik") or ""))
    fmt = ""
    try:
        detay = json.loads(haber.get("detay_metni") or "{}")
        fmt = str(detay.get("format_turu") or "").lower()
    except Exception:
        detay = {}

    is_sozluk = fmt in ("sozluk", "sozluk_uret") or str(haber.get("kaynak", "")).startswith("EDM Sözlük Kartı")
    is_reels = fmt == "reels" or str(haber.get("kategori", "")).upper() == "REELS"
    if is_sozluk:
        baslik_etiket = "📖 <b>EDM EMLAK SÖZLÜĞÜ // OTOMATİK YAYIN</b>"
    elif is_reels:
        baslik_etiket = "🎬 <b>EDM REELS // OTOMATİK YAYIN</b>"
    else:
        baslik_etiket = "🚀 <b>OTOMATİK YAYIN</b>"

    try:
        album.medya_grubu_gonder(
            slayt_yollari,
            caption=f"{baslik_etiket} (#{haber_id})\n📌 <b>{manset}</b>\n⏳ <i>Kanallara dağıtılıyor, canlı yayın durumu birazdan iletilecek...</i>",
            yedek_urller=slayt_urlleri,
        )
    except Exception as e:  # noqa: BLE001 — görünürlük için; yayını durdurmaz
        log.warning("Otomatik yayın görseli Telegram'a iletilemedi: %s", e)

    # Sözlük kartı IG 4:5 + Story + Threads yanında ElevenLabs sesli YouTube Shorts, Facebook Reels ve TikTok Video olarak çıkar;
    # Reels ise 9:16 seslendirmeli dikey video modunda çıkar:
    tur_arg = "reels" if is_reels else "haber"
    if is_sozluk:
        hedefler = SOZLUK_OTO_YAYIN_HEDEFLERI
    elif is_reels:
        hedefler = REELS_OTO_YAYIN_HEDEFLERI
    else:
        hedefler = OTO_YAYIN_HEDEFLERI
    komut = [sys.executable, str(KOK / "scripts/yayinla.py"), "--tur", tur_arg, "--id", str(haber_id), "--hedef", hedefler]
    log.info("İçerik #%s otomatik yayınlanıyor: %s", haber_id, komut)
    try:
        calisma = subprocess.run(komut, cwd=KOK, capture_output=True, text=True, timeout=15 * 60)
    except subprocess.TimeoutExpired:
        log.error("İçerik #%s otomatik yayını zaman aşımına uğradı", haber_id)
        return False
    if calisma.returncode == 0 or "POSTEDM_SONUC=" in calisma.stdout:
        return True
    log.error("İçerik #%s otomatik yayınlanamadı: %s\n%s", haber_id, calisma.stdout[-600:], calisma.stderr[-600:])
    return False
