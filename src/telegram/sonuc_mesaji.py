"""
src/telegram/sonuc_mesaji.py — Onay mesajını yayın sonucuyla güncelleme ve işlem ilerleme çubuğu.

Katman 3 (etki): `sonucu_yaz` onay kartının düğmelerini canlı bağlantı / telafi tuşlarıyla değiştirir.
"""

from __future__ import annotations

import html
import logging
from typing import Any, Dict, List, Optional


from . import istemci

log = logging.getLogger(__name__)


def sonucu_yaz(
    mesaj_id: Optional[int],
    metin: str,
    bildir: bool = False,
    reply_markup: Optional[Dict[str, Any]] = None,
    ek_dugmeler: Optional[List[List[Dict[str, str]]]] = None,
) -> bool:
    """
    Onay mesajını sonuçla günceller, butonları canlı linkler veya telafi tuşlarıyla değiştirir.
    bildir=True ise ayrıca grupta yeni bir mesaj olarak iletir.
    """
    if not reply_markup and ek_dugmeler:
        reply_markup = {"inline_keyboard": ek_dugmeler}

    duzenlendi = False
    if mesaj_id:
        duzenlendi = istemci.mesaji_guncelle(mesaj_id, metin, reply_markup=reply_markup)

    if bildir:
        try:
            istemci.mesaj_gonder(metin, reply_markup=reply_markup)
        except Exception as e:
            log.warning("Sonuç bildirimi gönderilemedi: %s", e)

    return duzenlendi


def durum_guncelle(mesaj_id: int, baslik: str, adim: int, toplam_adim: int = 4, detay: str = "") -> None:
    """İşlem sürerken Telegram'da görsel progress bar günceller."""
    if toplam_adim < 1:
        toplam_adim = 1
    adim = max(1, min(adim, toplam_adim))
    dolu = "▰" * adim
    bos = "▱" * max(0, toplam_adim - adim)
    yuzde = int((adim / max(1, toplam_adim)) * 100)
    metin = (
        f"⏳ <b>{html.escape(baslik)}</b>\n\n"
        f"<code>[{dolu}{bos}] %{yuzde} ({adim}/{toplam_adim})</code>\n"
        f"<i>{html.escape(detay)}</i>"
    )
    istemci.mesaji_guncelle(mesaj_id, metin)
