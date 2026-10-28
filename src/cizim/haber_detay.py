"""
src/cizim/haber_detay.py — DailyBrief Haber Detay Slaytı Çizimi
"""

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .. import config
from .sabitler import (
    FONT_MONO,
    FONT_MONO_BOLD,
    FONT_SANS,
    FONT_SANS_BOLD,
    GENISLIK,
    RENK_BEYAZ,
    RENK_CIZGI_KOYU,
    RENK_KURSUN,
    RENK_KURSUN_ACIK,
    RENK_METIN_GOVDE,
    RENK_MUREKKEP,
    RENK_UZMAN_CUBUK,
    RENK_UZMAN_ETIKET,
    YUKSEKLIK,
)
from .hatalar import TasmaHatasi
from .fontlar import _font_yukle
from .tipografi import (
    _etiketi_sigdir,
    _gorsel_girdisi,
    _kaynak_etiketi,
    _metin_sar,
    _temizle_tipografi,
)
from .tuval import _zemin_uret, tuval
from .bilesenler import _filigran_uygula, _logo_yerlestir

log = logging.getLogger(__name__)


@_gorsel_girdisi
def haber_dailybrief_detay_slayti_ciz(
    haber: Dict[str, Any],
    foto_yolu: Optional[Path | str] = None,
    cikti_yolu: Optional[Path] = None,
    olcu: str = "besleme",
    sayfa_no: str = "02 / 02",
    maddeler: Optional[List[Dict[str, Any]]] = None,
    ust_etiket: Optional[str] = None,
    goster_uzman_notu: bool = True,
    asgari_punto: int = 28,
) -> Path:
    """DailyBrief Haber Detay Slaytı (Ayrıntılar & EDM Uzman Analizi)."""
    from .haber_akis import haber_detay_maddelerini_ayikla

    uzman_notu = (haber.get("uzman_notu") or haber.get("cikarilacak_ders") or haber.get("stratejist_notu") or "").strip()
    if not uzman_notu and isinstance(haber.get("slayt_4_cta"), dict):
        uzman_notu = str(haber["slayt_4_cta"].get("aciklama", "")).strip()
    if uzman_notu:
        uzman_notu = re.sub(r"^(?:EDM\s+)?(?:Uzman\s+)?(?:Değerlendirmesi|Analizi|Notu|Stratejisi)\s*:\s*", "", uzman_notu, flags=re.IGNORECASE).strip()
    if not uzman_notu:
        goster_uzman_notu = False

    with tuval(olcu):
        genislik = GENISLIK
        yukseklik = YUKSEKLIK
        kenar = 70
        kullanilabilir_w = genislik - (2 * kenar)

        dikey_story = yukseklik >= 1700
        if dikey_story:
            ust_y = 300
            alt_y = yukseklik - 350
        else:
            ust_y = 62
            alt_y = 1250

        if cikti_yolu is None:
            cikti_yolu = config.yol_al(f"data/output/haber_dailybrief_detay_{os.getpid()}_{int(time.time())}.jpg")
        else:
            cikti_yolu = Path(cikti_yolu)
        cikti_yolu.parent.mkdir(parents=True, exist_ok=True)

        bg_img: Optional[Image.Image] = None
        if foto_yolu:
            fp = Path(foto_yolu)
            if fp.exists() and fp.is_file():
                try:
                    bg_img = ImageOps.exif_transpose(Image.open(fp)).convert("RGB")
                except Exception as fe:
                    log.warning("Detay slaytı arka plan fotoğrafı açılamadı: %s", fe)

        if bg_img:
            bg_w, bg_h = bg_img.size
            oran = max(genislik / bg_w, yukseklik / bg_h)
            yeni_w = int(bg_w * oran)
            yeni_h = int(bg_h * oran)
            bg_olcekli = bg_img.resize((yeni_w, yeni_h), Image.Resampling.LANCZOS)
            kirp_x = max(0, (yeni_w - genislik) // 2)
            kirp_y = max(0, (yeni_h - yukseklik) // 2)
            bg_kirp = bg_olcekli.crop((kirp_x, kirp_y, kirp_x + genislik, kirp_y + yukseklik))
            bg_kirp = bg_kirp.filter(ImageFilter.GaussianBlur(30))

            canvas = Image.new("RGB", (genislik, yukseklik), RENK_MUREKKEP)
            canvas.paste(bg_kirp, (0, 0))

            perde = Image.new("RGBA", (genislik, yukseklik), (10, 13, 19, 242))
            canvas = Image.alpha_composite(canvas.convert("RGBA"), perde).convert("RGB")
        else:
            canvas = _zemin_uret("murekkep", olcu=olcu)

        canvas = _filigran_uygula(canvas, acik_zemin=False)
        draw = ImageDraw.Draw(canvas)

        logo_w = 285
        logo_x = genislik - kenar - logo_w
        _logo_yerlestir(
            canvas,
            beyaz=True,
            x=logo_x,
            y=ust_y - 5,
            lw=logo_w,
            golge=True,
            kirmizi_zemin=False,
        )
        draw = ImageDraw.Draw(canvas)

        if not ust_etiket:
            ust_etiket = "// HABERİN AYRINTILARI"

        font_top_etiket = _font_yukle(FONT_MONO_BOLD, 21)

        temiz_maddeler = maddeler if maddeler is not None else haber_detay_maddelerini_ayikla(haber)

        n = len(temiz_maddeler)
        if dikey_story:
            bas_govde = (46 if n <= 1 else 42 if n == 2 else 38) if not goster_uzman_notu else (44 if n <= 1 else 40 if n == 2 else 36)
            uzman_bas = 40 if n <= 1 else (36 if n == 2 else 34)
            y_kursur = ust_y + 105
        else:
            bas_govde = (42 if n <= 1 else 38 if n == 2 else 34) if not goster_uzman_notu else (40 if n <= 1 else 36 if n == 2 else 32)
            uzman_bas = 38 if n <= 1 else (34 if n == 2 else 32)
            y_kursur = ust_y + 85
        yerlesim_bulundu = False
        for govde_p in range(bas_govde, min(asgari_punto, bas_govde) - 1, -2):
            etiket_p = govde_p + 6
            font_madde_etiket = _font_yukle(FONT_SANS_BOLD, etiket_p)
            font_madde_govde = _font_yukle(FONT_SANS, govde_p)
            lh_govde = int(govde_p * (1.44 if dikey_story else 1.42))
            lh_etiket = int(etiket_p * 1.18)
            if goster_uzman_notu:
                uzman_p = min(uzman_bas, govde_p + 2)
                font_uzman_etiket = _font_yukle(FONT_MONO_BOLD, 24 if dikey_story else 22)
                font_uzman_govde = _font_yukle(FONT_SANS_BOLD, uzman_p)
                uzman_lh = int(uzman_p * (1.42 if dikey_story else 1.4))
                pad_y = 30 if dikey_story else 24
                uzman_satirlari = _metin_sar(_temizle_tipografi(uzman_notu), font_uzman_govde, kullanilabilir_w - 60, draw)
                uzman_kart_h = pad_y + (30 if dikey_story else 26) + 14 + (len(uzman_satirlari) * uzman_lh) + pad_y
                uzman_kart_y = alt_y - (35 if dikey_story else 25) - uzman_kart_h
                kalan_h = (uzman_kart_y - (38 if dikey_story else 30)) - y_kursur
            else:
                uzman_kart_h = 0
                uzman_kart_y = alt_y - (35 if dikey_story else 25)
                kalan_h = (alt_y - (35 if dikey_story else 25)) - y_kursur

            maddeler_olculu = []
            for m in temiz_maddeler:
                etiket_satirlari = _metin_sar(_temizle_tipografi(m["etiket"]), font_madde_etiket, kullanilabilir_w - 38, draw)
                satirlar_m = _metin_sar(_temizle_tipografi(m["metin"]), font_madde_govde, kullanilabilir_w - 38, draw)
                h_etiket = len(etiket_satirlari) * lh_etiket
                maddeler_olculu.append({
                    "etiket_satirlari": etiket_satirlari,
                    "satirlar": satirlar_m,
                    "renk": m["renk"],
                    "h_etiket": h_etiket,
                    "h": h_etiket + (16 if dikey_story else 14) + (len(satirlar_m) * lh_govde),
                })
            if sum(mo["h"] for mo in maddeler_olculu) + (45 if dikey_story else 35) * max(0, n - 1) <= kalan_h:
                yerlesim_bulundu = True
                break
        if not yerlesim_bulundu:
            raise TasmaHatasi(f"Haber detay slaytına sığmadı ({n} madde)")

        draw.text((kenar, ust_y + 12), ust_etiket, font=font_top_etiket, fill=RENK_KURSUN_ACIK)
        draw.line([(kenar, ust_y + 60), (genislik - kenar, ust_y + 60)], fill=RENK_CIZGI_KOYU, width=1)

        madde_sayisi = max(1, n)
        toplam_madde_h = sum(mo["h"] for mo in maddeler_olculu)
        bosluk = (kalan_h - toplam_madde_h) // max(1, len(maddeler_olculu) - 1)
        max_bosluk = (140 if not goster_uzman_notu else 100) if dikey_story else (90 if not goster_uzman_notu else 75)
        min_bosluk = 45 if dikey_story else 35
        bosluk = max(min_bosluk, min(max_bosluk, bosluk))

        toplam_blok_h = toplam_madde_h + (bosluk * max(0, madde_sayisi - 1))
        curr_m_y = y_kursur + max(0, (kalan_h - toplam_blok_h) // 2)

        notch_w = (12 if dikey_story else 10) if (not goster_uzman_notu or len(temiz_maddeler) <= 1) else (10 if dikey_story else 8)
        notch_pad = 36 if dikey_story else (32 if notch_w >= 10 else 28)
        for mo in maddeler_olculu:
            m_h = mo["h"]
            draw.rounded_rectangle([kenar, curr_m_y + 3, kenar + notch_w, curr_m_y + m_h - 4], radius=4, fill=mo["renk"])
            ey = curr_m_y
            for es in mo["etiket_satirlari"]:
                draw.text((kenar + notch_pad, ey), es, font=font_madde_etiket, fill=mo["renk"])
                ey += lh_etiket

            gy = curr_m_y + mo["h_etiket"] + 12
            for s in mo["satirlar"]:
                draw.text((kenar + notch_pad, gy), s, font=font_madde_govde, fill=RENK_METIN_GOVDE)
                gy += lh_govde

            curr_m_y += m_h + bosluk

        if goster_uzman_notu:
            draw.rounded_rectangle([(kenar, uzman_kart_y), (genislik - kenar, uzman_kart_y + uzman_kart_h)], radius=14, fill=(20, 24, 34), outline=(55, 65, 85), width=1)
            draw.rounded_rectangle([(kenar, uzman_kart_y), (kenar + 8, uzman_kart_y + uzman_kart_h)], radius=3, fill=RENK_UZMAN_CUBUK)
            draw.text((kenar + 28, uzman_kart_y + pad_y), "// EDM DEĞERLENDİRMESİ:", font=font_uzman_etiket, fill=RENK_UZMAN_ETIKET)

            uy = uzman_kart_y + pad_y + 26 + 14
            for s in uzman_satirlari:
                draw.text((kenar + 28, uy), s, font=font_uzman_govde, fill=RENK_BEYAZ)
                uy += uzman_lh

        draw.line([(kenar, alt_y), (genislik - kenar, alt_y)], fill=RENK_CIZGI_KOYU, width=1)

        font_alt = _font_yukle(FONT_MONO, 17)
        bbox_s = draw.textbbox((0, 0), sayfa_no, font=font_alt)
        s_w = bbox_s[2] - bbox_s[0]
        kaynak_txt = _etiketi_sigdir(_kaynak_etiketi(haber), font_alt, genislik - 2 * kenar - s_w - 30, draw)
        draw.text((kenar, alt_y + 20), kaynak_txt, font=font_alt, fill=RENK_KURSUN)
        draw.text((genislik - kenar - s_w, alt_y + 20), sayfa_no, font=font_alt, fill=RENK_KURSUN_ACIK if "›" in sayfa_no else RENK_KURSUN)

        canvas.save(cikti_yolu, "JPEG", quality=95)
        log.info("DailyBrief haber detay slaytı üretildi: %s (%dx%d, olcu=%s)", cikti_yolu.name, genislik, yukseklik, olcu)
        return cikti_yolu
