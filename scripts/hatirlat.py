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


import argparse


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
    parser = argparse.ArgumentParser(description="EDM Onay Bekleyen Paylaşımları Hatırlatıcı")
    parser.add_argument("--zorla", "-z", action="store_true", help="60 dakika bekleme sınırını yok say ve hemen hatırlat")
    args = parser.parse_args()

    bekleyenler = db.onay_bekleyen_haberleri_getir(limit=5)
    if not bekleyenler:
        log.info("Onay bekleyen içerik yok.")
        if args.zorla:
            telegram_bot.mesaj_gonder("✨ <b>Harika!</b> Şu anda onay bekleyen herhangi bir içerik bulunmuyor.\n\nTüm içerikler yayınlandı veya akış güncel.")
        return

    hatirlatilan_sayisi = 0
    for haber in bekleyenler:
        haber_id = haber["id"]
        dakika = bekleme_suresi_dakika(haber)
        if not args.zorla and dakika is not None and dakika < 60:
            log.info("Haber #%d henüz %d dakikadır bekliyor, hatırlatma için erken.", haber_id, int(dakika))
            continue

        baslik = haber.get("manset") or haber.get("orijinal_baslik") or "İçerik"
        saat_str = f"{int(dakika // 60)} saat " if dakika and dakika >= 60 else ""
        sure_str = f"{saat_str}{int(dakika % 60) if dakika else 0} dakikadır" if dakika else "Bir süredir"

        is_reels = (haber.get("kategori") == "REELS" or (haber.get("kaynak") and "reels" in str(haber.get("kaynak")).lower()))

        if is_reels:
            metin = (
                f"⏰ <b>ONAY BEKLEYEN REELS VİDEOSU HATIRLATMASI</b>\n\n"
                f"🎬 <b>Başlık:</b> {baslik}\n"
                f"⏳ <b>Bekleme Süresi:</b> {sure_str} onay bekliyor.\n\n"
                f"<i>Videoyu Instagram uygulamasından trend müzikle paylaşabilir; YouTube Shorts ve TikTok için tek tıkla yayınlayabilirsiniz:</i>"
            )
            butonlar = {
                "inline_keyboard": [
                    [
                        {"text": "🚀 YouTube & TikTok'ta Otomatik Yayınla", "callback_data": f"onayla:reels:video:{haber_id}"},
                    ],
                    [
                        {"text": "🔄 Yeniden Üret", "callback_data": f"yenile:reels:{haber_id}"},
                        {"text": "❌ İptal Et", "callback_data": f"reddet:reels:{haber_id}"},
                    ],
                ]
            }
        else:
            metin = (
                f"⏰ <b>ONAY BEKLEYEN PAYLAŞIM HATIRLATMASI</b>\n\n"
                f"📌 <b>Başlık:</b> {baslik}\n"
                f"⏳ <b>Bekleme Süresi:</b> {sure_str} onay bekliyor.\n\n"
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
        hatirlatilan_sayisi += 1
        log.info("Haber #%d için hatırlatma mesajı Telegram'a iletildi.", haber_id)

    if hatirlatilan_sayisi == 0 and args.zorla:
        telegram_bot.mesaj_gonder("ℹ️ İçerik yakın zamanda hazırlandığı için henüz hatırlatma eşiğine (60 dk) ulaşmadı.")


if __name__ == "__main__":
    main()
