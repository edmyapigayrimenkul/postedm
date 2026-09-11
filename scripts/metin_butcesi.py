#!/usr/bin/env python3
"""
scripts/metin_butcesi.py — Çizicinin Gerçek Metin Kapasitesini Ölçer

ICERIK-SISTEMI.md §5 tablosunun ve src/generate_text.py:BUTCE sözlüğünün kaynağı.

Font veya kutu genişliği değişince ÇALIŞTIRILMALI: prompt çizicinin sığdırdığından
uzun metin isterse make_image sessizce kırpar. Üretimde görülen "cümlenin ortasında
biten kart" hatası tam olarak bu uyumsuzluktu.

    python scripts/metin_butcesi.py
"""

from __future__ import annotations

import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from PIL import Image, ImageDraw, ImageFont

from src import generate_text, make_image as mi

# Türkçe ortalama karakter genişliğini temsil eden ölçüm metni.
# Türkçe'de "ğ ş ı İ ü ö ç" ve uzun ekler ortalama genişliği İngilizce'den
# ayırdığı için ölçüm gerçek bir Türkçe cümleyle yapılır.
OLCUM_METNI = (
    "Hissedarlardan herhangi birine noterden resmi feragatname imzalatılmadan "
    "yapılan satışlarda diğer paydaşlar iki yıl içinde önalım davası açabilir"
)

# (etiket, font yolu, punto, kutu genişliği, azami satır, BUTCE anahtarı)
ALANLAR = [
    ("Manşet satırı (kapak)",     mi.FONT_FRAUNCES,      78, 940,      1, "manset_satir"),
    ("Spot (kapak)",              mi.FONT_SANS_MEDIUM,   32, 940,      3, "spot"),
    ("Kart başlığı (slayt 2)",    mi.FONT_SANS_BOLD,     34, 940 - 60, 1, "kart_baslik"),
    ("Kart açıklaması (slayt 2)", mi.FONT_SANS_MEDIUM,   29, 940 - 60, 4, "kart_aciklama"),
    ("Adım başlığı (slayt 3)",    mi.FONT_SANS_BOLD,     33, 940 - 60, 1, "adim_baslik"),
    ("Adım açıklaması (slayt 3)", mi.FONT_SANS_MEDIUM,   28, 940 - 75, 3, "adim_aciklama"),
    ("Rozet şeridi",              mi.FONT_MONO_BOLD,     19, 620,      1, "rozet"),
    ("Yasal dayanak şeridi",      mi.FONT_MONO,          21, 700,      1, "yasal_dayanak"),
]

# Bütçe, sığan miktarın bu oranı kadar. Tam sınıra yazılan Türkçe metin
# ilk uzun kelimede taşıyor; %20 pay o taşmayı karşılıyor.
GUVENLIK_PAYI = 0.80


def main() -> int:
    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    print(f"{'ALAN':30} {'PUNTO':>6} {'SIĞAN':>7} {'ÖNERİ':>7} {'MEVCUT':>7}  DURUM")
    print("-" * 78)

    hatali = 0
    for etiket, font_yolu, punto, genislik, satir, anahtar in ALANLAR:
        font = ImageFont.truetype(str(font_yolu), punto)
        genislik_px = draw.textbbox((0, 0), OLCUM_METNI, font=font)[2]
        ort_kar = genislik_px / len(OLCUM_METNI)
        sigan = int((genislik / ort_kar) * satir)
        oneri = int(sigan * GUVENLIK_PAYI)
        mevcut = generate_text.BUTCE.get(anahtar, 0)

        if mevcut > sigan:
            durum, ek = "TAŞIYOR", 1
        elif mevcut > oneri:
            durum, ek = "sınırda", 0
        else:
            durum, ek = "uygun", 0
        hatali += ek
        print(f"{etiket:30} {punto:>6} {sigan:>7} {oneri:>7} {mevcut:>7}  {durum}")

    print()
    if hatali:
        print(f"{hatali} alan çiziciden uzun. src/generate_text.py:BUTCE güncellenmeli,")
        print("ardından ICERIK-SISTEMI.md §5 tablosu da elden geçirilmeli.")
        return 1
    print("Tüm bütçeler çizicinin kapasitesi içinde.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
