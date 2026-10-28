"""
src/cizim/haber_kapak.py — Haber Kapak ve DailyBrief Kapak Slaytı Çizimleri
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw, ImageFilter

from .. import config
from .sabitler import (
    FONT_FRAUNCES,
    FONT_MONO,
    FONT_SANS,
    GENISLIK,
    RENK_BEYAZ,
    RENK_CIZGI_KOYU,
    RENK_KIRMIZI,
    RENK_KURSUN,
    RENK_KURSUN_ACIK,
    RENK_METIN_GOVDE,
    RENK_MUREKKEP,
    YUKSEKLIK,
)
from .fontlar import _font_yukle
from .tipografi import (
    _etiketi_sigdir,
    _gorsel_girdisi,
    _kaynak_etiketi,
    _metin_sar,
    _temizle_tipografi,
    tr_buyuk,
)
from .tuval import _zemin_uret, tuval
from .bilesenler import _filigran_uygula, _logo_yerlestir, _rozet_ciz
from .stok import _perde_maskesi_smoothstep
from .haber_arka_plan import _haber_arkaplan_hazirla

log = logging.getLogger(__name__)


@_gorsel_girdisi
def haber_dailybrief_slayti_ciz(
    haber: Dict[str, Any],
    foto_yolu: Optional[Path | str] = None,
    cikti_yolu: Optional[Path] = None,
    olcu: str = "besleme",
    sayfa_no: Optional[str] = None,
) -> Path:
    """Instabot (DailyBrief) mimarisi paritesi: Haber kartı üretir."""
    if isinstance(haber, dict):
        dm = haber.get("detay_metni")
        if dm and isinstance(dm, str) and dm.strip().startswith("{"):
            try:
                parsed = json.loads(dm)
                if isinstance(parsed, dict):
                    haber = {**parsed, **haber}
                    if parsed.get("kanca") and not haber.get("kanca"):
                        haber["kanca"] = parsed["kanca"]
            except Exception:
                pass

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
            cikti_yolu = config.yol_al(f"data/output/haber_dailybrief_{os.getpid()}_{int(time.time())}.jpg")
        else:
            cikti_yolu = Path(cikti_yolu)
        cikti_yolu.parent.mkdir(parents=True, exist_ok=True)

        bg_img = _haber_arkaplan_hazirla(haber, foto_yolu=foto_yolu, cikti_yolu=cikti_yolu)

        if bg_img:
            bg_w, bg_h = bg_img.size
            oran = max(genislik / bg_w, yukseklik / bg_h)
            yeni_w = int(bg_w * oran)
            yeni_h = int(bg_h * oran)
            bg_olcekli = bg_img.resize((yeni_w, yeni_h), Image.Resampling.LANCZOS)

            kirp_x = max(0, (yeni_w - genislik) // 2)
            kirp_y = max(0, (yeni_h - yukseklik) // 2)
            bg_kirp = bg_olcekli.crop((kirp_x, kirp_y, kirp_x + genislik, kirp_y + yukseklik))

            canvas = Image.new("RGB", (genislik, yukseklik), RENK_MUREKKEP)
            canvas.paste(bg_kirp, (0, 0))
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

        from ..yeni_formatlar import kategori_temizle
        kategori_adi = tr_buyuk(kategori_temizle(haber.get("kategori") or haber.get("kategori_kodu")))
        rozet_txt = f"EDM GÜNDEM // {kategori_adi}"
        azami_rozet_w = logo_x - kenar - 30
        _rozet_ciz(
            draw,
            kenar,
            ust_y,
            rozet_txt,
            bg_color=RENK_KIRMIZI,
            fg_color=RENK_BEYAZ,
            font_boyut=20,
            max_w=azami_rozet_w,
        )

        manset_raw = haber.get("manset") or haber.get("baslik") or "Gündem Özeti"
        spot_raw = haber.get("spot") or haber.get("ozet") or ""

        spot_temiz = _temizle_tipografi(spot_raw)
        punto_spot = 34 if dikey_story else 32
        font_spot = _font_yukle(FONT_SANS, punto_spot)
        spot_satirlari = _metin_sar(spot_temiz, font_spot, kullanilabilir_w, draw) if spot_temiz else []
        while len(spot_satirlari) > 4 and punto_spot > 24:
            punto_spot -= 2
            font_spot = _font_yukle(FONT_SANS, punto_spot)
            spot_satirlari = _metin_sar(spot_temiz, font_spot, kullanilabilir_w, draw)
        spot_satirlari = spot_satirlari[:4]
        spot_lh = int(punto_spot * (1.40 if dikey_story else 1.36))
        spot_h = len(spot_satirlari) * spot_lh

        manset_temiz = _temizle_tipografi(manset_raw)
        punto_manset = 74 if dikey_story else 68
        font_manset = _font_yukle(FONT_FRAUNCES, punto_manset)
        manset_satirlari = _metin_sar(manset_temiz, font_manset, kullanilabilir_w, draw)
        while len(manset_satirlari) > 3 and punto_manset > 46:
            punto_manset -= 2
            font_manset = _font_yukle(FONT_FRAUNCES, punto_manset)
            manset_satirlari = _metin_sar(manset_temiz, font_manset, kullanilabilir_w, draw)
        manset_satirlari = manset_satirlari[:3]

        manset_lh = int(punto_manset * (1.20 if dikey_story else 1.18))
        manset_h = len(manset_satirlari) * manset_lh

        spot_ust_y = alt_y - (34 if dikey_story else 28) - spot_h
        manset_ust_y = spot_ust_y - ((28 if dikey_story else 22) if spot_h > 0 else 0) - manset_h

        if bg_img:
            perde_bas = max(220 if dikey_story else 320, manset_ust_y - (160 if dikey_story else 130))
            perde_son = min(alt_y, manset_ust_y + int(manset_h * 0.80))
            maske = _perde_maskesi_smoothstep(genislik, yukseklik, perde_bas, perde_son)
            koyu_zemin = Image.new("RGB", (genislik, yukseklik), RENK_MUREKKEP)
            canvas = Image.composite(koyu_zemin, canvas, maske)

            top_vignette = Image.new("RGBA", (genislik, yukseklik), (0, 0, 0, 0))
            tv_draw = ImageDraw.Draw(top_vignette)
            vignette_son = ust_y + 110
            for vy in range(vignette_son):
                alfa = int(80 * ((vignette_son - vy) / vignette_son) ** 1.6)
                tv_draw.line([(0, vy), (genislik, vy)], fill=(10, 12, 16, alfa))
            canvas = Image.alpha_composite(canvas.convert("RGBA"), top_vignette).convert("RGB")
            draw = ImageDraw.Draw(canvas)

        try:
            from .. import hook_motoru
            canvas = hook_motoru.hook_uygula(
                canvas=canvas,
                haber=haber,
                manset_ust_y=manset_ust_y,
                ust_y=ust_y,
                olcu=olcu,
            )
            draw = ImageDraw.Draw(canvas)
        except Exception as he:
            log.warning("Hook çiziminde hata (devam ediliyor): %s", he)

        golge = Image.new("RGBA", (genislik, yukseklik), (0, 0, 0, 0))
        golge_draw = ImageDraw.Draw(golge)
        curr_y = manset_ust_y
        for sat in manset_satirlari:
            golge_draw.text((kenar, curr_y + 4), sat, font=font_manset, fill=(0, 0, 0, 240))
            curr_y += manset_lh
        golge = golge.filter(ImageFilter.GaussianBlur(14))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), golge).convert("RGB")
        draw = ImageDraw.Draw(canvas)

        curr_y = manset_ust_y
        for sat in manset_satirlari:
            draw.text((kenar, curr_y), sat, font=font_manset, fill=RENK_BEYAZ)
            curr_y += manset_lh

        curr_y = spot_ust_y
        for sat in spot_satirlari:
            draw.text((kenar, curr_y), sat, font=font_spot, fill=RENK_METIN_GOVDE)
            curr_y += spot_lh

        draw.line([(kenar, alt_y), (genislik - kenar, alt_y)], fill=RENK_CIZGI_KOYU, width=1)

        kaynak_txt = _kaynak_etiketi(haber)
        foto_atif = (haber.get("foto_atif") or "").strip()
        if foto_atif:
            kaynak_txt = f"{kaynak_txt}  ·  {tr_buyuk(foto_atif)}"
        font_alt = _font_yukle(FONT_MONO, 17)

        if sayfa_no:
            sag_txt = f"{sayfa_no}  ›  KAYDIRIN" if "01" in sayfa_no and olcu == "besleme" and "KAYDIRIN" not in sayfa_no else sayfa_no
        else:
            sag_txt = "@edmyapigayrimenkul · Yatırım Ortağınız"
        bbox_s = draw.textbbox((0, 0), sag_txt, font=font_alt)
        s_w = bbox_s[2] - bbox_s[0]

        kaynak_txt = _etiketi_sigdir(kaynak_txt, font_alt, genislik - (2 * kenar) - s_w - 30, draw)

        draw.text((kenar, alt_y + 20), kaynak_txt, font=font_alt, fill=RENK_KURSUN)
        draw.text((genislik - kenar - s_w, alt_y + 20), sag_txt, font=font_alt, fill=RENK_KURSUN_ACIK if "›" in sag_txt else RENK_KURSUN)

        canvas.save(cikti_yolu, "JPEG", quality=95)
        log.info("DailyBrief haber slaytı üretildi: %s (%dx%d, olcu=%s)", cikti_yolu.name, genislik, yukseklik, olcu)
        return cikti_yolu
