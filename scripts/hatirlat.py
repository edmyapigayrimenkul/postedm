#!/usr/bin/env python3
"""
scripts/hatirlat.py — Onay Bekleyen Paylaşımları Telegram'da Hatırlatma Komutu
EDM Yapı & Gayrimenkul — Sosyal Medya Otomasyonu

Onay bekleyen içerik varsa (ve üzerinden 1 saatten fazla geçtiyse)
Telegram grubuna interaktif onay butonlarıyla kibar bir hatırlatma gönderir.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from src import db, telegram_bot

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def bekleme_suresi_dakika(haber: dict) -> float | None:
    ham = haber.get("eklenme_tarihi")
    if not ham:
        return None
    try:
        gonderim = datetime.fromisoformat(ham).replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - gonderim).total_seconds() / 60
    except Exception:
        return None


def main():
    bekleyenler = db.onay_bekleyen_haberleri_getir(limit=5)
    if not bekleyenler:
        log.info("Onay bekleyen içerik yok. Hatırlatmaya gerek duyulmadı.")
        return

    for haber in bekleyenler:
        haber_id = haber["id"]
        dakika = bekleme_suresi_dakika(haber)
        if dakika is not None and dakika < 60:
            log.info("Haber #%d henüz %d dakikadır bekliyor, hatırlatma için erken.", haber_id, int(dakika))
            continue

        baslik = haber.get("manset") or haber.get("orijinal_baslik") or "İçerik"
        saat_str = f"{int(dakika // 60)} saat " if dakika and dakika >= 60 else ""

        metin = (
            f"⏰ <b>ONAY BEKLEYEN PAYLAŞIM HATIRLATMASI</b>\n\n"
            f"📌 <b>Başlık:</b> {baslik}\n"
            f"⏳ <b>Bekleme Süresi:</b> {saat_str}{int(dakika % 60) if dakika else 0} dakikadır onay bekliyor.\n\n"
            f"<i>Lütfen aşağıdaki butonlardan birini seçerek yayını onaylayın veya erteleyin:</i>"
        )

        butonlar = {
            "inline_keyboard": [
                [
                    {"text": "🚀 Seçili Kanallarda Yayınla", "callback_data": f"onayla:haber:ig,threads:{haber_id}"},
                ],
                [
                    {"text": "🔄 Metinleri Yenile", "callback_data": f"yenile:haber:{haber_id}"},
                    {"text": "🎨 Formatı Değiştir", "callback_data": f"format_menu:{haber_id}"},
                ],
                [
                    {"text": "⏰ 1 Saat Ertele", "callback_data": f"ertele:haber:{haber_id}"},
                    {"text": "❌ İptal / Reddet", "callback_data": f"reddet:haber:{haber_id}"},
                ],
            ]
        }

        telegram_bot.mesaj_gonder(metin, reply_markup=butonlar)
        log.info("Haber #%d için hatırlatma mesajı Telegram'a iletildi.", haber_id)


if __name__ == "__main__":
    main()
