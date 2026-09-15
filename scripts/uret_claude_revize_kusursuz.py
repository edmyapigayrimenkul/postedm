#!/usr/bin/env python3
"""
scripts/uret_claude_revize_kusursuz.py
Claude Editoryal Kapanış Tasarımı — Kusursuz Geometrik & Tipografik Revizyon
Tüm boşluklar, orantısızlıklar ve hizalama hataları giderilmiş nihai editoryal şaheser.
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
KENAR = 72

RENK_KAGIT = (246, 245, 241)
RENK_KOYU = (18, 20, 24)
RENK_KIRMIZI = (217, 43, 43)
RENK_GRI = (78, 82, 88)
RENK_SILIK = (130, 134, 140)
RENK_CIZGI = (222, 226, 222)

CIKTI_YOLU = Path("/Users/macbook/.gemini/antigravity/brain/10849f7b-49c8-44a9-a6a4-91a15b9d0075/kapanis_claude_revize_kusursuz.jpg")


def ciz_kusursuz_claude():
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    canvas = mi._filigran_uygula(canvas, acik_zemin=True)
    draw = ImageDraw.Draw(canvas)
    yer = mi._yerlesim()

    # 1. Üst Rozet & Logo (Ferah, Kutu Lekesi Olmayan Zarif Rozet)
    rozet_txt = "TAHLİYE REHBERİ // BOŞ TARİH"
    f_roz = mi._font_yukle(mi.FONT_MONO_BOLD, 15)
    rw = draw.textbbox((0, 0), rozet_txt, font=f_roz)[2]
    # Siyah ağır kutu yerine, editoryal koyu füme / şık kapsül
    draw.rounded_rectangle([(KENAR, yer["kronik_ust"]), (KENAR + rw + 28, yer["kronik_ust"] + 34)], radius=17, fill=(232, 235, 232))
    draw.text((KENAR + 14, yer["kronik_ust"] + 9), rozet_txt, font=f_roz, fill=RENK_KOYU)

    # Sağ Üst Logo (Gölgesiz, Temiz)
    mi._logo_yerlestir(canvas, beyaz=False, y=yer["kronik_ust"] - 5, lw=224, golge=False)

    # 2. Başlık & Açıklama (Doğal Editoryal Akış)
    y = yer["ust"] + 15
    f_b = mi._font_yukle(mi.FONT_FRAUNCES, 56)
    draw.text((KENAR, y), "Doğru adımlarla", font=f_b, fill=RENK_KOYU); y += 64
    draw.text((KENAR, y), "GÜVENLİ KİRALAMA", font=f_b, fill=RENK_KIRMIZI); y += 76

    f_a = mi._font_yukle(mi.FONT_SANS_MEDIUM, 28)
    draw.text((KENAR, y), "Silivri ve Trakya genelinde mülk yönetimi ve hukuki", font=f_a, fill=RENK_GRI); y += 40
    draw.text((KENAR, y), "süreçlerinizde profesyonel kadromuzla yanınızdayız.", font=f_a, fill=RENK_GRI); y += 52

    # 3. Kaydetme Çağrısı (Belirgin Editoryal Köprü)
    k_metin = "BU REHBERİ KAYDEDİN · İHTİYAÇ ANINDA ELİNİZİN ALTINDA OLSUN"
    f_k = mi._font_yukle(mi.FONT_MONO_BOLD, 15)
    kw = draw.textbbox((0, 0), k_metin, font=f_k)[2]
    pad_k = 20
    draw.rounded_rectangle([(KENAR, y), (KENAR + kw + (pad_k * 2) + 24, y + 42)], radius=21, fill=(236, 239, 236))
    try:
        b_ik = mi._vektor_ikon_uret("bookmark", 18, RENK_KIRMIZI)
        canvas.paste(b_ik, (KENAR + pad_k, y + 12), b_ik)
    except Exception:
        pass
    draw.text((KENAR + pad_k + 24, y + 13), k_metin, font=f_k, fill=RENK_KOYU)
    y += 72

    # 4. Ortadaki Kılcal Ayraç (Homojen Geçiş Çizgisi)
    draw.line([(KENAR, y), (GEN - KENAR, y)], fill=RENK_CIZGI, width=1)
    y += 42

    # 5. Danışman & Telefon İkilisi (Gözün İlk Kilitleneceği Güçlü Otorite Bloğu)
    # 5A: Danışman Kimliği
    draw.text((KENAR, y), "YETKİLİ KURUCU DANIŞMAN", font=mi._font_yukle(mi.FONT_MONO_BOLD, 15), fill=RENK_KIRMIZI); y += 26
    draw.text((KENAR, y), "METİN ÖZDOĞAN", font=mi._font_yukle(mi.FONT_SANS_BOLD, 40), fill=RENK_KOYU); y += 48
    draw.text((KENAR, y), "EDM Yapı & Gayrimenkul · Silivri ve Trakya Bölge Sorumlusu", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 22), fill=RENK_GRI); y += 48

    # 5B: Doğrudan İletişim Hattı (Net, Baskın ve İsimle Orantılı)
    draw.text((KENAR, y), "DOĞRUDAN DANIŞMANLIK & İLETİŞİM HATTI", font=mi._font_yukle(mi.FONT_MONO_BOLD, 15), fill=RENK_KIRMIZI); y += 28
    draw.text((KENAR, y), "0536 343 41 97", font=mi._font_yukle(mi.FONT_MONO_BOLD, 60), fill=RENK_KOYU); y += 72
    draw.text((KENAR, y), "Haftanın 7 günü arayabilir veya WhatsApp üzerinden yazabilirsiniz.", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 19), fill=RENK_SILIK); y += 46

    # 6. Alt Yatay Kılcal Ayraç (İletişim Detayları ve QR Alanı)
    draw.line([(KENAR, y), (GEN - KENAR, y)], fill=RENK_CIZGI, width=1)
    y += 34

    # 7. Alt Bilgi Izgarası: Sol Taraf Adres/Web/Mail — Sağ Taraf Mükemmel Hizalı QR
    alt_alani_y = y
    qr_sz = 168
    qr_x = GEN - KENAR - qr_sz
    qr_y = alt_alani_y + 4

    # Sol Taraf Bilgileri
    ay = alt_alani_y
    draw.text((KENAR, ay), "OFİS ADRESİ", font=mi._font_yukle(mi.FONT_MONO_BOLD, 13), fill=RENK_KIRMIZI); ay += 22
    draw.text((KENAR, ay), "Alibey Mah. Albay Yunus Dirik Cad. No: 58/A · Silivri / İstanbul", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 20), fill=RENK_KOYU); ay += 36

    draw.text((KENAR, ay), "DİJİTAL ERİŞİM & RESMİ YAZIŞMA", font=mi._font_yukle(mi.FONT_MONO_BOLD, 13), fill=RENK_KIRMIZI); ay += 22
    draw.text((KENAR, ay), "edmyapigayrimenkul.com   ·   info@edmyapigayrimenkul.com", font=mi._font_yukle(mi.FONT_MONO, 18), fill=RENK_KOYU); ay += 26
    draw.text((KENAR, ay), "@edmyapigayrimenkul", font=mi._font_yukle(mi.FONT_MONO, 17), fill=RENK_SILIK)

    # Sağ Taraf: QR Kod ve Tam Matematiksel Ortalanmış Etiket
    q = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=4, border=1)
    q.add_data("https://maps.google.com/?q=Alibey+Mah+Albay+Yunus+Dirik+Cad+No+58A+Silivri")
    q.make(fit=True)
    qr_img = q.make_image(fill_color="#121418", back_color="#ffffff").convert("RGB")
    qr_img = qr_img.resize((qr_sz, qr_sz), Image.Resampling.LANCZOS)
    canvas.paste(qr_img, (qr_x, qr_y))

    f_lbl = mi._font_yukle(mi.FONT_MONO_BOLD, 12)
    lbl_txt = "OFİS KONUMU // TARA"
    lbl_w = draw.textbbox((0, 0), lbl_txt, font=f_lbl)[2]
    # QR kodun tam altına ortalanmış etiket
    draw.text((qr_x + (qr_sz - lbl_w) // 2, qr_y + qr_sz + 8), lbl_txt, font=f_lbl, fill=RENK_SILIK)

    # 8. Yasal Not (Tampon Güvenliği)
    draw.text((KENAR, yer["alt"] - 14), "Bu içerik genel bilgilendirmedir; bağlayıcı hukuki görüş için avukatınıza danışın.", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 16), fill=RENK_SILIK)

    # 9. En Alt Kurumsal Bar
    draw.text((KENAR, yer["alt_bar"] + 26), "EDM YAPI & GAYRİMENKUL", font=mi._font_yukle(mi.FONT_MONO, 19), fill=RENK_SILIK)
    draw.text((GEN - KENAR - 80, yer["alt_bar"] + 26), "04 / 04", font=mi._font_yukle(mi.FONT_MONO_BOLD, 19), fill=RENK_KIRMIZI)

    CIKTI_YOLU.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(CIKTI_YOLU, "JPEG", quality=95)
    print(f"✓ Kusursuz revize çıktı kaydedildi: {CIKTI_YOLU}")
    return CIKTI_YOLU

if __name__ == "__main__":
    ciz_kusursuz_claude()
