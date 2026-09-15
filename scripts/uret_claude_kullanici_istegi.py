#!/usr/bin/env python3
"""
scripts/uret_claude_kullanici_istegi.py
Kullanıcının Net Revizeleri:
1. "DOĞRUDAN HAT" yazısı TAMAMEN kaldırıldı.
2. İletişim bloğu alta dayalı (docked to bottom). Ortada lüks negatif alan.
3. Kırmızı web ve mail vektör ikonları eklendi.
4. METİN ÖZDOĞAN (42px) ve Telefon Numarası (68px) çok daha büyük ve baskın.
5. Kırmızı renkte, ortasında EDM amblemi bulunan yüksek çözünürlüklü QR kod.
6. "BU REHBERİ KAYDEDİN" metni daha ikna edici, otoriter ve belirgin (22px).
"""

from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageOps
import qrcode

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import make_image as mi, config

GEN = mi.GENISLIK   # 1080
YUK = mi.YUKSEKLIK  # 1350
KENAR = 76

RENK_KAGIT = (246, 245, 241)
RENK_KOYU = (18, 20, 24)
RENK_KIRMIZI = (217, 43, 43)
RENK_GRI = (84, 88, 94)
RENK_SILIK = (136, 140, 146)
RENK_CIZGI = (222, 224, 220)

CIKTI_YOLU = Path("/Users/macbook/.gemini/antigravity/brain/10849f7b-49c8-44a9-a6a4-91a15b9d0075/kapanis_claude_kullanici_ozel.jpg")


def _bordo_amblemli_qr(link: str, boyut: int = 200) -> Image.Image:
    """Koyu zengin bordo (#7A0D0D), merkezinde taşmayan sıkı beyaz zeminli kalın EDM amblemi olan şık QR kod üretir."""
    q = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=5,
        border=1,
    )
    q.add_data(link)
    q.make(fit=True)
    qr_img = q.make_image(fill_color="#7A0D0D", back_color="#ffffff").convert("RGBA")
    qr_img = qr_img.resize((boyut, boyut), Image.Resampling.LANCZOS)

    # Merkez amblem (Taşmayan sıkı beyaz zemin ve ekstra kalın logo)
    logo_yolu = KOK / "assets/logos/amblem-kalin.png"
    if not logo_yolu.exists():
        logo_yolu = KOK / "assets/logos/amblem.png"

    if logo_yolu.exists():
        try:
            emblem = Image.open(logo_yolu).convert("RGBA")
            logo_sz = 60
            sq_sz = 66
            sq_mask = Image.new("RGBA", (sq_sz, sq_sz), (0, 0, 0, 0))
            d_sq = ImageDraw.Draw(sq_mask)
            d_sq.rounded_rectangle([(0, 0), (sq_sz - 1, sq_sz - 1)], radius=12, fill=(255, 255, 255, 255))
            pos_s = ((boyut - sq_sz) // 2, (boyut - sq_sz) // 2)
            qr_img.paste(sq_mask, pos_s, sq_mask)

            emblem = emblem.resize((logo_sz, logo_sz), Image.Resampling.LANCZOS)
            pos_l = ((boyut - logo_sz) // 2, (boyut - logo_sz) // 2)
            qr_img.paste(emblem, pos_l, emblem)
        except Exception:
            pass

    return qr_img.convert("RGB")


def ciz():
    canvas = Image.new("RGB", (GEN, YUK), RENK_KAGIT)
    canvas = mi._filigran_uygula(canvas, acik_zemin=True)
    draw = ImageDraw.Draw(canvas)
    yer = mi._yerlesim()

    # 1. Üst Bar: Zarif Kapsül Rozet & Temiz Logo
    rozet_txt = "TAHLİYE REHBERİ // BOŞ TARİH"
    f_roz = mi._font_yukle(mi.FONT_MONO_BOLD, 15)
    rw = draw.textbbox((0, 0), rozet_txt, font=f_roz)[2]
    draw.rounded_rectangle([(KENAR, yer["kronik_ust"]), (KENAR + rw + 28, yer["kronik_ust"] + 34)], radius=17, fill=(234, 236, 234))
    draw.text((KENAR + 14, yer["kronik_ust"] + 9), rozet_txt, font=f_roz, fill=RENK_KOYU)

    mi._logo_yerlestir(canvas, beyaz=False, y=yer["kronik_ust"] - 5, lw=224, golge=False)

    # 2. Üst Editoryal Başlık Bloğu (ÇİZGİNİN ÜSTÜNDE)
    y = yer["ust"] + 30
    f_b = mi._font_yukle(mi.FONT_FRAUNCES, 60)
    draw.text((KENAR, y), "Doğru adımlarla", font=f_b, fill=RENK_KOYU); y += 70
    draw.text((KENAR, y), "GÜVENLİ KİRALAMA", font=f_b, fill=RENK_KIRMIZI); y += 84

    f_a = mi._font_yukle(mi.FONT_SANS_MEDIUM, 29)
    draw.text((KENAR, y), "Silivri ve Trakya genelinde mülk yönetimi ve hukuki", font=f_a, fill=RENK_GRI); y += 42
    draw.text((KENAR, y), "süreçlerinizde profesyonel kadromuzla yanınızdayız.", font=f_a, fill=RENK_GRI); y += 42

    # 3. EKRANIN ORTASINDAKİ YATAY ÇİZGİ
    cizgi_y = 525
    draw.line([(KENAR, cizgi_y), (GEN - KENAR, cizgi_y)], fill=RENK_CIZGI, width=1)

    # 4. ASİMETRİK KAHRAMAN SOSYAL ETKİLEŞİM ALANI (ÖNERİ 4)
    y_cta = cizgi_y + 24
    toplam_w = GEN - (2 * KENAR)
    gap = 18
    hero_w = 540
    right_w = toplam_w - hero_w - gap
    card_h = 104

    # Sol Kahraman Kart (Kaydet)
    draw.rounded_rectangle([(KENAR, y_cta), (KENAR + hero_w, y_cta + card_h)], radius=16, fill=(255, 255, 255), outline=RENK_CIZGI, width=1)
    # Sol kenar kırmızı şerit vurgusu
    draw.rounded_rectangle([(KENAR, y_cta), (KENAR + 6, y_cta + card_h)], radius=3, fill=RENK_KIRMIZI)

    ik_sz = 38
    try:
        ik = mi._vektor_ikon_uret("bookmark", ik_sz, RENK_KIRMIZI)
        canvas.paste(ik, (KENAR + 24, y_cta + (card_h - ik_sz) // 2), ik)
    except Exception:
        pass

    tx = KENAR + 24 + ik_sz + 16
    draw.text((tx, y_cta + 24), "BU REHBERİ KAYDEDİN", font=mi._font_yukle(mi.FONT_SANS_BOLD, 23), fill=RENK_KOYU)
    draw.text((tx, y_cta + 56), "İleride hukuki risk yaşamamak için saklayın.", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 16), fill=RENK_GRI)

    # Sağ İkili Sosyal Kapsüller (üst üste)
    rx = KENAR + hero_w + gap
    pill_h = 46
    pill_gap = 12
    right_actions = [
        ("comment", "Sorularınızı yorumda sorun", y_cta),
        ("follow", "Yeni rehberler için takip edin", y_cta + pill_h + pill_gap),
    ]
    f_rp = mi._font_yukle(mi.FONT_SANS_BOLD, 17)
    ik_sz_r = 22

    for ic_name, text, py in right_actions:
        draw.rounded_rectangle([(rx, py), (rx + right_w, py + pill_h)], radius=12, fill=(255, 255, 255), outline=RENK_CIZGI, width=1)
        try:
            ik = mi._vektor_ikon_uret(ic_name, ik_sz_r, RENK_KIRMIZI)
            canvas.paste(ik, (rx + 16, py + (pill_h - ik_sz_r) // 2), ik)
        except Exception:
            pass
        draw.text((rx + 16 + ik_sz_r + 12, py + 12), text, font=f_rp, fill=RENK_KOYU)

    # 5. ALTA DAYALI (TRULY DOCKED TO BOTTOM) İLETİŞİM BLOĞU (by = 870)
    qr_sz = 200
    qr_x = GEN - KENAR - qr_sz
    by = 870
    
    # 5A. METİN ÖZDOĞAN (42px Bold) & Kurucu Danışman
    draw.text((KENAR, by), "METİN ÖZDOĞAN", font=mi._font_yukle(mi.FONT_SANS_BOLD, 42), fill=RENK_KOYU); by += 50
    draw.text((KENAR, by), "Kurucu Danışman", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 24), fill=RENK_GRI); by += 48

    # Önce web & e-posta genişliğini hesapla (Telefon genişliğini hizalamak için)
    ik_sz_c = 22
    web_gen = draw.textbbox((0, 0), "edmyapigayrimenkul.com", font=mi._font_yukle(mi.FONT_MONO_BOLD, 19))[2]
    mail_x = KENAR + ik_sz_c + 10 + web_gen + 34
    mail_gen = draw.textbbox((0, 0), "info@edmyapigayrimenkul.com", font=mi._font_yukle(mi.FONT_MONO, 18))[2]
    mail_end_x = mail_x + ik_sz_c + 10 + mail_gen

    # 5B. DEV TELEFON NUMARASI (Genişliği e-posta satırının bitişiyle birebir aynı: mail_end_x)
    tel_y = by
    f_tel = mi._font_yukle(mi.FONT_MONO_BOLD, 75)
    tel_parts = ["0536", "343", "41", "97"]
    parts_w = sum(draw.textbbox((0, 0), p, font=f_tel)[2] for p in tel_parts)
    target_w = mail_end_x - KENAR
    gap = (target_w - parts_w) / (len(tel_parts) - 1)

    curr_x = KENAR
    for p in tel_parts:
        draw.text((curr_x, tel_y), p, font=f_tel, fill=RENK_KOYU)
        curr_x += draw.textbbox((0, 0), p, font=f_tel)[2] + gap
    by += 96

    # 5C. OFİS ADRESİ (Temiz Sans)
    draw.text((KENAR, by), "Alibey Mah. Albay Yunus Dirik Cad. No: 58/A · Silivri / İstanbul", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 21), fill=RENK_GRI); by += 44

    # 5D. WEB SİTESİ & E-POSTA (KIRMIZI ŞIK VEKTÖR İKONLARLA!)
    try:
        web_ik = mi._vektor_ikon_uret("web", ik_sz_c, RENK_KIRMIZI)
        canvas.paste(web_ik, (KENAR, by + 2), web_ik)
    except Exception:
        pass
    draw.text((KENAR + ik_sz_c + 10, by), "edmyapigayrimenkul.com", font=mi._font_yukle(mi.FONT_MONO_BOLD, 19), fill=RENK_KOYU)
    
    try:
        mail_ik = mi._vektor_ikon_uret("mail", ik_sz_c, RENK_KIRMIZI)
        canvas.paste(mail_ik, (mail_x, by + 2), mail_ik)
    except Exception:
        pass
    draw.text((mail_x + ik_sz_c + 10, by), "info@edmyapigayrimenkul.com", font=mi._font_yukle(mi.FONT_MONO, 18), fill=RENK_SILIK)

    # 6. SAĞ TARAF: BÜYÜTÜLMÜŞ KOYU BORDO QR KOD (200px, #7A0D0D, TAŞMAYAN SIKI BEYAZ ZEMİN)
    qr_y = tel_y + 2
    qr_img = _bordo_amblemli_qr("https://maps.google.com/?q=Alibey+Mah+Albay+Yunus+Dirik+Cad+No+58A+Silivri", qr_sz)
    canvas.paste(qr_img, (qr_x, qr_y))

    # QR Altı Ortalanmış Zarif Etiket
    f_lbl = mi._font_yukle(mi.FONT_MONO_BOLD, 12)
    lbl_txt = "OFİS KONUMU // TARA"
    lbl_w = draw.textbbox((0, 0), lbl_txt, font=f_lbl)[2]
    draw.text((qr_x + (qr_sz - lbl_w) // 2, qr_y + qr_sz + 8), lbl_txt, font=f_lbl, fill=RENK_SILIK)

    # 7. YASAL NOT & ALT KURUMSAL BAR (Sol alttaki mükerrer EDM yazısı kaldırıldı)
    draw.text((KENAR, yer["alt"] - 14), "Bu içerik genel bilgilendirmedir; bağlayıcı hukuki görüş için avukatınıza danışın.", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 16), fill=RENK_SILIK)
    draw.text((GEN - KENAR - 80, yer["alt_bar"] + 26), "04 / 04", font=mi._font_yukle(mi.FONT_MONO_BOLD, 19), fill=RENK_KIRMIZI)

    CIKTI_YOLU.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(CIKTI_YOLU, "JPEG", quality=95)
    print(f"✓ Kullanıcı özel revizesi kaydedildi: {CIKTI_YOLU}")
    return CIKTI_YOLU

if __name__ == "__main__":
    ciz()
