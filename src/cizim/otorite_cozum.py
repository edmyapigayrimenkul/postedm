"""
src/cizim/otorite_cozum.py — Otorite 3. Slaytı (Çözüm Yol Haritası) ve Kapanış Seçici
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
    RENK_MUREKKEP,
    RENK_MUREKKEP_2,
    YUKSEKLIK,
)
from .fontlar import _dikey_dagit, _ek_dolgu_hesapla, _font_yukle, _govde_sigdir
from .tipografi import _gorsel_girdisi, _metin_sar
from .tuval import _sayfa_etiketi
from .bilesenler import _logo_yerlestir, _rozet_ciz
from .finans import _finansal_tablo_ciz

log = logging.getLogger(__name__)


@_gorsel_girdisi
def otorite_slayt_3_cozum(veri: Dict[str, Any], cikti_yolu: Optional[Path] = None) -> Path:
    """Otorite 3. Slaytı (Çözüm Yol Haritası, Finansal Tablo veya Resmi Pafta)."""
    kenar_bosluk = 70
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)

    cozum_veri = veri.get("slayt_3_cozum") or {}
    tip = cozum_veri.get("tip", "adim_adim_rehber")

    if tip == "finansal_tablo":
        return _finansal_tablo_ciz(veri, cozum_veri, cikti_yolu)

    canvas = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_MUREKKEP)
    draw = ImageDraw.Draw(canvas)

    _rozet_ciz(draw, kenar_bosluk, 60, veri.get("rozet_metni", "HUKUK & TAPU REHBERİ // ADIM ADIM KORUNMA"), bg_color=RENK_MUREKKEP_2, fg_color=RENK_BEYAZ, border_color=RENK_CIZGI_KOYU)
    _logo_yerlestir(canvas, beyaz=True, y=55, lw=285)
    draw.line([(kenar_bosluk, 105), (GENISLIK - kenar_bosluk, 105)], fill=RENK_CIZGI_KOYU, width=1)

    baslik_ust = cozum_veri.get("baslik_ust") or ""
    baslik_vurgu = cozum_veri.get("baslik_vurgu") or "Atılacak adımlar"
    satirlar_ust = _metin_sar(baslik_ust, _font_yukle(FONT_SANS_BOLD, 46), kullanilabilir_w, draw)
    by = 135
    for su in satirlar_ust:
        draw.text((kenar_bosluk, by), su, font=_font_yukle(FONT_SANS_BOLD, 46), fill=RENK_BEYAZ)
        by += 58
    draw.text((kenar_bosluk, by), baslik_vurgu, font=_font_yukle(FONT_SANS_BOLD, 46), fill=RENK_KIRMIZI_CANLI)
    by += 68

    maddeler = cozum_veri.get("maddeler") or []
    f_no = _font_yukle(FONT_MONO_BOLD, 22)

    ADIM_GOVDE_Y = 74
    ADIM_ALT_PAY = 26

    olculer = []
    for m in maddeler:
        font, satirlar = _govde_sigdir(
            m.get("aciklama", ""), FONT_SANS_MEDIUM,
            baslangic_boyut=30, min_boyut=24,
            azami_w=kullanilabilir_w - 75, azami_satir=4, draw=draw,
        )
        satir_araligi = font.size + 12
        olculer.append({
            "madde": m, "font": font, "satirlar": satirlar,
            "satir_araligi": satir_araligi,
            "h": ADIM_GOVDE_Y + (len(satirlar) * satir_araligi) + ADIM_ALT_PAY,
        })

    ek_dolgu = _ek_dolgu_hesapla(
        [o["h"] for o in olculer], by, YUKSEKLIK - 130,
        asgari_bosluk=20, azami_ek=72,
    )
    for o in olculer:
        o["h"] += ek_dolgu
        o["govde_kaydirma"] = ek_dolgu // 2

    konumlar = _dikey_dagit(
        by, YUKSEKLIK - 130,
        [o["h"] for o in olculer],
        asgari_bosluk=20, azami_bosluk=52,
    )

    for olcu, my in zip(olculer, konumlar):
        m = olcu["madde"]
        kart_h = olcu["h"]
        no = str(m.get("no", "01")).zfill(2)

        draw.rounded_rectangle([(kenar_bosluk, my), (GENISLIK - kenar_bosluk, my + kart_h)], radius=10, fill=RENK_MUREKKEP_2, outline=(65, 75, 95))
        draw.rounded_rectangle([(kenar_bosluk, my), (kenar_bosluk + 7, my + kart_h)], radius=4, fill=RENK_KIRMIZI_CANLI)

        cx, cy = kenar_bosluk + 52, my + 38
        draw.ellipse([(cx - 24, cy - 24), (cx + 24, cy + 24)], fill=RENK_KIRMIZI_CANLI)
        bbox = draw.textbbox((0, 0), no, font=f_no)
        nw, nh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((cx - (nw // 2), cy - (nh // 2) - 2), no, font=f_no, fill=RENK_BEYAZ)

        b_font, b_satirlar = _govde_sigdir(
            m.get("baslik", ""), FONT_SANS_BOLD, 33, 26,
            GENISLIK - kenar_bosluk - (cx + 38) - 30, 1, draw,
        )
        draw.text((cx + 38, my + 21), b_satirlar[0] if b_satirlar else "", font=b_font, fill=RENK_BEYAZ)

        ay = my + ADIM_GOVDE_Y + olcu.get("govde_kaydirma", 0)
        for satir in olcu["satirlar"]:
            draw.text((kenar_bosluk + 35, ay), satir, font=olcu["font"], fill=RENK_METIN_GOVDE)
            ay += olcu["satir_araligi"]

    alt_y = YUKSEKLIK - 105
    draw.line([(kenar_bosluk, alt_y), (GENISLIK - kenar_bosluk, alt_y)], fill=RENK_CIZGI_KOYU, width=1)
    draw.text((kenar_bosluk, alt_y + 24), "EDM YAPI & GAYRİMENKUL // DANIŞMANLIK", font=_font_yukle(FONT_MONO, 19), fill=RENK_KURSUN)
    c_etiket = _sayfa_etiketi(veri, veri.get("_slayt_sirasi", 3))
    ce_w = draw.textbbox((0, 0), c_etiket, font=_font_yukle(FONT_MONO_BOLD, 17))[2]
    _rozet_ciz(draw, GENISLIK - kenar_bosluk - ce_w - 36, alt_y + 14, c_etiket, bg_color=RENK_KIRMIZI_CANLI, fg_color=RENK_BEYAZ, font_boyut=17)

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/otorite_03_cozum_{os.getpid()}.jpg")
    else:
        cikti_yolu = Path(cikti_yolu)
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


def slayt_kapanis(veri: Dict[str, Any], sayfa: str, cikti_yolu: Optional[Path] = None) -> Path:
    """Kapanış slaytı — Dinamik Stil Seçimli Prestij Mimarisi."""
    from ..kapanis_stilleri import kapanis_ciz
    stil = veri.get("kapanis_stili") or config.ayar_al("tasarim.kapanis_stili", "kartvizit")
    return kapanis_ciz(stil, veri, sayfa, cikti_yolu)
