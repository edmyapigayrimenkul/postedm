"""
src/kapanis_stilleri.py
EDM Yapı & Gayrimenkul — Kapanış Slaytı Stilleri Motoru

Desteklenen 11 Stil:
1. kartvizit: Lüks Kabartmalı Kartvizit (Floating Stationery)
2. kitap_afis: Merkezlenmiş Editoryal Kitap/Afiş (Centered Monolith)
3. split_screen: Çift Renk Zemin Bölünmesi (Kağıt & Derin Obsidyen)
4. mimari_pafta: Teknik Mimari Pafta, GPS Koordinat & Lejant Anteti
5. kurucu_mektubu: Kurucu Mektubu & Islak İmza & Samimi Çağrı
6. paspartu_fotograf: Paspartu Fotoğraf Penceresi & Galeri Katalog
7. dikey_tipografi: 90° Dikey Tipografi Şeridi & İskandinav Marjin
8. iletisim_terminali: Minimalist İletişim Terminali / 4 Satırlı Dashboard
9. dev_numara: Tipografik Monolit / 92px Dev Numara Posteri
10. resmi_muhur: Dairesel Onay Mührü & Resmi Danışmanlık Sertifikası
11. editoryal: Kutusuz Saf Tipografik Editoryal Düzen
"""

from __future__ import annotations
import logging
import math
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from PIL import Image, ImageDraw, ImageFilter
import qrcode

from src import config
from src.make_image import (
    GENISLIK, YUKSEKLIK, FONT_FRAUNCES, FONT_SANS_BOLD, FONT_SANS_SEMIBOLD,
    FONT_SANS_MEDIUM, FONT_MONO, FONT_MONO_BOLD, _font_yukle, _yerlesim,
    _filigran_uygula, _rozet_ciz, _logo_yerlestir, _vektor_ikon_uret,
    _temizle_tipografi, _govde_sigdir, _metin_sar, _slayt_cercevesi,
    _arti_isareti_ciz, _temiz_arkaplan_al
)

GECICI_DIZIN = config.yol_al("data/output")

GEN = 1080
YUK = 1350
KENAR = 72

log = logging.getLogger(__name__)


def __getattr__(name: str) -> Any:
    """Dinamik tuval ölçülerini make_image'den canlı alır (story/besleme uyumu)."""
    if name == "GEN":
        import src.make_image as mi
        return mi.GENISLIK
    elif name == "YUK":
        import src.make_image as mi
        return mi.YUKSEKLIK
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# EDM Renk Paleti
RENK_KAGIT = (246, 245, 241)
RENK_KAGIT_BEYAZ = (255, 255, 255)
RENK_KOYU = (18, 20, 24)
RENK_KIRMIZI = (217, 43, 43)
RENK_GRI_METIN = (88, 92, 98)
RENK_SILIK = (138, 142, 148)
RENK_CIZGI = (218, 222, 218)
RENK_MUREKKEP = (14, 16, 20)

VARSAYILAN_QR = "https://maps.google.com/?q=Alibey+Mah+Albay+Yunus+Dirik+Cad+No+58A+Silivri"


def _bilgileri_derle(veri: Dict[str, Any]) -> Dict[str, str]:
    """Veri sözlüğünden ve config'den tüm iletişim parametrelerini temizleyip derler."""
    cta = veri.get("slayt_4_cta") or {}
    s1 = _temizle_tipografi(str(cta.get("slogan_parca_1") or "Doğru adımlarla"))
    s2 = _temizle_tipografi(str(cta.get("slogan_vurgu") or "GÜVENLİ KİRALAMA"))
    aciklama = _temizle_tipografi(str(cta.get("aciklama") or "Silivri ve Trakya genelinde mülk yönetimi ve hukuki süreçlerinizde yanınızdayız."))
    kaydet = _temizle_tipografi(str(
        cta.get("kaydet_metni")
        or veri.get("kaydet_metni")
        or "BU REHBERİ KAYDEDİN · İHTİYAÇ ANINDA ELİNİZİN ALTINDA OLSUN"
    ))

    tel = str(veri.get("telefon") or config.ayar_al("kurum.telefon", "0536 343 41 97")).strip()
    isim = _temizle_tipografi(str(veri.get("danisman_isim") or "METİN ÖZDOĞAN"))
    unvan = _temizle_tipografi(str(veri.get("danisman_unvan") or "Kurucu Danışman"))
    adres = _temizle_tipografi(str(veri.get("adres") or config.ayar_al("kurum.adres", "Alibey Mah. Albay Yunus Dirik Cad. No: 58/A · Silivri")))
    eposta = str(veri.get("eposta") or config.ayar_al("kurum.eposta", "info@edmyapigayrimenkul.com")).strip()
    site = str(veri.get("site") or config.ayar_al("kurum.web_sitesi", "edmyapigayrimenkul.com")).replace("https://", "").replace("http://", "").strip("/")
    hesap = str(veri.get("hesap") or "@edmyapigayrimenkul").strip()
    qr_link = str(veri.get("qr_link") or VARSAYILAN_QR).strip()
    rozet = _temizle_tipografi(str(veri.get("rozet_metni") or "EDM DANIŞMANLIK"))

    return {
        "s1": s1, "s2": s2, "aciklama": aciklama, "kaydet": kaydet,
        "tel": tel, "isim": isim, "unvan": unvan, "adres": adres,
        "eposta": eposta, "site": site, "hesap": hesap, "qr_link": qr_link,
        "rozet": rozet
    }


def _qr_uret(link: str, boyut: int, zemin: str = "#ffffff", muhur: str = "#121316") -> Image.Image:
    """Verilen link için optimize edilmiş QR kod üretir."""
    q = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=4, border=1)
    q.add_data(link[:500] if link else VARSAYILAN_QR)
    q.make(fit=True)
    g = q.make_image(fill_color=muhur, back_color=zemin).convert("RGB")
    return g.resize((boyut, boyut), Image.Resampling.LANCZOS)


def _cikti_belirle(cikti_yolu: Optional[Path], stil_adi: str) -> Path:
    """Çıktı yolunu belirler veya geçici dizinde benzersiz yol oluşturur."""
    if cikti_yolu:
        yol = Path(cikti_yolu)
    else:
        import uuid
        yol = GECICI_DIZIN / f"kapanis_{stil_adi}_{uuid.uuid4().hex[:8]}.jpg"
    yol.parent.mkdir(parents=True, exist_ok=True)
    return yol


# =============================================================================
# 1. LÜKS KARTVİZİT (FLOATING STATIONERY CARD)
# =============================================================================
def ciz_01_luks_kartvizit(veri: Dict[str, Any], sayfa: str = "04 / 04", cikti_yolu: Optional[Path] = None) -> Path:
    b = _bilgileri_derle(veri)
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    canvas = _filigran_uygula(canvas, acik_zemin=True)
    draw = ImageDraw.Draw(canvas)
    yer = _yerlesim()

    _rozet_ciz(draw, KENAR, yer["kronik_ust"], b["rozet"], bg_color=(235, 238, 235), fg_color=RENK_KOYU, font_boyut=20)
    _logo_yerlestir(canvas, beyaz=False, y=yer["kronik_ust"] - 5, lw=285, golge=True)

    y = yer["ust"] + 15
    f_b = _font_yukle(FONT_FRAUNCES, 56)
    max_w = GEN - (2 * KENAR)
    s1_satirlar = _metin_sar(b["s1"], f_b, max_w, draw)[:1]
    s2_satirlar = _metin_sar(b["s2"], f_b, max_w, draw)[:1]
    draw.text((KENAR, y), s1_satirlar[0] if s1_satirlar else "", font=f_b, fill=RENK_KOYU); y += 64
    draw.text((KENAR, y), s2_satirlar[0] if s2_satirlar else "", font=f_b, fill=RENK_KIRMIZI); y += 76

    f_a = _font_yukle(FONT_SANS_MEDIUM, 28)
    a_satirlar = _metin_sar(b["aciklama"], f_a, max_w, draw)[:2]
    for sat in a_satirlar:
        draw.text((KENAR, y), sat, font=f_a, fill=RENK_GRI_METIN)
        y += 40
    y += 18

    # Rozet: Kaydet
    k_metin = b["kaydet"]
    f_k = _font_yukle(FONT_MONO_BOLD, 15)
    pad_k = 24
    kw = draw.textbbox((0, 0), k_metin, font=f_k)[2]
    max_kw = max_w - (pad_k * 2) - 40
    if kw > max_kw:
        while kw > max_kw and len(k_metin) > 10:
            k_metin = k_metin[:-2] + "…"
            kw = draw.textbbox((0, 0), k_metin, font=f_k)[2]
    pill_w = min(max_w, kw + (pad_k * 2) + 20)
    draw.rounded_rectangle([(KENAR, y), (KENAR + pill_w, y + 42)], radius=21, fill=(236, 238, 236))
    try:
        b_ik = _vektor_ikon_uret("bookmark", 18, RENK_KIRMIZI)
        canvas.paste(b_ik, (KENAR + pad_k, y + 12), b_ik)
    except Exception as e:
        # Sessiz kalırsa slayt ikonsuz/logosuz çıkar ve kimse fark etmez
        log.warning("Kapanış slaytı: marka öğesi çizilemedi: %s", e)
    draw.text((KENAR + pad_k + 24, y + 13), k_metin, font=f_k, fill=RENK_KOYU)

    # Havada Süzülen Lüks Kartvizit
    kart_w = GEN - (2 * KENAR)
    kart_h = 380
    kart_x = KENAR
    kart_y = yer["alt"] - kart_h - 40

    golge_katman = Image.new("RGBA", (GEN, YUK), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(golge_katman)
    g_draw.rounded_rectangle([(kart_x + 6, kart_y + 18), (kart_x + kart_w - 6, kart_y + kart_h + 24)], radius=24, fill=(0, 0, 0, 48))
    golge_katman = golge_katman.filter(ImageFilter.GaussianBlur(22))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), golge_katman).convert("RGB")
    draw = ImageDraw.Draw(canvas)

    draw.rounded_rectangle([(kart_x, kart_y), (kart_x + kart_w, kart_y + kart_h)], radius=20, fill=RENK_KAGIT_BEYAZ)
    draw.rectangle([(kart_x + 2, kart_y), (kart_x + kart_w - 2, kart_y + 6)], fill=RENK_KIRMIZI)

    kx = kart_x + 44
    ky = kart_y + 40
    draw.text((kx, ky), b["isim"], font=_font_yukle(FONT_SANS_BOLD, 36), fill=RENK_KOYU); ky += 44
    draw.text((kx, ky), f"{b['unvan']} · EDM Yapı & Gayrimenkul", font=_font_yukle(FONT_SANS_MEDIUM, 22), fill=RENK_GRI_METIN); ky += 44

    draw.text((kx, ky), "DOĞRUDAN HAT", font=_font_yukle(FONT_MONO_BOLD, 15), fill=RENK_KIRMIZI); ky += 24
    draw.text((kx, ky), b["tel"], font=_font_yukle(FONT_MONO_BOLD, 52), fill=RENK_KOYU); ky += 68

    adres_satirlar = _metin_sar(b["adres"], _font_yukle(FONT_SANS_MEDIUM, 20), kart_w - 44 - 170, draw)[:1]
    draw.text((kx, ky), adres_satirlar[0] if adres_satirlar else "", font=_font_yukle(FONT_SANS_MEDIUM, 20), fill=RENK_GRI_METIN); ky += 30
    draw.text((kx, ky), f"{b['site']}   ·   {b['eposta']}", font=_font_yukle(FONT_MONO, 17), fill=RENK_SILIK)

    qr = _qr_uret(b["qr_link"], 164)
    qr_x = kart_x + kart_w - 44 - 164
    qr_y = kart_y + 115
    canvas.paste(qr, (qr_x, qr_y))
    draw.text((qr_x + 36, qr_y + 172), "OFİS KONUMU", font=_font_yukle(FONT_MONO_BOLD, 13), fill=RENK_SILIK)

    draw.text((KENAR, yer["alt_bar"] + 26), "EDM YAPI & GAYRİMENKUL", font=_font_yukle(FONT_MONO, 19), fill=RENK_SILIK)
    draw.text((GEN - KENAR - 80, yer["alt_bar"] + 26), sayfa, font=_font_yukle(FONT_MONO_BOLD, 19), fill=RENK_KIRMIZI)

    yol = _cikti_belirle(cikti_yolu, "01_luks_kartvizit")
    canvas.save(yol, "JPEG", quality=95)
    return yol


# =============================================================================
# 2. MERKEZLENMİŞ EDİTORYAL KİTAP / AFİŞ (CENTERED MONOLITH)
# =============================================================================
def ciz_02_merkezlenmis_kitap_afis(veri: Dict[str, Any], sayfa: str = "04 / 04", cikti_yolu: Optional[Path] = None) -> Path:
    b = _bilgileri_derle(veri)
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    canvas = _filigran_uygula(canvas, acik_zemin=True)
    draw = ImageDraw.Draw(canvas)
    yer = _yerlesim()

    rozet_txt = f"{b['rozet']} REHBERİ"
    f_roz = _font_yukle(FONT_MONO_BOLD, 16)
    rw = draw.textbbox((0, 0), rozet_txt, font=f_roz)[2]
    draw.rounded_rectangle([(GEN//2 - rw//2 - 20, yer["kronik_ust"]), (GEN//2 + rw//2 + 20, yer["kronik_ust"] + 36)], radius=18, fill=(236, 238, 236))
    draw.text((GEN//2 - rw//2, yer["kronik_ust"] + 9), rozet_txt, font=f_roz, fill=RENK_KOYU)

    y = yer["ust"] + 40
    f_b = _font_yukle(FONT_FRAUNCES, 62)
    w1 = draw.textbbox((0, 0), b["s1"], font=f_b)[2]
    w2 = draw.textbbox((0, 0), b["s2"], font=f_b)[2]
    draw.text((GEN//2 - w1//2, y), b["s1"], font=f_b, fill=RENK_KOYU); y += 72
    draw.text((GEN//2 - w2//2, y), b["s2"], font=f_b, fill=RENK_KIRMIZI); y += 82

    f_a = _font_yukle(FONT_SANS_MEDIUM, 26)
    a_satirlar = _metin_sar(b["aciklama"], f_a, GEN - 160, draw)[:2]
    for sat in a_satirlar:
        sw = draw.textbbox((0, 0), sat, font=f_a)[2]
        draw.text((GEN//2 - sw//2, y), sat, font=f_a, fill=RENK_GRI_METIN)
        y += 36
    y += 30

    qr_sz = 184
    qr = _qr_uret(b["qr_link"], qr_sz)
    qr_x = GEN//2 - qr_sz//2
    qr_y = y
    canvas.paste(qr, (qr_x, qr_y))
    y += qr_sz + 18

    f_qr_lbl = _font_yukle(FONT_MONO_BOLD, 13)
    lbl = "OFİS KONUMU // QR KODU OKUTUN"
    lw = draw.textbbox((0, 0), lbl, font=f_qr_lbl)[2]
    draw.text((GEN//2 - lw//2, y), lbl, font=f_qr_lbl, fill=RENK_SILIK); y += 46

    f_tel = _font_yukle(FONT_MONO_BOLD, 54)
    tw = draw.textbbox((0, 0), b["tel"], font=f_tel)[2]
    draw.text((GEN//2 - tw//2, y), b["tel"], font=f_tel, fill=RENK_KOYU); y += 68

    f_isim = _font_yukle(FONT_SANS_BOLD, 26)
    isim_txt = f"{b['isim']}  ·  {b['unvan']}"
    iw = draw.textbbox((0, 0), isim_txt, font=f_isim)[2]
    draw.text((GEN//2 - iw//2, y), isim_txt, font=f_isim, fill=RENK_KOYU); y += 38

    f_ad = _font_yukle(FONT_SANS_MEDIUM, 20)
    aw = draw.textbbox((0, 0), b["adres"], font=f_ad)[2]
    draw.text((GEN//2 - aw//2, y), b["adres"], font=f_ad, fill=RENK_GRI_METIN); y += 32

    f_web = _font_yukle(FONT_MONO, 18)
    web_txt = f"{b['site']}   ·   {b['eposta']}"
    ww = draw.textbbox((0, 0), web_txt, font=f_web)[2]
    draw.text((GEN//2 - ww//2, y), web_txt, font=f_web, fill=RENK_SILIK); y += 52

    f_k = _font_yukle(FONT_MONO_BOLD, 15)
    kw = draw.textbbox((0, 0), b["kaydet"], font=f_k)[2]
    draw.text((GEN//2 - kw//2, yer["alt"] - 10), b["kaydet"], font=f_k, fill=RENK_KIRMIZI)

    yol = _cikti_belirle(cikti_yolu, "02_merkezlenmis_kitap_afis")
    canvas.save(yol, "JPEG", quality=95)
    return yol


# =============================================================================
# 3. SPLIT-SCREEN (ÇİFT RENK / GECE-GÜNDÜZ ZEMİN)
# =============================================================================
def ciz_03_split_screen(veri: Dict[str, Any], sayfa: str = "04 / 04", cikti_yolu: Optional[Path] = None) -> Path:
    b = _bilgileri_derle(veri)
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    draw = ImageDraw.Draw(canvas)
    yer = _yerlesim()

    split_y = int(YUK * 0.44)
    draw.rectangle([(0, split_y), (GEN, YUK)], fill=RENK_MUREKKEP)
    draw.rectangle([(0, split_y), (GEN, split_y + 4)], fill=RENK_KIRMIZI)

    _rozet_ciz(draw, KENAR, yer["kronik_ust"], b["rozet"], bg_color=(235, 238, 235), fg_color=RENK_KOYU, font_boyut=20)
    _logo_yerlestir(canvas, beyaz=False, y=yer["kronik_ust"] - 5, lw=285, golge=True)

    y = yer["ust"] + 10
    f_b = _font_yukle(FONT_FRAUNCES, 56)
    draw.text((KENAR, y), b["s1"], font=f_b, fill=RENK_KOYU); y += 64
    draw.text((KENAR, y), b["s2"], font=f_b, fill=RENK_KIRMIZI); y += 72

    f_a = _font_yukle(FONT_SANS_MEDIUM, 27)
    a_satirlar = _metin_sar(b["aciklama"], f_a, GEN - (2 * KENAR), draw)[:2]
    for sat in a_satirlar:
        draw.text((KENAR, y), sat, font=f_a, fill=RENK_GRI_METIN)
        y += 38
    y += 12

    try:
        b_ik = _vektor_ikon_uret("bookmark", 20, RENK_KIRMIZI)
        canvas.paste(b_ik, (KENAR, y - 2), b_ik)
    except Exception as e:
        # Sessiz kalırsa slayt ikonsuz/logosuz çıkar ve kimse fark etmez
        log.warning("Kapanış slaytı: marka öğesi çizilemedi: %s", e)
    draw.text((KENAR + 28, y), b["kaydet"], font=_font_yukle(FONT_MONO_BOLD, 15), fill=RENK_KOYU)

    by = split_y + 54
    draw.text((KENAR, by), "DOĞRUDAN DANIŞMANLIK HATTI", font=_font_yukle(FONT_MONO_BOLD, 17), fill=RENK_KIRMIZI); by += 34
    draw.text((KENAR, by), b["tel"], font=_font_yukle(FONT_MONO_BOLD, 64), fill=(255, 255, 255)); by += 96
    draw.text((KENAR, by), f"{b['isim']}   ·   {b['unvan']}", font=_font_yukle(FONT_SANS_BOLD, 26), fill=(245, 245, 245)); by += 44
    draw.text((KENAR, by), b["adres"], font=_font_yukle(FONT_SANS_MEDIUM, 21), fill=(185, 190, 195)); by += 38
    draw.text((KENAR, by), f"{b['site']}   ·   {b['eposta']}", font=_font_yukle(FONT_MONO, 19), fill=(140, 145, 155)); by += 32
    draw.text((KENAR, by), b["hesap"], font=_font_yukle(FONT_MONO, 18), fill=(140, 145, 155))

    qr = _qr_uret(b["qr_link"], 168, zemin="#ffffff", muhur="#121418")
    qr_x = GEN - KENAR - 168
    qr_y = split_y + 60
    draw.rounded_rectangle([(qr_x - 8, qr_y - 8), (qr_x + 168 + 8, qr_y + 168 + 48)], radius=12, fill=(24, 28, 34))
    canvas.paste(qr, (qr_x, qr_y))
    draw.text((qr_x + 36, qr_y + 168 + 14), "OFİS KONUMU", font=_font_yukle(FONT_MONO_BOLD, 13), fill=(180, 185, 195))

    draw.text((KENAR, yer["alt_bar"] + 26), "EDM YAPI & GAYRİMENKUL // DANIŞMANLIK", font=_font_yukle(FONT_MONO, 18), fill=(100, 105, 115))
    draw.text((GEN - KENAR - 80, yer["alt_bar"] + 26), sayfa, font=_font_yukle(FONT_MONO_BOLD, 19), fill=RENK_KIRMIZI)

    yol = _cikti_belirle(cikti_yolu, "03_split_screen")
    canvas.save(yol, "JPEG", quality=95)
    return yol


# =============================================================================
# 4. TEKNİK MİMARİ PAFTA & ANTET (ARCHITECTURAL BLUEPRINT)
# =============================================================================
def ciz_04_mimari_pafta(veri: Dict[str, Any], sayfa: str = "04 / 04", cikti_yolu: Optional[Path] = None) -> Path:
    b = _bilgileri_derle(veri)
    canvas = Image.new("RGB", (GEN, YUK), (245, 246, 242))
    draw = ImageDraw.Draw(canvas)
    yer = _yerlesim()

    grid_gap = 90
    grid_renk = (232, 235, 230)
    for x in range(0, GEN, grid_gap):
        draw.line([(x, 0), (x, YUK)], fill=grid_renk, width=1)
    for y in range(0, YUK, grid_gap):
        draw.line([(0, y), (GEN, y)], fill=grid_renk, width=1)

    for px, py in [(KENAR, 120), (GEN - KENAR, 120), (KENAR, YUK - 120), (GEN - KENAR, YUK - 120), (GEN//2, yer["ust"])]:
        _arti_isareti_ciz(draw, px, py, renk=RENK_KIRMIZI, boyut=16)

    draw.text((KENAR, 62), "KOORDİNAT: 41°04'26.8\"N  28°14'48.2\"E  //  PAFTA NO: #EDM-2026-SLV", font=_font_yukle(FONT_MONO_BOLD, 14), fill=RENK_SILIK)
    _logo_yerlestir(canvas, beyaz=False, y=52, lw=285, golge=True)

    y = yer["ust"] + 20
    f_b = _font_yukle(FONT_FRAUNCES, 54)
    draw.text((KENAR, y), b["s1"], font=f_b, fill=RENK_KOYU); y += 62
    draw.text((KENAR, y), b["s2"], font=f_b, fill=RENK_KIRMIZI); y += 74

    f_a = _font_yukle(FONT_SANS_MEDIUM, 27)
    a_satirlar = _metin_sar(b["aciklama"], f_a, GEN - (2 * KENAR), draw)[:2]
    for sat in a_satirlar:
        draw.text((KENAR, y), sat, font=f_a, fill=RENK_GRI_METIN)
        y += 38
    y += 12

    draw.text((KENAR, y), b["kaydet"], font=_font_yukle(FONT_MONO_BOLD, 14), fill=RENK_KOYU); y += 50

    antet_y = yer["alt"] - 360
    draw.rectangle([(KENAR, antet_y), (GEN - KENAR, yer["alt"] - 20)], fill=(255, 255, 255), outline=RENK_KOYU, width=2)
    draw.rectangle([(KENAR, antet_y), (GEN - KENAR, antet_y + 36)], fill=RENK_KOYU)
    draw.text((KENAR + 18, antet_y + 9), "DANIŞMANLIK & RESMİ İLETİŞİM ANTETİ // SİLİVRİ MERKEZ OFİS", font=_font_yukle(FONT_MONO_BOLD, 14), fill=(255, 255, 255))

    ay = antet_y + 54
    ax = KENAR + 28
    draw.text((ax, ay), "DANIŞMAN / FOUNDER", font=_font_yukle(FONT_MONO_BOLD, 14), fill=RENK_KIRMIZI); ay += 24
    draw.text((ax, ay), b["isim"], font=_font_yukle(FONT_SANS_BOLD, 28), fill=RENK_KOYU); ay += 40

    draw.text((ax, ay), "DOĞRUDAN TELEFON / WHATSAPP", font=_font_yukle(FONT_MONO_BOLD, 14), fill=RENK_KIRMIZI); ay += 24
    draw.text((ax, ay), b["tel"], font=_font_yukle(FONT_MONO_BOLD, 46), fill=RENK_KOYU); ay += 58

    draw.text((ax, ay), b["adres"], font=_font_yukle(FONT_SANS_MEDIUM, 19), fill=RENK_GRI_METIN); ay += 28
    draw.text((ax, ay), f"{b['site']}   ·   {b['eposta']}", font=_font_yukle(FONT_MONO, 17), fill=RENK_SILIK)

    qr = _qr_uret(b["qr_link"], 170)
    qr_x = GEN - KENAR - 170 - 24
    qr_y = antet_y + 54
    canvas.paste(qr, (qr_x, qr_y))
    draw.text((qr_x + 10, qr_y + 178), "PARSELE / KONUMA GİT", font=_font_yukle(FONT_MONO_BOLD, 13), fill=RENK_KOYU)
    draw.line([(qr_x - 24, antet_y + 36), (qr_x - 24, yer["alt"] - 20)], fill=RENK_CIZGI, width=1)

    yol = _cikti_belirle(cikti_yolu, "04_mimari_pafta")
    canvas.save(yol, "JPEG", quality=95)
    return yol


# =============================================================================
# 5. KURUCU MEKTUBU & ISLAK İMZA (FOUNDER'S LETTER)
# =============================================================================
def ciz_05_kurucu_mektubu(veri: Dict[str, Any], sayfa: str = "04 / 04", cikti_yolu: Optional[Path] = None) -> Path:
    b = _bilgileri_derle(veri)
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    canvas = _filigran_uygula(canvas, acik_zemin=True)
    draw = ImageDraw.Draw(canvas)
    yer = _yerlesim()

    _rozet_ciz(draw, KENAR, yer["kronik_ust"], "KURUCU NOTU // BİREBİR GÜVENCE", bg_color=(235, 238, 235), fg_color=RENK_KOYU, font_boyut=18)
    _logo_yerlestir(canvas, beyaz=False, y=yer["kronik_ust"] - 5, lw=285, golge=True)

    y = yer["ust"] + 20
    f_b = _font_yukle(FONT_FRAUNCES, 50)
    draw.text((KENAR, y), "“Gayrimenkulde doğru karar,", font=f_b, fill=RENK_KOYU); y += 60
    draw.text((KENAR, y), "sahada doğru rehberle başlar.”", font=f_b, fill=RENK_KIRMIZI); y += 80

    f_mektup = _font_yukle(FONT_SANS_MEDIUM, 26)
    satirlar = [
        "Silivri ve Trakya genelinde gayrimenkul kiralarken veya yatırım",
        "yaparken her adımın teknik ve hukuki bir karşılığı vardır.",
        "Kulaktan dolma bilgiler yerine bizzat yerinde incelediğimiz",
        "doğrulanmış verilerle yanınızdayız.",
        "",
        "Resmi imzanızı atmadan önce dosyanızı birlikte incelemek",
        "ve kahvemizi içmek için ofisimize her zaman beklerim."
    ]
    for sat in satirlar:
        if sat:
            draw.text((KENAR, y), sat, font=f_mektup, fill=RENK_KOYU)
        y += 38
    y += 24

    imza_y = y
    draw.line([(KENAR, imza_y + 50), (KENAR + 340, imza_y + 50)], fill=RENK_CIZGI, width=1)
    draw.text((KENAR + 10, imza_y), b["isim"].title(), font=_font_yukle(FONT_FRAUNCES, 44), fill=RENK_KIRMIZI)
    draw.text((KENAR + 10, imza_y + 60), f"{b['isim']}  ·  {b['unvan']}", font=_font_yukle(FONT_SANS_BOLD, 22), fill=RENK_KOYU)
    draw.text((KENAR + 10, imza_y + 90), "EDM Yapı & Gayrimenkul", font=_font_yukle(FONT_SANS_MEDIUM, 19), fill=RENK_GRI_METIN)

    sag_x = GEN - KENAR - 280
    qr = _qr_uret(b["qr_link"], 144)
    canvas.paste(qr, (sag_x + 136, imza_y - 20))
    draw.text((sag_x + 154, imza_y + 132), "OFİS KONUMU", font=_font_yukle(FONT_MONO_BOLD, 12), fill=RENK_SILIK)

    by = yer["alt"] - 130
    draw.line([(KENAR, by - 24), (GEN - KENAR, by - 24)], fill=RENK_CIZGI, width=1)
    draw.text((KENAR, by), "DOĞRUDAN TELEFON:", font=_font_yukle(FONT_MONO_BOLD, 16), fill=RENK_KIRMIZI)
    draw.text((KENAR + 210, by - 4), b["tel"], font=_font_yukle(FONT_MONO_BOLD, 38), fill=RENK_KOYU)
    draw.text((GEN - KENAR - 320, by + 4), b["site"], font=_font_yukle(FONT_MONO_BOLD, 19), fill=RENK_KOYU)
    by += 44
    draw.text((KENAR, by), b["adres"], font=_font_yukle(FONT_SANS_MEDIUM, 20), fill=RENK_GRI_METIN)
    draw.text((GEN - KENAR - 320, by), b["eposta"], font=_font_yukle(FONT_MONO, 18), fill=RENK_SILIK)

    draw.text((KENAR, yer["alt"] - 14), b["kaydet"], font=_font_yukle(FONT_SANS_MEDIUM, 15), fill=RENK_SILIK)

    yol = _cikti_belirle(cikti_yolu, "05_kurucu_mektubu")
    canvas.save(yol, "JPEG", quality=95)
    return yol


# =============================================================================
# 6. PASPARTU FOTOĞRAF PENCERESİ (PHOTO PASSEPARTOUT)
# =============================================================================
def ciz_06_paspartu_fotograf(veri: Dict[str, Any], sayfa: str = "04 / 04", cikti_yolu: Optional[Path] = None) -> Path:
    b = _bilgileri_derle(veri)
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    draw = ImageDraw.Draw(canvas)
    yer = _yerlesim()

    _rozet_ciz(draw, KENAR, yer["kronik_ust"], b["rozet"], bg_color=(235, 238, 235), fg_color=RENK_KOYU, font_boyut=20)
    _logo_yerlestir(canvas, beyaz=False, y=yer["kronik_ust"] - 5, lw=285, golge=True)

    y = yer["ust"] + 10
    f_b = _font_yukle(FONT_FRAUNCES, 50)
    draw.text((KENAR, y), b["s1"], font=f_b, fill=RENK_KOYU); y += 58
    draw.text((KENAR, y), b["s2"], font=f_b, fill=RENK_KIRMIZI); y += 68

    foto_w = GEN - (2 * KENAR)
    foto_h = 320
    foto_y = y
    try:
        foto_kaynak = _temiz_arkaplan_al("DANISMANLIK")
        foto = foto_kaynak.resize((foto_w, foto_h), Image.Resampling.LANCZOS).convert("RGBA")
        filtre = Image.new("RGBA", (foto_w, foto_h), (18, 22, 28, 120))
        foto = Image.alpha_composite(foto, filtre)
        canvas.paste(foto, (KENAR, foto_y))
    except Exception:
        draw.rectangle([(KENAR, foto_y), (KENAR + foto_w, foto_y + foto_h)], fill=(230, 232, 230))

    draw.rectangle([(KENAR, foto_y), (KENAR + foto_w, foto_y + foto_h)], outline=RENK_CIZGI, width=1)
    draw.rectangle([(KENAR + 24, foto_y + foto_h - 48), (KENAR + 380, foto_y + foto_h - 18)], fill=(12, 14, 18))
    draw.text((KENAR + 36, foto_y + foto_h - 42), "SİLİVRİ & TRAKYA SAHA OPERASYONU", font=_font_yukle(FONT_MONO_BOLD, 13), fill=(255, 255, 255))

    y = foto_y + foto_h + 26
    draw.text((KENAR, y), b["kaydet"], font=_font_yukle(FONT_MONO_BOLD, 15), fill=RENK_KOYU); y += 46

    by = y
    draw.text((KENAR, by), "DOĞRUDAN HAT", font=_font_yukle(FONT_MONO_BOLD, 16), fill=RENK_KIRMIZI); by += 30
    draw.text((KENAR, by), b["tel"], font=_font_yukle(FONT_MONO_BOLD, 52), fill=RENK_KOYU); by += 76
    draw.text((KENAR, by), f"{b['isim']}  ·  {b['unvan']}", font=_font_yukle(FONT_SANS_SEMIBOLD, 24), fill=RENK_KOYU); by += 38
    draw.text((KENAR, by), b["adres"], font=_font_yukle(FONT_SANS_MEDIUM, 21), fill=RENK_GRI_METIN); by += 32
    draw.text((KENAR, by), f"{b['site']}   ·   {b['eposta']}", font=_font_yukle(FONT_MONO, 18), fill=RENK_SILIK)

    qr = _qr_uret(b["qr_link"], 148)
    canvas.paste(qr, (GEN - KENAR - 148, y + 10))
    draw.text((GEN - KENAR - 148 + 26, y + 10 + 148 + 8), "OFİS KONUMU", font=_font_yukle(FONT_MONO_BOLD, 12), fill=RENK_SILIK)

    draw.text((KENAR, yer["alt"] - 14), "Bu içerik genel bilgilendirmedir; bağlayıcı hukuki görüş için avukatınıza danışın.", font=_font_yukle(FONT_SANS_MEDIUM, 16), fill=RENK_SILIK)

    yol = _cikti_belirle(cikti_yolu, "06_paspartu_fotograf")
    canvas.save(yol, "JPEG", quality=95)
    return yol


# =============================================================================
# 7. DİKEY 90° TİPOGRAFİ (SCANDINAVIAN ASYMMETRIC)
# =============================================================================
def ciz_07_dikey_tipografi(veri: Dict[str, Any], sayfa: str = "04 / 04", cikti_yolu: Optional[Path] = None) -> Path:
    b = _bilgileri_derle(veri)
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    canvas = _filigran_uygula(canvas, acik_zemin=True)
    draw = ImageDraw.Draw(canvas)
    yer = _yerlesim()

    dikey_metin = f"EDM YAPI & GAYRİMENKUL  ·  SİLİVRİ SAHA DANIŞMANLIĞI  ·  {b['tel']}"
    f_dik = _font_yukle(FONT_MONO_BOLD, 17)
    txt_img = Image.new("RGBA", (900, 40), (0, 0, 0, 0))
    t_draw = ImageDraw.Draw(txt_img)
    t_draw.text((0, 8), dikey_metin, font=f_dik, fill=RENK_KIRMIZI)
    txt_rot = txt_img.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)
    canvas.paste(txt_rot, (KENAR - 24, yer["ust"] + 20), txt_rot)

    ayrac_x = KENAR + 42
    draw.line([(ayrac_x, yer["ust"]), (ayrac_x, yer["alt"] - 10)], fill=RENK_CIZGI, width=1)

    sag_x = ayrac_x + 40
    sag_w = GEN - KENAR - sag_x

    _logo_yerlestir(canvas, beyaz=False, y=yer["kronik_ust"] - 5, lw=285, golge=True)

    y = yer["ust"] + 30
    f_b = _font_yukle(FONT_FRAUNCES, 56)
    draw.text((sag_x, y), b["s1"], font=f_b, fill=RENK_KOYU); y += 66
    draw.text((sag_x, y), b["s2"], font=f_b, fill=RENK_KIRMIZI); y += 78

    f_a = _font_yukle(FONT_SANS_MEDIUM, 28)
    a_satirlar = _metin_sar(b["aciklama"], f_a, sag_w, draw)[:3]
    for sat in a_satirlar:
        draw.text((sag_x, y), sat, font=f_a, fill=RENK_GRI_METIN)
        y += 38
    y += 20

    draw.text((sag_x, y), b["kaydet"], font=_font_yukle(FONT_MONO_BOLD, 15), fill=RENK_KOYU); y += 48
    draw.rectangle([(sag_x, y), (sag_x + 140, y + 3)], fill=RENK_KIRMIZI); y += 42

    draw.text((sag_x, y), "DOĞRUDAN HAT", font=_font_yukle(FONT_MONO_BOLD, 16), fill=RENK_SILIK); y += 28
    draw.text((sag_x, y), b["tel"], font=_font_yukle(FONT_MONO_BOLD, 54), fill=RENK_KOYU); y += 78
    draw.text((sag_x, y), f"{b['isim']}  ·  {b['unvan']}", font=_font_yukle(FONT_SANS_BOLD, 24), fill=RENK_KOYU); y += 38
    draw.text((sag_x, y), b["adres"], font=_font_yukle(FONT_SANS_MEDIUM, 20), fill=RENK_GRI_METIN); y += 34
    draw.text((sag_x, y), f"{b['site']}   ·   {b['eposta']}", font=_font_yukle(FONT_MONO, 18), fill=RENK_SILIK)

    qr = _qr_uret(b["qr_link"], 156)
    canvas.paste(qr, (GEN - KENAR - 156, y - 90))
    draw.text((GEN - KENAR - 156 + 30, y - 90 + 156 + 8), "OFİS KONUMU", font=_font_yukle(FONT_MONO_BOLD, 12), fill=RENK_SILIK)

    draw.text((sag_x, yer["alt"] - 14), "Bu içerik genel bilgilendirmedir; bağlayıcı hukuki görüş için avukatınıza danışın.", font=_font_yukle(FONT_SANS_MEDIUM, 16), fill=RENK_SILIK)

    yol = _cikti_belirle(cikti_yolu, "07_dikey_tipografi")
    canvas.save(yol, "JPEG", quality=95)
    return yol


# =============================================================================
# 8. MİNİMALİST İLETİŞİM TERMİNALİ (DASHBOARD ICON LIST)
# =============================================================================
def ciz_08_iletisim_terminali(veri: Dict[str, Any], sayfa: str = "04 / 04", cikti_yolu: Optional[Path] = None) -> Path:
    b = _bilgileri_derle(veri)
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    canvas = _filigran_uygula(canvas, acik_zemin=True)
    draw = ImageDraw.Draw(canvas)
    yer = _yerlesim()

    _rozet_ciz(draw, KENAR, yer["kronik_ust"], "HIZLI İLETİŞİM DİREKTÖRÜ", bg_color=(235, 238, 235), fg_color=RENK_KOYU, font_boyut=20)
    _logo_yerlestir(canvas, beyaz=False, y=yer["kronik_ust"] - 5, lw=285, golge=True)

    y = yer["ust"] + 15
    f_b = _font_yukle(FONT_FRAUNCES, 54)
    draw.text((KENAR, y), b["s1"], font=f_b, fill=RENK_KOYU); y += 62
    draw.text((KENAR, y), b["s2"], font=f_b, fill=RENK_KIRMIZI); y += 74

    f_a = _font_yukle(FONT_SANS_MEDIUM, 27)
    a_satirlar = _metin_sar(b["aciklama"], f_a, GEN - (2 * KENAR), draw)[:2]
    for sat in a_satirlar:
        draw.text((KENAR, y), sat, font=f_a, fill=RENK_GRI_METIN)
        y += 38
    y += 24

    terminal_y = y
    kanallar = [
        ("phone", "DOĞRUDAN HAT", b["tel"], "Haftanın 7 günü arayabilir / WhatsApp yazabilirsiniz."),
        ("pin", "OFİS ADRESİ", b["adres"], "Silivri / İstanbul (Merkez Ofis)"),
        ("web", "WEB SİTESİ", b["site"], "Tüm ilanlar ve kurumsal danışmanlık rehberleri"),
        ("mail", "E-POSTA", b["eposta"], "Resmi yazışma ve dosya inceleme talepleri"),
    ]

    for ik_ad, baslik, deger, aciklama in kanallar:
        draw.line([(KENAR, terminal_y), (GEN - KENAR, terminal_y)], fill=(228, 232, 228), width=1)
        try:
            ik = _vektor_ikon_uret(ik_ad, 28, RENK_KIRMIZI)
            canvas.paste(ik, (KENAR + 10, terminal_y + 16), ik)
        except Exception as e:
            # Sessiz kalırsa slayt ikonsuz/logosuz çıkar ve kimse fark etmez
            log.warning("Kapanış slaytı: marka öğesi çizilemedi: %s", e)
        draw.text((KENAR + 62, terminal_y + 12), baslik, font=_font_yukle(FONT_MONO_BOLD, 14), fill=RENK_KIRMIZI)
        draw.text((KENAR + 62, terminal_y + 32), deger, font=_font_yukle(FONT_MONO_BOLD if ik_ad == "phone" else FONT_SANS_BOLD, 26 if ik_ad == "phone" else 22), fill=RENK_KOYU)
        draw.text((KENAR + 62, terminal_y + 64), aciklama, font=_font_yukle(FONT_SANS_MEDIUM, 17), fill=RENK_SILIK)
        terminal_y += 94

    draw.line([(KENAR, terminal_y), (GEN - KENAR, terminal_y)], fill=(228, 232, 228), width=1)

    qr = _qr_uret(b["qr_link"], 150)
    canvas.paste(qr, (GEN - KENAR - 150, terminal_y + 18))
    draw.text((GEN - KENAR - 150 + 26, terminal_y + 18 + 150 + 6), "KONUMU TARA", font=_font_yukle(FONT_MONO_BOLD, 12), fill=RENK_SILIK)

    draw.text((KENAR, terminal_y + 24), f"{b['isim']}  ·  {b['unvan']}", font=_font_yukle(FONT_SANS_BOLD, 24), fill=RENK_KOYU)
    draw.text((KENAR, terminal_y + 58), "Silivri ve Trakya Gayrimenkul Yatırım Direktörlüğü", font=_font_yukle(FONT_SANS_MEDIUM, 19), fill=RENK_GRI_METIN)
    draw.text((KENAR, terminal_y + 96), b["kaydet"], font=_font_yukle(FONT_MONO_BOLD, 14), fill=RENK_KIRMIZI)

    yol = _cikti_belirle(cikti_yolu, "08_iletisim_terminali")
    canvas.save(yol, "JPEG", quality=95)
    return yol


# =============================================================================
# 9. TİPOGRAFİK MONOLİT / DEV NUMARA POSTERİ (MEGA NUMBER DIRECT CTA)
# =============================================================================
def ciz_09_dev_numara(veri: Dict[str, Any], sayfa: str = "04 / 04", cikti_yolu: Optional[Path] = None) -> Path:
    b = _bilgileri_derle(veri)
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    canvas = _filigran_uygula(canvas, acik_zemin=True)
    draw = ImageDraw.Draw(canvas)
    yer = _yerlesim()

    _rozet_ciz(draw, KENAR, yer["kronik_ust"], "EDM // TEK HAT", bg_color=(235, 238, 235), fg_color=RENK_KOYU, font_boyut=20)
    _logo_yerlestir(canvas, beyaz=False, y=yer["kronik_ust"] - 5, lw=285, golge=True)

    y = yer["ust"] + 20
    f_b = _font_yukle(FONT_FRAUNCES, 56)
    draw.text((KENAR, y), b["s1"], font=f_b, fill=RENK_KOYU); y += 64
    draw.text((KENAR, y), b["s2"], font=f_b, fill=RENK_KIRMIZI); y += 76

    f_a = _font_yukle(FONT_SANS_MEDIUM, 28)
    draw.text((KENAR, y), b["aciklama"], font=f_a, fill=RENK_GRI_METIN); y += 50
    draw.text((KENAR, y), b["kaydet"], font=_font_yukle(FONT_MONO_BOLD, 15), fill=RENK_KOYU); y += 40

    draw.line([(KENAR, y), (GEN - KENAR, y)], fill=RENK_CIZGI, width=1); y += 30
    draw.text((KENAR, y), "DOĞRUDAN DANIŞMANLIK & İLETİŞİM HATTI", font=_font_yukle(FONT_MONO_BOLD, 18), fill=RENK_KIRMIZI); y += 36
    draw.text((KENAR, y), b["tel"], font=_font_yukle(FONT_MONO_BOLD, 92), fill=RENK_KOYU); y += 128
    draw.line([(KENAR, y), (GEN - KENAR, y)], fill=RENK_CIZGI, width=1); y += 36

    draw.text((KENAR, y), b["isim"], font=_font_yukle(FONT_SANS_BOLD, 32), fill=RENK_KOYU); y += 42
    draw.text((KENAR, y), f"EDM Yapı & Gayrimenkul  ·  {b['unvan']}", font=_font_yukle(FONT_SANS_MEDIUM, 22), fill=RENK_GRI_METIN); y += 42
    draw.text((KENAR, y), b["adres"], font=_font_yukle(FONT_SANS_MEDIUM, 21), fill=RENK_GRI_METIN); y += 34
    draw.text((KENAR, y), f"{b['site']}   ·   {b['eposta']}", font=_font_yukle(FONT_MONO, 19), fill=RENK_SILIK)

    qr = _qr_uret(b["qr_link"], 164)
    canvas.paste(qr, (GEN - KENAR - 164, y - 110))
    draw.text((GEN - KENAR - 164 + 32, y - 110 + 164 + 8), "OFİS KONUMU", font=_font_yukle(FONT_MONO_BOLD, 13), fill=RENK_SILIK)

    draw.text((KENAR, yer["alt"] - 14), "Bu içerik genel bilgilendirmedir; bağlayıcı hukuki görüş için avukatınıza danışın.", font=_font_yukle(FONT_SANS_MEDIUM, 16), fill=RENK_SILIK)

    yol = _cikti_belirle(cikti_yolu, "09_dev_numara")
    canvas.save(yol, "JPEG", quality=95)
    return yol


# =============================================================================
# 10. RESMİ EKSPERTİZ MÜHRÜ & SERTİFİKA (OFFICIAL SEAL CERTIFICATE)
# =============================================================================
def ciz_10_resmi_muhur(veri: Dict[str, Any], sayfa: str = "04 / 04", cikti_yolu: Optional[Path] = None) -> Path:
    b = _bilgileri_derle(veri)
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    canvas = _filigran_uygula(canvas, acik_zemin=True)
    draw = ImageDraw.Draw(canvas)
    yer = _yerlesim()

    seal_r = 110
    seal_cx = GEN - KENAR - seal_r - 10
    seal_cy = yer["ust"] + 110
    draw.ellipse([(seal_cx - seal_r, seal_cy - seal_r), (seal_cx + seal_r, seal_cy + seal_r)], outline=RENK_KIRMIZI, width=2)
    draw.ellipse([(seal_cx - seal_r + 8, seal_cy - seal_r + 8), (seal_cx + seal_r - 8, seal_cy + seal_r - 8)], outline=RENK_KIRMIZI, width=1)

    f_seal_c = _font_yukle(FONT_MONO_BOLD, 15)
    draw.text((seal_cx - 48, seal_cy - 36), "★ ★ ★", font=f_seal_c, fill=RENK_KIRMIZI)
    draw.text((seal_cx - 62, seal_cy - 12), "DOĞRULANMIŞ", font=_font_yukle(FONT_MONO_BOLD, 15), fill=RENK_KIRMIZI)
    draw.text((seal_cx - 62, seal_cy + 12), "SAHA REHBERİ", font=_font_yukle(FONT_MONO_BOLD, 15), fill=RENK_KIRMIZI)
    draw.text((seal_cx - 40, seal_cy + 36), "SİLİVRİ", font=_font_yukle(FONT_MONO_BOLD, 13), fill=RENK_KOYU)

    _rozet_ciz(draw, KENAR, yer["kronik_ust"], "RESMİ ONAYLI DANIŞMANLIK", bg_color=(235, 238, 235), fg_color=RENK_KOYU, font_boyut=18)
    _logo_yerlestir(canvas, beyaz=False, y=yer["kronik_ust"] - 5, lw=285, golge=True)

    y = yer["ust"] + 20
    f_b = _font_yukle(FONT_FRAUNCES, 54)
    draw.text((KENAR, y), b["s1"], font=f_b, fill=RENK_KOYU); y += 62
    draw.text((KENAR, y), b["s2"], font=f_b, fill=RENK_KIRMIZI); y += 74

    f_a = _font_yukle(FONT_SANS_MEDIUM, 27)
    a_satirlar = _metin_sar(b["aciklama"], f_a, GEN - (2 * KENAR) - 230, draw)[:2]
    for sat in a_satirlar:
        draw.text((KENAR, y), sat, font=f_a, fill=RENK_GRI_METIN)
        y += 38
    y += 12

    draw.text((KENAR, y), b["kaydet"], font=_font_yukle(FONT_MONO_BOLD, 14), fill=RENK_KOYU); y += 46

    draw.line([(KENAR, y), (GEN - KENAR, y)], fill=RENK_CIZGI, width=1); y += 36

    by = y
    draw.text((KENAR, by), "YETKİLİ KURUCU DANIŞMAN", font=_font_yukle(FONT_MONO_BOLD, 16), fill=RENK_KIRMIZI); by += 28
    draw.text((KENAR, by), b["isim"], font=_font_yukle(FONT_SANS_BOLD, 36), fill=RENK_KOYU); by += 46
    draw.text((KENAR, by), f"EDM Yapı & Gayrimenkul  ·  {b['unvan']}", font=_font_yukle(FONT_SANS_MEDIUM, 21), fill=RENK_GRI_METIN); by += 46

    draw.text((KENAR, by), "DOĞRUDAN DANIŞMA HATTI", font=_font_yukle(FONT_MONO_BOLD, 16), fill=RENK_KIRMIZI); by += 28
    draw.text((KENAR, by), b["tel"], font=_font_yukle(FONT_MONO_BOLD, 56), fill=RENK_KOYU); by += 80

    draw.text((KENAR, by), b["adres"], font=_font_yukle(FONT_SANS_MEDIUM, 21), fill=RENK_GRI_METIN); by += 32
    draw.text((KENAR, by), f"{b['site']}   ·   {b['eposta']}", font=_font_yukle(FONT_MONO, 18), fill=RENK_SILIK)

    qr = _qr_uret(b["qr_link"], 160)
    canvas.paste(qr, (GEN - KENAR - 160, by - 120))
    draw.text((GEN - KENAR - 160 + 16, by - 120 + 160 + 8), "KONUM VE YOL TARİFİ", font=_font_yukle(FONT_MONO_BOLD, 12), fill=RENK_SILIK)

    draw.text((KENAR, yer["alt"] - 14), "Bu içerik genel bilgilendirmedir; bağlayıcı hukuki işlemleriniz için avukatınıza danışın.", font=_font_yukle(FONT_SANS_MEDIUM, 16), fill=RENK_SILIK)

    yol = _cikti_belirle(cikti_yolu, "10_resmi_muhur")
    canvas.save(yol, "JPEG", quality=95)
    return yol


# =============================================================================
# 11. EDİTORYAL (KLASİK KUTUSUZ SAF TİPOGRAFİ)
# =============================================================================
def ciz_11_editoryal(veri: Dict[str, Any], sayfa: str = "04 / 04", cikti_yolu: Optional[Path] = None) -> Path:
    b = _bilgileri_derle(veri)
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    canvas = _filigran_uygula(canvas, acik_zemin=True)
    draw = ImageDraw.Draw(canvas)
    yer = _yerlesim()

    # 1. Üst Bar: Hafif şık rozet & Temiz Logo
    rozet_txt = b["rozet"]
    f_roz = _font_yukle(FONT_MONO_BOLD, 15)
    rw = draw.textbbox((0, 0), rozet_txt, font=f_roz)[2]
    draw.rounded_rectangle([(KENAR, yer["kronik_ust"]), (KENAR + rw + 28, yer["kronik_ust"] + 34)], radius=17, fill=(234, 236, 234))
    draw.text((KENAR + 14, yer["kronik_ust"] + 9), rozet_txt, font=f_roz, fill=RENK_KOYU)

    _logo_yerlestir(canvas, beyaz=False, y=yer["kronik_ust"] - 5, lw=285, golge=True)

    # 2. Üst Editoryal Başlık Bloğu (ÇİZGİNİN ÜSTÜNDE)
    y = yer["ust"] + 20
    f_b = _font_yukle(FONT_FRAUNCES, 56)
    max_w = GEN - (2 * KENAR)
    s1_satirlar = _metin_sar(b["s1"], f_b, max_w, draw)[:1]
    s2_satirlar = _metin_sar(b["s2"], f_b, max_w, draw)[:1]
    draw.text((KENAR, y), s1_satirlar[0] if s1_satirlar else "", font=f_b, fill=RENK_KOYU); y += 68
    draw.text((KENAR, y), s2_satirlar[0] if s2_satirlar else "", font=f_b, fill=RENK_KIRMIZI); y += 78

    f_a = _font_yukle(FONT_SANS_MEDIUM, 28)
    a_satirlar = _metin_sar(b["aciklama"], f_a, max_w, draw)[:2]
    for sat in a_satirlar:
        draw.text((KENAR, y), sat, font=f_a, fill=RENK_GRI_METIN)
        y += 40

    # 3. EKRANIN ORTASINDAKİ YATAY ÇİZGİ
    cizgi_y = max(y + 14, int(YUK * 0.38))
    draw.line([(KENAR, cizgi_y), (GEN - KENAR, cizgi_y)], fill=RENK_CIZGI, width=1)

    # 4. ASİMETRİK KAHRAMAN SOSYAL ETKİLEŞİM ALANI (ÖNERİ 4)
    y_cta = cizgi_y + 24
    toplam_w = GEN - (2 * KENAR)
    gap = 18
    hero_w = min(540, int(toplam_w * 0.58))
    right_w = toplam_w - hero_w - gap
    card_h = 104

    # Sol Kahraman Kart (Kaydet)
    draw.rounded_rectangle([(KENAR, y_cta), (KENAR + hero_w, y_cta + card_h)], radius=16, fill=(255, 255, 255), outline=RENK_CIZGI, width=1)
    # Sol kenar kırmızı şerit vurgusu
    draw.rounded_rectangle([(KENAR, y_cta), (KENAR + 6, y_cta + card_h)], radius=3, fill=RENK_KIRMIZI)

    ik_sz = 38
    try:
        ik = _vektor_ikon_uret("bookmark", ik_sz, RENK_KIRMIZI)
        canvas.paste(ik, (KENAR + 24, y_cta + (card_h - ik_sz) // 2), ik)
    except Exception as e:
        # Sessiz kalırsa slayt ikonsuz/logosuz çıkar ve kimse fark etmez
        log.warning("Kapanış slaytı: marka öğesi çizilemedi: %s", e)

    tx = KENAR + 24 + ik_sz + 16
    draw.text((tx, y_cta + 24), "BU REHBERİ KAYDEDİN", font=_font_yukle(FONT_SANS_BOLD, 23), fill=RENK_KOYU)
    draw.text((tx, y_cta + 56), "İleride hukuki risk yaşamamak için saklayın.", font=_font_yukle(FONT_SANS_MEDIUM, 16), fill=RENK_GRI_METIN)

    # Sağ İkili Sosyal Kapsüller (üst üste)
    rx = KENAR + hero_w + gap
    pill_h = 46
    pill_gap = 12
    right_actions = [
        ("comment", "Sorularınızı yorumda sorun", y_cta),
        ("follow", "Yeni rehberler için takip edin", y_cta + pill_h + pill_gap),
    ]
    f_rp = _font_yukle(FONT_SANS_BOLD, 17)
    ik_sz_r = 22

    for ic_name, text, py in right_actions:
        draw.rounded_rectangle([(rx, py), (rx + right_w, py + pill_h)], radius=12, fill=(255, 255, 255), outline=RENK_CIZGI, width=1)
        try:
            ik = _vektor_ikon_uret(ic_name, ik_sz_r, RENK_KIRMIZI)
            canvas.paste(ik, (rx + 16, py + (pill_h - ik_sz_r) // 2), ik)
        except Exception as e:
            # Sessiz kalırsa slayt ikonsuz/logosuz çıkar ve kimse fark etmez
            log.warning("Kapanış slaytı: marka öğesi çizilemedi: %s", e)
        draw.text((rx + 16 + ik_sz_r + 12, py + 12), text, font=f_rp, fill=RENK_KOYU)

    # 5. ALTA DAYALI (DOCKED TO BOTTOM) İLETİŞİM BLOĞU
    by = yer["alt"] - 350

    # 5A. METİN ÖZDOĞAN (42px Bold) & Kurucu Danışman
    draw.text((KENAR, by), b["isim"], font=_font_yukle(FONT_SANS_BOLD, 42), fill=RENK_KOYU); by += 50
    unvan = b["unvan"].replace("EDM Yapı & Gayrimenkul", "").replace("EDM Yapı", "").strip().rstrip("·").strip()
    if not unvan:
        unvan = "Kurucu Danışman"
    draw.text((KENAR, by), unvan, font=_font_yukle(FONT_SANS_MEDIUM, 24), fill=RENK_GRI_METIN); by += 48

    # Önce web & e-posta genişliğini hesapla
    ik_sz_c = 22
    web_gen = draw.textbbox((0, 0), b["site"], font=_font_yukle(FONT_MONO_BOLD, 19))[2]
    mail_x = KENAR + ik_sz_c + 10 + web_gen + 34
    mail_gen = draw.textbbox((0, 0), b["eposta"], font=_font_yukle(FONT_MONO, 18))[2]
    mail_end_x = mail_x + ik_sz_c + 10 + mail_gen

    # 5B. DEV TELEFON NUMARASI
    tel_y = by
    f_tel = _font_yukle(FONT_MONO_BOLD, 75)
    tel_parts = b["tel"].split() if len(b["tel"].split()) == 4 else ["0536", "343", "41", "97"]
    parts_w = sum(draw.textbbox((0, 0), p, font=f_tel)[2] for p in tel_parts)
    target_w = mail_end_x - KENAR
    gap = (target_w - parts_w) / (len(tel_parts) - 1) if len(tel_parts) > 1 else 45

    curr_x = KENAR
    for p in tel_parts:
        draw.text((curr_x, tel_y), p, font=f_tel, fill=RENK_KOYU)
        curr_x += draw.textbbox((0, 0), p, font=f_tel)[2] + gap
    by += 96

    # 5C. OFİS ADRESİ
    adres_satirlar = _metin_sar(b["adres"], _font_yukle(FONT_SANS_MEDIUM, 21), max_w - 230, draw)[:1]
    draw.text((KENAR, by), adres_satirlar[0] if adres_satirlar else "", font=_font_yukle(FONT_SANS_MEDIUM, 21), fill=RENK_GRI_METIN); by += 44

    # 5D. WEB SİTESİ & E-POSTA (KIRMIZI ŞIK VEKTÖR İKONLARLA)
    try:
        web_ik = _vektor_ikon_uret("web", ik_sz_c, RENK_KIRMIZI)
        canvas.paste(web_ik, (KENAR, by + 2), web_ik)
    except Exception as e:
        # Sessiz kalırsa slayt ikonsuz/logosuz çıkar ve kimse fark etmez
        log.warning("Kapanış slaytı: marka öğesi çizilemedi: %s", e)
    draw.text((KENAR + ik_sz_c + 10, by), b["site"], font=_font_yukle(FONT_MONO_BOLD, 19), fill=RENK_KOYU)

    try:
        mail_ik = _vektor_ikon_uret("mail", ik_sz_c, RENK_KIRMIZI)
        canvas.paste(mail_ik, (mail_x, by + 2), mail_ik)
    except Exception as e:
        # Sessiz kalırsa slayt ikonsuz/logosuz çıkar ve kimse fark etmez
        log.warning("Kapanış slaytı: marka öğesi çizilemedi: %s", e)
    draw.text((mail_x + ik_sz_c + 10, by), b["eposta"], font=_font_yukle(FONT_MONO, 18), fill=RENK_SILIK)

    # 6. SAĞ TARAF: BÜYÜTÜLMÜŞ KOYU BORDO QR KOD (200px, #7A0D0D, TAŞMAYAN SIKI BEYAZ ZEMİN)
    qr_sz = 200
    qr_x = GEN - KENAR - qr_sz
    qr_y = tel_y + 2
    q = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=5, border=1)
    q.add_data(b["qr_link"][:500] if b["qr_link"] else VARSAYILAN_QR)
    q.make(fit=True)
    qr_img = q.make_image(fill_color="#7A0D0D", back_color="#ffffff").convert("RGBA")
    qr_img = qr_img.resize((qr_sz, qr_sz), Image.Resampling.LANCZOS)

    # Merkez amblem (Taşmayan sıkı beyaz zemin ve ekstra kalın logo)
    logo_yolu = Path(__file__).resolve().parent.parent / "assets/logos/amblem-kalin.png"
    if not logo_yolu.exists():
        logo_yolu = Path(__file__).resolve().parent.parent / "assets/logos/amblem.png"

    if logo_yolu.exists():
        try:
            emblem = Image.open(logo_yolu).convert("RGBA")
            logo_sz = 60
            sq_sz = 66
            sq_mask = Image.new("RGBA", (sq_sz, sq_sz), (0, 0, 0, 0))
            d_sq = ImageDraw.Draw(sq_mask)
            d_sq.rounded_rectangle([(0, 0), (sq_sz - 1, sq_sz - 1)], radius=12, fill=(255, 255, 255, 255))
            pos_s = ((qr_sz - sq_sz) // 2, (qr_sz - sq_sz) // 2)
            qr_img.paste(sq_mask, pos_s, sq_mask)

            emblem = emblem.resize((logo_sz, logo_sz), Image.Resampling.LANCZOS)
            pos_l = ((qr_sz - logo_sz) // 2, (qr_sz - logo_sz) // 2)
            qr_img.paste(emblem, pos_l, emblem)
        except Exception as e:
            # Sessiz kalırsa slayt ikonsuz/logosuz çıkar ve kimse fark etmez
            log.warning("Kapanış slaytı: marka öğesi çizilemedi: %s", e)

    canvas.paste(qr_img.convert("RGB"), (qr_x, qr_y))

    f_lbl = _font_yukle(FONT_MONO_BOLD, 12)
    lbl_txt = "OFİS KONUMU // TARA"
    lbl_w = draw.textbbox((0, 0), lbl_txt, font=f_lbl)[2]
    draw.text((qr_x + (qr_sz - lbl_w) // 2, qr_y + qr_sz + 8), lbl_txt, font=f_lbl, fill=RENK_SILIK)

    # 7. Yasal Not & Alt Bar (Sol alttaki mükerrer EDM yazısı kaldırıldı)
    draw.text((KENAR, yer["alt"] - 14), "Bu içerik genel bilgilendirmedir; bağlayıcı hukuki görüş için avukatınıza danışın.", font=_font_yukle(FONT_SANS_MEDIUM, 16), fill=RENK_SILIK)
    draw.text((GEN - KENAR - 80, yer["alt_bar"] + 26), sayfa, font=_font_yukle(FONT_MONO_BOLD, 19), fill=RENK_KIRMIZI)

    yol = _cikti_belirle(cikti_yolu, "11_editoryal")
    canvas.save(yol, "JPEG", quality=95)
    return yol





# =============================================================================
# DİNAMİK SEÇİCİ & DAĞITICI FONKSİYON
# =============================================================================
STIL_HARITASI = {
    "kartvizit": ciz_01_luks_kartvizit,
    "01_luks_kartvizit": ciz_01_luks_kartvizit,
    "stationery": ciz_01_luks_kartvizit,

    "kitap_afis": ciz_02_merkezlenmis_kitap_afis,
    "02_merkezlenmis_kitap_afis": ciz_02_merkezlenmis_kitap_afis,
    "merkezlenmis": ciz_02_merkezlenmis_kitap_afis,

    "split_screen": ciz_03_split_screen,
    "03_split_screen": ciz_03_split_screen,
    "cift_zemin": ciz_03_split_screen,

    "mimari_pafta": ciz_04_mimari_pafta,
    "04_mimari_pafta": ciz_04_mimari_pafta,
    "blueprint": ciz_04_mimari_pafta,

    "kurucu_mektubu": ciz_05_kurucu_mektubu,
    "05_kurucu_mektubu": ciz_05_kurucu_mektubu,
    "imza": ciz_05_kurucu_mektubu,

    "paspartu_fotograf": ciz_06_paspartu_fotograf,
    "06_paspartu_fotograf": ciz_06_paspartu_fotograf,
    "katalog": ciz_06_paspartu_fotograf,

    "dikey_tipografi": ciz_07_dikey_tipografi,
    "07_dikey_tipografi": ciz_07_dikey_tipografi,
    "iskandinav": ciz_07_dikey_tipografi,

    "iletisim_terminali": ciz_08_iletisim_terminali,
    "08_iletisim_terminali": ciz_08_iletisim_terminali,
    "dashboard": ciz_08_iletisim_terminali,

    "dev_numara": ciz_09_dev_numara,
    "09_dev_numara": ciz_09_dev_numara,
    "monolit": ciz_09_dev_numara,

    "resmi_muhur": ciz_10_resmi_muhur,
    "10_resmi_muhur": ciz_10_resmi_muhur,
    "sertifika": ciz_10_resmi_muhur,

    "editoryal": ciz_11_editoryal,
    "11_editoryal": ciz_11_editoryal,
    "klasik": ciz_11_editoryal,
}


def kapanis_ciz(stil: Optional[str], veri: Dict[str, Any], sayfa: str = "04 / 04", cikti_yolu: Optional[Path] = None) -> Path:
    """İstenen stilde kapanış slaytını dinamik olarak çizer."""
    global GEN, YUK
    import src.make_image as mi
    GEN = mi.GENISLIK
    YUK = mi.YUKSEKLIK
    secilen_stil = (stil or "kartvizit").lower().strip()
    cizici = STIL_HARITASI.get(secilen_stil, ciz_01_luks_kartvizit)
    return cizici(veri, sayfa, cikti_yolu)
