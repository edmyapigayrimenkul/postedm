"""
scripts/youtube_auth.py — EDM YouTube Shorts OAuth2 Yetkilendirme ve Refresh Token Sihirbazı
Tarayıcıda Google giriş ekranını açar, @edmyapigayrimenkul kanalınızı seçtiğinizde
kalıcı YOUTUBE_REFRESH_TOKEN'ı alıp .env dosyasına otomatik kaydeder.

Kullanım:
    python scripts/youtube_auth.py
"""

from __future__ import annotations

import http.server
import json
import os
import socketserver
import sys
import urllib.parse
import webbrowser
from pathlib import Path

import requests
from dotenv import load_dotenv

KOK = Path(__file__).resolve().parent.parent
load_dotenv(KOK / ".env")

REDIRECT_PORT = 8989
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


class OAuthCallbackHandler(http.server.SimpleHTTPRequestHandler):
    auth_code = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/callback":
            params = urllib.parse.parse_qs(parsed.query)
            if "code" in params:
                OAuthCallbackHandler.auth_code = params["code"][0]
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    b"<html><body style='font-family:sans-serif;text-align:center;padding:40px;background:#121316;color:#f4f4f3;'>"
                    b"<h1 style='color:#f0000d;'>&#10004; EDM YouTube Yetkilendirmesi Ba&#351;ar&#305;l&#305;!</h1>"
                    b"<p>Bu sekmeyi kapatabilir ve terminale d&#246;nebilirsiniz.</p>"
                    b"</body></html>"
                )
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Hata: Yetki kodu alinamadi.")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def main():
    print("=" * 65)
    print("🎬 EDM YAPI & GAYRİMENKUL — YOUTUBE SHORTS BAĞLANTI SİHİRBAZI")
    print("=" * 65)

    client_id = os.getenv("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        print("\n❌ .env dosyasında YOUTUBE_CLIENT_ID veya YOUTUBE_CLIENT_SECRET eksik.")
        return

    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        + urllib.parse.urlencode({
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        })
    )

    code = None
    if len(sys.argv) > 1 and sys.argv[1].strip():
        arg = sys.argv[1].strip()
        if "code=" in arg:
            parsed = urllib.parse.urlparse(arg)
            params = urllib.parse.parse_qs(parsed.query)
            code = params.get("code", [None])[0]
        else:
            code = arg

    if not code:
        print("\n🌐 Tarayıcıda yetkilendirme sayfası açılıyor...")
        print(f"🔗 Otomatik açılmazsa şu linke tıklayın:\n{auth_url}\n")

        try:
            webbrowser.open(auth_url)
        except Exception:
            pass

        try:
            socketserver.TCPServer.allow_reuse_address = True
            with socketserver.TCPServer(("localhost", REDIRECT_PORT), OAuthCallbackHandler) as httpd:
                print(f"⏳ Port {REDIRECT_PORT} üzerinde yanıt bekleniyor (Onay verildikten sonra otomatik kapanır)...")
                while not OAuthCallbackHandler.auth_code:
                    httpd.handle_request()
                code = OAuthCallbackHandler.auth_code
        except Exception as e:
            print(f"\n⚠️  Otomatik yerel dinleyici başlatılamadı ({e}).")
            print("👉 Giriş yaptıktan sonra tarayıcınızın adres çubuğundaki linki (http://localhost:8989/callback?code=...) veya sadece code= değerini yapıştırın:")
            raw = input("URL veya Kod: ").strip()
            if "code=" in raw:
                parsed = urllib.parse.urlparse(raw)
                params = urllib.parse.parse_qs(parsed.query)
                code = params.get("code", [None])[0]
            else:
                code = raw

    if not code:
        print("❌ Yetki kodu bulunamadı.")
        return

    print("✅ Yetki kodu alındı, kalıcı Refresh Token alınıyor...")

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }

    res = requests.post(token_url, data=data, timeout=15)
    try:
        veri = res.json()
    except Exception:
        print(f"\n❌ Google API yanıtı çözümlenemedi (HTTP {res.status_code}): {res.text[:200]}")
        return

    refresh_token = veri.get("refresh_token")
    if not refresh_token:
        print(f"\n❌ Refresh Token alınamadı: {veri}")
        return

    print("\n🎉 TEBRİKLER! @edmyapigayrimenkul YouTube kanalı başarıyla bağlandı.")

    # .env Dosyasına Kaydet
    env_path = KOK / ".env"
    satirlar = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []

    yeni_satirlar = []
    bulundu = False
    for s in satirlar:
        if s.startswith("YOUTUBE_REFRESH_TOKEN="):
            yeni_satirlar.append(f"YOUTUBE_REFRESH_TOKEN={refresh_token}")
            bulundu = True
        else:
            yeni_satirlar.append(s)

    if not bulundu:
        yeni_satirlar.append(f"YOUTUBE_REFRESH_TOKEN={refresh_token}")

    env_path.write_text("\n".join(yeni_satirlar) + "\n", encoding="utf-8")
    print(f"💾 Kalıcı Refresh Token postedm/.env dosyasına kaydedildi.")

    # GitHub Actions Secrets Güncelle (gh CLI varsa)
    try:
        from src.refresh_token import github_secret_guncelle
        if github_secret_guncelle(refresh_token, "YOUTUBE_REFRESH_TOKEN"):
            print("🔒 GitHub Actions Secrets (YOUTUBE_REFRESH_TOKEN) otomatik güncellendi.")
    except Exception as e:
        print(f"ℹ️ GitHub secret güncellenemedi (manuel girilebilir): {e}")

    print("\n" + "=" * 68)
    print("⚠️  DİKKAT: GOOGLE OAUTH 7 GÜNLÜK JETON İPTALİ TUZAĞI (Instabot Dersi)")
    print("=" * 68)
    print("Google Cloud Console -> APIs & Services -> OAuth consent screen sayfasında")
    print("Uygulama 'Testing' durumunda ise, Google refresh token'ı TAM 7 GÜN SONRA")
    print("sessizce iptal eder. Kalıcı olması için 'Publish App' butonuna basarak")
    print("'In Production' moduna almalısınız. (Logo eklemeyin, gizlilik linki verin).")
    print("=" * 68 + "\n")


if __name__ == "__main__":
    main()

