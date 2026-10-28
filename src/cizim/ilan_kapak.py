"""
src/cizim/ilan_kapak.py — İlan Kapak (Hero) ve Kapanış (İletişim) Slaytları
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image, ImageDraw, ImageOps

from .. import config
from .sabitler import (
    FONT_FRAUNCES,
    FONT_MONO,
    FONT_MONO_BOLD,
    FONT_SANS,
    FONT_SANS_BOLD,
    GENISLIK,
    LOGO_YATAY,
    LOGO_YATAY_ACIK,
    RENK_BEYAZ,
    RENK_CIZGI,
    RENK_CIZGI_KOYU,
    RENK_KAGIT,
    RENK_KIRMIZI,
    RENK_KURSUN,
    RENK_MUREKKEP,
    RENK_MUREKKEP_2,
    YUKSEKLIK,
)
from .fontlar import _font_yukle
from .tipografi import _gorsel_girdisi, _metin_sar
from .stok import _foto_indir_veya_ac
from .bilesenler import _arti_isareti_ciz, _rozet_ciz

log = logging.getLogger(__name__)


@_gorsel_girdisi
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
        draw.rectangle([(0, 0), (GENISLIK, 920)], fill=RENK_MUREKKEP_2)

    # 2. Üst Bar: Sol üst rozet, sağ üst EDM Açık Logo
    kenar_bosluk = 65
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)

    islem_degeri = str(ilan.get("islem") or "satilik").lower()
    islem = {
        "satilik": "SATILIK",
        "kiralik": "KİRALIK",
        "gunluk-kiralik": "GÜNLÜK KİRALIK",
        "sezonluk-kiralik": "SEZONLUK KİRALIK",
        "devren-satilik": "DEVREN SATILIK",
        "devren-kiralik": "DEVREN KİRALIK",
    }.get(islem_degeri, islem_degeri.replace("-", " ").upper())
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
        except Exception as e:
            log.warning("logo (açık) yüklenemedi, slayt onsuz üretiliyor: %s", e)

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
    fiyat_ham = float(ilan.get("fiyat") or 0)
    para_simgesi = {"TRY": "₺", "USD": "$", "EUR": "€", "GBP": "£"}.get(
        str(ilan.get("para_birimi") or "TRY").upper(),
        str(ilan.get("para_birimi") or "TRY"),
    )
    donem = (
        " / Gün" if islem_degeri == "gunluk-kiralik"
        else " / Sezon" if islem_degeri == "sezonluk-kiralik"
        else " / Ay" if islem_degeri == "kiralik"
        else ""
    )
    fiyat_metni = f"{int(fiyat_ham):,} {para_simgesi}{donem}".replace(",", ".")

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


@_gorsel_girdisi
def ilan_kapanis_slayti_ciz(ilan: Dict[str, Any], cikti_yolu: Optional[Path] = None) -> Path:
    """İlanın 3. slaytı (Yatırım Danışmanı & İletişim Kartı): Sıcak kağıt, güven veren kurumsal kimlik."""
    img = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_KAGIT)
    draw = ImageDraw.Draw(img)

    kenar_bosluk = 80

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

    font_tel = _font_yukle(FONT_SANS_BOLD, 40)
    draw.text((kenar_bosluk + 45, kutu_y + 170), "0212 727 29 55", font=font_tel, fill=RENK_MUREKKEP)

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
        except Exception as e:
            log.warning("logo (koyu) yüklenemedi, slayt onsuz üretiliyor: %s", e)

    font_slogan = _font_yukle(FONT_MONO, 20)
    draw.text((kenar_bosluk, YUKSEKLIK - 90), "EDM YAPI & GAYRİMENKUL · YATIRIM ORTAĞINIZ", font=font_slogan, fill=RENK_KURSUN)

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/ilan_kapanis_{ilan.get('id')}.jpg")
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    img.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu
