#!/usr/bin/env python3
"""
scripts/uret_10_kapanis.py
Claude editoryal çizgisinde 10 farklı kapanış slaytı varyasyonu üretir.
Tüm görseller doğrudan artifacts dizinine kaydedilir.
"""

from __future__ import annotations
import sys
from pathlib import Path
from PIL import Image, ImageDraw

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import make_image as mi, config

ARTIFACT_DIR = Path("/Users/macbook/.gemini/antigravity/brain/10849f7b-49c8-44a9-a6a4-91a15b9d0075/kapanis_tasarimlari")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

ICERIK = {
    "baslik_1": "Doğru adımlarla",
    "baslik_2": "GÜVENLİ KİRALAMA",
    "aciklama": "Silivri ve Trakya genelinde mülk yönetimi ve hukuki süreçlerinizde yanınızdayız.",
    "kaydet": "BU REHBERİ KAYDEDİN · İHTİYAÇ ANINDA ELİNİZİN ALTINDA OLSUN",
    "isim": "METİN ÖZDOĞAN",
    "unvan": "Kurucu Danışman",
    "telefon": "0536 343 41 97",
    "adres": "Alibey Mah. Albay Yunus Dirik Cad. No: 58/A · Silivri",
    "eposta": "info@edmyapigayrimenkul.com",
    "site": "edmyapigayrimenkul.com",
    "hesap": "@edmyapigayrimenkul",
    "yasal": "Bu içerik genel bilgilendirmedir; bağlayıcı hukuki görüş için avukatınıza danışın.",
    "rozet": "EDM DANIŞMANLIK",
}

QR_LINK = "https://maps.google.com/?q=Alibey+Mah+Albay+Yunus+Dirik+Cad+No+58A+Silivri"


def _qr(boyut: int, zemin: str = "#ffffff", muhur: str = "#121316") -> Image.Image:
    import qrcode
    q = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=4, border=1)
    q.add_data(QR_LINK)
    q.make(fit=True)
    g = q.make_image(fill_color=muhur, back_color=zemin).convert("RGB")
    return g.resize((boyut, boyut), Image.Resampling.LANCZOS)


def _ust_blok(canvas, draw, kenar, yer, gen, p, baslik_punto=56, aciklama_punto=30, genislik_kisit=None):
    w = genislik_kisit or gen
    f1, s1 = mi._govde_sigdir(ICERIK["baslik_1"], mi.FONT_FRAUNCES, baslik_punto, 34, w, 2, draw)
    f2, s2 = mi._govde_sigdir(ICERIK["baslik_2"], mi.FONT_FRAUNCES, baslik_punto, 34, w, 2, draw)
    f_baslik = f1 if f1.size <= f2.size else f2
    s1 = mi._metin_sar(ICERIK["baslik_1"], f_baslik, w, draw)[:2]
    s2 = mi._metin_sar(ICERIK["baslik_2"], f_baslik, w, draw)[:2]
    b_aralik = int(f_baslik.size * 1.18)

    y = yer["ust"] + 24
    for satir in s1:
        draw.text((kenar, y), satir, font=f_baslik, fill=p["ana"]); y += b_aralik
    for satir in s2:
        draw.text((kenar, y), satir, font=f_baslik, fill=p["vurgu"]); y += b_aralik

    y += 18
    f_a, sat = mi._govde_sigdir(ICERIK["aciklama"], mi.FONT_SANS_MEDIUM, aciklama_punto, 22, w, 2, draw)
    for s_ in sat[:2]:
        draw.text((kenar, y), s_, font=f_a, fill=p["govde"]); y += int(f_a.size * 1.36)

    y += 18
    try:
        ikon = mi._vektor_ikon_uret("bookmark", 20, p["vurgu"])
        canvas.paste(ikon, (kenar, y - 2), ikon)
    except Exception:
        pass
    draw.text((kenar + 28, y), ICERIK["kaydet"], font=mi._font_yukle(mi.FONT_MONO_BOLD, 15), fill=p["ana"])
    return y + 24


def _yasal_ciz(draw, kenar, yer, p, yasal_metin=None):
    metin = yasal_metin or ICERIK["yasal"]
    draw.text((kenar, yer["alt"] - 14), metin, font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 16), fill=p["silik"])


def _kaydet_resim(canvas, ad):
    yol = ARTIFACT_DIR / f"{ad}.jpg"
    canvas.save(yol, "JPEG", quality=95)
    print(f"✓ {ad}.jpg üretildi")
    return yol


# ─────────────────────────────────────────────────────────────────────────────
# 1. Klasik Editoryal (Mevcut Onaylanan Şablon)
# ─────────────────────────────────────────────────────────────────────────────
def t01_klasik_editoryal():
    canvas, draw, p = mi._slayt_cercevesi("kagit", ICERIK["rozet"], "EDM YAPI & GAYRİMENKUL", "04 / 04")
    yer = mi._yerlesim(); kenar = yer["kenar"]; gen = mi.GENISLIK - 2 * kenar
    y = _ust_blok(canvas, draw, kenar, yer, gen, p)

    blok_h = 296
    blok_y = yer["alt"] - 36 - blok_h
    orta_y = y + (blok_y - y) // 2
    draw.line([(kenar, orta_y), (kenar + gen, orta_y)], fill=p["cizgi"], width=1)

    by = blok_y
    draw.text((kenar, by), "DOĞRUDAN HAT", font=mi._font_yukle(mi.FONT_MONO_BOLD, 17), fill=p["vurgu"]); by += 32
    draw.text((kenar, by), ICERIK["telefon"], font=mi._font_yukle(mi.FONT_MONO_BOLD, 54), fill=p["ana"]); by += 82
    draw.text((kenar, by), f"{ICERIK['isim']}  ·  {ICERIK['unvan']}", font=mi._font_yukle(mi.FONT_SANS_SEMIBOLD, 24), fill=p["ana"]); by += 40
    draw.text((kenar, by), ICERIK["adres"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 21), fill=p["govde"]); by += 34
    draw.text((kenar, by), ICERIK["eposta"], font=mi._font_yukle(mi.FONT_MONO, 19), fill=p["silik"]); by += 28
    draw.text((kenar, by), f"{ICERIK['site']}  ·  {ICERIK['hesap']}", font=mi._font_yukle(mi.FONT_MONO, 19), fill=p["silik"])

    qr = _qr(152)
    canvas.paste(qr, (mi.GENISLIK - kenar - 152, blok_y + 6))
    kw_y = blok_y + 6 + 152 + 8
    draw.rounded_rectangle([(mi.GENISLIK - kenar - 152, kw_y), (mi.GENISLIK - kenar - 88, kw_y + 24)], radius=4, fill=(240, 242, 240))
    draw.text((mi.GENISLIK - kenar - 143, kw_y + 5), "KONUM", font=mi._font_yukle(mi.FONT_MONO_BOLD, 12), fill=p["silik"])

    _yasal_ciz(draw, kenar, yer, p)
    return _kaydet_resim(canvas, "01_klasik_editoryal")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Kırmızı Numara Vurgusu (Conversion Hero)
# ─────────────────────────────────────────────────────────────────────────────
def t02_kirmizi_numara():
    canvas, draw, p = mi._slayt_cercevesi("kagit", ICERIK["rozet"], "EDM YAPI & GAYRİMENKUL", "04 / 04")
    yer = mi._yerlesim(); kenar = yer["kenar"]; gen = mi.GENISLIK - 2 * kenar
    y = _ust_blok(canvas, draw, kenar, yer, gen, p)

    blok_h = 296
    blok_y = yer["alt"] - 36 - blok_h
    orta_y = y + (blok_y - y) // 2
    draw.line([(kenar, orta_y), (kenar + gen, orta_y)], fill=p["cizgi"], width=1)

    by = blok_y
    draw.text((kenar, by), "DOĞRUDAN HAT", font=mi._font_yukle(mi.FONT_MONO_BOLD, 17), fill=p["silik"]); by += 32
    # Telefon EDM kırmızısı ile parlıyor
    draw.text((kenar, by), ICERIK["telefon"], font=mi._font_yukle(mi.FONT_MONO_BOLD, 56), fill=p["vurgu"]); by += 82
    draw.text((kenar, by), f"{ICERIK['isim']}  ·  {ICERIK['unvan']}", font=mi._font_yukle(mi.FONT_SANS_SEMIBOLD, 24), fill=p["ana"]); by += 40
    draw.text((kenar, by), ICERIK["adres"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 21), fill=p["govde"]); by += 34
    draw.text((kenar, by), ICERIK["eposta"], font=mi._font_yukle(mi.FONT_MONO, 19), fill=p["silik"]); by += 28
    draw.text((kenar, by), f"{ICERIK['site']}  ·  {ICERIK['hesap']}", font=mi._font_yukle(mi.FONT_MONO, 19), fill=p["silik"])

    qr = _qr(152)
    canvas.paste(qr, (mi.GENISLIK - kenar - 152, blok_y + 6))
    kw_y = blok_y + 6 + 152 + 8
    draw.rounded_rectangle([(mi.GENISLIK - kenar - 152, kw_y), (mi.GENISLIK - kenar - 88, kw_y + 24)], radius=4, fill=(240, 242, 240))
    draw.text((mi.GENISLIK - kenar - 143, kw_y + 5), "KONUM", font=mi._font_yukle(mi.FONT_MONO_BOLD, 12), fill=p["silik"])

    _yasal_ciz(draw, kenar, yer, p)
    return _kaydet_resim(canvas, "02_kirmizi_numara_vurgusu")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Çift Kılcal Kural & Simetri (Double Hairline Masthead)
# ─────────────────────────────────────────────────────────────────────────────
def t03_cift_kilcal_kural():
    canvas, draw, p = mi._slayt_cercevesi("kagit", ICERIK["rozet"], "EDM YAPI & GAYRİMENKUL", "04 / 04")
    yer = mi._yerlesim(); kenar = yer["kenar"]; gen = mi.GENISLIK - 2 * kenar
    y = _ust_blok(canvas, draw, kenar, yer, gen, p)

    blok_h = 286
    blok_y = yer["alt"] - 46 - blok_h
    # 1. Kılcal çizgi: İletişim bloğunun hemen üstünde
    draw.line([(kenar, blok_y - 36), (kenar + gen, blok_y - 36)], fill=p["cizgi"], width=1)

    by = blok_y
    draw.text((kenar, by), "DOĞRUDAN HAT", font=mi._font_yukle(mi.FONT_MONO_BOLD, 17), fill=p["vurgu"]); by += 32
    draw.text((kenar, by), ICERIK["telefon"], font=mi._font_yukle(mi.FONT_MONO_BOLD, 54), fill=p["ana"]); by += 80
    draw.text((kenar, by), f"{ICERIK['isim']}  ·  {ICERIK['unvan']}", font=mi._font_yukle(mi.FONT_SANS_SEMIBOLD, 24), fill=p["ana"]); by += 38
    draw.text((kenar, by), ICERIK["adres"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 21), fill=p["govde"]); by += 32
    draw.text((kenar, by), f"{ICERIK['site']}  ·  {ICERIK['eposta']}", font=mi._font_yukle(mi.FONT_MONO, 19), fill=p["silik"]); by += 28
    draw.text((kenar, by), f"Instagram: {ICERIK['hesap']}", font=mi._font_yukle(mi.FONT_MONO, 18), fill=p["silik"])

    qr = _qr(156)
    canvas.paste(qr, (mi.GENISLIK - kenar - 156, blok_y + 4))
    kw_y = blok_y + 4 + 156 + 8
    draw.rounded_rectangle([(mi.GENISLIK - kenar - 156, kw_y), (mi.GENISLIK - kenar - 92, kw_y + 24)], radius=4, fill=(240, 242, 240))
    draw.text((mi.GENISLIK - kenar - 147, kw_y + 5), "KONUM", font=mi._font_yukle(mi.FONT_MONO_BOLD, 12), fill=p["silik"])

    # 2. Kılcal çizgi: İletişim bloğunun hemen altında (yasal uyarı öncesi)
    draw.line([(kenar, yer["alt"] - 32), (kenar + gen, yer["alt"] - 32)], fill=p["cizgi"], width=1)
    _yasal_ciz(draw, kenar, yer, p)
    return _kaydet_resim(canvas, "03_cift_kilcal_kural")


# ─────────────────────────────────────────────────────────────────────────────
# 4. İki Sütunlu Kartvizit Mimarisi (Dual Column Business Card)
# ─────────────────────────────────────────────────────────────────────────────
def t04_iki_sutun_kartvizit():
    canvas, draw, p = mi._slayt_cercevesi("kagit", ICERIK["rozet"], "EDM YAPI & GAYRİMENKUL", "04 / 04")
    yer = mi._yerlesim(); kenar = yer["kenar"]; gen = mi.GENISLIK - 2 * kenar
    y = _ust_blok(canvas, draw, kenar, yer, gen, p, baslik_punto=54)

    blok_h = 320
    blok_y = yer["alt"] - 30 - blok_h
    orta_y = y + (blok_y - y) // 2
    draw.line([(kenar, orta_y), (kenar + gen, orta_y)], fill=p["cizgi"], width=1)

    sutun_x = kenar + int(gen * 0.52)
    # Dikey ayraç çizgisi
    draw.line([(sutun_x, blok_y), (sutun_x, blok_y + blok_h - 10)], fill=p["cizgi"], width=1)

    # Sol Sütun: Danışman & Doğrudan Hat
    by = blok_y
    draw.text((kenar, by), "DOĞRUDAN HAT", font=mi._font_yukle(mi.FONT_MONO_BOLD, 16), fill=p["vurgu"]); by += 30
    draw.text((kenar, by), ICERIK["telefon"], font=mi._font_yukle(mi.FONT_MONO_BOLD, 46), fill=p["ana"]); by += 72
    draw.text((kenar, by), ICERIK["isim"], font=mi._font_yukle(mi.FONT_SANS_BOLD, 26), fill=p["ana"]); by += 36
    draw.text((kenar, by), ICERIK["unvan"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 20), fill=p["govde"]); by += 46
    draw.text((kenar, by), ICERIK["site"], font=mi._font_yukle(mi.FONT_MONO_BOLD, 18), fill=p["ana"]); by += 26
    draw.text((kenar, by), ICERIK["eposta"], font=mi._font_yukle(mi.FONT_MONO, 17), fill=p["silik"])

    # Sağ Sütun: Ofis & Konum QR
    sag_x = sutun_x + 36
    sy = blok_y
    draw.text((sag_x, sy), "SİLİVRİ MERKEZ OFİS", font=mi._font_yukle(mi.FONT_MONO_BOLD, 16), fill=p["vurgu"]); sy += 30
    f_ad, a_sat = mi._govde_sigdir(ICERIK["adres"], mi.FONT_SANS_MEDIUM, 20, 16, mi.GENISLIK - kenar - sag_x, 2, draw)
    for s_ in a_sat[:2]:
        draw.text((sag_x, sy), s_, font=f_ad, fill=p["govde"]); sy += int(f_ad.size * 1.38)
    sy += 6
    draw.text((sag_x, sy), ICERIK["hesap"], font=mi._font_yukle(mi.FONT_MONO, 17), fill=p["silik"]); sy += 26

    qr = _qr(132)
    canvas.paste(qr, (sag_x, sy))
    draw.text((sag_x + 144, sy + 56), "HARİTADA\nGÖRÜNTÜLE", font=mi._font_yukle(mi.FONT_MONO_BOLD, 13), fill=p["silik"])

    _yasal_ciz(draw, kenar, yer, p)
    return _kaydet_resim(canvas, "04_iki_sutun_kartvizit")


# ─────────────────────────────────────────────────────────────────────────────
# 5. QR Sağ Üstte / Geniş İletişim Bandı (Top-Right QR / Full-Width Footer)
# ─────────────────────────────────────────────────────────────────────────────
def t05_qr_sag_ustte():
    canvas, draw, p = mi._slayt_cercevesi("kagit", ICERIK["rozet"], "EDM YAPI & GAYRİMENKUL", "04 / 04")
    yer = mi._yerlesim(); kenar = yer["kenar"]; gen = mi.GENISLIK - 2 * kenar

    # Sağ üstte QR Kod
    qr = _qr(140)
    qr_x = mi.GENISLIK - kenar - 140
    canvas.paste(qr, (qr_x, yer["ust"] + 24))
    draw.text((qr_x + 18, yer["ust"] + 24 + 140 + 8), "OFİS KONUMU", font=mi._font_yukle(mi.FONT_MONO_BOLD, 12), fill=p["silik"])

    # Başlık ve açıklama daraltılmış genişlikte
    y = _ust_blok(canvas, draw, kenar, yer, gen, p, baslik_punto=54, aciklama_punto=28, genislik_kisit=gen - 170)

    blok_h = 280
    blok_y = yer["alt"] - 36 - blok_h
    orta_y = y + (blok_y - y) // 2
    draw.line([(kenar, orta_y), (kenar + gen, orta_y)], fill=p["cizgi"], width=1)

    # Tam genişlikte ferah alt blok
    by = blok_y
    draw.text((kenar, by), "DOĞRUDAN HAT  //  BİREBİR DANIŞMANLIK", font=mi._font_yukle(mi.FONT_MONO_BOLD, 17), fill=p["vurgu"]); by += 34
    draw.text((kenar, by), ICERIK["telefon"], font=mi._font_yukle(mi.FONT_MONO_BOLD, 64), fill=p["ana"]); by += 90
    draw.text((kenar, by), f"{ICERIK['isim']}   ·   {ICERIK['unvan']}", font=mi._font_yukle(mi.FONT_SANS_BOLD, 26), fill=p["ana"]); by += 42
    draw.text((kenar, by), ICERIK["adres"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 22), fill=p["govde"]); by += 36
    draw.text((kenar, by), f"{ICERIK['site']}   ·   {ICERIK['eposta']}   ·   {ICERIK['hesap']}", font=mi._font_yukle(mi.FONT_MONO, 18), fill=p["silik"])

    _yasal_ciz(draw, kenar, yer, p)
    return _kaydet_resim(canvas, "05_qr_sag_ustte")


# ─────────────────────────────────────────────────────────────────────────────
# 6. Sol Mimari Vurgu Çizgisi (Architectural Edge)
# ─────────────────────────────────────────────────────────────────────────────
def t06_sol_vurgu_cizgisi():
    canvas, draw, p = mi._slayt_cercevesi("kagit", ICERIK["rozet"], "EDM YAPI & GAYRİMENKUL", "04 / 04")
    yer = mi._yerlesim(); kenar = yer["kenar"]; gen = mi.GENISLIK - 2 * kenar
    y = _ust_blok(canvas, draw, kenar, yer, gen, p)

    blok_h = 296
    blok_y = yer["alt"] - 36 - blok_h
    orta_y = y + (blok_y - y) // 2
    draw.line([(kenar, orta_y), (kenar + gen, orta_y)], fill=p["cizgi"], width=1)

    # Sol kenarda kırmızı mimari dikey çubuk
    draw.rounded_rectangle([(kenar, blok_y - 4), (kenar + 5, blok_y + blok_h - 10)], radius=3, fill=p["vurgu"])
    sol_ic = kenar + 34

    by = blok_y
    draw.text((sol_ic, by), "DOĞRUDAN HAT", font=mi._font_yukle(mi.FONT_MONO_BOLD, 17), fill=p["vurgu"]); by += 32
    draw.text((sol_ic, by), ICERIK["telefon"], font=mi._font_yukle(mi.FONT_MONO_BOLD, 54), fill=p["ana"]); by += 82
    draw.text((sol_ic, by), f"{ICERIK['isim']}  ·  {ICERIK['unvan']}", font=mi._font_yukle(mi.FONT_SANS_SEMIBOLD, 24), fill=p["ana"]); by += 40
    draw.text((sol_ic, by), ICERIK["adres"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 21), fill=p["govde"]); by += 34
    draw.text((sol_ic, by), ICERIK["eposta"], font=mi._font_yukle(mi.FONT_MONO, 19), fill=p["silik"]); by += 28
    draw.text((sol_ic, by), f"{ICERIK['site']}  ·  {ICERIK['hesap']}", font=mi._font_yukle(mi.FONT_MONO, 19), fill=p["silik"])

    qr = _qr(152)
    canvas.paste(qr, (mi.GENISLIK - kenar - 152, blok_y + 6))
    kw_y = blok_y + 6 + 152 + 8
    draw.rounded_rectangle([(mi.GENISLIK - kenar - 152, kw_y), (mi.GENISLIK - kenar - 88, kw_y + 24)], radius=4, fill=(240, 242, 240))
    draw.text((mi.GENISLIK - kenar - 143, kw_y + 5), "KONUM", font=mi._font_yukle(mi.FONT_MONO_BOLD, 12), fill=p["silik"])

    _yasal_ciz(draw, kenar, yer, p)
    return _kaydet_resim(canvas, "06_sol_mimari_vurgu")


# ─────────────────────────────────────────────────────────────────────────────
# 7. Hero Dev Telefon (Direct Action Heavy)
# ─────────────────────────────────────────────────────────────────────────────
def t07_hero_dev_telefon():
    canvas, draw, p = mi._slayt_cercevesi("kagit", ICERIK["rozet"], "EDM YAPI & GAYRİMENKUL", "04 / 04")
    yer = mi._yerlesim(); kenar = yer["kenar"]; gen = mi.GENISLIK - 2 * kenar
    y = _ust_blok(canvas, draw, kenar, yer, gen, p, baslik_punto=52, aciklama_punto=28)

    blok_h = 320
    blok_y = yer["alt"] - 30 - blok_h
    orta_y = y + (blok_y - y) // 2
    draw.line([(kenar, orta_y), (kenar + gen, orta_y)], fill=p["cizgi"], width=1)

    by = blok_y
    draw.text((kenar, by), "SORUNUZ VARSA DOĞRUDAN ARAYIN // HAFTANIN 7 GÜNÜ", font=mi._font_yukle(mi.FONT_MONO_BOLD, 16), fill=p["vurgu"]); by += 36
    # 76px dev telefon numarası
    draw.text((kenar, by), ICERIK["telefon"], font=mi._font_yukle(mi.FONT_MONO_BOLD, 76), fill=p["ana"]); by += 106
    draw.text((kenar, by), f"{ICERIK['isim']}  ·  {ICERIK['unvan']}", font=mi._font_yukle(mi.FONT_SANS_BOLD, 24), fill=p["ana"]); by += 38
    draw.text((kenar, by), ICERIK["adres"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 21), fill=p["govde"]); by += 34
    draw.text((kenar, by), ICERIK["eposta"], font=mi._font_yukle(mi.FONT_MONO, 18), fill=p["silik"]); by += 26
    draw.text((kenar, by), f"{ICERIK['site']}  ·  {ICERIK['hesap']}", font=mi._font_yukle(mi.FONT_MONO, 18), fill=p["silik"])

    qr = _qr(144)
    canvas.paste(qr, (mi.GENISLIK - kenar - 144, blok_y + 118))
    draw.text((mi.GENISLIK - kenar - 144 + 20, blok_y + 118 + 144 + 8), "OFİS KONUMU", font=mi._font_yukle(mi.FONT_MONO_BOLD, 12), fill=p["silik"])

    _yasal_ciz(draw, kenar, yer, p)
    return _kaydet_resim(canvas, "07_hero_dev_telefon")


# ─────────────────────────────────────────────────────────────────────────────
# 8. Kısa Kırmızı Editoryal Kural (Swiss Minimalist)
# ─────────────────────────────────────────────────────────────────────────────
def t08_kisa_kirmizi_cizgi():
    canvas, draw, p = mi._slayt_cercevesi("kagit", ICERIK["rozet"], "EDM YAPI & GAYRİMENKUL", "04 / 04")
    yer = mi._yerlesim(); kenar = yer["kenar"]; gen = mi.GENISLIK - 2 * kenar
    y = _ust_blok(canvas, draw, kenar, yer, gen, p)

    blok_h = 296
    blok_y = yer["alt"] - 36 - blok_h
    orta_y = y + (blok_y - y) // 2
    # Tam genişlik yerine sadece 130px kısa kırmızı kural
    draw.rectangle([(kenar, orta_y), (kenar + 130, orta_y + 3)], fill=p["vurgu"])

    by = blok_y
    draw.text((kenar, by), "DOĞRUDAN HAT", font=mi._font_yukle(mi.FONT_MONO_BOLD, 17), fill=p["silik"]); by += 32
    draw.text((kenar, by), ICERIK["telefon"], font=mi._font_yukle(mi.FONT_MONO_BOLD, 54), fill=p["ana"]); by += 82
    draw.text((kenar, by), f"{ICERIK['isim']}  ·  {ICERIK['unvan']}", font=mi._font_yukle(mi.FONT_SANS_SEMIBOLD, 24), fill=p["ana"]); by += 40
    draw.text((kenar, by), ICERIK["adres"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 21), fill=p["govde"]); by += 34
    draw.text((kenar, by), ICERIK["eposta"], font=mi._font_yukle(mi.FONT_MONO, 19), fill=p["silik"]); by += 28
    draw.text((kenar, by), f"{ICERIK['site']}  ·  {ICERIK['hesap']}", font=mi._font_yukle(mi.FONT_MONO, 19), fill=p["silik"])

    qr = _qr(152)
    canvas.paste(qr, (mi.GENISLIK - kenar - 152, blok_y + 6))
    kw_y = blok_y + 6 + 152 + 8
    draw.rounded_rectangle([(mi.GENISLIK - kenar - 152, kw_y), (mi.GENISLIK - kenar - 88, kw_y + 24)], radius=4, fill=(240, 242, 240))
    draw.text((mi.GENISLIK - kenar - 143, kw_y + 5), "KONUM", font=mi._font_yukle(mi.FONT_MONO_BOLD, 12), fill=p["silik"])

    _yasal_ciz(draw, kenar, yer, p)
    return _kaydet_resim(canvas, "08_kisa_kirmizi_cizgi")


# ─────────────────────────────────────────────────────────────────────────────
# 9. Koyu Gece / Executive Mürekkep (Dark Ink Luxury Edition)
# ─────────────────────────────────────────────────────────────────────────────
def t09_koyu_luks_murekkep():
    canvas, draw, p = mi._slayt_cercevesi("murekkep", ICERIK["rozet"], "EDM YAPI & GAYRİMENKUL", "04 / 04")
    yer = mi._yerlesim(); kenar = yer["kenar"]; gen = mi.GENISLIK - 2 * kenar
    y = _ust_blok(canvas, draw, kenar, yer, gen, p)

    blok_h = 296
    blok_y = yer["alt"] - 36 - blok_h
    orta_y = y + (blok_y - y) // 2
    draw.line([(kenar, orta_y), (kenar + gen, orta_y)], fill=p["cizgi"], width=1)

    by = blok_y
    draw.text((kenar, by), "DOĞRUDAN HAT", font=mi._font_yukle(mi.FONT_MONO_BOLD, 17), fill=p["vurgu"]); by += 32
    draw.text((kenar, by), ICERIK["telefon"], font=mi._font_yukle(mi.FONT_MONO_BOLD, 54), fill=p["ana"]); by += 82
    draw.text((kenar, by), f"{ICERIK['isim']}  ·  {ICERIK['unvan']}", font=mi._font_yukle(mi.FONT_SANS_SEMIBOLD, 24), fill=p["ana"]); by += 40
    draw.text((kenar, by), ICERIK["adres"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 21), fill=p["govde"]); by += 34
    draw.text((kenar, by), ICERIK["eposta"], font=mi._font_yukle(mi.FONT_MONO, 19), fill=p["silik"]); by += 28
    draw.text((kenar, by), f"{ICERIK['site']}  ·  {ICERIK['hesap']}", font=mi._font_yukle(mi.FONT_MONO, 19), fill=p["silik"])

    # Koyu zemin için açık QR Kod
    qr = _qr(152, zemin="#ffffff", muhur="#0e1013")
    canvas.paste(qr, (mi.GENISLIK - kenar - 152, blok_y + 6))
    kw_y = blok_y + 6 + 152 + 8
    draw.rounded_rectangle([(mi.GENISLIK - kenar - 152, kw_y), (mi.GENISLIK - kenar - 88, kw_y + 24)], radius=4, fill=(28, 32, 38))
    draw.text((mi.GENISLIK - kenar - 143, kw_y + 5), "KONUM", font=mi._font_yukle(mi.FONT_MONO_BOLD, 12), fill=p["vurgu"])

    _yasal_ciz(draw, kenar, yer, p)
    return _kaydet_resim(canvas, "09_koyu_luks_murekkep")


# ─────────────────────────────────────────────────────────────────────────────
# 10. Etiketli Editoryal Izgara (Structured Blueprint Grid)
# ─────────────────────────────────────────────────────────────────────────────
def t10_etiketli_mimari_izgara():
    canvas, draw, p = mi._slayt_cercevesi("kagit", ICERIK["rozet"], "EDM YAPI & GAYRİMENKUL", "04 / 04")
    yer = mi._yerlesim(); kenar = yer["kenar"]; gen = mi.GENISLIK - 2 * kenar
    y = _ust_blok(canvas, draw, kenar, yer, gen, p, baslik_punto=54)

    blok_h = 320
    blok_y = yer["alt"] - 30 - blok_h
    orta_y = y + (blok_y - y) // 2
    draw.line([(kenar, orta_y), (kenar + gen, orta_y)], fill=p["cizgi"], width=1)

    f_etiket = mi._font_yukle(mi.FONT_MONO_BOLD, 15)
    et_x = kenar
    val_x = kenar + 140

    by = blok_y
    # Satır 1: Telefon
    draw.text((et_x, by + 18), "TELEFON", font=f_etiket, fill=p["vurgu"])
    draw.text((val_x, by), ICERIK["telefon"], font=mi._font_yukle(mi.FONT_MONO_BOLD, 50), fill=p["ana"]); by += 82

    # Satır 2: Danışman
    draw.text((et_x, by + 4), "DANIŞMAN", font=f_etiket, fill=p["vurgu"])
    draw.text((val_x, by), f"{ICERIK['isim']}  ·  {ICERIK['unvan']}", font=mi._font_yukle(mi.FONT_SANS_SEMIBOLD, 24), fill=p["ana"]); by += 46

    # Satır 3: Ofis
    draw.text((et_x, by + 3), "ADRES", font=f_etiket, fill=p["vurgu"])
    draw.text((val_x, by), ICERIK["adres"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 21), fill=p["govde"]); by += 46

    # Satır 4: E-posta
    draw.text((et_x, by + 2), "E-POSTA", font=f_etiket, fill=p["vurgu"])
    draw.text((val_x, by), ICERIK["eposta"], font=mi._font_yukle(mi.FONT_MONO, 19), fill=p["silik"]); by += 36

    # Satır 5: Web & Sosyal
    draw.text((et_x, by + 2), "WEB", font=f_etiket, fill=p["vurgu"])
    draw.text((val_x, by), f"{ICERIK['site']}   ·   {ICERIK['hesap']}", font=mi._font_yukle(mi.FONT_MONO, 19), fill=p["silik"])

    qr = _qr(150)
    canvas.paste(qr, (mi.GENISLIK - kenar - 150, blok_y + 40))
    draw.text((mi.GENISLIK - kenar - 150 + 26, blok_y + 40 + 150 + 8), "OFİS KONUMU", font=mi._font_yukle(mi.FONT_MONO_BOLD, 12), fill=p["silik"])

    _yasal_ciz(draw, kenar, yer, p)
    return _kaydet_resim(canvas, "10_etiketli_mimari_izgara")


def main():
    print("10 Farklı Kapanış Tasarımı Üretiliyor...")
    t01_klasik_editoryal()
    t02_kirmizi_numara()
    t03_cift_kilcal_kural()
    t04_iki_sutun_kartvizit()
    t05_qr_sag_ustte()
    t06_sol_vurgu_cizgisi()
    t07_hero_dev_telefon()
    t08_kisa_kirmizi_cizgi()
    t09_koyu_luks_murekkep()
    t10_etiketli_mimari_izgara()
    print("Tüm 10 tasarım başarıyla üretildi!")

if __name__ == "__main__":
    main()
