#!/usr/bin/env python3
"""
scripts/sozluk_kart_dogrula.py — Sözlük kartı taslaklarını arşive girmeden önce denetler.

    python scripts/sozluk_kart_dogrula.py data/sozluk_taslak/A07.yaml [diğer.yaml ...]
    python scripts/sozluk_kart_dogrula.py taslak.yaml --json
    python scripts/sozluk_kart_dogrula.py taslak.yaml --hakem        # YALNIZ orkestratör: ikinci model (kota harcar)
    python scripts/sozluk_kart_dogrula.py taslak.yaml --kanunsuz     # ağsız yapı/çizim denetimi; birleştirme için GEÇERSİZ

Katmanlar (hepsi geçmeli): yapı → tekrar (arşiv + diğer taslaklar + dosya içi) → kanun (atıf okunabilir, dayanak alıntısı
birebir, kartta geçen sayılar maddede) → yayın kapısı (uyarısız) → iki ölçüde çizim (taşma yok). Ayrıca cümle başına
sözcük kökü örtüşmesi İPUCU olarak yazılır (hüküm değildir). Ayrıntı: src/sozluk_dogrulama.py, SOZLUK-KART-URETIMI.md.

Çıkış kodu: 0 = bütün kartlar temiz, 1 = en az bir kartta sorun var, 2 = dosya okunamadı.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# DB'YE DOKUNMA (MEMORY §6.4/§7.3): bu araç paralel ajanlarca depodaki çalışma kopyasında koşar; `src.db` içe
# aktarılırken şemayı göç ettirir ve WAL açar. Test modu DB'yi geçici kopyaya yönlendirir ve .env'i yüklemez.
# `--hakem` (ikinci model) .env anahtarı ister: yalnız orkestratör, tek süreç, bilerek gerçek ortamda çalışır.
if "--hakem" not in sys.argv:
    os.environ.setdefault("POSTEDM_TEST_MODU", "1")

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import sozluk_dogrulama as sd  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Sözlük kartı taslaklarını denetle")
    ap.add_argument("taslaklar", nargs="+", help="taslak YAML dosyaları (kartlar: listesi)")
    ap.add_argument("--json", action="store_true", help="makine okunur çıktı")
    ap.add_argument("--hakem", action="store_true", help="ikinci model anlam kayması denetimi (yalnız orkestratör)")
    ap.add_argument("--kanunsuz", action="store_true", help="kanun metnine bakma (ağ yok); sonuç birleştirme için geçersiz")
    ap.add_argument("--cizimsiz", action="store_true", help="çizimi atla (hızlı yapı/kanun denetimi)")
    args = ap.parse_args(argv)

    try:
        sonuc = sd.taslaklari_denetle(args.taslaklar, kanun=not args.kanunsuz, ciz=not args.cizimsiz, hakem=args.hakem)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2

    raporlar = [r for _yol, satirlar in sonuc for _kart, r in satirlar]
    if args.json:
        print(json.dumps([{"dosya": str(yol), "kartlar": [r.sozluk() for _k, r in satirlar]} for yol, satirlar in sonuc],
                         ensure_ascii=False, indent=1))
    else:
        for yol, satirlar in sonuc:
            print(f"== {yol} · {len(satirlar)} kart")
            for _kart, r in satirlar:
                print(f"  {'✓' if r.temiz else '✗'} {r.terim}" + (f"  [inceleme: {r.inceleme}]" if r.inceleme else ""))
                for s in r.sorunlar:
                    print(f"      ✗ {s}")
                for i in r.ipuclari:
                    print(f"      · ipucu: {i}")
        temiz = sum(1 for r in raporlar if r.temiz)
        print(f"\nToplam {len(raporlar)} kart · {temiz} temiz · {len(raporlar) - temiz} sorunlu")
        if args.kanunsuz:
            print("⚠️ --kanunsuz: kanun/kapı denetimi yapılmadı; bu sonuçla birleştirme YAPILMAZ.")
    return 0 if all(r.temiz for r in raporlar) else 1


if __name__ == "__main__":
    raise SystemExit(main())
