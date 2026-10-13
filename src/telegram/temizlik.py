"""
src/telegram/temizlik.py — Eski onay kartlarını / albüm mesajlarını Telegram grubundan siler.

Katman 3 (etki). Hangi mesajların silineceğini DB (`onay_istekleri`) söyler; silmeyi `istemci.mesaji_sil` yapar.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .. import db
from . import istemci

log = logging.getLogger(__name__)


def icerik_onceki_mesajlarini_temizle(tur: str, referans_id: Any, haric_mesaj_id: Optional[int] = None) -> int:
    """
    Aynı içerik için daha önce Telegram grubuna gönderilmiş olan onay kartı
    ve hatırlatma mesajlarını siler; böylece chatte mükerrer kartlar ve kaos oluşmaz.
    """
    try:
        eski_idler = db.onay_mesajlarini_getir(tur, str(referans_id))
        silinen = 0
        for mid in eski_idler:
            if haric_mesaj_id and mid == haric_mesaj_id:
                continue
            try:
                if istemci.mesaji_sil(mid):
                    silinen += 1
                db.onay_mesaj_silindi_isaretle(mid)
            except Exception as e:
                log.warning("Mesaj #%d silinemedi: %s", mid, e)
        if silinen > 0:
            log.info("İçerik (%s #%s) için önceki %d adet mesaj Telegram'dan temizlendi.", tur, referans_id, silinen)
        return silinen
    except Exception as e:
        log.warning("Önceki mesajlar temizlenirken hata: %s", e)
        return 0


def son_mesajlari_sil(adet: int = 1) -> int:
    """
    Son onay isteklerine ait tüm Telegram mesajlarını (albüm slaytları ve onay kartları) siler.
    /sil komutu veya bot yönetim aksiyonu ile tetiklenir.
    """
    try:
        mids = db.son_onay_istegi_mesajlarini_getir(adet=adet)
        silinen = 0
        for mid in mids:
            try:
                if istemci.mesaji_sil(mid):
                    silinen += 1
                db.onay_mesaj_silindi_isaretle(mid)
            except Exception as e:
                log.warning("Mesaj #%d silinemedi: %s", mid, e)
        if silinen > 0:
            log.info("Son onay isteklerinden %d adet Telegram mesajı silindi.", silinen)
        return silinen
    except Exception as e:
        log.warning("Son mesajlar silinirken hata: %s", e)
        return 0
