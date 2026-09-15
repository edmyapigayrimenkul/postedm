#!/usr/bin/env python3
"""
scripts/kapanis_alternatif2.py — Kapanış: A/B Ailesi Varyasyonları

İlk turda A (tek sütun) ve B (iki sütun) seçildi, A bir tık önde.
Bu tur o ailenin içinde kalıyor: kutu yok, şerit ızgarası yok, mürekkep
ayak yok. Yalnızca tipografi, çizgi ve boşluk.

İlk turdan üç düzeltme:
  · edmyapigayrimenkul.com geri geldi — kapanış tek yönlendirme noktası
  · "BU REHBERİ KAYDEDİN" geri geldi. İç slaytlardan kaldırılmıştı ama
    kapanışta kalması kararlaştırılmıştı; kutulu şerit yerine yer imi +
    tek satır mono olarak duruyor
  · Filigran kapanışta kapalı: üstte logo, sağda QR, altta kurum adı
    zaten var; dördüncü marka işareti orta boşluğun tek dolu öğesi
    haline geliyordu

Değişkenler:
  · kural sayısı ve genişliği (0, 1, 2, kısa)
  · telefonun ağırlığı ve rengi
  · QR'ın yeri (sağ üst / sağ alt / sütun içi)
  · kırmızının nereye düştüğü
  · danışman kimliğinin önem sırası
  · sol vurgu çizgisinin varlığı

    python scripts/kapanis_alternatif2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import make_image as mi
from scripts.kapanis_alternatif import ICERIK, _qr, _baslik_ciz

CIKTI = KOK / "data/output/kapanis2"

# İlk turda eksik kalan iki alan
ICERIK.setdefault("site", "edmyapigayrimenkul.com")
ICERIK.setdefault("kaydet", "BU REHBERİ KAYDEDİN · İHTİYAÇ ANINDA ELİNİZİN ALTINDA OLSUN")

# Önizleme kararı: kapanışta filigran yok. Üretim kodu değişmedi, yalnızca
# bu betik içinde etkisiz bırakılıyor ki varyantlar filigransız değerlendirilsin.
mi._filigran_uygula = lambda canvas, acik_zemin=False: canvas

BASLIK_PUNTO = 68
ALT_PAY = 6


def _kare(rozet="EDM DANIŞMANLIK"):
    canvas, draw, p = mi._slayt_cercevesi("kagit", rozet, "EDM YAPI & GAYRİMENKUL", "04 / 04")
    yer = mi._yerlesim()
    return canvas, draw, p, yer, yer["kenar"], mi.GENISLIK - 2 * yer["kenar"]


def _aciklama(draw, kenar, y, gen, p, punto=34):
    f, sat = mi._govde_sigdir(ICERIK["aciklama"], mi.FONT_SANS_MEDIUM, punto, 25, gen, 2, draw)
    for s in sat[:2]:
        draw.text((kenar, y), s, font=f, fill=p["govde"]); y += int(f.size * 1.36)
    return y


def _kaydet_ciz(canvas, draw, x, y, p, punto=17, renk=None):
    """Kaydet çağrısı — kutu değil, yer imi + tek satır mono."""
    try:
        ikon = mi._vektor_ikon_uret("bookmark", punto + 6, p["vurgu"])
        canvas.paste(ikon, (x, y - 3), ikon)
    except Exception:
        pass
    draw.text((x + punto + 16, y), ICERIK["kaydet"],
              font=mi._font_yukle(mi.FONT_MONO_BOLD, punto), fill=renk or p["ana"])
    return y + punto + 18


def _yasal(draw, kenar, yer, p, punto=16):
    draw.text((kenar, yer["alt"] + 22), ICERIK["yasal"],
              font=mi._font_yukle(mi.FONT_SANS_MEDIUM, punto), fill=p["silik"])


def _kaydet(canvas, yol):
    yol.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(yol, "JPEG", quality=95)
    return yol


# Standart A gövdesi: etiket → telefon → isim → unvan → adres → e-posta → site
# Yükseklik telefon puntosundan türer; blok alta çivilenirken bu ölçü kullanılır.
def _a_yukseklik(tel_punto=64):
    return 38 + int(tel_punto * 1.42) + 42 + 56 + 40 + 32 + 28


def _a_govdesi(draw, x, b, p, etiket_renk, tel_renk, tel_punto=64, etiket="DOĞRUDAN HAT"):
    draw.text((x, b), etiket, font=mi._font_yukle(mi.FONT_MONO_BOLD, 18), fill=etiket_renk); b += 38
    draw.text((x, b), ICERIK["telefon"], font=mi._font_yukle(mi.FONT_MONO_BOLD, tel_punto), fill=tel_renk)
    b += int(tel_punto * 1.42)
    draw.text((x, b), ICERIK["isim"], font=mi._font_yukle(mi.FONT_SANS_BOLD, 29), fill=p["ana"]); b += 42
    draw.text((x, b), ICERIK["unvan"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 23), fill=p["govde"]); b += 56
    draw.text((x, b), ICERIK["adres"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 23), fill=p["govde"]); b += 40
    draw.text((x, b), ICERIK["eposta"], font=mi._font_yukle(mi.FONT_MONO, 20), fill=p["silik"]); b += 32
    draw.text((x, b), f"{ICERIK['site']}  ·  {ICERIK['hesap']}", font=mi._font_yukle(mi.FONT_MONO, 20), fill=p["silik"])
    return b + 28


def _ust_blok(canvas, draw, kenar, yer, gen, p, baslik_punto=BASLIK_PUNTO, aciklama_punto=34, kaydet_renk=None):
    y = _baslik_ciz(draw, kenar, yer["ust"] - 12, gen, p, punto=baslik_punto)
    y = _aciklama(draw, kenar, y + 16, gen, p, aciklama_punto)
    return _kaydet_ciz(canvas, draw, kenar, y + 20, p, renk=kaydet_renk)


# ── A1 — Telefon kırmızı: vurgu başlıktan numaraya geçiyor ─────────────
def a1(yol):
    canvas, draw, p, yer, kenar, gen = _kare()
    y = _ust_blok(canvas, draw, kenar, yer, gen, p)
    blok = yer["alt"] - ALT_PAY - _a_yukseklik(64)
    draw.line([(kenar, (y + blok)//2), (kenar + gen, (y + blok)//2)], fill=p["cizgi"], width=1)
    _a_govdesi(draw, kenar, blok, p, p["silik"], p["vurgu"], 64)
    q = _qr(184)
    if q: canvas.paste(q, (mi.GENISLIK - kenar - 184, blok + 8))
    _yasal(draw, kenar, yer, p)
    return _kaydet(canvas, yol)


# ── A2 — İki kural: iletişim bloğu simetrik çerçeveleniyor ────────────
def a2(yol):
    canvas, draw, p, yer, kenar, gen = _kare()
    y = _ust_blok(canvas, draw, kenar, yer, gen, p)
    blok = yer["alt"] - ALT_PAY - _a_yukseklik(64)
    draw.line([(kenar, blok - 46), (kenar + gen, blok - 46)], fill=p["cizgi"], width=1)
    _a_govdesi(draw, kenar, blok, p, p["vurgu"], p["ana"], 64)
    q = _qr(184)
    if q: canvas.paste(q, (mi.GENISLIK - kenar - 184, blok + 8))
    draw.line([(kenar, yer["alt"] + 4), (kenar + gen, yer["alt"] + 4)], fill=p["cizgi"], width=1)
    _yasal(draw, kenar, yer, p, 15)
    return _kaydet(canvas, yol)


# ── A3 — QR sağ üstte: alt blok hiç bölünmüyor, tam genişlik ──────────
def a3(yol):
    canvas, draw, p, yer, kenar, gen = _kare()
    q = _qr(132)
    if q:
        canvas.paste(q, (mi.GENISLIK - kenar - 132, yer["ust"] - 6))
        draw.text((mi.GENISLIK - kenar - 132, yer["ust"] + 134), "OFİS KONUMU",
                  font=mi._font_yukle(mi.FONT_MONO_BOLD, 13), fill=p["silik"])
    y = _baslik_ciz(draw, kenar, yer["ust"] - 12, gen - 180, p, punto=62)
    y = _aciklama(draw, kenar, y + 16, gen, p, 34)
    y = _kaydet_ciz(canvas, draw, kenar, y + 20, p)
    blok = yer["alt"] - ALT_PAY - _a_yukseklik(72)
    draw.line([(kenar, (y + blok)//2), (kenar + gen, (y + blok)//2)], fill=p["cizgi"], width=1)
    _a_govdesi(draw, kenar, blok, p, p["vurgu"], p["ana"], 72)
    _yasal(draw, kenar, yer, p)
    return _kaydet(canvas, yol)


# ── A4 — Sol vurgu çizgisi: iç slaytların marka öğesi kapanışta da ────
def a4(yol):
    canvas, draw, p, yer, kenar, gen = _kare()
    _ust_blok(canvas, draw, kenar, yer, gen, p)
    h = _a_yukseklik(64)
    blok = yer["alt"] - ALT_PAY - h
    draw.rounded_rectangle([(kenar, blok - 10), (kenar + 6, blok + h - 30)], radius=3, fill=p["vurgu"])
    _a_govdesi(draw, kenar + 36, blok, p, p["vurgu"], p["ana"], 64)
    q = _qr(184)
    if q: canvas.paste(q, (mi.GENISLIK - kenar - 184, blok + 8))
    _yasal(draw, kenar, yer, p)
    return _kaydet(canvas, yol)


# ── A5 — Telefon hakim: kapanış tek bir eylem çağrısına indirgeniyor ──
def a5(yol):
    canvas, draw, p, yer, kenar, gen = _kare()
    y = _ust_blok(canvas, draw, kenar, yer, gen, p, baslik_punto=52, aciklama_punto=30)
    blok = yer["alt"] - ALT_PAY - 300
    draw.line([(kenar, (y + blok)//2), (kenar + gen, (y + blok)//2)], fill=p["cizgi"], width=1)
    b = blok
    draw.text((kenar, b), "SORUNUZ VARSA DOĞRUDAN ARAYIN", font=mi._font_yukle(mi.FONT_MONO_BOLD, 18), fill=p["vurgu"]); b += 40
    draw.text((kenar, b), ICERIK["telefon"], font=mi._font_yukle(mi.FONT_MONO_BOLD, 86), fill=p["ana"]); b += 128
    draw.text((kenar, b), f"{ICERIK['isim']}  ·  {ICERIK['unvan']}", font=mi._font_yukle(mi.FONT_SANS_SEMIBOLD, 24), fill=p["ana"]); b += 38
    draw.text((kenar, b), ICERIK["adres"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 20), fill=p["govde"]); b += 30
    draw.text((kenar, b), f"{ICERIK['site']}  ·  {ICERIK['hesap']}  ·  {ICERIK['eposta']}", font=mi._font_yukle(mi.FONT_MONO, 18), fill=p["silik"])
    q = _qr(140)
    if q: canvas.paste(q, (mi.GENISLIK - kenar - 140, blok + 120))
    _yasal(draw, kenar, yer, p)
    return _kaydet(canvas, yol)


# ── A6 — Hiç çizgi: yalnızca boşluk ritmi. En sade uç ─────────────────
def a6(yol):
    canvas, draw, p, yer, kenar, gen = _kare()
    _ust_blok(canvas, draw, kenar, yer, gen, p)
    blok = yer["alt"] - ALT_PAY - _a_yukseklik(64)
    _a_govdesi(draw, kenar, blok, p, p["vurgu"], p["ana"], 64)
    q = _qr(184)
    if q: canvas.paste(q, (mi.GENISLIK - kenar - 184, blok + 8))
    _yasal(draw, kenar, yer, p)
    return _kaydet(canvas, yol)


# ── A7 — Kısa kırmızı kural: marka vurgusu çizgiye taşınıyor ──────────
def a7(yol):
    canvas, draw, p, yer, kenar, gen = _kare()
    y = _ust_blok(canvas, draw, kenar, yer, gen, p, kaydet_renk=None)
    blok = yer["alt"] - ALT_PAY - _a_yukseklik(64)
    ky = (y + blok)//2
    draw.rectangle([(kenar, ky), (kenar + 132, ky + 4)], fill=p["vurgu"])
    _a_govdesi(draw, kenar, blok, p, p["silik"], p["ana"], 64)
    q = _qr(184)
    if q: canvas.paste(q, (mi.GENISLIK - kenar - 184, blok + 8))
    _yasal(draw, kenar, yer, p)
    return _kaydet(canvas, yol)


# ── B1 — İki sütun, kısa ayraç: ayraç yalnızca blok boyunca ───────────
def b1(yol):
    canvas, draw, p, yer, kenar, gen = _kare()
    y = _ust_blok(canvas, draw, kenar, yer, gen, p, baslik_punto=62)
    blok = yer["alt"] - ALT_PAY - 340
    orta = kenar + int(gen * 0.55)
    draw.line([(orta, blok - 14), (orta, blok + 330)], fill=p["cizgi"], width=1)
    b = blok
    draw.text((kenar, b), "DOĞRUDAN HAT", font=mi._font_yukle(mi.FONT_MONO_BOLD, 17), fill=p["vurgu"]); b += 36
    draw.text((kenar, b), ICERIK["telefon"], font=mi._font_yukle(mi.FONT_MONO_BOLD, 52), fill=p["ana"]); b += 84
    draw.text((kenar, b), ICERIK["isim"], font=mi._font_yukle(mi.FONT_SANS_BOLD, 27), fill=p["ana"]); b += 38
    draw.text((kenar, b), ICERIK["unvan"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 21), fill=p["govde"]); b += 54
    draw.text((kenar, b), ICERIK["eposta"], font=mi._font_yukle(mi.FONT_MONO, 18), fill=p["silik"]); b += 28
    draw.text((kenar, b), ICERIK["site"], font=mi._font_yukle(mi.FONT_MONO, 18), fill=p["silik"])
    sag = orta + 38
    g = blok
    draw.text((sag, g), "SİLİVRİ MERKEZ OFİS", font=mi._font_yukle(mi.FONT_MONO_BOLD, 17), fill=p["vurgu"]); g += 36
    f_ad, ad = mi._govde_sigdir(ICERIK["adres"], mi.FONT_SANS_MEDIUM, 22, 18, mi.GENISLIK - kenar - sag, 3, draw)
    for s in ad[:3]:
        draw.text((sag, g), s, font=f_ad, fill=p["govde"]); g += int(f_ad.size * 1.36)
    draw.text((sag, g + 6), ICERIK["hesap"], font=mi._font_yukle(mi.FONT_MONO, 18), fill=p["silik"]); g += 40
    q = _qr(150)
    if q: canvas.paste(q, (sag, g + 10))
    _yasal(draw, kenar, yer, p)
    return _kaydet(canvas, yol)


# ── B2 — Etiket sütunu: solda dar mono etiketler, sağda değerler ──────
def b2(yol):
    canvas, draw, p, yer, kenar, gen = _kare()
    _ust_blok(canvas, draw, kenar, yer, gen, p, baslik_punto=62)
    blok = yer["alt"] - ALT_PAY - 330
    et_x, dg_x = kenar, kenar + 200
    f_et = mi._font_yukle(mi.FONT_MONO_BOLD, 16)
    b = blok
    draw.text((et_x, b + 18), "TELEFON", font=f_et, fill=p["vurgu"])
    draw.text((dg_x, b), ICERIK["telefon"], font=mi._font_yukle(mi.FONT_MONO_BOLD, 52), fill=p["ana"]); b += 96
    draw.text((et_x, b + 5), "DANIŞMAN", font=f_et, fill=p["vurgu"])
    draw.text((dg_x, b), f"{ICERIK['isim']} · {ICERIK['unvan']}", font=mi._font_yukle(mi.FONT_SANS_SEMIBOLD, 25), fill=p["ana"]); b += 58
    draw.text((et_x, b + 4), "OFİS", font=f_et, fill=p["vurgu"])
    draw.text((dg_x, b), ICERIK["adres"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 22), fill=p["govde"]); b += 54
    draw.text((et_x, b + 3), "E-POSTA", font=f_et, fill=p["vurgu"])
    draw.text((dg_x, b), ICERIK["eposta"], font=mi._font_yukle(mi.FONT_MONO, 19), fill=p["silik"]); b += 44
    draw.text((et_x, b + 3), "WEB", font=f_et, fill=p["vurgu"])
    draw.text((dg_x, b), f"{ICERIK['site']}  ·  {ICERIK['hesap']}", font=mi._font_yukle(mi.FONT_MONO, 19), fill=p["silik"])
    q = _qr(150)
    if q: canvas.paste(q, (mi.GENISLIK - kenar - 150, blok + 118))
    _yasal(draw, kenar, yer, p)
    return _kaydet(canvas, yol)


# ── B3 — Ağırlık sağda: QR ve adres sağ sütunda büyür, sol sadece hat ─
def b3(yol):
    canvas, draw, p, yer, kenar, gen = _kare()
    _ust_blok(canvas, draw, kenar, yer, gen, p, baslik_punto=62)
    blok = yer["alt"] - ALT_PAY - 340
    orta = kenar + int(gen * 0.46)
    draw.line([(kenar, blok - 46), (kenar + gen, blok - 46)], fill=p["cizgi"], width=1)
    b = blok
    draw.text((kenar, b), "DOĞRUDAN HAT", font=mi._font_yukle(mi.FONT_MONO_BOLD, 17), fill=p["vurgu"]); b += 36
    draw.text((kenar, b), ICERIK["telefon"], font=mi._font_yukle(mi.FONT_MONO_BOLD, 44), fill=p["ana"]); b += 76
    draw.text((kenar, b), ICERIK["isim"], font=mi._font_yukle(mi.FONT_SANS_BOLD, 26), fill=p["ana"]); b += 36
    draw.text((kenar, b), ICERIK["unvan"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 21), fill=p["govde"]); b += 52
    draw.text((kenar, b), ICERIK["eposta"], font=mi._font_yukle(mi.FONT_MONO, 18), fill=p["silik"]); b += 28
    draw.text((kenar, b), ICERIK["site"], font=mi._font_yukle(mi.FONT_MONO, 18), fill=p["silik"]); b += 28
    draw.text((kenar, b), ICERIK["hesap"], font=mi._font_yukle(mi.FONT_MONO, 18), fill=p["silik"])
    sag = orta + 44
    g = blok
    draw.text((sag, g), "SİLİVRİ MERKEZ OFİS", font=mi._font_yukle(mi.FONT_MONO_BOLD, 17), fill=p["vurgu"]); g += 36
    f_ad, ad = mi._govde_sigdir(ICERIK["adres"], mi.FONT_SANS_MEDIUM, 23, 18, mi.GENISLIK - kenar - sag, 3, draw)
    for s in ad[:3]:
        draw.text((sag, g), s, font=f_ad, fill=p["govde"]); g += int(f_ad.size * 1.36)
    q = _qr(176)
    if q: canvas.paste(q, (sag, g + 16))
    _yasal(draw, kenar, yer, p)
    return _kaydet(canvas, yol)


VARYANTLAR = {
    "A1_telefon_kirmizi": a1,
    "A2_iki_kural": a2,
    "A3_qr_sag_ust": a3,
    "A4_sol_vurgu_cizgisi": a4,
    "A5_telefon_hakim": a5,
    "A6_cizgisiz": a6,
    "A7_kisa_kirmizi_kural": a7,
    "B1_kisa_ayrac": b1,
    "B2_etiket_sutunu": b2,
    "B3_agirlik_sagda": b3,
}


def main() -> int:
    CIKTI.mkdir(parents=True, exist_ok=True)
    for ad, fn in VARYANTLAR.items():
        print("  ✓", fn(CIKTI / f"{ad}.jpg").name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
