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

# Otomatik yayında kullanılan kanallar: finans bülteniyle aynı (hazirla.yml'deki sırlarla yayınlanabilenler;
# LinkedIn sırları yalnız yayinla.yml'de var)
OTO_YAYIN_HEDEFLERI = "ig,threads,story,tiktok,facebook,youtube"


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
    baslik_etiket = "📖 <b>EDM EMLAK SÖZLÜĞÜ // OTOMATİK YAYIN</b>" if is_sozluk else "🚀 <b>OTOMATİK YAYIN</b>"

    try:
        album.medya_grubu_gonder(
            slayt_yollari,
            caption=f"{baslik_etiket} (#{haber_id})\n📌 <b>{manset}</b>\n⏳ <i>Kanallara dağıtılıyor, canlı yayın durumu birazdan iletilecek...</i>",
            yedek_urller=slayt_urlleri,
        )
    except Exception as e:  # noqa: BLE001 — görünürlük için; yayını durdurmaz
        log.warning("Otomatik yayın görseli Telegram'a iletilemedi: %s", e)

    # Sözlük kartı statik bilgi kartıdır; YouTube Shorts video kanalı hariç tutulur:
    hedefler = "ig,threads,story,tiktok,facebook" if is_sozluk else OTO_YAYIN_HEDEFLERI
    komut = [sys.executable, str(KOK / "scripts/yayinla.py"), "--tur", "haber", "--id", str(haber_id), "--hedef", hedefler]
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
