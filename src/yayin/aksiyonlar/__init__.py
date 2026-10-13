"""
yayin/aksiyonlar — Yayın DEĞİL, içerik üzerinde yapılan işlemler (Telegram butonları): reddet, çöpe at, ertele, kaldır, elle paylaşım paketi,
"paylaştım", yenile, metin ve fotoğraf özelleştirme.

Her işlev kendi işini yapar; `isle` hangi işlemin hangi işleve gittiğini ve ortak sonu (WAL boşaltma) bilir.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ... import db
from ..baglam import Istek
from . import foto, taslak, yonetim


def isle(istek: Istek, mevcut: Optional[Dict[str, Any]]) -> bool:
    """İstek bir işlemse yapar ve True döner; yayın isteğiyse (kanal listesi) False."""
    hedef = istek.hedef
    if hedef in ("reddet", "iptal"):
        taslak.reddet(istek, mevcut)
    elif hedef == "cope_at":
        taslak.cope_at(istek, mevcut)
    elif hedef == "ertele":
        yonetim.ertele(istek)
    elif hedef in ("kaldir", "sil"):
        yonetim.kaldir(istek)
    elif hedef == "manuel_paket":
        yonetim.manuel_paket(istek)
    elif hedef in ("tamamla", "manuel_tamam"):
        yonetim.tamamla(istek)
    elif hedef == "yenile":
        taslak.yenile(istek)
    elif hedef in ("metin_ozetle", "metin_detaylandir", "metin_yenile"):
        taslak.metin(istek)
    elif hedef in ("foto_degistir", "foto_editoryal", "foto_gercek", "foto_stok", "foto_ai", "foto_ilk", "foto_adaylar") or hedef.startswith("gorsel_sec:"):
        foto.foto(istek)
    else:
        return False
    db.wal_bosalt()
    return True
