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

    print("\n🌐 Tarayıcıda yetkilendirme sayfası açılıyor...")
    print(f"🔗 Otomatik açılmazsa şu linke tıklayın:\n{auth_url}\n")

    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    print(f"⏳ Port {REDIRECT_PORT} üzerinde yanıt bekleniyor (Onay verildikten sonra otomatik kapanır)...")
    with socketserver.TCPServer(("localhost", REDIRECT_PORT), OAuthCallbackHandler) as httpd:
        while not OAuthCallbackHandler.auth_code:
            httpd.handle_request()

    code = OAuthCallbackHandler.auth_code
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
    veri = res.json()

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


if __name__ == "__main__":
    main()
