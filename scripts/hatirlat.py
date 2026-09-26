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
from datetime import datetime, timedelta, timezone
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
        gonderim = datetime.fromisoformat(str(ham).strip().replace(" ", "T"))
        if gonderim.tzinfo is None:
            gonderim = gonderim.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - gonderim).total_seconds() / 60
    except Exception:
        return None


def planli_yayin_bekliyor(haber: dict, simdi: datetime | None = None) -> bool:
    try:
        an = datetime.fromisoformat(str(haber.get("planlanan_yayin") or ""))
    except ValueError:
        return False
    if an.tzinfo is None:
        an = an.replace(tzinfo=timezone.utc)
    return (simdi or datetime.now(timezone.utc)) < an + timedelta(hours=3)


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="EDM Onay Bekleyen Paylaşımları Hatırlatıcı")
    parser.add_argument("--zorla", "-z", action="store_true", help="60 dakika bekleme sınırını yok say ve hemen hatırlat")
    args = parser.parse_args(argv)

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
        baslik = haber.get("manset") or haber.get("orijinal_baslik") or "İçerik"
        mevcut_hatirlatma = haber.get("hatirlatma_sayisi") or 0

        # Planlı yayını bekleyen içerik hatırlatılmaz: hatırlatma eski onay mesajlarını
        # silip yeni kart attığı için "⏹ Planı iptal et" düğmesi kayboluyordu. Plan 3
        # saatten fazla geçmişse (cron çalışmadıysa) hatırlatma yeniden devreye girer.
        if planli_yayin_bekliyor(haber):
            log.info("Haber #%d planlı yayını bekliyor (%s); hatırlatılmadı.", haber_id, haber.get("planlanan_yayin"))
            continue

        # 1. Zaman aşımı kontrolü (Kullanıcı kuralı: 5 gün = 120 saat = 7200 dakika)
        # Gündüz gelen haberler unutulsa dahi 5 güne kadar onay kuyruğunda korunur, silinmez/arşivlenmez.
        ZAMAN_ASIMI_DAKIKA = 5 * 24 * 60
        if dakika is not None and dakika >= ZAMAN_ASIMI_DAKIKA:
            log.info("Haber #%d zaman aşımına uğradı (%d dakika, %d hatırlatma).", haber_id, int(dakika), mevcut_hatirlatma)
            db.durum_zaman_asimi_yap(haber_id)
            telegram_bot.mesaj_gonder(
                f"📁 <b>İÇERİK ZAMAN AŞIMINA UĞRADI (Arşiv Bilgisi)</b>\n\n"
                f"📌 <b>Başlık:</b> {baslik}\n\n"
                f"<i>Değerli EDM Ekibi; bu içerik taslağı 5 günlük bekleme süresinin ardından yayın akışımızın güncelliğini korumak amacıyla arşive kaldırılmıştır. İhtiyaç halinde dilediğiniz zaman yeniden üretebilirsiniz.</i>"
            )
            continue

        if not args.zorla and dakika is not None and dakika < 60:
            log.info("Haber #%d henüz %d dakikadır bekliyor, hatırlatma için erken.", haber_id, int(dakika))
            continue

        # Azami bildirim kısıtı: Kullanıcıyı mesaj yağmuruna tutmamak için en fazla 3 hatırlatma gönderilir.
        # 3 hatırlatmadan sonra içerik onay kuyruğunda sessizce 5 gün boyunca bekletilir, kullanıcı istediğinde yayınlayabilir.
        if not args.zorla and mevcut_hatirlatma >= 3:
            log.info("Haber #%d azami hatırlatma adedine (%d) ulaştı. 5 günlük onay süresine kadar sessizce bekletiliyor.", haber_id, mevcut_hatirlatma)
            continue

        yeni_sayi = db.hatirlatma_arttir(haber_id)
        saat_str = f"{int(dakika // 60)} saat " if dakika and dakika >= 60 else ""
        sure_str = f"{saat_str}{int(dakika % 60) if dakika else 0} dakika" if dakika else "Kısa bir süre"

        is_reels = (haber.get("kategori") == "REELS" or (haber.get("kaynak") and "reels" in str(haber.get("kaynak")).lower()))
        tur = "reels" if is_reels else "haber"

        if is_reels:
            metin = (
                f"✨ <b>Sayın EDM Ekibi,</b> ({yeni_sayi}. Hatırlatma)\n\n"
                f"Yayına hazır 9:16 dikey Reels videomuz onayınızı beklemektedir:\n\n"
                f"🎬 <b>Başlık:</b> {baslik}\n"
                f"⏱️ <b>Hazırlanma:</b> {sure_str} önce tamamlandı.\n\n"
                f"<i>İçeriği inceleyip aşağıdaki seçeneklerden dilediğinizi tercih edebilirsiniz:</i>"
            )
            butonlar = {
                "inline_keyboard": [
                    [
                        {"text": "🚀 YouTube & TikTok'ta Otomatik Yayınla", "callback_data": f"onayla:reels:video:{haber_id}"},
                    ],
                    [
                        {"text": "✅ Instagram'da Paylaştım (Tamamlandı)", "callback_data": f"onayla:reels:tamamla:{haber_id}"},
                    ],
                    [
                        {"text": "🔄 Yeniden Üret", "callback_data": f"yenile:reels:{haber_id}"},
                        {"text": "❌ İptal Et", "callback_data": f"reddet:reels:{haber_id}"},
                    ],
                ]
            }
        else:
            metin = (
                f"✨ <b>Sayın EDM Ekibi,</b> ({yeni_sayi}. Hatırlatma)\n\n"
                f"Onayınızı bekleyen güncel içerik taslağımız hazır durumdadır:\n\n"
                f"📌 <b>Başlık:</b> {baslik}\n"
                f"⏱️ <b>Hazırlanma:</b> {sure_str} önce tamamlandı.\n\n"
                f"<i>İçeriği inceleyip aşağıdaki seçeneklerden dilediğinizi tercih edebilirsiniz:</i>"
            )
            butonlar = {
                "inline_keyboard": [
                    [
                        {"text": "🚀 Seçili Kanallarda Yayınla", "callback_data": f"onayla:haber:ig,threads:{haber_id}"},
                        {"text": "📲 Manuel Paket", "callback_data": f"manuel_paket:{haber_id}"},
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

        # Chat kaosunu önle: Aynı içerik için daha önce atılmış olan onay veya hatırlatma kartlarını temizle
        telegram_bot.icerik_onceki_mesajlarini_temizle(tur, haber_id)

        res = telegram_bot.mesaj_gonder(metin, reply_markup=butonlar)
        if res and isinstance(res, dict) and "message_id" in res:
            _, chat_id = telegram_bot._bot_bilgileri()
            try:
                cid = int(str(chat_id).strip()) if str(chat_id).lstrip("-").isdigit() else None
                db.onay_istegi_kaydet(tur, str(haber_id), res["message_id"], cid)
            except Exception as e:
                log.warning("Hatırlatma mesaj ID kaydı hatası: %s", e)

        hatirlatilan_sayisi += 1
        log.info("Haber #%d için hatırlatma mesajı (%d.) Telegram'a iletildi.", haber_id, yeni_sayi)

    if hatirlatilan_sayisi == 0 and args.zorla:
        telegram_bot.mesaj_gonder("✨ <b>Bilgilendirme:</b> İçerik yakın zamanda hazırlandığı için henüz hatırlatma periyoduna (60 dk) girmedi.")

    db.wal_bosalt()


if __name__ == "__main__":
    main()
