"""
scripts/test_dailybrief_style.py — EDM Daily Brief Tarzı Haber Postu Denemesi
Instabot / DailyBrief tasarım dilini EDM kurumsal kimliğiyle birleştirir.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
import requests
import io

GENISLIK = 1080
YUKSEKLIK = 1350
KENAR = 65

KOK = Path(__file__).resolve().parent.parent

# Fontlar
FONT_BASLIK = ImageFont.truetype(str(KOK / "assets/fonts/Fraunces.ttf"), 54)
FONT_BASLIK_SANS = ImageFont.truetype(str(KOK / "assets/fonts/IBMPlexSans[wdth,wght].ttf"), 50)
FONT_OZET = ImageFont.truetype(str(KOK / "assets/fonts/IBMPlexSans[wdth,wght].ttf"), 28)
FONT_ROZET = ImageFont.truetype(str(KOK / "assets/fonts/IBMPlexMono-Bold.ttf"), 20)
FONT_ALT = ImageFont.truetype(str(KOK / "assets/fonts/IBMPlexMono.ttf"), 20)

# Renkler
KIRMIZI = (240, 0, 13)
BEYAZ = (255, 255, 255)
KURSUN = (160, 165, 175)
MUREKKEP = (14, 15, 18)

def main():
    # 1. Arka Plan (Lüks modern mimari görseli)
    bg_url = "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1080&q=85"
    res = requests.get(bg_url, headers={"User-Agent": "Mozilla/5.0"})
    foto = Image.open(io.BytesIO(res.content)).convert("RGB")
    canvas = ImageOps.fit(foto, (GENISLIK, YUKSEKLIK), Image.Resampling.LANCZOS)

    # 2. DailyBrief Tarzı Dinamik Perde (Alttan yukarı derin karartma)
    perde = Image.new("RGBA", (GENISLIK, YUKSEKLIK), (0, 0, 0, 0))
    p_draw = ImageDraw.Draw(perde)

    # Üst köşe hafif vignette (Logo ve rozetin parlaması için)
    for y in range(250):
        alfa = int(140 * ((250 - y) / 250) ** 1.5)
        p_draw.line([(0, y), (GENISLIK, y)], fill=(10, 12, 16, alfa))

    # Alt perde (y=480'den aşağıya doğru karartma)
    serit_basi = 480
    serit_tam = 820
    for y in range(serit_basi, YUKSEKLIK):
        if y < serit_tam:
            alfa = int(245 * ((y - serit_basi) / (serit_tam - serit_basi)) ** 1.4)
        else:
            alfa = 245
        p_draw.line([(0, y), (GENISLIK, y)], fill=(12, 14, 18, alfa))

    canvas = Image.alpha_composite(canvas.convert("RGBA"), perde).convert("RGB")
    draw = ImageDraw.Draw(canvas)

    # 3. Üst Blok (Rozet + Logo)
    # Kırmızı rozet
    r_text = "GÜNCEL GELİŞME // KONUT & ARSA"
    bbox_r = draw.textbbox((0, 0), r_text, font=FONT_ROZET)
    rw = bbox_r[2] - bbox_r[0]
    draw.rounded_rectangle([(KENAR, 60), (KENAR + rw + 32, 106)], radius=4, fill=KIRMIZI)
    draw.text((KENAR + 16, 73), r_text, font=FONT_ROZET, fill=BEYAZ)

    # Sağ üst logo
    logo_path = KOK / "assets/logos/logo-yatay-acik.png"
    if logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA")
        lw = 230
        lh = int(logo.height * (lw / logo.width))
        logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)
        canvas.paste(logo, (GENISLIK - KENAR - lw, 58), logo)

    # 4. Başlık ve Özet
    baslik = "Konut Kredisi Faizlerinde İndirim Beklentisi:\nFiyatlar ve Talep Nasıl Etkilenecek?"
    ozet = (
        "Merkez Bankası'nın son piyasa analizleri ve sektör temsilcilerinin açıklamalarına göre, "
        "kredi faizlerindeki olası gevşeme ertelenen konut talebini yeniden harekete geçirebilir. "
        "Yatırımcıların arsa ve konut alımında dikkat etmesi gereken kritik göstergeler incelendi."
    )

    # Metni sarma
    def sar(metin, font, max_w):
        kelimeler = metin.split()
        satirlar, current = [], []
        for k in kelimeler:
            test = " ".join(current + [k])
            w = draw.textbbox((0, 0), test, font=font)[2]
            if w <= max_w:
                current.append(k)
            else:
                if current: satirlar.append(" ".join(current))
                current = [k]
        if current: satirlar.append(" ".join(current))
        return satirlar

    # 5. Difüzyon Gölgesi ile Başlık (DailyBrief İmzası)
    b_satirlar = baslik.split("\n")
    y_baslik = 740

    golge = Image.new("RGBA", (GENISLIK, YUKSEKLIK), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(golge)
    gy = y_baslik
    for b in b_satirlar:
        g_draw.text((KENAR, gy + 4), b, font=FONT_BASLIK, fill=(0, 0, 0, 240))
        gy += 66
    golge = golge.filter(ImageFilter.GaussianBlur(12))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), golge).convert("RGB")
    draw = ImageDraw.Draw(canvas)

    by = y_baslik
    for b in b_satirlar:
        draw.text((KENAR, by), b, font=FONT_BASLIK, fill=BEYAZ)
        by += 66

    # 6. Özet Metin
    o_satirlar = sar(ozet, FONT_OZET, GENISLIK - (2 * KENAR))
    oy = by + 26
    for o in o_satirlar[:4]:
        draw.text((KENAR, oy), o, font=FONT_OZET, fill=(230, 235, 242))
        oy += 42

    # 7. Alt Bilgi Şeridi (DailyBrief Stili Ayrım + Kaynak + İkon/Kanal)
    alt_y = YUKSEKLIK - 110
    draw.line([(KENAR, alt_y), (GENISLIK - KENAR, alt_y)], fill=(50, 55, 65), width=1)
    
    tarih_kaynak = "EDM ARAŞTIRMA  //  08 EYLÜL 2026"
    draw.text((KENAR, alt_y + 25), tarih_kaynak, font=FONT_ALT, fill=KURSUN)

    kanal_metni = "@edmyapigayrimenkul"
    kw = draw.textbbox((0, 0), kanal_metni, font=FONT_ALT)[2]
    draw.text((GENISLIK - KENAR - kw, alt_y + 25), kanal_metni, font=FONT_ALT, fill=BEYAZ)

    out_file = KOK / "data/output/dailybrief_edm_test.jpg"
    canvas.save(out_file, "JPEG", quality=95)
    print("Daily Brief Style Test Created:", out_file)

if __name__ == "__main__":
    main()
