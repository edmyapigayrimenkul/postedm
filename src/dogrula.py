"""
dogrula.py — Yayın Öncesi İçerik Denetimi

Onay mesajı gönderilmeden ÖNCE çalışır. İki tür bulgu var:
  ⛔ kritik — kaynakta olmayan madde, süre, çoğunluk, oran, içtihat ya da kaynak
     adresi açılmayan haber. İçerik ONAYA BİLE SUNULMAZ (2026-09-24 kararı:
     yalan bilgiye müsamaha yok). Üretimde bir kez düzeltme turu denenir.
  ⚠️ uyarı — onaylayan kişiye "şuna bir daha bak" der, yayını kilitlemez.

instabot'un `dogrula.py`'sinden uyarlandı; denetimler emlak içeriğine göre
yeniden yazıldı.

EN BÜYÜK RİSKİMİZ UYDURMA MEVZUAT. Gerçek bir emlak ofisinin hesabında
yanlış kanun maddesi ciddi bir sorumluluktur. Prompt bunu yasaklıyor
(ICERIK-SISTEMI.md §7.2) ama prompt bir dilek, bu katman bir denetim.

⚠️ TÜRKÇE 'İ' TUZAĞI: "İlişkin".lower() Python'da noktalı i üretir
("i̇lişkin") ve düz karşılaştırma TUTMAZ. instabot'ta bu yüzden tarama
sessizce hiçbir şey yakalamadı, her şey "temiz" göründü. Bu modüldeki
tüm karşılaştırmalar `_kucult()` üzerinden geçer.

NE YAKALAMIYOR (bilinçli sınır): anlam kayması. "geçerlidir" ile
"geçersizdir" aynı maddeyi ve aynı kelimeleri taşır. Düzenli ifade bunu göremez;
`capraz_denetim.py` ikinci bir modele kaynakla içeriği karşılaştırtır (yalnız ⚠️,
kapıda `icerigi_denetle` içinde), son söz yine insan onayıdır.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional, Set

from . import filtre, haber_alanlari

log = logging.getLogger(__name__)


def _kucult(metin: str) -> str:
    return filtre.kucult(metin)


def _sadelestir(metin: str) -> str:
    """Türkçe karakterleri ve noktalamayı indirger."""
    metin = metin.replace("İ", "i").replace("I", "i").replace("ı", "i")
    metin = unicodedata.normalize("NFKD", metin)
    metin = "".join(c for c in metin if not unicodedata.combining(c))
    return re.sub(r"[^0-9a-z]", " ", metin.lower())


def _kok(kelime: str) -> str:
    """
    Kaba kök: kesme işaretinden kes, kalanın ilk %70'ini al.
    "İstanbul'a" -> "istanbul",  "Soruşturmasında" -> "sorustur"
    """
    k = _sadelestir(kelime.split("'")[0]).strip()
    return k[: max(4, int(len(k) * 0.7))]


def _sayilar(metin: str) -> Set[str]:
    """Ayraçları temizlenmiş sayılar. '2.500' ve '2500' aynı sayılıyor."""
    duz = metin.replace(".", "").replace(",", "")
    return {s for s in re.findall(r"\d+", duz) if len(s) >= 1}


_YAZIYLA_SAYI = {
    "bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5, "altı": 6,
    "yedi": 7, "sekiz": 8, "dokuz": 9, "on": 10, "yirmi": 20,
    "otuz": 30, "kırk": 40, "elli": 50, "altmış": 60, "yetmiş": 70,
    "seksen": 80, "doksan": 90, "yüz": 100,
}

_CARPANLAR = {"bin": 1000, "milyon": 10 ** 6, "milyar": 10 ** 9}


def sayi_esdegerleri(metin: str | None) -> Set[str]:
    """
    Kaynak metindeki sayıların BÜTÜN makul Türkçe yazımları.
    "435 bin 683" -> 435683, "4 lira 62 kuruş" -> 462, vb.
    """
    m = str(metin or "")
    sonuc = set(_sayilar(m))

    obek = re.compile(r"(\d[\d.,]*)\s*(bin|milyon|milyar)?(?=\s|$|[^\w])", re.IGNORECASE)
    parcalar = list(obek.finditer(m))
    i = 0
    while i < len(parcalar):
        toplam = 0.0
        onceki_carpan = None
        j = i
        while j < len(parcalar):
            e = parcalar[j]
            try:
                taban = float(e.group(1).replace(".", "").replace(",", "."))
            except ValueError:
                break
            carpan = _CARPANLAR.get((e.group(2) or "").lower(), 1)
            if onceki_carpan is not None and carpan >= onceki_carpan:
                break
            if j > i and m[parcalar[j - 1].end():e.start()].strip():
                break
            toplam += taban * carpan
            onceki_carpan = carpan
            j += 1
            if carpan == 1:
                break
        if j > i and toplam:
            try:
                sonuc.add(str(int(toplam)))
            except (ValueError, OverflowError):
                pass
        artan = 0.0
        for k in range(j - 1, i - 1, -1):
            e = parcalar[k]
            try:
                taban = float(e.group(1).replace(".", "").replace(",", "."))
            except ValueError:
                break
            artan += taban * _CARPANLAR.get((e.group(2) or "").lower(), 1)
            try:
                sonuc.add(str(int(artan)))
            except (ValueError, OverflowError):
                break
        i = max(j, i + 1)

    for e in re.finditer(r"(\d+)[,.](\d+)", m):
        sonuc.update((e.group(1), e.group(2), e.group(1) + e.group(2)))

    for e in re.finditer(r"(\d+)\s*(?:lira|tl|₺)\s*(\d+)\s*kuru", m, re.IGNORECASE):
        sonuc.add(e.group(1) + e.group(2))

    sade = _sadelestir(m)
    for kelime, deger in _YAZIYLA_SAYI.items():
        if re.search(r"\b" + _sadelestir(kelime).strip() + r"\b", sade):
            sonuc.add(str(deger))

    return sonuc


def alintiyi_denetle(alinti: str, kaynak: str) -> bool:
    """
    Alıntı kaynak metinde gerçekten geçiyor mu (%85 ardışık kelime penceresi).
    """
    if not alinti or not kaynak:
        return False

    a_kelime = [_kok(k) for k in alinti.split() if len(k) > 2]
    if len(a_kelime) < 3:
        return False

    k_sade = _sadelestir(kaynak)
    k_kelime = [_kok(k) for k in kaynak.split() if len(k) > 2]

    pencere = len(a_kelime) + 6
    hedef = int(len(a_kelime) * 0.85)
    for i in range(max(1, len(k_kelime) - pencere + 1)):
        parca = set(k_kelime[i:i + pencere])
        if sum(1 for k in a_kelime if k in parca) >= hedef:
            return True

    return _sadelestir(alinti).strip() in k_sade



# Metinde kanun maddesi arayan desenler
_MADDE_DESENLERI = [
    re.compile(r"\bmd\.?\s*(\d+(?:/\d+)?)", re.IGNORECASE),
    re.compile(r"\bmadde\s*(\d+(?:/\d+)?)", re.IGNORECASE),
    re.compile(r"\b(\d{4})\s*sayılı", re.IGNORECASE),
]

# Konuyu duyurup sonucu saklayan başlık kalıpları.
# "Şufa nedir?" kötü bir manşet değil ama "...hakkında bilmeniz gerekenler"
# okuyana hiçbir şey vaat etmiyor.
_ICI_BOS_KALIPLAR = [
    "bilmeniz gerekenler", "hakkında her şey", "ne anlama geliyor",
    "dikkat çeken detay", "işte detaylar", "merak edilenler",
    "a-z rehberi", "tüm detaylar", "son durum", "gündemde",
]

# Abartı / clickbait kalıpları (prompt yasaklıyor, burada denetleniyor)
_ABARTI = ["şok", "inanılmaz", "kaçırmayın", "bomba", "müjde", "sakın",
           "asla", "herkes bunu", "kimse bilmiyor", "sır gibi"]

# İçi boş genel geçer tavsiyeler ("Sakin Otorite" yerine kuru nasihat veren kalıplar)
_BOS_TAVSIYELER = [
    "uzmana danışın", "uzmanına danışın", "avukatınıza başvurun",
    "dikkatli olun", "araştırma yapın", "ihmal etmeyin",
    "tedbirli olun", "önem taşır", "göz ardı etmeyin", "yetkililere danışın",
    # #509 (2026-10-06): "yatırımcılar makroekonomik verileri yakından takip ediyor",
    # "değerleri titizlikle kontrol edilmeye devam edilmelidir"
    "yakından takip", "titizlikle",
]

# Yakın bölge adları — brief'te yerel bağ yokken metinde geçiyorsa uydurma olabilir
_YEREL_ADLAR = ["silivri", "trakya", "çatalca", "çorlu", "çerkezköy",
                "tekirdağ", "edirne", "kırklareli", "selimpaşa", "alibey"]

_DUYGU_ATFI = re.compile(
    r"gurur|coşku|moral kaynağı|motivasyon kaynağı|sevinç kaynağı|"
    r"tüm (Türkiye|ülke|dünya)'?d[ae]", re.IGNORECASE)

_TOREN_DILI = re.compile(
    r"tarihin?in en (önemli|büyük|prestijli|unutulmaz)|prestijli başarı|"
    r"kayda geçiyor|altın harflerle|başarılarından biri olarak|"
    r"zaferle birlikte|bölgenin parlayan yıldızı|yatırımcıların gözdesi|"
    r"fırsat kapısı|göz kamaştır", re.IGNORECASE)

_SOMUT_SAYI = re.compile(r"\d")

_ETIKET_FIILLERI = {
    "bitti", "erdi", "edildi", "oldu", "başladı", "açıklandı",
    "yapıldı", "geldi", "gitti", "kaldı", "düştü", "çıktı",
    "verildi", "alındı", "yükseldi", "kesildi", "uzatıldı",
    "sona", "kalktı", "sürüyor", "ediyor", "gerekiyor",
}

_ETIKET_SAYI_EKLERI = re.compile(
    r"^(ya[sş][ıi]nda|ma[cç]l[ıi]k|sezonluk|ki[sş]ilik|katl[ıi]|"
    r"puanl[ıi]k|haneli|gunluk )", re.IGNORECASE)


def bos_ovgu_mu(cumle: str) -> bool:
    """
    Bu cümle bilgi taşımayan bir övgü veya yapay tören dili mi?
    Bilgi veren somut sayılı ifadeler korunur.
    """
    metin = (cumle or "").strip()
    if not metin:
        return False
    if _DUYGU_ATFI.search(metin):
        return True
    return bool(_TOREN_DILI.search(metin)) and not _SOMUT_SAYI.search(metin)


def ovguyu_ele(cumle: str) -> str:
    """İçi boş övgüyse boş dize döner — çağıran taraf o bloğu basmaz."""
    if bos_ovgu_mu(cumle):
        log.info("içi boş övgü elendi: %s", (cumle or "")[:80])
        return ""
    return cumle


def vurgu_zayif_mi(deger: str | None, etiket: str | None) -> str | None:
    """
    Vurgu rakamı kancaya veya slayta basılmaya değer mi?
    Zayıfsa sebebi döner (loglanabilsin diye), güçlüyse None.
    """
    d = (deger or "").strip()
    e = (etiket or "").strip()
    if not d:
        return None

    # ① Çıplak tek haneli sayı — büyüklük/çarpıcılık duygusu yok
    if re.fullmatch(r"\d", d):
        return "çıplak tek haneli sayı"

    # ② Etiket rakama yapışan ekle başlıyor ("38 yaşındaki …")
    if _ETIKET_SAYI_EKLERI.match(_sadelestir(e).strip()):
        return "etiket rakama yapışan ekle başlıyor"

    # ③ Etiket cümle — açık fiille bitiyor
    son = (e.split() or [""])[-1].strip(".,;:").casefold()
    if son in _ETIKET_FIILLERI:
        return "etiket cümle parçası (fiille bitiyor)"

    return None


def _tum_metin(veri: Dict[str, Any], captionlar: bool = False) -> str:
    """Görselde çizilen tüm metinleri tek dizede toplar.

    `captionlar=True` açıklama metinlerini de katar. Hukuki iddia denetimi
    (madde, süre, çoğunluk, oran) onlarla çalışır: Threads'te okunan şey
    caption'ın kendisi; #142'deki "2 yıl" hem görselde hem caption'daydı.
    Marka sesi denetimleri görselle sınırlı kalır — caption'daki hashtag ve
    kapanış çağrısı orada yanlış alarm üretir.
    """
    parcalar: List[str] = []

    def topla(d: Any) -> None:
        if isinstance(d, dict):
            for k, v in d.items():
                if k.startswith("_") or (k.startswith("caption") and not captionlar):
                    continue
                topla(v)
        elif isinstance(d, list):
            for v in d:
                topla(v)
        elif isinstance(d, str):
            parcalar.append(d)

    topla(veri)
    return " ".join(parcalar)


# ---------------------------------------------------------------------------
# HABER: kaynak metin ölçüttür (instabot `haberi_dogrula` paritesi)
# ---------------------------------------------------------------------------
#
# 2026-10-07 denetimi: haber yolunda rakam denetimi yalnızca % ve TL'ye bakıyordu
# ve `haberden_brief` her zaman `veri_kaynagi` doldurduğu için kaynakta olmayan
# rakam bile ⚠️ kalıyordu. Uydurma Silivri bağı da ⚠️ idi; yayınlanan 4 haberin
# 4'ünde vardı ve onaylayan göz alıştığı için geçiyordu. Haberde kaynak metin
# elimizde: orada olmayan sayı ve yerel bağ kanıtlanmış uydurmadır.

_HABER_ALANLARI = ("manset", "spot", "kanca", "vurgu_sayi", "vurgu_etiket", "alinti",
                   "neden_onemli", "sana_etkisi", "sirada_ne_var", "uzman_notu")


def _caption_govdesi(metin: str) -> str:
    """Sistemin eklediği iletişim satırı ve etiketler denetime girmez."""
    satirlar = [s for s in str(metin or "").splitlines()
                if "edmyapigayrimenkul" not in s.lower()]
    return re.sub(r"#\S+", " ", "\n".join(satirlar))


def haber_parcalari(veri: Dict[str, Any], captionlar: bool = False,
                    etiketler: bool = True) -> List[str]:
    """Haber içeriğinde modelin yazdığı metin, alan alan: kapak, maddeler, not,
    caption gövdesi (satır satır).

    `_tum_metin` her dize alanı topluyor (görsel adresi, kategori kodu…); sayı
    denetiminde adresteki rakamlar uydurma sanılırdı. Alanlar ayrı tutulur ki
    her biri cümle başı sayılsın — birleşik metinde maddenin ilk kelimesi
    önceki etiketin devamı gibi görünüp özel isim sanılıyordu.
    """
    parcalar = [haber_alanlari.kalin_sil(veri.get(k)) for k in _HABER_ALANLARI]
    if isinstance(veri.get("detay_yazisi"), str) and veri["detay_yazisi"].strip():
        # Instabot şeması: paragraflar (`**` işaretleri metne girmez)
        parcalar.extend(haber_alanlari.detay_paragraflari(veri, kalin=False))
    for m in veri.get("detay_maddeleri") or []:     # eski B5 kayıtları
        if isinstance(m, dict):
            if etiketler:
                # Eski kayıtlarda etiketler "01 // …" diye numaralı
                parcalar.append(re.sub(r"^\s*\d{1,2}\s*//\s*", "", str(m.get("etiket") or "")))
            parcalar.append(str(m.get("metin") or ""))
    if captionlar:
        for k in ("caption_instagram", "caption_facebook", "caption_threads"):
            parcalar.extend(_caption_govdesi(veri.get(k) or "").splitlines())
    return [p for p in parcalar if p.strip()]


def haber_metni(veri: Dict[str, Any], captionlar: bool = False) -> str:
    return " ".join(haber_parcalari(veri, captionlar))


# Model "SPK" yerine "Sermaye Piyasası Kurulu" yazabilir; kurum adı içindeki cins
# isimler ve milliyet sıfatları uydurma kişi/kurum değildir. Liste bilerek dar
# (instabot ölçümü: geniş liste 5 elemenin 3'ünde yanlış alarm verdi).
_ISIM_DURAKLARI = {
    "kurulu", "kurumu", "kurum", "bakanligi", "bakanlik", "baskanligi",
    "baskani", "mudurlugu", "mudurluk", "genel", "meclis", "meclisi",
    "piyasasi", "piyasalari", "kanunu", "kanun", "yonetmeligi", "komisyonu",
    "birligi", "odasi", "dernegi", "vakfi", "universitesi", "belediyesi",
    "valiligi", "mahkemesi", "dairesi", "merkezi", "idaresi", "ajansi",
    "borsasi", "bankasi", "sirketi", "holding", "grubu", "hukuk", "ceza",
    "turk", "alman", "ingiliz", "fransiz", "amerikan", "japon", "cinli", "rus",
    "edm", "yapi", "gayrimenkul", "kaynak", "temsili", "uzman", "degerlendirmesi", "notu",
    "bakani", "baskan", "sozcusu", "yardimcisi", "vekili", "muduru",
    "ocak", "subat", "mart", "nisan", "mayis", "haziran", "temmuz", "agustos",
    "eylul", "ekim", "kasim", "aralik",
    "pazartesi", "sali", "carsamba", "persembe", "cuma", "cumartesi", "pazar",
}


def _ozel_isimler(metin: str) -> List[str]:
    """Cümle ortasında büyük harfle başlayan kelimeler (cümle başı atlanır)."""
    bulunan: List[str] = []
    kelimeler = metin.split()
    for i, kelime in enumerate(kelimeler):
        temiz = kelime.strip(".,;:!?'\"()[]«»“”")
        if len(temiz) < 4 or not temiz[0].isupper() or temiz.isupper():
            continue
        if i == 0 or kelimeler[i - 1].endswith((".", ":", "?", "!", "//")):
            continue
        sade = _sadelestir(temiz.split("'")[0].split("’")[0]).strip()
        if not sade or sade in _ISIM_DURAKLARI:
            continue
        bulunan.append(temiz)
    return bulunan


# Kancada bilgi taşımayan bitişler (instabot prompt kuralı 4). Dar tutuldu.
_ICI_BOS_KANCA = re.compile(
    r"\b(yay[ıi]nland[ıi]|a[çc][ıi]kland[ıi]|g[üu]ndemde|yeni d[öo]nem|riski|tepkisi|endi[şs]esi)\s*$",
    re.IGNORECASE)


# "GEREKLİ BELGE VE KRİTERLER" gibi, hiçbir somut şey söylemeyen genel kelimeler (#470)
_GENEL_KANCA_KELIMELERI = {
    "gerekli", "belge", "belgeler", "kriter", "kriterler", "şart", "şartlar", "bilgi", "bilgiler", "detay",
    "detaylar", "gelişme", "gelişmeler", "süreç", "yeni", "önemli", "dikkat", "ve", "ile", "için", "başvuru",
    "karar", "kurallar", "kural", "değişiklik", "dönem", "haber", "son", "durum", "açıklama", "açıklandı",
}


def kanca_ici_bos_mu(kanca: Optional[str]) -> bool:
    """Rakam, tarih ya da ad taşımayan kanca: boş bir fiille bitiyor ya da yalnız genel kelimelerden oluşuyor."""
    k = str(kanca or "").strip()
    if not k or re.search(r"\d", k):
        return False
    if any(_ICI_BOS_KANCA.search(p.strip()) for p in k.split("//") if p.strip()):
        return True
    kelimeler = [_kucult(w).strip(".,;:") for w in k.replace("//", " ").split()]   # Türkçe İ tuzağı: .lower() değil
    kelimeler = [w for w in kelimeler if w]
    return bool(kelimeler) and all(w in _GENEL_KANCA_KELIMELERI for w in kelimeler)


# Kaynakta suçlama/soruşturma olduğunu gösteren ifadeler (Instabot `SUCLAMA_ISARETI`).
_SUCLAMA_ISARETI = ("iddia", "öne sürül", "şüpheli", "gözaltına", "soruşturma",
                    "savcılık", "hakkında dava", "suçlam", "tutuklama talebi")
# Üretilen metinde ihtiyat korunduğunu gösteren ifadeler (Instabot `IHTIYAT_ISARETI`).
_IHTIYAT_ISARETI = ("iddia", "öne sürül", "şüpheli", "soruşturma", "gözaltı",
                    "savcılık", "hakkında dava", "suçlam", "tutukland", "yargılan",
                    "belirtil", "bildiril", "açıklad", "duyur")


def suclama_dili_denetle(veri: Dict[str, Any], kaynak: str) -> List[str]:
    """Kaynakta suçlama/soruşturma varsa üretilen metinde ihtiyat dili korunmuş mu?

    Sayı ve isim denetimi bunu yakalamaz: kaynak "hakkında soruşturma başlatıldı" derken
    metin "suç örgütü elebaşı" diyebilir, bütün sayı ve isimler tutar ama dil
    kesinleşmiştir (iftira riski). Instabot ölçümü: atıflı başlıkta ("Kurum: …") yanlış
    alarm verdiği için atıflı başlık muaf. Uyarıdır, yayını kilitlemez.
    """
    kaynak_sade = _sadelestir(kaynak or "")
    if not kaynak_sade or not any(_sadelestir(k) in kaynak_sade for k in _SUCLAMA_ISARETI):
        return []
    baslik = haber_alanlari.kalin_sil(veri.get("manset"))
    if re.match(r"^[^:]{2,40}:", baslik):
        return []
    uretilen = _sadelestir(" ".join([baslik, haber_alanlari.kalin_sil(veri.get("spot")),
                                     " ".join(haber_alanlari.detay_paragraflari(veri, kalin=False)),
                                     haber_alanlari.kalin_sil(veri.get("caption_instagram"))]))
    if any(_sadelestir(k) in uretilen for k in _IHTIYAT_ISARETI):
        return []
    return ["⚠️ SUÇLAMA KESİN DİLLE: kaynakta soruşturma/iddia var, metinde ihtiyat dili (iddia, soruşturma, "
            "şüpheli…) yok — kimse mahkeme kararı olmadan suçlu ilan edilmez."]


def haber_alanlarini_sadelestir(veri: Dict[str, Any], kaynak: str) -> Dict[str, Any]:
    """Üretim sonrası: kaynakta dayanağı olmayan ÇİZİLEN öğeleri sessizce eler (Instabot standardı).

    Uydurma alıntı kapıda ⛔ olurdu; ama bir alıntı yüzünden bütün içeriği durdurmak yerine
    alıntı atılır ve slayt onsuz basılır (Instabot: `alintiyi_denetle`). Aynısı zayıf ya da
    kaynaksız vurgu rakamı, boş övgü ve içi boş kanca için geçerli. Kapı yedek olarak durur.
    """
    if not isinstance(veri, dict):
        return veri
    kaynak = kaynak or ""

    # İnce kaynak (bilinen ama 400 karakterden kısa): model boşluğu genel cümlelerle dolduruyor
    # (#171: "…önem taşıyor", "…süreçleri takip edilecek"). Detay ilk iki paragrafla sınırlanır;
    # çıkarım ağırlıklı alanlar (neden önemli, sana etkisi) atılır.
    if kaynak.strip() and len(kaynak.strip()) < 400:
        paragraflar = haber_alanlari.detay_paragraflari(veri)
        if len(paragraflar) > 2:
            veri["detay_yazisi"] = "\n\n".join(paragraflar[:2])
        veri["neden_onemli"] = veri["sana_etkisi"] = ""

    # Başlığın sonunda nokta yok (prompt kuralı; model sık atlıyor, #470)
    if isinstance(veri.get("manset"), str):
        veri["manset"] = veri["manset"].strip().rstrip(".").strip()

    soz, _sahibi = haber_alanlari.alinti(veri)
    if soz and (len(soz.split()) > 24 or not alintiyi_denetle(soz, kaynak)):
        log.info("kaynakta doğrulanamayan alıntı atıldı: %s", soz[:60])
        veri["alinti"] = veri["alinti_sahibi"] = ""

    sayi, etiket = haber_alanlari.vurgu(veri)
    if etiket and len(etiket) > 44:
        # Etiket ad öbeğidir, cümle değil; tek satırda 30 puntoda durur
        etiket = etiket[:44].rsplit(" ", 1)[0].rstrip(" ,;:-")
        veri["vurgu_etiket"] = etiket
    if sayi:
        neden = vurgu_zayif_mi(sayi, etiket)
        if not neden and len(sayi) > 18:
            neden = "sayı çok uzun (dev punto tek satıra sığmaz)"
        kaynak_sayilar = sayi_esdegerleri(kaynak)
        # Başlıkta, özette ya da kancada zaten geçen sayı "ikinci çarpıcı sayı" değildir
        baslikta = _sayilar(" ".join(haber_alanlari.kalin_sil(veri.get(k)) for k in ("manset", "spot", "kanca")))
        sayi_set = _sayilar(sayi)
        if not neden and kaynak and not sayi_set <= kaynak_sayilar:
            neden = "sayı kaynakta yok"
        if not neden and sayi_set and sayi_set <= baslikta:
            neden = "sayı başlıkta/özette/kancada zaten geçiyor"
        if neden:
            log.info("vurgu rakamı atıldı (%s): %s / %s", neden, sayi, etiket)
            veri["vurgu_sayi"] = veri["vurgu_etiket"] = ""

    for alan in ("neden_onemli", "sana_etkisi"):
        if veri.get(alan):
            veri[alan] = ovguyu_ele(str(veri[alan]))

    if kanca_ici_bos_mu(veri.get("kanca")):
        log.info("içi boş kanca atıldı: %s", veri.get("kanca"))
        veri["kanca"] = ""

    kod = str(veri.get("ulke_kodu") or "").strip().lower()
    veri["ulke_kodu"] = kod if re.fullmatch(r"[a-z]{2,12}", kod) else ""
    if not veri["ulke_kodu"]:
        veri["ulke_adi"] = ""
    return veri


def haber_kaynak_denetimi(veri: Dict[str, Any], brief: Dict[str, Any]) -> List[str]:
    """Haber içeriğini KAYNAK METNE karşı denetler."""
    uyarilar: List[str] = []
    kaynak = str(brief.get("makale_metni") or "")
    if not kaynak.strip():
        return uyarilar
    uretilen = haber_metni(veri, captionlar=True)

    kaynak_sayi = sayi_esdegerleri(kaynak)
    eksik = sorted({s for s in _sayilar(uretilen) if s not in kaynak_sayi},
                   key=lambda s: (len(s), s))
    if eksik:
        uyarilar.append(
            f"⛔ SAYI KAYNAKTA YOK: {', '.join(eksik[:4])} içerikte geçiyor ama haberin "
            f"kendi metninde yok. Yuvarlama ya da uydurma olabilir."
        )

    kaynak_kucuk = _kucult(kaynak)
    uretilen_kucuk = _kucult(uretilen)
    yerel = [a for a in _YEREL_ADLAR if a in uretilen_kucuk and a not in kaynak_kucuk]
    if yerel:
        uyarilar.append(
            f"⛔ YEREL BAĞ KAYNAKTA YOK: içerikte \"{yerel[0]}\" geçiyor ama haber "
            f"bölgeden hiç söz etmiyor."
        )

    # Manşet ve etiketler başlık düzeninde olabilir; özel isim denetimine girmez.
    # Yerel adlar yukarıda ⛔ olarak zaten raporlandı.
    kaynak_sade = _sadelestir(kaynak)
    yerel_sade = {_sadelestir(a).strip() for a in _YEREL_ADLAR}
    govde = haber_parcalari({k: v for k, v in veri.items() if k != "manset"},
                            captionlar=True, etiketler=False)
    isimler = sorted({i for parca in govde for i in _ozel_isimler(parca)
                      if _kok(i) and _kok(i) not in kaynak_sade
                      and _sadelestir(i.split("'")[0]).strip() not in yerel_sade})
    if isimler:
        uyarilar.append(
            f"⚠️ AD KAYNAKTA YOK: {', '.join(isimler[:6])} — kaynakta geçmiyor, elle teyit edin."
        )

    uyarilar.extend(suclama_dili_denetle(veri, kaynak))

    if kanca_ici_bos_mu(veri.get("kanca")):
        uyarilar.append(
            f"⚠️ İÇİ BOŞ KANCA: \"{veri.get('kanca')}\" — somut bir ayrıntı taşımıyor."
        )
    return uyarilar


def _maddeleri_bul(metin: str) -> List[str]:
    bulunan: List[str] = []
    for desen in _MADDE_DESENLERI:
        bulunan.extend(m.group(0).strip() for m in desen.finditer(metin))
    return bulunan


def _kanun_metni(brief: Optional[Dict[str, Any]]) -> str:
    """Süre/çoğunluk denetiminin ölçütü: haberde kaynak metin, konuda maddenin güncel metni."""
    if not brief:
        return ""
    if "mevzuat_metni" in brief:
        return str(brief.get("mevzuat_metni") or "")
    atif = brief.get("mevzuat")
    if not atif:
        return ""
    from . import config
    if config.test_modu():
        return ""
    try:
        from . import mevzuat
        return mevzuat.brief_mevzuati(atif).get("metin") or ""
    except Exception as e:
        log.warning("Güncel madde metni alınamadı, süre denetimi atlandı: %s", e)
        return ""


def denetle(veri: Dict[str, Any], brief: Optional[Dict[str, Any]] = None) -> List[str]:
    """İçeriği denetler ve uyarı listesi döner. Boş liste = temiz.

    `brief` verilirse mevzuat ve yerel bağ iddiaları onunla karşılaştırılır.
    """
    uyarilar: List[str] = []
    metin = _tum_metin(veri)
    kucuk = _kucult(metin)
    # Hukuki iddialar caption'da da aynı sorumluluğu taşır
    hukuki = _tum_metin(veri, captionlar=True)
    hukuki_kucuk = _kucult(hukuki)

    # --- 1. UYDURMA MEVZUAT (en kritik) ---
    maddeler = _maddeleri_bul(hukuki)
    if maddeler:
        dogrulanmis = _kucult(str((brief or {}).get("mevzuat") or ""))
        if not dogrulanmis:
            uyarilar.append(
                f"⛔ MEVZUAT DOĞRULANMAMIŞ: metinde {', '.join(sorted(set(maddeler))[:3])} "
                f"geçiyor ama brief'te doğrulanmış mevzuat YOK. Madde numarası uydurulmuş olabilir."
            )
        else:
            # Brief'te mevzuat var; metindeki her madde onunla örtüşmeli
            # Sayı KELİME olarak aranır: alt-dize araması "md. 9"u kaynaktaki
            # "3194" içinde bulup doğrulanmış sayıyordu.
            kacak = [m for m in set(maddeler)
                     if not any(re.search(rf"(?<![\d/]){re.escape(p)}(?![\d/])", dogrulanmis)
                                for p in re.findall(r"\d+(?:/\d+)?", m))]
            if kacak:
                uyarilar.append(
                    f"⛔ EK MADDE: metinde {', '.join(sorted(kacak)[:3])} geçiyor ama "
                    f"brief yalnızca \"{(brief or {}).get('mevzuat')}\" doğruluyor."
                )

    # --- 1b. SÜRE / ÇOĞUNLUK KANUN METNİYLE UYUŞMUYOR ---
    # Model eski hukuku biliyor (2026-09-24: önalımda "2 yıl" yazdı, kanun 7571 ile
    # 1 yıla inmişti; kentsel dönüşümde "üçte iki" yazdı, 2019'dan beri salt
    # çoğunluk). Brief'te maddenin güncel metni varsa içerikteki her süre ve
    # çoğunluk ifadesi o metinde geçmeli. Haberde ölçüt kaynak metnin kendisidir.
    kanun_metni = _kanun_metni(brief)
    if kanun_metni:
        from . import mevzuat as _mevzuat
        kacak_sure = sorted(_mevzuat.sure_ifadeleri(hukuki) - _mevzuat.sure_ifadeleri(kanun_metni))
        if kacak_sure:
            ornek = ", ".join(f"{n} {b}" for n, b in kacak_sure[:3])
            uyarilar.append(
                f"⛔ SÜRE KAYNAKTA YOK: içerikte {ornek} geçiyor ama maddenin güncel metninde "
                f"(ya da haber kaynağında) böyle bir süre yok. Eski hukuk ya da uydurma olabilir."
            )
        kanun_kucuk = _kucult(kanun_metni)
        kacak_cogunluk = [c for c in _mevzuat.CUNLUK_IFADELERI
                          if c in _mevzuat.cogunluk_katla(hukuki_kucuk) and c not in _mevzuat.cogunluk_katla(kanun_kucuk)]
        if kacak_cogunluk:
            uyarilar.append(
                f"⛔ ÇOĞUNLUK KAYNAKTA YOK: \"{kacak_cogunluk[0]}\" geçiyor ama güncel metinde bu çoğunluk yok."
            )
    elif brief is not None:
        # Ölçüt metin yok (yönetmeliğe dayanan konu, atıfsız özel içerik): süre
        # doğrulanamıyor. Kilitlemez ama onaylayanın gözünden kaçmasın.
        from . import mevzuat as _mevzuat
        dogrulanamayan = sorted(_mevzuat.sure_ifadeleri(hukuki))
        if dogrulanamayan:
            ornek = ", ".join(f"{n} {b}" for n, b in dogrulanamayan[:3])
            uyarilar.append(
                f"⚠️ SÜRE DOĞRULANAMADI: {ornek} — karşılaştırılacak kanun metni yok, elle teyit edin."
            )

    # --- 1c. UYDURMA İÇTİHAT ---
    # Esas/karar numarası ya da daire + yıl/sayı kalıbı: brief'te yoksa uydurulmuştur.
    ictihatlar = re.findall(
        r"(?:\bE\.\s*\d{4}/\d+|\bK\.\s*\d{4}/\d+|\d{1,2}\.\s*(?:Hukuk|Ceza)\s+Dairesi[^.,;]{0,30}\d{4}/\d+|\bHGK[^.,;]{0,30}\d{4}/\d+)",
        hukuki,
    )
    kaynaklar = " ".join(str((brief or {}).get(k) or "") for k in ("mevzuat", "mevzuat_metni", "makale_metni"))
    uydurma_ictihat = [i for i in ictihatlar if i not in kaynaklar]
    if uydurma_ictihat:
        uyarilar.append(
            f"⛔ UYDURMA İÇTİHAT OLABİLİR: \"{uydurma_ictihat[0]}\" kaynakta yok — Yargıtay karar numarası doğrulanmadan yazılmaz."
        )

    # --- 2. DAYANAKSIZ RAKAM ---
    # Oran ve tutar kaynağında (kanun metni ya da haber metni) geçmiyorsa
    # uydurulmuştur; "yalan bilgiye müsamaha yok" kararıyla (2026-09-24) bu artık
    # KRİTİK. Kaynak metin yoksa ve brief bir veri kaynağı da göstermiyorsa aynı.
    # Brief'te veri kaynağı (TÜİK, TCMB…) varsa rakam dışarıdan doğrulanamaz,
    # onaylayan kişiye uyarı olarak kalır.
    from . import mevzuat as _mevzuat_o
    haber_olcutu = bool((brief or {}).get("kaynak_metin_olcut"))
    oranlar = set() if haber_olcutu else _mevzuat_o.oran_ifadeleri(hukuki)
    tutarlar = [] if haber_olcutu else re.findall(
        r"\b\d[\d.,]*\s*(?:milyon|milyar|bin)?\s*(?:TL|lira|₺)", hukuki, re.IGNORECASE)
    if oranlar or tutarlar:
        veri_kaynagi = (brief or {}).get("veri_kaynagi")
        kaynak_sayilar = _mevzuat_o.oran_ifadeleri(kanun_metni) | sayi_esdegerleri(kanun_metni) if kanun_metni else set()
        kacak_oran = sorted(o for o in oranlar if o not in kaynak_sayilar)
        kacak_tutar = [t for t in tutarlar if not (_sayilar(t) & kaynak_sayilar)]
        kacak = [f"%{o}" for o in kacak_oran] + kacak_tutar
        if kacak and not veri_kaynagi:
            uyarilar.append(
                f"⛔ RAKAM KAYNAKTA YOK: {', '.join(kacak[:3])} geçiyor ama ne kanun metninde "
                f"ne haber kaynağında var, brief'te veri kaynağı da yok."
            )
        elif kacak:
            uyarilar.append(
                f"⚠️ DAYANAKSIZ RAKAM: {', '.join(kacak[:3])} — \"{veri_kaynagi}\" kaynağından elle teyit edin."
            )

    # --- 3. ZORLAMA YEREL BAĞ ---
    if haber_olcutu:
        # Rakam ve yerel bağ haberde kaynak metne karşı ⛔ olarak denetlenir
        uyarilar.extend(haber_kaynak_denetimi(veri, brief or {}))
    gecen_yerel = [a for a in _YEREL_ADLAR if a in kucuk]
    if gecen_yerel and brief is not None and not brief.get("yerel") and not haber_olcutu:
        uyarilar.append(
            f"⚠️ YEREL BAĞ UYDURULMUŞ OLABİLİR: metinde \"{gecen_yerel[0]}\" geçiyor "
            f"ama brief'te yerel bağ tanımlı değil."
        )

    # --- 4. MARKA SESİ ---
    if "!" in metin:
        uyarilar.append("⚠️ ÜNLEM İŞARETİ: marka sesi sakin otorite, ünlem kullanılmıyor.")
    abartilar = [a for a in _ABARTI if a in kucuk]
    if abartilar:
        uyarilar.append(f"⚠️ ABARTI DİLİ: \"{abartilar[0]}\" geçiyor.")
    bos_tavsiyeler = [b for b in _BOS_TAVSIYELER if b in kucuk]
    if bos_tavsiyeler:
        uyarilar.append(f"⚠️ BOŞ TAVSİYE (FLUFF): \"{bos_tavsiyeler[0]}\" geçiyor — genel geçer tavsiye yerine somut resmi merci, belge adı veya yasal süre belirtin.")
    for cumle in re.split(r"[.!?\n]+", metin):
        c_temiz = cumle.strip()
        if c_temiz and bos_ovgu_mu(c_temiz):
            uyarilar.append(f"⚠️ BOŞ ÖVGÜ / TÖREN DİLİ: \"{c_temiz[:50]}\" — bilgi taşımayan övgü yerine somut veri verin.")
            break

    # --- 5. İÇİ BOŞ MANŞET ---
    manset = _kucult(" ".join(str(veri.get(k) or "") for k in
                              ("manset", "manset_parca_1", "manset_vurgu", "manset_parca_2")))
    bos = [k for k in _ICI_BOS_KALIPLAR if k in manset]
    if bos:
        uyarilar.append(f"⚠️ İÇİ BOŞ MANŞET: \"{bos[0]}\" — konuyu duyuruyor ama sonucu saklıyor.")

    # --- 6. ALINTI DOĞRULAMA (instabot standardı) ---
    alinti = str(veri.get("alinti") or veri.get("alinti_metni") or "").strip()
    if alinti and len(alinti) > 10 and brief:
        kaynak_metin = str(brief.get("kaynak_metin") or brief.get("makale_metni") or brief.get("orijinal_ozet") or "").strip()
        if kaynak_metin and not alintiyi_denetle(alinti, kaynak_metin):
            uyarilar.append(f"⛔ UYDURMA ALINTI OLABİLİR: \"{alinti[:60]}...\" kaynak metinde birebir bulunamadı.")

    return uyarilar


def kritik_var(uyarilar: List[str]) -> bool:
    return any(u.startswith("⛔") for u in uyarilar)


def haberden_brief(haber: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Haber içeriği için brief: doğrulama ölçütü KAYNAK METNİN KENDİSİ.

    Konu bankası içeriğinde brief ayrı tutuluyor; haberde yoktu ve haber yolu
    madde numarası/alıntı denetiminden hiç geçmiyordu. Burada kaynak metin hem
    "doğrulanmış mevzuat" (madde numarası kaynakta geçiyor mu) hem de alıntı
    karşılaştırması için kullanılır.
    """
    if not haber:
        return None
    kaynak = " ".join(str(haber.get(k) or "") for k in ("orijinal_baslik", "orijinal_ozet", "makale_metni")).strip()
    if not kaynak:
        return None
    kucuk = _kucult(kaynak)
    return {
        "mevzuat": kaynak,
        "mevzuat_metni": kaynak,  # süre/çoğunluk ifadeleri kaynağa karşı denetlenir
        "veri_kaynagi": haber.get("kaynak") or "haber kaynağı",
        "yerel": any(a in kucuk for a in _YEREL_ADLAR),
        "makale_metni": kaynak,
        "kaynak_metin_olcut": True,
    }


def kaynak_denetle(haber: Optional[Dict[str, Any]]) -> List[str]:
    """Haber içeriğinin kaynağı gerçekten var mı.

    #170 ve #171 (2026-09-21) "İBB Şehircilik" haberi olarak yayına çıktı; kaynak
    adreslerinden biri 404, diğerinin alan adı hiç çözülmüyordu. İki cümlelik
    deneme kayıtlarıydı; ada/parsel/emsal/itiraz tarihi ayrıntılarını model uydurdu.
    EDM'nin kendi ürettiği (konu bankası, özel) içerik bu denetimden muaftır.
    """
    if not haber or str(haber.get("kaynak") or "").startswith("EDM"):
        return []
    adres = str(haber.get("orijinal_url") or "").strip()
    if not adres.startswith(("http://", "https://")):
        return ["⛔ KAYNAK YOK: haberin orijinal adresi kayıtlı değil — kaynaksız haber yayınlanmaz."]
    from . import config
    if config.test_modu():
        return []
    import requests
    try:
        r = requests.get(adres, timeout=12, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}, stream=True)
        r.close()
        if r.status_code in (404, 410):
            return [f"⛔ KAYNAK YOK: {adres[:80]} → HTTP {r.status_code}. Böyle bir haber sayfası yok."]
        if r.status_code >= 400:
            # Haber siteleri botları sık sık 403/429 ile geri çeviriyor (Emlakkulisi gibi):
            # sayfa var ama doğrulanamadı — insan teyidi ister, yayını kilitlemez.
            return [f"⚠️ KAYNAK ERİŞİME KAPALI: {adres[:80]} → HTTP {r.status_code}. Haberi kaynağından elle teyit edin."]
    except (requests.ConnectionError, requests.Timeout) as e:
        return [f"⛔ KAYNAK AÇILMIYOR: {adres[:80]} ({type(e).__name__}) — alan adı çözülmüyor ya da yanıt yok."]
    except requests.RequestException as e:
        return [f"⚠️ KAYNAK DENETLENEMEDİ: {adres[:80]} ({type(e).__name__})."]
    return []


def _haber_mi(haber: Optional[Dict[str, Any]]) -> bool:
    return bool(haber) and not str(haber.get("kaynak") or "").startswith("EDM")


def _birlesik_brief(veri: Dict[str, Any], haber: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Haberden üretilmiş içerikte ölçüt İKİ kaynaktır: haber metni ve (varsa)
    triyajın bulduğu kanun maddesinin güncel metni.

    Önceden içerik brief'i (triyaj) varsa haber metni hiç kullanılmıyordu: haberde
    "30 gün askı" yazıyor, içerik "15 gün" diyor — süre kanun atfına karşı
    denetleniyordu, haberin kendisine değil.
    """
    brief = veri.get("_brief")
    haber_brief = haberden_brief(haber) if _haber_mi(haber) else None
    if not brief:
        return haber_brief
    if not haber_brief:
        return brief
    birlesik = dict(brief)
    birlesik["mevzuat"] = f"{brief.get('mevzuat') or ''} {haber_brief['mevzuat']}".strip()
    birlesik["mevzuat_metni"] = f"{haber_brief['mevzuat_metni']}\n{_kanun_metni(brief)}".strip()
    birlesik["makale_metni"] = haber_brief["makale_metni"]
    birlesik["veri_kaynagi"] = brief.get("veri_kaynagi") or haber_brief["veri_kaynagi"]
    birlesik["yerel"] = brief.get("yerel") or haber_brief["yerel"]
    birlesik["kaynak_metin_olcut"] = True
    return birlesik


def icerigi_denetle(veri: Dict[str, Any], haber: Optional[Dict[str, Any]] = None,
                    anlam: bool = True) -> List[str]:
    """Tüm yolların ortak girişi: brief içerikte yoksa haberin kaynak metninden kurulur.

    `anlam=True`: ⛔ bulgu yoksa ikinci bir model içeriği kaynakla karşılaştırır (anlam kayması,
    yalnız ⚠️). ⛔ varken sorulmaz: içerik zaten durduruluyor. Yayın anındaki kapı (`anlam=False`)
    uyarıları kullanmadığı için modeli boşuna çağırmaz."""
    brief = _birlesik_brief(veri, haber)
    uyarilar = kaynak_denetle(haber) + denetle(veri, brief)
    if anlam and not kritik_var(uyarilar):
        uyarilar += _anlam_denetimi(veri, brief)
    return uyarilar


def _anlam_denetimi(veri: Dict[str, Any], brief: Optional[Dict[str, Any]]) -> List[str]:
    """Kaynak (haber metni ya da madde metni) varsa anlam kayması hakemi; her hatada [] (fail-open)."""
    try:
        from . import capraz_denetim
        return capraz_denetim.denetle(veri, _kanun_metni(brief))
    except Exception as e:  # noqa: BLE001 — hakem yüzünden kapı kırılmaz
        log.warning("Anlam denetimi atlandı: %s", e)
        return []


def yayin_engeli_metni(haber_id: Any, uyarilar: List[str]) -> str:
    """Kritik bulgu varsa içerik onaya bile sunulmaz; gruba giden açıklama.

    2026-09-24 kararı: yalan bilgiye müsamaha yok. Önceden kritik uyarı onay
    mesajının başına yazılıp içerik yine de "Yayınla" butonuyla sunuluyordu;
    #142 ve #68 bu uyarı sistemi olmadan, #170 uyarı çıksa bile yayınlanabilirdi.
    """
    kritikler = [u for u in uyarilar if u.startswith("⛔")]
    return (
        f"🛑 <b>İçerik #{haber_id} durduruldu — yayına sunulmadı.</b>\n\n"
        + "\n".join(kritikler[:5])
        + "\n\n<i>Kaynakta olmayan bilgi yayınlanmıyor. Konu kilitlendi; "
          "aşağıdaki düğmeyle sıradaki konudan yeni içerik üretebilirsin.</i>"
    )


def uyari_basligi(uyarilar: List[str]) -> str:
    """Uyarıları Telegram önizlemesinin başına konacak bloğa çevirir."""
    if not uyarilar:
        return "✅ <b>Denetim temiz</b>\n\n"
    kritik = sum(1 for u in uyarilar if u.startswith("⛔"))
    basligi = f"⛔ <b>{kritik} KRİTİK UYARI</b>" if kritik else f"⚠️ <b>{len(uyarilar)} uyarı</b>"
    return basligi + "\n" + "\n".join(uyarilar) + "\n\n"
