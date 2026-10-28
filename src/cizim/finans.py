"""
src/cizim/finans.py — Karşılaştırma ve Finansal Tablo Çizimi
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw

from .. import config
from .sabitler import (
    FONT_MONO,
    FONT_MONO_BOLD,
    FONT_SANS_BOLD,
    FONT_SANS_MEDIUM,
    GENISLIK,
    RENK_BEYAZ,
    RENK_CIZGI_KOYU,
    RENK_KIRMIZI,
    RENK_KIRMIZI_CANLI,
    RENK_KIRMIZI_DERIN,
    RENK_KURSUN,
    RENK_METIN_GOVDE,
    RENK_MUREKKEP,
    RENK_MUREKKEP_2,
    YUKSEKLIK,
)
from .hatalar import EksikIcerik, TasmaHatasi
from .fontlar import _font_yukle, _govde_sigdir
from .tipografi import _metin_sar
from .tuval import _rozet_kirp, _sayfa_etiketi, _yerlesim
from .bilesenler import _logo_yerlestir, _rozet_ciz
from .normalize import _metin

log = logging.getLogger(__name__)


def _finansal_tablo_ciz(veri: Dict[str, Any], cozum_veri: Dict[str, Any], cikti_yolu: Optional[Path]) -> Path:
    """Karşılaştırma tablosu (B2): iki kolon, satır satır aynı ölçüt."""
    kenar_bosluk = 70
    kullanilabilir_w = GENISLIK - (2 * kenar_bosluk)
    col_w = (kullanilabilir_w - 20) // 2
    hucre_w = col_w - 40

    def _ciftler(ham: Any) -> List[Tuple[str, str]]:
        sonuc = []
        for oge in ham if isinstance(ham, (list, tuple)) else []:
            if isinstance(oge, (list, tuple)) and len(oge) >= 2:
                sonuc.append((_metin(oge[0]), _metin(oge[1])))
            elif isinstance(oge, dict):
                sonuc.append((_metin(oge.get("olcut") or oge.get("baslik")), _metin(oge.get("deger") or oge.get("aciklama"))))
            elif oge is not None and _metin(oge):
                sonuc.append(("", _metin(oge)))
        return [(b, v) for b, v in sonuc if b or v]

    sol = _ciftler(cozum_veri.get("sol_kolon_veriler"))
    sag = _ciftler(cozum_veri.get("sag_kolon_veriler"))
    if not sol or not sag:
        raise EksikIcerik("Karşılaştırma tablosu: kolon verisi üretilmedi")
    not_metin = _metin(cozum_veri.get("stratejist_notu"))

    canvas = Image.new("RGB", (GENISLIK, YUKSEKLIK), RENK_MUREKKEP)
    draw = ImageDraw.Draw(canvas)

    yer = _yerlesim()
    kayma = yer["kronik_ust"] - 62
    _rozet_ciz(draw, kenar_bosluk, 60 + kayma, _rozet_kirp(veri.get("rozet_metni") or "KARŞILAŞTIRMA", 44), bg_color=RENK_KIRMIZI)
    _logo_yerlestir(canvas, beyaz=True, y=55 + kayma, lw=285)

    y = 135 + kayma
    for metin, renk in ((_metin(cozum_veri.get("baslik_ust")), RENK_BEYAZ),
                        (_metin(cozum_veri.get("baslik_vurgu")), RENK_KIRMIZI_CANLI)):
        if not metin:
            continue
        for punto in range(52, 35, -2):
            f = _font_yukle(FONT_SANS_BOLD, punto)
            if draw.textbbox((0, 0), metin, font=f)[2] <= kullanilabilir_w:
                break
        else:
            raise TasmaHatasi(f"Tablo başlığı sığmadı: {metin[:40]}")
        draw.text((kenar_bosluk, y), metin, font=f, fill=renk)
        y += 63
    alt_baslik = _metin(cozum_veri.get("alt_baslik"))
    if alt_baslik:
        ab_font, ab_satirlar = _govde_sigdir(alt_baslik, FONT_SANS_MEDIUM, 26, 22, kullanilabilir_w, 2, draw)
        if len(_metin_sar(alt_baslik, ab_font, kullanilabilir_w, draw)) > 2:
            raise TasmaHatasi("Tablo alt başlığı iki satırı aşıyor")
        y += 10
        for satir in ab_satirlar:
            draw.text((kenar_bosluk, y), satir, font=ab_font, fill=RENK_METIN_GOVDE)
            y += 34
    tablo_y = y + 20

    alt_y = yer["alt_bar"] - 5
    not_font = _font_yukle(FONT_SANS_MEDIUM, 26)
    not_satirlar = _metin_sar(not_metin, not_font, kullanilabilir_w - 60, draw) if not_metin else []
    not_h = (65 + len(not_satirlar) * 38 + 22) if not_satirlar else 0

    def olc(punto_deger: int):
        f_bas = _font_yukle(FONT_MONO, 18)
        f_val = _font_yukle(FONT_SANS_BOLD, punto_deger)
        satir_h_val = int(punto_deger * 1.3)
        satirlar = []
        for i in range(max(len(sol), len(sag))):
            hucreler = []
            for kolon in (sol, sag):
                bas, val = kolon[i] if i < len(kolon) else ("", "")
                b_sat = _metin_sar(bas, f_bas, hucre_w, draw) if bas else []
                v_sat = _metin_sar(val, f_val, hucre_w, draw) if val else []
                hucreler.append((b_sat, v_sat))
            yuk = max(len(b) * 24 + (4 if b else 0) + len(v) * satir_h_val for b, v in hucreler) + 26
            satirlar.append((hucreler, yuk))
        return f_bas, f_val, satir_h_val, satirlar

    tablo_alt_sinir = alt_y - 30 - (not_h + 30 if not_h else 0)
    for punto_deger in (25, 24, 23, 22):
        f_bas, f_val, satir_h_val, satirlar = olc(punto_deger)
        tablo_h = 80 + sum(yuk for _, yuk in satirlar)
        if tablo_y + tablo_h <= tablo_alt_sinir:
            break
    else:
        raise TasmaHatasi(f"Karşılaştırma tablosu sığmadı ({len(sol)} satır, not {len(not_metin)} karakter)")

    x_kolonlar = (kenar_bosluk, kenar_bosluk + col_w + 20)
    basliklar = (_rozet_kirp(cozum_veri.get("sol_kolon_baslik") or "", 30), _rozet_kirp(cozum_veri.get("sag_kolon_baslik") or "", 30))
    bas_renk = ((30, 35, 46), RENK_KIRMIZI_DERIN)
    for k, x in enumerate(x_kolonlar):
        draw.rounded_rectangle([(x, tablo_y), (x + col_w, tablo_y + tablo_h)], radius=10, fill=RENK_MUREKKEP_2, outline=RENK_CIZGI_KOYU)
        draw.rounded_rectangle([(x, tablo_y), (x + col_w, tablo_y + 60)], radius=10, fill=bas_renk[k])
        draw.text((x + 20, tablo_y + 18), basliklar[k], font=_font_yukle(FONT_MONO_BOLD, 18), fill=RENK_BEYAZ)

    ky = tablo_y + 80
    for sira, (hucreler, yuk) in enumerate(satirlar):
        for k, (b_sat, v_sat) in enumerate(hucreler):
            x = x_kolonlar[k] + 20
            yy = ky
            for s in b_sat:
                draw.text((x, yy), s, font=f_bas, fill=RENK_KURSUN)
                yy += 24
            yy += 4 if b_sat else 0
            for s in v_sat:
                draw.text((x, yy), s, font=f_val, fill=RENK_BEYAZ)
                yy += satir_h_val
            if sira < len(satirlar) - 1:
                draw.line([(x, ky + yuk - 12), (x_kolonlar[k] + col_w - 20, ky + yuk - 12)], fill=RENK_CIZGI_KOYU, width=1)
        ky += yuk

    if not_satirlar:
        sonuc_y = tablo_y + tablo_h + 30
        draw.rounded_rectangle([(kenar_bosluk, sonuc_y), (GENISLIK - kenar_bosluk, sonuc_y + not_h)], radius=10, fill=(24, 28, 40), outline=RENK_KIRMIZI_CANLI)
        draw.text((kenar_bosluk + 30, sonuc_y + 24), "STRATEJİST NOTU:", font=_font_yukle(FONT_MONO_BOLD, 19), fill=RENK_KIRMIZI_CANLI)
        for idx, s in enumerate(not_satirlar):
            draw.text((kenar_bosluk + 30, sonuc_y + 65 + (idx * 38)), s, font=not_font, fill=RENK_METIN_GOVDE)

    draw.line([(kenar_bosluk, alt_y), (GENISLIK - kenar_bosluk, alt_y)], fill=RENK_CIZGI_KOYU, width=1)
    draw.text((kenar_bosluk, alt_y + 24), "EDM YAPI & GAYRİMENKUL // KARŞILAŞTIRMA", font=_font_yukle(FONT_MONO, 19), fill=RENK_KURSUN)
    c_etiket = _sayfa_etiketi(veri, veri.get("_slayt_sirasi", 3))
    ce_w = draw.textbbox((0, 0), c_etiket, font=_font_yukle(FONT_MONO_BOLD, 17))[2]
    _rozet_ciz(draw, GENISLIK - kenar_bosluk - ce_w - 36, alt_y + 14, c_etiket, bg_color=RENK_KIRMIZI_CANLI, fg_color=RENK_BEYAZ, font_boyut=17)

    if cikti_yolu is None:
        cikti_yolu = config.yol_al(f"data/output/tablo_{os.getpid()}_{int(time.time())}.jpg")
    Path(cikti_yolu).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cikti_yolu, "JPEG", quality=95)
    return Path(cikti_yolu)
