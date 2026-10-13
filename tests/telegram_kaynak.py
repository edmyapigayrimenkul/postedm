"""Kaynak metni okuyan testler için: Telegram kodu 2026-10-13'te src/telegram_bot.py'den src/telegram/ paketine bölündü."""

from __future__ import annotations

from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def telegram_kaynagi() -> str:
    """src/telegram/**/*.py birleşik kaynak metni (src/telegram_bot.py yalnız cephe; kod barındırmaz)."""
    return "\n".join(yol.read_text(encoding="utf-8") for yol in sorted((KOK / "src" / "telegram").rglob("*.py")))
