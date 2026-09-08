"""
make_image.py — EDM Marka Paftası Görsel Motoru
Pillow ile 1080x1350 (4:5 dikey) formatında kurumsal kimlik standartlarına
tam uyumlu Haber ve İlan slaytları üretir.
"""

from __future__ import annotations

import io
import logging
import math
import os
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from . import config, fetch_listings

log = logging.getLogger(__name__)

# Tuval boyutları (4:5 oranı)
GENISLIK = 1080
YUKSEKLIK = 1350

# Renk Paleti (EDM Marka Rehberi)
RENK_KIRMIZI = (240, 0, 13)       # #f0000d
RENK_KIRMIZI_DERIN = (196, 3, 15) # #c4030f
RENK_MUREKKEP = (18, 19, 22)      # #121316 (Koyu metin / Zemin)
RENK_KAGIT = (244, 244, 243)      # #f4f4f3 (Açık pafta zemini)
RENK_KIREC = (228, 228, 225)      # #e4e4e1
RENK_KURSUN = (138, 139, 143)     # #8a8b8f (Açıklama / İkincil metin)
RENK_CIZGI = (214, 214, 211)      # #d6d6d3 (Teknik saç teli çizgiler)
RENK_BEYAZ = (255, 255, 255)

# Font Yolları
FONT_FRAUNCES = config.yol_al("assets/fonts/Fraunces-Variable.ttf")
FONT_SANS = config.yol_al("assets/fonts/IBMPlexSans-Variable.ttf")
FONT_MONO = config.yol_al("assets/fonts/IBMPlexMono-Regular.ttf")

# Logo Yolları
LOGO_AMBLEM = config.yol_al("assets/logos/amblem.png")
LOGO_YATAY = config.yol_al("assets/logos/logo-yatay.png")
LOGO_YATAY_ACIK = config.yol_al("assets/logos/logo-yatay-acik.png")
LOGO_SLOGAN = config.yol_al("assets/logos/slogan.png")
LOGO_PIN = config.yol_al("assets/logos/pin-sembol.png")


def _font_yukle(yol: Path, boyut: int) -> ImageFont.FreeTypeFont:
    """TTF fontunu belirtilen boyutta yükler, bulunamazsa varsayılan döner."""
    try:
        return ImageFont.truetype(str(yol), boyut)
    except Exception as e:
        log.warning("Font yüklenemedi (%s, %d): %s", yol, boyut, e)
        return ImageFont.load_default()


def _metin_sar(metin: str, font: ImageFont.FreeTypeFont, azami_genislik: int, draw: ImageDraw.ImageDraw) -> List[str]:
    """Metni piksel genişliğine göre satırlara böler."""
    kelimeler = metin.split()
    satirlar = []
    mevcut = []

    for k in kelimeler:
        deneme = " ".join(mevcut + [k])
        bbox = draw.textbbox((0, 0), deneme, font=font)
        w = bbox[2] - bbox[0]
        if w <= azami_genislik:
            mevcut.append(k)
        else:
            if mevcut:
                satirlar.append(" ".join(mevcut))
                mevcut = [k]
            else:
                satirlar.append(k)
                mevcut = []
    if mevcut:
        satirlar.append(" ".join(mevcut))
    return satirlar


def _foto_indir_veya_ac(foto_url_veya_yol: str) -> Optional[Image.Image]:
    """URL veya yerel dosya yolundan görseli açar, RGB döndürür."""
    if not foto_url_veya_yol:
        return None
    try:
        if foto_url_veya_yol.startswith("http://") or foto_url_veya_yol.startswith("https://"):
            resp = requests.get(foto_url_veya_yol, timeout=12)
            if resp.status_code == 200:
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                return img
        else:
            p = Path(foto_url_veya_yol)
            if p.exists():
                return Image.open(p).convert("RGB")
    except Exception as e:
        log.warning("Görsel yüklenemedi (%s): %s", foto_url_veya_yol, e)
    return None


# =========================================================================
# 1. HABER SLAYTI ÜRETİCİ (4:5 DİKEY PAFTA)
# =========================================================================


def haber_slayti_1_ciz(
    manset: str,
    spot: str,
    kaynak: str,
    tarih: str,
    foto_url: Optional[str] = None,
    cikti_yolu: Optional[Path] = None,
) -> Path:
    """Haberin 1. slaytını (Kapak / Manşet) EDM Marka Paftası formatında çizer."""
    img = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_KAGIT)
    draw = ImageDraw.Draw(img)

    kenar_bosluk = 70
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)

    # 1. Üst Başlık Şeridi (Teknik Mono Üst Bant)
    draw.line([(kenar_bosluk, 80), (GENISLIK - kenar_bosluk, 80)], fill=RENK_CIZGI, width=1)

    font_mono_ust = _font_yukle(FONT_MONO, 20)
    ust_etiket = f"EDM PAFTA // {kaynak.upper()} — {tarih[:10]}"
    draw.text((kenar_bosluk, 50), ust_etiket, font=font_mono_ust, fill=RENK_KURSUN)

    # Sağ üstte kırmızı EDM pini
    if LOGO_PIN.exists():
        try:
            pin_img = Image.open(LOGO_PIN).convert("RGBA")
            pin_img.thumbnail((36, 36), Image.Resampling.LANCZOS)
            img.paste(pin_img, (GENISLIK - kenar_bosluk - pin_img.width, 42), pin_img)
        except Exception:
            pass

    y_imlec = 120

    # 2. Varsa Haber Fotoğrafı (Orantılı Kırpma)
    foto = _foto_indir_veya_ac(foto_url) if foto_url else None
    if foto:
        foto_h = 500
        foto_genisletilmis = ImageOps.fit(foto, (kullanilabilir_w, foto_h), Image.Resampling.LANCZOS)
        img.paste(foto_genisletilmis, (kenar_bosluk, y_imlec))

        # Fotoğraf çerçeve çizgisi
        draw.rectangle(
            [(kenar_bosluk, y_imlec), (kenar_bosluk + kullanilabilir_w, y_imlec + foto_h)],
            outline=RENK_CIZGI,
            width=1,
        )
        y_imlec += foto_h + 45
    else:
        y_imlec += 60

    # 3. Manşet (Fraunces Serif — Sakin, Tok, Vurucu)
    font_manset = _font_yukle(FONT_FRAUNCES, 52)
    manset_satirlari = _metin_sar(manset, font_manset, kullanilabilir_w, draw)

    for satir in manset_satirlari[:4]:
        draw.text((kenar_bosluk, y_imlec), satir, font=font_manset, fill=RENK_MUREKKEP)
        y_imlec += 66

    y_imlec += 25

    # İnce kırmızı vurgu çizgisi
    draw.line([(kenar_bosluk, y_imlec), (kenar_bosluk + 80, y_imlec)], fill=RENK_KIRMIZI, width=3)
    y_imlec += 30

    # 4. Spot Metin (IBM Plex Sans)
    font_spot = _font_yukle(FONT_SANS, 30)
    spot_satirlari = _metin_sar(spot, font_spot, kullanilabilir_w, draw)

    for satir in spot_satirlari[:4]:
        draw.text((kenar_bosluk, y_imlec), satir, font=font_spot, fill=RENK_MUREKKEP)
        y_imlec += 44

    # 5. Alt İmza Şeridi (Footer)
    alt_y = YUKSEKLIK - 100
    draw.line([(kenar_bosluk, alt_y), (GENISLIK - kenar_bosluk, alt_y)], fill=RENK_CIZGI, width=1)

    font_mono_alt = _font_yukle(FONT_MONO, 22)
    draw.text((kenar_bosluk, alt_y + 25), "EDM YAPI & GAYRİMENKUL", font=font_mono_alt, fill=RENK_MUREKKEP)
    
    web_yazi = "edmyapigayrimenkul.com"
    bbox_w = draw.textbbox((0, 0), web_yazi, font=font_mono_alt)[2]
    draw.text((GENISLIK - kenar_bosluk - bbox_w, alt_y + 25), web_yazi, font=font_mono_alt, fill=RENK_KURSUN)

    # Kaydet
    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/haber_kapak_{os.getpid()}.jpg")
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    img.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


def haber_slayti_2_ciz(
    manset: str,
    detay_metni: str,
    vurgu_sayi: Optional[str] = None,
    vurgu_etiket: Optional[str] = None,
    cikti_yolu: Optional[Path] = None,
) -> Path:
    """Haberin 2. slaytını (Detay / Veri Paftası) çizer."""
    img = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_KAGIT)
    draw = ImageDraw.Draw(img)

    kenar_bosluk = 70
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)

    # Üst Şerit
    draw.line([(kenar_bosluk, 80), (GENISLIK - kenar_bosluk, 80)], fill=RENK_CIZGI, width=1)
    font_mono_ust = _font_yukle(FONT_MONO, 20)
    draw.text((kenar_bosluk, 50), "EDM ANALİZ // DETAY & PİYASA ETKİSİ", font=font_mono_ust, fill=RENK_KURSUN)

    # Sağ üst sayfa no
    draw.text((GENISLIK - kenar_bosluk - 50, 50), "02 / 02", font=font_mono_ust, fill=RENK_KIRMIZI)

    y_imlec = 140

    # Varsa Büyük Vurgu Sayısı (Örn: %25 veya 850 bin)
    if vurgu_sayi:
        font_vurgu = _font_yukle(FONT_FRAUNCES, 96)
        draw.text((kenar_bosluk, y_imlec), vurgu_sayi, font=font_vurgu, fill=RENK_KIRMIZI)
        bbox = draw.textbbox((kenar_bosluk, y_imlec), vurgu_sayi, font=font_vurgu)
        y_imlec = bbox[3] + 10

        if vurgu_etiket:
            font_etiket = _font_yukle(FONT_MONO, 24)
            draw.text((kenar_bosluk, y_imlec), vurgu_etiket.upper(), font=font_etiket, fill=RENK_KURSUN)
            y_imlec += 50

        # Bölücü çizgi
        draw.line([(kenar_bosluk, y_imlec), (GENISLIK - kenar_bosluk, y_imlec)], fill=RENK_CIZGI, width=1)
        y_imlec += 45
    else:
        y_imlec += 40

    # Detay Paragrafı (IBM Plex Sans)
    font_detay = _font_yukle(FONT_SANS, 34)
    satirlar = _metin_sar(detay_metni, font_detay, kullanilabilir_w, draw)

    for satir in satirlar:
        draw.text((kenar_bosluk, y_imlec), satir, font=font_detay, fill=RENK_MUREKKEP)
        y_imlec += 52

    # Yatırım Ortağı Vaat Kutusu
    kutu_y = YUKSEKLIK - 320
    draw.rectangle([(kenar_bosluk, kutu_y), (GENISLIK - kenar_bosluk, kutu_y + 160)], fill=RENK_KIREC)
    draw.rectangle([(kenar_bosluk, kutu_y), (kenar_bosluk + 6, kutu_y + 160)], fill=RENK_KIRMIZI)

    font_kutu_baslik = _font_yukle(FONT_FRAUNCES, 28)
    draw.text((kenar_bosluk + 30, kutu_y + 25), "Tapuya kadar yanınızda.", font=font_kutu_baslik, fill=RENK_MUREKKEP)

    font_kutu_metin = _font_yukle(FONT_SANS, 22)
    kutu_aciklama = "Mevzuat, imar ve değerleme süreçlerindeki tüm sorularınız için EDM uzmanlığı bir telefon uzağınızda."
    kutu_satirlari = _metin_sar(kutu_aciklama, font_kutu_metin, kullanilabilir_w - 60, draw)
    ky = kutu_y + 70
    for ks in kutu_satirlari:
        draw.text((kenar_bosluk + 30, ky), ks, font=font_kutu_metin, fill=RENK_KURSUN)
        ky += 32

    # Alt Şerit
    alt_y = YUKSEKLIK - 100
    draw.line([(kenar_bosluk, alt_y), (GENISLIK - kenar_bosluk, alt_y)], fill=RENK_CIZGI, width=1)
    font_mono_alt = _font_yukle(FONT_MONO, 22)
    draw.text((kenar_bosluk, alt_y + 25), "EDM YAPI & GAYRİMENKUL · 0536 343 41 97", font=font_mono_alt, fill=RENK_MUREKKEP)

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/haber_detay_{os.getpid()}.jpg")
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    img.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


# =========================================================================
# 2. İLAN SLAYTI ÜRETİCİ (TEK TIKLA PORTFÖY PAYLAŞIMI)
# =========================================================================


def ilan_kapak_slayti_ciz(
    ilan: Dict[str, Any],
    cikti_yolu: Optional[Path] = None,
) -> Path:
    """İlanın 1. slaytını (Prestijli Fotoğraf + Mimari Panel) çizer."""
    img = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_MUREKKEP)
    draw = ImageDraw.Draw(img)

    # 1. Ana Mülk Fotoğrafı (Üst %65'i kaplar: 1080x880)
    gorseller = ilan.get("gorseller", [])
    if isinstance(gorseller, str):
        import json
        try:
            gorseller = json.loads(gorseller)
        except Exception:
            gorseller = []

    foto = _foto_indir_veya_ac(gorseller[0]) if gorseller else None
    if foto:
        foto_kirpilmis = ImageOps.fit(foto, (GENISLIK, 880), Image.Resampling.LANCZOS)
        img.paste(foto_kirpilmis, (0, 0))

        # Fotoğrafın altına hafif gölge perdesi koy (panelle kaynaşsın)
        perde = Image.new("RGBA", (GENISLIK, 150), (0, 0, 0, 0))
        p_draw = ImageDraw.Draw(perde)
        for i in range(150):
            alfa = int(220 * (i / 150))
            p_draw.line([(0, i), (GENISLIK, i)], fill=(18, 19, 22, alfa))
        img.paste(perde, (0, 730), perde)

    # Rozetler: Sol üst amblem, sağ üst işlem tipi
    if LOGO_PIN.exists():
        try:
            pin = Image.open(LOGO_PIN).convert("RGBA")
            pin.thumbnail((44, 44), Image.Resampling.LANCZOS)
            # Beyaz daire zemin arkasına
            draw.ellipse([(45, 45), (105, 105)], fill=RENK_BEYAZ)
            img.paste(pin, (53, 53), pin)
        except Exception:
            pass

    # Sağ üst satılık/kiralık rozeti
    islem = (ilan.get("islem") or "satilik").upper()
    tip = (ilan.get("tip") or "Gayrimenkul").upper()
    rozet_metni = f"{islem} {tip}"
    font_rozet = _font_yukle(FONT_MONO, 22)
    bbox_r = draw.textbbox((0, 0), rozet_metni, font=font_rozet)
    rw = bbox_r[2] - bbox_r[0]
    draw.rectangle([(GENISLIK - rw - 80, 50), (GENISLIK - 50, 96)], fill=RENK_KIRMIZI)
    draw.text((GENISLIK - rw - 65, 62), rozet_metni, font=font_rozet, fill=RENK_BEYAZ)

    # 2. Alt Rölöve / Mimari Panel (880px'den 1350px'e kadar)
    kenar_bosluk = 65
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)
    panel_y = 880

    # Panel üst ayrım çizgisi
    draw.line([(0, panel_y), (GENISLIK, panel_y)], fill=RENK_CIZGI, width=1)

    # Lokasyon etiketi
    ilce = ilan.get("ilce", "Silivri")
    mahalle = ilan.get("mahalle", "")
    lokasyon_metni = f"{ilce.upper()} · {mahalle.upper()}"
    font_mono_lok = _font_yukle(FONT_MONO, 22)
    draw.text((kenar_bosluk, panel_y + 35), lokasyon_metni, font=font_mono_lok, fill=RENK_KURSUN)

    # Büyük İlan Başlığı (Fraunces Serif)
    font_baslik = _font_yukle(FONT_FRAUNCES, 46)
    baslik_satirlari = _metin_sar(ilan.get("baslik", ""), font_baslik, kullanilabilir_w, draw)
    by = panel_y + 75
    for satir in baslik_satirlari[:2]:
        draw.text((kenar_bosluk, by), satir, font=font_baslik, fill=RENK_KAGIT)
        by += 56

    # Alt Çizgi
    cizgi_y = YUKSEKLIK - 130
    draw.line([(kenar_bosluk, cizgi_y), (GENISLIK - kenar_bosluk, cizgi_y)], fill=(40, 42, 48), width=1)

    # Metrikler (Sol alt: Oda | Metrekare)
    m2 = ilan.get("m2")
    oda = ilan.get("oda")
    metrikler = []
    if m2:
        metrikler.append(f"{int(m2):,} m²".replace(",", "."))
    if oda:
        metrikler.append(str(oda))
    metrik_yazi = "  |  ".join(metrikler)

    font_metrik = _font_yukle(FONT_MONO, 26)
    draw.text((kenar_bosluk, cizgi_y + 35), metrik_yazi, font=font_metrik, fill=RENK_KAGIT)

    # Fiyat (Sağ alt: Net, tabular rakam)
    fiyat_str = fetch_listings.ilan_fiyat_bicimlendir(
        float(ilan.get("fiyat", 0)), ilan.get("paraBirimi", "TRY")
    )
    font_fiyat = _font_yukle(FONT_MONO, 38)
    bbox_f = draw.textbbox((0, 0), fiyat_str, font=font_fiyat)
    fw = bbox_f[2] - bbox_f[0]
    draw.text((GENISLIK - kenar_bosluk - fw, cizgi_y + 26), fiyat_str, font=font_fiyat, fill=RENK_KIRMIZI)

    # Kaydet
    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/ilan_kapak_{ilan.get('id')}.jpg")
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    img.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


def ilan_kapanis_slayti_ciz(
    ilan: Dict[str, Any],
    cikti_yolu: Optional[Path] = None,
) -> Path:
    """İlanın son slaytını (Danışman ve İletişim Kartı) çizer."""
    img = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_KAGIT)
    draw = ImageDraw.Draw(img)

    kenar_bosluk = 80
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)

    # Üst Şerit
    draw.line([(kenar_bosluk, 100), (GENISLIK - kenar_bosluk, 100)], fill=RENK_CIZGI, width=1)
    font_mono_ust = _font_yukle(FONT_MONO, 22)
    draw.text((kenar_bosluk, 65), "EDM YAPI & GAYRİMENKUL // İLETİŞİM", font=font_mono_ust, fill=RENK_KURSUN)

    # Merkez Başlık
    font_baslik = _font_yukle(FONT_FRAUNCES, 60)
    draw.text((kenar_bosluk, 240), "Detaylı bilgi ve", font=font_baslik, fill=RENK_MUREKKEP)
    draw.text((kenar_bosluk, 315), "yerinde sunum için.", font=font_baslik, fill=RENK_KIRMIZI)

    # Açıklama
    font_aciklama = _font_yukle(FONT_SANS, 30)
    draw.text(
        (kenar_bosluk, 420),
        "Portföyümüzdeki bu gayrimenkulün tapu, imar ve güncel piyasa\nkoşullarını birlikte değerlendirelim.",
        font=font_aciklama,
        fill=RENK_MUREKKEP,
    )

    # Danışman Bilgi Paneli
    kutu_y = 560
    draw.rectangle([(kenar_bosluk, kutu_y), (GENISLIK - kenar_bosluk, kutu_y + 360)], fill=RENK_BEYAZ, outline=RENK_CIZGI)

    font_danisman_etiket = _font_yukle(FONT_MONO, 22)
    draw.text((kenar_bosluk + 40, kutu_y + 40), "YATIRIM DANIŞMANINIZ", font=font_danisman_etiket, fill=RENK_KIRMIZI)

    danisman_adi = "Doğukan Özdoğan"
    if "metin" in str(ilan.get("danisman", "")).lower():
        danisman_adi = "Metin Özdoğan"
    elif "ercan" in str(ilan.get("danisman", "")).lower():
        danisman_adi = "Ercan Taşdemirler"
    elif "basri" in str(ilan.get("danisman", "")).lower():
        danisman_adi = "Basri Çelik"

    font_danisman_ad = _font_yukle(FONT_FRAUNCES, 44)
    draw.text((kenar_bosluk + 40, kutu_y + 80), danisman_adi, font=font_danisman_ad, fill=RENK_MUREKKEP)

    font_tel = _font_yukle(FONT_MONO, 38)
    draw.text((kenar_bosluk + 40, kutu_y + 160), "0536 343 41 97", font=font_tel, fill=RENK_MUREKKEP)

    font_adres = _font_yukle(FONT_SANS, 22)
    draw.text((kenar_bosluk + 40, kutu_y + 240), "Alibey Mah. Albay Yunus Dirik Cad. No: 58/A, Silivri", font=font_adres, fill=RENK_KURSUN)
    draw.text((kenar_bosluk + 40, kutu_y + 280), "info@edmyapigayrimenkul.com · edmyapigayrimenkul.com", font=font_adres, fill=RENK_KURSUN)

    # Alt Şerit ve Logo
    if LOGO_YATAY.exists():
        try:
            logo = Image.open(LOGO_YATAY).convert("RGBA")
            logo.thumbnail((400, 100), Image.Resampling.LANCZOS)
            img.paste(logo, (kenar_bosluk, YUKSEKLIK - 180), logo)
        except Exception:
            pass

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/ilan_kapanis_{ilan.get('id')}.jpg")
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    img.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu
