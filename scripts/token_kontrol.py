#!/usr/bin/env python3
"""
scripts/token_kontrol.py — EDM Sosyal Medya & API Token Sağlık Denetleyicisi
Instabot / Daily Brief mimarisinden uyarlanmıştır.
Tüm bağlı platformların token durumunu tek ekranda raporlar.
İsteğe bağlı olarak --threads-yenile ile Threads tokenını yeniler.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

import requests
from src import config, refresh_token, youtube


def main():
    parser = argparse.ArgumentParser(description="EDM API Token Sağlık Denetleyicisi")
    parser.add_argument("--threads-yenile", action="store_true", help="Threads 60 günlük tokenını yeniler ve .env'ye kaydeder")
    args = parser.parse_args()

    print("=" * 65)
    print(" 🏥 EDM SOSYAL MEDYA & API SAĞLIK RAPORU")
    print("=" * 65)

    # 1. Threads Token Yenileme (İstendiyse)
    if args.threads_yenile:
        print("\n⏳ Threads tokenı yenileniyor...")
        yeni = refresh_token.threads_token_yenile()
        if yeni:
            print("✅ Threads tokenı başarıyla yenilendi ve .env güncellendi!")
        else:
            print("❌ Threads tokenı yenilenemedi!")
        print("-" * 65)

    # 2. Telegram Bot Kontrolü
    tg_token = config.env_al("TELEGRAM_BOT_TOKEN")
    tg_chat = config.env_al("TELEGRAM_CHAT_ID")
    if tg_token:
        try:
            r = requests.get(f"https://api.telegram.org/bot{tg_token}/getMe", timeout=10)
            if r.status_code == 200:
                bot_ad = r.json().get("result", {}).get("username")
                print(f"✅ Telegram Bot      : Aktif (@{bot_ad}) | Grup ID: {tg_chat}")
            else:
                print(f"❌ Telegram Bot      : Geçersiz Token ({r.status_code})")
        except Exception as e:
            print(f"⚠️ Telegram Bot      : Bağlantı hatası ({e})")
    else:
        print("⚪ Telegram Bot      : Tanımsız (.env eksik)")

    # 3. Google Gemini API Kontrolü
    gemini_key = config.env_al("GEMINI_API_KEY")
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash?key={gemini_key}"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                print("✅ Google Gemini AI  : Aktif (gemini-2.5-flash yanıt veriyor)")
            else:
                print(f"❌ Google Gemini AI  : Hata ({r.status_code})")
        except Exception as e:
            print(f"⚠️ Google Gemini AI  : Bağlantı hatası ({e})")
    else:
        print("⚪ Google Gemini AI  : Tanımsız")

    # 4. Meta (Instagram & Facebook) Kontrolü
    meta_durum = refresh_token.meta_token_durumu()
    if meta_durum["gecerli"]:
        print(f"✅ Meta (IG + FB)    : {meta_durum['mesaj']} (Sayfa ID: {meta_durum.get('sayfa_id')})")
    else:
        print(f"❌ Meta (IG + FB)    : {meta_durum['mesaj']}")

    # 5. Threads API Kontrolü
    threads_durum = refresh_token.threads_token_durumu()
    if threads_durum["gecerli"]:
        print(f"✅ Threads API       : {threads_durum['mesaj']} (ID: {threads_durum.get('id')})")
    else:
        print(f"❌ Threads API       : {threads_durum['mesaj']}")

    # 6. YouTube Data API (Shorts) Kontrolü
    yt_token = youtube.access_token_al()
    if yt_token:
        print("✅ YouTube Shorts    : Aktif (OAuth2 Refresh Token geçerli)")
    else:
        print("❌ YouTube Shorts    : Token yenilenemedi (CLIENT_ID / REFRESH_TOKEN kontrol edin)")

    # 7. TikTok API Kontrolü
    tt_token = config.env_al("TIKTOK_ACCESS_TOKEN")
    tt_refresh = config.env_al("TIKTOK_REFRESH_TOKEN")
    if tt_token or tt_refresh:
        print(f"ℹ️ TikTok API        : Token tanımlı (Refresh Token: {'Var' if tt_refresh else 'Yok'})")
    else:
        print("⚪ TikTok API        : Yapılandırılmamış")

    # 8. ImgBB / Catbox Görsel Barındırma
    imgbb_key = config.env_al("IMGBB_API_KEY")
    if imgbb_key:
        print("✅ ImgBB CDN         : API Anahtarı mevcut (Catbox.moe yedek aktif)")
    else:
        print("ℹ️ Görsel CDN        : ImgBB yok, Catbox.moe yedek aktif")

    print("=" * 65)
    print("💡 İpucu: Threads tokenını yenilemek için: python scripts/token_kontrol.py --threads-yenile")


if __name__ == "__main__":
    main()
