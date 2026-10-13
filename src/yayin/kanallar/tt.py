"""TikTok: Reels/sesli yayında video, diğer durumda fotoğraf carousel'i (tek sayfa ise tekil resim)."""

from __future__ import annotations

import logging

from ... import tiktok
from ..baglam import YayinBaglami
from ..ilerleme import Ilerleme
from ..sonuc import BILGI, HATA, YAYINDA, KanalSonucu

log = logging.getLogger(__name__)

KANAL = "tiktok"
TASLAK_VIDEO = "🎵 <b>TikTok (Video):</b> Taslak Olarak Yüklendi (Uygulamadan Paylaşılacak) 📥"
TASLAK_FOTO = "🎵 <b>TikTok:</b> Taslak Olarak Yüklendi (Uygulamadan Paylaşılacak) 📥"


def yayinla(b: YayinBaglami, ilerleme: Ilerleme) -> KanalSonucu:
    ilerleme.bildir(KANAL, "⏳ Yükleniyor...")
    s = KanalSonucu(KANAL, etiket="❌ Hata")
    res: dict = {}
    if b.reels_modu or b.ses_modu:
        tt_video = b.v_yolu if (b.v_yolu and b.v_yolu.exists()) else b.sesli_video_yolu
        if tt_video and tt_video.exists():
            try:
                res = tiktok.video_yukle(tt_video, baslik=b.baslik)
                if res.get("durum"):
                    if res.get("taslak_mi"):
                        s.ekle(TASLAK_VIDEO, BILGI)
                    else:
                        s.ekle("🎵 <b>TikTok (Video):</b> Paylaşıldı ✓", YAYINDA)
                else:
                    s.ekle(f"🎵 <b>TikTok:</b> {res.get('hata') or 'Hata'} ✗", HATA)
            except Exception as tt_e:  # noqa: BLE001
                log.warning("TikTok video yükleme hatası: %s", tt_e)
                s.ekle(f"🎵 <b>TikTok:</b> Hata ({tt_e}) ✗", HATA)
        else:
            s.ekle("🎵 <b>TikTok:</b> Video üretilemedi ✗", HATA)
    else:
        try:
            res = tiktok.foto_yayinla(b.public_urller, baslik=b.baslik, hazir_video_yolu=b.v_yolu)
            if res.get("durum"):
                if res.get("taslak_mi"):
                    s.ekle(TASLAK_FOTO, BILGI)
                else:
                    tur_etiket = "Tekil Resim" if b.tek_sayfa else "Carousel"
                    s.ekle(f"🎵 <b>TikTok ({tur_etiket}):</b> Paylaşıldı ✓", YAYINDA)
            else:
                s.ekle(f"🎵 <b>TikTok:</b> {res.get('hata') or 'Hata'} ✗", HATA)
        except Exception as tt_e:  # noqa: BLE001
            log.warning("TikTok fotoğraf paylaşım hatası: %s", tt_e)
            s.ekle(f"🎵 <b>TikTok:</b> Hata ({tt_e}) ✗", HATA)

    s.ham = res if isinstance(res, dict) else {}
    if s.ham.get("durum"):
        s.etiket = "📥 Taslak Yüklendi" if s.ham.get("taslak_mi") else "✅ Yayında"
    ilerleme.bildir(KANAL, s.etiket, increment=True)
    return s
