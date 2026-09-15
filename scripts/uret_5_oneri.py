import sys
from pathlib import Path
import qrcode
from PIL import Image, ImageDraw, ImageFilter

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

import src.make_image as mi

GEN, YUK = 1080, 1350
KENAR = 76

RENK_KAGIT = (248, 249, 248)
RENK_KOYU = (20, 22, 26)
RENK_KIRMIZI = (217, 43, 43)
RENK_GRI = (90, 96, 106)
RENK_SILIK = (150, 156, 164)
RENK_CIZGI = (222, 226, 224)

# Load thickened amblem
AMBLEM_KALIN_PATH = KOK / "assets/logos/amblem-kalin.png"

def _bordo_qr(link: str, boyut: int = 140) -> Image.Image:
    q = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=5,
        border=1,
    )
    q.add_data(link)
    q.make(fit=True)
    qr_img = q.make_image(fill_color="#701111", back_color="#ffffff").convert("RGBA")
    qr_img = qr_img.resize((boyut, boyut), Image.Resampling.LANCZOS)

    if AMBLEM_KALIN_PATH.exists():
        emblem = Image.open(AMBLEM_KALIN_PATH).convert("RGBA")
        logo_sz = 44
        emblem = emblem.resize((logo_sz, logo_sz), Image.Resampling.LANCZOS)
        # SIFIR BEYAZ KUTU: Doğrudan ortaya yapıştır
        pos_l = ((boyut - logo_sz) // 2, (boyut - logo_sz) // 2)
        qr_img.paste(emblem, pos_l, emblem)

    return qr_img.convert("RGB")

def _temel_cizim():
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

    return canvas, draw, yer, cizgi_y

def _alt_bilgileri_ciz(canvas, draw, yer):
    # 5. ALTA DAYALI İLETİŞİM BLOĞU (by = 870)
    qr_sz = 140
    qr_x = GEN - KENAR - qr_sz
    by = 870
    
    # 5A. METİN ÖZDOĞAN (42px Bold) & Kurucu Danışman
    draw.text((KENAR, by), "METİN ÖZDOĞAN", font=mi._font_yukle(mi.FONT_SANS_BOLD, 42), fill=RENK_KOYU); by += 50
    draw.text((KENAR, by), "Kurucu Danışman", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 24), fill=RENK_GRI); by += 48

    # 5B. DEV TELEFON NUMARASI & QR ÜST SINIRI
    tel_y = by
    draw.text((KENAR, tel_y), "0536 343 41 97", font=mi._font_yukle(mi.FONT_MONO_BOLD, 68), fill=RENK_KOYU); by += 88

    # 5C. OFİS ADRESİ (Temiz Sans)
    draw.text((KENAR, by), "Alibey Mah. Albay Yunus Dirik Cad. No: 58/A · Silivri / İstanbul", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 21), fill=RENK_GRI); by += 44

    # 5D. WEB SİTESİ & E-POSTA (KIRMIZI ŞIK VEKTÖR İKONLARLA)
    ik_sz = 22
    try:
        web_ik = mi._vektor_ikon_uret("web", ik_sz, RENK_KIRMIZI)
        canvas.paste(web_ik, (KENAR, by + 2), web_ik)
    except Exception:
        pass
    draw.text((KENAR + ik_sz + 10, by), "edmyapigayrimenkul.com", font=mi._font_yukle(mi.FONT_MONO_BOLD, 19), fill=RENK_KOYU)

    web_gen = draw.textbbox((0, 0), "edmyapigayrimenkul.com", font=mi._font_yukle(mi.FONT_MONO_BOLD, 19))[2]
    mail_x = KENAR + ik_sz + 10 + web_gen + 34

    try:
        mail_ik = mi._vektor_ikon_uret("mail", ik_sz, RENK_KIRMIZI)
        canvas.paste(mail_ik, (mail_x, by + 2), mail_ik)
    except Exception:
        pass
    draw.text((mail_x + ik_sz + 10, by), "info@edmyapigayrimenkul.com", font=mi._font_yukle(mi.FONT_MONO, 18), fill=RENK_SILIK)

    # 6. SAĞ TARAF: BORDO & BEYAZ KUTUSUZ QR KOD
    qr_y = tel_y + 4
    qr_img = _bordo_qr("https://maps.google.com/?q=Alibey+Mah+Albay+Yunus+Dirik+Cad+No+58A+Silivri", qr_sz)
    canvas.paste(qr_img, (qr_x, qr_y))

    # QR Altı Ortalanmış Zarif Etiket
    f_lbl = mi._font_yukle(mi.FONT_MONO_BOLD, 11)
    lbl_txt = "OFİS KONUMU // TARA"
    lbl_w = draw.textbbox((0, 0), lbl_txt, font=f_lbl)[2]
    draw.text((qr_x + (qr_sz - lbl_w) // 2, qr_y + qr_sz + 8), lbl_txt, font=f_lbl, fill=RENK_SILIK)

    # 7. YASAL NOT & ALT KURUMSAL BAR
    draw.text((KENAR, yer["alt"] - 14), "Bu içerik genel bilgilendirmedir; bağlayıcı hukuki görüş için avukatınıza danışın.", font=mi._font_yukle(mi.FONT_SANS_MEDIUM, 16), fill=RENK_SILIK)
    draw.text((KENAR, yer["alt_bar"] + 26), "EDM YAPI & GAYRİMENKUL", font=mi._font_yukle(mi.FONT_MONO, 19), fill=RENK_SILIK)
    draw.text((GEN - KENAR - 80, yer["alt_bar"] + 26), "04 / 04", font=mi._font_yukle(mi.FONT_MONO_BOLD, 19), fill=RENK_KIRMIZI)

# -------------------------------------------------------------
# ÖNERİ 1: YÜZEN KAPSÜLLER (FLOATING PILL CHIPS)
# -------------------------------------------------------------
def ciz_oneri_1(hedef: Path):
    canvas, draw, yer, cizgi_y = _temel_cizim()
    y_cta = cizgi_y + 24
    toplam_w = GEN - 2 * KENAR
    gap = 16
    pill_w = (toplam_w - 2 * gap) // 3
    pill_h = 76

    actions = [
        ("bookmark", "KAYDEDİN", "İhtiyaç anında bakın"),
        ("comment", "SORU SORUN", "Yorumda yanıtlayalım"),
        ("follow", "TAKİP EDİN", "Yeni rehberler için"),
    ]
    f_tit = mi._font_yukle(mi.FONT_SANS_BOLD, 19)
    f_sub = mi._font_yukle(mi.FONT_SANS_MEDIUM, 14)
    ik_sz = 34

    for i, (ic_name, tit, sub) in enumerate(actions):
        px = KENAR + i * (pill_w + gap)
        # Kapsül gövdesi (hafif yumuşak arkaplan + ince kenar)
        draw.rounded_rectangle([(px, y_cta), (px + pill_w, y_cta + pill_h)], radius=pill_h//2, fill=(255, 255, 255), outline=RENK_CIZGI, width=1)
        
        tw1 = draw.textbbox((0, 0), tit, font=f_tit)[2]
        tw2 = draw.textbbox((0, 0), sub, font=f_sub)[2]
        max_tw = max(tw1, tw2)
        group_w = ik_sz + 12 + max_tw
        start_x = px + (pill_w - group_w) // 2

        try:
            ik = mi._vektor_ikon_uret(ic_name, ik_sz, RENK_KIRMIZI)
            canvas.paste(ik, (int(start_x), y_cta + (pill_h - ik_sz) // 2), ik)
        except Exception:
            pass

        tx = int(start_x + ik_sz + 12)
        draw.text((tx, y_cta + 16), tit, font=f_tit, fill=RENK_KOYU)
        draw.text((tx, y_cta + 40), sub, font=f_sub, fill=RENK_GRI)

    _alt_bilgileri_ciz(canvas, draw, yer)
    canvas.save(hedef, "JPEG", quality=95)

# -------------------------------------------------------------
# ÖNERİ 2: INSTAGRAM NATIVE ROZETLER (CIRCULAR ICON BADGES)
# -------------------------------------------------------------
def ciz_oneri_2(hedef: Path):
    canvas, draw, yer, cizgi_y = _temel_cizim()
    y_cta = cizgi_y + 24
    bar_w = GEN - 2 * KENAR
    bar_h = 100
    draw.rounded_rectangle([(KENAR, y_cta), (KENAR + bar_w, y_cta + bar_h)], radius=16, fill=(255, 255, 255), outline=RENK_CIZGI, width=1)

    col_w = bar_w / 3
    actions = [
        ("bookmark", "KAYDEDİN", "İhtiyaç anında bakın"),
        ("comment", "SORU SORUN", "Yorumlarda yanıtlayalım"),
        ("follow", "TAKİP EDİN", "Yeni rehberler için"),
    ]
    f_tit = mi._font_yukle(mi.FONT_SANS_BOLD, 21)
    f_sub = mi._font_yukle(mi.FONT_SANS_MEDIUM, 15)
    badge_sz = 48
    ik_sz = 26

    for i, (ic_name, tit, sub) in enumerate(actions):
        col_x = KENAR + (i * col_w)
        if i > 0:
            draw.line([(col_x, y_cta + 18), (col_x, y_cta + bar_h - 18)], fill=RENK_CIZGI, width=1)

        tw1 = draw.textbbox((0, 0), tit, font=f_tit)[2]
        tw2 = draw.textbbox((0, 0), sub, font=f_sub)[2]
        max_tw = max(tw1, tw2)
        group_w = badge_sz + 14 + max_tw
        start_x = col_x + (col_w - group_w) / 2

        # Kırmızımsı rozet çemberi
        bx = int(start_x)
        by_b = int(y_cta + (bar_h - badge_sz) // 2)
        draw.ellipse([(bx, by_b), (bx + badge_sz, by_b + badge_sz)], fill=(253, 240, 240))

        try:
            ik = mi._vektor_ikon_uret(ic_name, ik_sz, RENK_KIRMIZI)
            canvas.paste(ik, (bx + (badge_sz - ik_sz) // 2, by_b + (badge_sz - ik_sz) // 2), ik)
        except Exception:
            pass

        tx = int(start_x + badge_sz + 14)
        draw.text((tx, y_cta + 24), tit, font=f_tit, fill=RENK_KOYU)
        draw.text((tx, y_cta + 52), sub, font=f_sub, fill=RENK_GRI)

    _alt_bilgileri_ciz(canvas, draw, yer)
    canvas.save(hedef, "JPEG", quality=95)

# -------------------------------------------------------------
# ÖNERİ 3: TEK SATIR MİNİMALİST ŞERİT (KOMPAKT & FERAH)
# -------------------------------------------------------------
def ciz_oneri_3(hedef: Path):
    canvas, draw, yer, cizgi_y = _temel_cizim()
    y_cta = cizgi_y + 24
    bar_w = GEN - 2 * KENAR
    bar_h = 64
    draw.rounded_rectangle([(KENAR, y_cta), (KENAR + bar_w, y_cta + bar_h)], radius=14, fill=(255, 255, 255), outline=RENK_CIZGI, width=1)

    col_w = bar_w / 3
    actions = [
        ("bookmark", "Kaydedin"),
        ("comment", "Yorum Yapın"),
        ("follow", "Takip Edin"),
    ]
    f_tit = mi._font_yukle(mi.FONT_SANS_BOLD, 22)
    ik_sz = 26

    for i, (ic_name, tit) in enumerate(actions):
        col_x = KENAR + (i * col_w)
        if i > 0:
            draw.line([(col_x, y_cta + 14), (col_x, y_cta + bar_h - 14)], fill=RENK_CIZGI, width=1)

        tw = draw.textbbox((0, 0), tit, font=f_tit)[2]
        group_w = ik_sz + 12 + tw
        start_x = col_x + (col_w - group_w) / 2

        try:
            ik = mi._vektor_ikon_uret(ic_name, ik_sz, RENK_KIRMIZI)
            canvas.paste(ik, (int(start_x), y_cta + (bar_h - ik_sz) // 2), ik)
        except Exception:
            pass

        tx = int(start_x + ik_sz + 12)
        draw.text((tx, y_cta + 18), tit, font=f_tit, fill=RENK_KOYU)

    _alt_bilgileri_ciz(canvas, draw, yer)
    canvas.save(hedef, "JPEG", quality=95)

# -------------------------------------------------------------
# ÖNERİ 4: ASİMETRİK KAHRAMAN KART (KAYDET ÖNCELİKLİ)
# -------------------------------------------------------------
def ciz_oneri_4(hedef: Path):
    canvas, draw, yer, cizgi_y = _temel_cizim()
    y_cta = cizgi_y + 24
    toplam_w = GEN - 2 * KENAR
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

    _alt_bilgileri_ciz(canvas, draw, yer)
    canvas.save(hedef, "JPEG", quality=95)

# -------------------------------------------------------------
# ÖNERİ 5: 3 BAĞIMSIZ DİKEY MİNİ-KART (APPLE STYLE GRID)
# -------------------------------------------------------------
def ciz_oneri_5(hedef: Path):
    canvas, draw, yer, cizgi_y = _temel_cizim()
    y_cta = cizgi_y + 24
    toplam_w = GEN - 2 * KENAR
    gap = 16
    card_w = (toplam_w - 2 * gap) // 3
    card_h = 124

    actions = [
        ("bookmark", "KAYDEDİN", "İhtiyaç anında bakın"),
        ("comment", "SORU SORUN", "Yorumlarda yanıtlayalım"),
        ("follow", "TAKİP EDİN", "Yeni rehberler için"),
    ]
    f_tit = mi._font_yukle(mi.FONT_SANS_BOLD, 20)
    f_sub = mi._font_yukle(mi.FONT_SANS_MEDIUM, 14)
    ik_sz = 34

    for i, (ic_name, tit, sub) in enumerate(actions):
        cx = KENAR + i * (card_w + gap)
        draw.rounded_rectangle([(cx, y_cta), (cx + card_w, y_cta + card_h)], radius=16, fill=(255, 255, 255), outline=RENK_CIZGI, width=1)

        # Ortalanmış dikey düzen
        try:
            ik = mi._vektor_ikon_uret(ic_name, ik_sz, RENK_KIRMIZI)
            canvas.paste(ik, (int(cx + (card_w - ik_sz) // 2), y_cta + 18), ik)
        except Exception:
            pass

        tw1 = draw.textbbox((0, 0), tit, font=f_tit)[2]
        tw2 = draw.textbbox((0, 0), sub, font=f_sub)[2]
        draw.text((cx + (card_w - tw1) // 2, y_cta + 62), tit, font=f_tit, fill=RENK_KOYU)
        draw.text((cx + (card_w - tw2) // 2, y_cta + 90), sub, font=f_sub, fill=RENK_GRI)

    _alt_bilgileri_ciz(canvas, draw, yer)
    canvas.save(hedef, "JPEG", quality=95)

if __name__ == "__main__":
    OUT_DIR = Path("/Users/macbook/.gemini/antigravity/brain/10849f7b-49c8-44a9-a6a4-91a15b9d0075")
    ciz_oneri_1(OUT_DIR / "oneri_1_yuzen_kapsuller.jpg")
    ciz_oneri_2(OUT_DIR / "oneri_2_instagram_native.jpg")
    ciz_oneri_3(OUT_DIR / "oneri_3_tek_satir_minimal.jpg")
    ciz_oneri_4(OUT_DIR / "oneri_4_asimetrik_kahraman.jpg")
    ciz_oneri_5(OUT_DIR / "oneri_5_mini_kartlar.jpg")
    print("5 öneri başarıyla oluşturuldu!")
