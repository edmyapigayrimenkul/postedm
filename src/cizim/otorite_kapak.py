"""
src/cizim/otorite_kapak.py — Otorite & Haber 1. Slaytı (Hero Hook Kapak)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw

from .. import config
from .sabitler import (
    FONT_MONO_BOLD,
    FONT_SANS_BOLD,
    FONT_SANS_MEDIUM,
    GENISLIK,
    RENK_BEYAZ,
    RENK_KIRMIZI,
    RENK_KURSUN,
    RENK_METIN_GOVDE,
    RENK_MUREKKEP,
    YUKSEKLIK,
)
from .hatalar import TasmaHatasi
from .fontlar import _font_yukle
from .tipografi import (
    _gorsel_girdisi,
    _metin_sar,
    _temizle_tipografi,
    tr_ilk_buyuk,
)
from .tuval import _rozet_kirp, _sayfa_etiketi, _yerlesim
from .bilesenler import _difuzyon_golgeli_metin, _logo_yerlestir, _rozet_ciz
from .stok import _temiz_arkaplan_al

log = logging.getLogger(__name__)


@_gorsel_girdisi
def otorite_slayt_1_kapak(veri: Dict[str, Any], cikti_yolu: Optional[Path] = None) -> Path:
    """Otorite / Haber 1. Slaytı (Hero Hook Kapak):
    Metin uzunluğuna göre dinamik perdesi, difüzyon gölgesi ve iki tonlu manşetiyle
    0.8 saniyede durduran kanca kapak üretir.
    """
    kenar_bosluk = 70
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)

    # 1. Arka Plan
    kategori_kodu = veri.get("kategori_kodu") or veri.get("kategori", "HUKUK")
    foto_url = veri.get("gorsel_url") or veri.get("foto_url")
    tohum = veri.get("manset") or veri.get("manset_vurgu") or veri.get("id") or veri.get("orijinal_baslik")
    if veri.get("saf_editoryal"):
        canvas = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_MUREKKEP)
    else:
        haric = [veri.get("onceki_foto")] if veri.get("foto_degistir") and veri.get("onceki_foto") else None
        konu_metni = " ".join(str(veri.get(k) or "") for k in ("manset_parca_1", "manset_vurgu", "manset_parca_2", "manset", "spot", "rozet_metni"))
        canvas = _temiz_arkaplan_al(kategori_kodu, foto_url, tohum=tohum, haric_tut=haric, konu_metni=konu_metni)

    # 2. Manşet ve Başlık Verisini Analiz Et
    manset_ham = veri.get("manset", "")
    manset_p1 = veri.get("manset_parca_1")
    manset_vurgu = veri.get("manset_vurgu")
    manset_p2 = veri.get("manset_parca_2")

    dummy_img = Image.new("RGB", (10, 10))
    dummy_draw = ImageDraw.Draw(dummy_img)

    p1_str = tr_ilk_buyuk(_temizle_tipografi(str(manset_p1)).strip()) if manset_p1 else ""
    vurgu_str = _temizle_tipografi(str(manset_vurgu)).strip().replace("i", "İ").replace("ı", "I").upper() if manset_vurgu else ""
    p2_str = _temizle_tipografi(str(manset_p2)).strip() if manset_p2 else ""

    if not (p1_str or vurgu_str or p2_str) and manset_ham:
        ham_satirlar = [s.strip() for s in str(manset_ham).split("\n") if s.strip()]
        if len(ham_satirlar) == 1:
            p1_str = ham_satirlar[0]
        elif len(ham_satirlar) == 2:
            p1_str = ham_satirlar[0]
            vurgu_str = ham_satirlar[1].upper()
        else:
            p1_str = ham_satirlar[0]
            vurgu_str = ham_satirlar[1].upper()
            p2_str = " ".join(ham_satirlar[2:])

    pad_x = 22
    pad_y = 12
    gap_v = 16

    olcum = " ".join(str(p) for p in (p1_str, vurgu_str, p2_str) if p)
    uzunluk = len(olcum)
    if uzunluk <= 30:
        font_boyut = 96
    elif uzunluk <= 55:
        font_boyut = 88
    else:
        font_boyut = 80

    while font_boyut > 56:
        f_test = _font_yukle(FONT_SANS_BOLD, font_boyut)
        fits = True
        if vurgu_str:
            bbv_t = dummy_draw.textbbox((0, 0), vurgu_str, font=f_test)
            if (bbv_t[2] - bbv_t[0]) + (2 * pad_x) > kullanilabilir_w:
                fits = False
        if p1_str:
            bb1_t = dummy_draw.textbbox((0, 0), p1_str, font=f_test)
            if (bb1_t[2] - bb1_t[0]) > kullanilabilir_w:
                fits = False
        if p2_str:
            bb2_t = dummy_draw.textbbox((0, 0), p2_str, font=f_test)
            if (bb2_t[2] - bb2_t[0]) > kullanilabilir_w:
                fits = False
        if fits:
            break
        font_boyut -= 2

    font_manset = _font_yukle(FONT_SANS_BOLD, font_boyut)

    manset_satirlari: List[Tuple[str, bool]] = []
    if p1_str:
        manset_satirlari += [(s, False) for s in _metin_sar(p1_str, font_manset, kullanilabilir_w, dummy_draw)]
    if vurgu_str:
        manset_satirlari += [(s, True) for s in _metin_sar(vurgu_str, font_manset, kullanilabilir_w - 2 * pad_x, dummy_draw)]
    if p2_str:
        manset_satirlari += [(s, False) for s in _metin_sar(p2_str, font_manset, kullanilabilir_w, dummy_draw)]
    if len(manset_satirlari) > 5:
        raise TasmaHatasi(f"Kapak manşeti {len(manset_satirlari)} satıra çıktı ({len(olcum)} karakter)")

    ref = dummy_draw.textbbox((0, 0), "ÇĞİÖŞÜ ağy", font=font_manset)
    ref_ust, satir_h = ref[1], ref[3] - ref[1]
    vref = dummy_draw.textbbox((0, 0), "ÇĞİÖŞÜ", font=font_manset)
    v_ink_h = vref[3] - vref[1]
    box_h = v_ink_h + (2 * pad_y)
    h_baslik = sum((box_h if v else satir_h) for _, v in manset_satirlari) + gap_v * max(0, len(manset_satirlari) - 1)

    spot_ham = veri.get("spot") or veri.get("slayt_1_spot") or veri.get("detay_metni", "")
    spot_satirlari: List[str] = []
    spot_satir_h = 50
    font_spot = _font_yukle(FONT_SANS_MEDIUM, 36)
    if str(spot_ham or "").strip():
        for punto in (36, 34, 32, 30, 28):
            font_spot = _font_yukle(FONT_SANS_MEDIUM, punto)
            spot_satirlari = _metin_sar(spot_ham, font_spot, kullanilabilir_w - 60, dummy_draw)
            spot_satir_h = int(punto * 1.39)
            if len(spot_satirlari) <= (4 if punto > 32 else 5):
                break
        else:
            raise TasmaHatasi(f"Kapak spotu {len(str(spot_ham))} karakter; 28px'te bile 5 satırı aşıyor")

    h_spot_box = (len(spot_satirlari) * spot_satir_h) + 34 if spot_satirlari else 0

    alt_y = _yerlesim()["alt_bar"] - 5
    spot_end = alt_y - 35
    sy = spot_end - h_spot_box if spot_satirlari else spot_end
    by = sy - 35 - h_baslik
    if by < _yerlesim()["kronik_ust"] + 110:
        raise TasmaHatasi("Kapak manşeti ve spot üst rozete dayanıyor")

    serit_basi = max(180, by - (160 if YUKSEKLIK >= 1700 else 140))
    serit_tam = by + 220
    PANEL_ALFA = 185

    perde = Image.new("RGBA", (GENISLIK, YUKSEKLIK), (0, 0, 0, 0))
    p_draw = ImageDraw.Draw(perde)

    vignette_h = 240 if YUKSEKLIK >= 1700 else 200
    for y in range(vignette_h):
        alfa = int(75 * ((vignette_h - y) / vignette_h) ** 1.8)
        p_draw.line([(0, y), (GENISLIK, y)], fill=(8, 10, 14, alfa))

    azami_alfa = 240 if YUKSEKLIK >= 1700 else 252
    for y in range(serit_basi, YUKSEKLIK):
        if y < by:
            alfa = int(PANEL_ALFA * (((y - serit_basi) / max(1, by - serit_basi)) ** 1.15))
        elif y < serit_tam:
            alfa = int(PANEL_ALFA + (azami_alfa - PANEL_ALFA) * (((y - by) / max(1, serit_tam - by)) ** 0.85))
        else:
            alfa = azami_alfa
        p_draw.line([(0, y), (GENISLIK, y)], fill=(10, 12, 16, min(alfa, 255)))

    c_rgba = canvas.convert("RGBA")
    c_rgba.paste(perde, (0, 0), perde)
    canvas = c_rgba.convert("RGB")
    draw = ImageDraw.Draw(canvas)

    rozet_metin = _rozet_kirp(veri.get("rozet_metni") or "EDM ANALİZ // GAYRİMENKUL", 46)
    ku = _yerlesim()["kronik_ust"]
    _rozet_ciz(draw, kenar_bosluk, ku, rozet_metin, bg_color=RENK_KIRMIZI, fg_color=RENK_BEYAZ, font_boyut=20)
    _logo_yerlestir(canvas, beyaz=True, y=ku - 5, lw=285, golge=True)

    curr_y = by
    for metin, vurgu_mu in manset_satirlari:
        if not vurgu_mu:
            _difuzyon_golgeli_metin(canvas, [(metin, RENK_BEYAZ)], kenar_bosluk, curr_y - ref_ust, font_manset)
            curr_y += satir_h + gap_v
            continue
        bbv = dummy_draw.textbbox((0, 0), metin, font=font_manset)
        v_ink_w = bbv[2] - bbv[0]
        box_w = v_ink_w + (2 * pad_x)
        box_y, box_x = curr_y, kenar_bosluk - pad_x

        c_rgba = canvas.convert("RGBA")
        kapsul = Image.new("RGBA", (GENISLIK, YUKSEKLIK), (0, 0, 0, 0))
        ImageDraw.Draw(kapsul).rounded_rectangle([(box_x, box_y), (box_x + box_w, box_y + box_h)], radius=10, fill=(*RENK_KIRMIZI, 255))
        c_rgba.alpha_composite(kapsul)
        canvas = c_rgba.convert("RGB")
        draw = ImageDraw.Draw(canvas)

        tx = box_x + (box_w - v_ink_w) / 2 - bbv[0]
        ty = box_y + (box_h - v_ink_h) / 2 - vref[1]
        draw.text((tx, ty), metin, font=font_manset, fill=RENK_BEYAZ)
        curr_y = box_y + box_h + gap_v
        ty = box_y + (box_h - v_ink_h) / 2 - vref[1]
        draw.text((tx, ty), metin, font=font_manset, fill=RENK_BEYAZ)
        curr_y = box_y + box_h + gap_v

    if spot_satirlari:
        spot_card = Image.new("RGBA", (kullanilabilir_w, h_spot_box), (14, 18, 26, 220))
        sc_draw = ImageDraw.Draw(spot_card)
        sc_draw.rounded_rectangle([(0, 0), (kullanilabilir_w - 1, h_spot_box - 1)], radius=8, outline=(65, 75, 95, 190), width=1)
        sc_draw.rounded_rectangle([(0, 0), (6, h_spot_box - 1)], radius=3, fill=(*RENK_KIRMIZI, 255))
        curr_ty = 18
        for sl in spot_satirlari:
            sc_draw.text((26, curr_ty), sl, font=font_spot, fill=RENK_METIN_GOVDE)
            curr_ty += spot_satir_h

        c_rgba = canvas.convert("RGBA")
        c_rgba.paste(spot_card, (kenar_bosluk, sy), spot_card)
        canvas = c_rgba.convert("RGB")
        draw = ImageDraw.Draw(canvas)

    draw.line([(kenar_bosluk, alt_y), (GENISLIK - kenar_bosluk, alt_y)], fill=(55, 62, 75), width=1)
    draw.text((kenar_bosluk, alt_y + 22), "EDM YAPI & GAYRİMENKUL // BÜLTEN", font=_font_yukle(FONT_MONO_BOLD, 21), fill=RENK_KURSUN)
    kapak_etiket = _sayfa_etiketi(veri, 1)
    if kapak_etiket and str(kapak_etiket).strip():
        ke_w = draw.textbbox((0, 0), kapak_etiket, font=_font_yukle(FONT_MONO_BOLD, 18))[2]
        _rozet_ciz(draw, GENISLIK - kenar_bosluk - ke_w - 38, alt_y + 12, kapak_etiket, bg_color=RENK_KIRMIZI, fg_color=RENK_BEYAZ, font_boyut=18)

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/otorite_01_kapak_{os.getpid()}.jpg")
    else:
        cikti_yolu = Path(cikti_yolu)
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu
