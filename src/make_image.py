"""
make_image.py — EDM Marka Paftası Görsel Motoru (V2 - Ultra Premium & Kanca Etkisi)
Pillow ile 1080x1350 (4:5 dikey) formatında kurumsal kimlik standartlarına
tam uyumlu, yüksek dönüşümlü Haber ve İlan slaytları üretir.
"""

from __future__ import annotations

import io
import json
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

# Tuval boyutları (Instagram & Threads 4:5 Dikey Oranı)
GENISLIK = 1080
YUKSEKLIK = 1350

# Renk Paleti (EDM Marka Rehberi & Web Sitesi)
RENK_KIRMIZI = (240, 0, 13)       # #f0000d (İmza EDM Kırmızısı)
RENK_KIRMIZI_DERIN = (196, 3, 15) # #c4030f
RENK_MUREKKEP = (18, 19, 22)      # #121316 (Derin Mürekkep Siyahı)
RENK_MUREKKEP_2 = (26, 28, 33)    # #1a1c21 (İkincil Koyu Zemin)
RENK_MUREKKEP_3 = (36, 39, 45)    # #24272d (Kutu Çerçeve Rengi)
RENK_KAGIT = (244, 244, 243)      # #f4f4f3 (Sıcak Pafta Kağıdı)
RENK_KIREC = (228, 228, 225)      # #e4e4e1 (Açık Çerçeve & Kutu)
RENK_KURSUN = (138, 139, 143)     # #8a8b8f (Teknik Rölöve & Metadata)
RENK_CIZGI = (214, 214, 211)      # #d6d6d3 (Kılavuz Çizgiler)
RENK_CIZGI_KOYU = (45, 48, 56)    # Koyu zemin ayrım çizgisi
RENK_BEYAZ = (255, 255, 255)

# Doğrulanmış Türkçe Destekli Font Yolları
FONT_FRAUNCES = config.yol_al("assets/fonts/Fraunces.ttf")
FONT_SANS = config.yol_al("assets/fonts/IBMPlexSans[wdth,wght].ttf")
FONT_MONO = config.yol_al("assets/fonts/IBMPlexMono.ttf")
FONT_MONO_BOLD = config.yol_al("assets/fonts/IBMPlexMono-Bold.ttf")

# Logo ve Amblem Yolları
LOGO_AMBLEM = config.yol_al("assets/logos/amblem.png")
LOGO_YATAY = config.yol_al("assets/logos/logo-yatay.png")
LOGO_YATAY_ACIK = config.yol_al("assets/logos/logo-yatay-acik.png")
LOGO_SLOGAN = config.yol_al("assets/logos/slogan.png")
LOGO_PIN = config.yol_al("assets/logos/pin-sembol.png")


def _font_yukle(yol: Path, boyut: int) -> ImageFont.FreeTypeFont:
    """TTF fontunu belirtilen boyutta yükler."""
    try:
        if yol.exists():
            return ImageFont.truetype(str(yol), boyut)
    except Exception as e:
        log.warning("Font yükleme hatası (%s, %d): %s", yol, boyut, e)
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
    """URL veya yerel dosyadan görseli açar, User-Agent ekleyerek çeker."""
    if not foto_url_veya_yol:
        return None
    try:
        if foto_url_veya_yol.startswith("http://") or foto_url_veya_yol.startswith("https://"):
            headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
            resp = requests.get(foto_url_veya_yol, headers=headers, timeout=12)
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


def _rozet_ciz(draw: ImageDraw.ImageDraw, x: int, y: int, metin: str, bg_color=RENK_KIRMIZI, fg_color=RENK_BEYAZ, font_boyut=20) -> int:
    """Teknik mono rozet çizer ve kapladığı genişliği döndürür."""
    font = _font_yukle(FONT_MONO_BOLD, font_boyut)
    bbox = draw.textbbox((0, 0), metin, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    pad_x = 18
    pad_y = 10
    draw.rounded_rectangle(
        [(x, y), (x + w + (pad_x * 2), y + h + (pad_y * 2))],
        radius=4,
        fill=bg_color,
    )
    draw.text((x + pad_x, y + pad_y - 1), metin, font=font, fill=fg_color)
    return w + (pad_x * 2)


def _arti_isareti_ciz(draw: ImageDraw.ImageDraw, x: int, y: int, renk=RENK_KURSUN, boyut=12):
    """Rölöve ve imar paftası köşe artı işaretini çizer."""
    r = boyut // 2
    draw.line([(x - r, y), (x + r, y)], fill=renk, width=1)
    draw.line([(x, y - r), (x, y + r)], fill=renk, width=1)


# =========================================================================
# 1. İLAN SLAYTI ÜRETİCİLERİ (TEK TIKLA PORTFÖY PAYLAŞIMI)
# =========================================================================


def ilan_kapak_slayti_ciz(ilan: Dict[str, Any], cikti_yolu: Optional[Path] = None) -> Path:
    """İlanın 1. slaytı (Kanca / Hero Kapak): Devasa fotoğraf, şık serif manşet ve fiyat."""
    img = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_MUREKKEP)
    draw = ImageDraw.Draw(img)

    # 1. Fotoğrafları Al
    gorseller = ilan.get("gorseller")
    if not gorseller:
        try:
            gorseller = json.loads(ilan.get("gorseller_json") or "[]")
        except Exception:
            gorseller = []

    foto = _foto_indir_veya_ac(gorseller[0]) if gorseller else None
    if foto:
        # Fotoğrafı 1080x920 alanına şık kırp
        foto_kirpilmis = ImageOps.fit(foto, (GENISLIK, 920), Image.Resampling.LANCZOS)
        img.paste(foto_kirpilmis, (0, 0))

        # Alttan yukarıya doğru derin sinematik gradyan perde (y=500'den y=920'ye)
        perde = Image.new("RGBA", (GENISLIK, 420), (0, 0, 0, 0))
        p_draw = ImageDraw.Draw(perde)
        for i in range(420):
            alfa = int(255 * (i / 420) ** 1.3)
            p_draw.line([(0, i), (GENISLIK, i)], fill=(18, 19, 22, min(alfa, 255)))
        img.paste(perde, (0, 500), perde)
    else:
        # Fotoğraf yoksa prestijli geometrik koyu zemin
        draw.rectangle([(0, 0), (GENISLIK, 920)], fill=RENK_MUREKKEP_2)

    # 2. Üst Bar: Sol üst rozet, sağ üst EDM Açık Logo
    kenar_bosluk = 65
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)

    islem = (ilan.get("islem") or "satilik").upper()
    tip = (ilan.get("tip") or "Gayrimenkul").upper()
    rozet_metni = f"{islem} {tip}"
    _rozet_ciz(draw, kenar_bosluk, 55, rozet_metni, bg_color=RENK_KIRMIZI, font_boyut=20)

    # Sağ üst logo (logo-yatay-acik.png)
    if LOGO_YATAY_ACIK.exists():
        try:
            logo = Image.open(LOGO_YATAY_ACIK).convert("RGBA")
            lw = 240
            lh = int(logo.height * (lw / logo.width))
            logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)
            img.paste(logo, (GENISLIK - kenar_bosluk - lw, 52), logo)
        except Exception:
            pass

    # 3. Rölöve Ayrım Çizgisi & Köşe Artı İşaretleri (y=830)
    panel_y = 830
    draw.line([(kenar_bosluk, panel_y), (GENISLIK - kenar_bosluk, panel_y)], fill=RENK_CIZGI_KOYU, width=1)
    _arti_isareti_ciz(draw, kenar_bosluk, panel_y, renk=RENK_KIRMIZI, boyut=14)
    _arti_isareti_ciz(draw, GENISLIK - kenar_bosluk, panel_y, renk=RENK_KIRMIZI, boyut=14)

    # 4. Lokasyon & İlan No (Mono Metadata)
    ilce = (ilan.get("ilce") or "SİLİVRİ").upper()
    mahalle = (ilan.get("mahalle") or "").upper()
    lokasyon_yazi = f"{ilce} · {mahalle}  //  PORTFÖY NO: #{ilan.get('id', '')}"
    font_mono_lok = _font_yukle(FONT_MONO, 20)
    draw.text((kenar_bosluk, panel_y + 24), lokasyon_yazi, font=font_mono_lok, fill=RENK_KURSUN)

    # 5. Büyük Başlık (Fraunces Serif — Zarafet ve Kanca)
    baslik = ilan.get("baslik", "").strip()
    font_baslik = _font_yukle(FONT_FRAUNCES, 46)
    baslik_satirlari = _metin_sar(baslik, font_baslik, kullanilabilir_w, draw)
    by = panel_y + 64
    for satir in baslik_satirlari[:2]:
        draw.text((kenar_bosluk, by), satir, font=font_baslik, fill=RENK_KAGIT)
        by += 54

    # 6. Devasa Fiyat & Vurgu (Fraunces Serif)
    fiyat_ham = float(ilan.get("fiyat", 0))
    islem_kiralik = "kiralik" in str(ilan.get("islem", "")).lower()
    if islem_kiralik:
        fiyat_metni = f"{int(fiyat_ham):,} TL / Ay".replace(",", ".")
    else:
        fiyat_metni = f"{int(fiyat_ham):,} TL".replace(",", ".")

    fiyat_y = by + 20
    font_fiyat_etiket = _font_yukle(FONT_MONO, 18)
    draw.text((kenar_bosluk, fiyat_y), "GÜNCEL FİYAT", font=font_fiyat_etiket, fill=RENK_KIRMIZI)

    font_fiyat = _font_yukle(FONT_FRAUNCES, 58)
    draw.text((kenar_bosluk, fiyat_y + 24), fiyat_metni, font=font_fiyat, fill=RENK_KAGIT)

    # 7. Teknik Metrikler Şeridi (m², Oda, vb.)
    metrik_y = YUKSEKLIK - 145
    draw.line([(kenar_bosluk, metrik_y), (GENISLIK - kenar_bosluk, metrik_y)], fill=RENK_CIZGI_KOYU, width=1)

    m2 = ilan.get("m2")
    oda = ilan.get("oda")
    parcalar = []
    if m2:
        parcalar.append(f"{int(m2):,} m²".replace(",", "."))
    if oda:
        parcalar.append(str(oda))
    parcalar.append("SİLİVRİ BÖLGE UZMANLIĞI")

    font_metrik = _font_yukle(FONT_MONO, 22)
    draw.text((kenar_bosluk, metrik_y + 22), "  |  ".join(parcalar), font=font_metrik, fill=RENK_KURSUN)

    # Sağ Altta Kaydırma İşareti (Hook CTA)
    font_kaydir = _font_yukle(FONT_MONO_BOLD, 20)
    kaydir_metni = "01 / 03 >"
    bbox_k = draw.textbbox((0, 0), kaydir_metni, font=font_kaydir)
    kw = bbox_k[2] - bbox_k[0]
    draw.text((GENISLIK - kenar_bosluk - kw, metrik_y + 22), kaydir_metni, font=font_kaydir, fill=RENK_KIRMIZI)

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/ilan_kapak_{ilan.get('id')}.jpg")
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    img.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


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
        except Exception:
            pass

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

    maddeler = [
        ("01", "Mülkiyet & İmar", "Tapu kayıtları, iskan ve kadastral sınırları incelenmiş güvenli gayrimenkul."),
        ("02", "Konum & Ulaşım", f"{ilan.get('mahalle', 'Silivri')} bölgesinde ana ulaşım akslarına ve sahil hattına yakın."),
        ("03", "Kullanım Konforu", "Ferah yerleşim planı, doğal ışık alan odalar ve yüksek kullanım ergonomisi."),
        ("04", "Yatırım Potansiyeli", "Silivri ve Trakya gelişim aksında değer kazanma potansiyeli yüksek portföy."),
    ]

    ky = y_kutu + 60
    font_no = _font_yukle(FONT_MONO_BOLD, 22)
    font_mb = _font_yukle(FONT_FRAUNCES, 24)
    font_mt = _font_yukle(FONT_SANS, 19)

    for no, bas, aciklama in maddeler:
        # Sol kırmızı numara
        draw.text((kenar_bosluk, ky), no, font=font_no, fill=RENK_KIRMIZI)
        # Başlık
        draw.text((kenar_bosluk + 55, ky - 2), bas, font=font_mb, fill=RENK_KAGIT)
        # Açıklama
        draw.text((kenar_bosluk + 55, ky + 30), aciklama, font=font_mt, fill=RENK_KURSUN)
        # Alt ayrım çizgisi
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


def ilan_kapanis_slayti_ciz(ilan: Dict[str, Any], cikti_yolu: Optional[Path] = None) -> Path:
    """İlanın 3. slaytı (Yatırım Danışmanı & İletişim Kartı): Sıcak kağıt, güven veren kurumsal kimlik."""
    img = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_KAGIT)
    draw = ImageDraw.Draw(img)

    kenar_bosluk = 80
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)

    # 1. Üst Şerit
    draw.line([(kenar_bosluk, 90), (GENISLIK - kenar_bosluk, 90)], fill=RENK_CIZGI, width=1)
    font_mono_ust = _font_yukle(FONT_MONO, 22)
    draw.text((kenar_bosluk, 55), "EDM YAPI & GAYRİMENKUL // İLETİŞİM", font=font_mono_ust, fill=RENK_KURSUN)

    # 2. Vurucu Başlık (Fraunces Serif)
    font_baslik = _font_yukle(FONT_FRAUNCES, 62)
    draw.text((kenar_bosluk, 200), "Detaylı bilgi ve", font=font_baslik, fill=RENK_MUREKKEP)
    draw.text((kenar_bosluk, 280), "yerinde sunum için.", font=font_baslik, fill=RENK_KIRMIZI)

    # Açıklama
    font_aciklama = _font_yukle(FONT_SANS, 28)
    draw.text(
        (kenar_bosluk, 385),
        "Portföyümüzdeki bu gayrimenkulün tapu, imar ve güncel piyasa\nkoşullarını yerinde birlikte değerlendirelim.",
        font=font_aciklama,
        fill=RENK_MUREKKEP,
    )

    # 3. Danışman Kartı (Beyaz Lüks Kutu)
    kutu_y = 520
    draw.rectangle([(kenar_bosluk, kutu_y), (GENISLIK - kenar_bosluk, kutu_y + 390)], fill=RENK_BEYAZ, outline=RENK_CIZGI)
    draw.rectangle([(kenar_bosluk, kutu_y), (kenar_bosluk + 8, kutu_y + 390)], fill=RENK_KIRMIZI)

    font_danisman_etiket = _font_yukle(FONT_MONO_BOLD, 22)
    draw.text((kenar_bosluk + 45, kutu_y + 40), "YATIRIM DANIŞMANINIZ", font=font_danisman_etiket, fill=RENK_KIRMIZI)

    danisman_adi = "Doğukan Özdoğan"
    d_raw = str(ilan.get("danisman", "")).lower()
    if "metin" in d_raw:
        danisman_adi = "Metin Özdoğan"
    elif "ercan" in d_raw:
        danisman_adi = "Ercan Taşdemirler"
    elif "basri" in d_raw:
        danisman_adi = "Basri Çelik"

    font_danisman_ad = _font_yukle(FONT_FRAUNCES, 48)
    draw.text((kenar_bosluk + 45, kutu_y + 85), danisman_adi, font=font_danisman_ad, fill=RENK_MUREKKEP)

    font_tel = _font_yukle(FONT_MONO_BOLD, 40)
    draw.text((kenar_bosluk + 45, kutu_y + 170), "0536 343 41 97", font=font_tel, fill=RENK_MUREKKEP)

    draw.line([(kenar_bosluk + 45, kutu_y + 245), (GENISLIK - kenar_bosluk - 45, kutu_y + 245)], fill=RENK_CIZGI, width=1)

    font_adres = _font_yukle(FONT_SANS, 24)
    draw.text((kenar_bosluk + 45, kutu_y + 270), "Alibey Mah. Albay Yunus Dirik Cad. No: 58/A, Silivri", font=font_adres, fill=RENK_KURSUN)
    draw.text((kenar_bosluk + 45, kutu_y + 315), "info@edmyapigayrimenkul.com · edmyapigayrimenkul.com", font=font_adres, fill=RENK_MUREKKEP)

    # 4. Alt Logo (Normal Yatay Logo)
    if LOGO_YATAY.exists():
        try:
            logo = Image.open(LOGO_YATAY).convert("RGBA")
            lw = 380
            lh = int(logo.height * (lw / logo.width))
            logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)
            img.paste(logo, (kenar_bosluk, YUKSEKLIK - 240), logo)
        except Exception:
            pass

    font_slogan = _font_yukle(FONT_MONO, 20)
    draw.text((kenar_bosluk, YUKSEKLIK - 90), "EDM YAPI & GAYRİMENKUL · YATIRIM ORTAĞINIZ", font=font_slogan, fill=RENK_KURSUN)

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/ilan_kapanis_{ilan.get('id')}.jpg")
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    img.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


# =========================================================================
# 2. HABER & ANALİZ SLAYTI ÜRETİCİLERİ (EDİTORİAL PAFTA)
# =========================================================================


def haber_slayti_1_ciz(
    manset: str,
    spot: str,
    kaynak: str,
    tarih: str,
    foto_url: Optional[str] = None,
    cikti_yolu: Optional[Path] = None,
) -> Path:
    """Haberin 1. slaytı (Kapak / Manşet): Kanca etkisi yaratan editorial mimari pafta."""
    img = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_MUREKKEP)
    draw = ImageDraw.Draw(img)

    kenar_bosluk = 70
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)

    # 1. Üst Şerit
    _rozet_ciz(draw, kenar_bosluk, 55, "EDM ANALİZ // GAYRİMENKUL", bg_color=RENK_KIRMIZI, font_boyut=20)

    if LOGO_YATAY_ACIK.exists():
        try:
            logo = Image.open(LOGO_YATAY_ACIK).convert("RGBA")
            lw = 220
            lh = int(logo.height * (lw / logo.width))
            logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)
            img.paste(logo, (GENISLIK - kenar_bosluk - lw, 52), logo)
        except Exception:
            pass

    panel_y = 120
    draw.line([(kenar_bosluk, panel_y), (GENISLIK - kenar_bosluk, panel_y)], fill=RENK_CIZGI_KOYU, width=1)
    _arti_isareti_ciz(draw, kenar_bosluk, panel_y, renk=RENK_KIRMIZI, boyut=14)

    # 2. Kaynak & Tarih
    font_mono_ust = _font_yukle(FONT_MONO, 20)
    draw.text((kenar_bosluk, panel_y + 24), f"KAYNAK: {kaynak.upper()}  //  TARİH: {tarih[:10]}", font=font_mono_ust, fill=RENK_KURSUN)

    # 3. Devasa Manşet (Fraunces Serif — Hook Etkisi)
    font_manset = _font_yukle(FONT_FRAUNCES, 56)
    satirlar = _metin_sar(manset, font_manset, kullanilabilir_w, draw)
    my = panel_y + 80
    for s in satirlar[:4]:
        draw.text((kenar_bosluk, my), s, font=font_manset, fill=RENK_KAGIT)
        my += 68

    # 4. Spot Metin (Plex Sans)
    font_spot = _font_yukle(FONT_SANS, 30)
    spot_satirlari = _metin_sar(spot, font_spot, kullanilabilir_w, draw)
    sy = my + 30
    for ss in spot_satirlari[:3]:
        draw.text((kenar_bosluk, sy), ss, font=font_spot, fill=RENK_KIREC)
        sy += 44

    # 5. Varsa Görsel veya Mimari Veri Kutusu
    kutu_y = sy + 40
    kutu_h = YUKSEKLIK - kutu_y - 140
    if kutu_h > 150:
        draw.rectangle([(kenar_bosluk, kutu_y), (GENISLIK - kenar_bosluk, kutu_y + kutu_h)], fill=RENK_MUREKKEP_2, outline=RENK_CIZGI_KOYU)
        draw.rectangle([(kenar_bosluk, kutu_y), (kenar_bosluk + 6, kutu_y + kutu_h)], fill=RENK_KIRMIZI)

        draw.text((kenar_bosluk + 35, kutu_y + 35), "SEKTÖREL DEĞERLENDİRME", font=_font_yukle(FONT_MONO_BOLD, 22), fill=RENK_KIRMIZI)
        ozet_yazi = "Silivri ve Trakya aksındaki piyasa dinamiklerini, resmi veriler ve saha tecrübemizle analiz ediyoruz."
        ozet_satir = _metin_sar(ozet_yazi, _font_yukle(FONT_SANS, 24), kullanilabilir_w - 70, draw)
        oy = kutu_y + 75
        for osat in ozet_satir:
            draw.text((kenar_bosluk + 35, oy), osat, font=_font_yukle(FONT_SANS, 24), fill=RENK_KURSUN)
            oy += 34

    # 6. Alt Şerit
    alt_y = YUKSEKLIK - 100
    draw.line([(kenar_bosluk, alt_y), (GENISLIK - kenar_bosluk, alt_y)], fill=RENK_CIZGI_KOYU, width=1)
    draw.text((kenar_bosluk, alt_y + 25), "EDM YAPI & GAYRİMENKUL // ARAŞTIRMA", font=_font_yukle(FONT_MONO, 20), fill=RENK_KURSUN)
    draw.text((GENISLIK - kenar_bosluk - 210, alt_y + 25), "01 / 03 > Kaydırın", font=_font_yukle(FONT_MONO_BOLD, 20), fill=RENK_KIRMIZI)

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/haber_kapak_{os.getpid()}.jpg")
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    img.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


def haber_slayti_2_ciz(
    manset: str,
    maddeler: List[str],
    cikti_yolu: Optional[Path] = None,
) -> Path:
    """Haberin 2. slaytı (Analiz & 3 Hap Madde): Rölöve pafta dilinde analiz."""
    img = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_MUREKKEP)
    draw = ImageDraw.Draw(img)

    kenar_bosluk = 70
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)

    # 1. Üst Bar
    _rozet_ciz(draw, kenar_bosluk, 55, "PİYASA ÇIKARIMLARI", bg_color=RENK_MUREKKEP_3, fg_color=RENK_KAGIT, font_boyut=20)
    if LOGO_YATAY_ACIK.exists():
        try:
            logo = Image.open(LOGO_YATAY_ACIK).convert("RGBA")
            lw = 200
            lh = int(logo.height * (lw / logo.width))
            logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)
            img.paste(logo, (GENISLIK - kenar_bosluk - lw, 52), logo)
        except Exception:
            pass

    draw.line([(kenar_bosluk, 110), (GENISLIK - kenar_bosluk, 110)], fill=RENK_CIZGI_KOYU, width=1)

    # 2. Bölüm Başlığı
    font_bb = _font_yukle(FONT_FRAUNCES, 44)
    draw.text((kenar_bosluk, 150), "Bölgeye Etkileri ve", font=font_bb, fill=RENK_KAGIT)
    draw.text((kenar_bosluk, 210), "Yatırımcı Notları", font=font_bb, fill=RENK_KIRMIZI)

    # 3. Maddeler
    my = 310
    font_no = _font_yukle(FONT_MONO_BOLD, 26)
    font_metin = _font_yukle(FONT_SANS, 28)

    for idx, madde in enumerate(maddeler[:3], start=1):
        numara_str = f"0{idx}"
        draw.text((kenar_bosluk, my), numara_str, font=font_no, fill=RENK_KIRMIZI)

        satirlar = _metin_sar(madde, font_metin, kullanilabilir_w - 70, draw)
        sy = my - 2
        for s in satirlar:
            draw.text((kenar_bosluk + 70, sy), s, font=font_metin, fill=RENK_KAGIT)
            sy += 42

        # Ayırıcı çizgi
        draw.line([(kenar_bosluk, sy + 30), (GENISLIK - kenar_bosluk, sy + 30)], fill=RENK_CIZGI_KOYU, width=1)
        my = sy + 65

    # 4. Alt Şerit
    alt_y = YUKSEKLIK - 100
    draw.line([(kenar_bosluk, alt_y), (GENISLIK - kenar_bosluk, alt_y)], fill=RENK_CIZGI_KOYU, width=1)
    draw.text((kenar_bosluk, alt_y + 25), "EDM YAPI & GAYRİMENKUL // ANALİZ", font=_font_yukle(FONT_MONO, 20), fill=RENK_KURSUN)
    draw.text((GENISLIK - kenar_bosluk - 210, alt_y + 25), "02 / 03 > Kaydırın", font=_font_yukle(FONT_MONO_BOLD, 20), fill=RENK_KIRMIZI)

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/haber_analiz_{os.getpid()}.jpg")
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    img.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu


def haber_kapanis_slayti_ciz(
    cikti_yolu: Optional[Path] = None,
) -> Path:
    """Haberin 3. slaytı (Kapanış & Kurumsal Çağrı): Sıcak pafta kağıdı, güçlü CTA."""
    img = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_KAGIT)
    draw = ImageDraw.Draw(img)

    kenar_bosluk = 80
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)

    draw.line([(kenar_bosluk, 90), (GENISLIK - kenar_bosluk, 90)], fill=RENK_CIZGI, width=1)
    draw.text((kenar_bosluk, 55), "EDM YAPI & GAYRİMENKUL // DANIŞMANLIK", font=_font_yukle(FONT_MONO, 22), fill=RENK_KURSUN)

    font_baslik = _font_yukle(FONT_FRAUNCES, 58)
    draw.text((kenar_bosluk, 220), "Doğru zamanda,", font=font_baslik, fill=RENK_MUREKKEP)
    draw.text((kenar_bosluk, 295), "doğru gayrimenkul.", font=font_baslik, fill=RENK_KIRMIZI)

    font_aciklama = _font_yukle(FONT_SANS, 28)
    aciklama_metni = (
        "Silivri ve çevre bölgelerdeki arsa, konut ve ticari yatırım fırsatları\n"
        "hakkında uzman görüşü almak için bizimle iletişime geçebilirsiniz."
    )
    draw.text((kenar_bosluk, 400), aciklama_metni, font=font_aciklama, fill=RENK_MUREKKEP)

    # İletişim Kutusu
    kutu_y = 540
    draw.rectangle([(kenar_bosluk, kutu_y), (GENISLIK - kenar_bosluk, kutu_y + 360)], fill=RENK_BEYAZ, outline=RENK_CIZGI)
    draw.rectangle([(kenar_bosluk, kutu_y), (kenar_bosluk + 8, kutu_y + 360)], fill=RENK_KIRMIZI)

    draw.text((kenar_bosluk + 45, kutu_y + 40), "SİLİVRİ BÖLGE UZMANLIĞI", font=_font_yukle(FONT_MONO_BOLD, 22), fill=RENK_KIRMIZI)
    draw.text((kenar_bosluk + 45, kutu_y + 85), "EDM Danışmanlık Hattı", font=_font_yukle(FONT_FRAUNCES, 44), fill=RENK_MUREKKEP)
    draw.text((kenar_bosluk + 45, kutu_y + 160), "0536 343 41 97", font=_font_yukle(FONT_MONO_BOLD, 40), fill=RENK_MUREKKEP)

    draw.line([(kenar_bosluk + 45, kutu_y + 235), (GENISLIK - kenar_bosluk - 45, kutu_y + 235)], fill=RENK_CIZGI, width=1)
    draw.text((kenar_bosluk + 45, kutu_y + 260), "Alibey Mah. Albay Yunus Dirik Cad. No: 58/A, Silivri", font=_font_yukle(FONT_SANS, 24), fill=RENK_KURSUN)
    draw.text((kenar_bosluk + 45, kutu_y + 300), "edmyapigayrimenkul.com", font=_font_yukle(FONT_SANS, 24), fill=RENK_KIRMIZI)

    # Alt Logo
    if LOGO_YATAY.exists():
        try:
            logo = Image.open(LOGO_YATAY).convert("RGBA")
            lw = 380
            lh = int(logo.height * (lw / logo.width))
            logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)
            img.paste(logo, (kenar_bosluk, YUKSEKLIK - 240), logo)
        except Exception:
            pass

    draw.text((kenar_bosluk, YUKSEKLIK - 90), "EDM YAPI & GAYRİMENKUL · YATIRIM ORTAĞINIZ", font=_font_yukle(FONT_MONO, 20), fill=RENK_KURSUN)

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/haber_kapanis_{os.getpid()}.jpg")
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    img.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu
