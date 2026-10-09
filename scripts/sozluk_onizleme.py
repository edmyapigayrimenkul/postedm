#!/usr/bin/env python3
"""
scripts/sozluk_onizleme.py — Sözlük kartlarını çizip kontak sayfalarına dizer (yayın ortamında önizleme).

NİYE (2026-10-09): yayın GitHub'ın Linux makinesinde çiziliyor, geliştirme macOS'ta. Pillow orada HarfBuzz/raqm ile
kerning uyguluyor, metin birkaç piksel farklı ölçülüyor: aynı kart bir ortamda 3, diğerinde 4 satır oldu ve
"KAT İRTİFAKI" 116 yerine 118 punto çıktı (CI kırmızıydı). Yerelde kusursuz görünen kartın yayında nasıl göründüğü
yalnız orada çizilince bilinir: `.github/workflows/sozluk-onizleme.yml` bu betiği çalıştırıp çıktıyı artefakt olarak yükler.

    python scripts/sozluk_onizleme.py --cikti onizleme            # 34 kart × (besleme, story)
    python scripts/sozluk_onizleme.py --cikti onizleme SZ-001 SZ-009   # yalnız bu kartlar
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("POSTEDM_TEST_MODU", "1")   # DB ve .env'e dokunma: yalnız çizim

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

import PIL  # noqa: E402
from PIL import Image, features  # noqa: E402

from src import sozluk_arsivi, yeni_formatlar  # noqa: E402


def ortam_raporu() -> str:
    ozellikler = {ad: features.check(ad) for ad in ("raqm", "fribidi", "harfbuzz", "freetype2")}
    return (f"Python {sys.version.split()[0]} · Pillow {PIL.__version__} · FreeType {features.version('freetype2')} · "
            f"yerleşim: {'RAQM (HarfBuzz kerning)' if ozellikler['raqm'] else 'BASIC'} · {ozellikler}")


def kontak(yollar: list, genislik: int, yukseklik: int, sutun: int, satir: int, onek: Path) -> list:
    """Görselleri sutun×satır'lık sayfalara dizer; yazılan dosyaların listesini döner."""
    yazilan = []
    sayfa = sutun * satir
    for n in range(0, len(yollar), sayfa):
        tab = Image.new("RGB", (genislik * sutun, yukseklik * satir), "white")
        for i, yol in enumerate(yollar[n:n + sayfa]):
            im = Image.open(yol).convert("RGB").resize((genislik - 8, yukseklik - 8), Image.LANCZOS)
            tab.paste(im, ((i % sutun) * genislik + 4, (i // sutun) * yukseklik + 4))
        hedef = onek.parent / f"{onek.name}_{n // sayfa + 1}.jpg"
        tab.save(hedef, quality=88)
        yazilan.append(hedef)
    return yazilan


def main() -> int:
    ap = argparse.ArgumentParser(description="Sözlük kartı önizlemesi")
    ap.add_argument("kodlar", nargs="*", help="yalnız bu kart kodları (boşsa hepsi)")
    ap.add_argument("--cikti", default="onizleme", help="çıktı klasörü")
    args = ap.parse_args()

    cikti = Path(args.cikti)
    cikti.mkdir(parents=True, exist_ok=True)
    kartlar = [k for k in sozluk_arsivi.kartlari_yukle(tazele=True) if not args.kodlar or k["kod"] in args.kodlar]
    yollar = {"besleme": [], "story": []}
    for k in kartlar:
        veri = sozluk_arsivi.karttan_veri(k)
        for olcu in yollar:
            yol = yeni_formatlar.slaytlari_uret(veri, format_turu="sozluk", cikti_dizini=cikti, cikti_onek=f"{k['kod']}_{olcu}", olcu=olcu)[0]
            yollar[olcu].append(Path(yol))
    kontak(yollar["besleme"], 540, 675, 3, 2, cikti / "kontak_besleme")
    kontak(yollar["story"], 360, 640, 4, 2, cikti / "kontak_story")
    rapor = ortam_raporu()
    (cikti / "ortam.txt").write_text(rapor + "\n", encoding="utf-8")
    print(rapor)
    print(f"{len(kartlar)} kart çizildi → {cikti}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
