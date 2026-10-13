"""
yayin/ilerleme.py — Canlı yayın durumu: onay kartı üzerinde "kanal kanal ilerleme" göstergesi.

Kanallar paralel çalışır; güncellemeler 1,2 sn'de bir sınırlanır (Telegram düzenleme sınırı), tamamlanma güncellemesi her zaman gider.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Iterable, Optional

from .. import telegram_bot

log = logging.getLogger(__name__)

SINIR_SN = 1.2


class Ilerleme:
    def __init__(self, hedef_kanallar: Iterable[str], mesaj_id: Optional[int], baslik: object):
        kanallar = list(hedef_kanallar)
        self.mesaj_id = mesaj_id
        self.baslik = baslik
        self.toplam_adim = max(1, len(kanallar))
        self.durum_haritasi: Dict[str, str] = {k: "⏱️ Sırada" for k in kanallar}
        self.tamamlanan = 0
        self.son_edit = 0.0
        self.baslangic_ts = time.time()
        self._kilit = threading.Lock()
        self._kanallar = kanallar

    def gecen_sure(self) -> float:
        return (time.time() - self.baslangic_ts) if self.baslangic_ts > 0 else 0.0

    def baslat(self) -> None:
        """Dağıtım başlamadan 0/N durumunu gösterir."""
        if not (self.mesaj_id and self._kanallar):
            return
        try:
            telegram_bot.canli_yayin_durumu_guncelle(
                mesaj_id=self.mesaj_id,
                baslik=self.baslik,
                adim=0,
                toplam_adim=self.toplam_adim,
                durum_haritasi=self.durum_haritasi,
                baslangic_ts=self.baslangic_ts,
            )
        except Exception as e_bas:  # noqa: BLE001 — gösterge yayını durdurmaz
            log.debug("Canlı yayın başlangıç bildirimi gönderilemedi: %s", e_bas)

    def bildir(self, kanal: str, durum: str, increment: bool = False) -> None:
        with self._kilit:
            if kanal in self.durum_haritasi:
                self.durum_haritasi[kanal] = durum
            if increment:
                self.tamamlanan = min(self.toplam_adim, self.tamamlanan + 1)
            ad = self.tamamlanan
            snap = dict(self.durum_haritasi)

        if not self.mesaj_id:
            return

        simdi = time.time()
        if (ad < self.toplam_adim) and (simdi - self.son_edit < SINIR_SN):
            return

        self.son_edit = simdi
        try:
            telegram_bot.canli_yayin_durumu_guncelle(
                mesaj_id=self.mesaj_id,
                baslik=self.baslik,
                adim=ad,
                toplam_adim=self.toplam_adim,
                durum_haritasi=snap,
                baslangic_ts=self.baslangic_ts,
            )
        except Exception as de:  # noqa: BLE001
            log.debug("Canlı durum güncelleme hatası: %s", de)
