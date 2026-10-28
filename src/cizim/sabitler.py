"""
src/cizim/sabitler.py — Çizim motoru renkleri, font yolları, tuval ölçüleri ve logolar.
"""

from __future__ import annotations

from pathlib import Path
from .. import config

# Tuval boyutları (Instagram & Threads 4:5 Dikey Oranı)
GENISLIK = 1080
YUKSEKLIK = 1350

# Çoklu tuval ölçüleri tablosu
TUVAL_OLCULERI = {
    "besleme": (1080, 1350),  # 4:5 Instagram Feed Carousel
    "story": (1080, 1920),    # 9:16 Instagram Story
}

# Renk Paleti (EDM Marka Rehberi & Web Sitesi)
RENK_KIRMIZI = (240, 0, 13)       # #f0000d (İmza EDM Kırmızısı)
RENK_KIRMIZI_DERIN = (196, 3, 15) # #c4030f
RENK_MUREKKEP = (18, 19, 22)      # #121316 (Derin Mürekkep Siyahı)
RENK_MUREKKEP_2 = (26, 28, 33)    # #1a1c21 (İkincil Koyu Zemin)
RENK_MUREKKEP_3 = (36, 39, 45)    # #24272d (Kutu Çerçeve Rengi)
RENK_KAGIT = (246, 246, 244)      # #f6f6f4 (Sıcak Pafta Kağıdı)
RENK_KAGIT_KUTU = (255, 255, 255) # #ffffff (Beyaz Kart)
RENK_KIREC = (228, 228, 225)      # #e4e4e1 (Açık Çerçeve & Kutu)
RENK_KURSUN = (138, 139, 143)     # #8a8b8f (Teknik Rölöve & Metadata)
RENK_KURSUN_ACIK = (218, 222, 230)# #dadee6 (Gövde Metinleri)
RENK_CIZGI = (214, 214, 211)      # #d6d6d3 (Kılavuz Çizgiler)
RENK_CIZGI_ACIK = (220, 220, 216) # #dededa (Açık Pafta Çizgisi)
RENK_CIZGI_KOYU = (45, 48, 56)    # Koyu zemin ayrım çizgisi
RENK_BEYAZ = (255, 255, 255)
RENK_YESIL = (34, 197, 94)        # Yeşil onay/savunma rengi
RENK_METIN_GOVDE = (245, 247, 250)    # Kristal netliğinde, yüksek kontrastlı gövde rengi
RENK_KIRMIZI_CANLI = (255, 59, 48)   # #ff3b30 (Koyu zeminde parlayan canlı mercan kırmızısı)
RENK_KIRMIZI_VURGU = (255, 45, 55)   # #ff2d37 (Manşetlerde difüzyon gölgesiyle parlayan kırmızı)
RENK_UZMAN_CUBUK = RENK_KIRMIZI
RENK_UZMAN_ETIKET = (228, 228, 225)

# Doğrulanmış Türkçe Destekli Font Yolları
FONT_FRAUNCES = config.yol_al("assets/fonts/Fraunces.ttf")
FONT_SANS = config.yol_al("assets/fonts/IBMPlexSans-Medium.ttf")
FONT_SANS_REGULAR = config.yol_al("assets/fonts/IBMPlexSans-Regular.ttf")
FONT_SANS_MEDIUM = config.yol_al("assets/fonts/IBMPlexSans-Medium.ttf")
FONT_SANS_SEMIBOLD = config.yol_al("assets/fonts/IBMPlexSans-SemiBold.ttf")
FONT_SANS_BOLD = config.yol_al("assets/fonts/IBMPlexSans-Bold.ttf")
FONT_INTER_MEDIUM = config.yol_al("assets/fonts/Inter-Medium.ttf")
FONT_INTER_BOLD = config.yol_al("assets/fonts/Inter-Bold.ttf")
FONT_MONO = config.yol_al("assets/fonts/IBMPlexMono.ttf")
FONT_MONO_BOLD = config.yol_al("assets/fonts/IBMPlexMono-Bold.ttf")

# Logo ve Amblem Yolları
LOGO_AMBLEM = config.yol_al("assets/logos/amblem.png")
LOGO_YATAY = config.yol_al("assets/logos/logo-yatay.png")
LOGO_YATAY_ACIK = config.yol_al("assets/logos/logo-yatay-acik.png")
LOGO_YATAY_BEYAZ = config.yol_al("assets/logos/logo-yatay-beyaz.png")
LOGO_SLOGAN = config.yol_al("assets/logos/slogan.png")
LOGO_PIN = config.yol_al("assets/logos/pin-sembol.png")

# Metin Bütçesi & Sınırlar
BUYUKLUK_KELIMELERI = {"bin", "milyon", "milyar", "trilyon"}
PARA_BIRIMLERI = {"₺", "$", "€", "£"}
UNVAN_VE_KISALTMALAR = {
    "dr.", "doç.", "prof.", "av.", "md.", "no.", "sf.", "vb.", "cad.", "sok.", "mah.", "apt.", "bl.",
}
AZAMI_SARILACAK = 4000
OPTIK_KALDIRMA = 26

# Zemin varyantları
ZEMINLER: dict[str, dict[str, Any]] = {
    "murekkep": {
        "zemin": RENK_MUREKKEP,
        "ana": RENK_BEYAZ,
        "govde": RENK_KURSUN_ACIK,
        "vurgu": RENK_KIRMIZI_CANLI,
        "silik": RENK_KURSUN,
        "cizgi": RENK_CIZGI_KOYU,
        "rozet_bg": RENK_MUREKKEP_2,
        "rozet_fg": RENK_BEYAZ,
        "logo_beyaz": True,
    },
    "kagit": {
        "zemin": RENK_KAGIT,
        "ana": RENK_MUREKKEP,
        "govde": (58, 60, 66),
        "vurgu": RENK_KIRMIZI_DERIN,
        "silik": (122, 124, 130),
        "cizgi": RENK_CIZGI,
        "rozet_bg": RENK_MUREKKEP,
        "rozet_fg": RENK_BEYAZ,
        "logo_beyaz": False,
    },
    "kirmizi": {
        "zemin": RENK_KIRMIZI_DERIN,
        "ana": RENK_BEYAZ,
        "govde": (255, 228, 230),
        "vurgu": RENK_BEYAZ,
        "silik": (255, 190, 195),
        "cizgi": (232, 90, 100),
        "rozet_bg": RENK_MUREKKEP,
        "rozet_fg": RENK_BEYAZ,
        "logo_beyaz": True,
        "logo_golge": False,
    },
}
