#!/usr/bin/env python3
"""
scripts/tiktok_auth.py — TikTok Content Posting API v2 PKCE Yetkilendirme Sihirbazı
EDM Yapı & Gayrimenkul — TikTok Entegrasyonu

TikTok Developer Portal'da Sandbox veya Canlı uygulama yetkisi almak için kullanılır.
Portalda App ayarlarındaki Redirect URI:
    https://edm-telegram-dispatcher.ezanplus.workers.dev/tiktok-callback
olmalıdır.
"""

import base64
import hashlib
import json
import os
import secrets
import sys
import urllib.parse
import webbrowser
from pathlib import Path

import requests
from dotenv import load_dotenv

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

load_dotenv(KOK / ".env")

REDIRECT_URI = os.getenv("TIKTOK_REDIRECT_URI", "https://edmyapigayrimenkul.com/tiktok-callback")
SCOPES = ["user.info.basic", "video.upload", "video.publish"]


def generate_pkce_pair():
    """PKCE code_verifier ve code_challenge üretir."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def main():
    print("=" * 65)
    print("🎵 EDM YAPI & GAYRİMENKUL — TIKTOK PKCE YETKİLENDİRME SİHİRBAZI")
    print("=" * 65)

    client_key = os.getenv("TIKTOK_CLIENT_KEY", "").strip()
    client_secret = os.getenv("TIKTOK_CLIENT_SECRET", "").strip()

    if not client_key:
        print("\n📌 TikTok Developer Portal'dan (developers.tiktok.com) aldığınız:")
        client_key = input("👉 Client Key: ").strip()
    if not client_secret:
        client_secret = input("👉 Client Secret: ").strip()

    if not client_key or not client_secret:
        print("❌ Client Key veya Client Secret boş bırakılamaz.")
        return

    code_verifier, code_challenge = generate_pkce_pair()

    auth_params = {
        "client_key": client_key,
        "scope": ",".join(SCOPES),
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "state": "edm_tiktok_auth",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    auth_url = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(auth_params)

    print(f"\n📌 TikTok Portalındaki Redirect URI:")
    print(f"   {REDIRECT_URI}")
    print("\n🌐 Tarayıcıda yetkilendirme sayfası açılıyor...")
    print(f"🔗 Link:\n{auth_url}\n")

    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    print("=" * 65)
    print("📋 Yetkilendirmeyi onayladıktan sonra ekranda açılan KODU yapıştırın:")
    code_raw = input("👉 Kod veya Yönlenen URL: ").strip()

    code = code_raw
    if "code=" in code_raw:
        parsed = urllib.parse.urlparse(code_raw)
        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [code_raw])[0]

    if not code:
        print("❌ Yetkilendirme kodu girilmedi.")
        return

    print("✅ Kod işleniyor, Access Token alınıyor...")

    token_url = "https://open.tiktokapis.com/v2/oauth/token/"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "client_key": client_key,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier,
    }

    try:
        res = requests.post(token_url, headers=headers, data=data, timeout=20)
        veri = res.json()
    except Exception as e:
        print(f"❌ TikTok API bağlantı hatası: {e}")
        return

    data_block = veri.get("data", {})
    access_token = data_block.get("access_token") or veri.get("access_token")
    refresh_token = data_block.get("refresh_token") or veri.get("refresh_token")
    open_id = data_block.get("open_id") or veri.get("open_id")

    if not access_token:
        print(f"\n❌ Token alınamadı: {veri}")
        return

    print("\n🎉 TEBRİKLER! TikTok yetkilendirmesi başarıyla tamamlandı.")
    print(f"🔑 Access Token: {access_token[:15]}...")

    # .env'ye kaydet
    env_path = KOK / ".env"
    satirlar = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []

    yeni_anahtarlar = {
        "TIKTOK_CLIENT_KEY": client_key,
        "TIKTOK_CLIENT_SECRET": client_secret,
        "TIKTOK_ACCESS_TOKEN": access_token,
        "TIKTOK_REFRESH_TOKEN": refresh_token or "",
        "TIKTOK_OPEN_ID": open_id or "",
    }

    seen = set()
    yeni_satirlar = []
    for s in satirlar:
        if "=" in s:
            k = s.split("=", 1)[0].strip()
            if k in yeni_anahtarlar:
                yeni_satirlar.append(f"{k}={yeni_anahtarlar[k]}")
                seen.add(k)
                continue
        yeni_satirlar.append(s)

    for k, v in yeni_anahtarlar.items():
        if k not in seen and v:
            yeni_satirlar.append(f"{k}={v}")

    env_path.write_text("\n".join(yeni_satirlar) + "\n", encoding="utf-8")
    print("💾 .env dosyası güncellendi!")

    # Veritabanına YAZILMAZ: data/edm.db git'e gidiyor, jetonlar depo geçmişine
    # girer. Üretimin okuduğu yer GitHub secret'ları.
    try:
        from src import refresh_token as rt
        tamam = rt.github_secret_guncelle(access_token, "TIKTOK_ACCESS_TOKEN")
        if refresh_token:
            tamam = rt.github_secret_guncelle(refresh_token, "TIKTOK_REFRESH_TOKEN") and tamam
        print("💾 GitHub secret'ları güncellendi!" if tamam else
              "⚠️ GitHub secret'ları güncellenemedi — TIKTOK_ACCESS_TOKEN ve TIKTOK_REFRESH_TOKEN'ı\n"
              "   depo ayarlarından (Settings → Secrets → Actions) elle güncelle.")
    except Exception as e:
        print(f"⚠️ GitHub secret'ları güncellenemedi ({e}); depo ayarlarından elle güncelle.")

    print("=" * 65)


if __name__ == "__main__":
    main()
