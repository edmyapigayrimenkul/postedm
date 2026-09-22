"""
src/yeni_formatlar.py — EDM 4 Temel Format Görsel Motoru
1. EDM EMLAK SÖZLÜĞÜ (Kireç Bej Zemin, Dev Fraunces Kelime, Kitap Filigranı, Tırnaklı Hukuki Tanım)
2. NEDİR DOĞRUSU? (Kırmızı Gradient Zemin, Dev Şehir Efsanesi Hook, Beyaz Alt Zemin, Alta Dayalı Altın Kural)
3. GERÇEK HUKUKİ VAKA ANALİZİ (Siyah Editoryal Zemin, Fraunces Manşet, Fraunces Hüküm, Alta Dayalı Ders Kartı)
4. NET CEVAP REHBERİ / SORU-CEVAP (Beyaz Zemin, Fraunces Soru, '?' Filigranı, Net Cevap Rozeti, Alta Dayalı Tavsiye)
"""

from __future__ import annotations

import logging
import re
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

KATEGORI_HARITASI = {
    "S1": "TAPU & HUKUK",
    "S2": "KİRACI & EV SAHİBİ",
    "S3": "ARSA & İMAR",
    "S4": "KİRA & ENFLASYON",
    "TAPU_VE_HUKUK": "TAPU & HUKUK",
    "KIRACI_VE_EV_SAHIBI": "KİRACI & EV SAHİBİ",
    "ARSA_VE_IMAR": "ARSA & İMAR",
    "FINANS_VE_BANKACILIK": "FİNANS & BANKACILIK",
    "PIYASA_VE_YATIRIM": "PİYASA & YATIRIM",
    "HUKUK": "TAPU & HUKUK",
    "KİRA": "KİRA & ENFLASYON",
    "KIRA": "KİRA & ENFLASYON",
    "ARSA": "ARSA & İMAR",
    "TAPU": "TAPU & HUKUK",
    "IMAR": "ARSA & İMAR",
    "İMAR": "ARSA & İMAR",
    "IMAR_VE_PARSEL": "İMAR & PARSELASYON",
    "KENTSEL_DONUSUM": "KENTSEL DÖNÜŞÜM",
    "MIRAS_VE_INTIKAL": "MİRAS & İNTİKAL",
    "TARLA_VE_TINYHOUSE": "TARLA & TİNY HOUSE",
    "KIRA_VE_TAHLIYE": "KİRA & TAHLİYE",
    "KAMULASTIRMA": "KAMULAŞTIRMA",
    "RUHSAT_VE_PROJE": "RUHSAT & PROJE",
    "YATIRIM_VE_DEGERLEME": "YATIRIM & DEĞERLEME",
    "VERGI_VE_HARC": "VERGİ & HARÇ",
    "TARIM_VE_ARAZI": "TARIM & ARAZİ",
    "SEKTOR_GUNDEMI": "SEKTÖR GÜNDEMİ",
}


def kategori_temizle(kat: Optional[str]) -> str:
    if not kat:
        return "GAYRİMENKUL & HUKUK"
    k = str(kat).strip()
    k_up = k.upper()
    if k_up in KATEGORI_HARITASI:
        return KATEGORI_HARITASI[k_up]
    for code in ("S1", "S2", "S3", "S4"):
        if k_up == code or k_up.startswith(f"{code}-") or k_up.startswith(f"{code}_") or k_up.startswith(f"{code} "):
            return KATEGORI_HARITASI[code]
    temiz = k.replace("_", " ").strip()
    return temiz if temiz else "GAYRİMENKUL & HUKUK"


# =============================================================================
# 1. FORMAT: EDM GAYRİMENKUL SÖZLÜĞÜ
# =============================================================================
def ciz_buyuk_sozluk_filigran_vector(
    draw_target: ImageDraw.ImageDraw,
    cx: int = 320,
    cy: int = 310,
    w: int = 520,
    h: int = 350,
    alpha: int = 23,
) -> None:
    """Çok daha büyük (w=520, h=350), kelimelerin ve kategorinin arkasına zarifçe taşan mimari açık kitap filigranı."""
    renk = (18, 19, 22, alpha)
    hw = w // 2
    hh = h // 2
    sol_pts = [(cx - 8, cy - hh + 24), (cx - hw, cy - hh + 4), (cx - hw, cy + hh - 20), (cx - 8, cy + hh + 4)]
    sag_pts = [(cx + 8, cy - hh + 24), (cx + hw, cy - hh + 4), (cx + hw, cy + hh - 20), (cx + 8, cy + hh + 4)]
    draw_target.polygon(sol_pts, outline=renk, width=5)
    draw_target.polygon(sag_pts, outline=renk, width=5)
    draw_target.line([(cx, cy - hh + 20), (cx, cy + hh + 10)], fill=renk, width=6)

    for dy in np.linspace(-hh + 65, hh - 65, 5):
        int_dy = int(dy)
        draw_target.line([(cx - hw + 38, cy + int_dy - 4), (cx - 36, cy + int_dy + 2)], fill=renk, width=3)
        draw_target.line([(cx + 36, cy + int_dy + 2), (cx + hw - 38, cy + int_dy - 4)], fill=renk, width=3)

    ribbon_pts = [(cx - 7, cy + hh + 4), (cx + 7, cy + hh + 4), (cx + 6, cy + hh + 44), (cx, cy + hh + 34), (cx - 6, cy + hh + 44)]
    draw_target.polygon(ribbon_pts, fill=(196, 3, 15, int(alpha * 1.8)))


def uret_sozluk(
    cikti_yolu: Path,
    terim: str,
    kategori: str,
    tanim_metni: str,
    puf_maddeleri: Any,
    sayfa_no: str = "SÖZLÜK // 01",
) -> Path:
    canvas = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_KIREC_BEJ)
    canvas = make_image._filigran_uygula(canvas, acik_zemin=True)

    yer = make_image._yerlesim()
    kenar = yer["kenar"]
    kullanilabilir_w = GENISLIK - (2 * kenar)
    ku = yer["kronik_ust"]

    # Header: Sol üstte Emlak Sözlüğü rozeti, sağ üstte EDM Logosu (4:5 Standart Hizalama)
    kat_temiz = kategori_temizle(kategori)
    draw_init = ImageDraw.Draw(canvas)
    make_image._rozet_ciz(draw_init, kenar, ku, f"EMLAK SÖZLÜĞÜ // {kat_temiz.upper()}", bg_color=RENK_MUREKKEP, fg_color=RENK_BEYAZ, font_boyut=20)
    make_image._logo_yerlestir(canvas, beyaz=False, y=ku - 5, lw=285, golge=False, kirmizi_zemin=False)

    alt_y = yer["alt_bar"]

    # 1. Öneri Kartı: ALTA DAYALI
    if isinstance(puf_maddeleri, list):
        temiz_maddeler = []
        for m in puf_maddeleri:
            m_str = str(m).strip()
            if ":" in m_str:
                m_str = m_str.split(":", 1)[1].strip()
            temiz_maddeler.append(m_str)
        puf_metin = " ".join(temiz_maddeler[:2])
    else:
        puf_metin = str(puf_maddeleri)

    f_puf_etiket = make_image._font_yukle(FONT_MONO_BOLD, 20)
    f_puf_govde = make_image._font_yukle(FONT_SANS_MEDIUM, 31)
    img_temp = Image.new("RGB", (10, 10))
    d_temp = ImageDraw.Draw(img_temp)
    puf_satirlar = make_image._metin_sar(puf_metin, f_puf_govde, kullanilabilir_w - 56, d_temp)
    h_kutu = 52 + (len(puf_satirlar) * 44) + 24
    kutu_y = alt_y - 26 - h_kutu

    # 2. Terim: BOLD FRAUNCES BLACK (136px -> 68px)
    parcalar = terim.split()
    en_uzun_kelime = max(parcalar, key=len) if parcalar else terim
    f_punto = 136
    while f_punto >= 68:
        f_test = make_image._font_yukle(FONT_FRAUNCES, f_punto)
        bb = f_test.getbbox(en_uzun_kelime)
        if (bb[2] - bb[0]) <= kullanilabilir_w:
            break
        f_punto -= 2

    f_terim = make_image._font_yukle(FONT_FRAUNCES, f_punto)
    terim_satirlar = make_image._metin_sar(terim, f_terim, kullanilabilir_w, d_temp)
    line_h_terim = int(f_punto * 1.15)
    h_terim = len(terim_satirlar) * line_h_terim

    # 3. Anlam (Tanım Metni): Dinamik Punto (38px - 42px) + Paragraf Başı Boşluğu
    f_tanim_punto = 38 if len(tanim_metni) > 160 else 42
    f_tanim = make_image._font_yukle(FONT_SANS_MEDIUM, f_tanim_punto)
    line_h_tanim = int(f_tanim_punto * 1.38)
    indent_px = int(f_tanim_punto * 1.6)

    tanim_kelimeler = tanim_metni.split()
    tanim_satirlar = []
    curr = []
    for w in tanim_kelimeler:
        cand = (" ".join(curr + [w])) if curr else w
        max_w = (kullanilabilir_w - indent_px) if len(tanim_satirlar) == 0 else kullanilabilir_w
        if d_temp.textbbox((0, 0), cand, font=f_tanim)[2] <= max_w:
            curr.append(w)
        else:
            if curr:
                tanim_satirlar.append(" ".join(curr))
            curr = [w]
    if curr:
        tanim_satirlar.append(" ".join(curr))

    h_tanim = len(tanim_satirlar) * line_h_tanim

    ust_sinir = ku + 80
    kullanilabilir_orta_h = (kutu_y - 28) - ust_sinir
    toplam_orta_h = h_terim + 22 + 34 + 34 + h_tanim
    bosluk_payi = max(0, (kullanilabilir_orta_h - toplam_orta_h) // 3)
    curr_y = ust_sinir + min(36, bosluk_payi)

    # Filigran Katmanı (Kitap filigranı + Paragraf başı '“' filigranı)
    overlay = Image.new("RGBA", (GENISLIK, YUKSEKLIK), (255, 255, 255, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    ciz_buyuk_sozluk_filigran_vector(overlay_draw, cx=320, cy=330, w=520, h=350, alpha=23)

    ty = curr_y + h_terim + 16 + 34 + 36
    f_quote = make_image._font_yukle(FONT_FRAUNCES, int(f_tanim_punto * 1.8))
    overlay_draw.text((kenar + 2, ty - 8), "“", font=f_quote, fill=(18, 19, 22, 60))

    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(canvas)

    # Footer
    draw.line([(kenar, alt_y), (GENISLIK - kenar, alt_y)], fill=RENK_KIREC_BORDER, width=1)
    draw.text((kenar, alt_y + 26), "EDM YAPI & GAYRİMENKUL // EMLAK SÖZLÜĞÜ", font=make_image._font_yukle(FONT_MONO, 19), fill=RENK_KURSUN)
    sf = make_image._font_yukle(FONT_MONO_BOLD, 19)
    sw = draw.textbbox((0, 0), sayfa_no, font=sf)[2]
    draw.text((GENISLIK - kenar - sw, alt_y + 26), sayfa_no, font=sf, fill=RENK_MUREKKEP)

    # Terim Başlığı
    for s in terim_satirlar:
        draw.text((kenar, curr_y), s, font=f_terim, fill=RENK_MUREKKEP)
        curr_y += line_h_terim
    curr_y += 16

    draw.line([(kenar, curr_y), (GENISLIK - kenar, curr_y)], fill=RENK_KIREC_BORDER, width=2)
    curr_y += 34

    draw.text((kenar, curr_y), "TANIM & ANLAMI", font=make_image._font_yukle(FONT_MONO_BOLD, 20), fill=RENK_KURSUN)
    curr_y += 36

    for i, s in enumerate(tanim_satirlar):
        x_pos = kenar + (indent_px if i == 0 else 0)
        draw.text((x_pos, curr_y), s, font=f_tanim, fill=RENK_MUREKKEP)
        curr_y += line_h_tanim

    # Alta dayalı öneri kartı (Koyu Zemin + Altın Sarısı Vurgu)
    draw.rounded_rectangle([(kenar, kutu_y), (GENISLIK - kenar, kutu_y + h_kutu)], radius=12, fill=RENK_MUREKKEP, outline=(50, 53, 62), width=1)
    draw.rounded_rectangle([(kenar, kutu_y), (kenar + 6, kutu_y + h_kutu)], radius=2, fill=RENK_ALTIN)
    draw.text((kenar + 28, kutu_y + 18), "YATIRIMCI İÇİN ÖNEMİ:", font=f_puf_etiket, fill=RENK_ALTIN)
    py = kutu_y + 52
    for s in puf_satirlar:
        draw.text((kenar + 28, py), s, font=f_puf_govde, fill=RENK_BEYAZ)
        py += 44

    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


# =============================================================================
# 2. FORMAT: NEDİR DOĞRUSU? (YANLIŞ / DOĞRU)
# =============================================================================
def ciz_tik_filigran(
    draw_target: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    boy: int = 320,
    renk: Tuple[int, int, int, int] = (34, 197, 94, 52),
    kalinlik: int = 46,
    r: Optional[int] = None,
) -> None:
    if r is not None:
        boy = r * 2
    # Sağ kenara taşan kalın mimari tik (Çembersiz, güçlü ve zarif)
    w_line = kalinlik
    p_radius = w_line // 2
    p1 = (cx - int(boy * 0.42), cy - int(boy * 0.05))
    p2 = (cx - int(boy * 0.12), cy + int(boy * 0.35))
    p3 = (cx + int(boy * 0.45), cy - int(boy * 0.40))
    draw_target.line([p1, p2], fill=renk, width=w_line)
    draw_target.line([p2, p3], fill=renk, width=w_line)
    for pt in (p1, p2, p3):
        draw_target.ellipse(
            [(pt[0] - p_radius, pt[1] - p_radius), (pt[0] + p_radius, pt[1] + p_radius)],
            fill=renk,
        )


def ciz_vektor_carpi_filigran(
    draw_target: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    boy: int = 300,
    renk: Tuple[int, int, int, int] = (255, 255, 255, 45),
    kalinlik: int = 46,
    r: Optional[int] = None,
) -> None:
    if r is not None:
        boy = r * 2
    # Sağ kenara taşan kalın mimari çarpı (Çembersiz, güçlü ve zarif)
    w_line = kalinlik
    p_radius = w_line // 2
    for p_line in [
        ((cx - boy // 2, cy - boy // 2), (cx + boy // 2, cy + boy // 2)),
        ((cx - boy // 2, cy + boy // 2), (cx + boy // 2, cy - boy // 2)),
    ]:
        draw_target.line(p_line, fill=renk, width=w_line)
        for pt in p_line:
            draw_target.ellipse(
                [(pt[0] - p_radius, pt[1] - p_radius), (pt[0] + p_radius, pt[1] + p_radius)],
                fill=renk,
            )


def uret_nedir_dogrusu(
    cikti_yolu: Path,
    konu: str,
    yanlis_metin: str,
    dogru_metin: str,
    altin_kural: str,
) -> Path:
    w, h = GENISLIK, YUKSEKLIK
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    r1, g1, b1 = (120, 8, 14)  # Koyu Bordo / Derin EDM Kırmızısı
    r2, g2, b2 = 255, 255, 255
    y_start = 480
    y_end = 640
    arr[:y_start, :] = [r1, g1, b1]
    for y in range(y_start, y_end):
        t = (y - y_start) / (y_end - y_start)
        s = t * t * (3 - 2 * t)
        arr[y, :] = [int(r1 + (r2 - r1) * s), int(g1 + (r2 - g1) * s), int(b1 + (r2 - b1) * s)]
    arr[y_end:, :] = [r2, g2, b2]

    canvas = Image.fromarray(arr)
    yer = make_image._yerlesim()
    kenar = yer["kenar"]
    kullanilabilir_w = GENISLIK - (2 * kenar)
    ku = yer["kronik_ust"]

    # Altın Kural Kartı Yüksekliği (Alta dayalı)
    f_kural_baslik = make_image._font_yukle(FONT_MONO_BOLD, 20)
    f_kural_govde = make_image._font_yukle(FONT_SANS_BOLD, 29)
    img_temp = Image.new("RGB", (10, 10))
    d_temp = ImageDraw.Draw(img_temp)
    kural_satirlar = make_image._metin_sar(altin_kural or "", f_kural_govde, kullanilabilir_w - 52, d_temp)
    if len(kural_satirlar) > 3:
        f_kural_govde = make_image._font_yukle(FONT_SANS_BOLD, 26)
        kural_satirlar = make_image._metin_sar(altin_kural or "", f_kural_govde, kullanilabilir_w - 52, d_temp)
    h_kutu = 48 + (len(kural_satirlar) * 40) + 20

    alt_bar_y = yer["alt_bar"]
    kutu_y = alt_bar_y - 26 - h_kutu

    # Doğru Metni (Dinamik Punto 36px - 46px + Paragraf başı boşluğu)
    beyaz_alan_h = kutu_y - (y_end + 25)
    best_punto = 38
    best_satirlar = []
    best_line_h = 54
    best_indent = 64

    for punto_test in (46, 44, 42, 40, 38, 36):
        f_test = make_image._font_yukle(FONT_SANS_MEDIUM, punto_test)
        lh_test = int(punto_test * 1.36)
        ind_test = int(punto_test * 1.6)

        d_words = (dogru_metin or "").split()
        cand_lines = []
        c_line = []
        for w in d_words:
            cand_str = (" ".join(c_line + [w])) if c_line else w
            max_w = (kullanilabilir_w - ind_test) if len(cand_lines) == 0 else kullanilabilir_w
            if d_temp.textbbox((0, 0), cand_str, font=f_test)[2] <= max_w:
                c_line.append(w)
            else:
                if c_line:
                    cand_lines.append(" ".join(c_line))
                c_line = [w]
        if c_line:
            cand_lines.append(" ".join(c_line))

        h_calc = len(cand_lines) * lh_test
        if h_calc <= (beyaz_alan_h - 36):
            best_punto = punto_test
            best_satirlar = cand_lines
            best_line_h = lh_test
            best_indent = ind_test
            break

    f_dogru = make_image._font_yukle(FONT_SANS_MEDIUM, best_punto)
    dogru_satirlar = best_satirlar if best_satirlar else make_image._metin_sar(dogru_metin or "", f_dogru, kullanilabilir_w, d_temp)
    line_h_dogru = best_line_h
    indent_px = best_indent

    h_dogru = len(dogru_satirlar) * line_h_dogru
    alt_bosluk = max(10, (beyaz_alan_h - h_dogru) // 2)
    dogru_y = y_end + 25 + alt_bosluk

    # Filigran Katmanı (Sağ kenardan taşan kalın mimari Çarpı + Tik + Paragraf başı '“' filigranı)
    overlay = Image.new("RGBA", (GENISLIK, YUKSEKLIK), (255, 255, 255, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    cx_carpi = GENISLIK - 45
    cy_carpi = ku + 280
    ciz_vektor_carpi_filigran(overlay_draw, cx=cx_carpi, cy=cy_carpi, boy=300, renk=(255, 255, 255, 45), kalinlik=46)
    cx_tik = GENISLIK - 65
    cy_tik = dogru_y + 135
    ciz_tik_filigran(overlay_draw, cx=cx_tik, cy=cy_tik, boy=320, renk=(34, 197, 94, 52), kalinlik=46)

    # Paragraf başı '“' filigranı (puntoyla orantılı)
    f_quote_size = int(best_punto * 1.85)
    f_quote = make_image._font_yukle(FONT_FRAUNCES, f_quote_size)
    overlay_draw.text((kenar + 2, dogru_y - int(best_punto * 0.22)), "“", font=f_quote, fill=(18, 19, 22, 55))

    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(canvas)

    konu_baslik = kategori_temizle(konu)
    make_image._rozet_ciz(draw, kenar, ku, f"NEDİR DOĞRUSU? // {konu_baslik.upper()}", bg_color=RENK_MUREKKEP, fg_color=RENK_BEYAZ, font_boyut=20)
    make_image._logo_yerlestir(canvas, beyaz=True, y=ku - 5, lw=285, golge=True, kirmizi_zemin=True)

    # Yanlış Metni: SAĞA DOĞRU TAM GENİŞLİK (kullanilabilir_w) + TİPOGRAFİK TIRNAKLAR
    temiz_yanlis = re.sub(r"""^[\s"'“”‘’]+|[\s"'“”‘’]+$""", '', yanlis_metin or "")
    yanlis_formatli = f"“{temiz_yanlis}”"

    kirmizi_alan_h = y_start - (ku + 75)
    f_punto = 50
    while f_punto >= 32:
        f_test = make_image._font_yukle(FONT_SANS_BOLD, f_punto)
        lh_test = int(f_punto * 1.25)
        test_satirlar = make_image._metin_sar(yanlis_formatli, f_test, kullanilabilir_w, draw)
        if len(test_satirlar) * lh_test <= kirmizi_alan_h - 20:
            break
        f_punto -= 2

    f_yanlis = make_image._font_yukle(FONT_SANS_BOLD, f_punto)
    line_h = int(f_punto * 1.25)
    yanlis_satirlar = make_image._metin_sar(yanlis_formatli, f_yanlis, kullanilabilir_w, draw)

    if yanlis_satirlar:
        yanlis_satirlar[0] = "“" + yanlis_satirlar[0].lstrip(' "“')
        yanlis_satirlar[-1] = yanlis_satirlar[-1].rstrip(' "”') + "”"

    h_yanlis = len(yanlis_satirlar) * line_h
    yanlis_y = ku + 75 + max(10, (kirmizi_alan_h - h_yanlis) // 2)

    for s in yanlis_satirlar:
        draw.text((kenar, yanlis_y), s, font=f_yanlis, fill=(255, 255, 255))
        yanlis_y += line_h

    # Doğru Metni Çizimi
    curr_dy = dogru_y
    for i, s in enumerate(dogru_satirlar):
        x_pos = kenar + (indent_px if i == 0 else 0)
        draw.text((x_pos, curr_dy), s, font=f_dogru, fill=RENK_MUREKKEP)
        curr_dy += line_h_dogru

    # Altın Kural Kartı (Alta dayalı - Altın Sarısı Vurgu)
    draw.rounded_rectangle([(kenar, kutu_y), (GENISLIK - kenar, kutu_y + h_kutu)], radius=12, fill=RENK_MUREKKEP, outline=(55, 58, 66), width=1)
    draw.rounded_rectangle([(kenar, kutu_y), (kenar + 6, kutu_y + h_kutu)], radius=2, fill=RENK_ALTIN)
    draw.text((kenar + 28, kutu_y + 18), "EDM ALTIN KURALI:", font=f_kural_baslik, fill=RENK_ALTIN)
    ky = kutu_y + 52
    for s in kural_satirlar:
        draw.text((kenar + 28, ky), s, font=f_kural_govde, fill=RENK_BEYAZ)
        ky += 40

    # Footer
    draw.line([(kenar, alt_bar_y), (GENISLIK - kenar, alt_bar_y)], fill=RENK_CIZGI_ACIK, width=1)
    draw.text((kenar, alt_bar_y + 26), "EDM YAPI & GAYRİMENKUL // HUKUK & GERÇEK", font=make_image._font_yukle(FONT_MONO, 19), fill=RENK_KURSUN)
    draw.text((GENISLIK - kenar - 170, alt_bar_y + 26), "NEDİR DOĞRUSU?", font=make_image._font_yukle(FONT_MONO_BOLD, 19), fill=RENK_MUREKKEP)

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


def uret_vaka_slayt2(
    cikti_yolu: Path,
    vaka_kodu: str,
    yargitay_hukmu: str,
    cikarilacak_ders: str,
    sayfa_no: str = "02 / 02",
    rozet_baslik: Optional[str] = None,
    hukum_baslik: Optional[str] = None,
    ders_baslik: Optional[str] = None,
    alt_arsiv_metni: Optional[str] = None,
) -> Path:
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
    rozet_metni = rozet_baslik or f"GERÇEK HUKUKİ VAKA // {vaka_kodu.upper()} - KARAR"
    make_image._rozet_ciz(draw, kenar, ku, rozet_metni, bg_color=RENK_LOGO_KIRMIZI, fg_color=RENK_BEYAZ, font_boyut=20, max_w=azami_rozet_w)
    make_image._logo_yerlestir(canvas, beyaz=True, y=ku - 5, lw=logo_w, golge=True, kirmizi_zemin=False)

    alt_y = yer["alt_bar"]
    draw.line([(kenar, alt_y), (GENISLIK - kenar, alt_y)], fill=RENK_CIZGI_KOYU, width=1)
    alt_txt = alt_arsiv_metni or "EDM HUKUK ARŞİVİ // EMSAL İÇTİHAT DOSYASI"
    draw.text((kenar, alt_y + 26), alt_txt, font=make_image._font_yukle(FONT_MONO, 18), fill=RENK_KURSUN)
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
    etiket_txt = hukum_baslik or "YARGITAY'IN VERDİĞİ KESİN HÜKÜM"
    make_image._rozet_ciz(draw, kenar, curr_y, etiket_txt, bg_color=RENK_LOGO_KIRMIZI, fg_color=RENK_BEYAZ, font_boyut=17, max_w=kullanilabilir_w)
    curr_y += 44

    for s in hukum_satirlar:
        draw.text((kenar, curr_y), s, font=f_hukum, fill=RENK_BEYAZ)
        curr_y += leading_hukum

    draw.rounded_rectangle([(kenar, kutu_y), (GENISLIK - kenar, kutu_y + h_kutu)], radius=12, fill=(28, 32, 42), outline=(55, 65, 85), width=1)
    draw.rounded_rectangle([(kenar, kutu_y), (kenar + 6, kutu_y + h_kutu)], radius=2, fill=RENK_ALTIN)
    ders_etiket_txt = ders_baslik or "BU DAVADAN ÇIKARILACAK DERS:"
    draw.text((kenar + 28, kutu_y + 18), ders_etiket_txt, font=f_ders_etiket, fill=RENK_ALTIN)

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
    w, h = GENISLIK, YUKSEKLIK
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    r1, g1, b1 = RENK_MUREKKEP  # Üstte Derin Mürekkep
    r2, g2, b2 = 255, 255, 255  # Altta Beyaz
    y_start = 480
    y_end = 640
    arr[:y_start, :] = [r1, g1, b1]
    for y in range(y_start, y_end):
        t = (y - y_start) / (y_end - y_start)
        s = t * t * (3 - 2 * t)
        arr[y, :] = [int(r1 + (r2 - r1) * s), int(g1 + (r2 - g1) * s), int(b1 + (r2 - b1) * s)]
    arr[y_end:, :] = [r2, g2, b2]

    canvas = Image.fromarray(arr)
    yer = make_image._yerlesim()
    kenar = yer["kenar"]
    kullanilabilir_w = GENISLIK - (2 * kenar)
    ku = yer["kronik_ust"]
    alt_bar_y = yer["alt_bar"]

    img_temp = Image.new("RGB", (10, 10))
    d_temp = ImageDraw.Draw(img_temp)

    # 1. EDM Uzman Tavsiyesi Kartı (Alta Dayalı - Altın Sarısı Vurgu)
    f_tavsiye_baslik = make_image._font_yukle(FONT_MONO_BOLD, 20)
    f_tavsiye_govde = make_image._font_yukle(FONT_SANS_BOLD, 26)
    tavsiye_satirlar = make_image._metin_sar(tavsiye_metin or "", f_tavsiye_govde, kullanilabilir_w - 56, d_temp)
    if len(tavsiye_satirlar) > 3:
        f_tavsiye_govde = make_image._font_yukle(FONT_SANS_BOLD, 24)
        tavsiye_satirlar = make_image._metin_sar(tavsiye_metin or "", f_tavsiye_govde, kullanilabilir_w - 56, d_temp)
    leading_tavsiye = 38
    h_kutu = 52 + (len(tavsiye_satirlar) * leading_tavsiye) + 20
    kutu_y = alt_bar_y - 26 - h_kutu

    # 2. Cevap Rozeti ve Açıklama Metni Alanı (Alt Beyaz Alan)
    # Cevap biraz daha aşağıda başlasın: y_end + 35
    cevap_y = y_end + 35

    # Açıklama Metni: Dinamik Punto (36px - 42px) + Paragraf Başı Boşluğu
    beyaz_alan_h = (kutu_y - 20) - (cevap_y + 60)
    best_punto = 38
    best_satirlar = []
    best_line_h = 52
    best_indent = 60

    for punto_test in (42, 40, 38, 36):
        f_test = make_image._font_yukle(FONT_SANS_MEDIUM, punto_test)
        lh_test = int(punto_test * 1.36)
        ind_test = int(punto_test * 1.6)

        d_words = (aciklama or "").split()
        cand_lines = []
        c_line = []
        for word in d_words:
            cand_str = (" ".join(c_line + [word])) if c_line else word
            max_w = (kullanilabilir_w - ind_test) if len(cand_lines) == 0 else kullanilabilir_w
            if d_temp.textbbox((0, 0), cand_str, font=f_test)[2] <= max_w:
                c_line.append(word)
            else:
                if c_line:
                    cand_lines.append(" ".join(c_line))
                c_line = [word]
        if c_line:
            cand_lines.append(" ".join(c_line))

        h_calc = len(cand_lines) * lh_test
        if h_calc <= (beyaz_alan_h - 10):
            best_punto = punto_test
            best_satirlar = cand_lines
            best_line_h = lh_test
            best_indent = ind_test
            break

    f_aciklama = make_image._font_yukle(FONT_SANS_MEDIUM, best_punto)
    aciklama_satirlar = best_satirlar if best_satirlar else make_image._metin_sar(aciklama or "", f_aciklama, kullanilabilir_w, d_temp)
    line_h_aciklama = best_line_h
    indent_px = best_indent
    aciklama_y = cevap_y + 60

    # 3. Filigran Katmanı (Üstte şık soru işareti, altta paragraf başı '“' tırnak filigranı)
    overlay = Image.new("RGBA", (GENISLIK, YUKSEKLIK), (255, 255, 255, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    # Üst koyu alan soru işareti filigranı
    f_soru_mark = make_image._font_yukle(FONT_FRAUNCES, 280)
    overlay_draw.text((GENISLIK - 240, ku + 50), "?", font=f_soru_mark, fill=(255, 255, 255, 28))

    # Alt beyaz alan paragraf başı '“' filigranı
    f_quote_size = int(best_punto * 1.85)
    f_quote = make_image._font_yukle(FONT_FRAUNCES, f_quote_size)
    overlay_draw.text((kenar + 2, aciklama_y - int(best_punto * 0.22)), "“", font=f_quote, fill=(18, 19, 22, 55))

    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(canvas)

    # Header: Sol üstte Net Cevap rozeti, sağ üstte EDM Logosu
    kat_temiz = kategori_temizle(kategori)
    make_image._rozet_ciz(draw, kenar, ku, f"NET CEVAP // {kat_temiz.upper()}", bg_color=RENK_LOGO_KIRMIZI, fg_color=RENK_BEYAZ, font_boyut=20)
    make_image._logo_yerlestir(canvas, beyaz=True, y=ku - 5, lw=285, golge=True, kirmizi_zemin=False)

    # Soru Metni: Üst Koyu Alanda (Fraunces Beyaz, dinamik punto)
    koyu_alan_h = y_start - (ku + 75)
    punto_soru = 62
    while punto_soru >= 44:
        f_s_test = make_image._font_yukle(FONT_FRAUNCES, punto_soru)
        lh_s_test = int(punto_soru * 1.25)
        s_test_satirlar = make_image._metin_sar(soru or "", f_s_test, kullanilabilir_w, draw)
        if len(s_test_satirlar) * lh_s_test <= koyu_alan_h - 20:
            break
        punto_soru -= 2

    f_soru = make_image._font_yukle(FONT_FRAUNCES, punto_soru)
    line_h_soru = int(punto_soru * 1.25)
    soru_satirlar = make_image._metin_sar(soru or "", f_soru, kullanilabilir_w, draw)
    h_soru = len(soru_satirlar) * line_h_soru
    sy = ku + 75 + max(10, (koyu_alan_h - h_soru) // 2)

    for s in soru_satirlar:
        draw.text((kenar, sy), s, font=f_soru, fill=RENK_BEYAZ)
        sy += line_h_soru

    # Cevap Rozeti (Alt Beyaz Alanda)
    make_image._rozet_ciz(draw, kenar, cevap_y, net_cevap, bg_color=RENK_MUREKKEP, fg_color=RENK_BEYAZ, font_boyut=22, max_w=kullanilabilir_w)

    # Açıklama Metni Çizimi (İlk satır girintili)
    ay = aciklama_y
    for i, s in enumerate(aciklama_satirlar):
        x_pos = kenar + (indent_px if i == 0 else 0)
        draw.text((x_pos, ay), s, font=f_aciklama, fill=RENK_MUREKKEP)
        ay += line_h_aciklama

    # EDM Uzman Tavsiyesi Kartı (Alta dayalı - Altın Sarısı Vurgu)
    draw.rounded_rectangle([(kenar, kutu_y), (GENISLIK - kenar, kutu_y + h_kutu)], radius=12, fill=RENK_MUREKKEP, outline=(50, 53, 62), width=1)
    draw.rounded_rectangle([(kenar, kutu_y), (kenar + 6, kutu_y + h_kutu)], radius=2, fill=RENK_ALTIN)
    draw.text((kenar + 28, kutu_y + 18), "EDM UZMAN TAVSİYESİ:", font=f_tavsiye_baslik, fill=RENK_ALTIN)
    ty = kutu_y + 52
    for s in tavsiye_satirlar:
        draw.text((kenar + 28, ty), s, font=f_tavsiye_govde, fill=RENK_BEYAZ)
        ty += leading_tavsiye

    # Footer
    draw.line([(kenar, alt_bar_y), (GENISLIK - kenar, alt_bar_y)], fill=RENK_CIZGI_ACIK, width=1)
    draw.text((kenar, alt_bar_y + 26), "EDM YAPI & GAYRİMENKUL // NET CEVAP REHBERİ", font=make_image._font_yukle(FONT_MONO, 19), fill=RENK_KURSUN)
    draw.text((GENISLIK - kenar - 170, alt_bar_y + 26), "TEK KARE / CEVAP", font=make_image._font_yukle(FONT_MONO_BOLD, 19), fill=RENK_MUREKKEP)

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
    olcu: str = "besleme",
) -> List[Path]:
    """İçerik verisini inceleyip 4 yeni formattan en uygun olanı seçerek slaytları üretir.
    Hem doğrudan yeni format şemalarını (sozluk, nedir_dogrusu, net_cevap, vaka) hem de geriye dönük uyumluluk adaptörünü destekler.
    """
    if cikti_dizini is None:
        cikti_dizini = config.yol_al("data/output/gonderiler")
    cikti_dizini.mkdir(parents=True, exist_ok=True)

    format_turu = str(format_turu or veri.get("format_turu") or veri.get("format") or "").lower()
    kat_ham = veri.get("kategori") or veri.get("kategori_kodu") or "TAPU VE HUKUK"
    kategori = kategori_temizle(kat_ham)
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
        konu_raw = veri.get("konu") or veri.get("rozet_metni") or kat_ham
        konu = kategori_temizle(konu_raw)

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
        vaka_raw = veri.get("vaka_kodu") or veri.get("konu_kodu") or "01 / EMSAL DOSYA"
        vaka_kodu = kategori_temizle(vaka_raw)
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

    # 5. DAILYBRIEF HABER FORMATI (Instabot Paritesi: Gerçek/Stok Fotoğraf + Okuma Perdesi + Manşet)
    # Seçenek 2 (Dinamik 2 veya 3 Slayt): Zengin teknik haberler 3 slayt, kısa haberler 2 slayt
    if format_turu in ("dailybrief", "haber", "haber_dailybrief") or veri.get("bicim") in ("haber", "B5"):
        foto_yolu = veri.get("foto_yolu") or veri.get("gorsel_yolu")
        slaytlar = make_image.haber_dailybrief_slaytlari_uret(
            haber=veri,
            cikti_dizini=cikti_dizini,
            cikti_onek=cikti_onek,
            olcu=olcu,
            foto_yolu=foto_yolu,
        )
        log.info("Yeni Format Üretildi (DAILYBRIEF HABER %d Slayt): %s", len(slaytlar), ", ".join(str(p) for p in slaytlar))
        return slaytlar

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

        konu_raw = veri.get("konu") or veri.get("rozet_metni") or kat_ham
        konu = kategori_temizle(konu_raw)
        uret_nedir_dogrusu(p1, konu=konu, yanlis_metin=yanlis, dogru_metin=dogru, altin_kural=altin_kural)
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

        vaka_raw = veri.get("konu_kodu", "01 / EMSAL DOSYA")
        vaka_kodu = kategori_temizle(vaka_raw)
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
