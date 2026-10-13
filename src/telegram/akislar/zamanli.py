"""
src/telegram/akislar/zamanli.py — Zamanlanmış slotların "bugün çalıştı mı" korumasının yardımcıları (TR günü, slot anahtarı).

Katman 0-1: yalnız `db.ayar_*` okur/yazar. Cloudflare cron ile GitHub yedek cron'u aynı slotu iki kez üretmesin diye `hazirla.py` kullanır.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from ... import db

log = logging.getLogger(__name__)


def _tr_bugun() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=3)).date().isoformat()


# Zamanlanmış günlük turu iki yerden tetiklenebilir: Cloudflare cron'u (asıl yol, dakikasında çalışır) ve GitHub cron'u
# (yedek; 6-10 saat gecikebiliyor). Aynı slot aynı Türkiye gününde ikinci kez ÜRETİLMEZ: aksi halde geç gelen GitHub
# koşusu ikinci içerik, ikinci konu tüketimi ve (sözlükte) onay kuyruğuna ikinci kart demek olurdu.
ZAMANLI_GUNLUK_SLOTLAR = ("bilgilendirici", "sozluk")


def _zamanli_slot_anahtari(slot: str) -> str:
    return f"zamanli_slot_son_gun:{slot}"


def zamanli_slot_bugun_yapildi(slot: str) -> bool:
    """Bu slotun zamanlanmış turu bugün (TR) zaten başarıyla çalıştı mı?"""
    if slot not in ZAMANLI_GUNLUK_SLOTLAR:
        return False
    return db.ayar_oku(_zamanli_slot_anahtari(slot)) == _tr_bugun()


def zamanli_slot_isaretle(slot: str) -> None:
    """Zamanlanmış turun bugün başarıyla çalıştığını kaydeder (başarısız tur işaretlenmez: yedek tetik yeniden dener)."""
    if slot in ZAMANLI_GUNLUK_SLOTLAR:
        db.ayar_yaz(_zamanli_slot_anahtari(slot), _tr_bugun())
