"""
src/yeni_formatlar.py — EDM 4 Temel Format Görsel Motoru
1. EDM EMLAK SÖZLÜĞÜ (Kireç Bej Zemin, Dev Fraunces Kelime, Kitap Filigranı, Tırnaklı Hukuki Tanım)
2. NEDİR DOĞRUSU? (Mürekkep üst: yanlış inanış, Kağıt alt: doğrusu) + adım slaytları + kapanış
3. ÖRNEK OLAY (Siyah Editoryal Zemin, Fraunces Manşet, Kanuna Göre Sonuç, Alta Dayalı Ders Kartı) + adım slaytları + kapanış
4. NET CEVAP (Kağıt zemin; cevap sayfanın en büyük yazısı) + adım slaytları + kapanış

Sözlük tek kare kalır; diğer üçü 2026-09-24'ten beri çok slaytlıdır — tek kareler
her kanalda en düşük erişimdeydi. Zorunlu alan yoksa üretim durur (EksikIcerik);
koddaki genel cümleyle doldurulmaz.
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
# Alt bilgi kartı: eskiden amber (#EBAF37) — marka dışıydı. Çubuk kırmızı, etiket kireç.
RENK_KART_CUBUK = (240, 0, 13)
RENK_KART_ETIKET = (228, 228, 225)

FONT_FRAUNCES = config.yol_al("assets/fonts/Fraunces.ttf")
FONT_SANS_BOLD = make_image.FONT_SANS_BOLD      # IBM Plex Sans (make_image'daki gerekçe)
FONT_SANS_MEDIUM = make_image.FONT_SANS_MEDIUM
FONT_MONO = config.yol_al("assets/fonts/IBMPlexMono.ttf")
FONT_MONO_BOLD = config.yol_al("assets/fonts/IBMPlexMono-Bold.ttf")


# Hata sınıfları temel çizim modülünde tanımlı: B1/haber çizicileri de aynı
# sınıfı fırlatır ve telegram_bot'taki tek yakalama hepsini kapsar.
EksikIcerik = make_image.EksikIcerik
TasmaHatasi = make_image.TasmaHatasi


_OLCUM = ImageDraw.Draw(Image.new("RGB", (10, 10)))


def _satir_genisligi(metin: str, font: ImageFont.FreeTypeFont) -> int:
    return _OLCUM.textbbox((0, 0), metin, font=font)[2]


_SARMA_ONBELLEK: Dict[Tuple[str, str, int, int, int], List[str]] = {}


def _girintili_sar(metin: str, font: ImageFont.FreeTypeFont, genislik: int, girinti: int = 0) -> List[str]:
    """Ortak satır kırıcı (uzun kelimeyi de böler). İlk satır girintiyle sığmazsa
    bütün satırlar girinti kadar dar kırılır — girinti hiçbir zaman taşma yaratmaz.

    Sonuç önbelleğe alınır: yerleşim çözücü aynı metni onlarca punto/alan
    birleşiminde dener (uzun tanımda önbelleksiz 11 sn sürüyordu)."""
    anahtar = (metin or "", str(getattr(font, "path", "")), int(getattr(font, "size", 0)), genislik, girinti)
    if anahtar in _SARMA_ONBELLEK:
        return list(_SARMA_ONBELLEK[anahtar])
    satirlar = make_image._metin_sar(metin or "", font, genislik, _OLCUM)
    if girinti and satirlar and _satir_genisligi(satirlar[0], font) + girinti > genislik:
        satirlar = make_image._metin_sar(metin or "", font, genislik - girinti, _OLCUM)
    if len(_SARMA_ONBELLEK) > 4000:
        _SARMA_ONBELLEK.clear()
    _SARMA_ONBELLEK[anahtar] = satirlar
    return list(satirlar)


def _sigdir(
    metin: str,
    font_yolu: Path,
    puntolar: Any,
    genislik: int,
    azami_yukseklik: int,
    satir_carpani: float = 1.36,
    girinti_carpani: float = 0.0,
    azami_satir: Optional[int] = None,
) -> Optional[Tuple[ImageFont.FreeTypeFont, List[str], int, int]]:
    """Metni verilen alana sığan en büyük puntoyla kırar.
    Döner: (font, satırlar, satır yüksekliği, girinti) ya da sığmıyorsa None."""
    for punto in puntolar:
        font = make_image._font_yukle(font_yolu, punto)
        girinti = int(punto * girinti_carpani)
        satirlar = _girintili_sar(metin, font, genislik, girinti)
        satir_h = int(punto * satir_carpani)
        if len(satirlar) * satir_h <= azami_yukseklik and (azami_satir is None or len(satirlar) <= azami_satir):
            ilk_sigdi = not girinti or _satir_genisligi(satirlar[0], font) + girinti <= genislik if satirlar else True
            return font, satirlar, satir_h, (girinti if ilk_sigdi else 0)
    return None


def _madde_listesi(ham: Any) -> List[str]:
    """Sözlük "önem" maddeleri: liste ya da tek metin. Metin olduğu gibi kalır —
    eskiden "Başlık: açıklama" maddesinin başlığı atılıyordu, bu da içerik kaybıydı."""
    if ham is None:
        return []
    ogeler = ham if isinstance(ham, (list, tuple)) else [ham]
    sonuc = []
    for m in ogeler:
        if m is None:
            continue
        if isinstance(m, dict):
            metin = ": ".join(str(m.get(k)).strip() for k in ("baslik", "aciklama") if m.get(k))
        else:
            metin = str(m)
        metin = metin.strip()
        if metin:
            sonuc.append(metin)
    return sonuc

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
    """Emlak Sözlüğü kartı: terim (kahraman), tanım, alta dayalı "önemi" kutusu.

    Yerleşim ÖLÇÜLEREK çözülür (2026-09-25): önce kutu (bütün maddeler), sonra
    terim ve tanım kalan alana sığan en büyük puntoyla. Eskiden tanımın puntosu
    yalnızca karakter sayısından seçiliyordu ve #243'te son iki satır kutunun
    altında kaldı; kutu da maddelerin yalnızca ilk ikisini basıyordu.
    """
    canvas = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_KIREC_BEJ)
    canvas = make_image._filigran_uygula(canvas, acik_zemin=True)

    yer = make_image._yerlesim()
    kenar = yer["kenar"]
    kullanilabilir_w = GENISLIK - (2 * kenar)
    ku = yer["kronik_ust"]
    alt_y = yer["alt_bar"]
    ust_sinir = ku + 80
    ARA_TERIM_TANIM = 16 + 34 + 36   # çizgi + etiket boşluğu

    maddeler = _madde_listesi(puf_maddeleri)
    f_puf_etiket = make_image._font_yukle(FONT_MONO_BOLD, 20)

    def kutu_olc(punto: int):
        font = make_image._font_yukle(FONT_SANS_MEDIUM, punto)
        satir_h = int(punto * 1.36)
        bloklar = [_girintili_sar(m, font, kullanilabilir_w - 56 - 30) for m in maddeler]
        yukseklik = (52 + sum(len(b) for b in bloklar) * satir_h + (len(bloklar) - 1) * 12 + 24) if maddeler else 0
        return font, bloklar, satir_h, yukseklik

    # Öncelik OKUNAKLILIK: önce tanım rahat puntoda (≥36) tutulur, terim ona göre
    # küçülür; ikinci turda tanım 32'ye kadar iner. (Önceki sıra terimi 136px'te
    # tutup uzun tanımı 32px'e itiyordu.) Kısa tanım alan varsa 48px'e büyür.
    terim_olcu = {}

    def terim_olc(p: int):
        if p not in terim_olcu:
            terim_olcu[p] = _sigdir(terim, FONT_FRAUNCES, [p], kullanilabilir_w, 10_000, 1.15, azami_satir=2 if p > 76 else 3)
        return terim_olcu[p]

    cozum = None
    for tanim_puntolari, terim_puntolari in ((range(48, 35, -2), range(136, 75, -4)), (range(34, 31, -2), range(136, 59, -4))):
        for puf_p in (30, 28, 26, 24):
            f_puf, puf_bloklar, puf_h, h_kutu = kutu_olc(puf_p)
            kutu_y = alt_y - 26 - h_kutu
            tanim_alt = (kutu_y - 28) if h_kutu else (alt_y - 40)
            for tanim_p in tanim_puntolari:
                for terim_p in terim_puntolari:
                    terim_sonuc = terim_olc(terim_p)
                    if not terim_sonuc:
                        continue
                    f_terim, terim_satirlar, terim_h, _ = terim_sonuc
                    tanim_ust = ust_sinir + len(terim_satirlar) * terim_h + ARA_TERIM_TANIM
                    tanim_sonuc = _sigdir(tanim_metni, FONT_SANS_MEDIUM, [tanim_p], kullanilabilir_w,
                                          tanim_alt - tanim_ust, 1.38, girinti_carpani=1.6)
                    if tanim_sonuc:
                        cozum = (f_puf, puf_bloklar, puf_h, h_kutu, kutu_y, f_terim, terim_satirlar, terim_h, tanim_sonuc, tanim_alt)
                        break
                if cozum:
                    break
            if cozum:
                break
        if cozum:
            break
    if cozum is None:
        # Son şans: en küçük okunur puntolar
        f_puf, puf_bloklar, puf_h, h_kutu = kutu_olc(24)
        kutu_y = alt_y - 26 - h_kutu
        tanim_alt = (kutu_y - 28) if h_kutu else (alt_y - 40)
        terim_sonuc = _sigdir(terim, FONT_FRAUNCES, range(60, 47, -4), kullanilabilir_w, 10_000, 1.15, azami_satir=3)
        if terim_sonuc:
            f_terim, terim_satirlar, terim_h, _ = terim_sonuc
            tanim_ust = ust_sinir + len(terim_satirlar) * terim_h + ARA_TERIM_TANIM
            tanim_sonuc = _sigdir(tanim_metni, FONT_SANS_MEDIUM, (30, 28), kullanilabilir_w, tanim_alt - tanim_ust, 1.38, girinti_carpani=1.6)
            if tanim_sonuc:
                cozum = (f_puf, puf_bloklar, puf_h, h_kutu, kutu_y, f_terim, terim_satirlar, terim_h, tanim_sonuc, tanim_alt)
    if cozum is None:
        raise TasmaHatasi(
            f"Sözlük kartına sığmadı: terim {len(terim)}, tanım {len(tanim_metni or '')} karakter, "
            f"{len(maddeler)} madde ({sum(len(m) for m in maddeler)} karakter)"
        )

    f_puf, puf_bloklar, puf_h, h_kutu, kutu_y, f_terim, terim_satirlar, terim_h, tanim_sonuc, tanim_alt = cozum
    f_tanim, tanim_satirlar, tanim_h, girinti = tanim_sonuc
    f_tanim_punto = f_tanim.size

    # Dikey yerleşim: artan boşluk üste en fazla 36px, gerisi bloklar arasında kalır
    orta_h = len(terim_satirlar) * terim_h + ARA_TERIM_TANIM + len(tanim_satirlar) * tanim_h
    # Kalan boşluk üst ve alta 2'ye 3 oranında dağılır (eskiden hepsi tanımın altında kalıyordu)
    curr_y = ust_sinir + max(0, (tanim_alt - ust_sinir - orta_h) * 2 // 5)

    # Header
    kat_temiz = kategori_temizle(kategori)
    draw_init = ImageDraw.Draw(canvas)
    logo_x = GENISLIK - kenar - 285
    make_image._rozet_ciz(draw_init, kenar, ku, make_image._rozet_kirp(f"EMLAK SÖZLÜĞÜ // {kat_temiz.upper()}", 44),
                          bg_color=RENK_MUREKKEP, fg_color=RENK_BEYAZ, font_boyut=20, max_w=logo_x - kenar - 30)
    make_image._logo_yerlestir(canvas, beyaz=False, y=ku - 5, lw=285, golge=False, kirmizi_zemin=False)

    # Filigran Katmanı (Kitap filigranı + Paragraf başı '“' filigranı)
    overlay = Image.new("RGBA", (GENISLIK, YUKSEKLIK), (255, 255, 255, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    ciz_buyuk_sozluk_filigran_vector(overlay_draw, cx=320, cy=330, w=520, h=350, alpha=23)
    ty = curr_y + len(terim_satirlar) * terim_h + ARA_TERIM_TANIM
    if girinti:
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
        curr_y += terim_h
    curr_y += 16

    draw.line([(kenar, curr_y), (GENISLIK - kenar, curr_y)], fill=RENK_KIREC_BORDER, width=2)
    curr_y += 34

    draw.text((kenar, curr_y), "TANIM & ANLAMI", font=make_image._font_yukle(FONT_MONO_BOLD, 20), fill=RENK_KURSUN)
    curr_y += 36

    for i, s in enumerate(tanim_satirlar):
        draw.text((kenar + (girinti if i == 0 else 0), curr_y), s, font=f_tanim, fill=RENK_MUREKKEP)
        curr_y += tanim_h

    # Alta dayalı "önemi" kutusu — BÜTÜN maddeler, her biri ayrı satır
    if h_kutu:
        draw.rounded_rectangle([(kenar, kutu_y), (GENISLIK - kenar, kutu_y + h_kutu)], radius=12, fill=RENK_MUREKKEP, outline=(50, 53, 62), width=1)
        draw.rounded_rectangle([(kenar, kutu_y), (kenar + 6, kutu_y + h_kutu)], radius=2, fill=RENK_KART_CUBUK)
        draw.text((kenar + 28, kutu_y + 18), "YATIRIMCI İÇİN ÖNEMİ:", font=f_puf_etiket, fill=RENK_KART_ETIKET)
        py = kutu_y + 52
        for blok in puf_bloklar:
            draw.text((kenar + 28, py), "—", font=f_puf, fill=RENK_KART_ETIKET)
            for s in blok:
                draw.text((kenar + 28 + 30, py), s, font=f_puf, fill=RENK_BEYAZ)
                py += puf_h
            py += 12

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
    sayfa_no: str = "01 / 01",
) -> Path:
    w, h = GENISLIK, YUKSEKLIK
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    # Üst: mürekkep (yanlış inanış), alt: kağıt (doğrusu). Eskiden üst bordo, alt
    # saf beyazdı — akış kırmızıya boğuluyordu; marka oranı %5 kırmızı.
    r1, g1, b1 = RENK_MUREKKEP
    r2, g2, b2 = 244, 244, 243
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
    # Kural yoksa kart da yok: eskiden koddaki genel bir cümle basılıyordu
    h_kutu = (48 + (len(kural_satirlar) * 40) + 20) if (altin_kural or "").strip() else 0

    alt_bar_y = yer["alt_bar"]
    kutu_y = alt_bar_y - 26 - h_kutu

    # Doğru Metni: kalan alana sığan en büyük punto (46 → 30). Eskiden sığmayınca
    # en küçük puntoyla basılıp alttaki kural kutusunun ALTINA giriyordu; ortak
    # satır kırıcı uzun kelimeyi de böler (URL tuvalden taşıyordu).
    beyaz_alan_h = kutu_y - (y_end + 25)
    dogru_sonuc = _sigdir(dogru_metin, FONT_SANS_MEDIUM, range(46, 29, -2), kullanilabilir_w,
                          beyaz_alan_h - 36 - 44, 1.36, girinti_carpani=1.6)
    if dogru_sonuc is None:
        raise TasmaHatasi(f"Nedir Doğrusu: doğrusu ({len(dogru_metin or '')} karakter) ve kural kutusu karta sığmadı")
    f_dogru, dogru_satirlar, line_h_dogru, indent_px = dogru_sonuc
    best_punto = f_dogru.size

    h_dogru = len(dogru_satirlar) * line_h_dogru
    # "DOĞRUSU" etiketi (44px) metnin üstünde; etiket de alanın içinde kalsın
    alt_bosluk = max(0, (beyaz_alan_h - 44 - h_dogru) // 2)
    dogru_y = y_end + 25 + 44 + alt_bosluk

    # Filigran Katmanı (Sağ kenardan taşan kalın mimari Çarpı + Tik + Paragraf başı '“' filigranı)
    overlay = Image.new("RGBA", (GENISLIK, YUKSEKLIK), (255, 255, 255, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    cx_carpi = GENISLIK - 45
    cy_carpi = ku + 280
    ciz_vektor_carpi_filigran(overlay_draw, cx=cx_carpi, cy=cy_carpi, boy=300, renk=(240, 0, 13, 70), kalinlik=46)
    cx_tik = GENISLIK - 65
    cy_tik = dogru_y + 135
    # Yeşil tik marka dışıydı; kağıtta mürekkep filigran
    ciz_tik_filigran(overlay_draw, cx=cx_tik, cy=cy_tik, boy=320, renk=(18, 19, 22, 26), kalinlik=46)

    # Paragraf başı '“' filigranı (puntoyla orantılı)
    f_quote_size = int(best_punto * 1.85)
    f_quote = make_image._font_yukle(FONT_FRAUNCES, f_quote_size)
    overlay_draw.text((kenar + 2, dogru_y - int(best_punto * 0.22)), "“", font=f_quote, fill=(18, 19, 22, 55))

    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(canvas)

    konu_baslik = kategori_temizle(konu)
    make_image._rozet_ciz(draw, kenar, ku, f"NEDİR DOĞRUSU? // {konu_baslik.upper()}", bg_color=RENK_LOGO_KIRMIZI, fg_color=RENK_BEYAZ, font_boyut=20)
    make_image._logo_yerlestir(canvas, beyaz=True, y=ku - 5, lw=285, golge=True, kirmizi_zemin=False)

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
    else:
        raise TasmaHatasi(f"Nedir Doğrusu: yanlış inanış ({len(temiz_yanlis)} karakter) üst bölüme sığmadı")

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

    # "DOĞRUSU" etiketi: kağıt zeminde kırmızı yalnızca 18px üstü kalın metinde
    draw.text((kenar, dogru_y - 44), "DOĞRUSU", font=make_image._font_yukle(FONT_MONO_BOLD, 22), fill=RENK_LOGO_KIRMIZI)

    # EDM kuralı kartı (alta dayalı) — yalnızca model bir kural yazdıysa
    if h_kutu:
        draw.rounded_rectangle([(kenar, kutu_y), (GENISLIK - kenar, kutu_y + h_kutu)], radius=12, fill=RENK_MUREKKEP, outline=(55, 58, 66), width=1)
        draw.rounded_rectangle([(kenar, kutu_y), (kenar + 6, kutu_y + h_kutu)], radius=2, fill=RENK_KART_CUBUK)
        draw.text((kenar + 28, kutu_y + 18), "EDM KURALI:", font=f_kural_baslik, fill=RENK_KART_ETIKET)
        ky = kutu_y + 52
        for s in kural_satirlar:
            draw.text((kenar + 28, ky), s, font=f_kural_govde, fill=RENK_BEYAZ)
            ky += 40

    # Footer
    draw.line([(kenar, alt_bar_y), (GENISLIK - kenar, alt_bar_y)], fill=RENK_CIZGI_ACIK, width=1)
    draw.text((kenar, alt_bar_y + 26), "EDM YAPI & GAYRİMENKUL // NEDİR DOĞRUSU", font=make_image._font_yukle(FONT_MONO, 19), fill=RENK_KURSUN)
    sf = make_image._font_yukle(FONT_MONO_BOLD, 19)
    sw = draw.textbbox((0, 0), sayfa_no, font=sf)[2]
    draw.text((GENISLIK - kenar - sw, alt_bar_y + 26), sayfa_no, font=sf, fill=RENK_MUREKKEP)

    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


# =============================================================================
# 3. FORMAT: ÖRNEK OLAY (SLAYT 1 & SLAYT 2)
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
    # "Gerçek hukuki vaka" yanıltıcıydı: anlatılan tipik bir örnek olay, dava değil
    rozet_metni = f"ÖRNEK OLAY // {vaka_kodu.upper()}"
    make_image._rozet_ciz(draw, kenar, ku, rozet_metni, bg_color=(32, 35, 42), fg_color=RENK_BEYAZ, font_boyut=20, max_w=azami_rozet_w)
    make_image._logo_yerlestir(canvas, beyaz=True, y=ku - 5, lw=logo_w, golge=True, kirmizi_zemin=False)

    alt_y = yer["alt_bar"]
    draw.line([(kenar, alt_y), (GENISLIK - kenar, alt_y)], fill=RENK_CIZGI_KOYU, width=1)
    f_kaynak_alt = make_image._font_yukle(FONT_MONO, 17)
    # Dayanak yalnızca başlığın üstündeki rozette; alt bilgide tekrar edilmez
    draw.text((kenar, alt_y + 26), "EDM YAPI & GAYRİMENKUL // ÖRNEK OLAY", font=f_kaynak_alt, fill=RENK_KURSUN)
    sf = make_image._font_yukle(FONT_MONO_BOLD, 20)
    draw.text((GENISLIK - kenar - draw.textbbox((0, 0), sayfa_no, font=sf)[2], alt_y + 26), sayfa_no, font=sf, fill=RENK_BEYAZ)

    # Kırmızı "KAYDIRIN" şeridi kaldırıldı: kaydırma işareti diğer formatlardaki gibi
    # sayfa numarasındaki "›" (aynı bilgi iki yerde tekrarlanıyordu); alan olaya kalır.
    ust_sinir = yer["ust"] - 15
    dayanak_var = bool((yargitay_kaynak or "").strip())
    rozet_payi = 46 if dayanak_var else 0
    kullanilabilir_orta_h = (alt_y - 40) - ust_sinir - rozet_payi

    # Kaydırma şeridinin boşalttığı alan kullanılsın: başlık 88, olay 38'den başlar
    punto_manset = 88
    punto_olay = 38
    while punto_manset >= 52:
        f_manset_test = make_image._font_yukle(FONT_FRAUNCES, punto_manset)
        leading_manset_test = punto_manset + 16
        manset_satirlar_test = make_image._metin_sar(manset, f_manset_test, kullanilabilir_w, draw)
        h_manset_test = len(manset_satirlar_test) * leading_manset_test

        f_olay_test = make_image._font_yukle(FONT_SANS_MEDIUM, punto_olay)
        leading_olay_test = punto_olay + 18
        olay_satirlar_test = make_image._metin_sar(olay_detay, f_olay_test, kullanilabilir_w, draw)
        h_olay_test = len(olay_satirlar_test) * leading_olay_test

        if (h_manset_test + 28 + 32 + 36 + h_olay_test) <= kullanilabilir_orta_h:
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
        # Hiçbir punto birleşimi sığmadı: en küçük puntoyla basmak kutunun altına taşırdı
        raise TasmaHatasi(f"Örnek olay: başlık ({len(manset)}) ve olay ({len(olay_detay)} karakter) ilk slayta sığmadı")

    f_manset = make_image._font_yukle(FONT_FRAUNCES, punto_manset_final)
    f_etiket = make_image._font_yukle(FONT_MONO_BOLD, 21)
    f_olay = make_image._font_yukle(FONT_SANS_MEDIUM, punto_olay_final)

    h_manset = len(manset_satirlar) * leading_manset
    h_olay = len(olay_satirlar) * leading_olay
    toplam_orta_h = rozet_payi + h_manset + 28 + 32 + 36 + h_olay
    curr_y = ust_sinir + max(0, (kullanilabilir_orta_h + rozet_payi - toplam_orta_h) // 3)

    # "EMSAL İÇTİHAT" etiketi BDDK kararını bile mahkeme içtihadı gibi gösteriyordu (#157).
    # Dayanak yoksa rozet de yok (eskiden boş "DAYANAK //" basılıyordu).
    if dayanak_var:
        emsal_etiket = make_image._rozet_kirp(f"DAYANAK // {make_image.tr_buyuk(yargitay_kaynak)}", 60)
        make_image._rozet_ciz(draw, kenar, curr_y, emsal_etiket, bg_color=RENK_LOGO_KIRMIZI, fg_color=RENK_BEYAZ, font_boyut=17, max_w=kullanilabilir_w)
        curr_y += 46

    for s in manset_satirlar:
        draw.text((kenar, curr_y), s, font=f_manset, fill=RENK_BEYAZ)
        curr_y += leading_manset
    curr_y += 16

    draw.line([(kenar, curr_y), (GENISLIK - kenar, curr_y)], fill=RENK_CIZGI_KOYU, width=2)
    curr_y += 28

    # Anlatılan tipik bir örnek; mahkemeye yansımış gibi sunmak yanıltıcıydı
    draw.text((kenar, curr_y), "// ÖRNEK OLAY:", font=f_etiket, fill=RENK_KURSUN)
    curr_y += 36
    for s in olay_satirlar:
        draw.text((kenar, curr_y), s, font=f_olay, fill=(225, 230, 240))
        curr_y += leading_olay


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
    rozet_metni = rozet_baslik or f"ÖRNEK OLAY // {vaka_kodu.upper()} — SONUÇ"
    make_image._rozet_ciz(draw, kenar, ku, rozet_metni, bg_color=RENK_LOGO_KIRMIZI, fg_color=RENK_BEYAZ, font_boyut=20, max_w=azami_rozet_w)
    make_image._logo_yerlestir(canvas, beyaz=True, y=ku - 5, lw=logo_w, golge=True, kirmizi_zemin=False)

    alt_y = yer["alt_bar"]
    draw.line([(kenar, alt_y), (GENISLIK - kenar, alt_y)], fill=RENK_CIZGI_KOYU, width=1)
    # "Hukuk arşivi" avukatlık algısı yaratıyordu; biz emlak ofisiyiz
    alt_txt = alt_arsiv_metni or "EDM YAPI & GAYRİMENKUL // ÖRNEK OLAY"
    draw.text((kenar, alt_y + 26), alt_txt, font=make_image._font_yukle(FONT_MONO, 18), fill=RENK_KURSUN)
    sf = make_image._font_yukle(FONT_MONO_BOLD, 20)
    draw.text((GENISLIK - kenar - draw.textbbox((0, 0), sayfa_no, font=sf)[2], alt_y + 26), sayfa_no, font=sf, fill=RENK_BEYAZ)

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
    h_kutu = (54 + (len(ders_satirlar) * leading_ders) + 20) if (cikarilacak_ders or "").strip() else 0
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
        raise TasmaHatasi(f"Örnek olay: sonuç ({len(yargitay_hukmu)}) ve ders ({len(cikarilacak_ders or '')} karakter) ikinci slayta sığmadı")

    f_etiket = make_image._font_yukle(FONT_MONO_BOLD, 22)
    f_hukum = make_image._font_yukle(FONT_FRAUNCES, punto_hukum_final)

    hukum_blok_h = 36 + 18 + h_hukum
    curr_y = ust_sinir + min(36, max(0, mevcut_hukum_h - hukum_blok_h) // 3)
    # Belirli bir karar yokken "Yargıtay'ın verdiği kesin hüküm" demek yanıltıcı
    # (#157, 2026-09-21). Model artık karar numarası uyduramıyor; etiket de uydurmasın.
    etiket_txt = hukum_baslik or "KANUNA GÖRE SONUÇ"
    make_image._rozet_ciz(draw, kenar, curr_y, etiket_txt, bg_color=RENK_LOGO_KIRMIZI, fg_color=RENK_BEYAZ, font_boyut=17, max_w=kullanilabilir_w)
    curr_y += 44

    for s in hukum_satirlar:
        draw.text((kenar, curr_y), s, font=f_hukum, fill=RENK_BEYAZ)
        curr_y += leading_hukum

    if h_kutu:
        draw.rounded_rectangle([(kenar, kutu_y), (GENISLIK - kenar, kutu_y + h_kutu)], radius=12, fill=(28, 32, 42), outline=(55, 65, 85), width=1)
        draw.rounded_rectangle([(kenar, kutu_y), (kenar + 6, kutu_y + h_kutu)], radius=2, fill=RENK_KART_CUBUK)
        # Dava değil örnek olay: "bu davadan" yanıltıcıydı
        ders_etiket_txt = ders_baslik or "BU ÖRNEKTEN ÇIKARILACAK DERS:"
        draw.text((kenar + 28, kutu_y + 18), ders_etiket_txt, font=f_ders_etiket, fill=RENK_KART_ETIKET)

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
    draw.rounded_rectangle([(kenar, kutu_y), (kenar + 6, kutu_y + h_kutu)], radius=2, fill=RENK_KART_CUBUK)
    draw.text((kenar + 28, kutu_y + 18), "EDM UZMAN TAVSİYESİ:", font=f_tavsiye_baslik, fill=RENK_KART_ETIKET)
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
# 4b. NET CEVAP KAPAĞI (2026-09-24)
# =============================================================================
def _cumle_duzeni(metin: str) -> str:
    """Tamamı büyük harfle gelen metni cümle düzenine çeker (Türkçe İ/ı doğru)."""
    harfler = [c for c in metin if c.isalpha()]
    if not harfler or not all(c.isupper() for c in harfler):
        return metin
    kucuk = metin.replace("I", "ı").replace("İ", "i").lower()

    def buyut(m: "re.Match[str]") -> str:
        h = m.group(2)
        return m.group(1) + ("İ" if h == "i" else h.upper())

    # Metnin ve her cümlenin ilk harfi büyük ("Hayır. Önce …")
    return re.sub(r"(^|[.!?]\s+)(\w)", buyut, kucuk)


def uret_net_cevap_kapak(
    cikti_yolu: Path,
    kategori: str,
    soru: str,
    net_cevap: str,
    gerekce: str,
    sayfa_no: str = "01 / 01",
) -> Path:
    """Net Cevap kapağı: soru küçük, CEVAP sayfanın en büyük yazısı.

    Eski tek kare tasarımda cevap, sorunun altında 22 piksellik mono bir
    şeritteydi — formatın varlık sebebi olan cevap telefonda okunmuyordu
    (2026-09-24 denetimi). Kağıt zemin, mürekkep yazı; kırmızı yalnızca
    cevabın üstündeki kısa çizgide (marka oranı %5 kırmızı).
    """
    cevap = re.sub(r"^\s*CEVAP\s*[:：]\s*", "", net_cevap or "", flags=re.IGNORECASE).strip()
    cevap = _cumle_duzeni(cevap)
    soru = (soru or "").strip()
    gerekce = (gerekce or "").strip()

    with make_image.tuval("besleme"):
        canvas, draw, p = make_image._slayt_cercevesi(
            "kagit", f"NET CEVAP // {kategori_temizle(kategori)}",
            "EDM YAPI & GAYRİMENKUL // NET CEVAP", sayfa_no,
        )
        yer = make_image._yerlesim()
        kenar = yer["kenar"]
        genislik = make_image.GENISLIK - 2 * kenar
        ust, alt = yer["ust"], yer["alt"]
        alan = alt - ust

        def olc(metin: str, font_yolu: Path, punto: int, satir_carpani: float):
            f = make_image._font_yukle(font_yolu, punto)
            satirlar = make_image._metin_sar(metin, f, genislik, draw) if metin else []
            return f, satirlar, int(punto * satir_carpani)

        secim = None
        # Kısa cevap daha iri (128px'e kadar), gerekçe 40px'e kadar büyür
        for c_p in range(128, 51, -4):
            for s_p, g_p in ((48, 40), (46, 36), (42, 34), (38, 31), (36, 29)):
                fs, ss, lhs = olc(soru, FONT_FRAUNCES, s_p, 1.22)
                fc, sc, lhc = olc(cevap, FONT_FRAUNCES, c_p, 1.1)
                fg, sg, lhg = olc(gerekce, FONT_SANS_MEDIUM, g_p, 1.42)
                h = len(ss) * lhs + 34 + 8 + 40 + len(sc) * lhc + (44 + len(sg) * lhg if sg else 0)
                if h <= alan and len(sc) <= 5 and len(ss) <= 3:
                    secim = (fs, ss, lhs, fc, sc, lhc, fg, sg, lhg, h)
                    break
            if secim:
                break
        if secim is None:
            # Eskiden gerekçe sessizce kısaltılıyordu: okur yarım cümle görürdü
            raise TasmaHatasi(f"Net Cevap: soru ({len(soru)}), cevap ({len(cevap)}) ve gerekçe ({len(gerekce)} karakter) kapağa sığmadı")
        fs, ss, lhs, fc, sc, lhc, fg, sg, lhg, h = secim

        # İri "?" filigranı sağ üstte, kireç tonunda
        overlay = Image.new("RGBA", (make_image.GENISLIK, make_image.YUKSEKLIK), (0, 0, 0, 0))
        ImageDraw.Draw(overlay).text(
            (make_image.GENISLIK - kenar - 190, ust - 60), "?",
            font=make_image._font_yukle(FONT_FRAUNCES, 300), fill=(18, 19, 22, 16),
        )
        canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(canvas)

        y = ust + max(0, (alan - h) * 2 // 5)
        for satir in ss:
            draw.text((kenar, y), satir, font=fs, fill=p["govde"])
            y += lhs
        y += 34
        draw.rectangle([(kenar, y), (kenar + 96, y + 8)], fill=make_image.RENK_KIRMIZI)
        y += 8 + 40
        for satir in sc:
            draw.text((kenar, y), satir, font=fc, fill=p["ana"])
            y += lhc
        if sg:
            y += 44
            for satir in sg:
                draw.text((kenar, y), satir, font=fg, fill=p["govde"])
                y += lhg

    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


# =============================================================================
# OTOMATİK ŞABLON SEÇİCİ VE ÜRETİCİ DİSPATCHER
# =============================================================================
def _ilk_dolu(*degerler: Any) -> str:
    for d in degerler:
        if isinstance(d, str) and d.strip():
            return d.strip()
    return ""


def _kartlar(veri: Dict[str, Any]) -> List[Dict[str, Any]]:
    s2 = veri.get("slayt_2_detay") or {}
    if not isinstance(s2, dict):
        return []
    kartlar = [k for k in (s2.get("kartlar") or []) if isinstance(k, dict)]
    if not kartlar:
        kartlar = [k for k in (s2.get("kart_1"), s2.get("kart_2")) if isinstance(k, dict)]
    return kartlar


def _adimlar(veri: Dict[str, Any]) -> List[Dict[str, str]]:
    s3 = veri.get("slayt_3_cozum") or {}
    ham = s3.get("maddeler") if isinstance(s3, dict) else None
    sonuc: List[Dict[str, str]] = []
    for i, m in enumerate(ham or [], start=1):
        if isinstance(m, dict) and _ilk_dolu(m.get("baslik"), m.get("aciklama")):
            sonuc.append({"no": str(m.get("no") or f"{i:02d}"), "baslik": _ilk_dolu(m.get("baslik")),
                          "aciklama": _ilk_dolu(m.get("aciklama"))})
        elif isinstance(m, str) and m.strip():
            baslik, _, aciklama = m.partition(":")
            sonuc.append({"no": f"{i:02d}", "baslik": baslik.strip(), "aciklama": aciklama.strip()})
    return sonuc[:5]


def _sayfa(sira: int, toplam: int) -> str:
    etiket = f"{sira:02d} / {toplam:02d}"
    return etiket if sira >= toplam else f"{etiket}  ›"


def _devam_slaytlari(
    veri: Dict[str, Any],
    adimlar: List[Dict[str, str]],
    cikti_dizini: Path,
    cikti_onek: str,
    bas_sira: int,
    toplam: int,
) -> List[Path]:
    """Format kapağından sonraki slaytlar: her adım ayrı sayfa + kapanış.

    Tek kare formatlar (Nedir Doğrusu, Net Cevap, Vaka) her kanalda en düşük
    erişimdeydi; çok slaytlı B1 en yüksekti (2026-09-24 denetimi). Adımlar
    kağıt zeminde — akış mürekkep ve kırmızıya boğuluyordu.
    """
    yollar: List[Path] = []
    normal = make_image.veriyi_normalize_et(veri)
    rozet = _ilk_dolu((veri.get("slayt_3_cozum") or {}).get("baslik_vurgu") if isinstance(veri.get("slayt_3_cozum"), dict) else "",
                      veri.get("rozet_metni"), "ATILACAK ADIMLAR")
    with make_image.tuval("besleme"):
        for i, m in enumerate(adimlar):
            sira = bas_sira + i
            yol = cikti_dizini / f"{cikti_onek}_{sira:02d}_adim.jpg"
            yollar.append(make_image.slayt_adim(
                "kagit", rozet, m["no"], m["baslik"], m["aciklama"], len(adimlar),
                "EDM YAPI & GAYRİMENKUL // DANIŞMANLIK", _sayfa(sira, toplam), yol,
            ))
        normal["_toplam_slayt"] = toplam
        yol = cikti_dizini / f"{cikti_onek}_{toplam:02d}_kapanis.jpg"
        yollar.append(make_image.slayt_kapanis(normal, _sayfa(toplam, toplam), yol))
    return yollar


def slaytlari_uret(
    veri: Dict[str, Any],
    cikti_dizini: Optional[Path] = None,
    cikti_onek: str = "post",
    format_turu: Optional[str] = None,
    olcu: str = "besleme",
) -> List[Path]:
    """İçerik verisinden formatın slaytlarını üretir.

    Sözlük tek karedir. Nedir Doğrusu, Net Cevap ve Vaka kendi kapak(lar)ının
    ardından adım slaytlarına ve kapanışa açılır. Tanınmayan biçim standart
    B1 carousel'e gider.

    Zorunlu alan yoksa `EksikIcerik` fırlatır — koddaki genel cümleyle doldurmaz.
    """
    if cikti_dizini is None:
        cikti_dizini = config.yol_al("data/output/gonderiler")
    cikti_dizini = Path(cikti_dizini)
    cikti_dizini.mkdir(parents=True, exist_ok=True)

    format_turu = str(format_turu or veri.get("format_turu") or veri.get("format") or "").lower()
    kat_ham = veri.get("kategori") or veri.get("kategori_kodu") or "TAPU VE HUKUK"
    kategori = kategori_temizle(kat_ham)
    brief = veri.get("_brief", {}) or {}
    kartlar = _kartlar(veri)
    adimlar = _adimlar(veri)

    # 1. SÖZLÜK — tek kare kalır (kullanıcı kararı, 2026-09-24)
    if format_turu in ("sozluk", "sozluk_uret") or ("terim" in veri and ("tanim_metni" in veri or "tanim" in veri)):
        terim = _ilk_dolu(veri.get("terim"), veri.get("manset_vurgu"))
        tanim = _ilk_dolu(veri.get("tanim_metni"), veri.get("tanim"), veri.get("spot"))
        if not terim or not tanim:
            raise EksikIcerik("Sözlük: terim ya da tanım üretilmedi")
        # Liste yerine düz metin gelirse karakter karakter bölünmesin
        maddeler = _madde_listesi(veri.get("puf_maddeleri") or veri.get("maddeler"))
        if not maddeler:
            maddeler = [f"{a['baslik']}: {a['aciklama']}".strip(": ") for a in adimlar[:3]]
        p1 = cikti_dizini / f"{cikti_onek}_sozluk.jpg"
        uret_sozluk(p1, terim=terim, kategori=kategori, tanim_metni=tanim, puf_maddeleri=maddeler)
        log.info("Format üretildi (SÖZLÜK): %s", p1)
        return [p1]

    # 2. NEDİR DOĞRUSU
    if format_turu in ("nedir_dogrusu", "dogrusu", "yaygin_yanlis") or ("yanlis_metin" in veri and "dogru_metin" in veri):
        # Manşet ya da spot "yanlış" diye kullanılamaz: onlar DOĞRU bilgiyi taşır
        yanlis = _ilk_dolu(veri.get("yanlis_metin"), (kartlar[0].get("aciklama") if kartlar else ""))
        dogru = _ilk_dolu(veri.get("dogru_metin"), (kartlar[1].get("aciklama") if len(kartlar) > 1 else ""), veri.get("spot"))
        if not yanlis or not dogru:
            raise EksikIcerik("Nedir Doğrusu: yanlış inanış ya da doğrusu üretilmedi")
        toplam = 1 + len(adimlar) + 1
        p1 = cikti_dizini / f"{cikti_onek}_01_nedir_dogrusu.jpg"
        konu = kategori_temizle(veri.get("konu") or veri.get("rozet_metni") or kat_ham)
        uret_nedir_dogrusu(p1, konu=konu, yanlis_metin=yanlis, dogru_metin=dogru,
                           altin_kural=_ilk_dolu(veri.get("altin_kural")), sayfa_no=_sayfa(1, toplam))
        yollar = [p1] + _devam_slaytlari(veri, adimlar, cikti_dizini, cikti_onek, 2, toplam)
        log.info("Format üretildi (NEDİR DOĞRUSU, %d slayt)", len(yollar))
        return yollar

    # 3. NET CEVAP
    if format_turu in ("net_cevap", "soru", "kim_hakli") or ("soru" in veri and "net_cevap" in veri and "aciklama" in veri):
        soru = _ilk_dolu(veri.get("soru"))
        cevap = _ilk_dolu(veri.get("net_cevap"),
                          " ".join(x for x in (veri.get("manset_vurgu"), veri.get("manset_parca_2")) if x))
        if not soru or not cevap:
            raise EksikIcerik("Net Cevap: soru ya da cevap üretilmedi")
        if not soru.endswith("?"):
            soru += "?"
        tavsiye = _ilk_dolu(veri.get("tavsiye_metin"), veri.get("tavsiye"))
        if not adimlar and tavsiye:
            adimlar = [{"no": "01", "baslik": "Ne yapmalı", "aciklama": tavsiye}]
        toplam = 1 + len(adimlar) + 1
        p1 = cikti_dizini / f"{cikti_onek}_01_net_cevap.jpg"
        uret_net_cevap_kapak(p1, kategori=kat_ham, soru=soru, net_cevap=cevap,
                             gerekce=_ilk_dolu(veri.get("aciklama"), veri.get("spot")), sayfa_no=_sayfa(1, toplam))
        yollar = [p1] + _devam_slaytlari(veri, adimlar, cikti_dizini, cikti_onek, 2, toplam)
        log.info("Format üretildi (NET CEVAP, %d slayt)", len(yollar))
        return yollar

    # 4. ÖRNEK OLAY (vaka)
    if format_turu in ("vaka", "emsal_karar") or ("yargitay_hukmu" in veri and "cikarilacak_ders" in veri):
        olay = _ilk_dolu(veri.get("olay_detay"), veri.get("spot"))
        hukum = _ilk_dolu(veri.get("yargitay_hukmu"), (kartlar[0].get("aciklama") if kartlar else ""))
        if not olay or not hukum:
            raise EksikIcerik("Örnek olay: olay ya da kanuna göre sonuç üretilmedi")
        manset = _ilk_dolu(veri.get("manset"), " ".join(
            x for x in (veri.get("manset_parca_1"), veri.get("manset_vurgu"), veri.get("manset_parca_2")) if x))
        # Dayanak yalnızca içerikte ya da brief'te varsa; "Yargıtay Emsal İçtihadı" yedeği uydurmaydı
        kaynak = _ilk_dolu(veri.get("yargitay_kaynak"), veri.get("yasal_dayanak"), brief.get("mevzuat"))
        vaka_kodu = kategori_temizle(veri.get("vaka_kodu") or veri.get("konu_kodu") or kat_ham)
        toplam = 2 + len(adimlar) + 1
        p1 = cikti_dizini / f"{cikti_onek}_01_vaka.jpg"
        p2 = cikti_dizini / f"{cikti_onek}_02_vaka.jpg"
        uret_vaka_slayt1(p1, vaka_kodu=vaka_kodu, yargitay_kaynak=kaynak, manset=manset or olay[:75],
                         olay_detay=olay, sayfa_no=_sayfa(1, toplam))
        uret_vaka_slayt2(p2, vaka_kodu=vaka_kodu, yargitay_hukmu=hukum,
                         cikarilacak_ders=_ilk_dolu(veri.get("cikarilacak_ders")), sayfa_no=_sayfa(2, toplam))
        yollar = [p1, p2] + _devam_slaytlari(veri, adimlar, cikti_dizini, cikti_onek, 3, toplam)
        log.info("Format üretildi (ÖRNEK OLAY, %d slayt)", len(yollar))
        return yollar

    # 5. DAILYBRIEF HABER FORMATI
    if format_turu in ("dailybrief", "haber", "haber_dailybrief") or veri.get("bicim") in ("haber", "B5"):
        foto_yolu = veri.get("foto_yolu") or veri.get("gorsel_yolu")
        slaytlar = make_image.haber_dailybrief_slaytlari_uret(
            haber=veri,
            cikti_dizini=cikti_dizini,
            cikti_onek=cikti_onek,
            olcu=olcu,
            foto_yolu=foto_yolu,
        )
        log.info("Format üretildi (HABER, %d slayt)", len(slaytlar))
        return slaytlar

    # Tanınmayan biçim: standart çok slaytlı carousel. Eskiden B1/B2/B3 veri
    # tek karelik formatlara "uyarlanıyor", eksik alanlar sabit cümlelerle
    # dolduruluyordu (bkz. EksikIcerik).
    return make_image.otorite_gonderi_slaytlari_uret(veri, cikti_onek=cikti_onek, olcu=olcu)
