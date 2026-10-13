"""YouTube Shorts: her zaman dikey video (fon müzikli ya da seslendirmeli)."""

from __future__ import annotations

import logging

from ... import youtube
from ..baglam import YayinBaglami
from ..ilerleme import Ilerleme
from ..sonuc import HATA, YAYINDA, KanalSonucu

log = logging.getLogger(__name__)

KANAL = "youtube"


def yayinla(b: YayinBaglami, ilerleme: Ilerleme) -> KanalSonucu:
    ilerleme.bildir(KANAL, "⏳ Yükleniyor...")
    s = KanalSonucu(KANAL, etiket="❌ Hata")
    if b.sesli_video_yolu and b.sesli_video_yolu.exists():
        try:
            res = youtube.shorts_yukle(b.sesli_video_yolu, baslik=b.baslik, aciklama=b.caption)
            s.ham = res
            if res.get("durum"):
                s.ekle(f"▶️ <b>YouTube Shorts:</b> <a href='{res.get('url')}'>İzle</a> ✓", YAYINDA)
            else:
                s.ekle(f"▶️ <b>YouTube Shorts:</b> {res.get('hata') or 'Hata oluştu'} ✗", HATA)
        except Exception as yayin_hatasi:  # noqa: BLE001
            log.warning("YouTube Shorts yayını hatası: %s", yayin_hatasi)
            s.ekle(f"▶️ <b>YouTube Shorts:</b> Hata ({yayin_hatasi}) ✗", HATA)
    else:
        s.ekle("▶️ <b>YouTube Shorts:</b> Dikey video üretilemedi ✗", HATA)
    if s.ham.get("durum"):
        s.etiket = "✅ Yayında"
    ilerleme.bildir(KANAL, s.etiket, increment=True)
    return s
