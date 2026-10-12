"""
gizlilik.py — Hata metinlerinden gizli değerleri ayıklar.

NİYE VAR (2026-10-12): hata kayıtları `data/edm.db`'ye yazılıyor ve DB git'e gidiyor (MEMORY §7.4: gizli anahtar
DB'ye yazılmaz). `requests` istisnaları isteğin tam URL'sini taşır; Graph API çağrılarında
`...?access_token=EAAB...` sorgu parametresi hata metnine girer. Aynı şey Telegram bot adresi
(`/bot123:ABC.../sendMessage`), Gemini anahtarı (`x-goog-api-key`) ve `Authorization: Bearer ...` için geçerli.

Maskeleme kayıttan ÖNCE yapılır; kayıtlı metinden gizli değer geri getirilemez.
"""

from __future__ import annotations

import re

_MASKE = "***"

# anahtar=değer / "anahtar": "değer" biçimleri (sorgu parametresi, JSON, başlık)
_ANAHTAR_ADLARI = (
    r"access_token|refresh_token|id_token|client_secret|client_key|api[_-]?key|x-goog-api-key|xi-api-key|"
    r"secret|password|passwd|authorization|token|signature|sig"
)
_ANAHTAR_DEGER = re.compile(
    rf"""(?P<oncesi>(?<![A-Za-z])["']?(?:{_ANAHTAR_ADLARI})["']?\s*[:=]\s*["']?(?:Bearer\s+)?)(?P<deger>[^"'&\s,;}}\]]+)""",
    re.IGNORECASE,
)

# Biçimi tanınan jetonlar (anahtar adı olmasa da yakalanır)
_BICIMLER = (
    (re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}"), f"Bearer {_MASKE}"),
    (re.compile(r"bot\d{6,}:[A-Za-z0-9_-]{20,}"), f"bot{_MASKE}"),            # Telegram bot adresi
    (re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}"), f"tg:{_MASKE}"),            # Telegram bot jetonu (çıplak)
    (re.compile(r"AIza[0-9A-Za-z_-]{20,}"), f"AIza{_MASKE}"),                  # Google API anahtarı
    (re.compile(r"\bEAA[A-Za-z0-9]{20,}"), f"EAA{_MASKE}"),                    # Meta (Graph) jetonu
    (re.compile(r"\bTH[A-Za-z0-9]{2}[A-Za-z0-9_-]{40,}"), f"TH{_MASKE}"),      # Threads uzun ömürlü jeton
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), f"gh_{_MASKE}"),             # GitHub jetonları
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), f"github_pat_{_MASKE}"),
    (re.compile(r"\bsk_[A-Za-z0-9]{20,}"), f"sk_{_MASKE}"),                    # ElevenLabs
    (re.compile(r"\bya29\.[A-Za-z0-9._-]{20,}"), f"ya29.{_MASKE}"),            # Google OAuth erişim jetonu
    (re.compile(r"\b1//[A-Za-z0-9._-]{20,}"), f"1//{_MASKE}"),                 # Google yenileme jetonu
    (re.compile(r"\bact\.[A-Za-z0-9._-]{20,}"), f"act.{_MASKE}"),              # TikTok erişim jetonu
    (re.compile(r"\brft\.[A-Za-z0-9._-]{20,}"), f"rft.{_MASKE}"),              # TikTok yenileme jetonu
)


def maskele(metin: object) -> str:
    """Metindeki bilinen gizli değer biçimlerini `***` ile değiştirir. Metin olmayan girdiyi `str`'e çevirir."""
    if metin is None:
        return ""
    sonuc = str(metin)
    sonuc = _ANAHTAR_DEGER.sub(lambda m: m.group("oncesi") + _MASKE, sonuc)
    for desen, yerine in _BICIMLER:
        sonuc = desen.sub(yerine, sonuc)
    return sonuc
