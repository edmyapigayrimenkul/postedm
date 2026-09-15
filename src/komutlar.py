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

    # Hızlı İçerik Üretimi
    "yeni",
    "uret",
    "sozluk",
    "dogrusu",
    "vaka",
    "soru",

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
    {"command": "yardim", "description": "❓ Bot komutları ve kullanım kılavuzu"},

    # ── ✍️ OTORİTE İÇERİK ÜRETİMİ ─────────────────────────────────────
    {"command": "yeni", "description": "✍️ Sıradaki konuyu hemen üretip onaya sun"},
    {"command": "sozluk", "description": "📖 EDM Gayrimenkul Sözlüğü postu üret"},
    {"command": "dogrusu", "description": "⚖️ Nedir Doğrusu? (Efsane vs Gerçek) üret"},
    {"command": "vaka", "description": "📂 Hukuki Vaka Analizi (2 Slayt Carousel) üret"},
    {"command": "soru", "description": "❓ Net Cevap Rehberi (Soru & Hüküm) üret"},

    # ── ⏸️ AKIŞ KONTROLÜ ─────────────────────────────────────────────
    {"command": "durdur", "description": "⏸️ Otomatik paylaşımları duraklat"},
    {"command": "devam", "description": "▶️ Duraklatılmış botu başlat"},
]


def mesajsiz_komut_mu(komut: str) -> bool:
    """Verilen komutun serbest bir komut olup olmadığını denetler."""
    if not komut:
        return False
    temiz = komut.strip().lstrip("/").lower()
    kok = temiz.split(":", 1)[0].strip()
    return kok in MESAJSIZ_KOMUTLAR or temiz in MESAJSIZ_KOMUTLAR
