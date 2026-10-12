#!/usr/bin/env python3
"""
scripts/sozluk_kart_birlestir.py — Onaylı sözlük kartı taslaklarını arşive (data/sozluk_kartlari.yaml) ekler.

    python scripts/sozluk_kart_birlestir.py data/sozluk_taslak/A07.yaml --kuru     # ne ekleneceğini göster, yazma
    python scripts/sozluk_kart_birlestir.py data/sozluk_taslak/*.yaml              # ekle

Yalnız `inceleme: onay` ya da `inceleme: duzeltildi` olan VE denetimden (kanun + kapı + çizim dahil) yeniden temiz çıkan
kartlar eklenir; kod (SZ-035…) arşivdeki en büyük numaradan devam ederek atanır, tekrarlar atılır. Arşivin başlık
yorumlarına dokunulmaz (kartlar sona eklenir), yazım atomiktir ve ardından arşiv yeniden doğrulanır; tutmazsa eski
haline döner. Çıkış kodu: 0 = tamam (hiç kart eklenmemesi de tamam), 1 = yazım/doğrulama hatası, 2 = dosya okunamadı.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# DB'YE DOKUNMA (MEMORY §6.4/§7.3): `src.db` içe aktarılırken şemayı göç ettirir ve WAL açar; arşivi güncelleyen
# bu araç depo kopyasındaki data/edm.db'yi değiştirmemeli. Test modu DB'yi geçici kopyaya yönlendirir.
os.environ.setdefault("POSTEDM_TEST_MODU", "1")

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import sozluk_dogrulama as sd  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Onaylı sözlük kartı taslaklarını arşive ekle")
    ap.add_argument("taslaklar", nargs="+", help="taslak YAML dosyaları")
    ap.add_argument("--kuru", action="store_true", help="yazma; ne ekleneceğini göster")
    args = ap.parse_args(argv)

    try:
        rapor = sd.birlestir(args.taslaklar, kuru=args.kuru)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2

    for k in rapor.eklenen:
        print(f"  + {k['kod']}  {k['terim']}  ({k['mevzuat']})")
    for terim, neden in rapor.atlanan:
        print(f"  - ATLANDI {terim}: {neden}")
    if rapor.hata:
        print(f"✗ {rapor.hata}", file=sys.stderr)
        return 1
    if args.kuru:
        print(f"\n[KURU] {len(rapor.eklenen)} kart eklenecekti, {len(rapor.atlanan)} atlandı. Arşive yazılmadı.")
    else:
        print(f"\n{len(rapor.eklenen)} kart arşive eklendi, {len(rapor.atlanan)} atlandı.")
        if rapor.eklenen:
            print("Sonraki adım: python scripts/hazirla.py --durum  ·  python -m unittest tests.test_sozluk_arsivi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
