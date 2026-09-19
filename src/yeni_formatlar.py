"""
src/yeni_formatlar.py — EDM 4 Temel Format Görsel Motoru
1. EDM EMLAK SÖZLÜĞÜ (Kireç Bej Zemin, Dev Fraunces Kelime, Kitap Filigranı, Tırnaklı Hukuki Tanım)
2. NEDİR DOĞRUSU? (Kırmızı Gradient Zemin, Dev Şehir Efsanesi Hook, Beyaz Alt Zemin, Alta Dayalı Altın Kural)
3. GERÇEK HUKUKİ VAKA ANALİZİ (Siyah Editoryal Zemin, Fraunces Manşet, Fraunces Hüküm, Alta Dayalı Ders Kartı)
4. NET CEVAP REHBERİ / SORU-CEVAP (Beyaz Zemin, Fraunces Soru, '?' Filigranı, Net Cevap Rozeti, Alta Dayalı Tavsiye)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import config, make_image

log = logging.getLogger(__name__)

GENISLIK = 1080
YUKSEKLIK = 1350

# Renk Paleti
RENK_MUREKKEP = (18, 19, 22)
RENK_BEYAZ = (255, 255, 255)
RENK_LOGO_KIRMIZI = (196, 3, 15)
RENK_KIREC_BEJ = (235, 235, 231)
RENK_KIREC_KUTU = (226, 226, 221)
RENK_KIREC_BORDER = (212, 212, 206)
RENK_KURSUN = (138, 139, 143)
RENK_CIZGI_ACIK = (220, 220, 216)
RENK_CIZGI_KOYU = (45, 48, 56)
RENK_ALTIN = (235, 175, 55)  # Sıcak, prestijli altın sarısı (#EBAF37)

FONT_FRAUNCES = config.yol_al("assets/fonts/Fraunces.ttf")
FONT_SANS_BOLD = config.yol_al("assets/fonts/PlusJakartaSans-Bold.ttf")
FONT_SANS_MEDIUM = config.yol_al("assets/fonts/PlusJakartaSans-Medium.ttf")
FONT_MONO = config.yol_al("assets/fonts/IBMPlexMono.ttf")
FONT_MONO_BOLD = config.yol_al("assets/fonts/IBMPlexMono-Bold.ttf")


# =============================================================================
# 1. FORMAT: EDM GAYRİMENKUL SÖZLÜĞÜ
# =============================================================================
def ciz_sag_sozluk_filigran(draw_target: ImageDraw.ImageDraw, cx: int, cy: int, w: int = 290, h: int = 195, alpha: int = 30) -> None:
    """Sağ üstte açık kitap ikonu filigranı."""
    renk = (18, 19, 22, alpha)
    hw = w // 2
    hh = h // 2
    sol_pts = [(cx - 6, cy - hh + 16), (cx - hw, cy - hh + 4), (cx - hw, cy + hh - 14), (cx - 6, cy + hh + 4)]
    sag_pts = [(cx + 6, cy - hh + 16), (cx + hw, cy - hh + 4), (cx + hw, cy + hh - 14), (cx + 6, cy + hh + 4)]
    draw_target.polygon(sol_pts, outline=renk, width=4)
    draw_target.polygon(sag_pts, outline=renk, width=4)
    draw_target.line([(cx, cy - hh + 12), (cx, cy + hh + 8)], fill=renk, width=5)

    for dy in np.linspace(-hh + 45, hh - 45, 4):
        int_dy = int(dy)
        draw_target.line([(cx - hw + 25, cy + int_dy - 2), (cx - 24, cy + int_dy + 2)], fill=renk, width=2)
        draw_target.line([(cx + 24, cy + int_dy + 2), (cx + hw - 25, cy + int_dy - 2)], fill=renk, width=2)

    ribbon_pts = [(cx - 5, cy + hh + 4), (cx + 5, cy + hh + 4), (cx + 4, cy + hh + 30), (cx, cy + hh + 22), (cx - 4, cy + hh + 30)]
    draw_target.polygon(ribbon_pts, fill=(196, 3, 15, int(alpha * 2)))


def uret_sozluk(cikti_yolu: Path, terim: str, kategori: str, tanim_metni: str, puf_maddeleri: Any, sayfa_no: str = "SÖZLÜK // 01") -> Path:
    canvas = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_KIREC_BEJ)
    canvas = make_image._filigran_uygula(canvas, acik_zemin=True)

    yer = make_image._yerlesim()
    kenar = yer["kenar"]
    kullanilabilir_w = GENISLIK - (2 * kenar)
    ku = yer["kronik_ust"]

    # Logo ve sağ üst kitap filigranı
    make_image._logo_yerlestir(canvas, beyaz=False, y=ku - 5, lw=285, golge=False, kirmizi_zemin=False)

    overlay = Image.new("RGBA", (GENISLIK, YUKSEKLIK), (255, 255, 255, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    ciz_sag_sozluk_filigran(overlay_draw, cx=GENISLIK - kenar - 145, cy=ku + 105, w=280, h=185, alpha=24)

    alt_y = yer["alt_bar"]
    draw = ImageDraw.Draw(canvas)
    draw.line([(kenar, alt_y), (GENISLIK - kenar, alt_y)], fill=RENK_KIREC_BORDER, width=1)
    draw.text((kenar, alt_y + 26), "EDM YAPI & GAYRİMENKUL // EMLAK SÖZLÜĞÜ", font=make_image._font_yukle(FONT_MONO, 19), fill=RENK_KURSUN)
    sf = make_image._font_yukle(FONT_MONO_BOLD, 19)
    sw = draw.textbbox((0, 0), sayfa_no, font=sf)[2]
    draw.text((GENISLIK - kenar - sw, alt_y + 26), sayfa_no, font=sf, fill=RENK_MUREKKEP)

    # Kategori etiketi
    kat_y = 160
    f_kat = make_image._font_yukle(FONT_MONO_BOLD, 21)
    draw.text((kenar, kat_y), f"// {kategori.upper()}", font=f_kat, fill=RENK_LOGO_KIRMIZI)

    # Terim Punto ve Satır Hesaplama (Maksimum 2 satır, 1 satıra sığıyorsa öncelikli tek satır)
    best_satirlar = []
    best_punto = 65
    for f_punto in range(110, 60, -2):
        f_test = make_image._font_yukle(FONT_FRAUNCES, f_punto)
        img_temp = Image.new("RGB", (10, 10))
        d_temp = ImageDraw.Draw(img_temp)
        satirlar = make_image._metin_sar(terim, f_test, kullanilabilir_w, d_temp)
        if len(satirlar) <= 2:
            best_satirlar = satirlar
            best_punto = f_punto
            if len(satirlar) == 1 and f_punto >= 85:
                break

    f_terim = make_image._font_yukle(FONT_FRAUNCES, best_punto)
    terim_satirlar = best_satirlar
    line_h_terim = int(best_punto * 1.15)

    # Terim başlangıcı: Kitap filigranı ve logo alt hizasına saygılı, ferah
    terim_y = 225
    for s in terim_satirlar:
        draw.text((kenar, terim_y), s, font=f_terim, fill=RENK_MUREKKEP)
        terim_y += line_h_terim

    # Çizgi
    cizgi_y = terim_y + 16
    draw.line([(kenar, cizgi_y), (GENISLIK - kenar, cizgi_y)], fill=RENK_KIREC_BORDER, width=2)

    # Tanım Başlığı & Metni
    tanim_baslik_y = cizgi_y + 26
    draw.text((kenar, tanim_baslik_y), "// HUKUKİ VE TEKNİK TANIM:", font=make_image._font_yukle(FONT_MONO_BOLD, 18), fill=RENK_KURSUN)

    # Tanım Gövdesi
    f_tanim = make_image._font_yukle(FONT_SANS_MEDIUM, 31)
    indent_px = 56
    tanim_kelimeler = tanim_metni.split()
    tanim_satirlar = []
    curr_satir = []
    for w in tanim_kelimeler:
        test_s = (" ".join(curr_satir + [w])) if curr_satir else w
        max_w = (kullanilabilir_w - indent_px) if len(tanim_satirlar) == 0 else kullanilabilir_w
        if draw.textbbox((0, 0), test_s, font=f_tanim)[2] <= max_w:
            curr_satir.append(w)
        else:
            if curr_satir:
                tanim_satirlar.append(" ".join(curr_satir))
            curr_satir = [w]
    if curr_satir:
        tanim_satirlar.append(" ".join(curr_satir))

    ty = tanim_baslik_y + 38

    # Çift Tırnak Filigranı (%50 küçültülmüş 70pt, tam paragraf başı boşluğuna denk gelir)
    f_quote = make_image._font_yukle(FONT_FRAUNCES, 70)
    overlay_draw.text((kenar + 4, ty - 15), "“", font=f_quote, fill=(18, 19, 22, 55))

    for i, s in enumerate(tanim_satirlar):
        x_pos = kenar + (indent_px if i == 0 else 0)
        draw.text((x_pos, ty), s, font=f_tanim, fill=RENK_MUREKKEP)
        ty += 46

    # Püf Maddeleri Hesabı
    f_puf_etiket = make_image._font_yukle(FONT_MONO_BOLD, 20)
    f_puf_madde_baslik = make_image._font_yukle(FONT_SANS_BOLD, 27)
    f_puf_govde = make_image._font_yukle(FONT_SANS_MEDIUM, 26)

    if isinstance(puf_maddeleri, list):
        maddeler = puf_maddeleri
    else:
        maddeler = [str(puf_maddeleri)]

    puf_icerik_h = 0
    parsed_maddeler = []
    for m in maddeler:
        m_str = str(m).strip()
        if ":" in m_str:
            b, a = m_str.split(":", 1)
            b = b.strip() + ":"
            a = a.strip()
        else:
            b = "◆"
            a = m_str
        b_satirlar = make_image._metin_sar(b, f_puf_madde_baslik, kullanilabilir_w - 60, draw)
        a_satirlar = make_image._metin_sar(a, f_puf_govde, kullanilabilir_w - 60, draw)
        puf_icerik_h += (len(b_satirlar) * 35) + (len(a_satirlar) * 35) + 14
        parsed_maddeler.append((b_satirlar, a_satirlar))

    h_kutu = 48 + puf_icerik_h + 16
    kutu_y = alt_y - 24 - h_kutu
    if kutu_y < ty + 30:
        kutu_y = ty + 30

    # Kutuyu ve içini çiz
    draw.rounded_rectangle([(kenar, kutu_y), (GENISLIK - kenar, kutu_y + h_kutu)], radius=12, fill=RENK_KIREC_KUTU, outline=RENK_KIREC_BORDER, width=1)
    draw.rounded_rectangle([(kenar, kutu_y), (kenar + 6, kutu_y + h_kutu)], radius=2, fill=RENK_LOGO_KIRMIZI)
    draw.text((kenar + 28, kutu_y + 18), "YATIRIMCI GÖZÜYLE DEĞERLENDİRME:", font=f_puf_etiket, fill=RENK_LOGO_KIRMIZI)

    py = kutu_y + 54
    for b_satirlar, a_satirlar in parsed_maddeler:
        for s in b_satirlar:
            draw.text((kenar + 28, py), s, font=f_puf_madde_baslik, fill=RENK_MUREKKEP)
            py += 35
        for s in a_satirlar:
            draw.text((kenar + 28, py), s, font=f_puf_govde, fill=(45, 48, 55))
            py += 35
        py += 12

    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


# =============================================================================
# 2. FORMAT: NEDİR DOĞRUSU? (YANLIŞ / DOĞRU)
# =============================================================================
def hazirla_taban_nedir_dogrusu() -> Tuple[Image.Image, int, int]:
    w, h = GENISLIK, YUKSEKLIK
    arr = np.zeros((h, w, 3), dtype=np.uint8)

    r1, g1, b1 = RENK_LOGO_KIRMIZI  # 196, 3, 15 (#C4030F - Tam Logo Kırmızısı)
    r2, g2, b2 = 255, 255, 255      # Saf Beyaz

    y_start = 490
    y_end = 650

    arr[:y_start, :] = [r1, g1, b1]

    for y in range(y_start, y_end):
        t = (y - y_start) / (y_end - y_start)
        s = t * t * (3 - 2 * t)  # Smoothstep
        r = int(r1 + (r2 - r1) * s)
        g = int(g1 + (r2 - g1) * s)
        b = int(b1 + (r2 - b1) * s)
        arr[y, :] = [r, g, b]

    arr[y_end:, :] = [r2, g2, b2]

    canvas = Image.fromarray(arr)

    # Alt beyaz kısma hafif pafta filigranı uygula
    overlay_filigran = Image.new("RGB", (GENISLIK, YUKSEKLIK), (255, 255, 255))
    overlay_filigran = make_image._filigran_uygula(overlay_filigran, acik_zemin=True)
    f_arr = np.array(overlay_filigran)
    canvas_arr = np.array(canvas)
    canvas_arr[y_end:, :, :] = f_arr[y_end:, :, :]
    return Image.fromarray(canvas_arr), y_start, y_end


def uret_nedir_dogrusu(cikti_yolu: Path, konu: str, yanlis_metin: str, dogru_metin: str, altin_kural: str) -> Path:
    canvas, y_start, y_end = hazirla_taban_nedir_dogrusu()
    draw = ImageDraw.Draw(canvas)

    yer = make_image._yerlesim()
    kenar = yer["kenar"]
    kullanilabilir_w = GENISLIK - (2 * kenar)
    ku = yer["kronik_ust"]

    # Header: Kırmızı zemin üzerinde beyaz logo + DOĞRU BİLİNEN YANLIŞLAR rozeti
    konu_baslik = (konu or "HUKUK & GERÇEK").upper()
    rozet_metni = f"DOĞRU BİLİNEN YANLIŞLAR // {konu_baslik}"
    make_image._rozet_ciz(
        draw, kenar, ku, rozet_metni,
        bg_color=RENK_MUREKKEP, fg_color=RENK_BEYAZ, font_boyut=19
    )
    make_image._logo_yerlestir(
        canvas,
        beyaz=True,
        y=ku - 5,
        lw=285,
        golge=True,
        kirmizi_zemin=True,
    )

    # 1. YANLIŞ KISMI (Kırmızı alanda dev beyaz Fraunces tırnaklı metin)
    yanlis_formatli = (yanlis_metin or "").strip()
    if yanlis_formatli and not yanlis_formatli.startswith("“") and not yanlis_formatli.startswith('"'):
        yanlis_formatli = f'“{yanlis_formatli}”'

    kirmizi_alan_h = y_start - (ku + 65)

    # Dinamik punto hesabı (40 - 54 arası)
    punto_yanlis = 54
    best_yanlis_satirlar = []
    best_yanlis_leading = 66
    for p in range(54, 38, -2):
        f_test = make_image._font_yukle(FONT_FRAUNCES, p)
        leading = int(p * 1.25)
        lines = make_image._metin_sar(yanlis_formatli, f_test, kullanilabilir_w, draw)
        if len(lines) * leading <= kirmizi_alan_h:
            punto_yanlis = p
            best_yanlis_leading = leading
            best_yanlis_satirlar = lines
            break
    else:
        punto_yanlis = 40
        best_yanlis_leading = 50
        f_test = make_image._font_yukle(FONT_FRAUNCES, punto_yanlis)
        best_yanlis_satirlar = make_image._metin_sar(yanlis_formatli, f_test, kullanilabilir_w, draw)

    f_yanlis = make_image._font_yukle(FONT_FRAUNCES, punto_yanlis)
    h_yanlis = len(best_yanlis_satirlar) * best_yanlis_leading
    yanlis_y = ku + 65 + max(10, (kirmizi_alan_h - h_yanlis) // 2)

    for s in best_yanlis_satirlar:
        draw.text((kenar, yanlis_y), s, font=f_yanlis, fill=(255, 255, 255))
        yanlis_y += best_yanlis_leading

    # 2. DOĞRU KISMI (Soft geçişin bittiği beyaz alanda metin)
    f_kural_baslik = make_image._font_yukle(FONT_MONO_BOLD, 20)
    f_kural_govde = make_image._font_yukle(FONT_SANS_BOLD, 29)
    kural_satirlar = make_image._metin_sar(altin_kural or "", f_kural_govde, kullanilabilir_w - 52, draw)
    if len(kural_satirlar) > 3:
        f_kural_govde = make_image._font_yukle(FONT_SANS_BOLD, 26)
        kural_satirlar = make_image._metin_sar(altin_kural or "", f_kural_govde, kullanilabilir_w - 52, draw)

    h_kutu = 48 + (len(kural_satirlar) * 40) + 20
    alt_bar_y = yer["alt_bar"]
    beyaz_alan_h = alt_bar_y - (y_end + 30)

    # Doğru gövde metnini dinamik punto ile sığdır
    punto_dogru = 34
    best_dogru_satirlar = []
    best_dogru_leading = 50
    for p in range(34, 24, -2):
        f_test = make_image._font_yukle(FONT_SANS_MEDIUM, p)
        leading = int(p * 1.45)
        lines = make_image._metin_sar(dogru_metin or "", f_test, kullanilabilir_w, draw)
        if (len(lines) * leading + 38 + h_kutu) <= beyaz_alan_h:
            punto_dogru = p
            best_dogru_leading = leading
            best_dogru_satirlar = lines
            break
    else:
        punto_dogru = 24
        best_dogru_leading = 35
        f_test = make_image._font_yukle(FONT_SANS_MEDIUM, punto_dogru)
        best_dogru_satirlar = make_image._metin_sar(dogru_metin or "", f_test, kullanilabilir_w, draw)

    f_dogru_govde = make_image._font_yukle(FONT_SANS_MEDIUM, punto_dogru)
    h_dogru = len(best_dogru_satirlar) * best_dogru_leading
    toplam_alt_h = h_dogru + 38 + h_kutu
    alt_bosluk = max(10, (beyaz_alan_h - toplam_alt_h) // 2)
    curr_y = y_end + 30 + alt_bosluk

    # Doğru metni (Mürekkep siyahı)
    for s in best_dogru_satirlar:
        draw.text((kenar, curr_y), s, font=f_dogru_govde, fill=RENK_MUREKKEP)
        curr_y += best_dogru_leading
    curr_y += 38

    # EDM Altın Kuralı Kartı
    draw.rounded_rectangle(
        [(kenar, curr_y), (GENISLIK - kenar, curr_y + h_kutu)],
        radius=12,
        fill=RENK_MUREKKEP,
        outline=(45, 48, 56),
        width=1,
    )
    draw.rounded_rectangle(
        [(kenar, curr_y), (kenar + 6, curr_y + h_kutu)],
        radius=2,
        fill=RENK_LOGO_KIRMIZI,
    )
    draw.text((kenar + 28, curr_y + 18), "EDM ALTIN KURALI:", font=f_kural_baslik, fill=RENK_LOGO_KIRMIZI)
    ky = curr_y + 52
    for s in kural_satirlar:
        draw.text((kenar + 28, ky), s, font=f_kural_govde, fill=RENK_BEYAZ)
        ky += 40

    # Footer
    draw.line([(kenar, alt_bar_y), (GENISLIK - kenar, alt_bar_y)], fill=RENK_CIZGI_ACIK, width=1)
    draw.text((kenar, alt_bar_y + 26), "EDM YAPI & GAYRİMENKUL // DOĞRU BİLİNEN YANLIŞLAR", font=make_image._font_yukle(FONT_MONO, 19), fill=RENK_KURSUN)
    draw.text((GENISLIK - kenar - 170, alt_bar_y + 26), "HUKUKİ GERÇEK", font=make_image._font_yukle(FONT_MONO_BOLD, 19), fill=RENK_MUREKKEP)

    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


# =============================================================================
# 3. FORMAT: GERÇEK HUKUKİ VAKA ANALİZİ (SLAYT 1 & SLAYT 2)
# =============================================================================
def uret_vaka_slayt1(cikti_yolu: Path, vaka_kodu: str, yargitay_kaynak: str, manset: str, olay_detay: str, sayfa_no: str = "01 / 02") -> Path:
    canvas = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_MUREKKEP)
    canvas = make_image._filigran_uygula(canvas, acik_zemin=False)
    draw = ImageDraw.Draw(canvas)

    yer = make_image._yerlesim()
    kenar = yer["kenar"]
    kullanilabilir_w = GENISLIK - (2 * kenar)
    ku = yer["kronik_ust"]

    logo_w = 285
    logo_x = GENISLIK - kenar - logo_w
    azami_rozet_w = logo_x - kenar - 30
    rozet_metni = f"GERÇEK HUKUKİ VAKA // {vaka_kodu.upper()}"
    make_image._rozet_ciz(draw, kenar, ku, rozet_metni, bg_color=(32, 35, 42), fg_color=RENK_BEYAZ, font_boyut=20, max_w=azami_rozet_w)
    make_image._logo_yerlestir(canvas, beyaz=True, y=ku - 5, lw=logo_w, golge=True, kirmizi_zemin=False)

    alt_y = yer["alt_bar"]
    draw.line([(kenar, alt_y), (GENISLIK - kenar, alt_y)], fill=RENK_CIZGI_KOYU, width=1)
    f_kaynak_alt = make_image._font_yukle(FONT_MONO, 17)
    kaynak_metni = f"KAYNAK: {yargitay_kaynak}"
    if len(kaynak_metni) > 55:
        kaynak_metni = kaynak_metni[:52] + "…"
    draw.text((kenar, alt_y + 26), kaynak_metni, font=f_kaynak_alt, fill=RENK_KURSUN)
    draw.text((GENISLIK - kenar - 90, alt_y + 26), sayfa_no, font=make_image._font_yukle(FONT_MONO_BOLD, 20), fill=RENK_BEYAZ)

    ust_sinir = yer["ust"] - 15
    kaydir_kutusu_h = 64
    kaydir_y = alt_y - 24 - kaydir_kutusu_h
    kullanilabilir_orta_h = kaydir_y - 24 - ust_sinir

    punto_manset = 76
    punto_olay = 34
    while punto_manset >= 52:
        f_manset_test = make_image._font_yukle(FONT_FRAUNCES, punto_manset)
        leading_manset_test = punto_manset + 16
        manset_satirlar_test = make_image._metin_sar(manset, f_manset_test, kullanilabilir_w, draw)
        h_manset_test = len(manset_satirlar_test) * leading_manset_test

        f_olay_test = make_image._font_yukle(FONT_SANS_MEDIUM, punto_olay)
        leading_olay_test = punto_olay + 18
        olay_satirlar_test = make_image._metin_sar(olay_detay, f_olay_test, kullanilabilir_w, draw)
        h_olay_test = len(olay_satirlar_test) * leading_olay_test

        if (34 + h_manset_test + 28 + 32 + h_olay_test) <= kullanilabilir_orta_h:
            punto_manset_final = punto_manset
            leading_manset = leading_manset_test
            manset_satirlar = manset_satirlar_test
            punto_olay_final = punto_olay
            leading_olay = leading_olay_test
            olay_satirlar = olay_satirlar_test
            break
        if punto_manset > 56:
            punto_manset -= 4
        elif punto_olay > 26:
            punto_olay -= 2
        else:
            punto_manset -= 4
    else:
        punto_manset_final = 52
        leading_manset = 64
        punto_olay_final = 26
        leading_olay = 38
        f_m = make_image._font_yukle(FONT_FRAUNCES, punto_manset_final)
        f_o = make_image._font_yukle(FONT_SANS_MEDIUM, punto_olay_final)
        manset_satirlar = make_image._metin_sar(manset, f_m, kullanilabilir_w, draw)
        olay_satirlar = make_image._metin_sar(olay_detay, f_o, kullanilabilir_w, draw)

    f_manset = make_image._font_yukle(FONT_FRAUNCES, punto_manset_final)
    f_etiket = make_image._font_yukle(FONT_MONO_BOLD, 21)
    f_olay = make_image._font_yukle(FONT_SANS_MEDIUM, punto_olay_final)

    h_manset = len(manset_satirlar) * leading_manset
    h_olay = len(olay_satirlar) * leading_olay
    toplam_orta_h = 34 + h_manset + 28 + 32 + h_olay
    curr_y = ust_sinir + min(36, max(0, kullanilabilir_orta_h - toplam_orta_h) // 3)

    emsal_etiket = f"EMSAL İÇTİHAT // {yargitay_kaynak.upper()}"
    f_kaynak_ust = make_image._font_yukle(FONT_MONO_BOLD, 20)
    bbox_emsal = draw.textbbox((0, 0), emsal_etiket, font=f_kaynak_ust)
    if (bbox_emsal[2] - bbox_emsal[0]) > kullanilabilir_w:
        f_kaynak_ust = make_image._font_yukle(FONT_MONO_BOLD, 16)
        bbox_emsal = draw.textbbox((0, 0), emsal_etiket, font=f_kaynak_ust)
        if (bbox_emsal[2] - bbox_emsal[0]) > kullanilabilir_w:
            emsal_etiket = emsal_etiket[:52].rstrip() + "…"

    make_image._rozet_ciz(draw, kenar, curr_y, emsal_etiket, bg_color=RENK_LOGO_KIRMIZI, fg_color=RENK_BEYAZ, font_boyut=17, max_w=kullanilabilir_w)
    curr_y += 46

    for s in manset_satirlar:
        draw.text((kenar, curr_y), s, font=f_manset, fill=RENK_BEYAZ)
        curr_y += leading_manset
    curr_y += 16

    draw.line([(kenar, curr_y), (GENISLIK - kenar, curr_y)], fill=RENK_CIZGI_KOYU, width=2)
    curr_y += 28

    draw.text((kenar, curr_y), "// MAHKEMEYE YANSIYAN OLAY:", font=f_etiket, fill=RENK_KURSUN)
    curr_y += 36
    for s in olay_satirlar:
        draw.text((kenar, curr_y), s, font=f_olay, fill=(225, 230, 240))
        curr_y += leading_olay

    draw.rounded_rectangle([(kenar, kaydir_y), (GENISLIK - kenar, kaydir_y + kaydir_kutusu_h)], radius=10, fill=RENK_LOGO_KIRMIZI)
    draw.text((kenar + 24, kaydir_y + 18), "KAYDIRIN // YARGITAY HÜKMÜ VE ALINACAK DERS ››", font=make_image._font_yukle(FONT_MONO_BOLD, 20), fill=RENK_BEYAZ)

    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


def uret_vaka_slayt2(cikti_yolu: Path, vaka_kodu: str, yargitay_hukmu: str, cikarilacak_ders: str, sayfa_no: str = "02 / 02") -> Path:
    canvas = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_MUREKKEP)
    canvas = make_image._filigran_uygula(canvas, acik_zemin=False)
    draw = ImageDraw.Draw(canvas)

    yer = make_image._yerlesim()
    kenar = yer["kenar"]
    kullanilabilir_w = GENISLIK - (2 * kenar)
    ku = yer["kronik_ust"]

    logo_w = 285
    logo_x = GENISLIK - kenar - logo_w
    azami_rozet_w = logo_x - kenar - 30
    rozet_metni = f"GERÇEK HUKUKİ VAKA // {vaka_kodu.upper()} - KARAR"
    make_image._rozet_ciz(draw, kenar, ku, rozet_metni, bg_color=RENK_LOGO_KIRMIZI, fg_color=RENK_BEYAZ, font_boyut=20, max_w=azami_rozet_w)
    make_image._logo_yerlestir(canvas, beyaz=True, y=ku - 5, lw=logo_w, golge=True, kirmizi_zemin=False)

    alt_y = yer["alt_bar"]
    draw.line([(kenar, alt_y), (GENISLIK - kenar, alt_y)], fill=RENK_CIZGI_KOYU, width=1)
    draw.text((kenar, alt_y + 26), "EDM HUKUK ARŞİVİ // EMSAL İÇTİHAT DOSYASI", font=make_image._font_yukle(FONT_MONO, 18), fill=RENK_KURSUN)
    draw.text((GENISLIK - kenar - 90, alt_y + 26), sayfa_no, font=make_image._font_yukle(FONT_MONO_BOLD, 20), fill=RENK_LOGO_KIRMIZI)

    punto_ders = 29
    leading_ders = 41
    f_ders_govde = make_image._font_yukle(FONT_SANS_BOLD, punto_ders)
    ders_satirlar = make_image._metin_sar(cikarilacak_ders, f_ders_govde, kullanilabilir_w - 56, draw)

    if len(ders_satirlar) > 3:
        punto_ders = 25
        leading_ders = 35
        f_ders_govde = make_image._font_yukle(FONT_SANS_BOLD, punto_ders)
        ders_satirlar = make_image._metin_sar(cikarilacak_ders, f_ders_govde, kullanilabilir_w - 56, draw)

    f_ders_etiket = make_image._font_yukle(FONT_MONO_BOLD, 21)
    h_kutu = 54 + (len(ders_satirlar) * leading_ders) + 20
    kutu_alt_bosluk = 26
    kutu_y = alt_y - kutu_alt_bosluk - h_kutu

    ust_sinir = yer["ust"] - 10
    mevcut_hukum_h = (kutu_y - 28) - ust_sinir

    punto_hukum = 54
    while punto_hukum >= 30:
        f_hukum_test = make_image._font_yukle(FONT_FRAUNCES, punto_hukum)
        leading_hukum_test = int(punto_hukum * 1.32)
        hukum_satirlar_test = make_image._metin_sar(yargitay_hukmu, f_hukum_test, kullanilabilir_w, draw)
        h_hukum_test = len(hukum_satirlar_test) * leading_hukum_test
        if (36 + 22 + h_hukum_test) <= mevcut_hukum_h:
            punto_hukum_final = punto_hukum
            leading_hukum = leading_hukum_test
            hukum_satirlar = hukum_satirlar_test
            h_hukum = h_hukum_test
            break
        punto_hukum -= 2
    else:
        punto_hukum_final = 30
        leading_hukum = 42
        f_hukum_test = make_image._font_yukle(FONT_FRAUNCES, punto_hukum_final)
        hukum_satirlar = make_image._metin_sar(yargitay_hukmu, f_hukum_test, kullanilabilir_w, draw)
        h_hukum = len(hukum_satirlar) * leading_hukum

    f_etiket = make_image._font_yukle(FONT_MONO_BOLD, 22)
    f_hukum = make_image._font_yukle(FONT_FRAUNCES, punto_hukum_final)

    hukum_blok_h = 36 + 18 + h_hukum
    curr_y = ust_sinir + min(36, max(0, mevcut_hukum_h - hukum_blok_h) // 3)
    make_image._rozet_ciz(draw, kenar, curr_y, "YARGITAY'IN VERDİĞİ KESİN HÜKÜM", bg_color=RENK_LOGO_KIRMIZI, fg_color=RENK_BEYAZ, font_boyut=17, max_w=kullanilabilir_w)
    curr_y += 44

    for s in hukum_satirlar:
        draw.text((kenar, curr_y), s, font=f_hukum, fill=RENK_BEYAZ)
        curr_y += leading_hukum

    draw.rounded_rectangle([(kenar, kutu_y), (GENISLIK - kenar, kutu_y + h_kutu)], radius=12, fill=(28, 32, 42), outline=(55, 65, 85), width=1)
    draw.rounded_rectangle([(kenar, kutu_y), (kenar + 6, kutu_y + h_kutu)], radius=2, fill=RENK_ALTIN)
    draw.text((kenar + 28, kutu_y + 18), "BU DAVADAN ÇIKARILACAK DERS:", font=f_ders_etiket, fill=RENK_ALTIN)

    dy = kutu_y + 52
    for s in ders_satirlar:
        draw.text((kenar + 28, dy), s, font=f_ders_govde, fill=RENK_BEYAZ)
        dy += leading_ders

    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


# =============================================================================
# 4. FORMAT: NET CEVAP REHBERİ / SORU-CEVAP
# =============================================================================
def uret_net_cevap_tek_kare(cikti_yolu: Path, kategori: str, soru: str, net_cevap: str, aciklama: str, tavsiye_metin: str) -> Path:
    canvas = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_BEYAZ)
    canvas = make_image._filigran_uygula(canvas, acik_zemin=True)

    yer = make_image._yerlesim()
    kenar = yer["kenar"]
    kullanilabilir_w = GENISLIK - (2 * kenar)
    ku = yer["kronik_ust"]

    overlay = Image.new("RGBA", (GENISLIK, YUKSEKLIK), (255, 255, 255, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    f_soru_isareti = make_image._font_yukle(FONT_FRAUNCES, 320)
    overlay_draw.text((GENISLIK - 300, ku + 75), "?", font=f_soru_isareti, fill=(18, 19, 22, 20))

    draw = ImageDraw.Draw(canvas)

    logo_w = 285
    logo_x = GENISLIK - kenar - logo_w
    azami_rozet_w = logo_x - kenar - 30
    rozet_metni = f"NET CEVAP // {kategori.upper()}"
    make_image._rozet_ciz(draw, kenar, ku, rozet_metni, bg_color=RENK_MUREKKEP, fg_color=RENK_BEYAZ, font_boyut=20, max_w=azami_rozet_w)
    make_image._logo_yerlestir(canvas, beyaz=False, y=ku - 5, lw=logo_w, golge=False, kirmizi_zemin=False)

    alt_y = yer["alt_bar"]
    draw.line([(kenar, alt_y), (GENISLIK - kenar, alt_y)], fill=RENK_CIZGI_ACIK, width=1)
    draw.text((kenar, alt_y + 26), "EDM YAPI & GAYRİMENKUL // NET CEVAP REHBERİ", font=make_image._font_yukle(FONT_MONO, 19), fill=RENK_KURSUN)
    draw.text((GENISLIK - kenar - 170, alt_y + 26), "TEK KARE / CEVAP", font=make_image._font_yukle(FONT_MONO_BOLD, 19), fill=RENK_MUREKKEP)

    punto_tavsiye = 30
    leading_tavsiye = 42
    f_tavsiye_govde = make_image._font_yukle(FONT_SANS_BOLD, punto_tavsiye)
    tavsiye_satirlar = make_image._metin_sar(tavsiye_metin, f_tavsiye_govde, kullanilabilir_w - 90, draw)

    if len(tavsiye_satirlar) > 3:
        punto_tavsiye = 26
        leading_tavsiye = 36
        f_tavsiye_govde = make_image._font_yukle(FONT_SANS_BOLD, punto_tavsiye)
        tavsiye_satirlar = make_image._metin_sar(tavsiye_metin, f_tavsiye_govde, kullanilabilir_w - 90, draw)

    h_kutu = 28 + (len(tavsiye_satirlar) * leading_tavsiye) + 24
    kutu_alt_bosluk = 26
    kutu_y = alt_y - kutu_alt_bosluk - h_kutu

    ust_sinir = yer["ust"] - 15
    mevcut_orta_h = (kutu_y - 28) - ust_sinir

    punto_soru = 84
    punto_aciklama = 36
    while punto_soru >= 52:
        f_soru_test = make_image._font_yukle(FONT_FRAUNCES, punto_soru)
        leading_soru_test = punto_soru + 16
        soru_satirlar_test = make_image._metin_sar(soru, f_soru_test, kullanilabilir_w - 60, draw)
        h_soru_test = len(soru_satirlar_test) * leading_soru_test

        f_aciklama_test = make_image._font_yukle(FONT_SANS_MEDIUM, punto_aciklama)
        leading_aciklama_test = punto_aciklama + 16
        aciklama_satirlar_test = make_image._metin_sar(aciklama, f_aciklama_test, kullanilabilir_w, draw)
        h_aciklama_test = len(aciklama_satirlar_test) * leading_aciklama_test

        if (h_soru_test + 26 + 54 + 30 + h_aciklama_test) <= mevcut_orta_h:
            punto_soru_final = punto_soru
            leading_soru = leading_soru_test
            soru_satirlar = soru_satirlar_test
            punto_aciklama_final = punto_aciklama
            leading_aciklama = leading_aciklama_test
            aciklama_satirlar = aciklama_satirlar_test
            break
        if punto_soru > 60:
            punto_soru -= 4
        elif punto_aciklama > 26:
            punto_aciklama -= 2
        else:
            punto_soru -= 4
    else:
        punto_soru_final = 52
        leading_soru = 64
        punto_aciklama_final = 26
        leading_aciklama = 38
        f_s = make_image._font_yukle(FONT_FRAUNCES, punto_soru_final)
        f_a = make_image._font_yukle(FONT_SANS_MEDIUM, punto_aciklama_final)
        soru_satirlar = make_image._metin_sar(soru, f_s, kullanilabilir_w - 60, draw)
        aciklama_satirlar = make_image._metin_sar(aciklama, f_a, kullanilabilir_w, draw)

    f_soru = make_image._font_yukle(FONT_FRAUNCES, punto_soru_final)
    f_aciklama = make_image._font_yukle(FONT_SANS_MEDIUM, punto_aciklama_final)

    h_soru = len(soru_satirlar) * leading_soru
    h_aciklama = len(aciklama_satirlar) * leading_aciklama
    toplam_orta_h = h_soru + 26 + 54 + 30 + h_aciklama
    curr_y = ust_sinir + min(36, max(0, mevcut_orta_h - toplam_orta_h) // 3)

    for s in soru_satirlar:
        draw.text((kenar, curr_y), s, font=f_soru, fill=RENK_MUREKKEP)
        curr_y += leading_soru
    curr_y += 26

    make_image._rozet_ciz(draw, kenar, curr_y, net_cevap, bg_color=RENK_MUREKKEP, fg_color=RENK_BEYAZ, font_boyut=22, max_w=kullanilabilir_w)
    curr_y += 58

    for s in aciklama_satirlar:
        draw.text((kenar, curr_y), s, font=f_aciklama, fill=RENK_MUREKKEP)
        curr_y += leading_aciklama

    draw.rounded_rectangle([(kenar, kutu_y), (GENISLIK - kenar, kutu_y + h_kutu)], radius=10, fill=(247, 248, 250), outline=(220, 222, 228), width=1)
    draw.rounded_rectangle([(kenar, kutu_y), (kenar + 6, kutu_y + h_kutu)], radius=2, fill=RENK_LOGO_KIRMIZI)

    f_unlem = make_image._font_yukle(FONT_FRAUNCES, 60)
    bbox = f_unlem.getbbox("!")
    uw = bbox[2] - bbox[0]
    uh = bbox[3] - bbox[1]
    kutu_ortasi_y = kutu_y + (h_kutu // 2)
    sag_x = GENISLIK - kenar - 42
    overlay_draw.text((sag_x - (uw // 2), kutu_ortasi_y - (uh // 2) - 4), "!", font=f_unlem, fill=(196, 3, 15, 42))

    ty = kutu_y + 24
    for s in tavsiye_satirlar:
        draw.text((kenar + 28, ty), s, font=f_tavsiye_govde, fill=(28, 30, 36))
        ty += leading_tavsiye

    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


# =============================================================================
# OTOMATİK ŞABLON SEÇİCİ VE ÜRETİCİ DİSPATCHER
# =============================================================================
def slaytlari_uret(
    veri: Dict[str, Any],
    cikti_dizini: Optional[Path] = None,
    cikti_onek: str = "post",
    format_turu: Optional[str] = None,
) -> List[Path]:
    """İçerik verisini inceleyip 4 yeni formattan en uygun olanı seçerek slaytları üretir.
    Hem doğrudan yeni format şemalarını (sozluk, nedir_dogrusu, net_cevap, vaka) hem de geriye dönük uyumluluk adaptörünü destekler.
    """
    if cikti_dizini is None:
        cikti_dizini = config.yol_al("data/output/gonderiler")
    cikti_dizini.mkdir(parents=True, exist_ok=True)

    format_turu = str(format_turu or veri.get("format_turu") or veri.get("format") or "").lower()
    kategori = veri.get("kategori") or veri.get("kategori_kodu", "TAPU VE HUKUK").replace("_", " ")
    brief = veri.get("_brief", {}) or {}

    # =========================================================================
    # A) DOĞRUDAN YENİ FORMAT ŞEMALARI & GÜÇLENDİRİLMİŞ ÇIKARIM
    # =========================================================================
    # 1. DOĞRUDAN SÖZLÜK
    if format_turu in ("sozluk", "sozluk_uret") or ("terim" in veri and ("tanim_metni" in veri or "tanim" in veri)):
        p1 = cikti_dizini / f"{cikti_onek}_sozluk.jpg"
        terim = (veri.get("terim") or veri.get("manset_vurgu") or veri.get("manset_parca_1") or "GAYRİMENKUL HUKUKU").strip()
        tanim = (veri.get("tanim_metni") or veri.get("tanim") or veri.get("spot") or "").strip()
        maddeler = veri.get("puf_maddeleri") or veri.get("maddeler") or []
        if not maddeler:
            s3 = veri.get("slayt_3_cozum", {})
            if isinstance(s3, dict):
                for m in s3.get("maddeler", [])[:3]:
                    if isinstance(m, dict):
                        maddeler.append(f"{m.get('baslik', '')}: {m.get('aciklama', '')}".strip(": "))
                    else:
                        maddeler.append(str(m))
        if not maddeler:
            maddeler = ["Mevzuat Uyarısı: Kanuni süreleri kaçırmamak adına yasal takvimleri takip edin."]
        uret_sozluk(p1, terim=terim, kategori=kategori, tanim_metni=tanim, puf_maddeleri=maddeler)
        log.info("Yeni Format Üretildi (NATIVE SÖZLÜK): %s", p1)
        return [p1]

    # 2. DOĞRUDAN NEDİR DOĞRUSU?
    if format_turu in ("nedir_dogrusu", "dogrusu", "yaygin_yanlis") or ("yanlis_metin" in veri and "dogru_metin" in veri):
        p1 = cikti_dizini / f"{cikti_onek}_nedir_dogrusu.jpg"
        konu = (veri.get("konu") or veri.get("rozet_metni") or kategori or "HUKUK & GERÇEK").strip()

        yanlis = (veri.get("yanlis_metin") or "").strip()
        if not yanlis:
            s2 = veri.get("slayt_2_detay", {})
            if isinstance(s2, dict):
                k1 = s2.get("kart_1", {})
                if isinstance(k1, dict) and "aciklama" in k1:
                    yanlis = k1.get("aciklama", "").strip()
                elif "kartlar" in s2 and s2["kartlar"]:
                    yanlis = s2["kartlar"][0].get("aciklama", "").strip()
            if not yanlis:
                yanlis = f"{veri.get('manset_parca_1', '')} {veri.get('manset_vurgu', '')}".strip()
            if not yanlis or len(yanlis) < 10:
                yanlis = (veri.get("spot") or "Tapu senedi her şeyin tek ve kesin garantisidir.")[:120].strip()

        dogru = (veri.get("dogru_metin") or "").strip()
        if not dogru:
            s2 = veri.get("slayt_2_detay", {})
            if isinstance(s2, dict):
                k2 = s2.get("kart_2", {})
                if isinstance(k2, dict) and "aciklama" in k2:
                    dogru = k2.get("aciklama", "").strip()
                elif "kartlar" in s2 and len(s2["kartlar"]) > 1:
                    dogru = s2["kartlar"][1].get("aciklama", "").strip()
            if not dogru:
                dogru = (veri.get("spot") or "").strip()

        altin = (veri.get("altin_kural") or "").strip()
        if not altin:
            s3 = veri.get("slayt_3_cozum", {})
            if isinstance(s3, dict):
                maddeler = s3.get("maddeler", [])
                if maddeler:
                    m0 = maddeler[0]
                    if isinstance(m0, dict):
                        altin = f"{m0.get('baslik', '')}: {m0.get('aciklama', '')}".strip(": ")
                    else:
                        altin = str(m0).strip()
            if not altin:
                cta = veri.get("slayt_4_cta", {})
                if isinstance(cta, dict) and "aciklama" in cta:
                    altin = cta.get("aciklama", "").strip()
            if not altin:
                altin = "Noter onayı ve tapu sicil şerhi olmadan hiçbir sözlü taahhüde güvenmeyin."

        uret_nedir_dogrusu(p1, konu=konu, yanlis_metin=yanlis, dogru_metin=dogru, altin_kural=altin)
        log.info("Yeni Format Üretildi (NATIVE NEDİR DOĞRUSU): %s", p1)
        return [p1]

    # 3. DOĞRUDAN NET CEVAP REHBERİ
    if format_turu in ("net_cevap", "soru", "kim_hakli") or ("soru" in veri and "net_cevap" in veri and "aciklama" in veri):
        p1 = cikti_dizini / f"{cikti_onek}_net_cevap.jpg"
        soru = (veri.get("soru") or f"{veri.get('manset_parca_1', '')} {veri.get('manset_vurgu', '')}").strip()
        if not soru.endswith("?"):
            soru += "?"
        net_cevap = (veri.get("net_cevap") or veri.get("manset_parca_2") or "CEVAP: ŞARTA BAĞLIDIR").strip()
        if not net_cevap.upper().startswith("CEVAP"):
            net_cevap = f"CEVAP: {net_cevap.upper()}"
        aciklama = (veri.get("aciklama") or veri.get("spot") or "").strip()
        tavsiye = (veri.get("tavsiye_metin") or veri.get("tavsiye") or "").strip()
        if not tavsiye:
            s3 = veri.get("slayt_3_cozum", {})
            if isinstance(s3, dict):
                m = s3.get("maddeler", [])
                if m:
                    tavsiye = (m[0].get("aciklama", "") if isinstance(m[0], dict) else str(m[0])).strip()
        if not tavsiye:
            tavsiye = "İşlem yapmadan önce belediye imar ve tapu müdürlüğünden teyit alın."
        uret_net_cevap_tek_kare(p1, kategori=kategori, soru=soru, net_cevap=net_cevap, aciklama=aciklama, tavsiye_metin=tavsiye)
        log.info("Yeni Format Üretildi (NATIVE NET CEVAP): %s", p1)
        return [p1]

    # 4. DOĞRUDAN VAKA ANALİZİ
    if format_turu in ("vaka", "emsal_karar") or ("yargitay_hukmu" in veri and "cikarilacak_ders" in veri):
        p1 = cikti_dizini / f"{cikti_onek}_vaka_s1.jpg"
        p2 = cikti_dizini / f"{cikti_onek}_vaka_s2.jpg"
        vaka_kodu = (veri.get("vaka_kodu") or veri.get("konu_kodu") or "01 / EMSAL DOSYA").strip()
        kaynak = (veri.get("yargitay_kaynak") or veri.get("yasal_dayanak") or brief.get("mevzuat") or "Yargıtay Emsal İçtihadı").strip()
        manset = (veri.get("manset") or f"{veri.get('manset_parca_1', '')} {veri.get('manset_vurgu', '')} {veri.get('manset_parca_2', '')}").strip()
        if not manset or len(manset) < 10:
            manset = (veri.get("spot") or "")[:75].strip()
        olay = (veri.get("olay_detay") or veri.get("spot") or "").strip()
        hukum = (veri.get("yargitay_hukmu") or "").strip()
        if not hukum:
            s2 = veri.get("slayt_2_detay", {})
            if isinstance(s2, dict):
                kartlar = s2.get("kartlar", [])
                if kartlar:
                    hukum = kartlar[0].get("aciklama", "").strip()
                elif "kart_1" in s2 or "kart_2" in s2:
                    k1 = s2.get("kart_1", {})
                    k2 = s2.get("kart_2", {})
                    p1_txt = f"{k1.get('baslik', '')}: {k1.get('aciklama', '')}".strip(": ") if k1 else ""
                    p2_txt = f"{k2.get('baslik', '')}: {k2.get('aciklama', '')}".strip(": ") if k2 else ""
                    hukum = f"{p1_txt} | {p2_txt}".strip(" |")
        if not hukum:
            hukum = "Yargıtay yerleşik içtihatları uyarınca, resmi tescil ve bildirim yapılmayan işlemler iyi niyetli üçüncü kişilere karşı ileri sürülemez."

        ders = (veri.get("cikarilacak_ders") or "").strip()
        if not ders:
            s3 = veri.get("slayt_3_cozum", {})
            if isinstance(s3, dict):
                maddeler = s3.get("maddeler", [])
                if maddeler:
                    m0 = maddeler[0]
                    ders = (m0.get("aciklama", "") if isinstance(m0, dict) else str(m0)).strip()
        if not ders:
            ders = "Tapu devirlerinde sözleşmelerinizi noter onaylı yapın ve tapu siciline mutlaka şerh işleyin."

        uret_vaka_slayt1(p1, vaka_kodu=vaka_kodu, yargitay_kaynak=kaynak, manset=manset, olay_detay=olay, sayfa_no="01 / 02")
        uret_vaka_slayt2(p2, vaka_kodu=vaka_kodu, yargitay_hukmu=hukum, cikarilacak_ders=ders, sayfa_no="02 / 02")
        log.info("Yeni Format Üretildi (NATIVE VAKA ANALİZİ): %s, %s", p1, p2)
        return [p1, p2]

    # =========================================================================
    # B) ESKİ BİÇİMLERDEN (B1, B2, B3) AKILLI ADAPTASYON (FALLBACK)
    # =========================================================================
    bicim = veri.get("bicim", "B1")
    brief = veri.get("_brief", {}) or {}
    kanca = brief.get("kanca_kalip", "")

    # B1. NEDİR DOĞRUSU? (B2 veya kanca_kalip == 'yaygin_yanlis')
    if bicim == "B2" or kanca == "yaygin_yanlis" or "yanlis" in kanca:
        p1 = cikti_dizini / f"{cikti_onek}_nedir_dogrusu.jpg"
        yanlis = f"{veri.get('manset_parca_1', '')} {veri.get('manset_vurgu', '')}".strip()
        if not yanlis or len(yanlis) < 10:
            yanlis = veri.get("spot", "Tapu senedi her şeyin tek ve kesin garantisidir.")[:80]
        
        dogru = ""
        s2 = veri.get("slayt_2_detay", {})
        if isinstance(s2, dict):
            kartlar = s2.get("kartlar", [])
            if kartlar:
                dogru = kartlar[0].get("aciklama", "")
            elif "kart_2" in s2 or "kart_1" in s2:
                k = s2.get("kart_2") or s2.get("kart_1", {})
                dogru = f"{k.get('baslik', '')}: {k.get('aciklama', '')}".strip(": ")
        if not dogru:
            dogru = veri.get("spot", "")
        
        altin_kural = ""
        s3 = veri.get("slayt_3_cozum", {})
        if isinstance(s3, dict):
            maddeler = s3.get("maddeler", [])
            if maddeler:
                m0 = maddeler[0]
                if isinstance(m0, dict):
                    altin_kural = f"{m0.get('baslik', '')}: {m0.get('aciklama', '')}".strip(": ")
                else:
                    altin_kural = str(m0)
        if not altin_kural:
            altin_kural = "Noter onayı ve tapu sicil şerhi olmadan hiçbir sözlü taahhüde güvenmeyin."

        uret_nedir_dogrusu(p1, konu=kategori, yanlis_metin=yanlis, dogru_metin=dogru, altin_kural=altin_kural)
        log.info("Yeni Format Üretildi (NEDİR DOĞRUSU): %s", p1)
        return [p1]

    # B2. NET CEVAP REHBERİ (B3 veya kanca_kalip in ('kim_hakli', 'soru'))
    elif bicim == "B3" or kanca in ("kim_hakli", "soru") or "?" in veri.get("manset_parca_1", ""):
        p1 = cikti_dizini / f"{cikti_onek}_net_cevap.jpg"
        soru = f"{veri.get('manset_parca_1', '')} {veri.get('manset_vurgu', '')}".strip()
        if not soru.endswith("?"):
            soru += "?"
        net_cevap = veri.get("manset_parca_2", "CEVAP: ŞARTA BAĞLIDIR")
        if not net_cevap.upper().startswith("CEVAP"):
            net_cevap = f"CEVAP: {net_cevap.upper()}"
        aciklama = veri.get("spot", "")
        
        tavsiye = ""
        s3 = veri.get("slayt_3_cozum", {})
        if isinstance(s3, dict):
            maddeler = s3.get("maddeler", [])
            if maddeler:
                m0 = maddeler[0]
                tavsiye = m0.get("aciklama", "") if isinstance(m0, dict) else str(m0)
        if not tavsiye:
            tavsiye = "İşlem yapmadan önce belediye imar ve tapu müdürlüğünden teyit alın."

        uret_net_cevap_tek_kare(p1, kategori=kategori, soru=soru, net_cevap=net_cevap, aciklama=aciklama, tavsiye_metin=tavsiye)
        log.info("Yeni Format Üretildi (NET CEVAP): %s", p1)
        return [p1]

    # B3. GERÇEK HUKUKİ VAKA ANALİZİ (B1 - Risk Dosyası / Emsal Karar)
    elif bicim == "B1" or "hukuk" in kategori.lower() or "dava" in veri.get("manset_vurgu", "").lower():
        p1 = cikti_dizini / f"{cikti_onek}_vaka_s1.jpg"
        p2 = cikti_dizini / f"{cikti_onek}_vaka_s2.jpg"
        manset = f"{veri.get('manset_parca_1', '')} {veri.get('manset_vurgu', '')} {veri.get('manset_parca_2', '')}".strip()
        if not manset or len(manset) < 10:
            manset = veri.get("spot", "")[:75]
        kaynak = veri.get("yasal_dayanak") or brief.get("mevzuat") or "Yargıtay Emsal İçtihadı"
        olay = veri.get("spot", "")
        
        hukum = ""
        s2 = veri.get("slayt_2_detay", {})
        if isinstance(s2, dict):
            kartlar = s2.get("kartlar", [])
            if kartlar:
                hukum = kartlar[0].get("aciklama", "")
            elif "kart_1" in s2 or "kart_2" in s2:
                k1 = s2.get("kart_1", {})
                k2 = s2.get("kart_2", {})
                p1_txt = f"{k1.get('baslik', '')}: {k1.get('aciklama', '')}".strip(": ") if k1 else ""
                p2_txt = f"{k2.get('baslik', '')}: {k2.get('aciklama', '')}".strip(": ") if k2 else ""
                hukum = f"{p1_txt} | {p2_txt}".strip(" |")
        if not hukum:
            hukum = "Yargıtay yerleşik içtihatları uyarınca, resmi tescil ve bildirim yapılmayan işlemler iyi niyetli üçüncü kişilere karşı ileri sürülemez."

        ders = ""
        s3 = veri.get("slayt_3_cozum", {})
        if isinstance(s3, dict):
            maddeler = s3.get("maddeler", [])
            if maddeler:
                m0 = maddeler[0]
                ders = m0.get("aciklama", "") if isinstance(m0, dict) else str(m0)
        if not ders:
            ders = "Tapu devirlerinde sözleşmelerinizi noter onaylı yapın ve tapu siciline mutlaka şerh işleyin."

        vaka_kodu = veri.get("konu_kodu", "01 / EMSAL DOSYA")
        uret_vaka_slayt1(p1, vaka_kodu=vaka_kodu, yargitay_kaynak=kaynak, manset=manset, olay_detay=olay, sayfa_no="01 / 02")
        uret_vaka_slayt2(p2, vaka_kodu=vaka_kodu, yargitay_hukmu=hukum, cikarilacak_ders=ders, sayfa_no="02 / 02")
        log.info("Yeni Format Üretildi (VAKA ANALİZİ): %s, %s", p1, p2)
        return [p1, p2]

    # B4. SÖZLÜK (Terim veya genel format)
    else:
        p1 = cikti_dizini / f"{cikti_onek}_sozluk.jpg"
        terim = veri.get("manset_vurgu") or veri.get("manset_parca_1") or "GAYRİMENKUL HUKUKU"
        tanim = veri.get("spot", "")
        maddeler = []
        s3 = veri.get("slayt_3_cozum", {})
        if isinstance(s3, dict):
            for m in s3.get("maddeler", [])[:3]:
                if isinstance(m, dict):
                    maddeler.append(f"{m.get('baslik', '')}: {m.get('aciklama', '')}".strip(": "))
                else:
                    maddeler.append(str(m))
        if not maddeler:
            maddeler = ["Mevzuat Uyarısı: Kanuni süreleri kaçırmamak adına yasal takvimleri takip edin."]

        uret_sozluk(p1, terim=terim, kategori=kategori, tanim_metni=tanim, puf_maddeleri=maddeler)
        log.info("Yeni Format Üretildi (EDM SÖZLÜK): %s", p1)
        return [p1]
