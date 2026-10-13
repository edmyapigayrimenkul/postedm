"""Instagram besleme gönderisi: carousel (tek sayfa ise tekil resim). Reels seçiliyse bu kanal çalışmaz (bkz. reels.py)."""

from __future__ import annotations

import logging

from ... import instagram
from ..baglam import YayinBaglami
from ..ilerleme import Ilerleme
from ..sonuc import HATA, YAYINDA, KanalSonucu

log = logging.getLogger(__name__)

KANAL = "instagram"


def yayinla(b: YayinBaglami, ilerleme: Ilerleme) -> KanalSonucu:
    ilerleme.bildir(KANAL, "⏳ Yükleniyor...")
    s = KanalSonucu(KANAL, etiket="❌ Hata")
    try:
        gorseller_ig = b.public_urller
        if b.tek_sayfa:
            p_id = instagram.tekil_gorsel_yayinla(gorseller_ig[0], b.caption)
            etiket = "Instagram (Tekil Resim)"
        else:
            p_id = instagram.carousel_yayinla(gorseller_ig, b.caption)
            etiket = "Instagram (Carousel)"
        s.kimlik = p_id
        if p_id:
            s.ekle(f"📸 <b>{etiket}:</b> Paylaşıldı ✓", YAYINDA)
        else:
            s.ekle("📸 <b>Instagram:</b> Hata oluştu ✗", HATA)
    except Exception as yayin_hatasi:  # noqa: BLE001
        log.warning("Instagram yayını hatası: %s", yayin_hatasi)
        s.ekle(f"📸 <b>Instagram:</b> Hata ({yayin_hatasi}) ✗", HATA)
    if s.kimlik:
        s.etiket = "✅ Yayında"
    ilerleme.bildir(KANAL, s.etiket, increment=True)
    return s
