"""
haber_puanlama.py — Haber Değerlendirme Motoru

Bir haberin EDM için paylaşmaya değer olup olmadığına karar verir ve kararı
AÇIKLAR. Tek bir sayı yerine adlandırılmış bileşenler üretir; böylece "bu haber
neden elendi" sorusu yanıtlanabilir.

Neden yeniden yazıldı — gerçek veriyle ölçülen üç kusur:

1. KAYNAK AĞIRLIĞI İÇERİĞİ EZİYORDU. Eski formül `onem = agirlik + sinyal`
   idi; ağırlık 7-10, sinyal 0-10. Sonuç: aynı Yargıtay kararı AA'dan geçiyor,
   Hürriyet'ten eleniyordu. "Silivri imar planı askıya çıktı" (EDM için
   olabilecek en değerli haber) eleniyor, genel bir faiz haberi geçiyordu.
   Kaynağın prestiji, O HABERİN değerli olduğunu söylemez.

2. TÜRKÇE EK YAPISI GÖZ ARDI EDİLİYORDU. `\\bev sahibi\\b` deseni
   "ev sahipleri"ni tutmuyor, `\\bkira\\b` "kiracının"ı tutmuyordu. Emlakkulisi
   beslemesinde "Ev sahipleri dikkat! Bu maddeyi kontrol etmeden tahliye davası
   açmayın" başlığı bu yüzden eleniyordu — oysa aradığımız içeriğin tarifi bu.

3. REKLAM GÜRÜLTÜSÜ SÜZÜLMÜYORDU. Emlak haber kaynaklarının yarısı proje
   tanıtımı ("X projesinde 6 milyon TL'den başlayan fiyatlarla satışta").
   İçinde "konut" geçtiği için süzgeçten geçiyorlardı.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import filtre

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Türkçe ek-duyarlı eşleşme
# ---------------------------------------------------------------------------

# Türkçe eklemeli bir dil: kök sabit kalır, ekler sona yapışır.
# "tapu" → tapuda, tapunun, tapuya, tapusuz; "kira" → kiralık, kiracı, kirada.
# Bu yüzden kelime sonu sınırı (\b) yerine EK TOLERANSLI desen kullanılıyor.
_EK_DESEN = r"(?:[a-zçğıöşü']{0,8})?(?=\b|[^a-zçğıöşü])"

# Kök eşleşmesinin yanlış kelimeyi yakaladığı bilinen durumlar.
# Emlakkulisi beslemesinde "Lego Kiraztepe'de 48 ay taksitle yazlık" başlığı
# "kira" köküne takılıyordu.
YANLIS_ESLESME = {
    "kira": ["kiraz", "kirazl", "kiraath"],
    "arsa": ["arsen"],
    "daire": ["dairesel"],
    "imar": ["imaj", "imalat", "imam"],
    "kat": ["katıl", "katk", "katil", "katman", "kate", "katr"],
    "ev": [],          # "ev" tek başına çok kısa; aşağıda özel ele alınıyor
}

# Tek başına aranmayacak kadar kısa/yaygın kökler yalnızca tamlama içinde geçer
KISA_KOKLER = {"ev", "kat"}


# Türkçe ünsüz yumuşaması: sonu p/ç/t/k ile biten kök, ünlüyle başlayan ek
# alınca b/c/d/ğ'ye döner. "sahip" → "sahibi" ama "sahipleri".
# Bu yüzden kökün iki biçimi de aranmalı; birim testi bunu
# `terim_gecer("Ev sahipleri", "ev sahip")` vakasıyla yakaladı.
_YUMUSAMA = {"p": "b", "ç": "c", "t": "d", "k": "ğ"}


def _kok_varyantlari(kok: str) -> List[str]:
    varyantlar = [kok]
    if kok and kok[-1] in _YUMUSAMA:
        varyantlar.append(kok[:-1] + _YUMUSAMA[kok[-1]])
    # "k" çoğu zaman "ğ" yerine korunur (park → parkı); ters yönü de dene
    ters = {v: k for k, v in _YUMUSAMA.items()}
    if kok and kok[-1] in ters:
        varyantlar.append(kok[:-1] + ters[kok[-1]])
    return varyantlar


def _desen(kok: str) -> re.Pattern:
    govde = "|".join(re.escape(v) for v in _kok_varyantlari(kok.lower()))
    return re.compile(r"(?:^|[^a-zçğıöşü])(?:" + govde + r")" + _EK_DESEN, re.IGNORECASE)


_DESEN_ONBELLEK: Dict[str, re.Pattern] = {}


def terim_gecer(metin: str, kok: str) -> bool:
    """Kökün metinde (ekleriyle birlikte) geçip geçmediğini söyler."""
    kok = filtre.kucult(kok).strip()
    metin_k = filtre.kucult(metin)
    if kok in KISA_KOKLER and " " not in kok:
        # "ev" gibi kökler yalnızca tam kelime olarak sayılır; "evrak", "evlilik"
        # gibi kelimeler yanlış pozitif üretiyordu.
        return re.search(r"(?:^|[^a-zçğıöşü])" + re.escape(kok) + r"(?=\b|[^a-zçğıöşü])", metin_k) is not None

    if kok not in _DESEN_ONBELLEK:
        _DESEN_ONBELLEK[kok] = _desen(kok)
    if not _DESEN_ONBELLEK[kok].search(metin_k):
        return False

    for yanlis in YANLIS_ESLESME.get(kok, []):
        if yanlis in metin_k:
            # Yanlış eşleşme kelimesi dışında gerçek bir geçiş var mı
            temiz = re.sub(re.escape(yanlis) + r"[a-zçğıöşü']*", " ", metin_k)
            if not _DESEN_ONBELLEK[kok].search(temiz):
                return False
    return True


def _kacini_tutuyor(metin: str, kokler: List[str]) -> List[str]:
    return [k for k in kokler if terim_gecer(metin, k)]


# ---------------------------------------------------------------------------
# Terim kümeleri — her biri bir içerik sütununa bağlı (ICERIK-SISTEMI.md §3)
# ---------------------------------------------------------------------------

MEVZUAT = [
    "yargıtay", "danıştay", "kanun", "yönetmelik", "genelge", "tebliğ",
    "resmî gazete", "resmi gazete", "içtihat", "emsal karar", "mahkeme",
    "yasa", "düzenleme", "madde", "hüküm", "yürürlü",
]

EYLEM = [   # okuyanın bir şey YAPMASI gereken haberler
    "başvuru", "son tarih", "süre", "itiraz", "askıya çık", "askı",
    "beyan", "bildirim", "zorunlu", "ceza", "yaptırım", "muafiyet",
    "indirim", "istisna", "hak düşürücü", "ihtar", "dava aç",
]

# Sütun eşlemesi: haber bir sütuna oturmuyorsa bizim işimiz değildir
SUTUN_TERIMLERI: Dict[str, List[str]] = {
    "S1": ["tapu", "şufa", "önalım", "hisseli", "şerh", "kadastro", "miras",
           "intikal", "ipotek", "vekâlet", "vekalet", "kaparo", "temellük",
           "harç", "devir", "tescil", "iskân", "iskan", "kat mülkiyet", "kat irtifak"],
    "S2": ["kiracı", "ev sahip", "kira", "tahliye", "depozito",
           "taahhütname", "aidat", "kontrat", "kira artış", "tüfe"],
    "S3": ["imar", "arsa", "tarla", "parsel", "emsal", "taks", "kaks",
           "ifraz", "tevhid", "tiny house", "ruhsat", "kamulaştırma",
           "tarım arazisi", "yapı kayıt", "kentsel dönüşüm"],
    "S4": ["konut fiyat", "metrekare", "m2", "kira çarpan", "getiri",
           "konut satış", "faiz", "konut kredisi", "enflasyon", "amortisman",
           "değer artış", "emlak vergisi", "rayiç"],
}

YEREL_YAKIN = ["silivri", "trakya", "çatalca", "büyükçekmece", "beylikdüzü",
               "çorlu", "çerkezköy", "tekirdağ", "edirne", "kırklareli", "marmaraereğlisi"]
YEREL_GENIS = ["istanbul", "marmara"]

KITLE_GENIS = ["kiracı", "ev sahip", "konut", "daire", "kira", "tapu"]

# ---------------------------------------------------------------------------
# Olumsuz sinyaller
# ---------------------------------------------------------------------------

# Proje tanıtımı / ilan. Emlak haber kaynaklarının yarısı bu.
REKLAM = [
    "fiyatlarla satışta", "başlayan fiyatlarla", "fiyat listesi", "güncel fiyat",
    "taksitle", "peşinat", "senetle", "kampanya", "fırsat", "teslimler",
    "satışa çıktı", "satışta", "yeni proje", "lansman", "ödeme planı",
    "cazip", "ayrıcalık", "hemen teslim", "anahtar teslim",
]

PR_DEMEC = ["açıkladı", "konuştu", "ziyaret etti", "mesaj yayımladı",
            "değerlendirdi", "imzayı attı", "protokol imzaland", "ödül aldı"]

# Emlak kelimesi geçse de haber değeri olmayan konular
DISLANAN = [
    "cezaevi", "tutuklu", "gözaltı", "operasyon", "cinayet", "trafik kazası",
    "yangın", "maç", "transfer", "dizi", "konser", "festival", "altın fiyat",
    "döviz kuru", "borsa", "kripto", "vatandaşlık",
]

# Türkiye dışı — okuyucumuz için eyleme dönüşmez
UZAK = ["abd", "avrupa", "londra", "dubai", "ispanya", "karayip", "almanya",
        "euro bölgesi", "new york", "yunanistan"]

# Bölgemiz dışındaki büyük şehirler. Tam eleme değil, sıralama düzeltmesi:
# "Karayollarından Ankara'da satılık imarlı arsalar" en yüksek puanı alıp
# triyaj sırasının başına geçiyordu ve boşuna LLM çağrısı yakıyordu.
# Silivri'deki takipçi için Ankara arsa ihalesi eyleme dönüşmüyor.
UZAK_SEHIR = ["ankara", "izmir", "bursa", "antalya", "adana", "konya",
              "gaziantep", "trabzon", "samsun", "kayseri", "diyarbakır", "mersin"]

# Açıklayıcı/rehber içerik. Haber değil ama KONU ÖNERİSİ olarak değerli:
# "Temellük nedir?" bizim konu bankamızda olmayan bir konuyu işaret ediyor.
REHBER_KALIPLARI = ["nedir", "ne demek", "nasıl", "kimler", "hangi durumda",
                    "dikkat edilmesi", "nelere dikkat", "kaç gün", "ne zaman",
                    "gerekir mi", "alınır mı", "yapılır mı", "olur mu"]


@dataclass
class Degerlendirme:
    """Bir haberin puan dökümü. Karar açıklanabilir olsun diye her bileşen ayrı."""
    puan: int = 0
    sutun: Optional[str] = None
    bilesenler: Dict[str, int] = field(default_factory=dict)
    isaretler: List[str] = field(default_factory=list)
    rehber_mi: bool = False
    red_sebebi: Optional[str] = None

    @property
    def gecti(self) -> bool:
        return self.red_sebebi is None

    def ozet(self) -> str:
        if self.red_sebebi:
            return f"RED ({self.red_sebebi})"
        dokum = " ".join(f"{k}{v:+d}" for k, v in self.bilesenler.items() if v)
        return f"{self.puan:2} [{self.sutun}] {dokum}"


def degerlendir(baslik: str, ozet: str = "", yas_saat: float = 0.0) -> Degerlendirme:
    """Haberi puanlar ve hangi içerik sütununa ait olduğunu belirler.

    Puan 0-20 ölçeğinde. Karşılaştırma noktası: konu bankasından iyi hazırlanmış
    bir brief yaklaşık 12 değerindedir (ICERIK-SISTEMI.md §4). Haber ancak bunu
    geçerse takvimin önüne geçmeyi hak eder.
    """
    d = Degerlendirme()
    metin = f"{baslik} {ozet}".strip()
    if not metin:
        d.red_sebebi = "boş içerik"
        return d

    baslik_k = filtre.kucult(baslik)
    metin_k = filtre.kucult(metin)

    # --- Kesin elemeler ---
    if any(t in metin_k for t in DISLANAN):
        d.red_sebebi = "konu dışı"
        return d

    reklam_isaretleri = [r for r in REKLAM if r in metin_k]
    # Başlıkta hem reklam kalıbı hem fiyat varsa bu bir ilandır, haber değil
    fiyat_var = bool(re.search(r"\d[\d.,]*\s*(?:milyon|bin|tl|₺)", baslik_k))
    if reklam_isaretleri and (fiyat_var or len(reklam_isaretleri) >= 2):
        d.red_sebebi = f"proje tanıtımı ({reklam_isaretleri[0]})"
        return d

    # --- Sütun eşlemesi: hangi içerik sütununa oturuyor ---
    sutun_skorlari: List[Tuple[int, str]] = []
    for sutun, terimler in SUTUN_TERIMLERI.items():
        tutan = _kacini_tutuyor(metin, terimler)
        if tutan:
            sutun_skorlari.append((len(tutan), sutun))
    if not sutun_skorlari:
        d.red_sebebi = "içerik sütununa oturmuyor"
        return d
    sutun_skorlari.sort(reverse=True)
    d.sutun = sutun_skorlari[0][1]
    d.bilesenler["sutun"] = min(3, sutun_skorlari[0][0] * 2)

    # --- Mevzuat: en güçlü sinyal. Kanun değişikliği herkesi ilgilendirir ---
    mevzuat_tutan = _kacini_tutuyor(metin, MEVZUAT)
    if mevzuat_tutan:
        d.bilesenler["mevzuat"] = min(5, 2 + len(mevzuat_tutan))
        d.isaretler.append(f"mevzuat: {', '.join(mevzuat_tutan[:3])}")

    # --- Eylem: okuyanın yapması gereken bir şey var mı ---
    eylem_tutan = _kacini_tutuyor(metin, EYLEM)
    if eylem_tutan:
        d.bilesenler["eylem"] = min(4, len(eylem_tutan) + 1)
        d.isaretler.append(f"eylem: {', '.join(eylem_tutan[:3])}")

    # --- Yerellik: yakın bölge bizim işimiz, İstanbul geneli kısmen ---
    if _kacini_tutuyor(metin, YEREL_YAKIN):
        d.bilesenler["yerel"] = 5
        d.isaretler.append("yakın bölge")
    elif _kacini_tutuyor(metin, YEREL_GENIS):
        d.bilesenler["yerel"] = 2

    # --- Kitle genişliği ---
    kitle = _kacini_tutuyor(metin, KITLE_GENIS)
    if kitle:
        d.bilesenler["kitle"] = min(2, len(kitle))

    # --- Somutluk: rakam, tarih, madde numarası ---
    somut = 0
    if re.search(r"\bmd\.?\s*\d+|\bmadde\s*\d+|\b\d{4}\s*sayılı", metin, re.IGNORECASE):
        somut += 2
    if re.search(r"%\s*\d+|\byüzde\s*\d+", metin):
        somut += 1
    if re.search(r"\b\d+\s*(?:gün|ay|yıl)\b", metin):
        somut += 1
    if somut:
        d.bilesenler["somut"] = min(3, somut)

    # --- Tazelik ---
    if yas_saat <= 12:
        d.bilesenler["taze"] = 2
    elif yas_saat <= 36:
        d.bilesenler["taze"] = 1

    # --- Olumsuzlar ---
    if any(p in baslik_l for p in PR_DEMEC):
        d.bilesenler["pr"] = -3
        d.isaretler.append("demeç/PR dili")
    if reklam_isaretleri:
        d.bilesenler["reklam"] = -3
        d.isaretler.append(f"reklam dili: {reklam_isaretleri[0]}")
    if _kacini_tutuyor(metin, UZAK) and not d.bilesenler.get("yerel"):
        d.bilesenler["uzak"] = -3
        d.isaretler.append("Türkiye dışı")
    elif not d.bilesenler.get("yerel"):
        uzak_sehirler = _kacini_tutuyor(metin, UZAK_SEHIR)
        if uzak_sehirler:
            d.bilesenler["baska_sehir"] = -3
            d.isaretler.append(f"bölge dışı: {uzak_sehirler[0]}")

    # --- Rehber/açıklayıcı içerik: haber değil, konu önerisi ---
    if any(k in baslik_l for k in REHBER_KALIPLARI):
        d.rehber_mi = True
        d.isaretler.append("rehber içerik — konu bankası adayı")

    d.puan = max(0, sum(d.bilesenler.values()))
    return d
