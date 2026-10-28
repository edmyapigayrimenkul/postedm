"""
src/cizim/otorite_detay.py — Otorite 2. Slaytı (Problem Analizi / İkili Kıyaslama)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image, ImageDraw

from .. import config
from .sabitler import (
    FONT_MONO,
    FONT_MONO_BOLD,
    FONT_SANS_BOLD,
    FONT_SANS_MEDIUM,
    GENISLIK,
    RENK_BEYAZ,
    RENK_CIZGI_KOYU,
    RENK_KIRMIZI_CANLI,
    RENK_KURSUN,
    RENK_METIN_GOVDE,
    RENK_MUREKKEP_2,
    RENK_YESIL,
    YUKSEKLIK,
)
from .fontlar import _dikey_dagit, _ek_dolgu_hesapla, _font_yukle, _govde_sigdir
from .tipografi import _gorsel_girdisi
from .tuval import _sayfa_etiketi
from .bilesenler import _difuzyon_golgeli_metin, _logo_yerlestir, _rozet_ciz
from .ikonlar import _vektor_ikon_uret
from .stok import _temiz_arkaplan_al

log = logging.getLogger(__name__)


@_gorsel_girdisi
def otorite_slayt_2_detay(veri: Dict[str, Any], cikti_yolu: Optional[Path] = None) -> Path:
    """Otorite 2. Slaytı (Problem Analizi veya İkili Kıyaslama Kartları)."""
    kenar_bosluk = 70
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)

    kategori_kodu = veri.get("kategori_kodu") or veri.get("kategori", "GENEL")
    tohum = veri.get("manset") or veri.get("id") or veri.get("orijinal_baslik")
    canvas = _temiz_arkaplan_al(kategori_kodu, tohum=tohum)

    karartma = Image.new("RGBA", (GENISLIK, YUKSEKLIK), (10, 12, 16, 190))
    c_rgba = canvas.convert("RGBA")
    c_rgba.paste(karartma, (0, 0), karartma)
    canvas = c_rgba.convert("RGB")
    draw = ImageDraw.Draw(canvas)

    # 1. Üst Bar
    rozet = veri.get("rozet_metni") or "SEKTÖREL ANALİZ // HUKUK & UYGULAMA"
    _rozet_ciz(draw, kenar_bosluk, 60, rozet, bg_color=RENK_MUREKKEP_2, fg_color=RENK_BEYAZ, border_color=RENK_CIZGI_KOYU)
    _logo_yerlestir(canvas, beyaz=True, y=55, lw=285)

    # 2. Bölüm Manşeti
    detay_veri = veri.get("slayt_2_detay") or {}
    baslik_1 = detay_veri.get("baslik_satir_1") or ""
    baslik_vurgu = detay_veri.get("baslik_vurgu") or ""

    satirlar = [
        (baslik_1, RENK_BEYAZ),
        (baslik_vurgu, RENK_KIRMIZI_CANLI),
    ]
    _difuzyon_golgeli_metin(canvas, satirlar, kenar_bosluk, 140, _font_yukle(FONT_SANS_BOLD, 52), satir_araligi=64)

    k1 = detay_veri.get("kart_1") or {}
    k2 = detay_veri.get("kart_2") or {}

    KART_UST_PAY = 20
    KART_BASLIK_Y = 64
    KART_GOVDE_Y = 114
    KART_ALT_PAY = 24

    def _kart_olc(kart: Dict[str, Any]) -> Dict[str, Any]:
        font, satirlar = _govde_sigdir(
            kart.get("aciklama", ""), FONT_SANS_MEDIUM,
            baslangic_boyut=32, min_boyut=26,
            azami_w=kullanilabilir_w - 60, azami_satir=5, draw=draw,
        )
        satir_araligi = font.size + 10
        yukseklik = KART_GOVDE_Y + (len(satirlar) * satir_araligi) + KART_ALT_PAY
        return {"kart": kart, "font": font, "satirlar": satirlar,
                "satir_araligi": satir_araligi, "h": yukseklik}

    olculer = [_kart_olc(k1), _kart_olc(k2)]

    SAVE_H = 120
    ust_sinir = 275
    alt_sinir = YUKSEKLIK - 130

    ek_dolgu = _ek_dolgu_hesapla(
        [o["h"] for o in olculer] + [SAVE_H], ust_sinir, alt_sinir,
        asgari_bosluk=18, azami_ek=64,
    )
    for o in olculer:
        o["h"] += ek_dolgu
        o["govde_kaydirma"] = ek_dolgu // 2

    konumlar = _dikey_dagit(
        ust_sinir, alt_sinir,
        [o["h"] for o in olculer] + [SAVE_H],
        asgari_bosluk=18, azami_bosluk=44,
    )

    c_rgba = canvas.convert("RGBA")

    for olcu, ky in zip(olculer, konumlar):
        kart = olcu["kart"]
        k_h = olcu["h"]
        kart_img = Image.new("RGBA", (kullanilabilir_w, k_h), (18, 22, 32, 245))
        kd = ImageDraw.Draw(kart_img)
        kd.rounded_rectangle([(0, 0), (kullanilabilir_w - 1, k_h - 1)], radius=10, outline=(65, 75, 95, 255), width=1)

        kirmizi_mi = (kart.get("renk") == "kirmizi")
        sol_renk = (*RENK_KIRMIZI_CANLI, 255) if kirmizi_mi else (*RENK_YESIL, 255)
        kd.rounded_rectangle([(0, 0), (7, k_h - 1)], radius=4, fill=sol_renk)

        etiket = kart.get("etiket", "").replace("[", "").replace("]", "").strip()
        rozet_bg = (180, 15, 25) if kirmizi_mi else (20, 130, 60)
        _rozet_ciz(kd, 28, KART_UST_PAY, etiket, bg_color=rozet_bg, fg_color=RENK_BEYAZ, font_boyut=17)

        b_font, b_satirlar = _govde_sigdir(
            kart.get("baslik", ""), FONT_SANS_BOLD, 34, 27,
            kullanilabilir_w - 60, 1, kd,
        )
        kd.text((28, KART_BASLIK_Y), b_satirlar[0] if b_satirlar else "", font=b_font, fill=RENK_BEYAZ)

        gy = KART_GOVDE_Y + olcu.get("govde_kaydirma", 0)
        for satir in olcu["satirlar"]:
            kd.text((28, gy), satir, font=olcu["font"], fill=RENK_METIN_GOVDE)
            gy += olcu["satir_araligi"]

        c_rgba.paste(kart_img, (kenar_bosluk, ky), kart_img)

    # 4. Apple Glassmorphic "Kaydet & Sakla" Widget'ı
    save_y = konumlar[-1]
    save_h = SAVE_H
    save_box = Image.new("RGBA", (kullanilabilir_w, save_h), (22, 26, 38, 240))
    sb_draw = ImageDraw.Draw(save_box)
    sb_draw.rounded_rectangle([(0, 0), (kullanilabilir_w - 1, save_h - 1)], radius=12, outline=(70, 80, 105, 220), width=1)

    icon_cx, icon_cy = 56, save_h // 2
    sb_draw.ellipse([(icon_cx - 28, icon_cy - 28), (icon_cx + 28, icon_cy + 28)], fill=(*RENK_KIRMIZI_CANLI, 255))
    b_icon = _vektor_ikon_uret("bookmark", 30, (255, 255, 255))
    save_box.paste(b_icon, (icon_cx - 15, icon_cy - 15), b_icon)

    tx = 106
    sb_draw.text((tx, 28), "HUKUKİ MEVZUAT KAYDI  //  EDM ARŞİVİ", font=_font_yukle(FONT_MONO_BOLD, 20), fill=RENK_KIRMIZI_CANLI)
    kaydet_metni = (veri.get("slayt_4_cta") or {}).get("kaydet_metni") or "Hukuki haklarınızı korumak adına bu rehberi arşivinize ekleyin."
    kf, ks = _govde_sigdir(kaydet_metni, FONT_SANS_MEDIUM, 24, 19, kullanilabilir_w - tx - 30, 1, sb_draw)
    sb_draw.text((tx, 60), ks[0] if ks else "", font=kf, fill=RENK_BEYAZ)

    c_rgba.paste(save_box, (kenar_bosluk, save_y), save_box)
    canvas = c_rgba.convert("RGB")
    draw = ImageDraw.Draw(canvas)

    # 5. Alt Bar
    alt_y = YUKSEKLIK - 105
    draw.line([(kenar_bosluk, alt_y), (GENISLIK - kenar_bosluk, alt_y)], fill=RENK_CIZGI_KOYU, width=1)
    draw.text((kenar_bosluk, alt_y + 24), "EDM YAPI & GAYRİMENKUL // HUKUK BÜLTENİ", font=_font_yukle(FONT_MONO, 19), fill=RENK_KURSUN)
    d_etiket = _sayfa_etiketi(veri, 2)
    de_w = draw.textbbox((0, 0), d_etiket, font=_font_yukle(FONT_MONO_BOLD, 17))[2]
    _rozet_ciz(draw, GENISLIK - kenar_bosluk - de_w - 36, alt_y + 14, d_etiket, bg_color=RENK_KIRMIZI_CANLI, fg_color=RENK_BEYAZ, font_boyut=17)

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/otorite_02_detay_{os.getpid()}.jpg")
    else:
        cikti_yolu = Path(cikti_yolu)
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu
