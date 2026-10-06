"""
haber_tasarim.py — Haber tasarımı: Instabot (Daily Brief) ile AYNI, EDM kimliğiyle.

KURAL (kullanıcı kararı, 2026-10-07): haber içeriğinde her şey Instabot'la aynıdır;
yalnızca logo ve renkler EDM'indir. Bu yüzden çizim kodu Instabot'un `make_image.py`
dosyasından AST ile BİREBİR çıkarıldı (`scratchpad` betiği, yorumlarıyla birlikte);
elle yeniden yazılmadı. Aşağıdaki "EDM TEMASI" bölümü dışındaki her şey Instabot'tur:
fotoğraf yerleşimi (1150 px'e iniş + göl yansıması + yumuşak perde), başlık/özet
dizgisi (`**` vurgu), detay sayfaları (iri giriş paragrafı, vurgu rakamı, alıntı,
dengeli sayfalama), bayrak flaması, alt bilgi. Instabot'ta düzeltme yapılınca burada
da yapılmalı: iki tarafı karşılaştırmak için `src/haber_tasarim.py` ↔
`instabot/src/make_image.py`.

ANA KARE: tek bir 1080x1920 çizilir ve TÜM içerik 4:5 merkez kutusunda
(y=285..1635) durur (`STORY_GUVENLI_PAY`). 9:16 (Story, Reels, Shorts, TikTok)
ana kare olduğu gibi kullanılır; akış (4:5) ana karenin ortadan 1080x1350
kırpılmasıdır. Kutunun dışı yalnızca fotoğraf ve zemindir; kırpılınca kaybolan şey
yoktur. Bu yüzden 4:5 ve 9:16 hiçbir zaman ayrı yerleşim değildir.

YAZI TİPİ: Inter Variable (Instabot'unkiyle aynı dosya, md5 aynı). Türkçe karakter
kapsamı ÖLÇÜLDÜ: ğ Ğ ş Ş ı İ ö Ö ü Ü ç Ç ₺ % ’ “ ” … — · × hiçbiri eksik değil.
(`Fraunces-Variable`, `IBMPlexSans-Variable` ve `IBMPlexMono-Regular` dosyaları ise
Latin alt kümesidir: ğ ş İ ₺ yok, bu modülde kullanılmaz.)
"""

from __future__ import annotations

import itertools
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from . import config, fetch_flag

log = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# EDM TEMASI — Instabot'tan TEK fark burası (logo, renkler, alan adı)
# ----------------------------------------------------------------------
# Kurumsal kimlik: %70 nötr / %25 mürekkep / %5 kırmızı. Amber, turkuaz ve yeşil
# yok (MEMORY.md §8.7); Instabot'un bu renkleri EDM'de kırmızı, kireç ve kurşunla
# karşılanır.
ZEMIN = (18, 19, 22)            # Mürekkep #121316 (Instabot: koyu turkuaz/mor)
VURGU = (255, 59, 48)           # koyu zeminde canlı kırmızı #ff3b30 (Instabot: amber)
VURGU_DERIN = (196, 3, 15)      # Derin Kırmızı #C4030F (dolgu)
PARLAK = (244, 244, 242)        # Kağıt #F4F4F3
ACIK = (228, 228, 225)          # Kireç #E4E4E1
GOVDE = (208, 208, 206)
SOLUK = (176, 176, 174)
IKINCIL = (138, 139, 143)       # Kurşun #8A8B8F (Instabot: turkuaz)

# KIRMIZI METİN YALNIZCA DÜZ KOYU ZEMİNDE (detay sayfaları, çizgi ve çentikler).
# Fotoğraf üstünde kırmızı metin okunmuyor: Instabot'ta ölçüldü (kırmızı #EF4444
# kontrast 2,02; büyük metin eşiği 3,00). EDM'de kanca bu yüzden dolgu plakalıdır
# (hook_motoru.py).

ALAN_ADI = "edmyapigayrimenkul.com"
LOGO_GENISLIK = 300             # yatay logo, Instabot'taki 144 px yuvarlak logonun karşılığı

KOK = config.KOK_DIZIN
FONT_YOLU = config.yol_al("assets/fonts/Inter-Variable.ttf")
LOGO_KLASORU = config.yol_al("assets/icons")

GENISLIK, YUKSEKLIK = 1080, 1920
STORY_GENISLIK, STORY_YUKSEKLIK = GENISLIK, YUKSEKLIK
KUTU_UST = (YUKSEKLIK - 1350) // 2      # 285
KUTU_ALT = KUTU_UST + 1350              # 1635

AYARLAR: Dict[str, Any] = {
    "gorsel": {
        "genislik": GENISLIK, "yukseklik": YUKSEKLIK,
        "kenar_bosluk": 80, "dikey_guvenli_pay": 330,
        "kanal_ikon_boyu": 34, "kanca_ciz": True,
        "perde_rengi": list(ZEMIN),
    },
    "sosyal": {"kanallar": ["instagram", "threads", "facebook", "youtube", "tiktok"]},
}


def serit_rengi(kategori: str, g: dict) -> tuple:
    """EDM'de kategoriye göre renk şeridi yok: tek kurumsal mürekkep (Instabot: kategori rengi)."""
    return ZEMIN


def arkaplan_uret_yedek(kategori: str, genislik: int, yukseklik: int, g: dict | None = None) -> Image.Image:
    """Fotoğraf yoksa düz mürekkep gradyanı (Instabot: kategori renginden gradyan)."""
    ust, alt = ZEMIN, tuple(min(255, k + 14) for k in ZEMIN)
    gorsel = Image.new("RGB", (genislik, yukseklik), ust)
    ciz = ImageDraw.Draw(gorsel)
    for y in range(yukseklik):
        o = y / yukseklik
        ciz.line([(0, y), (genislik, y)],
                 fill=tuple(int(ust[i] + (alt[i] - ust[i]) * o) for i in range(3)))
    return gorsel


def _logoyu_bas(gorsel: Image.Image, x: int, y: int, boy: int = 144) -> Image.Image:
    """EDM yatay logosu (Instabot: yuvarlak DailyBrief logosu). `boy` yok sayılır."""
    from . import make_image
    try:
        tuval = gorsel.convert("RGB")
        make_image._logo_yerlestir(tuval, beyaz=True, x=x, y=y, lw=LOGO_GENISLIK, golge=True, kirmizi_zemin=False)
        return tuval
    except Exception as e:
        log.warning("logo basılamadı: %s", e)
        return gorsel


def _font(punto: int, eksenler: list[float]) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONT_YOLU), punto)
    try:
        f.set_variation_by_axes(eksenler)
    except Exception:
        pass            # değişken font desteği yoksa varsayılan ağırlıkla devam
    return f


# ======================================================================
# INSTABOT KODU (birebir) — değiştirme; Instabot'ta düzelt, buraya taşı
# ======================================================================

# Inter değişken fontunun eksen sırası: [Optical size, Weight]
EKSEN_BASLIK = [32.0, 800.0]      # kalın, büyük punto için


EKSEN_OZET = [20.0, 450.0]        # başlık altı özet — ince, okunur


EKSEN_KUCUK = [14.0, 600.0]       # alt bilgi satırı


def _buyuk_harf(metin: str) -> str:
    """
    Türkçeye uygun büyük harf çevirimi.

    Python'un `.upper()` metodu 'i' harfini 'I' yapıyor, oysa Türkçede
    doğrusu 'İ'. İlk denemede ülke adı "TÜRKIYE" çıktı — bir haber
    hesabında bu hatayı yapmak kötü görünür. Aynı şekilde 'ı' da 'I'
    olmalı, Python bunu zaten doğru yapıyor ama açıkça yazmak
    davranışı ileride tahmin edilebilir kılıyor.
    """
    return metin.replace("i", "İ").replace("ı", "I").upper()


def _kelimeleri_satir_yap(kelimeler: list[tuple[str, bool]]) -> str:
    """
    Kelimeleri birleştirir; ardışık bold kelimeleri tek bir **word1 word2** içine alır.
    Kesme işareti ve noktalamaları önceki kelimeye boşluksuz bağlar.
    """
    parcalar = []
    bold_grup = []
    for w, is_b in kelimeler:
        if is_b:
            bold_grup.append(w)
        else:
            if bold_grup:
                joined = " ".join(bold_grup)
                parcalar.append(f"**{joined}**")
                bold_grup = []
            parcalar.append(w)
    if bold_grup:
        joined = " ".join(bold_grup)
        parcalar.append(f"**{joined}**")

    satir = ""
    for p in parcalar:
        if not satir:
            satir = p
        elif p.startswith(("'", "’", ",", ".", ":", ";", "!", "?", ")", "]", "”")):
            satir += p
        else:
            satir += f" {p}"
    return satir


UNVAN_VE_KISALTMALAR = {
    "dr.", "dr", "doç.", "doç", "prof.", "prof", "av.", "av", "yrd.", "yrd",
    "uzm.", "uzm", "müh.", "müh", "mim.", "mim", "sn.", "sn", "sayın",
    "gen.", "gen", "alb.", "alb", "bnb.", "bnb", "yzb.", "yzb",
    "tğm.", "tğm", "ütğm.", "ütğm", "astsb.", "astsb",
    "md.", "md", "mad.", "mad", "sf.", "sf", "no.", "no", "nr.", "nr"
}


BUYUKLUK_KELIMELERI = {"bin", "milyon", "milyar", "trilyon"}


PARA_BIRIMLERI = {"₺", "$", "€", "£", "tl", "try", "usd", "eur"}


def _is_para_birimi(w: str) -> bool:
    """Para sembolü, birim veya ekli halini (₺, ₺'ye, TL'de, $'a vb.) tespit eder."""
    if not w:
        return False
    if w.startswith(("₺", "$", "€", "£")):
        return True
    clean = re.sub(r"[^\w₺$€£]", "", w.lower())
    if clean in PARA_BIRIMLERI or any(clean.startswith(p) for p in ("₺", "tl", "try", "usd", "eur")):
        return True
    return bool(re.match(r"^(?:₺|\$|€|£|tl|try|usd|eur)(?:'[\wğüşıöç]+)?$", w, re.IGNORECASE))


def _is_sayi(w: str) -> bool:
    """Sayısal değer veya tutar (2.500, 45,50, 100 vb.) olup olmadığını denetler."""
    if not w:
        return False
    clean = re.sub(r"[\.,]", "", w.strip("*_"))
    return clean.isdigit()


def _is_unvan_veya_on_ek(w: str) -> bool:
    """Unvan, kısaltma veya sıra sayısı (Doç., Dr., Prof., 14. vb.) olup olmadığını denetler."""
    if not w:
        return False
    clean = w.lower().strip("*_()[]")
    if clean in UNVAN_VE_KISALTMALAR:
        return True
    if re.match(r"^\d+\.$", clean):
        return True
    return False


def _satirlara_bol(metin: str, font, azami_genislik: int, ciz) -> list[str]:
    """
    Kelime kelime ilerleyip satır genişliğini aşmadan böler.
    Satır bölünmelerinde **bold** etiketlerinin kopmasını önler.
    ₺ gibi para birimlerinin önceki rakamdan ve unvanların sonraki kelimeden
    kopmasını engelleyen akıllı yapışkanlık (glue) kurallarını uygular.
    """
    if not metin:
        return []

    from . import filtre
    metin = filtre.tipografi_temizle(metin)

    # 1. Regex ile metni (**bold** ve düz) parçala
    pattern = re.compile(r"(\*\*[^*]+\*\*)")
    parts = pattern.split(metin)
    tokens: list[tuple[str, bool]] = []

    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) >= 4:
            clean_part = part[2:-2]
            for w in clean_part.split():
                if w:
                    tokens.append((w, True))
        else:
            for w in part.split():
                if w:
                    tokens.append((w, False))

    if not tokens:
        return []

    # EDM YAMASI (2026-10-07): satıra sığmayan TEK kelime (uzun URL, birleşik kelime)
    # tuvali taşırıyordu. Kelime, satıra sığan en uzun parçalara bölünür.
    genisletilmis: list[tuple[str, bool]] = []
    for w, b in tokens:
        while ciz.textlength(w, font=font) > azami_genislik and len(w) > 1:
            alt, ust = 1, len(w) - 1
            while alt < ust:
                orta = (alt + ust + 1) // 2
                if ciz.textlength(w[:orta], font=font) <= azami_genislik:
                    alt = orta
                else:
                    ust = orta - 1
            genisletilmis.append((w[:alt], b))
            w = w[alt:]
        genisletilmis.append((w, b))
    tokens = genisletilmis

    # 2. Satırlara böl ve yapışkanlık kurallarını işlet
    satirlar = []
    gecerli_kelimeler = []
    gecerli_str = ""

    for word, bold in tokens:
        aday_str = f"{gecerli_str} {word}".strip()
        if ciz.textlength(aday_str, font=font) <= azami_genislik:
            gecerli_str = aday_str
            gecerli_kelimeler.append((word, bold))
        else:
            tasinanlar = []

            # Kural 1: Para / birim sembolü taşıyorsa önceki rakamı ve büyüklüğü beraberinde çeksin
            if _is_para_birimi(word) and gecerli_kelimeler:
                if (len(gecerli_kelimeler) >= 2
                        and gecerli_kelimeler[-1][0].lower().strip("*") in BUYUKLUK_KELIMELERI
                        and _is_sayi(gecerli_kelimeler[-2][0])):
                    if len(gecerli_kelimeler) > 2:
                        b = gecerli_kelimeler.pop()
                        s = gecerli_kelimeler.pop()
                        tasinanlar = [s, b]
                elif _is_sayi(gecerli_kelimeler[-1][0]):
                    if len(gecerli_kelimeler) > 1:
                        tasinanlar = [gecerli_kelimeler.pop()]

            # Kural 2: Büyüklük (bin, milyon) taşıyorsa önceki sayıyı çeksin
            elif word.lower().strip("*") in BUYUKLUK_KELIMELERI and gecerli_kelimeler:
                if _is_sayi(gecerli_kelimeler[-1][0]) and len(gecerli_kelimeler) > 1:
                    tasinanlar = [gecerli_kelimeler.pop()]

            # Kural 3: Satır sonunda unvan/ön ek kaldıysa (Doç., Dr., 14.), yeni satıra taşınsın
            elif gecerli_kelimeler:
                while len(gecerli_kelimeler) > 1 and _is_unvan_veya_on_ek(gecerli_kelimeler[-1][0]):
                    tasinanlar.insert(0, gecerli_kelimeler.pop())

            if gecerli_kelimeler:
                satirlar.append(_kelimeleri_satir_yap(gecerli_kelimeler))

            gecerli_kelimeler = tasinanlar + [(word, bold)]
            gecerli_str = " ".join(w for w, _ in gecerli_kelimeler)

    if gecerli_kelimeler:
        satirlar.append(_kelimeleri_satir_yap(gecerli_kelimeler))

    return satirlar


def _formatli_satir_ciz(
    ciz: ImageDraw.ImageDraw,
    x: int,
    y: int,
    satir: str,
    punto: int,
    spot: bool = False,
    varsayilan_renk: tuple[int, int, int] | None = None,
) -> None:
    """
    Satırdaki metni çizer; vurgu ve tırnak işaretlerini tipografik olarak işler:
      * Normal metinde **bold** vurgusu -> kalın ve parlak beyaz (veya altın rengi)
      * Spot (kalın) metinde **vurgu** -> normal/ince ağırlık (zıt ağırlık efekti)
      * Tırnak içindeki söylemler "..." veya “...” -> açık parlak beyaz
    """
    base_wght = 750.0 if spot else 450.0
    vurgu_wght = 400.0 if spot else 800.0

    f_norm = _font(punto, [20.0, base_wght])
    f_vurgu = _font(punto, [20.0, vurgu_wght])

    c_norm = varsayilan_renk or ((255, 255, 255) if spot else GOVDE)
    c_vurgu = VURGU if spot else (255, 255, 255)
    c_alinti = PARLAK

    desen = re.compile(r'(\*\*[^*]+\*\*|\"[^\"]+\"|“[^”]+”)')
    cur_x = x
    son = 0
    for m in desen.finditer(satir):
        if m.start() > son:
            t = satir[son:m.start()].replace("**", "")
            ciz.text((cur_x, y), t, font=f_norm, fill=c_norm)
            cur_x += int(ciz.textlength(t, font=f_norm))
        ham = m.group()
        if ham.startswith('**') and ham.endswith('**'):
            t = ham[2:-2].replace("**", "")
            ciz.text((cur_x, y), t, font=f_vurgu, fill=c_vurgu)
            cur_x += int(ciz.textlength(t, font=f_vurgu))
        elif (ham.startswith('"') and ham.endswith('"')) or (ham.startswith('“') and ham.endswith('”')):
            # ⚠️ TIRNAK DALI DA YILDIZI TEMİZLEMELİ (7 Eyl 2026).
            # Desen `**kalın**` ve `"alıntı"` kalıplarını AYNI alternasyonda
            # arıyor; metin `"**Yurt kazandı**"` gibi İÇ İÇE olduğunda tırnak
            # alternatifi kazanıyor ve bu dal `ham`i olduğu gibi çiziyordu.
            # Sonuç slaytta göründü: « " **Yurt kazandı** " ». Kalın dalında
            # `.replace("**","")` vardı, burada yoktu.
            t = ham.replace("**", "")
            ciz.text((cur_x, y), t, font=f_vurgu, fill=c_alinti)
            cur_x += int(ciz.textlength(t, font=f_vurgu))
        son = m.end()
    if son < len(satir):
        t = satir[son:].replace("**", "")
        ciz.text((cur_x, y), t, font=f_norm, fill=c_norm)
        cur_x += int(ciz.textlength(t, font=f_norm))


# ⚠️ BAŞLIK PUNTO TAVANI — 96'dan 80'e indirildi (18 Ağu 2026).
#
# 96 tavanla ölçüldü: bir turdaki 10 başlığın 8'i altı satırı doldurup
# 640-700 px kaplıyordu, yani slaytın yarısını. Yazı alanı büyüdükçe
# okuma perdesi de büyüyor ve arka plandaki fotoğraf neredeyse tamamen
# örtülüyordu — kullanıcının şikâyeti buydu.
#
# Ölçüm (aynı 10 başlık, ortalama kapladığı yükseklik):
#     96 -> 643 px  (8/10 başlık altı satır)
#     88 -> 556 px  (5/10)
#     80 -> 446 px  (1/10)
#     72 -> 374 px  (0/10)   <- seçilen
#
# 72'ye inildi (18 Ağu, kullanıcı isteği): başlık artık düz renk şeridin
# değil fotoğrafın üstünde duruyor, yer kapladıkça fotoğrafı örtüyor.
# Daha aşağı inilmedi — manşetin uzaktan okunabilmesi bu tasarımın temel
# şartı, slayt kaydırılırken haber ÖĞRENİLMİŞ olmalı.
BASLIK_PUNTO_TAVAN = 72


def _basligi_yerlestir(metin: str, ciz, alan_genislik: int, alan_yukseklik: int):
    """
    Başlığı alana sığdıran en büyük puntoyu bulur.
    Büyükten küçüğe deniyoruz: başlık kısaysa iri, uzunsa küçük olsun.
    """
    for punto in range(BASLIK_PUNTO_TAVAN, 39, -4):
        font = _font(punto, EKSEN_BASLIK)
        satirlar = _satirlara_bol(metin, font, alan_genislik, ciz)
        satir_yuksekligi = int(punto * 1.22)
        toplam = satir_yuksekligi * len(satirlar)
        if toplam <= alan_yukseklik and len(satirlar) <= 6:
            return font, satirlar, satir_yuksekligi

    # Buraya düşerse başlık aşırı uzun — en küçük puntoyla kırpıyoruz
    font = _font(40, EKSEN_BASLIK)
    satirlar = _satirlara_bol(metin, font, alan_genislik, ciz)[:6]
    return font, satirlar, int(40 * 1.22)


def _ozeti_yerlestir(metin: str, ciz, alan_genislik: int, azami_satir: int = 4, punto: int = 34):
    """
    Başlık altındaki özet satırını böler. Başlıktan farklı olarak punto
    sabit: özet her slaytta aynı boyda olmalı, yoksa carousel kayarken
    yazı boyu zıplıyor gibi görünür.
    """
    font = _font(punto, EKSEN_OZET)
    satirlar = _satirlara_bol(metin, font, alan_genislik, ciz)
    if len(satirlar) > azami_satir:
        satirlar = satirlar[:azami_satir]
        son = satirlar[-1].rstrip(" ,;:")
        # EDM YAMASI: "…" eklenince satır kenara taşıyordu (kenara 0 px); sığana dek kelime atılır.
        while " " in son and ciz.textlength(son.replace("**", "") + "…", font=font) > alan_genislik:
            son = son.rsplit(" ", 1)[0].rstrip(" ,;:")
        satirlar[-1] = son + "…"
    return font, satirlar, int(punto * 1.42)


def _perde_taban_alfa(arkaplan: Image.Image, kutu: tuple) -> int:
    """
    Yazının oturacağı kutudaki ortalama parlaklığa bakıp perdenin ne kadar
    koyu olması gerektiğini söyler.

    Neden gerekli: sabit perde her arka planda aynı işi görmüyor. Koyu
    gradyanda gereğinden fazlaydı, açık gri bir duvar fotoğrafında ise
    yetersiz kaldı — ilk denemede başlığın üst satırı fotoğrafın içinde
    eridi. Perdeyi arka plana göre ayarlamak bunu kökten çözüyor.
    """
    parca = arkaplan.convert("L").crop(kutu)
    ortalama = sum(parca.get_flattened_data()) / max(1, parca.width * parca.height)
    # Ölçüldü: gradyan arka planın yazı bölgesi ~43, açık bir portre ~123.
    # 55'in altı zaten yeterince koyu, orada perde çizmek gradyanın üstünde
    # görünür bir bant bırakıyordu — o yüzden 0'a düşüyor.
    #   43  -> 0    (gradyan: perde yok, temiz kalır)
    #   123 -> 130  (portre: başlık ayrışır)
    #   200 -> 232  (parlak arka plan: güçlü perde)
    return max(0, min(245, int((ortalama - 55) * 1.63)))


# --- YATAY FOTOĞRAF YERLEŞİMİ (3 Eyl 2026, kullanıcı isteği) ---
#
# ⚠️ ESKİ HÂLİ: yatay fotoğraf 720px'de kesiliyordu ve başlık 1140'ta
# başlıyordu — arada ~420px "ne fotoğraf ne yazı" olan ölü bant kalıyordu.
# Kullanıcı: *"neden yazının çok üstünde yatay bir şekilde duruyor resim,
# ayrık duruyor çok fazla, burada açıklamaya kadar resim olurdu"*.
#
# Dört varyant üretilip yan yana gösterildi (720 / 1150 / 1450 / 1920) ve
# 1150 seçildi. Gerekçe: başlık fotoğrafın üstüne oturuyor (ayrıklık
# bitiyor) ama fotoğrafın ANLATTIĞI ŞEY bozulmuyor. 1450 ve 1920'de zoom
# arttıkça kadraj dağılıyor — Fed örneğinde madalyon iki yandan kesiliyordu.
FOTO_HEDEF_ALT = 1150


# ⚠️ BÜYÜTME TAVANI. Yatay fotoğrafı dikey tuvale yaymak onu BÜYÜTMEK
# demek ve büyütme bulanıklaştırır. Zoom oranı basitçe
# `hedef_yukseklik / kaynak_yukseklik`. 1200x709'luk tipik bir OG
# fotoğrafı 1150'ye çıkarken 1.62x büyüyor ve temiz kalıyor; küçük bir
# kaynakta aynı hedef yumuşama yaratır. O yüzden hedef sabit değil:
# fotoğraf yeterince büyük değilse daha AZ iniyor. Bulanık basmaktansa
# biraz daha kısa dursun.
FOTO_AZAMI_BUYUTME = 1.9


# Fotoğrafın en az ineceği yer — eski davranışın tabanı.
FOTO_ASGARI_ALT = 720


def _perde_maskesi(genislik: int, yukseklik: int,
                   bas: int, son: int) -> Image.Image:
    """
    Fotoğraftan düz zemine geçiş maskesi (0 = fotoğraf, 255 = düz zemin).

    ⚠️ EĞRİ SMOOTHSTEP: `t*t*(3-2t)`. Kullanıcı isteği (3 Eyl 2026):
    *"alt ve üst arasında renkleri bağlayıcı, biraz daha soft geçiş"*.
    Eski eğri `t**1.8` idi ve BAŞLANGICI KESKİNDİ — türevi 0 noktasında
    sıfır değil, yani perdenin nerede başladığı ince bir çizgi olarak
    görünüyordu. Smoothstep'in iki ucunda da türev sıfır, bu yüzden ne
    başladığı ne bittiği yer belli oluyor.

    ⚠️ PERFORMANS: eski kod her piksel için `putpixel` çağırıyordu —
    1080x1920 = 2 milyon Python çağrısı, slayt başına saniyeler.
    Degrade yalnızca Y'ye bağlı olduğu için 1 piksel genişliğinde
    üretilip yatayda geriliyor.
    """
    seritler = []
    for y in range(yukseklik):
        if y <= bas:
            v = 0
        elif y >= son:
            v = 255
        else:
            t = (y - bas) / (son - bas)
            v = int(255 * (t * t * (3 - 2 * t)))      # smoothstep
        seritler.append(v)
    serit = Image.new("L", (1, yukseklik))
    serit.putdata(seritler)
    return serit.resize((genislik, yukseklik), Image.BILINEAR)


def _yansima_ekle(canvas: Image.Image, foto: Image.Image,
                  foto_alt: int, yukseklik: int,
                  derinlik: int | None = None) -> None:
    """
    Fotoğrafın alt kenarına GÖL YANSIMASI ekler (yerinde değiştirir).

    ⚠️ NEDEN GEREKTİ (3 Eyl 2026, kullanıcı): *"bazı fotolarda fotoğrafın
    hemen altındaki alan çok keskin bir şekilde bitiyor"*. Fotoğraf
    `foto_alt`'ta bitiyor, altında bulanık ambiyans başlıyor ve ikisinin
    arasında NET BİR ÇİZGİ kalıyordu. Perde o çizgiyi ancak yeterince
    aşağıdaysa gizliyor; büyütme tavanı yüzünden fotoğraf erken bittiğinde
    (küçük kaynak) çizgi perdenin şeffaf bölgesine denk gelip görünüyordu.

    Çözüm: fotoğrafın alt şeridini dikey çevirip altına koymak. Su
    yüzeyindeki yansıma gibi — kenar artık "kesilmiş" değil, görüntünün
    kendi devamı oluyor. İçerik ilgili kaldığı için bulanık ambiyanstan
    da iyi duruyor.

    Aşağı indikçe hem SOLUYOR hem BULANIKLAŞIYOR: gerçek su yansıması da
    öyle davranır, sabit opaklıkta bir ayna görüntüsü yapay duruyor.
    """
    bosluk = yukseklik - foto_alt
    if bosluk <= 8:
        return                                     # yansımaya yer yok

    derinlik = derinlik or min(bosluk, int(foto_alt * 0.42))
    if derinlik < 24:
        return

    genislik = canvas.width
    # Fotoğrafın en alt `derinlik` kadarını al ve dikey çevir
    serit = canvas.crop((0, max(0, foto_alt - derinlik), genislik, foto_alt))
    yansima = serit.transpose(Image.FLIP_TOP_BOTTOM)

    # ⚠️ Bulanıklık YUKARIDAN AŞAĞI artmalı. Tek seferde blur uygulamak
    # yansımanın üst ucunu da bulanıklaştırır ve birleşme yeri yine
    # belli olur. Bantlara bölüp her banda kendi yarıçapını veriyoruz.
    bant = max(8, derinlik // 12)
    parcalar = []
    for ust in range(0, derinlik, bant):
        alt = min(ust + bant, derinlik)
        t = ust / derinlik
        parca = yansima.crop((0, ust, genislik, alt))
        yaricap = 0.6 + t * 5.0
        parcalar.append((ust, parca.filter(ImageFilter.GaussianBlur(yaricap))))
    for ust, parca in parcalar:
        yansima.paste(parca, (0, ust))

    # Solma maskesi: üstte yarı görünür, altta tamamen kayıp
    alfa = []
    for y in range(derinlik):
        t = y / derinlik
        alfa.append(int(150 * (1 - t) ** 1.6))
    m = Image.new("L", (1, derinlik))
    m.putdata(alfa)
    maske = m.resize((genislik, derinlik), Image.BILINEAR)

    canvas.paste(yansima, (0, foto_alt), maske)


def fotograftan_arkaplan(
    foto: Image.Image, genislik: int, yukseklik: int
) -> Image.Image:
    """
    Ham haber veya basın fotoğrafını 1080x1920 dikey Story tuvaline akıllıca yerleştirir.

    - EXIF yön matrisini (ImageOps.exif_transpose) otomatik uygular; asla yan veya ters dönmez.
    - Dikey portreleri (ratio <= 0.8) üstten hizalı ve doğal derinlikle yerleştirir.
    - Yatay/16:9 basın fotoğraflarını (ratio > 0.8) aşırı dijital zoom ile kesip bulanıklaştırmak
      yerine, geniş kadrajıyla üst alana yerleştirir, arka plana yumuşak ambiyans ışıltısı verir
      ve alt metin alanına kesintisiz editoryal degrade ile eritir.
    """
    foto = ImageOps.exif_transpose(foto).convert("RGB")
    f_genislik, f_yukseklik = foto.size
    foto_oran = f_genislik / f_yukseklik

    canvas = Image.new("RGB", (genislik, yukseklik), ZEMIN)

    if foto_oran <= 0.78:
        # Doğal dikey portre (9:16 veya 4:5 portre)
        hedef_oran = genislik / yukseklik
        if foto_oran > hedef_oran:
            yeni_genislik = int(f_yukseklik * hedef_oran)
            sol = (f_genislik - yeni_genislik) // 2
            foto_c = foto.crop((sol, 0, sol + yeni_genislik, f_yukseklik))
        else:
            yeni_yukseklik = int(f_genislik / hedef_oran)
            ust = int((f_yukseklik - yeni_yukseklik) * 0.12)
            foto_c = foto.crop((0, ust, f_genislik, ust + yeni_yukseklik))
        foto_res = foto_c.resize((genislik, yukseklik), Image.LANCZOS)
        canvas.paste(foto_res, (0, 0))
    else:
        # Yatay veya kare fotoğraf (16:9 HD, 4:3, 1:1)
        # 1. Arka plan ambiyans ışıltısı (keskin kenar/boşluk olmaması için)
        ambiyans = foto.resize((genislik, yukseklik), Image.BILINEAR)
        ambiyans = ambiyans.filter(ImageFilter.GaussianBlur(radius=40))
        # Koyu overlay
        amb_draw = ImageDraw.Draw(ambiyans, "RGBA")
        amb_draw.rectangle([0, 0, genislik, yukseklik], fill=(*ZEMIN, 150))
        canvas.paste(ambiyans, (0, 0))

        # 2. Fotoğrafı başlığın başladığı yere KADAR indir.
        #    Ölçekli tuvale oranla: 1920'lik tasarımda 1150.
        hedef_alt = int(FOTO_HEDEF_ALT * yukseklik / 1920)
        taban_alt = int(FOTO_ASGARI_ALT * yukseklik / 1920)

        # ⚠️ BÜYÜTME TAVANI — bulanık basmaktansa daha kısa dur.
        # Geniş fotoğrafta zoom = hedef_yukseklik / kaynak_yukseklik.
        tavan_alt = int(f_yukseklik * FOTO_AZAMI_BUYUTME)
        hedef_alt = max(taban_alt, min(hedef_alt, tavan_alt))

        # Tuvali (genislik x hedef_alt) KAPLAYACAK şekilde kırp
        hedef_oran = genislik / hedef_alt
        if foto_oran > hedef_oran:
            yeni_w = int(f_yukseklik * hedef_oran)
            sol_k = (f_genislik - yeni_w) // 2
            foto_k = foto.crop((sol_k, 0, sol_k + yeni_w, f_yukseklik))
        else:
            yeni_h = int(f_genislik / hedef_oran)
            foto_k = foto.crop((0, 0, f_genislik, yeni_h))

        canvas.paste(foto_k.resize((genislik, hedef_alt), Image.LANCZOS), (0, 0))

        # Alt kenardaki keskin kesimi göl yansımasıyla yumuşat
        _yansima_ekle(canvas, foto, hedef_alt, yukseklik)

    # 3. Fotoğraftan düz zemine YUMUŞAK geçiş.
    #    Perde fotoğrafın bittiği yerin ÜSTÜNDE başlıyor ki fotoğrafın
    #    alt kenarı düz bir çizgi olarak görünmesin — başlık zaten oraya
    #    oturuyor ve okunması için karartma gerekiyor.
    perde_bas = int(700 * yukseklik / 1920)
    perde_son = int(1350 * yukseklik / 1920)
    mask = _perde_maskesi(genislik, yukseklik, perde_bas, perde_son)

    koyu_zemin = Image.new("RGB", (genislik, yukseklik), ZEMIN)
    canvas.paste(koyu_zemin, (0, 0), mask)

    # 4. Kristal netleştirme
    res = canvas.filter(ImageFilter.UnsharpMask(radius=1.2, percent=105, threshold=2))
    return res


def _bayragi_bas(
    gorsel: Image.Image, ulke_kodu: str, ulke_adi: str, kenar: int
) -> Image.Image:
    """
    Sağ üst köşeye ülke flaması basar: sağ kenara yapışık, sol ucu
    kırlangıç kuyruğu (içe doğru V çentik).

    NEDEN FLAMA, DÜZ BAYRAK DEĞİL:
        Önce bayrağı düz bir dikdörtgen olarak basıp altına ülke adı
        yazmıştık; sade kaldı ve açık fotoğraflarda yazı zeminden zor
        ayrıldı. Flamanın kendi koyu zemini olduğu için hem her arka
        planda aynı netlikte okunuyor hem de üst şeride karakter katıyor.

    Yükseklik SABİT, genişlik değişken:
        Bayrak oranları ülkeye göre farklı (İsviçre kare, Nepal üçgen).
        Genişliği sabitleseydik bazı bayraklar ezilirdi. Bunun yerine
        bayrak yüksekliğini sabitleyip genişliği orana göre hesaplıyoruz;
        flama da içeriğe göre uzuyor.

    Görüntüyü DEĞİŞTİRİP döner (alpha_composite yeni nesne üretiyor).
    """
    bayrak = fetch_flag.bayrak_al(ulke_kodu)
    if bayrak is None:
        return gorsel

    b_yuk = 54
    b_gen = max(1, int(bayrak.width * b_yuk / bayrak.height))
    bayrak = bayrak.resize((b_gen, b_yuk), Image.LANCZOS)
    kose_maske = Image.new("L", (b_gen, b_yuk), 0)
    ImageDraw.Draw(kose_maske).rounded_rectangle(
        [0, 0, b_gen - 1, b_yuk - 1], radius=5, fill=255
    )
    bayrak.putalpha(kose_maske)

    font = _font(19, EKSEN_KUCUK)
    metin = _buyuk_harf(ulke_adi or "")
    olcum = ImageDraw.Draw(gorsel)
    metin_genislik = olcum.textlength(metin, font=font) if metin else 0

    # Dikey istif: bayrak üstte, ülke adı altında. Flamanın genişliğini
    # ikisinden hangisi genişse o belirliyor — "Çin" ile "Birleşik Krallık"
    # aynı şablonda düzgün otursun diye.
    ust_pay, ara, alt_pay = 9, 6, 9
    yazi_yuk = 19 if metin else 0
    icerik_gen = int(max(b_gen, metin_genislik))
    yukseklik = ust_pay + b_yuk + (ara + yazi_yuk if metin else 0) + alt_pay

    uc_payi = 38                      # sol uçtaki V çentik için ayrılan yer
    ic_sol, ic_sag = 22, 28
    genislik = uc_payi + ic_sol + icerik_gen + ic_sag

    x1 = gorsel.width                 # sağ kenara yapışık
    x0 = x1 - genislik
    y0 = kenar - 10
    y1 = y0 + yukseklik
    orta_y = (y0 + y1) / 2

    # Kırlangıç kuyruğu: sol kenarın bir noktası içeri giriyor.
    # Kırılım flamanın geometrik ortasında DEĞİL — bayrakla ülke adı
    # arasındaki boşluğun hizasında. Böylece çentik içerikteki ayrımı
    # takip ediyor; ortada olunca bayrağın üstüne denk gelip keyfi
    # duruyordu. Ülke adı yoksa ortaya düşüyor.
    kirilim_y = (y0 + ust_pay + b_yuk + ara / 2) if metin else orta_y
    nokta = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0 + uc_payi, kirilim_y)]

    golge = Image.new("RGBA", gorsel.size, (0, 0, 0, 0))
    ImageDraw.Draw(golge).polygon(
        [(px, py + 4) for px, py in nokta], fill=(0, 0, 0, 120)
    )
    gorsel = Image.alpha_composite(
        gorsel.convert("RGBA"), golge.filter(ImageFilter.GaussianBlur(9))
    )

    katman = Image.new("RGBA", gorsel.size, (0, 0, 0, 0))
    ImageDraw.Draw(katman).polygon(nokta, fill=(*ZEMIN, 214))
    gorsel = Image.alpha_composite(gorsel, katman).convert("RGB")

    # Bayrak ve yazı, içerik alanında yatayda ortalanıyor
    icerik_x = x0 + uc_payi + ic_sol
    gorsel.paste(
        bayrak,
        (int(icerik_x + (icerik_gen - b_gen) / 2), int(y0 + ust_pay)),
        bayrak,
    )

    if metin:
        ImageDraw.Draw(gorsel).text(
            (
                icerik_x + (icerik_gen - metin_genislik) / 2,
                y0 + ust_pay + b_yuk + ara,
            ),
            metin, font=font, fill=PARLAK,
        )
    return gorsel


def _kaynak_satiri_ciz(
    ciz: ImageDraw.Draw, kenar: int, alt_bilgi_y: int, kaynak: str, arsiv_ibaresi: bool = False
) -> None:
    """Slaytın sol altına şık bir altın nokta ve kaynak adını yazar."""
    kucuk = _font(26, EKSEN_KUCUK)
    # Zarif altın nokta
    ciz.ellipse([kenar, alt_bilgi_y + 8, kenar + 8, alt_bilgi_y + 16], fill=VURGU)
    metin = _buyuk_harf(kaynak)
    if arsiv_ibaresi:
        metin += "   ·   ARŞİV GÖRSELİ"
    # EDM YAMASI: uzun kaynak adı kanal ikonlarının üstüne taşıyordu; ikonlar ve sayfa
    # numarası için ~330 px ayrılır, sığmayan kaynak adı "…" ile kısalır.
    azami = GENISLIK - 2 * kenar - 18 - 330
    while len(metin) > 4 and ciz.textlength(metin, font=kucuk) > azami:
        metin = metin[:-2].rstrip(" ·") 
        if ciz.textlength(metin + "…", font=kucuk) <= azami:
            metin += "…"
            break
    ciz.text((kenar + 18, alt_bilgi_y), metin, font=kucuk, fill=SOLUK)


def _son_dakika_rozeti(ciz, x: int, y: int) -> tuple[int, int]:
    """
    "SON DAKİKA" etiketini çizer, SAĞ ve ALT kenarını döner.

    ⚠️ NEDEN ORTAK FONKSİYON (5 Eyl 2026): etiket İKİ yerde ayrı ayrı
    çiziliyordu (`story_haber` ve `detay_slayti`) ve veri rozetini
    çizen `yaziyi_bas` ikisinden de habersizdi. Rozet sağa yaslı,
    etiket soldan başlıyor; ikisi genişleyince ÇAKIŞIYORLARDI.
    ÖLÇÜLDÜ (gerçek slayt, piksel taraması): etiket x 186→421, rozet
    x 372→890 — **49 piksel örtüşme**. Kullanıcı ekran görüntüsüyle
    bildirdi.

    Artık kutuyu tek fonksiyon üretiyor ve sınırlarını döndürüyor;
    yerleşimi yapan taraf nereye kadar dolu olduğunu biliyor.
    """
    f = _font(24, EKSEN_KUCUK)
    etiket = "SON DAKİKA"
    metin_g = ciz.textlength(etiket, font=f)
    sag = int(x + metin_g + 28)
    alt = int(y + 46)
    ciz.rounded_rectangle([x, y, sag, alt], radius=6, fill=VURGU_DERIN)
    ciz.text((x + 14, y + 10), etiket, font=f, fill=(255, 255, 255))
    return sag, alt


def yaziyi_bas(
    arkaplan: Image.Image, baslik: str, kaynak: str, ayarlar: dict,
    ozet: str | None = None,
    arsiv_ibaresi: bool = False,
    ulke_kodu: str = "",
    ulke_adi: str = "",
    kategori: str = "",
    son_slayt: bool = False,
    veri_karti: dict | None = None,
    son_dakika: bool = False,
    haber: dict | None = None,
) -> Image.Image:
    """
    Arka planın üstüne başlığı, varsa özeti ve alt bilgiyi yazar.

    SIRA ÖNEMLİ: önce yazının nereye oturacağını ölçüyoruz, perdeyi
    ondan sonra çiziyoruz. Eski hâlinde perde sabit bir orandan (%30)
    başlıyordu ve karesel arttığı için başlığın üst satırları perdenin
    daha şeffaf bölgesine denk geliyordu — açık bir fotoğrafta yazı
    okunmuyordu. Perdeyi yazıya göre konumlandırınca sorun kalmıyor.
    """
    g = ayarlar["gorsel"]
    genislik, yukseklik = g["genislik"], g["yukseklik"]
    kenar = g["kenar_bosluk"]

    # Dikeyde kenara en yakın öğeler (bayrak, kaynak satırı) kırpma
    # riskine karşı içeri alınıyor; yatayda böyle bir kırpma yok.
    dikey_kenar = max(kenar, g.get("dikey_guvenli_pay", kenar))

    gorsel = arkaplan.resize((genislik, yukseklik), Image.LANCZOS)
    ciz = ImageDraw.Draw(gorsel)
    alan_genislik = genislik - 2 * kenar

    # --- 1) Ölçüm: bloklar nereye oturacak? (alttan yukarı doğru) ---
    alt_bilgi_y = yukseklik - dikey_kenar - 34

    # Uzun başlıklarda (>2 satır veya >85 karakter) alt özet puntosunu adaptif
    # olarak 34'ten 30'a çekerek üstteki kanca ve logoya ferah nefes alanı bırak.
    ozet_punto = 30 if len(baslik or "") > 85 else 34

    ozet_font, ozet_satirlari, ozet_satir_y = None, [], 0
    if ozet:
        ozet_font, ozet_satirlari, ozet_satir_y = _ozeti_yerlestir(
            ozet, ciz, alan_genislik, punto=ozet_punto
        )
    ozet_yuksekligi = ozet_satir_y * len(ozet_satirlari)

    # Özet varsa başlığa daha az yer kalıyor — sığdırma buna göre yapılmalı,
    # yoksa ikisi üst üste biner.
    baslik_alani = int(yukseklik * 0.42) - ozet_yuksekligi
    font, satirlar, satir_yuksekligi = _basligi_yerlestir(
        baslik, ciz, alan_genislik, baslik_alani
    )

    # Eğer başlık 2 satırı aşıyorsa ve özet henüz küçültülmediyse adaptif esnet
    if len(satirlar) > 2 and ozet_punto > 30 and ozet:
        ozet_punto = 30
        ozet_font, ozet_satirlari, ozet_satir_y = _ozeti_yerlestir(
            ozet, ciz, alan_genislik, punto=ozet_punto
        )
        ozet_yuksekligi = ozet_satir_y * len(ozet_satirlari)

    ozet_ust = alt_bilgi_y - (66 if son_slayt else 44) - ozet_yuksekligi
    baslik_ust = ozet_ust - (26 if ozet else 0) - satir_yuksekligi * len(satirlar)

    # --- 2) Perde: Standart kurumsal kategori renk şeridi (özet ve alt bilgiyi tam opak korur) ---
    taban = _perde_taban_alfa(gorsel, (0, baslik_ust, genislik, yukseklik))
    renk = serit_rengi(kategori, g)
    serit_ust = ozet_ust - 30 if ozet else alt_bilgi_y - 30
    serit_basi = max(0, serit_ust - (150 + taban))

    perde = Image.new("RGBA", (genislik, yukseklik), (0, 0, 0, 0))
    perde_ciz = ImageDraw.Draw(perde)

    # Üst köşelere hafif netleştirici vignette (logo ve flama arkası)
    for y in range(0, min(320, yukseklik)):
        ust_alfa = int(115 * ((320 - y) / 320) ** 1.8)
        perde_ciz.line([(0, y), (genislik, y)], fill=(*ZEMIN, ust_alfa))

    gecis = max(1, serit_ust - serit_basi)
    for y in range(serit_basi, yukseklik):
        if y < serit_ust:
            alfa = int(255 * ((y - serit_basi) / gecis) ** 1.6)
        else:
            alfa = 255
        perde_ciz.line([(0, y), (genislik, y)], fill=renk + (alfa,))

    gorsel = Image.alpha_composite(gorsel.convert("RGBA"), perde).convert("RGB")

    # --- 3) Çok Katmanlı Difüzyon Gölgesi (Yazıyı arka plandan kristal gibi ayırır) ---
    golge = Image.new("RGBA", (genislik, yukseklik), (0, 0, 0, 0))
    golge_ciz = ImageDraw.Draw(golge)
    y = baslik_ust
    for satir in satirlar:
        golge_ciz.text((kenar, y + 4), satir.replace("**", ""), font=font, fill=(0, 0, 0, 230))
        y += satir_yuksekligi
    golge = golge.filter(ImageFilter.GaussianBlur(13))
    gorsel = Image.alpha_composite(gorsel.convert("RGBA"), golge).convert("RGB")
    ciz = ImageDraw.Draw(gorsel)

    y = baslik_ust
    for satir in satirlar:
        ciz.text((kenar, y), satir.replace("**", ""), font=font, fill=(255, 255, 255))
        y += satir_yuksekligi

    y = ozet_ust
    for satir in ozet_satirlari:
        _formatli_satir_ciz(ciz, kenar, y, satir, punto=ozet_punto, spot=True, varsayilan_renk=ACIK)
        y += ozet_satir_y

    # --- 3.5) Editoryal Hook (Kanca) Çizimi (Yalnızca 9:16 / 1080x1920 Kapak Slaytlarında) ---
    # ⚠️ `kanca_ciz` ayarı: projedeki her özellik kapatılabiliyor
    # (`web_gorsel_ara`, `threadse_de_at`…), kancanın anahtarı yoktu.
    if haber and yukseklik >= 1800 and g.get("kanca_ciz", True):
        try:
            from . import hook_motoru
            # EDM kancası kendi imzasını kullanıyor (renk/okunurluk: hook_motoru.py)
            gorsel = hook_motoru.hook_uygula(gorsel, haber, baslik_ust, ust_y=dikey_kenar, olcu="story")
            ciz = ImageDraw.Draw(gorsel)
        except Exception as e:
            log.warning("hook çiziminde hata: %s", e)

    # Son slayt Call-To-Action (CTA) etkileşim rozeti
    if son_slayt:
        cta_font = _font(24, EKSEN_KUCUK)
        cta_metin = "★ Günün özetini kaçırmamak için kaydet & takip et"
        ciz.text((kenar, alt_bilgi_y - 36), cta_metin, font=cta_font, fill=VURGU)

    # Kaynak adı — şeffaflık ve gazetecilik atfı
    _kaynak_satiri_ciz(ciz, kenar, alt_bilgi_y, kaynak, arsiv_ibaresi=arsiv_ibaresi)

    # Sosyal kanal ikonları sağ altta: "bu içerik şu kanallarda da var".
    gorsel = kanal_ikonlari_bas(gorsel, ayarlar, alt_bilgi_y + 13)
    ciz = ImageDraw.Draw(gorsel)

    # Sol üstte DailyBrief logosu (%50 büyütülmüş 144px)
    gorsel = _logoyu_bas(gorsel, kenar, dikey_kenar - 16, boy=144)
    ciz = ImageDraw.Draw(gorsel)

    if ulke_kodu:
        gorsel = _bayragi_bas(gorsel, ulke_kodu, ulke_adi, dikey_kenar)

    # ⚠️ SON DAKİKA ETİKETİ ARTIK BURADA ÇİZİLİYOR. Eskiden çağıranlar
    # (`story_haber`) `yaziyi_bas`tan SONRA kendileri çiziyordu ve veri
    # rozetini yerleştiren kod etiketin varlığından habersizdi — ikisi
    # çakışıyordu (ölçüldü: 49 px örtüşme). Tek fonksiyon sahiplenince
    # yerleşim hesaplanabilir hale geliyor.
    ciz = ImageDraw.Draw(gorsel)
    sd_sag = sd_alt = 0
    if son_dakika:
        sd_sag, sd_alt = _son_dakika_rozeti(ciz, kenar + LOGO_GENISLIK + 18, dikey_kenar + 30)

    # ⚠️ VERİ KARTI ROZETİ KALDIRILDI (7 Eyl 2026):
    # Kullanıcı: *"ülke bayrağının solundaki özet rakamsal bilgi kartımızın
    # içeriği çok uzadığında soldaki logomuza taşıyor, tasarımı hoşuma gitmiyo
    # kaldıralım"*. Üst barda Logo (144px) + SON DAKİKA rozeti + Ülke Bayrağı
    # varken araya 4. bir kutu olarak giren cam rozet hem logoya biniyordu hem
    # görseli boğuyordu. Bu bilgi zaten başlıkta, spotta veya ayrıntı
    # sayfasındaki büyük odak kartında (vurgu_sayi) yer alıyor.
    return gorsel


def _ikon_instagram(ciz, x, y, boy, renk):
    """Yuvarlak köşeli kare + mercek + vizör noktası."""
    r = boy // 4
    ciz.rounded_rectangle([x, y, x + boy, y + boy], radius=r,
                          outline=renk, width=max(2, boy // 11))
    m = boy // 4
    ciz.ellipse([x + m, y + m, x + boy - m, y + boy - m],
                outline=renk, width=max(2, boy // 12))
    n = max(2, boy // 10)
    ciz.ellipse([x + boy - m + 1, y + m // 2, x + boy - m + 1 + n,
                 y + m // 2 + n], fill=renk)


def _ikon_x(ciz, x, y, boy, renk):
    """X: iki çapraz kalın çizgi."""
    k = max(2, boy // 8)
    p = boy // 8
    ciz.line([(x + p, y + p), (x + boy - p, y + boy - p)], fill=renk, width=k)
    ciz.line([(x + boy - p, y + p), (x + p, y + boy - p)], fill=renk, width=k)


def _ikon_facebook(ciz, x, y, boy, renk):
    """Daire içinde 'f' — harf fontta var, çizmeye gerek yok."""
    ciz.ellipse([x, y, x + boy, y + boy], outline=renk,
                width=max(2, boy // 11))
    f = _font(int(boy * 0.72), [14.0, 700.0])
    g = ciz.textlength("f", font=f)
    ciz.text((x + (boy - g) / 2, y + boy * 0.12), "f", font=f, fill=renk)


def _ikon_threads(ciz, x, y, boy, renk):
    """
    Threads: üstte sağa, altta sola dolanan iki kavis ve dikey gövde.

    Resmî logo SVG ve Pillow SVG okumuyor; Unicode'da da karşılığı yok
    (ölçüldü, fontta "NO GLYPH" çıkıyor). Diğer ikonlarda olduğu gibi
    tanınabilir bir sadeleştirme çiziliyor. Ayırt edici yanı ilmeğin
    KAPALI OLMAMASI — kapatılırsa "@" işaretine benziyor.
    """
    k = max(2, boy // 10)
    # Alt ilmek: sağ alttan başlayıp sola dolanıyor, sağ tarafı açık.
    ciz.arc([x + boy * 0.16, y + boy * 0.36, x + boy * 0.84, y + boy * 0.96],
            start=300, end=200, fill=renk, width=k)
    # Üst kavis: sola açılıp sağa kıvrılan kanca.
    ciz.arc([x + boy * 0.16, y + boy * 0.04, x + boy * 0.84, y + boy * 0.64],
            start=170, end=40, fill=renk, width=k)
    # Dikey gövde: iki kavsi birleştiriyor, harfi ayakta tutan çizgi.
    ciz.line([(x + boy * 0.5, y + boy * 0.18), (x + boy * 0.5, y + boy * 0.66)],
             fill=renk, width=k)


def _ikon_youtube(ciz, x, y, boy, renk):
    """YouTube: Yuvarlak köşeli dikdörtgen + sağa bakan üçgen play ikonu."""
    r = boy // 4
    ciz.rounded_rectangle([x, y + boy * 0.12, x + boy, y + boy * 0.88], radius=r,
                          outline=renk, width=max(2, boy // 11))
    p1 = (x + boy * 0.40, y + boy * 0.32)
    p2 = (x + boy * 0.40, y + boy * 0.68)
    p3 = (x + boy * 0.70, y + boy * 0.50)
    ciz.polygon([p1, p2, p3], fill=renk)


def _ikon_tiktok(ciz, x, y, boy, renk):
    """TikTok: Müzik notası (nota başı, gövde ve üst bayrak)."""
    k = max(2, boy // 10)
    ciz.ellipse([x + boy * 0.18, y + boy * 0.55, x + boy * 0.58, y + boy * 0.90], fill=renk)
    ciz.line([(x + boy * 0.52, y + boy * 0.15), (x + boy * 0.52, y + boy * 0.72)], fill=renk, width=k)
    ciz.arc([x + boy * 0.52, y + boy * 0.12, x + boy * 0.90, y + boy * 0.50],
            start=270, end=90, fill=renk, width=k)


IKONLAR = {
    "instagram": _ikon_instagram,
    "threads": _ikon_threads,
    "facebook": _ikon_facebook,
    "x": _ikon_x,
    "youtube": _ikon_youtube,
    "tiktok": _ikon_tiktok,
}


_logo_onbellek: dict[tuple[str, int], Image.Image] = {}


def _logo_maskesi(ad: str, boy: int):
    """
    Logonun alfa kanalını maske olarak döner, yoksa None.

    NEDEN MASKE: logolar kendi renklerinde (Instagram gradyanı, Facebook
    mavisi) geliyor ama alt bilgideki her şey tek renk. Alfayı maske alıp
    istediğimiz rengi basınca logo alt bilgiye uyuyor.

    Önbellek: bir turda 10 slayt çiziliyor ve her slayt aynı 4 logoyu
    istiyor; diskten 40 kez okumanın anlamı yok.
    """
    anahtar = (ad, boy)
    if anahtar in _logo_onbellek:
        return _logo_onbellek[anahtar]

    yol = LOGO_KLASORU / f"{ad}.png"
    if not yol.exists():
        return None
    try:
        logo = Image.open(yol).convert("RGBA")
        # En-boy oranı korunuyor: X logosu kare değil (330x299) ve
        # zorla kareye oturtulursa eziliyor.
        oran = min(boy / logo.width, boy / logo.height)
        yeni = (max(1, int(logo.width * oran)), max(1, int(logo.height * oran)))
        maske = logo.resize(yeni, Image.LANCZOS).split()[-1]
    except Exception as e:
        log.warning("logo okunamadı (%s): %s", ad, e)
        return None

    _logo_onbellek[anahtar] = maske
    return maske


def kanal_ikonlari_bas(gorsel, ayarlar, y_merkez: int, renk=SOLUK):
    """
    Slaytın alt bilgisine sosyal kanal ikonlarını basar.

    Sağ kenardan başlayıp sola doğru diziliyor; sol tarafta kaynak adı
    duruyor ve ona çarpmaması gerekiyor.

    Önce indirilmiş gerçek logo aranıyor, bulunamazsa elle çizime
    düşülüyor — logo dosyaları silinse bile slayt üretimi durmuyor.
    """
    kanallar = (ayarlar.get("sosyal", {}) or {}).get("kanallar") or []
    if not kanallar:
        return gorsel

    ciz = ImageDraw.Draw(gorsel)
    g = ayarlar["gorsel"]
    boy = g.get("kanal_ikon_boyu", 26)
    ara = boy + 14
    sag_x = g["genislik"] - g["kenar_bosluk"]
    toplam_genislik = len(kanallar) * boy + (len(kanallar) - 1) * 14
    sol_x = sag_x - toplam_genislik

    # 1. Sosyal Medya İkonlarının hemen üstüne tam ikon genişliğinde alan adı
    web_txt = ALAN_ADI
    f_web = _font(16, [14.0, 700.0])
    raw_w = ciz.textlength(web_txt, font=f_web)
    extra_space = max(0.0, (toplam_genislik - raw_w) / max(1, (len(web_txt) - 1)))
    cur_x = sol_x
    web_y = y_merkez - boy - 10
    for ch in web_txt:
        ciz.text((cur_x, web_y), ch, font=f_web, fill=SOLUK)
        cur_x += ciz.textlength(ch, font=f_web) + extra_space

    # 2. İkonları bas
    x = sag_x - boy
    for ad in reversed(kanallar):
        maske = _logo_maskesi(ad, boy)
        if maske is not None:
            # Dikeyde ortala: X logosu kare olmadığı için gerekiyor.
            ust = y_merkez - maske.height // 2
            sol = x + (boy - maske.width) // 2
            gorsel.paste(renk, (sol, ust), maske)
        elif ad in IKONLAR:
            IKONLAR[ad](ciz, x, y_merkez - boy // 2, boy, renk)
        else:
            continue
        x -= ara
    return gorsel


# 4:5 Güvenli Alan Payı: 9:16 (1080x1920) görselin içindeki tüm içerik
# (logo, başlık, özet, kaynak) 4:5 (1080x1350) merkez kutusunun (y=285..1635)
# içine güvenle sığar.
STORY_GUVENLI_PAY = 330


# Detay sayfasında sabit punto: 40 puntoda sayfa başına ~75 kelime
# sığıyor (ölçüldü). Puntoyu metne göre küçültmek yerine SAYFA EKLİYORUZ
# — 28 puntoya inen bir slayt telefonda okunmuyor ve carousel'de zaten
# 10 slayt hakkımız var.
DETAY_PUNTO = 37


# Giriş ("spot") paragrafı daha iri: slaytta ilk göze çarpan şey o olmalı.
# Gazete düzeninden alınma — düz tek blok metin telefonda duvar gibi
# görünüyor ve kaydırılıp geçiliyor.
DETAY_SPOT_PUNTO = 46


# Paragraflar arası nefes payı (piksel)
PARAGRAF_ARASI = 24


# Vurgu bloklarının puntoları
VURGU_SAYI_PUNTO = 92      # iri rakam — sayfanın çapası


VURGU_ETIKET_PUNTO = 30    # rakamın altındaki açıklama


ALINTI_PUNTO = 40


# Son dakika postu en fazla kaç detay sayfası taşısın.
# 1 haber + 4 detay = 5 slayt. Daha uzunu kaydırılmıyor.
AZAMI_DETAY_SAYFA = 4


TURKCE_KISALTMALAR = {
    "dr", "doc", "doç", "prof", "av", "yrd", "uzm", "muh", "müh", "mim",
    "sn", "gen", "alb", "bnb", "yzb", "tgm", "tğm", "utgm", "ütğm", "astsb",
    "emk", "bsk", "bşk", "mud", "müd", "vb", "vs", "sf", "s", "md", "mad",
    "no", "nr", "bkz", "or", "ör", "orn", "örn", "fiz", "kim", "biy",
    "ist", "ank", "izm", "cad", "sok", "apt", "al", "co", "inc", "ltd",
    "sti", "şti", "as", "aş", "tc", "t.c", "v"
}


def cumlelere_bol(metin: str) -> list[str]:
    """
    Türkçe unvan, kısaltma (Doç., Dr., vb.), sıra sayısı (14.) ve
    özel karakterleri bozmadan metni gerçek cümle sınırlarından ayırır.
    """
    if not metin or not metin.strip():
        return []

    cumleler = []
    baslangic = 0
    i = 0
    uzunluk = len(metin)

    while i < uzunluk:
        ch = metin[i]
        if ch in ".!?…":
            # Ardışık noktalamaları geç (...)
            j = i
            while j < uzunluk and metin[j] in ".!?…":
                j += 1

            # Noktalamadan sonraki boşluğu kontrol et
            k = j
            while k < uzunluk and metin[k].isspace():
                k += 1

            if k == uzunluk:
                # Metnin sonu
                cumle = metin[baslangic:].strip()
                if cumle:
                    cumleler.append(cumle)
                baslangic = uzunluk
                break

            if k > j:  # Noktalamadan sonra en az bir boşluk var
                sonraki_karakter = metin[k]

                # Tırnak veya parantez varsa bir sonraki karaktere bak
                if sonraki_karakter in "\"'“”‘’()[]" and k + 1 < uzunluk:
                    sonraki_karakter = metin[k + 1]

                # Cümle sonu olma koşulu: Sonraki karakter büyük harf olmalı
                buyuk_harf_mi = (sonraki_karakter.isupper()
                                 or sonraki_karakter in "ÇĞİÖŞÜ")

                # Noktadan önceki son kelimeyi bul
                onceki_metin = metin[baslangic:i].strip()
                kelimeler = re.findall(r"[a-zA-Z0-9çğıöşüÇĞİÖŞÜ]+", onceki_metin)
                son_kelime = kelimeler[-1] if kelimeler else ""
                son_kelime_kucuk = son_kelime.lower()

                # Kontroller:
                # a) Kısaltma mı? (Doç., Dr., vb.)
                kisaltma_mi = son_kelime_kucuk in TURKCE_KISALTMALAR
                # b) Sıra sayısı mı? (14., 2.)
                sira_sayisi_mi = son_kelime.isdigit()
                # c) Tek harfli baş harf mi? (M. Kemal)
                tek_harf_mi = len(son_kelime) == 1 and son_kelime.isupper()

                if buyuk_harf_mi and not kisaltma_mi and not sira_sayisi_mi and not tek_harf_mi:
                    # Gerçek cümle sonu!
                    cumle = metin[baslangic:j].strip()
                    if cumle:
                        cumleler.append(cumle)
                    baslangic = k
                    i = k
                    continue
            i = j
        else:
            i += 1

    kalan = metin[baslangic:].strip()
    if kalan:
        cumleler.append(kalan)

    return cumleler


def _metni_paragraflara_ayir(metin: str, azami_cumle: int = 3) -> list[str]:
    """
    Uzun veya tek parça detay metnini okunaklı, ferah paragraflara böler.
    Satır sonlarını korur; 3'ten fazla cümle içeren uzun blokları 2-3 cümlelik
    doğal paragraflara ayırarak okumayı kolaylaştırır.
    Türkçe kısaltma ve unvanları (Doç., Dr., vb.) korur.
    """
    if not metin or not metin.strip():
        return []

    ham_paragraflar = [p.strip() for p in re.split(r"\n+", metin.strip()) if p.strip()]
    sonuc = []

    for p in ham_paragraflar:
        cumleler = cumlelere_bol(p)
        if len(cumleler) <= azami_cumle:
            sonuc.append(p)
        elif len(cumleler) == 4:
            # 4 cümlede 3+1 yerine 2+2 daha dengeli ve ferah bir görünüm sunar
            sonuc.append(" ".join(cumleler[:2]).strip())
            sonuc.append(" ".join(cumleler[2:]).strip())
        else:
            for i in range(0, len(cumleler), azami_cumle):
                parca = " ".join(cumleler[i : i + azami_cumle]).strip()
                if parca:
                    sonuc.append(parca)

    return sonuc


def _sayfalari_dengeli_bol(
    bloklar: list[dict],
    kullanilabilir: int,
    azami_sayfa: int = AZAMI_DETAY_SAYFA,
    aralik: int = PARAGRAF_ARASI,
) -> list[list[dict]]:
    """
    Detay slaytı bloklarını (paragraflar, vurgu sayısı, alıntı, neden önemli vb.)
    sayfalar arasında estetik, nefes alan ve dengeli bir biçimde paylaştırır.

    Açgözlü (greedy) yaklaşımın bir önceki sayfayı alt bilgi çizgisine kadar doldurup
    son sayfayı tek satırlık bir alıntıyla %85 boş bırakmasını (yetim blok) engeller.
    """
    if not bloklar:
        return [[]]
    n = len(bloklar)
    if n == 1:
        return [bloklar]

    # 1. Açgözlü (greedy) simülasyonla asgari sayfa sayısını bul
    sayfalar_greedy: list[list[dict]] = []
    gecerli: list[dict] = []
    dolu = 0
    for b in bloklar:
        gerekli = b["yukseklik"] + (aralik if gecerli else 0)
        tek_vurgu = (len(gecerli) == 1 and gecerli[0].get("tip") == "sayi")
        if gecerli and dolu + gerekli > kullanilabilir and not tek_vurgu:
            sayfalar_greedy.append(gecerli)
            gecerli, dolu = [b], b["yukseklik"]
        else:
            gecerli.append(b)
            dolu += gerekli
    if gecerli:
        sayfalar_greedy.append(gecerli)

    k_min = len(sayfalar_greedy)
    if k_min <= 1:
        return [bloklar]
    k_min = min(k_min, azami_sayfa)

    ozel_kapanis_tipleri = {"alinti", "neden_onemli", "sirada_ne_var", "sana_etkisi"}
    en_iyi_bolum = None
    en_iyi_skor = float("inf")

    # Sayfa sayısı için k_min ve gerekirse k_min + 1'i dene
    for k in range(k_min, min(k_min + 2, azami_sayfa + 1)):
        for cuts in itertools.combinations(range(1, n), k - 1):
            idx = [0] + list(cuts) + [n]
            parts = [bloklar[idx[i]:idx[i + 1]] for i in range(k)]

            gecersiz = False
            heights = []
            orphan_ceza = 0

            for p in parts:
                h = sum(b.get("yukseklik", 0) for b in p) + aralik * (len(p) - 1)
                # Fiziksel sınır aşımı: bu bölümleme kesinlikle elenir
                if h > kullanilabilir:
                    gecersiz = True
                    break
                # Vurgu sayısı tek başına kalamaz (yanında mutlaka ilk metin olmalı)
                if p[0].get("tip") == "sayi" and len(p) == 1:
                    gecersiz = True
                    break
                # Yetim özel blok cezası (toplam blok >= 3 iken tek başına alıntı/neden önemli bırakma)
                if n >= 3 and len(p) == 1 and p[0].get("tip") in ozel_kapanis_tipleri:
                    orphan_ceza += 150000

                heights.append(h)

            if gecersiz:
                continue

            # Skorlama:
            # 1. Varyans: sayfaların birbirine yakın yükseklikte olmasını hedefler
            h_avg = sum(heights) / k
            var_cost = sum((h - h_avg) ** 2 for h in heights)

            # 2. Boy farkı (max - min)
            diff_cost = (max(heights) - min(heights)) * 50

            # 3. Boş sayfa oranı cezası (en küçük sayfa en büyük sayfanın %50'sinden az yer kaplarsa)
            min_oran = min(heights) / max(heights) if max(heights) > 0 else 1.0
            oran_ceza = 40000 * (0.50 - min_oran) if min_oran < 0.50 else 0

            # 4. Tek blok cezası (blok sayısı >= 4 iken sayfayı tek blokla kapatmayı cezalandır)
            tek_blok_ceza = sum(15000 for p in parts if len(p) == 1 and n >= 4)

            # 5. Gereksiz sayfa açma cezası (k > k_min ise)
            sayfa_ceza = (k - k_min) * 100000

            toplam_skor = var_cost + diff_cost + oran_ceza + tek_blok_ceza + sayfa_ceza + orphan_ceza
            if toplam_skor < en_iyi_skor:
                en_iyi_skor = toplam_skor
                en_iyi_bolum = parts

        # Eğer k_min sayfa sayısıyla yetim bloksuz geçerli bir bölüm bulunduysa dur
        if en_iyi_bolum is not None and en_iyi_skor < 100000:
            break

    return en_iyi_bolum if en_iyi_bolum is not None else sayfalar_greedy[:azami_sayfa]


def detay_sayfalara_bol(
    detay: str, ayarlar: dict,
    vurgu: tuple[str, str] | None = None,
    alinti: tuple[str, str] | None = None,
    neden_onemli: str | None = None,
    sirada_ne_var: str | None = None,
    trend_karti: Image.Image | None = None,
    sana_etkisi: str | None = None,
) -> list[list[dict]]:
    """
    Detay metnini paragraflara ayırıp sayfalara dağıtır.
    Smart Brevity formatını (Ne oldu / Sana Etkisi / Neden Önemli / Sırada Ne Var) ve Finans Trend Kartlarını destekler.
    """
    g = ayarlar["gorsel"]
    genislik = g.get("genislik", STORY_GENISLIK)
    yukseklik = g.get("yukseklik", STORY_YUKSEKLIK)
    kenar = g.get("kenar_bosluk", 80)
    dikey_kenar = max(kenar, g.get("dikey_guvenli_pay", STORY_GUVENLI_PAY))

    olcu = ImageDraw.Draw(Image.new("RGB", (genislik, yukseklik)))
    alan = genislik - 2 * kenar - 32  # Sol çentik ve girinti payı (kenar + 24)

    ust_blok = dikey_kenar + 120
    alt_bilgi_y = yukseklik - dikey_kenar - 34
    kullanilabilir = alt_bilgi_y - 40 - ust_blok

    paragraflar = _metni_paragraflara_ayir(detay or "")
    if not paragraflar and not vurgu and not alinti and not neden_onemli and not trend_karti and not sana_etkisi:
        return [[]]

    bloklar = []

    # Vurgu rakamı en başta: sayfanın çapası, ilk göze çarpan şey.
    if vurgu and vurgu[0]:
        s_punto = VURGU_SAYI_PUNTO
        for aday in (VURGU_SAYI_PUNTO, 76, 64, 54, 46):
            if olcu.textlength(vurgu[0], font=_font(aday, EKSEN_BASLIK)) <= alan:
                s_punto = aday
                break
        else:
            s_punto = 46
        bloklar.append({
            # ⚠️ Vurgu etiketi KALIN basılmıyor, düz çiziliyor — yıldız
            # gelirse ekranda görünür. Model bu alanda `**` kullanmamalı
            # ama kullanırsa burada eleniyor.
            "tip": "sayi", "sayi": vurgu[0],
            "etiket": (vurgu[1] or "").replace("**", ""),
            "punto": s_punto, "satirlar": [],
            "yukseklik": int(s_punto * 1.15) + int(VURGU_ETIKET_PUNTO * 1.7),
        })

    # Her paragrafı satırlara böl. İlki spot: daha iri punto.
    for i, metin in enumerate(paragraflar):
        spot = (i == 0)
        # Giriş (spot) paragrafı çok uzunsa (>140 karakter) veya dikey alan sıkışıkken
        # nefes alanını korumak için puntoyu 46'dan 40'a esnet
        if spot:
            punto = 40 if len(metin) > 140 else DETAY_SPOT_PUNTO
        else:
            punto = DETAY_PUNTO
        font = _font(punto, EKSEN_OZET)
        satirlar = _satirlara_bol(metin, font, alan, olcu)
        yukseklik_px = int(punto * 1.5) * len(satirlar)

        # Eğer tek paragraf tek sayfaya sığmıyorsa cümle sınırlarından böl
        if yukseklik_px > kullanilabilir:
            c_parcalar = cumlelere_bol(metin)
            if len(c_parcalar) >= 2:
                yari_c = max(1, len(c_parcalar) // 2)
                metin_1 = " ".join(c_parcalar[:yari_c])
                metin_2 = " ".join(c_parcalar[yari_c:])
                sat_1 = _satirlara_bol(metin_1, font, alan, olcu)
                sat_2 = _satirlara_bol(metin_2, _font(DETAY_PUNTO, EKSEN_OZET), alan, olcu)
                bloklar.append({"tip": "metin", "satirlar": sat_1, "spot": spot,
                                "punto": punto,
                                "yukseklik": int(punto * 1.5) * len(sat_1)})
                bloklar.append({"tip": "metin", "satirlar": sat_2, "spot": False,
                                "punto": DETAY_PUNTO,
                                "yukseklik": int(DETAY_PUNTO * 1.5) * len(sat_2)})
            else:
                bloklar.append({"tip": "metin", "satirlar": satirlar, "spot": spot,
                                "punto": punto,
                                "yukseklik": yukseklik_px})
        else:
            bloklar.append({"tip": "metin", "satirlar": satirlar, "spot": spot,
                            "punto": punto,
                            "yukseklik": yukseklik_px})

    # Sana / Piyasaya Etkisi (Zümrüt Yeşil Vurgulu Doğal Editoryal Blok)
    if sana_etkisi and sana_etkisi.strip():
        se_punto = DETAY_PUNTO - 3
        se_font = _font(se_punto, EKSEN_OZET)
        se_satirlar = _satirlara_bol(sana_etkisi.strip(), se_font, alan, olcu)
        bloklar.append({
            "tip": "sana_etkisi",
            "metin": sana_etkisi.strip(),
            "satirlar": se_satirlar,
            "spot": False,
            "yukseklik": int(se_punto * 1.5) * len(se_satirlar),
        })

    # Smart Brevity: Neden Önemli (Doğal editoryal blok)
    if neden_onemli and neden_onemli.strip():
        n_punto = DETAY_PUNTO - 3
        n_font = _font(n_punto, EKSEN_OZET)
        n_satirlar = _satirlara_bol(neden_onemli.strip(), n_font, alan, olcu)
        bloklar.append({
            "tip": "neden_onemli",
            "metin": neden_onemli.strip(),
            "satirlar": n_satirlar,
            "spot": False,
            "yukseklik": int(n_punto * 1.5) * len(n_satirlar),
        })

    # Smart Brevity: Sırada Ne Var (Doğal editoryal blok)
    if sirada_ne_var and sirada_ne_var.strip():
        s_punto = DETAY_PUNTO - 3
        s_font = _font(s_punto, EKSEN_OZET)
        s_satirlar = _satirlara_bol(sirada_ne_var.strip(), s_font, alan, olcu)
        bloklar.append({
            "tip": "sirada_ne_var",
            "metin": sirada_ne_var.strip(),
            "satirlar": s_satirlar,
            "spot": False,
            "yukseklik": int(s_punto * 1.5) * len(s_satirlar),
        })

    # Finans & Borsa: Otomatik Mini Trend Kartı (Sparkline)
    if trend_karti:
        bloklar.append({
            "tip": "trend_karti",
            "gorsel": trend_karti,
            "satirlar": [],
            "spot": False,
            "yukseklik": trend_karti.height + 24,
        })

    # Alıntı en sonda: kapanış
    if alinti and alinti[0]:
        a_font = _font(ALINTI_PUNTO, EKSEN_OZET)
        a_satirlar = _satirlara_bol(f"“{alinti[0]}”", a_font, alan - 8, olcu)
        bloklar.append({
            "tip": "alinti", "satirlar": a_satirlar,
            "sahibi": alinti[1] or "", "spot": False,
            "yukseklik": int(ALINTI_PUNTO * 1.45) * len(a_satirlar) + 54,
        })

    # VURGU + İLK PARAGRAF BİRLİKTE SIĞMALI.
    if len(bloklar) >= 2 and bloklar[0].get("tip") == "sayi":
        ikisi = bloklar[0]["yukseklik"] + PARAGRAF_ARASI + bloklar[1]["yukseklik"]
        for kucuk in (DETAY_PUNTO, 34, 31):
            if ikisi <= kullanilabilir:
                break
            f = _font(kucuk, EKSEN_OZET)
            yeni = _satirlara_bol(paragraflar[0], f, alan, olcu)
            bloklar[1] = {"tip": "metin", "satirlar": yeni, "spot": False,
                          "punto": kucuk,
                          "yukseklik": int(kucuk * 1.5) * len(yeni)}
            ikisi = bloklar[0]["yukseklik"] + PARAGRAF_ARASI + bloklar[1]["yukseklik"]

    # Sayfalara estetik ve dengeli dağıt (yetim blok korumalı)
    return _sayfalari_dengeli_bol(bloklar, kullanilabilir, AZAMI_DETAY_SAYFA, PARAGRAF_ARASI)


def detay_slayti(
    baslik: str, detay: str, kaynak: str, ayarlar: dict,
    kategori: str = "turkiye",
    son_dakika: bool = True,
    ulke_kodu: str | None = None,
    ulke_adi: str | None = None,
    satirlar: list[dict] | None = None,
    sayfa: int = 1,
    toplam_sayfa: int = 1,
    arkaplan: Image.Image | None = None,
    arsiv_ibaresi: bool = False,
) -> Image.Image:
    """
    Son dakika postunun 2. slaytı: haberin ayrıntısı.
    İkinci bir fotoğraf varsa hafif koyu perdeyle derinlikli zemin olarak kullanılır.
    """
    # ⚠️ Başlık DÜZ çiziliyor, kalın vurgusu yok — `**` gelirse ekranda
    # görünür. `ig_baslik` üretimde `markdown_temizle`den geçiyor ama
    # bu fonksiyon başka yollardan da çağrılabiliyor (özel haber,
    # elle kurulan tur); kapıyı burada da tutuyoruz.
    baslik = (baslik or "").replace("**", "")
    g = ayarlar["gorsel"]
    genislik, yukseklik = g["genislik"], g["yukseklik"]
    kenar = g["kenar_bosluk"]
    dikey_kenar = max(kenar, g.get("dikey_guvenli_pay", kenar))

    if arkaplan is not None:
        oran = max(genislik / arkaplan.width, yukseklik / arkaplan.height)
        yeni_w, yeni_h = int(arkaplan.width * oran), int(arkaplan.height * oran)
        foto_buyuk = arkaplan.resize((yeni_w, yeni_h), Image.LANCZOS)
        x_kirp = (yeni_w - genislik) // 2
        y_kirp = (yeni_h - yukseklik) // 2
        gorsel = foto_buyuk.crop((x_kirp, y_kirp, x_kirp + genislik, y_kirp + yukseklik))
        perde = Image.new("RGBA", (genislik, yukseklik), (*ZEMIN, 232))
        gorsel = Image.alpha_composite(gorsel.convert("RGBA"), perde).convert("RGB")
    else:
        gorsel = arkaplan_uret_yedek(kategori, genislik, yukseklik, g)
    ciz = ImageDraw.Draw(gorsel)
    alan_genislik = genislik - 2 * kenar

    # Bayrak sağ üstte duruyor; başlık oraya kadar uzarsa altında kalıyor.
    baslik_genislik = alan_genislik - (170 if ulke_kodu else 0)

    # Sol üst logo (%50 büyütülmüş 144px)
    gorsel = _logoyu_bas(gorsel, kenar, dikey_kenar - 16, boy=144)
    ciz = ImageDraw.Draw(gorsel)

    # --- Üst: SON DAKİKA etiketi (yalnızca olağanüstü olaylarda) ---
    if son_dakika:
        etiket_font = _font(24, EKSEN_KUCUK)
        etiket = "SON DAKİKA"
        metin_g = ciz.textlength(etiket, font=etiket_font)
        ciz.rounded_rectangle(
            [kenar + LOGO_GENISLIK + 18, dikey_kenar + 30, kenar + LOGO_GENISLIK + 18 + metin_g + 28, dikey_kenar + 76],
            radius=6,
            fill=VURGU_DERIN,
        )
        ciz.text((kenar + LOGO_GENISLIK + 18 + 14, dikey_kenar + 39), etiket, font=etiket_font,
                 fill=(255, 255, 255))

    # Detay sayfalarında tekrarlayan devasa başlık kaldırıldı.
    # Metin ferah ve geniş bir dikey alanda akar.
    y = dikey_kenar + 120

    # --- Detay metni: asıl içerik ---
    alt_bilgi_y = yukseklik - dikey_kenar - 34
    kullanilabilir = alt_bilgi_y - 40 - y

    # `satirlar` paragraf blokları listesi: [{"satirlar", "spot"}, ...]
    bloklar = satirlar
    if bloklar is None:
        d_font = _font(DETAY_PUNTO, EKSEN_OZET)
        bloklar = [{"satirlar": _satirlara_bol(detay, d_font, alan_genislik - 32, ciz),
                    "spot": False}]

    toplam = (sum(b.get("yukseklik", 0) for b in bloklar)
              + PARAGRAF_ARASI * max(0, len(bloklar) - 1))

    # Blokları kalan alanda dikeyde ortalıyoruz.
    y += max(0, (kullanilabilir - toplam) // 2)

    for i, b in enumerate(bloklar):
        tip = b.get("tip", "metin")

        if tip == "sayi":
            # İri rakam + altında ne olduğu. Amber renk: sayfadaki tek
            punto = b.get("punto", VURGU_SAYI_PUNTO)
            f = _font(punto, EKSEN_BASLIK)
            ciz.text((kenar, y), b["sayi"], font=f, fill=VURGU)
            y += int(punto * 1.15)
            if b["etiket"]:
                ciz.text((kenar + 4, y), _buyuk_harf(b["etiket"]),
                         font=_font(VURGU_ETIKET_PUNTO, EKSEN_KUCUK),
                         fill=SOLUK)
            y += int(VURGU_ETIKET_PUNTO * 1.7)

        elif tip == "alinti":
            # Sol kenarda dikey çizgi: alıntı olduğu bir bakışta belli.
            f = _font(ALINTI_PUNTO, EKSEN_OZET)
            satir_y = int(ALINTI_PUNTO * 1.45)
            blok_yuk = satir_y * len(b["satirlar"])
            ciz.rectangle([kenar, y, kenar + 5, y + blok_yuk],
                          fill=VURGU)
            for satir in b["satirlar"]:
                ciz.text((kenar + 26, y), satir, font=f, fill=PARLAK)
                y += satir_y
            if b["sahibi"]:
                ciz.text((kenar + 26, y + 8), f"— {b['sahibi']}",
                         font=_font(28, EKSEN_KUCUK), fill=SOLUK)
            y += 54

        elif tip in ("neden_onemli", "sirada_ne_var", "sana_etkisi"):
            if tip == "sana_etkisi":
                kenar_renk = PARLAK  # Parlak Zümrüt Yeşili (Emerald)
                varsayilan_renk = ACIK
            elif tip == "neden_onemli":
                kenar_renk = VURGU  # Sıcak Kehribar (Amber)
                varsayilan_renk = ACIK
            else:
                kenar_renk = IKINCIL   # Siber Turkuaz (Cyan)
                varsayilan_renk = GOVDE

            punto_kart = DETAY_PUNTO - 3
            satir_h = int(punto_kart * 1.5)
            blok_yuk = satir_h * len(b["satirlar"])
            # Zarif sol vurgu çizgisi (kutu yok, doğal ferah editoryal akış)
            ciz.rectangle([kenar, y, kenar + 4, y + blok_yuk], fill=kenar_renk)
            y_yazi = y
            for s in b["satirlar"]:
                _formatli_satir_ciz(ciz, kenar + 22, y_yazi, s, punto_kart, spot=False, varsayilan_renk=varsayilan_renk)
                y_yazi += satir_h
            y += blok_yuk

        elif tip == "trend_karti":
            img_tk = b["gorsel"]
            gorsel.paste(img_tk, (kenar, y), img_tk)
            y += b["yukseklik"]

        else:
            # Normal Detay Paragrafı (Spot veya Gelişme)
            punto = b.get("punto") or (DETAY_SPOT_PUNTO if b["spot"] else DETAY_PUNTO)
            satir_y = int(punto * 1.5)
            blok_yuk = satir_y * len(b["satirlar"])

            # Paragraf Başı Çentiği (Sleek Rounded Vertical Accent Notch):
            # 1. Paragraf (Spot): Canlı Amber (#E2AA58)
            # 2+ Paragraflar: Siber Turkuaz (#06B6D4)
            centik_renk = VURGU if b["spot"] else IKINCIL
            ciz.rounded_rectangle(
                [kenar, y + 4, kenar + 4, y + blok_yuk - 4],
                radius=2,
                fill=centik_renk
            )

            y_yazi = y
            for satir in b["satirlar"]:
                _formatli_satir_ciz(ciz, kenar + 24, y_yazi, satir, punto, spot=b["spot"])
                y_yazi += satir_y
            y += blok_yuk

        if i < len(bloklar) - 1:
            y += PARAGRAF_ARASI

    # --- Alt bilgi ---
    kucuk = _font(26, EKSEN_KUCUK)
    _kaynak_satiri_ciz(ciz, kenar, alt_bilgi_y, kaynak, arsiv_ibaresi=arsiv_ibaresi)

    # Sayfa göstergesi: "2/3". Birden fazla detay sayfası varken
    # takipçinin nerede olduğunu bilmesi gerekiyor.
    if toplam_sayfa > 1:
        gosterge = f"{sayfa}/{toplam_sayfa}"
        gen = ciz.textlength(gosterge, font=kucuk)
        ciz.text((genislik - kenar - gen, alt_bilgi_y), gosterge,
                 font=kucuk, fill=SOLUK)
        # İkonlar sayfa göstergesinin soluna kayıyor, üstüne binmesin.
        gecici = {**ayarlar, "gorsel": {**g,
                  "kenar_bosluk": kenar + int(gen) + 24}}
        gorsel = kanal_ikonlari_bas(gorsel, gecici, alt_bilgi_y + 13)
    else:
        gorsel = kanal_ikonlari_bas(gorsel, ayarlar, alt_bilgi_y + 13)

    if ulke_kodu:
        gorsel = _bayragi_bas(gorsel, ulke_kodu, ulke_adi, dikey_kenar)

    return gorsel



# ======================================================================
# EDM ARAYÜZÜ — girdiyi hazırlar, ana kareyi çizer, besleme için kırpar
# ======================================================================

def _foto_ac(kaynak: Any) -> Optional[Image.Image]:
    if not kaynak:
        return None
    if isinstance(kaynak, Image.Image):
        return kaynak
    from . import make_image
    try:
        return make_image._foto_indir_veya_ac(str(kaynak))
    except Exception as e:
        log.warning("Haber fotoğrafı açılamadı (%s): %s", str(kaynak)[:60], e)
        return None


def _kayittaki_alanlari_ac(haber: Dict[str, Any]) -> None:
    """DB kaydında içerik `detay_metni` sütununda JSON olarak durur; eksik alanları ona tamamlar."""
    dm = haber.get("detay_metni")
    if isinstance(dm, str) and dm.strip().startswith("{"):
        try:
            import json
            ayrisik = json.loads(dm)
        except Exception:
            return
        if isinstance(ayrisik, dict):
            for k, v in ayrisik.items():
                if haber.get(k) in (None, ""):
                    haber[k] = v


def fotografi_sec(haber: Dict[str, Any], foto_yolu: Any, cikti_dizini: Path) -> Optional[Image.Image]:
    """Kapak fotoğrafı zinciri: onaylanan fotoğraf → haberin kendi sayfası → kardeş haber → stok.

    Seçilen fotoğraf diske sabitlenir ve kayda yazılır: akış kareleri, 9:16 video ve
    yeniden çizimler hep AYNI fotoğrafı kullanır (Instabot standardı: onaylanan görsel
    yayınlanan görseldir; stok aramasını yeniden çalıştırmak başka bir fotoğraf getirir).
    """
    from . import make_image
    foto = _foto_ac(foto_yolu or haber.get("foto_yolu") or haber.get("gorsel_yolu") or haber.get("gorsel_url"))

    if foto is None:
        link = haber.get("orijinal_url") or haber.get("link") or haber.get("url")
        if link and str(link).startswith("http"):
            try:
                from . import fetch_article
                og = fetch_article.og_gorseli_cek(link)
                if not og:
                    tum = fetch_article.tum_gorselleri_cek(link)
                    og = tum[0] if tum else None
                foto = _foto_ac(og)
                if foto is not None:
                    haber["gorsel_url"] = og
            except Exception as e:
                log.debug("Haber sayfasından görsel çekilemedi: %s", e)

    if foto is None:
        try:
            alt, atif = make_image._haber_gorseli_alternatifi(haber, sira=int(haber.get("foto_sira") or 0))
            if alt is not None:
                foto = alt
                if atif:
                    haber["foto_atif"] = atif
        except Exception as e:
            log.debug("Kardeş haber görseli bulunamadı: %s", e)

    if foto is None:
        try:
            from . import fetch_stock
            baslik = (haber.get("orijinal_baslik") or haber.get("manset") or "").lower()
            if any(w in baslik for w in ("arsa", "arazi", "tarla", "parsel", "hazine", "milli emlak", "çatalca", "silivri")):
                sorgu = "real estate land field plot aerial"
            elif any(w in baslik for w in ("kira", "kiracı", "tahliye", "ev sahibi", "daire", "konut")):
                sorgu = "modern apartment house keys interior real estate"
            elif any(w in baslik for w in ("toki", "sosyal konut", "inşaat", "şantiye", "proje", "kentsel dönüşüm")):
                sorgu = "modern residential buildings construction architecture"
            else:
                sorgu = "modern luxury architecture real estate villa"
            stok = fetch_stock.stok_fotografi_ara(sorgu, kategori_kodu=haber.get("kategori_kodu") or "SEKTOREL_HABER_VE_ANALIZ")
            if stok and Path(stok).exists():
                foto = ImageOps.exif_transpose(Image.open(stok)).convert("RGB")
        except Exception as e:
            log.warning("Stok fotoğraf aranamadı: %s", e)

    if foto is not None:
        try:
            cikti_dizini.mkdir(parents=True, exist_ok=True)
            sabit = cikti_dizini / f"haber_foto_{haber.get('id') or 'x'}.jpg"
            if not sabit.exists():
                foto.convert("RGB").save(sabit, "JPEG", quality=95)
            haber["foto_yolu"] = haber["gorsel_yolu"] = str(sabit)
        except Exception as e:
            log.debug("Haber fotoğrafı diske sabitlenemedi: %s", e)
    return foto


def _bos_degil(*degerler: Any, paragraf: bool = False) -> str:
    """İlk dolu metin. Tek satırlı alanlarda satır sonu/ardışık boşluk tek boşluğa iner:
    Pillow satır sonlu metni ölçemiyor ve çiziciyi çökertiyordu (sabotaj vakası).
    `paragraf=True`: satır sonları korunur (paragraf ayracıdır)."""
    for d in degerler:
        if isinstance(d, str) and d.strip():
            if paragraf:
                return "\n".join(" ".join(s.split()) for s in d.strip().splitlines())
            return " ".join(d.split())
    return ""


def girdiyi_hazirla(haber: Dict[str, Any]) -> Dict[str, Any]:
    """Kayıttaki alanları Instabot'un çizici girdilerine çevirir.

    Hem Instabot adları (ig_baslik, slayt_ozet, detay_yazisi, vurgu_sayi…) hem de
    eski B5 alanları (manset, spot, detay_maddeleri, uzman_notu) kabul edilir; böylece
    onay bekleyen eski kayıtlar da çizilebilir.
    """
    baslik = _bos_degil(haber.get("ig_baslik"), haber.get("manset"), haber.get("baslik"),
                        haber.get("orijinal_baslik")).replace("**", "")
    ozet = _bos_degil(haber.get("slayt_ozet"), haber.get("spot"), haber.get("ozet"))
    detay = _bos_degil(haber.get("detay_yazisi"), paragraf=True)
    if not detay:
        parcalar = []
        for m in haber.get("detay_maddeleri") or []:
            if isinstance(m, dict) and _bos_degil(m.get("metin")):
                parcalar.append(_bos_degil(m.get("metin")))
        detay = "\n\n".join(parcalar)
    sayi = _bos_degil(haber.get("vurgu_sayi"))
    alinti = _bos_degil(haber.get("alinti"))
    return {
        "baslik": baslik,
        "ozet": ozet,
        "detay": detay,
        "kaynak": " · ".join(x for x in (_bos_degil(haber.get("kaynak_adi"), haber.get("kaynak")),
                                          _bos_degil(haber.get("foto_atif"))) if x),
        "vurgu": (sayi, _bos_degil(haber.get("vurgu_etiket"))) if sayi else None,
        "alinti": (alinti, _bos_degil(haber.get("alinti_sahibi"))) if alinti else None,
        "neden_onemli": _bos_degil(haber.get("neden_onemli")) or None,
        "sirada_ne_var": _bos_degil(haber.get("sirada_ne_var")) or None,
        # Eski B5'te "EDM uzman notu" vardı; Instabot'un karşılığı "sana etkisi"
        "sana_etkisi": _bos_degil(haber.get("sana_etkisi"), haber.get("uzman_notu")) or None,
        "ulke_kodu": _bos_degil(haber.get("ulke_kodu")),
        "ulke_adi": _bos_degil(haber.get("ulke_adi")),
        "kategori": _bos_degil(haber.get("kategori")) or "sektor",
    }


def ana_kareleri_ciz(haber: Dict[str, Any], foto: Any = None, kanca: bool = True):
    """1080x1920 ana kareler: kapak + detay sayfaları (Instabot düzeni). Üreteçtir: her kare
    çizildiği anda verilir, çağıran kaydeder. Hepsini önce çizip sonra kaydetmek,
    `scripts/gorsel_denetim.py`'nin çizim olaylarını yanlış karelere yazmasına yol açıyordu."""
    g = girdiyi_hazirla(haber)
    ayarlar = AYARLAR
    arka = _foto_ac(foto)
    if arka is not None:
        arkaplan = fotograftan_arkaplan(arka, GENISLIK, YUKSEKLIK)
    else:
        arkaplan = arkaplan_uret_yedek(g["kategori"], GENISLIK, YUKSEKLIK)

    kapak_haber = haber if kanca else {k: v for k, v in haber.items() if k not in ("kanca", "hook")}
    kapak = yaziyi_bas(
        arkaplan, g["baslik"], g["kaynak"], ayarlar,
        ozet=g["ozet"] or None,
        ulke_kodu=g["ulke_kodu"], ulke_adi=g["ulke_adi"],
        kategori=g["kategori"], haber=kapak_haber if kanca else None,
    )
    yield kapak

    sayfalar = detay_sayfalara_bol(
        g["detay"], ayarlar, vurgu=g["vurgu"], alinti=g["alinti"],
        neden_onemli=g["neden_onemli"], sirada_ne_var=g["sirada_ne_var"],
        sana_etkisi=g["sana_etkisi"],
    )
    sayfalar = [s for s in sayfalar if s]
    for i, bloklar in enumerate(sayfalar, start=1):
        yield detay_slayti(
            baslik=g["baslik"], detay=g["detay"], kaynak=g["kaynak"], ayarlar=ayarlar,
            kategori=g["kategori"], son_dakika=False,
            ulke_kodu=g["ulke_kodu"], ulke_adi=g["ulke_adi"],
            satirlar=bloklar, sayfa=i, toplam_sayfa=len(sayfalar),
        )


def beslemeye_kirp(ana: Image.Image) -> Image.Image:
    """9:16 ana kareden akış karesi: ortadan 1080x1350 (içerik zaten bu kutudadır)."""
    return ana.crop((0, KUTU_UST, GENISLIK, KUTU_ALT))


def slaytlari_uret(
    haber: Dict[str, Any],
    cikti_dizini: Path,
    cikti_onek: str,
    olcu: str = "besleme",
    foto_yolu: Any = None,
    kanca: bool = True,
) -> List[Path]:
    """Haber carousel'i: kapak + detay sayfaları. Dosya adları eski çizici ile aynı
    (`<onek>_dailybrief_s<n>.jpg`); çağıranlar (Telegram, yayın, video) değişmez."""
    cikti_dizini = Path(cikti_dizini)
    cikti_dizini.mkdir(parents=True, exist_ok=True)
    _kayittaki_alanlari_ac(haber)
    if not girdiyi_hazirla(haber)["baslik"]:
        from .make_image import EksikIcerik
        raise EksikIcerik("Haber: manşet yok")
    foto = fotografi_sec(haber, foto_yolu, cikti_dizini)
    yollar: List[Path] = []
    for i, kare in enumerate(ana_kareleri_ciz(haber, foto, kanca=kanca), start=1):
        cikti = beslemeye_kirp(kare) if olcu in ("besleme", "feed", "4_5") else kare
        yol = cikti_dizini / f"{cikti_onek}_dailybrief_s{i}.jpg"
        cikti.convert("RGB").save(yol, "JPEG", quality=95, subsampling=0, optimize=True)
        yollar.append(yol)
    log.info("Haber (Instabot tasarımı) %d slayt üretildi (olcu=%s)", len(yollar), olcu)
    return yollar
