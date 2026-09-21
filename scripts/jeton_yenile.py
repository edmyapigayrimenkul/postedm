#!/usr/bin/env python3
"""
scripts/jeton_yenile.py — Jeton Sağlığı ve Otomatik Yenileme

instabot dersi: **ölmüş jeton yenilenemiyor.** Süre dolmasını bekleme;
haftalık yenile, her seferinde 60 güne çeksin. Bir hafta kaçsa bile
ikinci şans kalır.

Jeton yenilenmezse bot bir sabah sessizce durur ve sebebi günlerce aranır.
Bu yüzden sonuç HER DURUMDA Telegram'a raporlanır — "sessiz başarısızlık"
bu projedeki en sık hata sınıfı.

    python scripts/jeton_yenile.py            # yenile + rapor
    python scripts/jeton_yenile.py --sadece-kontrol
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

import requests

from src import config, refresh_token

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# Yenilenen jeton buraya da yazılır; runner .env taşımıyor, Secret'tan okuyor.
GITHUB_SECRET_ADI = "THREADS_ACCESS_TOKEN"


def _youtube_durumu() -> Dict[str, Any]:
    """YouTube refresh_token'ı hâlâ geçerli mi.

    ⚠️ 7 GÜN TUZAĞI (MEMORY.md §6.1): Google Cloud OAuth ekranı "Testing"
    modundaysa refresh_token TAM 7 GÜN SONRA sessizce iptal ediliyor.
    Kalıcı çözüm consent screen'i "In production"a almak — ama logo
    yüklenmemeli, yoksa haftalarca süren marka incelemesi tetikleniyor.
    """
    cid = config.env_al("YOUTUBE_CLIENT_ID")
    csecret = config.env_al("YOUTUBE_CLIENT_SECRET")
    rtoken = config.env_al("YOUTUBE_REFRESH_TOKEN")
    if not (cid and csecret and rtoken):
        return {"gecerli": None, "mesaj": "yapılandırılmamış"}
    try:
        r = requests.post(
            "https://oauth2.googleapis.com/token",
            data={"client_id": cid, "client_secret": csecret,
                  "refresh_token": rtoken, "grant_type": "refresh_token"},
            timeout=20,
        )
        if r.status_code == 200:
            return {"gecerli": True, "mesaj": "refresh_token çalışıyor"}
        # Google hata gövdesi jeton yankılayabilir; yalnızca hata kodunu al
        kod = ""
        try:
            kod = r.json().get("error", "")
        except Exception:
            pass
        ek = " — OAuth ekranı 'Testing' modunda olabilir (7 gün tuzağı)" \
             if kod == "invalid_grant" else ""
        return {"gecerli": False, "mesaj": f"HTTP {r.status_code} {kod}{ek}"}
    except Exception as e:
        return {"gecerli": False, "mesaj": f"{type(e).__name__}"}


def main() -> int:
    ap = argparse.ArgumentParser(description="EDM jeton sağlığı ve yenileme")
    ap.add_argument("--sadece-kontrol", action="store_true",
                    help="Yenileme yapma, yalnızca durumu raporla")
    ap.add_argument("--sessiz", action="store_true", help="Telegram'a rapor gönderme")
    args = ap.parse_args()

    satirlar: List[str] = []
    sorunlu = False

    # --- Threads: 60 günlük, yenilenebilir ---
    if args.sadece_kontrol:
        d = refresh_token.threads_token_durumu()
        if d.get("gecerli"):
            satirlar.append(f"✅ Threads — {d.get('mesaj')}")
        else:
            sorunlu = True
            satirlar.append(f"❌ Threads — {d.get('mesaj')}")
    else:
        yeni = refresh_token.threads_token_yenile()
        if yeni:
            satirlar.append("✅ Threads — yenilendi, 60 gün eklendi")
            if refresh_token.github_secret_guncelle(yeni, GITHUB_SECRET_ADI):
                satirlar.append("   ↳ GitHub Secret güncellendi")
            else:
                satirlar.append("   ℹ️ GitHub Secret güncellenemedi (SECRET_YAZMA_PAT tanımlanmalı)")
        else:
            sorunlu = True
            d = refresh_token.threads_token_durumu()
            satirlar.append(f"❌ Threads YENİLENEMEDİ — {d.get('mesaj')}")
            satirlar.append("   ↳ Ölmüş jeton yenilenemez; Graph API Explorer'dan elle alınmalı")

    # --- Instagram / Facebook: kalıcı sayfa jetonu, yine de doğrula ---
    m = refresh_token.meta_token_durumu()
    if m.get("gecerli"):
        satirlar.append(f"✅ Instagram/Facebook — {m.get('mesaj', 'aktif')}")
    else:
        sorunlu = True
        satirlar.append(f"❌ Instagram/Facebook — {m.get('mesaj')}")

    # --- YouTube: 7 gün tuzağı ---
    y = _youtube_durumu()
    if y["gecerli"] is None:
        satirlar.append(f"➖ YouTube — {y['mesaj']}")
    elif y["gecerli"]:
        satirlar.append(f"✅ YouTube — {y['mesaj']}")
    else:
        sorunlu = True
        satirlar.append(f"❌ YouTube — {y['mesaj']}")

    # --- TikTok: 24 saatlik erişim jetonu, otomatik yenileme ---
    from src import tiktok
    try:
        if args.sadece_kontrol:
            token = config.env_al("TIKTOK_ACCESS_TOKEN")
            if token:
                satirlar.append("✅ TikTok — Yapılandırılmış ve aktif")
            else:
                sorunlu = True
                satirlar.append("❌ TikTok — Jeton eksik")
        else:
            yeni_tt = tiktok.token_yenile()
            if yeni_tt:
                satirlar.append("✅ TikTok — 24 saatlik jeton yenilendi")
                if refresh_token.github_secret_guncelle(yeni_tt, "TIKTOK_ACCESS_TOKEN"):
                    satirlar.append("   ↳ GitHub Secret (TIKTOK_ACCESS_TOKEN) güncellendi")
                yeni_refresh = os.environ.get("TIKTOK_REFRESH_TOKEN")
                if yeni_refresh:
                    refresh_token.github_secret_guncelle(yeni_refresh, "TIKTOK_REFRESH_TOKEN")
            else:
                token = config.env_al("TIKTOK_ACCESS_TOKEN")
                if token:
                    satirlar.append("✅ TikTok — Mevcut jeton devrede")
                else:
                    sorunlu = True
                    satirlar.append("❌ TikTok — Jeton yenilenemedi")
    except Exception as tt_err:
        sorunlu = True
        satirlar.append(f"❌ TikTok — Hata: {tt_err}")

    baslik = "🔑 <b>JETON RAPORU</b>" + ("  ⚠️ MÜDAHALE GEREKİYOR" if sorunlu else "")
    rapor = baslik + "\n\n" + "\n".join(satirlar)

    print("\n".join(satirlar))

    if not args.sessiz:
        try:
            from src import telegram_bot
            telegram_bot.mesaj_gonder(rapor)
        except Exception as e:
            log.warning("Telegram raporu gönderilemedi: %s", e)

    # Sorun varsa job kırmızı olsun — sessiz başarısızlık olmasın
    return 1 if sorunlu else 0


if __name__ == "__main__":
    raise SystemExit(main())
