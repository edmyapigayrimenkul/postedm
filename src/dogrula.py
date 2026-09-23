"""
dogrula.py — Yayın Öncesi İçerik Denetimi

Onay mesajı gönderilmeden ÖNCE çalışır ve uyarıları mesajın başına koyar.
Otomatik eleme YAPMAZ — insan onayı son söz olarak kalır. Amaç onaylayan
kişiye "şuna bir daha bak" demek.

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
"geçersizdir" aynı maddeyi ve aynı kelimeleri taşır. Bunu yakalayan tek
şey insan onayıdır.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional, Set

from . import filtre

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
]

# Yakın bölge adları — brief'te yerel bağ yokken metinde geçiyorsa uydurma olabilir
_YEREL_ADLAR = ["silivri", "trakya", "çatalca", "çorlu", "çerkezköy",
                "tekirdağ", "edirne", "kırklareli", "selimpaşa", "alibey"]


def _tum_metin(veri: Dict[str, Any]) -> str:
    """Görselde çizilen tüm metinleri tek dizede toplar (caption hariç)."""
    parcalar: List[str] = []

    def topla(d: Any) -> None:
        if isinstance(d, dict):
            for k, v in d.items():
                if k.startswith("_") or k.startswith("caption"):
                    continue
                topla(v)
        elif isinstance(d, list):
            for v in d:
                topla(v)
        elif isinstance(d, str):
            parcalar.append(d)

    topla(veri)
    return " ".join(parcalar)


def _maddeleri_bul(metin: str) -> List[str]:
    bulunan: List[str] = []
    for desen in _MADDE_DESENLERI:
        bulunan.extend(m.group(0).strip() for m in desen.finditer(metin))
    return bulunan


def denetle(veri: Dict[str, Any], brief: Optional[Dict[str, Any]] = None) -> List[str]:
    """İçeriği denetler ve uyarı listesi döner. Boş liste = temiz.

    `brief` verilirse mevzuat ve yerel bağ iddiaları onunla karşılaştırılır.
    """
    uyarilar: List[str] = []
    metin = _tum_metin(veri)
    kucuk = _kucult(metin)

    # --- 1. UYDURMA MEVZUAT (en kritik) ---
    maddeler = _maddeleri_bul(metin)
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

    # --- 2. DAYANAKSIZ RAKAM ---
    oranlar = re.findall(r"%\s?\d+|\byüzde\s+\d+", metin)
    tutarlar = re.findall(r"\b\d[\d.]*\s*(?:milyon|bin)\s*(?:TL|lira)", metin, re.IGNORECASE)
    if (oranlar or tutarlar) and not (brief or {}).get("veri_kaynagi"):
        ornek = (oranlar + tutarlar)[:3]
        uyarilar.append(
            f"⚠️ DAYANAKSIZ RAKAM: {', '.join(ornek)} geçiyor ama brief'te veri kaynağı yok."
        )

    # --- 3. ZORLAMA YEREL BAĞ ---
    gecen_yerel = [a for a in _YEREL_ADLAR if a in kucuk]
    if gecen_yerel and brief is not None and not brief.get("yerel"):
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
        "veri_kaynagi": haber.get("kaynak") or "haber kaynağı",
        "yerel": any(a in kucuk for a in _YEREL_ADLAR),
        "makale_metni": kaynak,
    }


def icerigi_denetle(veri: Dict[str, Any], haber: Optional[Dict[str, Any]] = None) -> List[str]:
    """Tüm yolların ortak girişi: brief içerikte yoksa haberin kaynak metninden kurulur."""
    return denetle(veri, veri.get("_brief") or haberden_brief(haber))


def uyari_basligi(uyarilar: List[str]) -> str:
    """Uyarıları Telegram önizlemesinin başına konacak bloğa çevirir."""
    if not uyarilar:
        return "✅ <b>Denetim temiz</b>\n\n"
    kritik = sum(1 for u in uyarilar if u.startswith("⛔"))
    basligi = f"⛔ <b>{kritik} KRİTİK UYARI</b>" if kritik else f"⚠️ <b>{len(uyarilar)} uyarı</b>"
    return basligi + "\n" + "\n".join(uyarilar) + "\n\n"
