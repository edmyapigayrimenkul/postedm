"""
src/cizim/otorite_kapanis.py — Otorite 4. Slaytı (Lüks Executive VIP Danışmanlık Kartı)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw

from .. import config
from .sabitler import (
    FONT_FRAUNCES,
    FONT_MONO,
    FONT_MONO_BOLD,
    FONT_SANS_BOLD,
    FONT_SANS_MEDIUM,
    FONT_SANS_SEMIBOLD,
    GENISLIK,
    RENK_BEYAZ,
    RENK_CIZGI_KOYU,
    RENK_KIRMIZI,
    RENK_KIRMIZI_CANLI,
    RENK_KURSUN,
    RENK_METIN_GOVDE,
    YUKSEKLIK,
)
from .fontlar import _font_yukle
from .tipografi import _gorsel_girdisi, _metin_sar
from .bilesenler import _difuzyon_golgeli_metin, _logo_yerlestir, _rozet_ciz
from .ikonlar import _edm_pin_al, _vektor_ikon_uret
from .stok import _temiz_arkaplan_al

log = logging.getLogger(__name__)


@_gorsel_girdisi
def otorite_slayt_4_kapanis(veri: Dict[str, Any], cikti_yolu: Optional[Path] = None) -> Path:
    """Otorite 4. Slaytı (Lüks ve Sade Executive VIP Danışmanlık Kartı)."""
    kenar_bosluk = 70
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)

    canvas = _temiz_arkaplan_al("DANISMANLIK")
    perde = Image.new("RGBA", (GENISLIK, YUKSEKLIK), (0, 0, 0, 0))
    p_draw = ImageDraw.Draw(perde)

    for y in range(250):
        alfa = int(160 * ((250 - y) / 250) ** 1.5)
        p_draw.line([(0, y), (GENISLIK, y)], fill=(8, 10, 14, alfa))

    for y in range(220, YUKSEKLIK):
        if y < 460:
            alfa = int(250 * ((y - 220) / 240) ** 1.2)
        else:
            alfa = 252
        p_draw.line([(0, y), (GENISLIK, y)], fill=(12, 14, 20, min(alfa, 255)))

    c_rgba = canvas.convert("RGBA")
    c_rgba.paste(perde, (0, 0), perde)
    canvas = c_rgba.convert("RGB")
    draw = ImageDraw.Draw(canvas)

    cta_veri = veri.get("slayt_4_cta") or {}

    _rozet_ciz(draw, kenar_bosluk, 60, "EDM DANIŞMANLIK // ÇÖZÜM ORTAĞINIZ", bg_color=RENK_KIRMIZI, fg_color=RENK_BEYAZ)
    _logo_yerlestir(canvas, beyaz=True, y=55, lw=285, golge=True)
    draw.line([(kenar_bosluk, 108), (GENISLIK - kenar_bosluk, 108)], fill=RENK_CIZGI_KOYU, width=1)

    slogan_1 = cta_veri.get("slogan_parca_1") or "Gayrimenkul Kararlarınızı"
    slogan_2 = cta_veri.get("slogan_vurgu") or "BİLGİ VE GÜVENE DAYANDIRIN."

    dummy_img = Image.new("RGB", (10, 10))
    dummy_draw = ImageDraw.Draw(dummy_img)
    f_slogan = _font_yukle(FONT_FRAUNCES, 48)

    s1_satirlar = _metin_sar(slogan_1, f_slogan, kullanilabilir_w, dummy_draw)
    s2_satirlar = _metin_sar(slogan_2, f_slogan, kullanilabilir_w, dummy_draw)

    slogan_satirlari: List[Tuple[str, Tuple[int, int, int]]] = (
        [(s, RENK_BEYAZ) for s in s1_satirlar] + [(s, RENK_KIRMIZI_CANLI) for s in s2_satirlar]
    )
    curr_sy = _difuzyon_golgeli_metin(canvas, slogan_satirlari, kenar_bosluk, 138, f_slogan, satir_araligi=62)

    draw = ImageDraw.Draw(canvas)
    aciklama = cta_veri.get("aciklama") or (
        "Silivri ve Trakya genelinde mülk alım, satım, tapu ve değerleme süreçlerinizde yanınızdayız."
    )
    ay = curr_sy + 14
    font_aciklama = _font_yukle(FONT_SANS_MEDIUM, 26)
    for s in _metin_sar(aciklama, font_aciklama, kullanilabilir_w, draw)[:2]:
        draw.text((kenar_bosluk, ay), s, font=font_aciklama, fill=RENK_METIN_GOVDE)
        ay += 38

    kutu_y = max(330, ay + 22)
    k_h = 750
    card_img = Image.new("RGBA", (kullanilabilir_w, k_h), (18, 22, 32, 248))
    card_draw = ImageDraw.Draw(card_img)
    card_draw.rounded_rectangle([(0, 0), (kullanilabilir_w - 1, k_h - 1)], radius=16, outline=(65, 75, 100, 255), width=1)
    card_draw.rounded_rectangle([(0, 0), (7, k_h - 1)], radius=4, fill=(*RENK_KIRMIZI_CANLI, 255))

    _rozet_ciz(
        card_draw,
        36,
        28,
        "DOĞRUDAN DANIŞMANLIK HATTI  //  7/24 BİLGİ",
        bg_color=(38, 20, 26),
        fg_color=RENK_BEYAZ,
        border_color=(*RENK_KIRMIZI_CANLI, 255),
        font_boyut=16,
    )

    p_cx, p_cy = 76, 126
    card_draw.ellipse([(p_cx - 34, p_cy - 34), (p_cx + 34, p_cy + 34)], fill=(32, 38, 52, 255), outline=(*RENK_KIRMIZI_CANLI, 200), width=1)
    p_icon = _vektor_ikon_uret("phone", 36, (255, 255, 255))
    card_img.paste(p_icon, (p_cx - 18, p_cy - 18), p_icon)

    card_draw.text((128, 96), "0212 727 29 55", font=_font_yukle(FONT_SANS_BOLD, 52), fill=RENK_BEYAZ)
    card_draw.text((128, 156), "Ön görüşme ve ücretsiz değerleme analizi için doğrudan arayabilirsiniz.", font=_font_yukle(FONT_SANS_MEDIUM, 23), fill=RENK_KURSUN)

    card_draw.line([(36, 212), (kullanilabilir_w - 36, 212)], fill=(45, 52, 70, 255), width=1)

    pin_img = _edm_pin_al(34)
    card_img.paste(pin_img, (36, 238), pin_img)
    card_draw.text((78, 236), "SİLİVRİ MERKEZ OFİS", font=_font_yukle(FONT_MONO_BOLD, 17), fill=RENK_KIRMIZI_CANLI)
    card_draw.text((36, 280), "Albay Yunus Dirik Cad. No: 58/A", font=_font_yukle(FONT_SANS_SEMIBOLD, 24), fill=RENK_BEYAZ)
    card_draw.text((36, 314), "Alibey Mah. Kılıç Apt., Silivri / İstanbul", font=_font_yukle(FONT_SANS_MEDIUM, 22), fill=RENK_KURSUN)

    _rozet_ciz(
        card_draw,
        36,
        364,
        "OFİS DAVETİ  //  HAFTANIN 7 GÜNÜ KAHVEYE BEKLERİZ",
        bg_color=(28, 32, 44),
        fg_color=RENK_BEYAZ,
        border_color=(60, 70, 90),
        font_boyut=15,
    )
    card_draw.text((36, 412), "Gayrimenkul kararlarınızı ofisimizde değerlendirin.", font=_font_yukle(FONT_SANS_MEDIUM, 21), fill=RENK_KURSUN)

    card_draw.line([(480, 230), (480, 480)], fill=(45, 52, 70, 255), width=1)

    w_icon = _vektor_ikon_uret("web", 28, (255, 255, 255))
    card_img.paste(w_icon, (516, 238), w_icon)
    card_draw.text((554, 236), "RESMİ WEB PLATFORMU", font=_font_yukle(FONT_MONO_BOLD, 16), fill=RENK_KIRMIZI_CANLI)
    card_draw.text((554, 262), "edmyapigayrimenkul.com", font=_font_yukle(FONT_SANS_SEMIBOLD, 23), fill=RENK_BEYAZ)

    m_icon = _vektor_ikon_uret("mail", 28, (255, 255, 255))
    card_img.paste(m_icon, (516, 318), m_icon)
    card_draw.text((554, 316), "KURUMSAL E-POSTA", font=_font_yukle(FONT_MONO_BOLD, 16), fill=RENK_KIRMIZI_CANLI)
    card_draw.text((554, 342), "info@edmyapigayrimenkul.com", font=_font_yukle(FONT_SANS_SEMIBOLD, 22), fill=RENK_BEYAZ)

    card_draw.text((554, 404), "@edmyapigayrimenkul", font=_font_yukle(FONT_MONO_BOLD, 18), fill=RENK_BEYAZ)
    card_draw.text((554, 430), "Instagram · Threads · TikTok · YouTube", font=_font_yukle(FONT_MONO, 15), fill=(130, 140, 160))

    card_draw.line([(36, 505), (kullanilabilir_w - 36, 505)], fill=(45, 52, 70, 255), width=1)

    inner_box_y = 530
    inner_box_h = 185
    card_draw.rounded_rectangle([(36, inner_box_y), (kullanilabilir_w - 36, inner_box_y + inner_box_h)], radius=12, fill=(24, 28, 40, 255), outline=(55, 65, 85, 255))

    b_cx, b_cy = 76, inner_box_y + (inner_box_h // 2)
    card_draw.ellipse([(b_cx - 24, b_cy - 24), (b_cx + 24, b_cy + 24)], fill=(*RENK_KIRMIZI_CANLI, 255))
    b_icon = _vektor_ikon_uret("bookmark", 26, (255, 255, 255))
    card_img.paste(b_icon, (b_cx - 13, b_cy - 13), b_icon)

    tx = 118
    card_draw.text((tx, inner_box_y + 24), "HUKUKİ MEVZUAT VE GAYRİMENKUL ARŞİVİ", font=_font_yukle(FONT_MONO_BOLD, 18), fill=RENK_KIRMIZI_CANLI)
    card_draw.text((tx, inner_box_y + 56), "İhtiyaç anında hızlıca başvurmak için bu rehberi kaydedebilirsiniz.", font=_font_yukle(FONT_SANS_MEDIUM, 23), fill=RENK_BEYAZ)
    card_draw.text((tx, inner_box_y + 92), "Silivri ve Trakya genelinde 15 yılı aşkın saha uzmanlığı ve güvenli işlem garantisi.", font=_font_yukle(FONT_SANS_MEDIUM, 20), fill=RENK_KURSUN)
    card_draw.text((tx, inner_box_y + 128), "EDM YAPI & GAYRİMENKUL  //  YATIRIM ORTAĞINIZ", font=_font_yukle(FONT_MONO_BOLD, 16), fill=(*RENK_KIRMIZI_CANLI, 220))

    if (veri.get("kategori_kodu") or "") in ("TAPU_VE_HUKUK", "EV_SAHIBI_VE_KIRACI", "ARSA_IMAR_VE_TINY_HOUSE"):
        card_draw.text(
            (tx, inner_box_y + 158),
            "Bu içerik genel bilgilendirmedir; bağlayıcı hukuki görüş için avukatınıza danışın.",
            font=_font_yukle(FONT_SANS_MEDIUM, 17), fill=(126, 134, 152),
        )

    c_rgba = canvas.convert("RGBA")
    c_rgba.paste(card_img, (kenar_bosluk, kutu_y), card_img)
    canvas = c_rgba.convert("RGB")
    draw = ImageDraw.Draw(canvas)

    alt_y = YUKSEKLIK - 105
    draw.line([(kenar_bosluk, alt_y), (GENISLIK - kenar_bosluk, alt_y)], fill=RENK_CIZGI_KOYU, width=1)
    draw.text((kenar_bosluk, alt_y + 24), "EDM YAPI & GAYRİMENKUL // DANIŞMANLIK & İLETİŞİM", font=_font_yukle(FONT_MONO, 19), fill=RENK_KURSUN)
    toplam_slayt = veri.get("_toplam_slayt", 4)
    sayfa_etiketi = f"{str(toplam_slayt).zfill(2)} / {str(toplam_slayt).zfill(2)}  ›  İLETİŞİM"
    sw = draw.textbbox((0, 0), sayfa_etiketi, font=_font_yukle(FONT_MONO_BOLD, 17))[2]
    _rozet_ciz(draw, GENISLIK - kenar_bosluk - sw - 36, alt_y + 14, sayfa_etiketi, bg_color=RENK_KIRMIZI_CANLI, fg_color=RENK_BEYAZ, font_boyut=17)

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/otorite_04_kapanis_{os.getpid()}.jpg")
    else:
        cikti_yolu = Path(cikti_yolu)
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return cikti_yolu
