#!/usr/bin/env python3
"""
scripts/kapanis_claude_deneme.py
Claude'un varyant_a tasarımına website ve kaydetme alanını ekleyen deneme betiği.
"""

from __future__ import annotations
import sys
from pathlib import Path
from PIL import Image, ImageDraw

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import make_image as mi
from scripts.kapanis_alternatif import ICERIK, _qr, _baslik_ciz

CIKTI = KOK / "data/output/kapanis_deneme"
CIKTI.mkdir(parents=True, exist_ok=True)

def olustur_varyasyon(ad: str, web_sirasi: int = 1, kaydet_stili: str = "yalin"):
    canvas, draw, p = mi._slayt_cercevesi("kagit", "EDM DANIŞMANLIK", "EDM YAPI & GAYRİMENKUL", "04 / 04")
    yer = mi._yerlesim()
    kenar = yer["kenar"]
    gen = mi.GENISLIK - 2 * kenar

    # 1. Başlık
    y = _baslik_ciz(draw, kenar, yer["ust"] + 24, gen, p, punto=56)
    y += 18

    # 2. Açıklama
    f_a, sat = mi._govde_sigdir(ICERIK["aciklama"], mi.FONT_SANS_MEDIUM, 30, 24, gen, 2, draw)
    for s_ in sat[:2]:
        draw.text((kenar, y), s_, font=f_a, fill=p["govde"])
        y += int(f_a.size * 1.36)

    # 3. Kaydetme Çizgisi
    y += 18
    kaydet_metin = "BU REHBERİ KAYDEDİN · İHTİYAÇ ANINDA ELİNİZİN ALTINDA OLSUN"
    if kaydet_stili == "yalin":
        try:
            ikon = mi._vektor_ikon_uret("bookmark", 20, p["vurgu"])
            canvas.paste(ikon, (kenar, y - 2), ikon)
        except Exception:
            pass
        draw.text((kenar + 28, y), kaydet_metin, font=mi._font_yukle(mi.FONT_MONO_BOLD, 15), fill=p["ana"])
        y += 24
    elif kaydet_stili == "rozet":
        pill_h = 36
        f_k = mi._font_yukle(mi.FONT_MONO_BOLD, 14)
        tw = draw.textbbox((0, 0), kaydet_metin, font=f_k)[2]
        pw = tw + 44
        draw.rounded_rectangle([(kenar, y), (kenar + pw, y + pill_h)], radius=6, fill=(242, 244, 242), outline=(222, 226, 222), width=1)
        try:
            ikon = mi._vektor_ikon_uret("bookmark", 16, p["vurgu"])
            canvas.paste(ikon, (kenar + 12, y + 10), ikon)
        except Exception:
            pass
        draw.text((kenar + 34, y + 9), kaydet_metin, font=f_k, fill=p["ana"])
        y += pill_h + 10

    # 4. İletişim Bloğu Ölçüleri
    blok_h = 296
    blok_y = yer["alt"] - 36 - blok_h

    # Orta kılcal ayraç çizgisi
    orta_cizgi_y = y + (blok_y - y) // 2
    draw.line([(kenar, orta_cizgi_y), (kenar + gen, orta_cizgi_y)], fill=p["cizgi"], width=1)

    by = blok_y
    draw.text((kenar, by), "DOĞRUDAN HAT", font=mi._font_yukle(mi.FONT_MONO_BOLD, 17), fill=p["vurgu"])
    by += 32
    draw.text((kenar, by), ICERIK["telefon"], font=mi._font_yukle(mi.FONT_MONO_BOLD, 54), fill=p["ana"])
    by += 82
    draw.text((kenar, by), f"{ICERIK['isim']}  ·  {ICERIK['unvan']}", font=mi._font_yukle(mi.FONT_SANS_SEMIBOLD, 24), fill=p["ana"])
    by += 40
    draw.text((kenar, by), ICERIK["adres"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 21), fill=p["govde"])
    by += 34

    if web_sirasi == 1:
        # e-posta üstte, web + sosyal medya altta
        draw.text((kenar, by), ICERIK["eposta"], font=mi._font_yukle(mi.FONT_MONO, 19), fill=p["silik"])
        by += 28
        draw.text((kenar, by), "edmyapigayrimenkul.com  ·  @edmyapigayrimenkul", font=mi._font_yukle(mi.FONT_MONO, 19), fill=p["silik"])
    elif web_sirasi == 2:
        # web + e-posta aynı satırda, sosyal medya altta
        draw.text((kenar, by), "edmyapigayrimenkul.com  ·  " + ICERIK["eposta"], font=mi._font_yukle(mi.FONT_MONO, 19), fill=p["silik"])
        by += 28
        draw.text((kenar, by), "@edmyapigayrimenkul", font=mi._font_yukle(mi.FONT_MONO, 19), fill=p["silik"])
    elif web_sirasi == 3:
        # web üstte, e-posta + sosyal medya altta
        draw.text((kenar, by), "edmyapigayrimenkul.com", font=mi._font_yukle(mi.FONT_MONO_BOLD, 19), fill=p["ana"])
        by += 28
        draw.text((kenar, by), f"{ICERIK['eposta']}  ·  @edmyapigayrimenkul", font=mi._font_yukle(mi.FONT_MONO, 19), fill=p["silik"])

    # QR Kod & KONUM
    qr = _qr(152)
    if qr:
        canvas.paste(qr, (mi.GENISLIK - kenar - 152, blok_y + 6))
        # Küçük konum rozeti
        kw_x = mi.GENISLIK - kenar - 152
        kw_y = blok_y + 166
        draw.rounded_rectangle([(kw_x, kw_y), (kw_x + 64, kw_y + 24)], radius=4, fill=(240, 242, 240))
        draw.text((kw_x + 9, kw_y + 5), "KONUM", font=mi._font_yukle(mi.FONT_MONO_BOLD, 12), fill=p["silik"])

    # Yasal uyarı (tampon güvenliği: yer['alt'] içinde)
    yasal_y = yer["alt"] - 14
    draw.text((kenar, yasal_y), ICERIK["yasal"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 16), fill=p["silik"])

    yol = CIKTI / f"{ad}.jpg"
    canvas.save(yol, "JPEG", quality=95)
    print("Üretildi:", yol)
    return yol

olustur_varyasyon("varyasyon_1_yalin_eposta_ustte", web_sirasi=1, kaydet_stili="yalin")
olustur_varyasyon("varyasyon_2_yalin_web_eposta_birlikte", web_sirasi=2, kaydet_stili="yalin")
olustur_varyasyon("varyasyon_3_yalin_web_bold_ustte", web_sirasi=3, kaydet_stili="yalin")
olustur_varyasyon("varyasyon_4_rozetli_kaydet", web_sirasi=1, kaydet_stili="rozet")
