"""
src/ayar.py — Telegram Üzerinden Canlı Değiştirilebilen Bot ve Yayın Ayarları

Instabot mimarisiyle tam uyumlu ayar yönetim motoru:
SQLite ayarlar tablosunda saklanır, Telegram üzerinden tek tıkla açılıp kapatılır.
Güvenlik: Yalnızca DEGISTIRILEBILIR beyaz listesindeki anahtarlar güncellenebilir.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from . import db

log = logging.getLogger("ayar")

DEGISTIRILEBILIR: Dict[str, Tuple[str, List[Any]]] = {
    "oto_yayin": ("🌙 Otomatik Yayın", [True, False]),
    "reels_varsayilan": ("🎬 Varsayılan Reels Modu", [True, False]),
    "kanal_threads": ("🧵 Threads Paylaşımı", [True, False]),
    "kanal_fb": ("📘 Facebook Paylaşımı", [True, False]),
    "kanal_tiktok": ("🎵 TikTok Paylaşımı", [True, False]),
    "kanal_youtube": ("▶️ YouTube Shorts", [True, False]),
}

VARSAYILANLAR: Dict[str, Any] = {
    "oto_yayin": True,
    "reels_varsayilan": False,
    "kanal_threads": True,
    "kanal_fb": True,
    "kanal_tiktok": True,
    "kanal_youtube": True,
}


def _deger_donustur(ham: Any, tip_ornek: Any) -> Any:
    """Metin veya ham veriyi hedef türe (bool, int vb.) çevirir."""
    if isinstance(tip_ornek, bool):
        if isinstance(ham, bool):
            return ham
        s = str(ham).strip().lower()
        return s in ("true", "1", "evet", "acik", "aktif")
    if isinstance(tip_ornek, int):
        try:
            return int(ham)
        except (ValueError, TypeError):
            return tip_ornek
    return str(ham)


def ayar_oku(anahtar: str) -> Any:
    """Belirtilen ayarın güncel değerini döner."""
    if anahtar not in DEGISTIRILEBILIR:
        return None
    varsayilan = VARSAYILANLAR.get(anahtar)
    kayitli = db.ayar_oku(anahtar, varsayilan=None)
    if kayitli is None:
        return varsayilan
    return _deger_donustur(kayitli, varsayilan)


def ayar_kaydet(anahtar: str, deger: Any) -> bool:
    """Beyaz listedeki bir ayarı günceller."""
    if anahtar not in DEGISTIRILEBILIR:
        log.warning("İzin verilmeyen ayar anahtarı: %s", anahtar)
        return False
    varsayilan = VARSAYILANLAR.get(anahtar)
    donusturulmus = _deger_donustur(deger, varsayilan)
    db.ayar_yaz(anahtar, str(donusturulmus).lower() if isinstance(donusturulmus, bool) else str(donusturulmus))
    log.info("Ayar güncellendi: %s -> %s", anahtar, donusturulmus)
    return True


def ayar_menusu() -> Dict[str, Any]:
    """Telegram inline klavyesi için ayar toggle butonlarını üretir."""
    satirlar = []
    for anahtar, (etiket, secenekler) in DEGISTIRILEBILIR.items():
        su_an = ayar_oku(anahtar)
        # Boolean toggle: True ise False, False ise True yapacak callback
        if isinstance(su_an, bool):
            yeni = not su_an
            durum_ikon = "✅ AÇIK" if su_an else "⬜ KAPALI"
            satirlar.append([
                {
                    "text": f"{etiket}: {durum_ikon}",
                    "callback_data": f"ayarsec:{anahtar}:{str(yeni).lower()}",
                }
            ])
        else:
            # Liste seçenekleri
            butonlar = []
            for sec in secenekler:
                secili = (sec == su_an)
                ikon = "●" if secili else "○"
                butonlar.append({
                    "text": f"{ikon} {sec}",
                    "callback_data": f"ayarsec:{anahtar}:{sec}",
                })
            satirlar.append(butonlar)

    satirlar.append([{"text": "← Kontrol Paneline Dön", "callback_data": "panel"}])
    return {"inline_keyboard": satirlar}
