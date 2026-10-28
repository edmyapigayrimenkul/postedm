"""
src/cizim/tuval.py — Tuval bağlam yöneticisi, dinamik yerleşim koordinatları ve zemin üretimi.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Tuple

from PIL import Image

from . import sabitler, tipografi

_tuval_lock = threading.RLock()


@contextmanager
def tuval(olcu: Any) -> Iterator[Tuple[int, int]]:
    """Çizim boyutunu geçici olarak değiştirir."""
    if isinstance(olcu, str):
        if olcu not in sabitler.TUVAL_OLCULERI:
            raise ValueError(f"Bilinmeyen tuval ölçüsü: {olcu!r}. Seçenekler: {sorted(sabitler.TUVAL_OLCULERI)}")
        en, boy = sabitler.TUVAL_OLCULERI[olcu]
    else:
        en, boy = olcu
        if not (320 <= int(en) <= 4096 and 320 <= int(boy) <= 4096):
            raise ValueError(f"Tuval ölçüsü makul aralıkta değil: {en}x{boy}")
        en, boy = int(en), int(boy)

    with _tuval_lock:
        import sys
        onceki = (sabitler.GENISLIK, sabitler.YUKSEKLIK)
        
        def _guncelle(w: int, h: int):
            sabitler.GENISLIK, sabitler.YUKSEKLIK = w, h
            for mod_name, mod in list(sys.modules.items()):
                if mod and (mod_name.startswith("src.cizim") or mod_name in ("src.make_image",)):
                    if hasattr(mod, "GENISLIK"):
                        try:
                            setattr(mod, "GENISLIK", w)
                        except Exception:
                            pass
                    if hasattr(mod, "YUKSEKLIK"):
                        try:
                            setattr(mod, "YUKSEKLIK", h)
                        except Exception:
                            pass

        _guncelle(en, boy)
        try:
            yield (en, boy)
        finally:
            _guncelle(onceki[0], onceki[1])


def _yerlesim() -> Dict[str, int]:
    """Geçerli tuval boyutundan yerleşim sınırlarını türetir."""
    w, h = sabitler.GENISLIK, sabitler.YUKSEKLIK
    if h >= 1700:
        kenar = max(48, round(w * 0.072))
        kronik_ust, ust, icerik_alt_payi, bar_payi = 300, 400, 370, 350
    elif w > h:
        kenar = max(60, round(w * 0.055))
        kronik_ust, ust, icerik_alt_payi, bar_payi = 50, 175, 120, 85
    else:
        kenar = max(48, round(w * 0.072))
        kronik_ust, ust, icerik_alt_payi, bar_payi = 62, 212, 135, 100

    alt_bar = h - bar_payi
    icerik_alt = h - icerik_alt_payi
    return {
        "kenar": kenar,
        "kronik_ust": kronik_ust,
        "ust": ust,
        "alt": icerik_alt,
        "alt_bar": alt_bar,
        "taban": icerik_alt - (40 if h >= 1700 else 95),
    }


def _rozet_kirp(metin: Any, azami: int) -> str:
    """Rozet metnini kelime sınırında kısaltır."""
    temiz = tipografi._temizle_tipografi("" if metin is None else str(metin))
    if len(temiz) <= azami:
        return temiz
    kesik = temiz[:azami - 1]
    bosluk = kesik.rfind(" ")
    if bosluk >= azami // 2:
        kesik = kesik[:bosluk]
    return kesik.rstrip(" ,.;:/-") + "…"


def _zemin_uret(zemin_adi: str = "murekkep", olcu: str = "besleme") -> Image.Image:
    """Belirtilen ölçü ve zemin temasına göre boş RGB tuval üretir."""
    p = sabitler.ZEMINLER.get(zemin_adi, sabitler.ZEMINLER["murekkep"])
    w, h = sabitler.TUVAL_OLCULERI.get(olcu, (sabitler.GENISLIK, sabitler.YUKSEKLIK))
    return Image.new("RGB", (w, h), p["zemin"])


def _sayfa_etiketi(veri: Dict[str, Any], sira: int) -> str:
    """Slayt sayacını gerçek slayt sayısından üretir.
    Dikey video (Reels/Shorts/Story) formatında 'KAYDIRIN' veya sayaç yazılmaz.
    """
    olcu = str(veri.get("olcu") or "").lower()
    if sabitler.YUKSEKLIK >= 1700 or olcu in ("story", "reels", "shorts", "dikey") or veri.get("_video_modu"):
        return ""
    toplam = veri.get("_toplam_slayt") or 4
    etiket = f"{str(sira).zfill(2)} / {str(toplam).zfill(2)}"
    return etiket if sira >= toplam else f"{etiket}  ›  KAYDIRIN"

