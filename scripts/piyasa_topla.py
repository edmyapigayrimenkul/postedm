#!/usr/bin/env python3
"""
scripts/piyasa_topla.py — Emlakjet bölge ortalamalarını toplar ve veritabanına yazar (S4 "Rakam & Bölge" kaynağı).

Aylık çalışır (.github/workflows/piyasa-verisi.yml). Bölge başına tek istek, istekler arası 2,5 sn; site erişimi
kapatırsa (403/429) zorlanmaz. Doğrulanamayan sayfa kaydedilmez; herhangi bir hata varsa çıkış kodu 1 olur ve iş
kırmızı biter (Telegram'a bildirim iş akışında). Ayrıntı ve sınırlar: src/piyasa_verisi.py.

    python scripts/piyasa_topla.py            # topla ve kaydet
    python scripts/piyasa_topla.py --kuru     # topla, ekrana yaz, KAYDETME
    python scripts/piyasa_topla.py --goster   # veritabanındaki son ölçümleri ve içerik bloklarını göster
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import piyasa_verisi as pv  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("piyasa_topla")


def _ozet(o: dict) -> str:
    kira = f", kira {pv.tl(o['m2_kira'], 2)} ₺/m²" if o.get("m2_kira") else ""
    degisim = f", yıllık {pv.yuzde(o['m2_degisim'])}" if o.get("m2_degisim") is not None else ""
    yeterli = sum(1 for m in o.get("mahalleler") or [] if (m.get("ilan_sayisi") or 0) >= pv.MAHALLE_ASGARI_ILAN)
    return (f"{o['tur']}/{o['bolge']}: {pv.tl(o['m2_fiyat'])} ₺/m²{degisim}{kira}; {pv.tl(o['ilan_sayisi'])} ilan; "
            f"{len(o.get('mahalleler') or [])} mahalle ({yeterli} tanesi ≥{pv.MAHALLE_ASGARI_ILAN} ilanlı)")


def goster() -> int:
    print(pv.durum_ozeti())
    for tur, bolge in pv.HEDEFLER:
        o = pv.son_olcum(tur, bolge)
        print(f"  {_ozet(o) if o else f'{tur}/{bolge}: ölçüm yok ya da bayat'}")
    for anahtar in pv.BLOKLAR:
        blok = pv.blok(anahtar)
        print(f"\n=== {anahtar}: {'HAZIR' if blok else 'KURULAMIYOR (veri yok, bayat ya da yetersiz)'}")
        if blok:
            print(blok)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Emlakjet bölge ortalamalarını topla")
    ap.add_argument("--kuru", action="store_true", help="kaydetmeden yalnız toplayıp özetle")
    ap.add_argument("--goster", action="store_true", help="kayıtlı son ölçümleri ve içerik bloklarını göster")
    args = ap.parse_args()

    if args.goster:
        return goster()

    olcumler, hatalar = pv.topla()
    for o in olcumler:
        log.info(_ozet(o))
    for h in hatalar:
        log.error("Toplanamadı: %s", h)

    if not olcumler:
        log.error("Hiçbir bölge toplanamadı; veritabanına dokunulmadı.")
        return 1
    if args.kuru:
        log.info("--kuru: %d ölçüm toplandı, kaydedilmedi.", len(olcumler))
        return 1 if hatalar else 0

    yazilan = pv.kaydet(olcumler)
    log.info("%d ölçüm (%d satır) kaydedildi. %s", len(olcumler), yazilan, pv.durum_ozeti())
    return 1 if hatalar else 0


if __name__ == "__main__":
    raise SystemExit(main())
