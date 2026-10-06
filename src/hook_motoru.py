"""
hook_motoru.py — EDM DailyBrief Editoryal Kanca (Hook) Motoru.

Kullanıcıyı akışta (4:5) ve story'de (9:16) ilk 0.5 saniyede içeriğe çeken,
kutulardan arındırılmış, saf tipografik ve difüzyon gölgeli
kanca (hook) çizim ve kompozisyon motoru.
(instabot referansı ile EDM kurumsal kimliğine uyarlanmıştır)

Özellikler:
  1. Renk Paleti (2026-09-25'ten beri yalnızca marka tonları):
     - Vurgu: EDM kırmızısının koyu zemin tonu (#FF3B30). Eskiden amber, altın
       sarısı ve zümrüt yeşiliydi — kurumsal kimlik dışıydı.
     - Saf beyaz, kireç ve kurşun.
  2. Tipografik Formatlar:
     - stat_punch: İri rakam + birim + dikey ayraç + 2 satır vurucu metin.
     - minimal_vurgu: Kicker (maddenin kendi etiketi, varsa) + 2 satır dev vurgu metni.
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

from . import config, make_image, dogrula

log = logging.getLogger(__name__)

# --- RENK PALETİ ---
KIRMIZI_CANLI = (255, 38, 48) # #FF2630 Ultra canlı, parlak ve fotoğrafta patlayan EDM kırmızısı
VURGU = KIRMIZI_CANLI         # kanca vurgusu ve etiket (eskiden amber #F59E0B / #FACC15)
KIREC = (228, 228, 225)       # #E4E4E1
WHITE = (255, 255, 255)
KURSUN = (138, 139, 143)      # #8A8B8F (eskiden arduvaz gri #94A3B8)

TUVAL_GENISLIK = 1080
KENAR_BOSLUK = 74
SAG_PAY = 74

# --- KANCA STİLİ (2026-10-07, kullanıcı: "hook kırmızısı dikkat çekici değil, okunmuyor") ---
# Sebep fizik: göz parlaklığı yeşil kanaldan okuyor (WCAG: R .21 / G .72 / B .07). Doymuş
# kırmızı koyu/orta tonlu fotoğrafta "parlak" değil KOYU kalır. Instabot'ta aynı şikâyet
# ölçüldü: kırmızı #EF4444 kontrast 2,02 (büyük metin eşiği 3,00), amber #F59E0B 3,54.
# Instabot amber'e geçti; EDM markasında amber/turkuaz/yeşil yok (MEMORY.md §8.7), bu yüzden
# kırmızı METİN olmaktan çıkıp DOLGU oldu (marka kuralı: kırmızı dolguda serbest, küçük
# metin olarak değil):
#   plaka  İkinci satır kırmızı plakada BEYAZ yazı. Kontrast ~4,4 (#F0000D) ve plaka
#          fotoğraftan bağımsız; B1/B2 kapaklarındaki "BİLE / DOĞRU FİYAT" kutusuyla aynı dil.
#   cubuk  İki satır beyaz, solda kırmızı dikey çubuk, arkada sınırlı koyu bant.
#   amber  Instabot'un birebir kancası (marka dışı; yalnız karşılaştırma için).
KANCA_STILI = "plaka"
PLAKA_KIRMIZI = (240, 0, 13)   # Kırmızı #F0000D (dolgu)
AMBER = (245, 158, 11)         # yalnız "amber" stili


def _font(punto: int, tip: str = "sans_bold") -> ImageFont.FreeTypeFont:
    """Font yükleyici yardımcısı. Kanca Instabot'la aynı Inter Variable 900 (Türkçe kapsamı tam)."""
    if tip == "sans_bold":
        from . import haber_tasarim
        return haber_tasarim._font(punto, [32.0 if punto >= 28 else 20.0, 900.0])
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


def _sigar_mi(metin: str, font: ImageFont.FreeTypeFont, azami_px: int) -> bool:
    """Kanca kırpılmaz: "…" ile kesilmiş bir kanca cümlenin anlamını değiştirebilir.
    Asgari puntoda sığmıyorsa çizici kancayı hiç basmaz, kapak kancasız kalır."""
    if not metin:
        return True
    bb = font.getbbox(metin)
    return (bb[2] - bb[0]) <= azami_px


def _basliktan_farkli_mi(t1: str, t2: str, baslik: str, azami_ortusme: float = 0.40) -> bool:
    """Kanca metninin başlıktan farklı bir şey söyleyip söylemediğini denetler.
    Kancanın manşetteki kelimeleri aynen veya kök olarak tekrar etmesini engeller.
    Kelime veya kök örtüşmesi %40'ı geçiyorsa kanca ÇİZİLMEZ (A kuralı)."""
    import re as _re
    from . import dogrula

    def _kelimeler(metin: str) -> set[str]:
        sadelesmis = dogrula._sadelestir(metin or "")
        return {k for k in _re.findall(r"\w+", sadelesmis) if len(k) > 2}

    kanca = _kelimeler(f"{t1} {t2}")
    if not kanca:
        return False
    baslik_k = _kelimeler(baslik)
    if not baslik_k:
        return True

    ortak = 0
    for kw in kanca:
        if kw in baslik_k or any((len(kw) >= 4 and len(bw) >= 4 and (kw in bw or bw in kw)) for bw in baslik_k):
            ortak += 1

    ortusme = ortak / len(kanca)
    return ortusme <= azami_ortusme


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
    renk: Tuple[int, int, int] = VURGU,
) -> Image.Image:
    """
    Rakam odaklı vuruş formatı (İri rakam + birim + dikey ayraç + 2 satır vurgu).
    Arka planda GaussianBlur(14) difüzyon gölgesiyle sıfır taşma garantili çizilir.
    """
    out = gorsel.copy()
    stil = KANCA_STILI
    # Rakam kırmızı METİN olarak fotoğrafta okunmuyordu: plaka/çubuk stillerinde beyaz,
    # kırmızı yalnız dolgu (plaka) ya da çubuk olarak girer.
    rakam_renk = AMBER if stil == "amber" else WHITE
    f_unit = _font(36, "sans_bold")
    f_lbl = _font(18, "mono_bold")
    satirlar = [s for s in [t1, t2] if s]

    # Rakam ve sol blok genişlik hesabı (Düz tabanlı modern lining rakamlar)
    sag_blok_asgari = 380
    f_num = _font(108, "sans_bold")
    for num_punto in range(108, 64, -4):
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
    f_t = _sigdiran_font(satirlar, 46, sag_alan, asgari=26, tip="sans_bold")
    if not all(_sigar_mi(sat, f_t, sag_alan) for sat in satirlar):
        log.warning("Kanca asgari puntoda sığmadı, kapak kancasız çizildi: %s", satirlar)
        return gorsel

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
    if stil == "plaka":
        draw.rectangle([x - 18, y + bb_num[1] - 8, x + sol_blok + 18, y + bb_num[3] + 14], fill=PLAKA_KIRMIZI)
    elif stil == "cubuk":
        draw.rectangle([x - 26, y + bb_num[1], x - 16, y + bb_num[3] + 6], fill=PLAKA_KIRMIZI)
    draw.text((x, y), num_txt, font=f_num, fill=rakam_renk)
    if unit_txt:
        draw.text((x + w_num + 12, y + 18), unit_txt, font=f_unit, fill=rakam_renk)
    if lbl_txt:
        draw.text((x + 2, y + 102), lbl_txt, font=f_lbl, fill=KURSUN)

    # Dikey ayraç
    h_cizgi = max(120, len(satirlar) * satir_adim)
    draw.line([(sep_x, y + 12), (sep_x, y + 12 + h_cizgi)], fill=(255, 255, 255, 80), width=2)

    # Sağ blok satırları
    for i, s in enumerate(satirlar):
        satir_rengi = AMBER if (stil == "amber" and i == 0) else WHITE
        draw.text((sag_x, y + 8 + i * satir_adim), s, font=f_t, fill=satir_rengi)

    return out


def _okuma_bandi(canvas: Image.Image, ust: int, alt: int, alfa: int = 150, yumusak: int = 90) -> Image.Image:
    """Yalnız [ust, alt] aralığında, iki yanı yumuşakça sönen koyu bant.

    İlk sürüm perdeyi tuvalin SONUNA kadar uzatıyordu; Instabot çiziminde kanca başlıktan
    SONRA çizildiği için başlık ve özet de kararıp gri kalıyordu (#452, 2026-10-07).
    """
    g, h = canvas.size
    ust, alt = max(0, ust), min(h, alt)
    serit = []
    for yy in range(h):
        if yy <= ust - yumusak or yy >= alt + yumusak:
            serit.append(0)
        elif yy < ust:
            u = (yy - (ust - yumusak)) / yumusak
            serit.append(int(alfa * u * u * (3 - 2 * u)))
        elif yy > alt:
            u = 1 - (yy - alt) / yumusak
            serit.append(int(alfa * u * u * (3 - 2 * u)))
        else:
            serit.append(alfa)
    maske = Image.new("L", (1, h))
    maske.putdata(serit)
    koyu = Image.new("RGB", (g, h), (18, 19, 22))   # Mürekkep #121316
    return Image.composite(koyu, canvas.convert("RGB"), maske.resize((g, h)))


def ciz_minimal_vurgu(
    gorsel: Image.Image,
    x: int,
    y: int,
    kicker: str,
    t1: str,
    t2: str,
    renk: Tuple[int, int, int] = VURGU,
    stil: Optional[str] = None,
) -> Image.Image:
    """
    Kutusuz editoryal kicker + dev vurgu başlığı; ikinci satırın okunurluğu `KANCA_STILI`ne bağlı.
    """
    stil = stil or KANCA_STILI
    out = gorsel.copy()
    # "●" karakteri IBM Plex Sans'ta yok, kutu (□) basılıyordu: nokta ayrıca çiziliyor.
    f_kicker = _font(28, "sans_bold")
    minimal_alan = max(200, (TUVAL_GENISLIK - SAG_PAY) - x)
    kicker = kicker.lstrip("●• ").strip()
    nokta = 15
    kicker_x = x + nokta + 12

    # Tavan punto (Instabot paritesi 92 punto)
    tavan_punto = 92
    f_title = _sigdiran_font([t1, t2], tavan_punto, minimal_alan - (24 if stil == "plaka" else 0), asgari=26, tip="sans_bold")
    if not (_sigar_mi(t1, f_title, minimal_alan) and _sigar_mi(t2, f_title, minimal_alan)):
        log.warning("Kanca asgari puntoda sığmadı, kapak kancasız çizildi: %s / %s", t1, t2)
        return gorsel
    if not _sigar_mi(kicker, f_kicker, minimal_alan - (kicker_x - x)):
        kicker = ""

    ust = 46 if kicker else 0
    satir_y = int(f_title.size * 1.12)
    govde_h = ust + (satir_y if t2 else 0) + int(f_title.size * 1.25)

    if stil == "cubuk":
        out = _okuma_bandi(out, y - 30, y + govde_h + 30)

    # Difüzyon Gölgesi
    shadow = Image.new("RGBA", (minimal_alan + 80, govde_h + 80), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    if kicker:
        sdraw.text((35 + kicker_x - x, 25), kicker, font=f_kicker, fill=(0, 0, 0, 230))
    sdraw.text((35, 25 + ust), t1, font=f_title, fill=(0, 0, 0, 240))
    if t2 and stil != "plaka":
        sdraw.text((35, 25 + ust + satir_y), t2, font=f_title, fill=(0, 0, 0, 240))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    out.paste(shadow, (x - 35, y - 25), shadow)

    draw = ImageDraw.Draw(out)
    nokta_renk = AMBER if stil == "amber" else PLAKA_KIRMIZI
    if kicker:
        orta = y + (f_kicker.getbbox("ÇĞ")[1] + f_kicker.getbbox("ÇĞ")[3]) // 2
        draw.ellipse([x, orta - nokta // 2, x + nokta, orta + nokta // 2], fill=nokta_renk)
        draw.text((kicker_x, y), kicker, font=f_kicker, fill=WHITE)
    draw.text((x, y + ust), t1, font=f_title, fill=WHITE)

    if t2:
        t2_y = y + ust + satir_y
        if stil == "plaka":
            bb = f_title.getbbox(t2)
            pad_x, pad_ust, pad_alt = 20, 6, 14
            plaka = [x - pad_x, t2_y + bb[1] - pad_ust, x + (bb[2] - bb[0]) + pad_x + bb[0], t2_y + bb[3] + pad_alt]
            draw.rectangle(plaka, fill=PLAKA_KIRMIZI)
            draw.text((x, t2_y), t2, font=f_title, fill=WHITE)
        elif stil == "amber":
            draw.text((x, t2_y), t2, font=f_title, fill=AMBER)
        else:  # cubuk
            draw.text((x, t2_y), t2, font=f_title, fill=WHITE)
    if stil == "cubuk":
        bar_ust = y + (0 if not kicker else ust)
        draw.rectangle([x - 26, bar_ust + 6, x - 16, y + govde_h - int(f_title.size * 0.2)], fill=PLAKA_KIRMIZI)

    return out


def hook_olustur(haber: Dict[str, Any], fallback: bool = False) -> Optional[Dict[str, Any]]:
    """
    Haber içeriğini analiz ederek en etkili gayrimenkul kancasını (hook) üretir.
    Öncelik Sırası:
      1. haber['kanca'] / haber['hook'] (veya detay_metni JSON içindeki 'kanca')
      2. Gayrimenkul / imar sayısal verisi (stat_punch)
      3. Haber detay maddeleri / spotundan rafine minimal_vurgu
      4. Kategori ve konuya duyarlı garantili somut kanca (fallback=True ise)
    """
    import json
    if isinstance(haber, dict):
        dm = haber.get("detay_metni")
        if dm and isinstance(dm, str) and dm.strip().startswith("{"):
            try:
                parsed = json.loads(dm)
                if isinstance(parsed, dict):
                    haber = {**parsed, **haber}
                    if not haber.get("kanca") and parsed.get("kanca"):
                        haber["kanca"] = parsed["kanca"]
            except Exception:
                pass

    baslik = haber.get("manset") or haber.get("baslik") or haber.get("orijinal_baslik") or ""
    spot = haber.get("spot") or haber.get("ozet") or haber.get("orijinal_ozet") or ""
    metin_tum = f"{baslik} {spot}"

    # Detay metni veya maddeleri varsa birleştir
    detay_maddeleri = make_image.haber_detay_maddelerini_ayikla(haber)
    for dm in detay_maddeleri:
        metin_tum += f" {dm.get('etiket', '')} {dm.get('metin', '')}"

    # 1. Açıkça belirtilmiş 'kanca' alanı varsa
    kanca_raw = haber.get("kanca") or haber.get("hook") or ""
    if kanca_raw and dogrula.kanca_ici_bos_mu(kanca_raw):
        # #509: "JAPON FİNANS GRUBU // RAPOR YAYINLANDI" fotoğrafın üstüne basıldı,
        # okuyana hiçbir şey katmadı. Boş kanca çizilmez; aşağıdaki somut adaylar denenir.
        log.info("İçi boş kanca çizilmedi: %s", kanca_raw)
        kanca_raw = ""
    if kanca_raw:
        kanca_temiz = str(kanca_raw).strip()
        if "//" in kanca_temiz:
            parts = [p.strip() for p in kanca_temiz.split("//", 1)]
            t1, t2 = tr_upper(parts[0]), tr_upper(parts[1])
        else:
            t1, t2 = _dengeli_bol(tr_upper(kanca_temiz).split())
        if (t1 or t2) and _basliktan_farkli_mi(t1, t2, baslik):
            return {
                "format": "minimal_vurgu",
                "kicker": "",
                "t1": t1,
                "t2": t2,
                "renk": VURGU,
            }
        else:
            log.info("Açık kanca başlığı tekrar ediyor/örtüşüyor (%s // %s vs '%s'), alternatif aranıyor", t1, t2, baslik)

    # 2. Sayısal / Gayrimenkul Veri Tespiti (stat_punch)
    # Başlıkta rakam yoksa veya rakam başlıkla örtüşmüyorsa
    baslikta_sayi_var = _baslikta_sayi_var_mi(baslik)
    
    govde_metni = " ".join([str(spot)] + [str(dm.get("metin", "")) for dm in detay_maddeleri])

    def _cumleden(eslesme: "re.Match[str]") -> Optional[Tuple[str, str]]:
        for cumle in re.split(r"(?<=[.!?;])\s+", govde_metni):
            konum = cumle.lower().find(eslesme.group(0).lower())
            if konum < 0:
                continue
            sonrasi = cumle[konum + len(eslesme.group(0)):].split()
            while sonrasi and sonrasi[0].lower().strip(",") in ("ve", "ile", "ise", "da", "de", "olan"):
                sonrasi.pop(0)
            kelimeler = [k.rstrip(".;") for k in sonrasi]
            if len(kelimeler) < 3:
                kelimeler = [k.rstrip(".;") for k in cumle.replace(eslesme.group(0), " ").split()]
            if not 3 <= len(kelimeler) <= 8:
                return None
            t1, t2 = _dengeli_bol(kelimeler)
            t1, t2 = tr_upper(t1), tr_upper(t2)
            return (t1, t2) if _basliktan_farkli_mi(t1, t2, baslik) else None
        return None

    kaliplar = [
        # (desen, birim, etiket, koşul)
        (r"(\d+)\s*(?:ADA)\b", "ADA", "ADA NO", not baslikta_sayi_var),
        (r"(\d+)\s*(?:GÜN|GÜNLÜK)\b", "GÜN", "SÜRE", "askı" in metin_tum.lower() or "itiraz" in metin_tum.lower()),
        (r"(?:KAKS|EMSAL)\s*[:=]?\s*([0-9][0-9\.,]*)", "KAKS", "EMSAL", True),
        (r"(%\s*[\d\.,]+)", "ORAN", "ORAN", not baslikta_sayi_var),
    ]
    for desen, birim, etiket, kosul in kaliplar:
        if not kosul:
            continue
        m = re.search(desen, metin_tum, re.IGNORECASE)
        if not m:
            continue
        deger = m.group(1).replace(" ", "")
        if dogrula.vurgu_zayif_mi(deger, birim):
            continue
        satirlar = _cumleden(m)
        if not satirlar:
            continue
        return {
            "format": "stat_punch",
            "num_txt": deger,
            "unit_txt": "" if birim == "ORAN" else birim,
            "lbl_txt": etiket,
            "t1": satirlar[0],
            "t2": satirlar[1],
            "renk": VURGU,
        }

    # 3. Sayısal veri bulunamadıysa: Detay Maddelerinden Editoryal minimal_vurgu
    if detay_maddeleri:
        for ilk_madde in detay_maddeleri:
            etiket = tr_upper(ilk_madde.get("etiket", ""))
            metin = ilk_madde.get("metin", "")
            if dogrula.bos_ovgu_mu(metin):
                continue
            ilk_cumle = re.split(r"(?<=[.!?;])\s+", str(metin).strip())[0]
            kelimeler = ilk_cumle.split()
            if 4 <= len(kelimeler) <= 9:
                t1, t2 = _dengeli_bol(kelimeler)
                t1, t2 = tr_upper(t1), tr_upper(t2)
                if _basliktan_farkli_mi(t1, t2, baslik):
                    return {
                        "format": "minimal_vurgu",
                        "kicker": etiket,
                        "t1": t1,
                        "t2": t2,
                        "renk": VURGU,
                    }

    if not fallback:
        return None

    # 4. Kaynaktan kanca çıkmadıysa: her haber için akıllı kategori/spot kancası
    kat = tr_upper(haber.get("kategori") or haber.get("kategori_kodu") or "")
    if any(w in (metin_tum + " " + kat).lower() for w in ("ihale", "milli emlak", "arazi", "satış", "hazine")):
        t1, t2 = "MİLLİ EMLAK & ARSA", "RESMİ SATIŞ VE İHALE"
    elif any(w in (metin_tum + " " + kat).lower() for w in ("vergi", "harç", "maliye", "ceza", "masak", "rayiç")):
        t1, t2 = "MALİYE VE TAPU", "CEZA VE DENETİM RİSKİ"
    elif any(w in (metin_tum + " " + kat).lower() for w in ("kredi", "faiz", "banka", "bddk", "tcmb", "ipotek")):
        t1, t2 = "KREDİ PİYASASI", "GÜNCEL ORAN VE LİMİT"
    elif any(w in (metin_tum + " " + kat).lower() for w in ("imar", "plan", "askı", "parsel", "kaks", "taks")):
        t1, t2 = "İMAR VE PARSELASYON", "ASKI VE İTİRAZ SÜRECİ"
    elif any(w in (metin_tum + " " + kat).lower() for w in ("kira", "tahliye", "kiracı", "ev sahibi", "depozito")):
        t1, t2 = "KİRA VE TAHLİYE", "YASAL HAK VE SÜREÇLER"
    else:
        if spot:
            ilk_spot_cumle = re.split(r"(?<=[.!?;])\s+", str(spot).strip())[0]
            k_spot = [k.rstrip(".,;") for k in ilk_spot_cumle.split() if len(k) > 2]
            if 3 <= len(k_spot) <= 7:
                s1, s2 = _dengeli_bol(k_spot)
                t1, t2 = tr_upper(s1), tr_upper(s2)
            else:
                t1, t2 = "SEKTÖR GÜNDEMİ", "GÜNCEL GELİŞME VE ANALİZ"
        else:
            t1, t2 = "SEKTÖR GÜNDEMİ", "GÜNCEL GELİŞME VE ANALİZ"

    return {
        "format": "minimal_vurgu",
        "kicker": "ÖNEMLİ GELİŞME",
        "t1": t1,
        "t2": t2,
        "renk": VURGU,
    }


def hook_rengi_belirle(
    canvas: Image.Image,
    x: int,
    y: int,
    w: int = 650,
    h: int = 140,
    tercih_edilen_renk: Optional[Tuple[int, int, int]] = None,
    varsayilan_dikkat_rengi: Tuple[int, int, int] = VURGU,
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


# Kanca ile başlık bloğu arasında bırakılacak EN AZ boşluk (instabot standardı).
# Kanca fotoğrafın içinde durmalı, metin rafının veya manşetin üstüne oturmamalı.
AYRIM_PAYI = 130
LOGO_ALT_SINIR = 500


def _bant_yogunlugu(edges: Image.Image, x0: int, y0: int, x1: int, y1: int) -> float:
    """Bir bandın kenar yoğunluğu — yazı ve ince detay burada yükselir."""
    from PIL import ImageStat
    if y1 <= y0 or x1 <= x0:
        return 999.0
    return ImageStat.Stat(edges.crop((x0, y0, x1, y1))).mean[0]


def uygun_alan_tespit_et(gorsel: Image.Image, baslik_ust: int, hook_h: int = 220, ust_sinir: int = 380) -> Tuple[str, int]:
    """Fotoğrafın kanca çizilmeye en sakin, ferah alanını tespit eder (instabot paritesi)."""
    from PIL import ImageFilter
    en_alt = baslik_ust - hook_h - AYRIM_PAYI
    varsayilan_y = max(ust_sinir, en_alt)
    try:
        genislik, _ = gorsel.size
        edges = gorsel.convert("L").filter(ImageFilter.FIND_EDGES)
        sag = min(genislik - KENAR_BOSLUK, 1006)
        adaylar = list(range(max(ust_sinir, 380), max(ust_sinir + 1, en_alt + 1), 45))
        if not adaylar:
            return "zemin", varsayilan_y
        olculen = [(_bant_yogunlugu(edges, KENAR_BOSLUK, y, sag, y + hook_h), y) for y in adaylar]
        en_dusuk = min(t[0] for t in olculen)
        y_sec = max(y for yog, y in olculen if yog <= en_dusuk + 2.0)
        return ("zemin" if y_sec >= en_alt - 45 else "foto"), y_sec
    except Exception as e:
        log.warning("Hook alan tespitinde hata: %s", e)
        return "zemin", varsayilan_y


def _metin_kutusu(oncesi: Image.Image, sonrasi: Image.Image) -> Optional[Tuple[int, int, int, int]]:
    """Çizilen kancanın GERÇEK metin sınırlarını döndürür."""
    try:
        from PIL import ImageChops
        return (ImageChops.difference(oncesi.convert("RGB"), sonrasi.convert("RGB"))
                .convert("L").point(lambda v: 255 if v > 110 else 0).getbbox())
    except Exception:
        return None


def hook_uygula(
    canvas: Image.Image,
    haber: Dict[str, Any],
    manset_ust_y: int,
    ust_y: int = 62,
    olcu: str = "besleme",
) -> Image.Image:
    """
    Kapak slaytına (Slayt 1) akıllı editoryal hook metnini ve difüzyon gölgesini yerleştirir.
    Instabot standardında AYRIM_PAYI (130px) ile başlığa asla yapışmaz; başlığı tekrarlıyorsa hiç çizilmez.
    """
    hook_veri = hook_olustur(haber)
    if not hook_veri:
        return canvas

    fmt = hook_veri.get("format", "minimal_vurgu")
    override_renk = haber.get("hook_renk_override")
    hook_h = 240 if fmt == "stat_punch" else (220 if hook_veri.get("t2") else 150)
    min_tavan = max(ust_y + 80, 240)
    logo_alt = max(ust_y + 130, 380)
    en_alt = manset_ust_y - hook_h - AYRIM_PAYI

    if en_alt < min_tavan:
        log.warning("Kanca için dikey alan yetersiz (en_alt=%d < min_tavan=%d), kancasız çiziliyor", en_alt, min_tavan)
        return canvas

    # 1. Fotoğrafın en sakin alanını tespit et
    hedef_ust = min(logo_alt, en_alt)
    konum, y = uygun_alan_tespit_et(canvas, manset_ust_y, hook_h=hook_h, ust_sinir=hedef_ust)
    if y is None:
        y = max(min_tavan, en_alt)

    # Üst ve alt sınır garantisi: Başlığa AYRIM_PAYI'ndan daha fazla yaklaşamaz
    y = max(min_tavan, min(y, en_alt))
    x_pos = KENAR_BOSLUK


    # Dinamik renk belirleme
    renk = hook_rengi_belirle(
        canvas=canvas,
        x=x_pos,
        y=y,
        w=650,
        h=hook_h,
        tercih_edilen_renk=override_renk,
        varsayilan_dikkat_rengi=hook_veri.get("renk", VURGU),
    )

    def _ciz(hedef: Image.Image, cizim_y: int) -> Image.Image:
        if fmt == "stat_punch":
            return ciz_stat_punch(
                hedef,
                x=x_pos,
                y=cizim_y,
                num_txt=hook_veri.get("num_txt", ""),
                unit_txt=hook_veri.get("unit_txt", ""),
                lbl_txt=hook_veri.get("lbl_txt", ""),
                t1=hook_veri.get("t1", ""),
                t2=hook_veri.get("t2", ""),
                renk=renk,
            )
        else:
            return ciz_minimal_vurgu(
                hedef,
                x=x_pos,
                y=cizim_y,
                kicker=hook_veri.get("kicker", ""),
                t1=hook_veri.get("t1", ""),
                t2=hook_veri.get("t2", ""),
                renk=renk,
            )

    sonuc = _ciz(canvas, y)

    # Nefes payı denetimi: Metin başlığa AYRIM_PAYI'ndan daha fazla yaklaştıysa yukarı al
    kutu = _metin_kutusu(canvas, sonuc)
    if kutu:
        tasma = kutu[3] - (manset_ust_y - AYRIM_PAYI)
        if tasma > 0:
            y = max(min_tavan, y - int(tasma))
            sonuc = _ciz(canvas, y)

    log.info("Hook başarıyla çizildi: fmt=%s, y=%d (ayrım payı %d)", fmt, y, AYRIM_PAYI)
    return sonuc
