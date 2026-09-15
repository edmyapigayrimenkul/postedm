"""
komutlar.py — EDM Telegram Botu Tek Merkezli Komut ve Yetki Yönetimi
Tüm Telegram komutları, serbest komutlar, slash açılır menüsü (setMyCommands)
ve menü tanımları tek merkezden yönetilir.
"""

from __future__ import annotations

from typing import List, Dict, Set

# Açık bir onay mesajına bağlı olmadan chat'ten doğrudan çağrılabilen komutlar
MESAJSIZ_KOMUTLAR: Set[str] = {
    # Kontrol & Yönetim
    "panel",
    "menu",
    "durum",
    "yardim",
    "start",
    "durdur",
    "duraklat",
    "devam",
    "devam_et",
    "saglik",
    "saglik_testi",
    "havuz_durum",
    "hatirlat",

    # Hızlı İçerik Üretimi
    "yeni",
    "uret",
    "sozluk",
    "dogrusu",
    "vaka",
    "soru",
    "reels",
    "video",

    # Aksiyonlar
    "ertele",
    "iptal",
    "yenile",
    "yayinla",
}

# Telegram resmi açılır menüsünde (setMyCommands) listelenen komutlar
KOMUT_MENUSU: List[Dict[str, str]] = [
    # ── 🎛 YÖNETİM & KONTROL MERKEZİ ─────────────────────────────────
    {"command": "panel", "description": "🎛 Kontrol merkezi ve hızlı işlemler"},
    {"command": "durum", "description": "📊 Bot sağlığı, sıradaki post ve kota"},
    {"command": "hatirlat", "description": "⏰ Onay bekleyen paylaşımları anında tara"},
    {"command": "yardim", "description": "❓ Bot komutları ve kullanım kılavuzu"},

    # ── ✍️ OTORİTE İÇERİK ÜRETİMİ ─────────────────────────────────────
    {"command": "yeni", "description": "✍️ Sıradaki konuyu hemen üretip onaya sun"},
    {"command": "sozluk", "description": "📖 EDM Gayrimenkul Sözlüğü postu üret"},
    {"command": "dogrusu", "description": "⚖️ Nedir Doğrusu? (Efsane vs Gerçek) üret"},
    {"command": "vaka", "description": "📂 Hukuki Vaka Analizi (2 Slayt Carousel) üret"},
    {"command": "soru", "description": "❓ Net Cevap Rehberi (Soru & Hüküm) üret"},
    {"command": "reels", "description": "🎬 9:16 Dikey Reels videosu üretip gruba sun"},

    # ── ⏸️ AKIŞ KONTROLÜ ─────────────────────────────────────────────
    {"command": "durdur", "description": "⏸️ Otomatik paylaşımları duraklat"},
    {"command": "devam", "description": "▶️ Duraklatılmış botu başlat"},
]


def mesajsiz_komut_mu(komut: str) -> bool:
    """Komutun onay mesajı olmadan bağımsız çalışıp çalışamayacağını doğrular."""
    temiz = (komut or "").strip().lower().lstrip("/")
    return temiz in MESAJSIZ_KOMUTLAR


def menuyu_telegrama_kaydet() -> bool:
    """Telegram resmi setMyCommands API'sini çağırarak komutları 3 kapsama kaydeder."""
    import os, requests
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return False
    url = f"https://api.telegram.org/bot{token}/setMyCommands"
    basarili = True
    for scope in [{"type": "default"}, {"type": "all_private_chats"}, {"type": "all_group_chats"}]:
        try:
            r = requests.post(url, json={"commands": KOMUT_MENUSU, "scope": scope}, timeout=10)
            if not r.json().get("ok"):
                basarili = False
        except Exception:
            basarili = False
    return basarili
