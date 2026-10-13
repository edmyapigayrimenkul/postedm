"""
src/telegram/akislar/havuz.py — Havuza alınmış hazır içeriği yeniden onaya sunma (model çağrılmaz).

Katman 4 (akış). Onaylanmayan içerik 1 günde havuza alınır (`scripts/hatirlat.py`, `db.durum_havuza_al`); bu modül aynı formatın bir sonraki
turunda onu yeniden sunar. Kullanıcı kararı (2026-10-13): hazır içerik yeniden üretilmez, başka bir gün tekrar önerilir.
"""

from __future__ import annotations

import logging
from typing import Optional

from ... import db, konu_bankasi
from . import onay

log = logging.getLogger(__name__)


def havuzdan_sun(format_turu: str) -> Optional[bool]:
    """Havuzdaki hazır içeriği (1 günde onaylanmayıp havuza alınmış) yeniden onaya sunar; MODEL ÇAĞRILMAZ. Havuz boşsa None.

    Aynı içerik numarasıyla (#id) yeni albüm + düğmeli kart düşer; slaytlar saklı veriden yeniden çizilir (Actions diski geçicidir).
    Yeniden sunum kapıdan geçemezse içerik arşive alınır, konusu iade edilir ve None döner: çağıran taze içerik üretir (gün boş geçmez)."""
    haber = konu_bankasi.havuzdaki_hazir_icerik(format_turu)
    if not haber:
        return None
    log.info("Havuzdaki hazır içerik #%s yeniden sunuluyor (%s); model çağrılmıyor.", haber["id"], format_turu)
    db.haber_guncelle(haber["id"], durum="yeni")
    sonuc = onay.haber_onayina_sun(haber["id"])
    if sonuc:
        return True
    log.warning("Havuzdaki içerik #%s yeniden sunulamadı; arşive alınıyor, taze içerik üretilecek.", haber["id"])
    db.durum_zaman_asimi_yap(haber["id"])
    konu_bankasi.konuyu_havuza_iade_et(haber["id"])
    return None
