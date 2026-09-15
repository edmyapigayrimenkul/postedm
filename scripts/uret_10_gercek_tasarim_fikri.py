#!/usr/bin/env python3
"""
scripts/uret_10_gercek_tasarim_fikri.py
10 Gerçek ve Radikal Farklı Kapanış Tasarım Konsepti:
1. Lüks Kartvizit (Floating Stationery)
2. Merkezlenmiş Editoryal Kitap/Afiş (Centered Monolith)
3. Split-Screen (Çift Renk Zemin Bölünmesi)
4. Teknik Mimari Pafta & Koordinat (Architectural Blueprint)
5. Kurucu Mektubu & Islak İmza (Founder's Letter)
6. Paspartu Fotoğraf Penceresi (Photo Frame & Catalogue)
7. Dikey 90° Tipografi & Asimetrik İskandinav (Vertical Typography)
8. Minimalist İletişim Terminali (Dashboard / Icon List)
9. Tipografik Monolit / Büyük Numara Posteri (Mega Number Poster)
10. Resmi Ekspertiz Mührü & Otorite Sertifikası (Official Seal & Stamp)
"""

from __future__ import annotations
import math
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import make_image as mi, config

ARTIFACT_DIR = Path("/Users/macbook/.gemini/antigravity/brain/10849f7b-49c8-44a9-a6a4-91a15b9d0075/kapanis_tasarimlari")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

GEN = mi.GENISLIK      # 1080
YUK = mi.YUKSEKLIK     # 1350
KENAR = 72

RENK_KAGIT = (246, 245, 241)
RENK_KAGIT_BEYAZ = (255, 255, 255)
RENK_KAGIT_KREM = (240, 238, 232)
RENK_KOYU = (18, 20, 24)
RENK_KIRMIZI = (217, 43, 43)
RENK_GRI_METIN = (88, 92, 98)
RENK_SILIK = (138, 142, 148)
RENK_CIZGI = (218, 222, 218)
RENK_MUREKKEP = (14, 16, 20)

QR_LINK = "https://maps.google.com/?q=Alibey+Mah+Albay+Yunus+Dirik+Cad+No+58A+Silivri"

def _qr(boyut: int, zemin: str = "#ffffff", muhur: str = "#121316") -> Image.Image:
    import qrcode
    q = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=4, border=1)
    q.add_data(QR_LINK)
    q.make(fit=True)
    g = q.make_image(fill_color=muhur, back_color=zemin).convert("RGB")
    return g.resize((boyut, boyut), Image.Resampling.LANCZOS)

def _kaydet(canvas: Image.Image, dosya_adi: str) -> Path:
    yol = ARTIFACT_DIR / f"{dosya_adi}.jpg"
    canvas.save(yol, "JPEG", quality=95)
    print(f"✓ {dosya_adi}.jpg kaydedildi")
    return yol

def _yasal_ciz(draw, kenar, yer, p=None, yasal_metin=None):
    metin = yasal_metin or "Bu içerik genel bilgilendirmedir; bağlayıcı hukuki görüş için avukatınıza danışın."
    renk = p.get("silik", RENK_SILIK) if isinstance(p, dict) else RENK_SILIK
    draw.text((kenar, yer["alt"] - 14), metin, font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 16), fill=renk)


# =============================================================================
# KONSEPT 1: LÜKS KARTVİZİT / EMBOSSED FLOATING STATIONERY
# =============================================================================
def konsept_01_luks_kartvizit():
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    canvas = mi._filigran_uygula(canvas, acik_zemin=True)
    draw = ImageDraw.Draw(canvas)
    yer = mi._yerlesim()

    # Üst Rozet & Logo
    mi._rozet_ciz(draw, KENAR, yer["kronik_ust"], "EDM DANIŞMANLIK", bg_color=(235, 238, 235), fg_color=RENK_KOYU, font_boyut=20)
    mi._logo_yerlestir(canvas, beyaz=False, y=yer["kronik_ust"] - 5, lw=228, golge=False)

    # Başlık & Açıklama
    y = yer["ust"] + 15
    f_b = mi._font_yukle(mi.FONT_FRAUNCES, 56)
    draw.text((KENAR, y), "Doğru adımlarla", font=f_b, fill=RENK_KOYU); y += 64
    draw.text((KENAR, y), "GÜVENLİ KİRALAMA", font=f_b, fill=RENK_KIRMIZI); y += 76

    f_a = mi._font_yukle(mi.FONT_SANS_MEDIUM, 28)
    draw.text((KENAR, y), "Silivri ve Trakya genelinde mülk yönetimi ve hukuki", font=f_a, fill=RENK_GRI_METIN); y += 38
    draw.text((KENAR, y), "süreçlerinizde profesyonel kadromuzla yanınızdayız.", font=f_a, fill=RENK_GRI_METIN); y += 54

    # Kaydetme Butonu (Mühür şeklinde)
    draw.rounded_rectangle([(KENAR, y), (KENAR + 460, y + 42)], radius=21, fill=(238, 240, 238), outline=RENK_CIZGI, width=1)
    try:
        b_ik = mi._vektor_ikon_uret("bookmark", 18, RENK_KIRMIZI)
        canvas.paste(b_ik, (KENAR + 16, y + 12), b_ik)
    except Exception:
        pass
    draw.text((KENAR + 42, y + 11), "BU REHBERİ KAYDEDİN · İHTİYAÇ ANINDA ARAYIN", font=mi._font_yukle(mi.FONT_MONO_BOLD, 13), fill=RENK_KOYU)

    # ALTA YÜZEN LÜKS FİZİKSEL KARTVİZİT (Stationery Card)
    kart_w = GEN - (2 * KENAR)
    kart_h = 440
    kart_x = KENAR
    kart_y = yer["alt"] - kart_h - 10

    # Kart Gölgesi
    golge_katmani = Image.new("RGBA", (GEN, YUK), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(golge_katmani)
    g_draw.rounded_rectangle([(kart_x + 8, kart_y + 16), (kart_x + kart_w + 8, kart_y + kart_h + 16)], radius=18, fill=(0, 0, 0, 38))
    golge_katmani = golge_katmani.filter(ImageFilter.GaussianBlur(14))
    canvas.paste(golge_katmani, (0, 0), golge_katmani)

    # Kart Gövdesi (Ultra lüks mat beyaz, çok ince kabartma kenar)
    draw.rounded_rectangle([(kart_x, kart_y), (kart_x + kart_w, kart_y + kart_h)], radius=18, fill=RENK_KAGIT_BEYAZ, outline=(226, 228, 226), width=1)
    # Kart Üst Kırmızı Vurgu Çizgisi
    draw.rounded_rectangle([(kart_x, kart_y), (kart_x + kart_w, kart_y + 6)], radius=3, fill=RENK_KIRMIZI)

    # Kart İçi Bilgiler
    ky = kart_y + 40
    kx = kart_x + 44
    draw.text((kx, ky), "METİN ÖZDOĞAN", font=mi._font_yukle(mi.FONT_SANS_BOLD, 34), fill=RENK_KOYU); ky += 42
    draw.text((kx, ky), "Kurucu Gayrimenkul & Yatırım Danışmanı", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 22), fill=RENK_GRI_METIN); ky += 48

    # İnce ayraç
    draw.line([(kx, ky), (kart_x + kart_w - 44, ky)], fill=(236, 238, 236), width=1); ky += 32

    draw.text((kx, ky), "DOĞRUDAN HAT", font=mi._font_yukle(mi.FONT_MONO_BOLD, 16), fill=RENK_KIRMIZI); ky += 28
    draw.text((kx, ky), "0536 343 41 97", font=mi._font_yukle(mi.FONT_MONO_BOLD, 50), fill=RENK_KOYU); ky += 68

    draw.text((kx, ky), "Alibey Mah. Albay Yunus Dirik Cad. No: 58/A · Silivri", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 20), fill=RENK_GRI_METIN); ky += 30
    draw.text((kx, ky), "edmyapigayrimenkul.com   ·   info@edmyapigayrimenkul.com", font=mi._font_yukle(mi.FONT_MONO, 17), fill=RENK_SILIK)

    # Kart Sağında Mühür QR Kod
    qr = _qr(164)
    qr_x = kart_x + kart_w - 44 - 164
    qr_y = kart_y + 115
    canvas.paste(qr, (qr_x, qr_y))
    draw.text((qr_x + 36, qr_y + 172), "OFİS KONUMU", font=mi._font_yukle(mi.FONT_MONO_BOLD, 13), fill=RENK_SILIK)

    # Alt Bar
    draw.text((KENAR, yer["alt_bar"] + 26), "EDM YAPI & GAYRİMENKUL", font=mi._font_yukle(mi.FONT_MONO, 19), fill=RENK_SILIK)
    draw.text((GEN - KENAR - 80, yer["alt_bar"] + 26), "04 / 04", font=mi._font_yukle(mi.FONT_MONO_BOLD, 19), fill=RENK_KIRMIZI)

    return _kaydet(canvas, "01_luks_kartvizit_stationery")


# =============================================================================
# KONSEPT 2: MERKEZLENMİŞ EDİTORYAL KİTAP / AFİŞ (CENTERED MONOLITH)
# =============================================================================
def konsept_02_merkezlenmis_kitap_afis():
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    canvas = mi._filigran_uygula(canvas, acik_zemin=True)
    draw = ImageDraw.Draw(canvas)
    yer = mi._yerlesim()

    # Üst Orta Rozet
    rozet_txt = "EDM DANIŞMANLIK REHBERİ"
    f_roz = mi._font_yukle(mi.FONT_MONO_BOLD, 16)
    rw = draw.textbbox((0, 0), rozet_txt, font=f_roz)[2]
    draw.rounded_rectangle([(GEN//2 - rw//2 - 20, yer["kronik_ust"]), (GEN//2 + rw//2 + 20, yer["kronik_ust"] + 36)], radius=18, fill=(236, 238, 236))
    draw.text((GEN//2 - rw//2, yer["kronik_ust"] + 9), rozet_txt, font=f_roz, fill=RENK_KOYU)

    # Merkez Başlık (Kitap Kapağı Zarafeti)
    y = yer["ust"] + 40
    f_b = mi._font_yukle(mi.FONT_FRAUNCES, 62)
    s1 = "Doğru adımlarla"
    s2 = "GÜVENLİ KİRALAMA"
    w1 = draw.textbbox((0, 0), s1, font=f_b)[2]
    w2 = draw.textbbox((0, 0), s2, font=f_b)[2]
    draw.text((GEN//2 - w1//2, y), s1, font=f_b, fill=RENK_KOYU); y += 72
    draw.text((GEN//2 - w2//2, y), s2, font=f_b, fill=RENK_KIRMIZI); y += 82

    f_a = mi._font_yukle(mi.FONT_SANS_MEDIUM, 26)
    a1 = "Silivri ve Trakya genelinde mülk yönetimi ve tüm hukuki"
    a2 = "süreçlerinizde profesyonel ekibimizle yanınızdayız."
    wa1 = draw.textbbox((0, 0), a1, font=f_a)[2]
    wa2 = draw.textbbox((0, 0), a2, font=f_a)[2]
    draw.text((GEN//2 - wa1//2, y), a1, font=f_a, fill=RENK_GRI_METIN); y += 36
    draw.text((GEN//2 - wa2//2, y), a2, font=f_a, fill=RENK_GRI_METIN); y += 60

    # Ortada Büyük Kare QR Kod (Bir Mühür Gibi)
    qr_sz = 184
    qr = _qr(qr_sz)
    qr_x = GEN//2 - qr_sz//2
    qr_y = y
    canvas.paste(qr, (qr_x, qr_y))
    y += qr_sz + 18

    f_qr_lbl = mi._font_yukle(mi.FONT_MONO_BOLD, 13)
    lbl = "OFİS KONUMU // QR KODU OKUTUN"
    lw = draw.textbbox((0, 0), lbl, font=f_qr_lbl)[2]
    draw.text((GEN//2 - lw//2, y), lbl, font=f_qr_lbl, fill=RENK_SILIK); y += 46

    # Merkez Telefon & Danışman
    f_tel = mi._font_yukle(mi.FONT_MONO_BOLD, 54)
    tel = "0536 343 41 97"
    tw = draw.textbbox((0, 0), tel, font=f_tel)[2]
    draw.text((GEN//2 - tw//2, y), tel, font=f_tel, fill=RENK_KOYU); y += 68

    f_isim = mi._font_yukle(mi.FONT_SANS_BOLD, 26)
    isim_txt = "METİN ÖZDOĞAN  ·  Kurucu Danışman"
    iw = draw.textbbox((0, 0), isim_txt, font=f_isim)[2]
    draw.text((GEN//2 - iw//2, y), isim_txt, font=f_isim, fill=RENK_KOYU); y += 38

    f_ad = mi._font_yukle(mi.FONT_SANS_MEDIUM, 20)
    ad_txt = "Alibey Mah. Albay Yunus Dirik Cad. No: 58/A · Silivri"
    aw = draw.textbbox((0, 0), ad_txt, font=f_ad)[2]
    draw.text((GEN//2 - aw//2, y), ad_txt, font=f_ad, fill=RENK_GRI_METIN); y += 32

    f_web = mi._font_yukle(mi.FONT_MONO, 18)
    web_txt = "edmyapigayrimenkul.com   ·   info@edmyapigayrimenkul.com"
    ww = draw.textbbox((0, 0), web_txt, font=f_web)[2]
    draw.text((GEN//2 - ww//2, y), web_txt, font=f_web, fill=RENK_SILIK); y += 52

    # En Altta Merkezlenmiş Kaydetme İmzası
    k_txt = "🔖 BU REHBERİ KAYDEDİN · İHTİYAÇ ANINDA ELİNİZİN ALTINDA OLSUN"
    f_k = mi._font_yukle(mi.FONT_MONO_BOLD, 15)
    kw = draw.textbbox((0, 0), k_txt, font=f_k)[2]
    draw.text((GEN//2 - kw//2, yer["alt"] - 10), k_txt, font=f_k, fill=RENK_KIRMIZI)

    return _kaydet(canvas, "02_merkezlenmis_kitap_afis")


# =============================================================================
# KONSEPT 3: SPLIT-SCREEN (ÇİFT RENK / GECE-GÜNDÜZ ZEMİN BÖLÜNMESİ)
# =============================================================================
def konsept_03_split_screen():
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    draw = ImageDraw.Draw(canvas)
    yer = mi._yerlesim()

    split_y = int(YUK * 0.44)

    # Alt Yarım: Derin Mürekkep Gece Zemin (#121418)
    draw.rectangle([(0, split_y), (GEN, YUK)], fill=RENK_MUREKKEP)
    # Bölünme Kılcal Çizgisi (Kırmızı aksan)
    draw.rectangle([(0, split_y), (GEN, split_y + 4)], fill=RENK_KIRMIZI)

    # --- ÜST YARIM (Açık Kağıt) ---
    mi._rozet_ciz(draw, KENAR, yer["kronik_ust"], "EDM DANIŞMANLIK", bg_color=(235, 238, 235), fg_color=RENK_KOYU, font_boyut=20)
    mi._logo_yerlestir(canvas, beyaz=False, y=yer["kronik_ust"] - 5, lw=228, golge=False)

    y = yer["ust"] + 10
    f_b = mi._font_yukle(mi.FONT_FRAUNCES, 56)
    draw.text((KENAR, y), "Doğru adımlarla", font=f_b, fill=RENK_KOYU); y += 64
    draw.text((KENAR, y), "GÜVENLİ KİRALAMA", font=f_b, fill=RENK_KIRMIZI); y += 72

    f_a = mi._font_yukle(mi.FONT_SANS_MEDIUM, 27)
    draw.text((KENAR, y), "Silivri ve Trakya genelinde mülk yönetimi ve hukuki", font=f_a, fill=RENK_GRI_METIN); y += 38
    draw.text((KENAR, y), "süreçlerinizde profesyonel kadromuzla yanınızdayız.", font=f_a, fill=RENK_GRI_METIN); y += 50

    try:
        b_ik = mi._vektor_ikon_uret("bookmark", 20, RENK_KIRMIZI)
        canvas.paste(b_ik, (KENAR, y - 2), b_ik)
    except Exception:
        pass
    draw.text((KENAR + 28, y), "BU REHBERİ KAYDEDİN · İHTİYAÇ ANINDA ELİNİZİN ALTINDA OLSUN", font=mi._font_yukle(mi.FONT_MONO_BOLD, 15), fill=RENK_KOYU)

    # --- ALT YARIM (Koyu Prestij Alanı) ---
    by = split_y + 54
    draw.text((KENAR, by), "DOĞRUDAN DANIŞMANLIK HATTI", font=mi._font_yukle(mi.FONT_MONO_BOLD, 17), fill=RENK_KIRMIZI); by += 34
    draw.text((KENAR, by), "0536 343 41 97", font=mi._font_yukle(mi.FONT_MONO_BOLD, 64), fill=(255, 255, 255)); by += 96
    draw.text((KENAR, by), "METİN ÖZDOĞAN   ·   Kurucu Danışman", font=mi._font_yukle(mi.FONT_SANS_BOLD, 26), fill=(245, 245, 245)); by += 44
    draw.text((KENAR, by), "Alibey Mah. Albay Yunus Dirik Cad. No: 58/A · Silivri / İstanbul", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 21), fill=(185, 190, 195)); by += 38
    draw.text((KENAR, by), "edmyapigayrimenkul.com   ·   info@edmyapigayrimenkul.com", font=mi._font_yukle(mi.FONT_MONO, 19), fill=(140, 145, 155)); by += 32
    draw.text((KENAR, by), "@edmyapigayrimenkul", font=mi._font_yukle(mi.FONT_MONO, 18), fill=(140, 145, 155))

    # Koyu Zemin Üzerinde Beyaz QR Kod Kartı
    qr = _qr(168, zemin="#ffffff", muhur="#121418")
    qr_x = GEN - KENAR - 168
    qr_y = split_y + 60
    # Beyaz kenar çerçevesi
    draw.rounded_rectangle([(qr_x - 10, qr_y - 10), (qr_x + 168 + 10, qr_y + 168 + 48)], radius=12, fill=(24, 28, 34), outline=(48, 54, 64), width=1)
    canvas.paste(qr, (qr_x, qr_y))
    draw.text((qr_x + 36, qr_y + 168 + 14), "OFİS KONUMU", font=mi._font_yukle(mi.FONT_MONO_BOLD, 13), fill=RENK_KIRMIZI)

    # Alt Bar
    draw.line([(KENAR, yer["alt_bar"]), (GEN - KENAR, yer["alt_bar"])], fill=(40, 44, 52), width=1)
    draw.text((KENAR, yer["alt_bar"] + 26), "EDM YAPI & GAYRİMENKUL // DANIŞMANLIK", font=mi._font_yukle(mi.FONT_MONO, 18), fill=(120, 125, 135))
    draw.text((GEN - KENAR - 80, yer["alt_bar"] + 26), "04 / 04", font=mi._font_yukle(mi.FONT_MONO_BOLD, 19), fill=RENK_KIRMIZI)

    return _kaydet(canvas, "03_split_screen_cift_zemin")


# =============================================================================
# KONSEPT 4: TEKNİK MİMARİ PAFTA & KOORDİNAT (BLUEPRINT & COORDINATES)
# =============================================================================
def konsept_04_mimari_pafta_grid():
    canvas = Image.new("RGB", (GEN, YUK), (245, 246, 242))
    draw = ImageDraw.Draw(canvas)
    yer = mi._yerlesim()

    # Hafif Teknik Pafta Izgarası (Grid Çizgileri)
    grid_gap = 90
    grid_renk = (232, 235, 230)
    for x in range(0, GEN, grid_gap):
        draw.line([(x, 0), (x, YUK)], fill=grid_renk, width=1)
    for y in range(0, YUK, grid_gap):
        draw.line([(0, y), (GEN, y)], fill=grid_renk, width=1)

    # Teknik Köşe Artı İşaretleri (+)
    for px, py in [(KENAR, 120), (GEN - KENAR, 120), (KENAR, YUK - 120), (GEN - KENAR, YUK - 120), (GEN//2, yer["ust"])]:
        mi._arti_isareti_ciz(draw, px, py, renk=RENK_KIRMIZI, boyut=16)

    # Üst Bilgi: Koordinat ve Pafta No
    draw.text((KENAR, 62), "KOORDİNAT: 41°04'26.8\"N  28°14'48.2\"E  //  PAFTA NO: #EDM-2026-SLV", font=mi._font_yukle(mi.FONT_MONO_BOLD, 14), fill=RENK_SILIK)
    mi._logo_yerlestir(canvas, beyaz=False, y=52, lw=210, golge=False)

    # Başlık & Açıklama
    y = yer["ust"] + 20
    f_b = mi._font_yukle(mi.FONT_FRAUNCES, 54)
    draw.text((KENAR, y), "Doğru adımlarla", font=f_b, fill=RENK_KOYU); y += 62
    draw.text((KENAR, y), "GÜVENLİ KİRALAMA", font=f_b, fill=RENK_KIRMIZI); y += 74

    f_a = mi._font_yukle(mi.FONT_SANS_MEDIUM, 27)
    draw.text((KENAR, y), "Silivri ve Trakya genelinde tapu, imar, ekspertiz ve hukuki", font=f_a, fill=RENK_GRI_METIN); y += 38
    draw.text((KENAR, y), "süreçlerinizde bizzat yerinde saha incelemesiyle yanınızdayız.", font=f_a, fill=RENK_GRI_METIN); y += 50

    draw.text((KENAR, y), "🔖 BU REHBERİ KAYDEDİN // İHTİYAÇ ANINDA SAHA DANIŞMANINIZI ARAYIN", font=mi._font_yukle(mi.FONT_MONO_BOLD, 14), fill=RENK_KOYU); y += 50

    # TEKNİK LEJANT PANELİ (Mimari Plan Anteti)
    antet_y = yer["alt"] - 360
    draw.rectangle([(KENAR, antet_y), (GEN - KENAR, yer["alt"] - 20)], fill=(255, 255, 255), outline=RENK_KOYU, width=2)
    # Başlık Şeridi
    draw.rectangle([(KENAR, antet_y), (GEN - KENAR, antet_y + 36)], fill=RENK_KOYU)
    draw.text((KENAR + 18, antet_y + 9), "DANIŞMANLIK & RESMİ İLETİŞİM ANTETİ // SİLİVRİ MERKEZ OFİS", font=mi._font_yukle(mi.FONT_MONO_BOLD, 14), fill=(255, 255, 255))

    ay = antet_y + 54
    ax = KENAR + 28
    draw.text((ax, ay), "DANIŞMAN / FOUNDER", font=mi._font_yukle(mi.FONT_MONO_BOLD, 14), fill=RENK_KIRMIZI); ay += 24
    draw.text((ax, ay), "METİN ÖZDOĞAN", font=mi._font_yukle(mi.FONT_SANS_BOLD, 28), fill=RENK_KOYU); ay += 40

    draw.text((ax, ay), "DOĞRUDAN TELEFON / WHATSAPP", font=mi._font_yukle(mi.FONT_MONO_BOLD, 14), fill=RENK_KIRMIZI); ay += 24
    draw.text((ax, ay), "0536 343 41 97", font=mi._font_yukle(mi.FONT_MONO_BOLD, 46), fill=RENK_KOYU); ay += 58

    draw.text((ax, ay), "Alibey Mah. Albay Yunus Dirik Cad. No: 58/A · Silivri", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 19), fill=RENK_GRI_METIN); ay += 28
    draw.text((ax, ay), "edmyapigayrimenkul.com   ·   info@edmyapigayrimenkul.com", font=mi._font_yukle(mi.FONT_MONO, 17), fill=RENK_SILIK)

    # Sağ Taraf: Lejant Haritası ve QR
    qr = _qr(170)
    qr_x = GEN - KENAR - 170 - 24
    qr_y = antet_y + 54
    canvas.paste(qr, (qr_x, qr_y))
    draw.text((qr_x + 10, qr_y + 178), "PARSELE / KONUMA GİT", font=mi._font_yukle(mi.FONT_MONO_BOLD, 13), fill=RENK_KOYU)

    # Dikey Ayraç
    draw.line([(qr_x - 24, antet_y + 36), (qr_x - 24, yer["alt"] - 20)], fill=RENK_CIZGI, width=1)

    return _kaydet(canvas, "04_mimari_pafta_grid")


# =============================================================================
# KONSEPT 5: KURUCU MEKTUBU & ISLAK İMZA (FOUNDER'S LETTER)
# =============================================================================
def konsept_05_kurucu_mektubu():
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    canvas = mi._filigran_uygula(canvas, acik_zemin=True)
    draw = ImageDraw.Draw(canvas)
    yer = mi._yerlesim()

    mi._rozet_ciz(draw, KENAR, yer["kronik_ust"], "KURUCU NOTU // BİREBİR GÜVENCE", bg_color=(235, 238, 235), fg_color=RENK_KOYU, font_boyut=18)
    mi._logo_yerlestir(canvas, beyaz=False, y=yer["kronik_ust"] - 5, lw=228, golge=False)

    y = yer["ust"] + 20
    f_b = mi._font_yukle(mi.FONT_FRAUNCES, 50)
    draw.text((KENAR, y), "“Gayrimenkulde doğru karar,", font=f_b, fill=RENK_KOYU); y += 60
    draw.text((KENAR, y), "sahada doğru rehberle başlar.”", font=f_b, fill=RENK_KIRMIZI); y += 80

    f_mektup = mi._font_yukle(mi.FONT_SANS_MEDIUM, 26)
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

    # Islak İmza Görseli / Tipografik İmza Çizgisi
    imza_y = y
    draw.line([(KENAR, imza_y + 50), (KENAR + 340, imza_y + 50)], fill=RENK_CIZGI, width=1)
    draw.text((KENAR + 10, imza_y), "Metin Özdoğan", font=mi._font_yukle(mi.FONT_FRAUNCES, 44), fill=RENK_KIRMIZI)
    draw.text((KENAR + 10, imza_y + 60), "METİN ÖZDOĞAN  ·  Kurucu Danışman", font=mi._font_yukle(mi.FONT_SANS_BOLD, 22), fill=RENK_KOYU)
    draw.text((KENAR + 10, imza_y + 90), "EDM Yapı & Gayrimenkul", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 19), fill=RENK_GRI_METIN)

    # İletişim & QR Sağ Tarafta Dengeleniyor
    sag_x = GEN - KENAR - 280
    qr = _qr(144)
    canvas.paste(qr, (sag_x + 136, imza_y - 20))
    draw.text((sag_x + 154, imza_y + 132), "OFİS KONUMU", font=mi._font_yukle(mi.FONT_MONO_BOLD, 12), fill=RENK_SILIK)

    # İletişim Alt Bloğu
    by = yer["alt"] - 130
    draw.line([(KENAR, by - 24), (GEN - KENAR, by - 24)], fill=RENK_CIZGI, width=1)
    draw.text((KENAR, by), "DOĞRUDAN TELEFON:", font=mi._font_yukle(mi.FONT_MONO_BOLD, 16), fill=RENK_KIRMIZI)
    draw.text((KENAR + 210, by - 4), "0536 343 41 97", font=mi._font_yukle(mi.FONT_MONO_BOLD, 38), fill=RENK_KOYU)
    draw.text((GEN - KENAR - 320, by + 4), "edmyapigayrimenkul.com", font=mi._font_yukle(mi.FONT_MONO_BOLD, 19), fill=RENK_KOYU)
    by += 44
    draw.text((KENAR, by), "Alibey Mah. Albay Yunus Dirik Cad. No: 58/A · Silivri / İstanbul", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 20), fill=RENK_GRI_METIN)
    draw.text((GEN - KENAR - 320, by), "info@edmyapigayrimenkul.com", font=mi._font_yukle(mi.FONT_MONO, 18), fill=RENK_SILIK)

    _yasal_ciz(draw, KENAR, yer, {"silik": RENK_SILIK}, "🔖 BU REHBERİ KAYDEDİN · HUKUKİ VE SEKTÖREL BİLGİLENDİRME AMACIYLA HAZIRLANMIŞTIR")

    return _kaydet(canvas, "05_kurucu_mektubu_imza")


# =============================================================================
# KONSEPT 6: PASPARTU FOTOĞRAF PENCERESİ (PHOTO PASSEPARTOUT)
# =============================================================================
def konsept_06_paspartu_fotograf():
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    draw = ImageDraw.Draw(canvas)
    yer = mi._yerlesim()

    mi._rozet_ciz(draw, KENAR, yer["kronik_ust"], "EDM DANIŞMANLIK", bg_color=(235, 238, 235), fg_color=RENK_KOYU, font_boyut=20)
    mi._logo_yerlestir(canvas, beyaz=False, y=yer["kronik_ust"] - 5, lw=228, golge=False)

    y = yer["ust"] + 10
    f_b = mi._font_yukle(mi.FONT_FRAUNCES, 50)
    draw.text((KENAR, y), "Doğru adımlarla", font=f_b, fill=RENK_KOYU); y += 58
    draw.text((KENAR, y), "GÜVENLİ KİRALAMA", font=f_b, fill=RENK_KIRMIZI); y += 68

    # Paspartu Fotoğraf Penceresi (Mimari Arşiv / Trakya Atmosferi)
    foto_w = GEN - (2 * KENAR)
    foto_h = 320
    foto_y = y
    try:
        foto_kaynak = mi._temiz_arkaplan_al("DANISMANLIK")
        foto = foto_kaynak.resize((foto_w, foto_h), Image.Resampling.LANCZOS).convert("RGBA")
        # Hafif monokrom / sepya ton filtre
        filtre = Image.new("RGBA", (foto_w, foto_h), (18, 22, 28, 120))
        foto = Image.alpha_composite(foto, filtre)
        canvas.paste(foto, (KENAR, foto_y))
    except Exception:
        draw.rectangle([(KENAR, foto_y), (KENAR + foto_w, foto_y + foto_h)], fill=(230, 232, 230))

    # Fotoğraf Paspartu Çerçevesi
    draw.rectangle([(KENAR, foto_y), (KENAR + foto_w, foto_y + foto_h)], outline=RENK_CIZGI, width=1)
    # Fotoğraf içi zarif etiket
    draw.rectangle([(KENAR + 24, foto_y + foto_h - 48), (KENAR + 380, foto_y + foto_h - 18)], fill=(12, 14, 18))
    draw.text((KENAR + 36, foto_y + foto_h - 42), "SİLİVRİ & TRAKYA SAHA OPERASYONU", font=mi._font_yukle(mi.FONT_MONO_BOLD, 13), fill=(255, 255, 255))

    y = foto_y + foto_h + 26
    draw.text((KENAR, y), "🔖 BU REHBERİ KAYDEDİN // İHTİYAÇ ANINDA ELİNİZİN ALTINDA OLSUN", font=mi._font_yukle(mi.FONT_MONO_BOLD, 15), fill=RENK_KOYU); y += 46

    # İletişim Katoloğu Bloğu
    by = y
    draw.text((KENAR, by), "DOĞRUDAN HAT", font=mi._font_yukle(mi.FONT_MONO_BOLD, 16), fill=RENK_KIRMIZI); by += 30
    draw.text((KENAR, by), "0536 343 41 97", font=mi._font_yukle(mi.FONT_MONO_BOLD, 52), fill=RENK_KOYU); by += 76
    draw.text((KENAR, by), "METİN ÖZDOĞAN  ·  Kurucu Danışman", font=mi._font_yukle(mi.FONT_SANS_SEMIBOLD, 24), fill=RENK_KOYU); by += 38
    draw.text((KENAR, by), "Alibey Mah. Albay Yunus Dirik Cad. No: 58/A · Silivri", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 21), fill=RENK_GRI_METIN); by += 32
    draw.text((KENAR, by), "edmyapigayrimenkul.com   ·   info@edmyapigayrimenkul.com", font=mi._font_yukle(mi.FONT_MONO, 18), fill=RENK_SILIK)

    qr = _qr(148)
    canvas.paste(qr, (GEN - KENAR - 148, y + 10))
    draw.text((GEN - KENAR - 148 + 26, y + 10 + 148 + 8), "OFİS KONUMU", font=mi._font_yukle(mi.FONT_MONO_BOLD, 12), fill=RENK_SILIK)

    _yasal_ciz(draw, KENAR, yer, {"silik": RENK_SILIK})
    return _kaydet(canvas, "06_paspartu_fotograf_katalog")


# =============================================================================
# KONSEPT 7: DİKEY 90° TİPOGRAFİ & ASİMETRİK İSKANDİNAV (VERTICAL TYPOGRAPHY)
# =============================================================================
def konsept_07_dikey_tipografi():
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    canvas = mi._filigran_uygula(canvas, acik_zemin=True)
    draw = ImageDraw.Draw(canvas)
    yer = mi._yerlesim()

    # Sol Dikey Başlık Şeridi (90 Derece Döndürülmüş Tipografi)
    dikey_metin = "EDM YAPI & GAYRİMENKUL  ·  SİLİVRİ SAHA DANIŞMANLIĞI  ·  0536 343 41 97"
    f_dik = mi._font_yukle(mi.FONT_MONO_BOLD, 17)
    txt_img = Image.new("RGBA", (900, 40), (0, 0, 0, 0))
    t_draw = ImageDraw.Draw(txt_img)
    t_draw.text((0, 8), dikey_metin, font=f_dik, fill=RENK_KIRMIZI)
    txt_rot = txt_img.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)
    canvas.paste(txt_rot, (KENAR - 24, yer["ust"] + 20), txt_rot)

    # Dikey Ayırıcı Kılcal Çizgi
    ayrac_x = KENAR + 42
    draw.line([(ayrac_x, yer["ust"]), (ayrac_x, yer["alt"] - 10)], fill=RENK_CIZGI, width=1)

    # Sağ Ana Gövde Alanı
    sag_x = ayrac_x + 40
    sag_w = GEN - KENAR - sag_x

    # Üst Logo & Rozet
    mi._logo_yerlestir(canvas, beyaz=False, y=yer["kronik_ust"] - 5, lw=220, golge=False)

    y = yer["ust"] + 30
    f_b = mi._font_yukle(mi.FONT_FRAUNCES, 56)
    draw.text((sag_x, y), "Doğru adımlarla", font=f_b, fill=RENK_KOYU); y += 66
    draw.text((sag_x, y), "GÜVENLİ KİRALAMA", font=f_b, fill=RENK_KIRMIZI); y += 78

    f_a = mi._font_yukle(mi.FONT_SANS_MEDIUM, 28)
    draw.text((sag_x, y), "Silivri ve Trakya genelinde mülk", font=f_a, fill=RENK_GRI_METIN); y += 38
    draw.text((sag_x, y), "yönetimi ve hukuki süreçlerinizde", font=f_a, fill=RENK_GRI_METIN); y += 38
    draw.text((sag_x, y), "kesintisiz danışmanlıkla yanınızdayız.", font=f_a, fill=RENK_GRI_METIN); y += 58

    draw.text((sag_x, y), "🔖 BU REHBERİ KAYDEDİN // ELİNİZİN ALTINDA OLSUN", font=mi._font_yukle(mi.FONT_MONO_BOLD, 15), fill=RENK_KOYU); y += 48

    # Kırmızı Yatay Çizgi
    draw.rectangle([(sag_x, y), (sag_x + 140, y + 3)], fill=RENK_KIRMIZI); y += 42

    # İletişim
    draw.text((sag_x, y), "DOĞRUDAN HAT", font=mi._font_yukle(mi.FONT_MONO_BOLD, 16), fill=RENK_SILIK); y += 28
    draw.text((sag_x, y), "0536 343 41 97", font=mi._font_yukle(mi.FONT_MONO_BOLD, 54), fill=RENK_KOYU); y += 78
    draw.text((sag_x, y), "METİN ÖZDOĞAN  ·  Kurucu Danışman", font=mi._font_yukle(mi.FONT_SANS_BOLD, 24), fill=RENK_KOYU); y += 38
    draw.text((sag_x, y), "Alibey Mah. Albay Yunus Dirik Cad. No: 58/A · Silivri", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 20), fill=RENK_GRI_METIN); y += 34
    draw.text((sag_x, y), "edmyapigayrimenkul.com   ·   info@edmyapigayrimenkul.com", font=mi._font_yukle(mi.FONT_MONO, 18), fill=RENK_SILIK)

    qr = _qr(156)
    canvas.paste(qr, (GEN - KENAR - 156, y - 90))
    draw.text((GEN - KENAR - 156 + 30, y - 90 + 156 + 8), "OFİS KONUMU", font=mi._font_yukle(mi.FONT_MONO_BOLD, 12), fill=RENK_SILIK)

    _yasal_ciz(draw, sag_x, yer, {"silik": RENK_SILIK})
    return _kaydet(canvas, "07_dikey_tipografi_iskandinav")


# =============================================================================
# KONSEPT 8: MİNİMALİST İLETİŞİM TERMİNALİ / DASHBOARD (ICONIC LIST)
# =============================================================================
def konsept_08_iletisim_terminali():
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    canvas = mi._filigran_uygula(canvas, acik_zemin=True)
    draw = ImageDraw.Draw(canvas)
    yer = mi._yerlesim()

    mi._rozet_ciz(draw, KENAR, yer["kronik_ust"], "HIZLI İLETİŞİM DİREKTÖRÜ", bg_color=(235, 238, 235), fg_color=RENK_KOYU, font_boyut=20)
    mi._logo_yerlestir(canvas, beyaz=False, y=yer["kronik_ust"] - 5, lw=228, golge=False)

    y = yer["ust"] + 15
    f_b = mi._font_yukle(mi.FONT_FRAUNCES, 54)
    draw.text((KENAR, y), "Doğru adımlarla", font=f_b, fill=RENK_KOYU); y += 62
    draw.text((KENAR, y), "GÜVENLİ KİRALAMA", font=f_b, fill=RENK_KIRMIZI); y += 74

    f_a = mi._font_yukle(mi.FONT_SANS_MEDIUM, 27)
    draw.text((KENAR, y), "Silivri ve Trakya genelinde tüm gayrimenkul ve yatırım", font=f_a, fill=RENK_GRI_METIN); y += 38
    draw.text((KENAR, y), "süreçlerinizde aşağıdaki kanallardan doğrudan bize ulaşın.", font=f_a, fill=RENK_GRI_METIN); y += 54

    # 4 Satırlı Minimalist Terminal Satırları
    terminal_y = y
    kanallar = [
        ("phone", "DOĞRUDAN HAT", "0536 343 41 97", "Haftanın 7 günü arayabilir / WhatsApp yazabilirsiniz."),
        ("pin", "OFİS ADRESİ", "Albay Yunus Dirik Cad. No: 58/A", "Alibey Mah. Silivri / İstanbul (Merkez Ofis)"),
        ("web", "WEB SİTESİ", "edmyapigayrimenkul.com", "Tüm ilanlar ve kurumsal danışmanlık rehberleri"),
        ("mail", "E-POSTA", "info@edmyapigayrimenkul.com", "Resmi yazışma ve dosya inceleme talepleri"),
    ]

    for ik_ad, baslik, deger, aciklama in kanallar:
        draw.line([(KENAR, terminal_y), (GEN - KENAR, terminal_y)], fill=(228, 232, 228), width=1)
        # İkon
        try:
            ik = mi._vektor_ikon_uret(ik_ad, 28, RENK_KIRMIZI)
            canvas.paste(ik, (KENAR + 10, terminal_y + 16), ik)
        except Exception:
            pass
        # Başlık ve Değer
        draw.text((KENAR + 62, terminal_y + 12), baslik, font=mi._font_yukle(mi.FONT_MONO_BOLD, 14), fill=RENK_KIRMIZI)
        draw.text((KENAR + 62, terminal_y + 32), deger, font=mi._font_yukle(mi.FONT_MONO_BOLD if ik_ad == "phone" else mi.FONT_SANS_BOLD, 26 if ik_ad == "phone" else 22), fill=RENK_KOYU)
        draw.text((KENAR + 62, terminal_y + 64), aciklama, font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 17), fill=RENK_SILIK)
        terminal_y += 94

    draw.line([(KENAR, terminal_y), (GEN - KENAR, terminal_y)], fill=(228, 232, 228), width=1)

    # Sağ Altta QR Kod
    qr = _qr(150)
    canvas.paste(qr, (GEN - KENAR - 150, terminal_y + 18))
    draw.text((GEN - KENAR - 150 + 26, terminal_y + 18 + 150 + 6), "KONUMU TARA", font=mi._font_yukle(mi.FONT_MONO_BOLD, 12), fill=RENK_SILIK)

    # Danışman İmzası ve Kaydetme
    draw.text((KENAR, terminal_y + 24), "METİN ÖZDOĞAN  ·  Kurucu Danışman", font=mi._font_yukle(mi.FONT_SANS_BOLD, 24), fill=RENK_KOYU)
    draw.text((KENAR, terminal_y + 58), "Silivri ve Trakya Gayrimenkul Yatırım Direktörlüğü", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 19), fill=RENK_GRI_METIN)
    draw.text((KENAR, terminal_y + 96), "🔖 BU REHBERİ KAYDEDİN · İHTİYAÇ DUYDUĞUNUZDA ELİNİZİN ALTINDA OLSUN", font=mi._font_yukle(mi.FONT_MONO_BOLD, 14), fill=RENK_KIRMIZI)

    return _kaydet(canvas, "08_iletisim_terminali_dashboard")


# =============================================================================
# KONSEPT 9: TİPOGRAFİK MONOLİT / DEV NUMARA POSTERİ (MEGA NUMBER POSTER)
# =============================================================================
def konsept_09_dev_numara_posteri():
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    canvas = mi._filigran_uygula(canvas, acik_zemin=True)
    draw = ImageDraw.Draw(canvas)
    yer = mi._yerlesim()

    mi._rozet_ciz(draw, KENAR, yer["kronik_ust"], "EDM // TEK HAT", bg_color=(235, 238, 235), fg_color=RENK_KOYU, font_boyut=20)
    mi._logo_yerlestir(canvas, beyaz=False, y=yer["kronik_ust"] - 5, lw=228, golge=False)

    y = yer["ust"] + 20
    f_b = mi._font_yukle(mi.FONT_FRAUNCES, 56)
    draw.text((KENAR, y), "Doğru adımlarla", font=f_b, fill=RENK_KOYU); y += 64
    draw.text((KENAR, y), "GÜVENLİ KİRALAMA", font=f_b, fill=RENK_KIRMIZI); y += 76

    f_a = mi._font_yukle(mi.FONT_SANS_MEDIUM, 28)
    draw.text((KENAR, y), "Sorunuz varsa lafı uzatmayın, doğrudan arayın.", font=f_a, fill=RENK_GRI_METIN); y += 50

    draw.text((KENAR, y), "🔖 BU REHBERİ KAYDEDİN · NUMARAYI TELEFONUNUZA EKLEYİN", font=mi._font_yukle(mi.FONT_MONO_BOLD, 15), fill=RENK_KOYU); y += 40

    # DEV TİPOGRAFİK NUMARA (96px Mega Monolith!)
    draw.line([(KENAR, y), (GEN - KENAR, y)], fill=RENK_CIZGI, width=1); y += 30
    draw.text((KENAR, y), "DOĞRUDAN DANIŞMANLIK & İLETİŞİM HATTI", font=mi._font_yukle(mi.FONT_MONO_BOLD, 18), fill=RENK_KIRMIZI); y += 36
    draw.text((KENAR, y), "0536 343 41 97", font=mi._font_yukle(mi.FONT_MONO_BOLD, 92), fill=RENK_KOYU); y += 128
    draw.line([(KENAR, y), (GEN - KENAR, y)], fill=RENK_CIZGI, width=1); y += 36

    # Alt Bilgiler: Sol Danışman ve Ofis, Sağ QR
    draw.text((KENAR, y), "METİN ÖZDOĞAN", font=mi._font_yukle(mi.FONT_SANS_BOLD, 32), fill=RENK_KOYU); y += 42
    draw.text((KENAR, y), "EDM Yapı & Gayrimenkul  ·  Kurucu Danışman", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 22), fill=RENK_GRI_METIN); y += 42
    draw.text((KENAR, y), "Alibey Mah. Albay Yunus Dirik Cad. No: 58/A · Silivri", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 21), fill=RENK_GRI_METIN); y += 34
    draw.text((KENAR, y), "edmyapigayrimenkul.com   ·   info@edmyapigayrimenkul.com", font=mi._font_yukle(mi.FONT_MONO, 19), fill=RENK_SILIK)

    qr = _qr(164)
    canvas.paste(qr, (GEN - KENAR - 164, y - 110))
    draw.text((GEN - KENAR - 164 + 32, y - 110 + 164 + 8), "OFİS KONUMU", font=mi._font_yukle(mi.FONT_MONO_BOLD, 13), fill=RENK_SILIK)

    _yasal_ciz(draw, KENAR, yer, {"silik": RENK_SILIK})
    return _kaydet(canvas, "09_dev_numara_posteri")


# =============================================================================
# KONSEPT 10: RESMİ EKSPERTİZ MÜHRÜ & SERTİFİKA (OFFICIAL SEAL & STAMP)
# =============================================================================
def konsept_10_resmi_ekspertiz_muhru():
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    canvas = mi._filigran_uygula(canvas, acik_zemin=True)
    draw = ImageDraw.Draw(canvas)
    yer = mi._yerlesim()

    # Dairesel Resmi Mühür (Seal) Çizimi (Yüksek Güven ve Prestij)
    seal_r = 110
    seal_cx = GEN - KENAR - seal_r - 10
    seal_cy = yer["ust"] + 110

    # Dış İnce Daire ve İç Daire
    draw.ellipse([(seal_cx - seal_r, seal_cy - seal_r), (seal_cx + seal_r, seal_cy + seal_r)], outline=RENK_KIRMIZI, width=2)
    draw.ellipse([(seal_cx - seal_r + 8, seal_cy - seal_r + 8), (seal_cx + seal_r - 8, seal_cy + seal_r - 8)], outline=RENK_KIRMIZI, width=1)
    # Merkez Rozet Metni
    f_seal_c = mi._font_yukle(mi.FONT_MONO_BOLD, 15)
    draw.text((seal_cx - 48, seal_cy - 36), "★ ★ ★", font=f_seal_c, fill=RENK_KIRMIZI)
    draw.text((seal_cx - 62, seal_cy - 12), "DOĞRULANMIŞ", font=mi._font_yukle(mi.FONT_MONO_BOLD, 15), fill=RENK_KIRMIZI)
    draw.text((seal_cx - 62, seal_cy + 12), "SAHA REHBERİ", font=mi._font_yukle(mi.FONT_MONO_BOLD, 15), fill=RENK_KIRMIZI)
    draw.text((seal_cx - 40, seal_cy + 36), "SİLİVRİ", font=mi._font_yukle(mi.FONT_MONO_BOLD, 13), fill=RENK_KOYU)

    mi._rozet_ciz(draw, KENAR, yer["kronik_ust"], "RESMİ ONAYLI DANIŞMANLIK", bg_color=(235, 238, 235), fg_color=RENK_KOYU, font_boyut=18)
    mi._logo_yerlestir(canvas, beyaz=False, y=yer["kronik_ust"] - 5, lw=220, golge=False)

    # Başlık (Mühür yanında ferah akış)
    y = yer["ust"] + 20
    f_b = mi._font_yukle(mi.FONT_FRAUNCES, 54)
    draw.text((KENAR, y), "Doğru adımlarla", font=f_b, fill=RENK_KOYU); y += 62
    draw.text((KENAR, y), "GÜVENLİ KİRALAMA", font=f_b, fill=RENK_KIRMIZI); y += 74

    f_a = mi._font_yukle(mi.FONT_SANS_MEDIUM, 27)
    draw.text((KENAR, y), "Silivri ve Trakya genelinde mülk yönetimi ve hukuki", font=f_a, fill=RENK_GRI_METIN); y += 38
    draw.text((KENAR, y), "süreçlerinizde resmi onaylı danışman güvencesi.", font=f_a, fill=RENK_GRI_METIN); y += 52

    draw.text((KENAR, y), "🔖 BU REHBERİ KAYDEDİN // SİLİVRİ RESMİ DANIŞMANLIK ARŞİVİ", font=mi._font_yukle(mi.FONT_MONO_BOLD, 14), fill=RENK_KOYU); y += 46

    # Sertifika Ayırıcı Çerçeve
    draw.line([(KENAR, y), (GEN - KENAR, y)], fill=RENK_CIZGI, width=1); y += 36

    # İletişim Sertifikası
    by = y
    draw.text((KENAR, by), "YETKİLİ KURUCU DANIŞMAN", font=mi._font_yukle(mi.FONT_MONO_BOLD, 16), fill=RENK_KIRMIZI); by += 28
    draw.text((KENAR, by), "METİN ÖZDOĞAN", font=mi._font_yukle(mi.FONT_SANS_BOLD, 36), fill=RENK_KOYU); by += 46
    draw.text((KENAR, by), "EDM Yapı & Gayrimenkul  ·  Silivri ve Trakya Bölge Sorumlusu", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 21), fill=RENK_GRI_METIN); by += 46

    draw.text((KENAR, by), "DOĞRUDAN DANIŞMA HATTI", font=mi._font_yukle(mi.FONT_MONO_BOLD, 16), fill=RENK_KIRMIZI); by += 28
    draw.text((KENAR, by), "0536 343 41 97", font=mi._font_yukle(mi.FONT_MONO_BOLD, 56), fill=RENK_KOYU); by += 80

    draw.text((KENAR, by), "Alibey Mah. Albay Yunus Dirik Cad. No: 58/A · Silivri / İstanbul", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 21), fill=RENK_GRI_METIN); by += 32
    draw.text((KENAR, by), "edmyapigayrimenkul.com   ·   info@edmyapigayrimenkul.com", font=mi._font_yukle(mi.FONT_MONO, 18), fill=RENK_SILIK)

    # Sağ Altta Sertifika QR Kodu
    qr = _qr(160)
    canvas.paste(qr, (GEN - KENAR - 160, by - 120))
    draw.text((GEN - KENAR - 160 + 16, by - 120 + 160 + 8), "KONUM VE YOL TARİFİ", font=mi._font_yukle(mi.FONT_MONO_BOLD, 12), fill=RENK_SILIK)

    _yasal_ciz(draw, KENAR, yer, {"silik": RENK_SILIK}, "Bu içerik genel bilgilendirmedir; bağlayıcı hukuki işlemleriniz için avukatınıza danışın.")
    return _kaydet(canvas, "10_resmi_ekspertiz_muhru")


def main():
    print("10 Farklı Radikal Tasarım Konsepti Üretiliyor...")
    konsept_01_luks_kartvizit()
    konsept_02_merkezlenmis_kitap_afis()
    konsept_03_split_screen()
    konsept_04_mimari_pafta_grid()
    konsept_05_kurucu_mektubu()
    konsept_06_paspartu_fotograf()
    konsept_07_dikey_tipografi()
    konsept_08_iletisim_terminali()
    konsept_09_dev_numara_posteri()
    konsept_10_resmi_ekspertiz_muhru()
    print("10 radikal tasarım konseptinin tamamı başarıyla üretildi!")

if __name__ == "__main__":
    main()
