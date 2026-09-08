#!/usr/bin/env python3
"""
scripts/telegram_poller.py — EDM Telegram Botu Canlı Dinleyici (Poller)
Telegram grubundaki /ilanlar, /haber komutlarını ve buton tıklamalarını
anlık dinler, ilan önizlemelerini ve onaylanan paylaşımları yürütür.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict

import requests

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import config, db, fetch_listings, fetch_news, telegram_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def main() -> None:
    token = config.env_al("TELEGRAM_BOT_TOKEN")
    chat_id_hedef = config.env_al("TELEGRAM_CHAT_ID")

    if not token:
        log.error("TELEGRAM_BOT_TOKEN eksik!")
        return

    log.info("🤖 EDM Telegram Bot Dinleyicisi Başlatıldı (@PostEdmBot)")
    print("=" * 60)
    print("🚀 EDM Telegram Botu Dinlemede...")
    print("Gruptan /ilanlar veya buton tıklamaları bekleniyor.")
    print("=" * 60)

    offset = 0

    while True:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            params = {"offset": offset, "timeout": 20}
            res = requests.get(url, params=params, timeout=25)

            if res.status_code != 200:
                time.sleep(3)
                continue

            veri = res.json()
            results = veri.get("result", [])

            for u in results:
                offset = u["update_id"] + 1

                # 1. Buton Tıklamaları (Callback Query)
                if "callback_query" in u:
                    cb = u["callback_query"]
                    cb_id = cb["id"]
                    data = cb.get("data", "")
                    sender = cb.get("from", {}).get("first_name", "Kullanıcı")

                    log.info("Buton tıklandı: %s (Kullanıcı: %s)", data, sender)

                    # Telegram bekleme simgesini kapat
                    try:
                        requests.post(
                            f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                            json={"callback_query_id": cb_id, "text": "İşlem başlatıldı..."},
                            timeout=5,
                        )
                    except Exception:
                        pass

                    # A. İlan Seçimi: ilan_sec:19802542
                    if data.startswith("ilan_sec:"):
                        ilan_id = data.split(":")[1]
                        log.info("İlan seçildi: #%s, önizleme hazırlanıyor...", ilan_id)
                        telegram_bot.ilan_postunu_hazirla_ve_sor(ilan_id)

                    # B. İlan Menüsü Yenile: ilan_menu_yenile
                    elif data == "ilan_menu_yenile":
                        fetch_listings.portfoyu_senkronize_et()
                        telegram_bot.tek_tikla_ilan_menusu_gonder()

                    # C. Onayla ve Yayınla: onayla:haber:hepsi:12 veya onayla:ilan:ig:19802542
                    elif data.startswith("onayla:"):
                        parcalar = data.split(":")
                        if len(parcalar) == 4:
                            _, tur, hedef, ref_id = parcalar
                            log.info("Yayın onaylandı: %s #%s -> %s", tur, ref_id, hedef)
                            telegram_bot.mesaj_gonder(
                                f"🚀 <b>{tur.upper()} #{ref_id}</b> için paylaşım süreci başlatıldı...\n"
                                f"Platformlar: <b>{hedef.upper()}</b>\nLütfen bekleyin..."
                            )
                            # scripts/yayinla.py çalıştır
                            cmd = [
                                sys.executable,
                                str(KOK / "scripts/yayinla.py"),
                                "--tur",
                                tur,
                                "--id",
                                ref_id,
                                "--hedef",
                                hedef,
                            ]
                            subprocess.run(cmd, cwd=str(KOK))

                    # D. Reddet: reddet:haber:12
                    elif data.startswith("reddet:"):
                        parcalar = data.split(":")
                        tur = parcalar[1] if len(parcalar) > 1 else "içerik"
                        ref_id = parcalar[2] if len(parcalar) > 2 else ""
                        telegram_bot.mesaj_gonder(f"❌ <b>{tur.upper()} #{ref_id}</b> yayından kaldırıldı.")

                # 2. Mesaj / Komutlar
                elif "message" in u:
                    msg = u["message"]
                    text = (msg.get("text") or "").strip()
                    chat = msg.get("chat", {})
                    c_id = str(chat.get("id"))

                    if text.startswith("/ilan") or text.startswith("/ilanlar"):
                        log.info("/ilanlar komutu alındı.")
                        fetch_listings.portfoyu_senkronize_et()
                        telegram_bot.tek_tikla_ilan_menusu_gonder()

                    elif text.startswith("/haber") or text.startswith("/haberler"):
                        log.info("/haber komutu alındı.")
                        fetch_news.rss_tara()
                        bekleyenler = db.bekleyen_haberleri_getir(limit=1)
                        if bekleyenler:
                            telegram_bot.haber_onayina_sun(bekleyenler[0]["id"])
                        else:
                            telegram_bot.mesaj_gonder("Şu anda sırada bekleyen yeni sektörel haber bulunmuyor.")

                    elif text.startswith("/durum"):
                        bekleyen_haber = len(db.bekleyen_haberleri_getir(limit=100))
                        telegram_bot.mesaj_gonder(
                            f"📊 <b>EDM SOSYAL MEDYA SİSTEM DURUMU</b>\n\n"
                            f"• Bekleyen Haberler: {bekleyen_haber}\n"
                            f"• Instagram: Aktif (@edmyapigayrimenkul)\n"
                            f"• Threads: Aktif (@edmyapigayrimenkul)\n"
                            f"• YouTube: Aktif (@edmyapigayrimenkul)\n"
                            f"• TikTok: Beklemede\n\n"
                            f"Komutlar:\n"
                            f"/ilanlar - Portföyden tek tıkla ilan seç\n"
                            f"/haber - En son sektörel haberi hazırla"
                        )

        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            log.error("Poller döngü hatası: %s", e)
            time.sleep(3)


if __name__ == "__main__":
    main()
