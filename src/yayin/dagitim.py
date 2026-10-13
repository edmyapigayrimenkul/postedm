"""
yayin/dagitim.py — Paralel dağıtım motoru: seçilen kanalların işçilerini aynı anda çalıştırır, sonuçlarını toplar.

Eski motor işçilere ortak bir liste ve `nonlocal` değişkenler veriyordu; bir işçi yakalanmamış hata atarsa future sessizce yutuluyor,
kanal raporda hiç görünmüyordu. Artık her işçi kendi `KanalSonucu`sunu döndürür; beklenmedik hata da rapora "Hata (...) ✗" satırı olur.
"""

from __future__ import annotations

import concurrent.futures
import logging
from typing import List

from .baglam import YayinBaglami
from .ilerleme import Ilerleme
from .kanallar import KANALLAR
from .sonuc import HATA, DagitimSonucu, KanalSonucu

log = logging.getLogger(__name__)

AZAMI_ISCI = 6


def dagit(b: YayinBaglami, kanallar: List[str], ilerleme: Ilerleme) -> DagitimSonucu:
    sonuc = DagitimSonucu()
    gorevler = [(k, KANALLAR[k]) for k in kanallar if k in KANALLAR]
    if not gorevler:
        return sonuc

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(AZAMI_ISCI, len(gorevler))) as executor:
        vadeler = [(k, executor.submit(fn, b, ilerleme)) for k, fn in gorevler]
        concurrent.futures.wait([v for _, v in vadeler])

    for kanal, vade in vadeler:
        try:
            kanal_sonucu = vade.result()
        except Exception as e:  # noqa: BLE001 — işçi kendi hatasını yakalayamadıysa kanal raporda yine görünsün
            log.exception("%s işçisi beklenmedik hata verdi", kanal)
            kanal_sonucu = KanalSonucu(kanal, etiket="❌ Hata")
            kanal_sonucu.ekle(f"⚠️ <b>{kanal}:</b> Hata ({e}) ✗", HATA)
            ilerleme.bildir(kanal, "❌ Hata", increment=True)
        sonuc.kanallar[kanal] = kanal_sonucu
    return sonuc
