#!/usr/bin/env python3
"""
scripts/uret_claude_ideal_denge.py
Claude Editoryal Kapanış — İdeal Denge (Sweet Spot / Golden Ratio)
Ne sıkış tıkış, ne de boş uçurum. Ferah, havadar, yalın ve kusursuz okunabilir.
"""

from pathlib import Path
import sys
from PIL import Image, ImageDraw

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import make_image as mi, config
import qrcode

GEN = mi.GENISLIK   # 1080
YUK = mi.YUKSEKLIK  # 1350
KENAR = 76

RENK_KAGIT = (246, 245, 241)
RENK_KOYU = (18, 20, 24)
RENK_KIRMIZI = (217, 43, 43)
RENK_GRI = (84, 88, 94)
RENK_SILIK = (136, 140, 146)
RENK_CIZGI = (220, 224, 220)

CIKTI_YOLU = Path("/Users/macbook/.gemini/antigravity/brain/10849f7b-49c8-44a9-a6a4-91a15b9d0075/kapanis_claude_ideal_denge.jpg")


def ciz_ideal_denge():
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    canvas = mi._filigran_uygula(canvas, acik_zemin=True)
    draw = ImageDraw.Draw(canvas)
    yer = mi._yerlesim()

    # 1. Üst Bar: Hafif şık rozet & Temiz Logo
    rozet_txt = "TAHLİYE REHBERİ // BOŞ TARİH"
    f_roz = mi._font_yukle(mi.FONT_MONO_BOLD, 15)
    rw = draw.textbbox((0, 0), rozet_txt, font=f_roz)[2]
    draw.rounded_rectangle([(KENAR, yer["kronik_ust"]), (KENAR + rw + 28, yer["kronik_ust"] + 34)], radius=17, fill=(234, 236, 234))
    draw.text((KENAR + 14, yer["kronik_ust"] + 9), rozet_txt, font=f_roz, fill=RENK_KOYU)

    mi._logo_yerlestir(canvas, beyaz=False, y=yer["kronik_ust"] - 5, lw=224, golge=False)

    # 2. Üst Blok (Başlık + Açıklama + Kaydet): Ferah ve zarif
    y = yer["ust"] + 45

    f_b = mi._font_yukle(mi.FONT_FRAUNCES, 58)
    draw.text((KENAR, y), "Doğru adımlarla", font=f_b, fill=RENK_KOYU); y += 68
    draw.text((KENAR, y), "GÜVENLİ KİRALAMA", font=f_b, fill=RENK_KIRMIZI); y += 82

    f_a = mi._font_yukle(mi.FONT_SANS_MEDIUM, 28)
    draw.text((KENAR, y), "Silivri ve Trakya genelinde mülk yönetimi ve hukuki", font=f_a, fill=RENK_GRI); y += 40
    draw.text((KENAR, y), "süreçlerinizde profesyonel kadromuzla yanınızdayız.", font=f_a, fill=RENK_GRI); y += 44

    # Kaydetme İmzası (Claude'un orijinal zarafeti: kutusuz, saf tipografi)
    try:
        b_ik = mi._vektor_ikon_uret("bookmark", 18, RENK_KIRMIZI)
        canvas.paste(b_ik, (KENAR, y + 1), b_ik)
    except Exception:
        pass
    draw.text((KENAR + 26, y), "BU REHBERİ KAYDEDİN · İHTİYAÇ ANINDA ELİNİZİN ALTINDA OLSUN", font=mi._font_yukle(mi.FONT_MONO_BOLD, 15), fill=RENK_KOYU)

    # 3. Ortada Tek, Sakin Kılcal Ayraç Çizgisi (Dengeli Nefes Alanı: Üstte ~100px, Altta ~90px)
    cizgi_y = 610
    draw.line([(KENAR, cizgi_y), (GEN - KENAR, cizgi_y)], fill=RENK_CIZGI, width=1)

    # 4. Alt İletişim Bloğu: Havadar, Dengeli, Sade
    # Sol Sütun Genişliği
    qr_sz = 160
    qr_x = GEN - KENAR - qr_sz
    max_sol_w = qr_x - KENAR - 36

    by = 690
    draw.text((KENAR, by), "DOĞRUDAN HAT", font=mi._font_yukle(mi.FONT_MONO_BOLD, 16), fill=RENK_KIRMIZI); by += 32
    draw.text((KENAR, by), "0536 343 41 97", font=mi._font_yukle(mi.FONT_MONO_BOLD, 54), fill=RENK_KOYU); by += 76

    draw.text((KENAR, by), "METİN ÖZDOĞAN  ·  Kurucu Danışman", font=mi._font_yukle(mi.FONT_SANS_BOLD, 26), fill=RENK_KOYU); by += 40
    draw.text((KENAR, by), "Alibey Mah. Albay Yunus Dirik Cad. No: 58/A · Silivri / İstanbul", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 21), fill=RENK_GRI); by += 36
    draw.text((KENAR, by), "edmyapigayrimenkul.com   ·   info@edmyapigayrimenkul.com", font=mi._font_yukle(mi.FONT_MONO, 18), fill=RENK_SILIK)

    # Sağ Taraf: QR Kod ve Ortalanmış Şık Etiket
    qr_y = 705
    q = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=4, border=1)
    q.add_data("https://maps.google.com/?q=Alibey+Mah+Albay+Yunus+Dirik+Cad+No+58A+Silivri")
    q.make(fit=True)
    qr_img = q.make_image(fill_color="#121418", back_color="#ffffff").convert("RGB")
    qr_img = qr_img.resize((qr_sz, qr_sz), Image.Resampling.LANCZOS)
    canvas.paste(qr_img, (qr_x, qr_y))

    f_lbl = mi._font_yukle(mi.FONT_MONO_BOLD, 12)
    lbl_txt = "OFİS KONUMU // TARA"
    lbl_w = draw.textbbox((0, 0), lbl_txt, font=f_lbl)[2]
    draw.text((qr_x + (qr_sz - lbl_w) // 2, qr_y + qr_sz + 10), lbl_txt, font=f_lbl, fill=RENK_SILIK)

    # 5. Yasal Not & Alt Bar
    draw.text((KENAR, yer["alt"] - 14), "Bu içerik genel bilgilendirmedir; bağlayıcı hukuki görüş için avukatınıza danışın.", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 16), fill=RENK_SILIK)
    draw.text((KENAR, yer["alt_bar"] + 26), "EDM YAPI & GAYRİMENKUL", font=mi._font_yukle(mi.FONT_MONO, 19), fill=RENK_SILIK)
    draw.text((GEN - KENAR - 80, yer["alt_bar"] + 26), "04 / 04", font=mi._font_yukle(mi.FONT_MONO_BOLD, 19), fill=RENK_KIRMIZI)

    CIKTI_YOLU.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(CIKTI_YOLU, "JPEG", quality=95)
    print(f"✓ İdeal Denge revizesi kaydedildi: {CIKTI_YOLU}")
    return CIKTI_YOLU

if __name__ == "__main__":
    ciz_ideal_denge()
