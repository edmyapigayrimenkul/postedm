"""Facebook: Reels/sesli yayında video (Reels), diğer durumda standart gönderi (görsel albümü)."""

from __future__ import annotations

import logging

from ... import facebook, generate_text
from ..baglam import YayinBaglami
from ..ilerleme import Ilerleme
from ..sonuc import HATA, YAYINDA, KanalSonucu

log = logging.getLogger(__name__)


def yayinla(b: YayinBaglami, ilerleme: Ilerleme) -> KanalSonucu:
    kanal = "facebook_reels" if b.reels_modu else "facebook"
    ilerleme.bildir(kanal, "⏳ Yükleniyor...")
    s = KanalSonucu(kanal, etiket="❌ Hata")
    fb_caption = (b.detay.get("caption_facebook") if isinstance(b.detay, dict) else "") or b.caption
    fb_caption = generate_text.caption_zenginlestir(
        fb_caption,
        kategori_kodu=b.haber.get("kategori") if b.haber else None,
        platform="facebook",
        manset=b.baslik,
    )
    if b.reels_modu:
        if b.sesli_video_yolu and b.sesli_video_yolu.exists():
            try:
                f_id = facebook.video_yayinla(b.sesli_video_yolu, description=fb_caption)
                s.kimlik = f_id
                if f_id:
                    s.ekle("📘 <b>Facebook (Reels):</b> Paylaşıldı ✓", YAYINDA)
                else:
                    s.ekle("📘 <b>Facebook Reels:</b> Hata oluştu ✗", HATA)
            except Exception as fe:  # noqa: BLE001
                log.warning("Facebook Reels yayını hatası: %s", fe)
                s.ekle(f"📘 <b>Facebook Reels:</b> Hata ({fe}) ✗", HATA)
        else:
            s.ekle("📘 <b>Facebook Reels:</b> Dikey video üretilemedi ✗", HATA)
    else:
        try:
            f_id = facebook.paylas(fb_caption, b.public_urller)
            s.kimlik = f_id
            if f_id:
                s.ekle("📘 <b>Facebook (Standart Gönderi):</b> Paylaşıldı ✓", YAYINDA)
            else:
                s.ekle("📘 <b>Facebook:</b> Hata oluştu ✗", HATA)
        except Exception as fe:  # noqa: BLE001
            log.warning("Facebook standart paylaşım hatası: %s", fe)
            s.ekle(f"📘 <b>Facebook:</b> Hata ({fe}) ✗", HATA)
    if s.kimlik:
        s.etiket = "✅ Yayında"
    ilerleme.bildir(kanal, s.etiket, increment=True)
    return s
