#!/usr/bin/env python3
"""
scripts/kontakt_foy.py — Stres Testi Çıktılarını Tek Föyde Toplar

Piksel denetimi taşmayı yakalar ama "çirkin mi" sorusunu yanıtlamaz. Bu betik
üretilen slaytları küçültüp tek görselde yan yana dizer; gözle tarama için.

    python scripts/kontakt_foy.py --olcu besleme --vaka on_kat_uzun
    python scripts/kontakt_foy.py --desen "story_*"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from PIL import Image, ImageDraw, ImageFont

KAYNAK = KOK / "data/output/stres"
KUCUK_EN = 260
BOSLUK = 14
ETIKET_H = 26


def main() -> int:
    ap = argparse.ArgumentParser(description="Stres çıktılarından kontakt föyü")
    ap.add_argument("--desen", default="*.jpg", help="Dosya deseni (örn: 'besleme_on_kat_uzun_*')")
    ap.add_argument("--olcu", default=None, help="besleme | story")
    ap.add_argument("--vaka", default=None, help="Vaka adı")
    ap.add_argument("--sutun", type=int, default=7, help="Satır başına slayt")
    ap.add_argument("--cikti", default=None)
    args = ap.parse_args()

    desen = args.desen
    if args.olcu or args.vaka:
        desen = f"{args.olcu or '*'}_{args.vaka or '*'}*.jpg"

    dosyalar = sorted(KAYNAK.glob(desen))
    if not dosyalar:
        print(f"Eşleşen dosya yok: {KAYNAK}/{desen}")
        return 1

    kucukler = []
    for d in dosyalar:
        img = Image.open(d).convert("RGB")
        oran = KUCUK_EN / img.width
        kucukler.append((d.stem, img.resize((KUCUK_EN, int(img.height * oran)), Image.Resampling.LANCZOS)))

    sutun = min(args.sutun, len(kucukler))
    satir = (len(kucukler) + sutun - 1) // sutun
    hucre_h = max(k.height for _, k in kucukler) + ETIKET_H

    foy = Image.new("RGB",
                    (sutun * KUCUK_EN + (sutun + 1) * BOSLUK,
                     satir * hucre_h + (satir + 1) * BOSLUK),
                    (24, 26, 32))
    draw = ImageDraw.Draw(foy)
    try:
        font = ImageFont.truetype(str(KOK / "assets/fonts/IBMPlexMono.ttf"), 13)
    except Exception:
        font = ImageFont.load_default()

    for i, (ad, k) in enumerate(kucukler):
        sx, sy = i % sutun, i // sutun
        x = BOSLUK + sx * (KUCUK_EN + BOSLUK)
        y = BOSLUK + sy * (hucre_h + BOSLUK)
        foy.paste(k, (x, y))
        # Kırpılmasın diye etiketin sonundan değil başından kes; ayırt edici kısım sonda
        etiket = ad if len(ad) <= 34 else "…" + ad[-33:]
        draw.text((x + 2, y + k.height + 6), etiket, font=font, fill=(168, 174, 186))

    cikti = Path(args.cikti) if args.cikti else KOK / f"data/output/kontakt_{desen.replace('*', 'X').replace('.jpg', '')}.jpg"
    cikti.parent.mkdir(parents=True, exist_ok=True)
    foy.save(cikti, "JPEG", quality=88)
    print(f"{len(kucukler)} slayt → {cikti}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
