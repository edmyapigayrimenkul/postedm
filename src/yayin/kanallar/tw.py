"""X (Twitter). ⚠️ `hedef.kanal_listesi` bu kanalı HİÇ seçmez: eski yayinla.py'de de `hedef_kanallar` listesine twitter eklenmiyordu
(işçi yazılmış, kayıt sözlüğünde "twitter"/"x" adıyla duruyor ama çağıran yok). Davranış korunuyor; açmak kararı ayrı."""

from __future__ import annotations

import logging

from ... import twitter
from ..baglam import YayinBaglami
from ..ilerleme import Ilerleme
from ..sonuc import HATA, YAYINDA, KanalSonucu

log = logging.getLogger(__name__)

KANAL = "twitter"


def yayinla(b: YayinBaglami, ilerleme: Ilerleme) -> KanalSonucu:
    ilerleme.bildir(KANAL, "⏳ Yükleniyor...")
    s = KanalSonucu(KANAL, etiket="❌ Hata")
    if not twitter.kullanilabilir_mi():
        s.ekle("🐦 <b>X (Twitter):</b> Yapılandırılmamış (API anahtarları eksik) ✗", HATA)
        ilerleme.bildir(KANAL, s.etiket, increment=True)
        return s

    try:
        tw_haberler = [b.haber] if b.haber else [{"baslik_orj": b.baslik, "ig_baslik": b.baslik, "slayt_ozet": b.caption, "ig_caption": b.caption}]
        ayarlar: dict = {}
        if len(tw_haberler) > 1 or (b.public_urller and len(b.public_urller) > 1):
            tw_id, tw_adet = twitter.zincir_yayinla(tw_haberler, b.public_urller, ayarlar)
            s.kimlik = tw_id
            if tw_id:
                s.ekle(f"🐦 <b>X (Twitter):</b> {tw_adet} tweet zinciri paylaşıldı ✓", YAYINDA)
            else:
                s.ekle("🐦 <b>X (Twitter):</b> Hata oluştu ✗", HATA)
        else:
            tw_id = twitter.tekil_yayinla(tw_haberler[0], b.public_urller, ayarlar)
            s.kimlik = tw_id
            if tw_id:
                s.ekle("🐦 <b>X (Twitter):</b> Paylaşıldı ✓", YAYINDA)
            else:
                s.ekle("🐦 <b>X (Twitter):</b> Hata oluştu ✗", HATA)
    except Exception as te:  # noqa: BLE001
        log.warning("Twitter paylaşım hatası: %s", te)
        s.ekle(f"🐦 <b>X (Twitter):</b> Hata ({te}) ✗", HATA)
    if s.kimlik:
        s.etiket = "✅ Yayında"
    ilerleme.bildir(KANAL, s.etiket, increment=True)
    return s
