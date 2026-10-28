"""
src/cizim/ilan_detay.py — İlan Detay (Mimari Detaylar & Yaşam Alanı) Slaytı
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image, ImageDraw, ImageOps

from .. import config
from .sabitler import (
    FONT_FRAUNCES,
    FONT_MONO,
    FONT_MONO_BOLD,
    FONT_SANS,
    GENISLIK,
    LOGO_YATAY_ACIK,
    RENK_CIZGI_KOYU,
    RENK_KAGIT,
    RENK_KIRMIZI,
    RENK_KURSUN,
    RENK_MUREKKEP,
    RENK_MUREKKEP_2,
    YUKSEKLIK,
)
from .fontlar import _font_yukle
from .tipografi import _gorsel_girdisi
from .stok import _foto_indir_veya_ac

log = logging.getLogger(__name__)


@_gorsel_girdisi
def ilan_detay_slayti_ciz(ilan: Dict[str, Any], cikti_yolu: Optional[Path] = None) -> Path:
    """İlanın 2. slaytı (Mimari Detaylar & Yaşam Alanı): Çift fotoğraf kolajı + 4 avantaj."""
    img = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_MUREKKEP)
    draw = ImageDraw.Draw(img)

    kenar_bosluk = 65
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)

    # 1. Üst Bar
    font_ust = _font_yukle(FONT_MONO, 20)
    draw.text((kenar_bosluk, 60), "PORTFÖY DETAYLARI // SİLİVRİ", font=font_ust, fill=RENK_KURSUN)

    if LOGO_YATAY_ACIK.exists():
        try:
            logo = Image.open(LOGO_YATAY_ACIK).convert("RGBA")
            lw = 200
            lh = int(logo.height * (lw / logo.width))
            logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)
            img.paste(logo, (GENISLIK - kenar_bosluk - lw, 52), logo)
        except Exception as e:
            log.warning("logo (açık) yüklenemedi, slayt onsuz üretiliyor: %s", e)

    draw.line([(kenar_bosluk, 105), (GENISLIK - kenar_bosluk, 105)], fill=RENK_CIZGI_KOYU, width=1)

    # 2. Fotoğraf Kolajı (2. ve 3. fotoğraflar yan yana)
    gorseller = ilan.get("gorseller")
    if not gorseller:
        try:
            gorseller = json.loads(ilan.get("gorseller_json") or "[]")
        except Exception:
            gorseller = []

    foto_w = (kullanilabilir_w - 20) // 2
    foto_h = 440
    y_foto = 135

    f1 = _foto_indir_veya_ac(gorseller[1]) if len(gorseller) > 1 else None
    f2 = _foto_indir_veya_ac(gorseller[2]) if len(gorseller) > 2 else None

    if f1:
        c1 = ImageOps.fit(f1, (foto_w, foto_h), Image.Resampling.LANCZOS)
        img.paste(c1, (kenar_bosluk, y_foto))
        draw.rectangle([(kenar_bosluk, y_foto), (kenar_bosluk + foto_w, y_foto + foto_h)], outline=RENK_CIZGI_KOYU, width=1)
    else:
        draw.rectangle([(kenar_bosluk, y_foto), (kenar_bosluk + foto_w, y_foto + foto_h)], fill=RENK_MUREKKEP_2)

    if f2:
        c2 = ImageOps.fit(f2, (foto_w, foto_h), Image.Resampling.LANCZOS)
        img.paste(c2, (kenar_bosluk + foto_w + 20, y_foto))
        draw.rectangle([(kenar_bosluk + foto_w + 20, y_foto), (kenar_bosluk + kullanilabilir_w, y_foto + foto_h)], outline=RENK_CIZGI_KOYU, width=1)
    else:
        draw.rectangle([(kenar_bosluk + foto_w + 20, y_foto), (kenar_bosluk + kullanilabilir_w, y_foto + foto_h)], fill=RENK_MUREKKEP_2)

    # 3. Mülk Nitelikleri & Avantaj Kutuları (4 Maddelik Pafta)
    y_kutu = 620
    font_sec_baslik = _font_yukle(FONT_FRAUNCES, 34)
    draw.text((kenar_bosluk, y_kutu), "Öne Çıkan Nitelikler", font=font_sec_baslik, fill=RENK_KAGIT)

    try:
        ozellikler = json.loads(ilan.get("ozellikler_json") or "{}")
    except Exception:
        ozellikler = {}
    gercek_bilgiler = []
    if ilan.get("m2"):
        gercek_bilgiler.append(("Alan", f"{int(float(ilan['m2'])):,} m² ilan alanı".replace(",", ".")))
    if ilan.get("oda"):
        gercek_bilgiler.append(("Oda Bilgisi", str(ilan["oda"])))
    if ilan.get("tip"):
        gercek_bilgiler.append(("Mülk Türü", str(ilan["tip"]).replace("-", " ").title()))
    for anahtar, deger in ozellikler.items():
        if deger and len(gercek_bilgiler) < 4:
            gercek_bilgiler.append((str(anahtar)[:32], str(deger)[:72]))
    if len(gercek_bilgiler) < 4:
        konum = " · ".join(x for x in [ilan.get("mahalle"), ilan.get("ilce")] if x)
        if konum:
            gercek_bilgiler.append(("Konum", konum))
    yedek_bilgiler = [
        ("Güncel İlan", f"Ayrıntılar için portföy no #{ilan.get('id', '')}"),
        ("Bölge Uzmanlığı", "Silivri ve Trakya saha deneyimi"),
        ("Doğrudan İletişim", "Güncel durum ve randevu için ofisimizle görüşün"),
        ("EDM Portföyü", "Güncel ayrıntılar ilan sayfasında"),
    ]
    for yedek in yedek_bilgiler:
        if len(gercek_bilgiler) >= 4:
            break
        gercek_bilgiler.append(yedek)
    maddeler = [
        (f"{sira:02d}", baslik, aciklama)
        for sira, (baslik, aciklama) in enumerate(gercek_bilgiler[:4], start=1)
    ]

    ky = y_kutu + 60
    font_no = _font_yukle(FONT_MONO_BOLD, 22)
    font_mb = _font_yukle(FONT_FRAUNCES, 24)
    font_mt = _font_yukle(FONT_SANS, 19)

    for no, bas, aciklama in maddeler:
        draw.text((kenar_bosluk, ky), no, font=font_no, fill=RENK_KIRMIZI)
        draw.text((kenar_bosluk + 55, ky - 2), bas, font=font_mb, fill=RENK_KAGIT)
        draw.text((kenar_bosluk + 55, ky + 30), aciklama, font=font_mt, fill=RENK_KURSUN)
        draw.line([(kenar_bosluk + 55, ky + 72), (GENISLIK - kenar_bosluk, ky + 72)], fill=RENK_CIZGI_KOYU, width=1)
        ky += 95

    # 4. Alt Bilgi
    alt_y = YUKSEKLIK - 110
    draw.line([(kenar_bosluk, alt_y), (GENISLIK - kenar_bosluk, alt_y)], fill=RENK_CIZGI_KOYU, width=1)
    draw.text((kenar_bosluk, alt_y + 25), "EDM YAPI & GAYRİMENKUL // SİLİVRİ", font=_font_yukle(FONT_MONO, 20), fill=RENK_KURSUN)
    draw.text((GENISLIK - kenar_bosluk - 100, alt_y + 25), "02 / 03 >", font=_font_yukle(FONT_MONO_BOLD, 20), fill=RENK_KIRMIZI)

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/ilan_detay_{ilan.get('id')}.jpg")
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    img.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu
