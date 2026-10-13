"""Kaynak metni okuyan testler için: yayın kodu 2026-10-13'te scripts/yayinla.py'den src/yayin/ paketine bölündü."""

from __future__ import annotations

from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def yayin_kaynagi() -> str:
    """scripts/yayinla.py + src/yayin/**/*.py birleşik kaynak metni."""
    parcalar = [(KOK / "scripts" / "yayinla.py").read_text(encoding="utf-8")]
    for yol in sorted((KOK / "src" / "yayin").rglob("*.py")):
        parcalar.append(yol.read_text(encoding="utf-8"))
    return "\n".join(parcalar)
