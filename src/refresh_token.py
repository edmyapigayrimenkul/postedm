"""
refresh_token.py — Meta, Threads ve Sosyal Medya Token Yönetim Modülü
Instabot mimarisinden uyarlanmıştır.
Threads 60 günlük tokenını süresi bitmeden yeniler, Meta ve YouTube tokenlarının sağlığını sorgular,
.env dosyasını günceller.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

from . import config

log = logging.getLogger(__name__)

ENV_YOLU = config.ENV_YOLU


def env_guncelle(anahtar: str, yeni_deger: str) -> bool:
    """Yerel .env dosyasındaki anahtarı günceller ve os.environ'a yazar."""
    if not ENV_YOLU.exists():
        log.warning(".env dosyası bulunamadı: %s", ENV_YOLU)
        return False
    try:
        satirlar = ENV_YOLU.read_text(encoding="utf-8").splitlines()
        bulundu = False
        for i, satir in enumerate(satirlar):
            eski_anahtar = satir.split("=", 1)[0].strip()
            if eski_anahtar == anahtar:
                satirlar[i] = f"{anahtar}={yeni_deger}"
                bulundu = True
                break
        if not bulundu:
            satirlar.append(f"{anahtar}={yeni_deger}")

        ENV_YOLU.write_text("\n".join(satirlar) + "\n", encoding="utf-8")
        os.environ[anahtar] = yeni_deger
        log.info(".env güncellendi: %s", anahtar)
        return True
    except Exception as e:
        log.error(".env güncellenirken hata: %s", e)
        return False


def threads_token_durumu() -> Dict[str, Any]:
    """Threads erişim jetonunun geçerliliğini ve hesap bilgilerini kontrol eder."""
    token = config.env_al("THREADS_ACCESS_TOKEN")
    if not token:
        return {"gecerli": False, "mesaj": "THREADS_ACCESS_TOKEN tanımlı değil"}

    try:
        res = requests.get(
            "https://graph.threads.net/v1.0/me",
            params={"fields": "id,username", "access_token": token},
            timeout=15,
        )
        if res.status_code == 200:
            veri = res.json()
            return {
                "gecerli": True,
                "id": veri.get("id"),
                "username": veri.get("username"),
                "mesaj": f"Aktif (@{veri.get('username')})",
            }
        else:
            return {"gecerli": False, "kod": res.status_code, "mesaj": res.text[:200]}
    except Exception as e:
        return {"gecerli": False, "mesaj": str(e)}


def threads_token_yenile() -> Optional[str]:
    """
    Threads'in 60 günlük Long-Lived User Tokenını yeniler ve .env'ye kaydeder.
    Meta API Kuralı: Tokenın süresi bitmeden önce çağrılmalıdır.
    """
    token = config.env_al("THREADS_ACCESS_TOKEN")
    if not token:
        log.warning("Threads yenileme için mevcut token bulunamadı.")
        return None

    try:
        res = requests.get(
            "https://graph.threads.net/refresh_access_token",
            params={"grant_type": "th_refresh_token", "access_token": token},
            timeout=20,
        )
        veri = res.json()
        if res.status_code == 200 and "access_token" in veri:
            yeni_token = veri["access_token"]
            kalan_saniye = veri.get("expires_in", 0)
            kalan_gun = kalan_saniye // 86400
            log.info("Threads tokenı başarıyla yenilendi! (Geçerlilik: %d gün)", kalan_gun)

            env_guncelle("THREADS_ACCESS_TOKEN", yeni_token)
            return yeni_token
        else:
            # Meta'nın hata gövdesi jetonu yankılayabiliyor; yalnızca kod ve mesaj alınır
            try:
                h = res.json().get("error", {})
                ayrinti = f"{h.get('code', res.status_code)} {h.get('message', '')[:120]}"
            except Exception:
                ayrinti = f"HTTP {res.status_code}"
            log.error("Threads token yenileme başarısız: %s", ayrinti)
    except Exception as e:
        log.error("Threads token yenileme istisnası: %s", e)

    return None


def meta_token_durumu() -> Dict[str, Any]:
    """Instagram & Facebook Page Token geçerliliğini doğrular."""
    token = config.env_al("INSTAGRAM_ACCESS_TOKEN")
    page_id = config.env_al("FACEBOOK_PAGE_ID", "145361567360773")

    if not token:
        return {"gecerli": False, "mesaj": "INSTAGRAM_ACCESS_TOKEN tanımlı değil"}

    try:
        res = requests.get(
            f"https://graph.facebook.com/v21.0/{page_id}",
            params={"fields": "id,name,link", "access_token": token},
            timeout=15,
        )
        if res.status_code == 200:
            veri = res.json()
            return {
                "gecerli": True,
                "sayfa": veri.get("name"),
                "sayfa_id": veri.get("id"),
                "mesaj": f"Aktif ({veri.get('name')})",
            }
        else:
            return {"gecerli": False, "kod": res.status_code, "mesaj": res.text[:200]}
    except Exception as e:
        return {"gecerli": False, "mesaj": str(e)}


def youtube_token_durumu() -> Dict[str, Any]:
    """YouTube OAuth2 ve kanal bağlantısının geçerliliğini doğrular."""
    from . import youtube
    token = youtube.access_token_al()
    if not token:
        return {"gecerli": False, "mesaj": "YouTube erişim jetonu alınamadı (invalid_grant veya eksik anahtar)"}
    try:
        res = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if res.status_code == 200:
            items = res.json().get("items", [])
            if items:
                baslik = items[0].get("snippet", {}).get("title")
                kanal_id = items[0].get("id")
                return {
                    "gecerli": True,
                    "kanal": baslik,
                    "kanal_id": kanal_id,
                    "mesaj": f"Aktif (@{baslik})",
                }
            return {"gecerli": True, "mesaj": "Aktif (Kanal bilgisi alınamadı)"}
        return {"gecerli": False, "kod": res.status_code, "mesaj": res.text[:200]}
    except Exception as e:
        return {"gecerli": False, "mesaj": str(e)}


def github_secret_guncelle(yeni: str, ad: str, repo: Optional[str] = None) -> bool:
    """
    Yeni tokenı GitHub Actions Secrets'a yazar.
    `gh` CLI aracılığıyla şifrelemeyi doğrudan halleder.
    """
    import subprocess
    cmd = ["gh", "secret", "set", ad]
    if repo:
        cmd.extend(["--repo", repo])
    try:
        sonuc = subprocess.run(
            cmd,
            input=yeni,
            text=True,
            capture_output=True,
            timeout=30,
        )
        if sonuc.returncode == 0:
            log.info("GitHub Secret başarıyla güncellendi: %s", ad)
            return True
        log.warning("gh secret set hatası (%s): %s", ad, sonuc.stderr.strip()[:200])
    except FileNotFoundError:
        log.warning("gh CLI bulunamadı (GitHub secret elle güncellenmeli).")
    except Exception as e:
        log.warning("GitHub secret güncellenemedi: %s", e)
    return False

