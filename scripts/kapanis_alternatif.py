#!/usr/bin/env python3
"""
scripts/kapanis_alternatif.py — Kapanış Slaytı Tasarım Alternatifleri

Mevcut kapanış üç yerde orantısız:
  · kutu içinde kutu içinde kutu (panel → telefon kartı → QR kartı → not kartı)
  · telefon 48px isimden (32px) büyük, başlıkla (54px) yarışıyor
  · 13+ bilgi parçası, 4 ayrı sol kırmızı çizgi

Beş alternatif. Hepsi aynı tasarım dilinde kalıyor: Fraunces başlık,
Plus Jakarta gövde, IBM Plex Mono teknik; kağıt zemin, mürekkep metin,
kırmızı vurgu; aynı üst kronik ve alt bar.

Değişen tek şey DÜZENLEYİCİ İLKE — her varyantın farklı bir yanıtı var:
"bu karede gözü ne yönetecek?"

    python scripts/kapanis_alternatif.py
"""

from __future__ import annotations

import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from PIL import Image

from src import config, make_image as mi

CIKTI = KOK / "data/output/kapanis"

# Ortak içerik — varyantlar arasında değişmez ki fark tasarımdan gelsin
ICERIK = {
    "baslik_1": "Doğru adımlarla",
    "baslik_2": "GÜVENLİ KİRALAMA",
    "aciklama": "Silivri ve Trakya genelinde mülk yönetimi ve hukuki süreçlerinizde yanınızdayız.",
    "isim": "METİN ÖZDOĞAN",
    "unvan": "Kurucu Danışman",
    "telefon": "0 212 727 2955",
    "adres": "Alibey Mah. Albay Yunus Dirik Cad. No: 58/A · Silivri",
    "eposta": "info@edmyapigayrimenkul.com",
    "hesap": "@edmyapigayrimenkul",
    "yasal": "Bu içerik genel bilgilendirmedir; bağlayıcı hukuki görüş için avukatınıza danışın.",
}

QR_ADRES = "https://maps.google.com/?q=Alibey+Mah+Albay+Yunus+Dirik+Cad+No+58A+Silivri"


def _qr(boyut: int, zemin: str = "#ffffff", muhur: str = "#121316") -> Image.Image | None:
    try:
        import qrcode
        q = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M,
                          box_size=4, border=1)
        q.add_data(QR_ADRES)
        q.make(fit=True)
        g = q.make_image(fill_color=muhur, back_color=zemin).convert("RGB")
        return g.resize((boyut, boyut), Image.Resampling.LANCZOS)
    except Exception:
        return None


def _baslik_ciz(draw, kenar, y, genislik, p, punto=56):
    """Ortak başlık bloğu: iki parçalı, ikinci parça kırmızı."""
    f, s1 = mi._govde_sigdir(ICERIK["baslik_1"], mi.FONT_FRAUNCES, punto, 36, genislik, 2, draw)
    f2, s2 = mi._govde_sigdir(ICERIK["baslik_2"], mi.FONT_FRAUNCES, punto, 36, genislik, 2, draw)
    f = f if f.size <= f2.size else f2
    s1 = mi._metin_sar(ICERIK["baslik_1"], f, genislik, draw)[:2]
    s2 = mi._metin_sar(ICERIK["baslik_2"], f, genislik, draw)[:2]
    aralik = int(f.size * 1.18)
    for satir in s1:
        draw.text((kenar, y), satir, font=f, fill=p["ana"]); y += aralik
    for satir in s2:
        draw.text((kenar, y), satir, font=f, fill=p["vurgu"]); y += aralik
    return y


# =========================================================================
# A — TEK SÜTUN HİYERARŞİ
#     Düzenleyici ilke: yalnızca tipografi. Hiç kutu yok, hiç çerçeve yok.
#     Bilgi önem sırasına göre küçülüyor; göz yukarıdan aşağı tek yol izliyor.
# =========================================================================
def varyant_a(yol: Path) -> Path:
    canvas, draw, p = mi._slayt_cercevesi("kagit", "EDM DANIŞMANLIK", "EDM YAPI & GAYRİMENKUL", "04 / 04")
    yer = mi._yerlesim(); kenar = yer["kenar"]; gen = mi.GENISLIK - 2 * kenar

    y = _baslik_ciz(draw, kenar, yer["ust"] + 24, gen, p)
    y += 18
    f_a, sat = mi._govde_sigdir(ICERIK["aciklama"], mi.FONT_SANS_MEDIUM, 30, 24, gen, 2, draw)
    for s_ in sat[:2]:
        draw.text((kenar, y), s_, font=f_a, fill=p["govde"]); y += int(f_a.size * 1.36)

    # İletişim bloğu ALTA YASLANIR; tek kural ikisinin ortasına düşer.
    # Kare böylece dolar ve filigran boş alanda tek başına kalmaz.
    blok_h = 292
    blok_y = yer["alt"] - 24 - blok_h
    draw.line([(kenar, y + (blok_y - y) // 2), (kenar + gen, y + (blok_y - y) // 2)],
              fill=p["cizgi"], width=1)

    by = blok_y
    draw.text((kenar, by), "DOĞRUDAN HAT", font=mi._font_yukle(mi.FONT_MONO_BOLD, 17), fill=p["vurgu"])
    by += 30
    draw.text((kenar, by), ICERIK["telefon"], font=mi._font_yukle(mi.FONT_MONO_BOLD, 54), fill=p["ana"])
    by += 82
    draw.text((kenar, by), f"{ICERIK['isim']}  ·  {ICERIK['unvan']}",
              font=mi._font_yukle(mi.FONT_SANS_SEMIBOLD, 24), fill=p["ana"])
    by += 40
    draw.text((kenar, by), ICERIK["adres"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 21), fill=p["govde"])
    by += 32
    draw.text((kenar, by), f"{ICERIK['eposta']}  ·  {ICERIK['hesap']}",
              font=mi._font_yukle(mi.FONT_MONO, 19), fill=p["silik"])

    qr = _qr(152)
    if qr:
        canvas.paste(qr, (mi.GENISLIK - kenar - 152, blok_y + 6))
        draw.text((mi.GENISLIK - kenar - 152, blok_y + 166), "KONUM",
                  font=mi._font_yukle(mi.FONT_MONO_BOLD, 13), fill=p["silik"])

    draw.text((kenar, yer["alt"] + 22), ICERIK["yasal"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 16), fill=p["silik"])
    yol.parent.mkdir(parents=True, exist_ok=True); canvas.save(yol, "JPEG", quality=95)
    return yol


# =========================================================================
# B — İKİ SÜTUN KARTVİZİT
#     Düzenleyici ilke: dikey ayraç. Sol kimlik, sağ konum.
#     Kartvizit mantığı — göz iki bloğu yan yana okuyor.
# =========================================================================
def varyant_b(yol: Path) -> Path:
    canvas, draw, p = mi._slayt_cercevesi("kagit", "EDM DANIŞMANLIK", "EDM YAPI & GAYRİMENKUL", "04 / 04")
    yer = mi._yerlesim(); kenar = yer["kenar"]; gen = mi.GENISLIK - 2 * kenar

    y = _baslik_ciz(draw, kenar, yer["ust"] + 30, gen, p)
    y += 16
    f_a, sat = mi._govde_sigdir(ICERIK["aciklama"], mi.FONT_SANS_MEDIUM, 29, 23, gen, 2, draw)
    for s in sat[:2]:
        draw.text((kenar, y), s, font=f_a, fill=p["govde"]); y += int(f_a.size * 1.36)

    # Sütunlar alta yaslanır; ayraç ikisini tam boy ayırır.
    blok_y = yer["alt"] - 24 - 322
    orta = kenar + int(gen * 0.58)
    draw.line([(orta, y + 60), (orta, yer["alt"] - 10)], fill=p["cizgi"], width=1)

    # Sol sütun — kimlik
    sy = blok_y
    draw.text((kenar, sy), "DOĞRUDAN HAT", font=mi._font_yukle(mi.FONT_MONO_BOLD, 16), fill=p["vurgu"])
    sy += 26
    draw.text((kenar, sy), ICERIK["telefon"], font=mi._font_yukle(mi.FONT_MONO_BOLD, 46), fill=p["ana"])
    sy += 66
    draw.text((kenar, sy), ICERIK["isim"], font=mi._font_yukle(mi.FONT_SANS_BOLD, 26), fill=p["ana"])
    sy += 34
    draw.text((kenar, sy), ICERIK["unvan"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 21), fill=p["govde"])
    sy += 46
    draw.text((kenar, sy), ICERIK["eposta"], font=mi._font_yukle(mi.FONT_MONO, 18), fill=p["silik"])
    sy += 26
    draw.text((kenar, sy), ICERIK["hesap"], font=mi._font_yukle(mi.FONT_MONO, 18), fill=p["silik"])

    # Sağ sütun — konum
    gy = blok_y
    sag = orta + 36
    draw.text((sag, gy), "SİLİVRİ MERKEZ OFİS", font=mi._font_yukle(mi.FONT_MONO_BOLD, 16), fill=p["vurgu"])
    gy += 30
    f_ad, ad_sat = mi._govde_sigdir(ICERIK["adres"], mi.FONT_SANS_MEDIUM, 21, 17,
                                    mi.GENISLIK - kenar - sag, 3, draw)
    for s in ad_sat[:3]:
        draw.text((sag, gy), s, font=f_ad, fill=p["govde"]); gy += int(f_ad.size * 1.35)
    qr = _qr(150)
    if qr:
        canvas.paste(qr, (sag, gy + 18))

    draw.text((kenar, yer["alt"] - 4), ICERIK["yasal"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 17), fill=p["silik"])
    yol.parent.mkdir(parents=True, exist_ok=True); canvas.save(yol, "JPEG", quality=95)
    return yol


# =========================================================================
# C — MÜREKKEP AYAK
#     Düzenleyici ilke: zemin kontrastı. Üstte kağıt ve bol boşluk,
#     altta tam genişlik mürekkep blok. Kutu yerine zemin değişimi.
# =========================================================================
def varyant_c(yol: Path) -> Path:
    canvas, draw, p = mi._slayt_cercevesi("kagit", "EDM DANIŞMANLIK", "EDM YAPI & GAYRİMENKUL", "04 / 04")
    yer = mi._yerlesim(); kenar = yer["kenar"]; gen = mi.GENISLIK - 2 * kenar

    y = _baslik_ciz(draw, kenar, yer["ust"] + 110, gen, p, punto=60)
    y += 20
    f_a, sat = mi._govde_sigdir(ICERIK["aciklama"], mi.FONT_SANS_MEDIUM, 30, 24, gen, 2, draw)
    for s in sat[:2]:
        draw.text((kenar, y), s, font=f_a, fill=p["govde"]); y += int(f_a.size * 1.36)

    # Mürekkep ayak — tam genişlik, kenar boşluğu yok (kareyi kesiyor)
    ayak_y = yer["alt_bar"] - 468
    draw.rectangle([(0, ayak_y), (mi.GENISLIK, yer["alt_bar"] - 24)], fill=mi.RENK_MUREKKEP)

    ty = ayak_y + 46
    draw.text((kenar, ty), "DOĞRUDAN HAT", font=mi._font_yukle(mi.FONT_MONO_BOLD, 17), fill=mi.RENK_KIRMIZI_CANLI)
    ty += 28
    draw.text((kenar, ty), ICERIK["telefon"], font=mi._font_yukle(mi.FONT_MONO_BOLD, 54), fill=mi.RENK_BEYAZ)
    ty += 78
    draw.text((kenar, ty), f"{ICERIK['isim']}  ·  {ICERIK['unvan']}",
              font=mi._font_yukle(mi.FONT_SANS_SEMIBOLD, 23), fill=mi.RENK_KURSUN_ACIK)
    ty += 38
    draw.text((kenar, ty), ICERIK["adres"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 20), fill=mi.RENK_KURSUN)
    ty += 30
    draw.text((kenar, ty), f"{ICERIK['eposta']}  ·  {ICERIK['hesap']}",
              font=mi._font_yukle(mi.FONT_MONO, 18), fill=mi.RENK_KURSUN)

    qr = _qr(140, zemin="#121316", muhur="#f4f4f3")
    if qr:
        canvas.paste(qr, (mi.GENISLIK - kenar - 140, ayak_y + 62))

    draw.text((kenar, yer["alt"] + 26), ICERIK["yasal"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 16), fill=p["silik"])
    yol.parent.mkdir(parents=True, exist_ok=True); canvas.save(yol, "JPEG", quality=95)
    return yol


# =========================================================================
# D — PAFTA ŞERİTLERİ
#     Düzenleyici ilke: yatay çizgi ızgarası. Her bilgi bir şerit;
#     solda mono etiket, sağda değer. Marka kimliğindeki rölöve/pafta hissi.
# =========================================================================
def varyant_d(yol: Path) -> Path:
    canvas, draw, p = mi._slayt_cercevesi("kagit", "EDM DANIŞMANLIK", "EDM YAPI & GAYRİMENKUL", "04 / 04")
    yer = mi._yerlesim(); kenar = yer["kenar"]; gen = mi.GENISLIK - 2 * kenar

    y = _baslik_ciz(draw, kenar, yer["ust"] + 26, gen, p, punto=54)
    y += 14
    f_a, sat = mi._govde_sigdir(ICERIK["aciklama"], mi.FONT_SANS_MEDIUM, 28, 23, gen, 2, draw)
    for s in sat[:2]:
        draw.text((kenar, y), s, font=f_a, fill=p["govde"]); y += int(f_a.size * 1.36)

    y += 46
    etiket_x = kenar
    deger_x = kenar + 230
    f_etiket = mi._font_yukle(mi.FONT_MONO_BOLD, 15)

    def serit(etiket: str, deger: str, punto: int, renk, bosluk: int = 58, mono=False) -> None:
        nonlocal y
        draw.line([(kenar, y), (kenar + gen, y)], fill=p["cizgi"], width=1)
        y += 18
        draw.text((etiket_x, y + 8), etiket, font=f_etiket, fill=p["vurgu"])
        f = mi._font_yukle(mi.FONT_MONO_BOLD if mono else mi.FONT_SANS_SEMIBOLD, punto)
        draw.text((deger_x, y), deger, font=f, fill=renk)
        y += bosluk

    # Şeritler kalan yüksekliğe eşit dağıtılır; kare altta boş kalmaz.
    kalan = (yer["alt"] - 160) - y
    pay = max(60, (kalan - 104) // 4)
    serit("TELEFON", ICERIK["telefon"], 42, p["ana"], 104, mono=True)
    serit("DANIŞMAN", f"{ICERIK['isim']} · {ICERIK['unvan']}", 23, p["ana"], pay)
    serit("OFİS", ICERIK["adres"], 21, p["govde"], pay)
    serit("E-POSTA", ICERIK["eposta"], 21, p["govde"], pay)
    serit("SOSYAL", ICERIK["hesap"], 21, p["govde"], pay)
    draw.line([(kenar, y), (kenar + gen, y)], fill=p["cizgi"], width=1)

    qr = _qr(118)
    if qr:
        canvas.paste(qr, (mi.GENISLIK - kenar - 118, y + 20))
        draw.text((kenar, y + 30), "KONUM İÇİN KAREKODU OKUTUN",
                  font=mi._font_yukle(mi.FONT_MONO_BOLD, 15), fill=p["silik"])
        draw.text((kenar, y + 58), ICERIK["yasal"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 16), fill=p["silik"])

    yol.parent.mkdir(parents=True, exist_ok=True); canvas.save(yol, "JPEG", quality=95)
    return yol


# =========================================================================
# E — TEK İŞ: ARANMAK
#     Düzenleyici ilke: tek hakim öğe. Kapanışın işi aranmaktır;
#     numara karenin yıldızı, geri kalan her şey küçük destek metni.
# =========================================================================
def varyant_e(yol: Path) -> Path:
    canvas, draw, p = mi._slayt_cercevesi("kagit", "EDM DANIŞMANLIK", "EDM YAPI & GAYRİMENKUL", "04 / 04")
    yer = mi._yerlesim(); kenar = yer["kenar"]; gen = mi.GENISLIK - 2 * kenar

    y = _baslik_ciz(draw, kenar, yer["ust"] + 24, gen, p, punto=50)

    # Devasa telefon — kareyi tek başına taşıyor
    tel_y = y + 96
    draw.text((kenar, tel_y - 34), "SORUNUZ VARSA DOĞRUDAN ARAYIN",
              font=mi._font_yukle(mi.FONT_MONO_BOLD, 18), fill=p["vurgu"])
    f_tel = mi._font_yukle(mi.FONT_MONO_BOLD, 78)
    draw.text((kenar, tel_y), ICERIK["telefon"], font=f_tel, fill=p["ana"])

    alt = yer["alt"] - 206
    draw.line([(kenar, alt), (kenar + gen, alt)], fill=p["cizgi"], width=1)
    alt += 26
    draw.text((kenar, alt), f"{ICERIK['isim']}  ·  {ICERIK['unvan']}",
              font=mi._font_yukle(mi.FONT_SANS_SEMIBOLD, 23), fill=p["ana"])
    alt += 36
    f_ad, ad_sat = mi._govde_sigdir(ICERIK["adres"], mi.FONT_SANS_MEDIUM, 20, 17, gen - 170, 2, draw)
    for s in ad_sat[:2]:
        draw.text((kenar, alt), s, font=f_ad, fill=p["govde"]); alt += int(f_ad.size * 1.34)
    draw.text((kenar, alt + 6), f"{ICERIK['eposta']}  ·  {ICERIK['hesap']}",
              font=mi._font_yukle(mi.FONT_MONO, 18), fill=p["silik"])

    qr = _qr(124)
    if qr:
        canvas.paste(qr, (mi.GENISLIK - kenar - 124, alt - 74))

    draw.text((kenar, yer["alt"] + 30), ICERIK["yasal"], font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 16), fill=p["silik"])
    yol.parent.mkdir(parents=True, exist_ok=True); canvas.save(yol, "JPEG", quality=95)
    return yol


VARYANTLAR = {
    "A_tek_sutun": varyant_a,
    "B_iki_sutun": varyant_b,
    "C_murekkep_ayak": varyant_c,
    "D_pafta_seritleri": varyant_d,
    "E_tek_is_aranmak": varyant_e,
}


def main() -> int:
    CIKTI.mkdir(parents=True, exist_ok=True)
    for ad, fn in VARYANTLAR.items():
        yol = fn(CIKTI / f"{ad}.jpg")
        print(f"  ✓ {yol.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
