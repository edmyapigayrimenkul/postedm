"""
hook_motoru.py — EDM DailyBrief Editoryal Kanca (Hook) Motoru.

Kullanıcıyı akışta (4:5) ve story'de (9:16) ilk 0.5 saniyede içeriğe çeken,
kutulardan arındırılmış, saf tipografik ve difüzyon gölgeli
kanca (hook) çizim ve kompozisyon motoru.
(instabot referansı ile EDM kurumsal kimliğine uyarlanmıştır)

Özellikler:
  1. Renk Paleti:
     - Sıcak Kehribar Sarısı (AMBER #F59E0B): Fotoğraf üzerinde maksimum parlaklık & kontrast.
     - Canlı EDM Kırmızısı (KIRMIZI_CANLI #FF3B30): Kritik mevzuat, askı, ceza ve uyarılar.
     - Saf Beyaz (WHITE #FFFFFF) & Metalik Gri (GRAY #94A3B8).
  2. Tipografik Formatlar:
     - stat_punch: İri rakam + birim + dikey ayraç + 2 satır vurucu metin.
     - minimal_vurgu: ● Kicker (Editoryal etiket) + 2 satır dev vurgu metni.
  3. Difüzyon Gölgesi:
     - GaussianBlur(14) ile arkaya yumuşak siyah difüzyon gölgesi atılarak
       fotoğraf ne kadar detaylı veya açık olursa olsun %100 kristal okunurluk sağlanır.
  4. Akıllı Gayrimenkul Veri Tespiti:
     - Ada, parsel, KAKS/emsal, askı günü, metrekare, bütçe gibi kilit verileri
       haber gövdesinden otomatik ayıklar ve başlıkla çakışmayacak şekilde kancaya dönüştürür.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np

from . import config, make_image

log = logging.getLogger(__name__)

# --- RENK PALETİ ---
AMBER_SARI = (250, 204, 21)   # #FACC15 (Parlak Güneş / Altın Sarısı — Her fotoğrafta kristal netlik)
AMBER = (245, 158, 11)        # #F59E0B (Sıcak Kehribar Sarısı)
KIRMIZI_CANLI = (255, 59, 48) # #FF3B30 (Canlı Mercan / EDM İkaz Kırmızısı)
YESIL_CANLI = (52, 211, 153)  # #34D399 (Canlı Zümrüt Yeşili)
WHITE = (255, 255, 255)
GRAY = (148, 163, 184)

TUVAL_GENISLIK = 1080
KENAR_BOSLUK = 74
SAG_PAY = 74


def _font(punto: int, tip: str = "sans_bold") -> ImageFont.FreeTypeFont:
    """Font yükleyici yardımcısı."""
    if tip == "fraunces":
        font_yolu = make_image.FONT_FRAUNCES
    elif tip == "sans_bold":
        font_yolu = make_image.FONT_SANS_BOLD
    elif tip == "mono_bold":
        font_yolu = make_image.FONT_MONO_BOLD
    elif tip == "mono":
        font_yolu = make_image.FONT_MONO
    else:
        font_yolu = make_image.FONT_SANS
    return make_image._font_yukle(font_yolu, punto)


def tr_upper(s: str) -> str:
    """Türkçe karakter duyarlı büyük harfe dönüştürücü."""
    if not s:
        return ""
    return s.replace("i", "İ").replace("ı", "I").upper()


def _dengeli_bol(kelimeler: List[str]) -> Tuple[str, str]:
    """
    Kelime listesini iki satıra böler — karakter dengesine göre
    ve rakamı biriminden (ada, parsel, gün, TL, vb.) koparmadan.
    """
    if len(kelimeler) < 2:
        return " ".join(kelimeler), ""

    def _sayi_biriminden_kopuyor(i: int) -> bool:
        onceki = kelimeler[i - 1].lower()
        suanki = kelimeler[i].lower()
        if re.fullmatch(r"[%₺$€]?[\d.,]+[%₺$€]?", onceki):
            return True
        if onceki in {"ada", "parsel", "kaks", "kat", "gün", "tl", "m²", "m2"}:
            return True
        return False

    def _tek_kisa_satir(i: int) -> bool:
        sol, sag = " ".join(kelimeler[:i]), " ".join(kelimeler[i:])
        return (len(kelimeler[:i]) < 2 and len(sol) < 7) or (len(kelimeler[i:]) < 2 and len(sag) < 7)

    for kisitlar in (
        (_tek_kisa_satir, _sayi_biriminden_kopuyor),
        (_sayi_biriminden_kopuyor,),
        (),
    ):
        en_iyi, en_iyi_fark = None, None
        for i in range(1, len(kelimeler)):
            if any(k(i) for k in kisitlar):
                continue
            fark = abs(len(" ".join(kelimeler[:i])) - len(" ".join(kelimeler[i:])))
            if en_iyi_fark is None or fark < en_iyi_fark:
                en_iyi, en_iyi_fark = i, fark
        if en_iyi is not None:
            return " ".join(kelimeler[:en_iyi]), " ".join(kelimeler[en_iyi:])

    return " ".join(kelimeler), ""


def _sigdiran_font(satirlar: List[str], punto_bas: int, azami_px: int, asgari: int = 26, tip: str = "sans_bold") -> ImageFont.FreeTypeFont:
    """Verilen satırların tümünü azami_px genişliğe sığdıran en büyük puntoyu bulur."""
    dolu = [x for x in satirlar if x]
    if not dolu:
        return _font(punto_bas, tip)
    for punto in range(punto_bas, asgari - 1, -2):
        f = _font(punto, tip)
        if all((f.getbbox(x)[2] - f.getbbox(x)[0]) <= azami_px for x in dolu):
            return f
    return _font(asgari, tip)


def _kirp(metin: str, font: ImageFont.FreeTypeFont, azami_px: int) -> str:
    """Punto küçültme yetmediğinde kelime kelime kırpar ve '…' ekler."""
    if not metin:
        return metin
    if (font.getbbox(metin)[2] - font.getbbox(metin)[0]) <= azami_px:
        return metin
    kelimeler = metin.split()
    while len(kelimeler) > 1:
        kelimeler.pop()
        aday = " ".join(kelimeler) + "…"
        if (font.getbbox(aday)[2] - font.getbbox(aday)[0]) <= azami_px:
            return aday
    return metin


def _basliktan_farkli_mi(t1: str, t2: str, baslik: str, azami_ortusme: float = 0.70) -> bool:
    """Kanca metninin başlıktan farklı bir şey söyleyip söylemediğini denetler."""
    def _kelimeler(metin: str) -> set[str]:
        s = metin.lower().replace("i̇", "i").replace("ı", "i")
        return {k for k in re.findall(r"\w+", s) if len(k) > 2}

    kanca = _kelimeler(f"{t1} {t2}")
    if not kanca:
        return False
    baslik_k = _kelimeler(baslik)
    if not baslik_k:
        return True
    ortak = len(kanca & baslik_k) / len(kanca)
    return ortak < azami_ortusme


def _baslikta_sayi_var_mi(baslik: str) -> bool:
    """Başlıkta zaten rakam var mı denetler."""
    return bool(re.search(r"\d", baslik or ""))


def ciz_stat_punch(
    gorsel: Image.Image,
    x: int,
    y: int,
    num_txt: str,
    unit_txt: str = "",
    lbl_txt: str = "",
    t1: str = "",
    t2: str = "",
    renk: Tuple[int, int, int] = AMBER,
) -> Image.Image:
    """
    Rakam odaklı vuruş formatı (İri rakam + birim + dikey ayraç + 2 satır vurgu).
    Arka planda GaussianBlur(14) difüzyon gölgesiyle sıfır taşma garantili çizilir.
    """
    out = gorsel.copy()
    f_unit = _font(32, "sans_bold")
    f_lbl = _font(16, "mono_bold")
    satirlar = [s for s in [t1, t2] if s]

    # Rakam ve sol blok genişlik hesabı (Düz tabanlı modern lining rakamlar)
    sag_blok_asgari = 380
    f_num = _font(96, "sans_bold")
    for num_punto in range(96, 54, -4):
        f_num = _font(num_punto, "sans_bold")
        w_num_d = f_num.getbbox(num_txt)[2] - f_num.getbbox(num_txt)[0]
        w_unit_d = (f_unit.getbbox(unit_txt)[2] - f_unit.getbbox(unit_txt)[0]) if unit_txt else 0
        w_lbl_d = (f_lbl.getbbox(lbl_txt)[2] - f_lbl.getbbox(lbl_txt)[0]) if lbl_txt else 0
        sol_d = max(w_num_d + (12 + w_unit_d if unit_txt else 0), w_lbl_d)
        if (TUVAL_GENISLIK - SAG_PAY) - (x + sol_d + 48) >= sag_blok_asgari:
            break

    bb_num = f_num.getbbox(num_txt)
    w_num = bb_num[2] - bb_num[0]
    h_num = bb_num[3] - bb_num[1]
    w_unit = (f_unit.getbbox(unit_txt)[2] - f_unit.getbbox(unit_txt)[0]) if unit_txt else 0
    w_lbl = (f_lbl.getbbox(lbl_txt)[2] - f_lbl.getbbox(lbl_txt)[0]) if lbl_txt else 0

    w_ust = w_num + (12 + w_unit if unit_txt else 0)
    sol_blok = max(w_ust, w_lbl)

    # Dinamik ayraç ve sağ blok konumu
    sep_x = x + sol_blok + 24
    sag_x = sep_x + 24

    sag_alan = max(160, (TUVAL_GENISLIK - SAG_PAY) - sag_x)
    f_t = _sigdiran_font(satirlar, 40, sag_alan, asgari=24, tip="sans_bold")
    satirlar = [_kirp(sat, f_t, sag_alan) for sat in satirlar]

    w_sag = max((f_t.getbbox(s)[2] - f_t.getbbox(s)[0] for s in satirlar), default=200)
    toplam_w = (sag_x + w_sag) - x
    satir_adim = max(36, int(f_t.size * 1.22))
    govde_h = max(140, len(satirlar) * satir_adim + 20)

    # 1. Difüzyon Gölgesi (Siyah alfa katman + GaussianBlur)
    shadow = Image.new("RGBA", (toplam_w + 100, govde_h + 80), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sx = 40
    sy = 30
    sdraw.text((sx, sy), num_txt, font=f_num, fill=(0, 0, 0, 240))
    if unit_txt:
        sdraw.text((sx + w_num + 12, sy + 18), unit_txt, font=f_unit, fill=(0, 0, 0, 240))
    if lbl_txt:
        sdraw.text((sx + 2, sy + 102), lbl_txt, font=f_lbl, fill=(0, 0, 0, 220))
    for i, s in enumerate(satirlar):
        sdraw.text((sx + (sep_x - x) + 24, sy + 8 + i * satir_adim), s, font=f_t, fill=(0, 0, 0, 240))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    out.paste(shadow, (x - 40, y - 30), shadow)

    # 2. Metin ve Çizgi Çizimi
    draw = ImageDraw.Draw(out)
    draw.text((x, y), num_txt, font=f_num, fill=renk)
    if unit_txt:
        draw.text((x + w_num + 12, y + 18), unit_txt, font=f_unit, fill=renk)
    if lbl_txt:
        draw.text((x + 2, y + 102), lbl_txt, font=f_lbl, fill=GRAY)

    # Dikey ayraç
    h_cizgi = max(120, len(satirlar) * satir_adim)
    draw.line([(sep_x, y + 12), (sep_x, y + 12 + h_cizgi)], fill=(255, 255, 255, 80), width=2)

    # Sağ blok satırları
    for i, s in enumerate(satirlar):
        satir_rengi = renk if i == 0 else WHITE
        draw.text((sag_x, y + 8 + i * satir_adim), s, font=f_t, fill=satir_rengi)

    return out


def ciz_minimal_vurgu(
    gorsel: Image.Image,
    x: int,
    y: int,
    kicker: str,
    t1: str,
    t2: str,
    renk: Tuple[int, int, int] = AMBER,
) -> Image.Image:
    """
    Kutulardan arınmış saf editoryal minimal kicker + dev vurgu başlığı.
    """
    out = gorsel.copy()
    f_kicker = _font(22, "sans_bold")
    minimal_alan = max(200, (TUVAL_GENISLIK - SAG_PAY) - x)

    # Tavan 56-64 punto (Manşet 70px olduğu için kanca hiyerarşik olarak zarif kalmalı)
    f_title = _sigdiran_font([t1, t2], 62, minimal_alan, asgari=32, tip="sans_bold")
    t1 = _kirp(t1, f_title, minimal_alan)
    t2 = _kirp(t2, f_title, minimal_alan)
    kicker = _kirp(kicker, f_kicker, minimal_alan)

    ust = 36 if kicker else 0
    satir_y = int(f_title.size * 1.18)
    govde_h = ust + (satir_y if t2 else 0) + int(f_title.size * 1.2)

    # Difüzyon Gölgesi
    shadow = Image.new("RGBA", (minimal_alan + 80, govde_h + 80), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    if kicker:
        sdraw.text((35, 25), kicker, font=f_kicker, fill=(0, 0, 0, 230))
    sdraw.text((35, 25 + ust), t1, font=f_title, fill=(0, 0, 0, 240))
    if t2:
        sdraw.text((35, 25 + ust + satir_y), t2, font=f_title, fill=(0, 0, 0, 240))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    out.paste(shadow, (x - 35, y - 25), shadow)

    # Metin Çizimi
    draw = ImageDraw.Draw(out)
    if kicker:
        draw.text((x, y), kicker, font=f_kicker, fill=renk)
    draw.text((x, y + ust), t1, font=f_title, fill=WHITE)
    if t2:
        draw.text((x, y + ust + satir_y), t2, font=f_title, fill=renk)

    return out


def hook_olustur(haber: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Haber içeriğini analiz ederek en etkili gayrimenkul kancasını (hook) üretir.
    Öncelik Sırası:
      1. haber['kanca'] / haber['hook']
      2. Gayrimenkul / imar sayısal verisi (stat_punch)
      3. Haber detay maddeleri / spotundan rafine minimal_vurgu
    """
    baslik = haber.get("manset") or haber.get("baslik") or haber.get("orijinal_baslik") or ""
    spot = haber.get("spot") or haber.get("ozet") or haber.get("orijinal_ozet") or ""
    kat = haber.get("kategori") or haber.get("kategori_kodu") or "GAYRİMENKUL"
    kat_low = str(kat).lower()
    metin_tum = f"{baslik} {spot}"

    # Detay metni veya maddeleri varsa birleştir
    detay_maddeleri = make_image.haber_detay_maddelerini_ayikla(haber)
    for dm in detay_maddeleri:
        metin_tum += f" {dm.get('etiket', '')} {dm.get('metin', '')}"

    # 1. Açıkça belirtilmiş 'kanca' alanı varsa
    kanca_raw = haber.get("kanca") or haber.get("hook") or ""
    if kanca_raw:
        kanca_temiz = str(kanca_raw).strip()
        t1, t2 = _dengeli_bol(tr_upper(kanca_temiz).split())
        if _basliktan_farkli_mi(t1, t2, baslik):
            kicker = "● KRİTİK GELİŞME"
            if "imar" in kat_low or "arsa" in kat_low:
                kicker = "● İMAR PLANI ASKIYA ÇIKTI" if "askı" in metin_tum.lower() else "● ARSA & İMAR DUYURUSU"
            elif "tapu" in kat_low or "hukuk" in kat_low:
                kicker = "● YARGITAY & HUKUK KARARI"
            elif "donusum" in kat_low or "dönüşüm" in kat_low:
                kicker = "● KENTSEL DÖNÜŞÜM GELİŞMESİ"
            return {
                "format": "minimal_vurgu",
                "kicker": kicker,
                "t1": t1,
                "t2": t2,
                "renk": AMBER,
            }

    # 2. Sayısal / Gayrimenkul Veri Tespiti (stat_punch)
    # Başlıkta rakam yoksa veya rakam başlıkla örtüşmüyorsa
    baslikta_sayi_var = _baslikta_sayi_var_mi(baslik)
    
    # Kalıp 1: "142 ADA" ve/veya "85 PARSEL"
    m_ada = re.search(r"(\d+)\s*(?:ADA)", metin_tum, re.IGNORECASE)
    m_parsel = re.search(r"(\d+)\s*(?:PARSEL)", metin_tum, re.IGNORECASE)
    if m_ada and not baslikta_sayi_var:
        num = m_ada.group(1)
        unit = "ADA"
        parsel_num = m_parsel.group(1) if m_parsel else ""
        t1 = f"{parsel_num} PARSEL ETKİLENİYOR" if parsel_num else "BÖLGE PARSELLERİ"
        t2 = "PLAN RESMEN ASKIYA ÇIKTI" if "askı" in metin_tum.lower() else "YENİ İMAR PLANI YÜRÜRLÜKTE"
        return {
            "format": "stat_punch",
            "num_txt": num,
            "unit_txt": unit,
            "lbl_txt": "PLAN SAHASI",
            "t1": t1,
            "t2": t2,
            "renk": AMBER,
        }

    # Kalıp 2: "30 GÜN" / "15 GÜN" (Askı ve İtiraz Süresi)
    m_gun = re.search(r"(\d+)\s*(GÜN|GÜNLÜK)", metin_tum, re.IGNORECASE)
    if m_gun and ("askı" in metin_tum.lower() or "itiraz" in metin_tum.lower()):
        num = m_gun.group(1)
        return {
            "format": "stat_punch",
            "num_txt": num,
            "unit_txt": "GÜN",
            "lbl_txt": "YASAL SÜREÇ",
            "t1": "RESMİ ASKI VE İTİRAZ",
            "t2": "SÜRECİ BAŞLAMIŞTIR",
            "renk": AMBER_SARI,
        }

    # Kalıp 3: KAKS / EMSAL (Örn: KAKS 0.60 veya Emsal 1.50)
    m_kaks = re.search(r"(?:KAKS|EMSAL)\s*[:=]?\s*([0-9\.,]+)", metin_tum, re.IGNORECASE)
    if m_kaks:
        val = m_kaks.group(1)
        return {
            "format": "stat_punch",
            "num_txt": val,
            "unit_txt": "KAKS",
            "lbl_txt": "YENİ EMSAL ORANI",
            "t1": "YAPILAŞMA VE İNŞAAT",
            "t2": "KOŞULLARI BELİRLENDİ",
            "renk": AMBER,
        }

    # Kalıp 4: Parasal veya Yüzdesel Vurgu (Örn: %25 ZAM, %4 Harç, 500 BİN TL)
    m_yuzde = re.search(r"(%\s*[\d\.,]+)", metin_tum)
    if m_yuzde and not baslikta_sayi_var:
        val = m_yuzde.group(1).replace(" ", "")
        return {
            "format": "stat_punch",
            "num_txt": val,
            "unit_txt": "ORAN",
            "lbl_txt": "GÜNCEL ORAN",
            "t1": "RESMİ TARİFE VE",
            "t2": "UYGULAMA ŞARTLARI",
            "renk": AMBER,
        }

    # 3. Sayısal veri bulunamadıysa: Detay Maddelerinden Editoryal minimal_vurgu
    if detay_maddeleri:
        ilk_madde = detay_maddeleri[0]
        etiket = tr_upper(ilk_madde.get("etiket", ""))
        metin = ilk_madde.get("metin", "")
        # Metinden kısa ve vurucu 2 satır çıkar
        kelimeler = metin.split()
        if len(kelimeler) >= 4:
            t1, t2 = _dengeli_bol(kelimeler[:8])
            t1, t2 = tr_upper(t1), tr_upper(t2)
            if _basliktan_farkli_mi(t1, t2, baslik):
                kicker = f"● {etiket}" if etiket else "● SEKTÖREL BÜLTEN"
                return {
                    "format": "minimal_vurgu",
                    "kicker": kicker,
                    "t1": t1,
                    "t2": t2,
                    "renk": AMBER,
                }

    # 4. Hiçbiri olmazsa kategoriye göre şık minimal kanca
    kat = haber.get("kategori") or "GÜNDEM"
    kat_str = str(kat).replace("_", " ").upper()
    return {
        "format": "minimal_vurgu",
        "kicker": f"● {kat_str} BÜLTENİ",
        "t1": "YATIRIMCILAR VE MÜLK",
        "t2": "SAHİPLERİ İÇİN KRİTİK DETAY",
        "renk": AMBER,
    }


def hook_rengi_belirle(
    canvas: Image.Image,
    x: int,
    y: int,
    w: int = 650,
    h: int = 140,
    tercih_edilen_renk: Optional[Tuple[int, int, int]] = None,
    varsayilan_dikkat_rengi: Tuple[int, int, int] = AMBER_SARI,
) -> Tuple[int, int, int]:
    """
    Kullanıcı Tasarım İlkesi:
    - Kırmızının arkasında net kontrast oluşturduğu (açık zeminli, beyaz, buz mavisi)
      durumlarda kırmızı kullanılabilir.
    - Ancak arka planda kiremit kırmızısı/kahverengi çatı dokusu, koyu zemin veya renk karmaşası
      varsa kırmızı boğulur; bu durumda dikkat çekici parlak altın sarısı (#FACC15) seçilir.
    """
    if tercih_edilen_renk is not None:
        return tercih_edilen_renk

    try:
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(canvas.width, x + w)
        y2 = min(canvas.height, y + h)
        patch = canvas.crop((x1, y1, x2, y2)).convert("RGB")
        arr = np.array(patch, dtype=np.float32)

        mean_r = float(np.mean(arr[:, :, 0]))
        mean_g = float(np.mean(arr[:, :, 1]))
        mean_b = float(np.mean(arr[:, :, 2]))
        luminance = 0.299 * mean_r + 0.587 * mean_g + 0.114 * mean_b
        std_all = float(np.std(arr))

        # Kırmızının gerçekten temiz ve net okunabileceği durum:
        # Zemin oldukça aydınlık (lum >= 190) ve doku karmaşası az (std_all < 35) ise kırmızı kullanılabilir.
        if luminance >= 190.0 and std_all < 35.0 and mean_r < 210.0:
            return KIRMIZI_CANLI

        return varsayilan_dikkat_rengi
    except Exception as e:
        log.debug("Hook rengi analiz hatası: %s", e)
        return varsayilan_dikkat_rengi


def hook_uygula(
    canvas: Image.Image,
    haber: Dict[str, Any],
    manset_ust_y: int,
    ust_y: int = 62,
    olcu: str = "besleme",
) -> Image.Image:
    """
    Kapak slaytına (Slayt 1) akıllı editoryal hook metnini ve difüzyon gölgesini yerleştirir.
    4:5 ve 9:16 oranlarında güvenli alanda, başlığa yapışmayacak ve logonun altına oturacak şekilde konumlanır.
    """
    hook_veri = hook_olustur(haber)
    if not hook_veri:
        return canvas

    fmt = hook_veri.get("format", "minimal_vurgu")
    override_renk = haber.get("hook_renk_override")

    # Dikey koordinat hesabı:
    # Üst sınır: ust_y + 120 (EDM logosu ve rozetin altı)
    # Alt sınır: manset_ust_y - 65 (Manşetle aradaki ferah ayrım payı — instabot AYRIM_PAYI standardı)
    ust_sinir = ust_y + 120
    hook_h = 145 if fmt == "stat_punch" else 130
    alt_sinir = manset_ust_y - 65

    if alt_sinir - hook_h < ust_sinir:
        y_pos = max(ust_sinir, alt_sinir - hook_h)
    else:
        y_pos = alt_sinir - hook_h

    x_pos = KENAR_BOSLUK

    # Arka plan kontrastına göre dinamik renk adaptasyonu (Kullanıcı Kuralı)
    renk = hook_rengi_belirle(
        canvas=canvas,
        x=x_pos,
        y=y_pos,
        w=650,
        h=hook_h,
        tercih_edilen_renk=override_renk,
        varsayilan_dikkat_rengi=hook_veri.get("renk", AMBER_SARI),
    )

    if fmt == "stat_punch":
        return ciz_stat_punch(
            canvas,
            x=x_pos,
            y=y_pos,
            num_txt=hook_veri.get("num_txt", ""),
            unit_txt=hook_veri.get("unit_txt", ""),
            lbl_txt=hook_veri.get("lbl_txt", ""),
            t1=hook_veri.get("t1", ""),
            t2=hook_veri.get("t2", ""),
            renk=renk,
        )
    else:
        return ciz_minimal_vurgu(
            canvas,
            x=x_pos,
            y=y_pos,
            kicker=hook_veri.get("kicker", ""),
            t1=hook_veri.get("t1", ""),
            t2=hook_veri.get("t2", ""),
            renk=renk,
        )
