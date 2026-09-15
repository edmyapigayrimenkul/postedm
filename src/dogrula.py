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
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# Türkçe'ye özel küçültme: I→ı, İ→i. Python'un varsayılan lower()'ı
# "İ" için noktalı i (U+0069 U+0307) üretiyor ve eşleşmeyi bozuyor.
_KUCUK = str.maketrans("IİÇĞÖŞÜ", "içğöşü".rjust(7, "ı")[:7])


def _kucult(metin: str) -> str:
    return metin.replace("I", "ı").replace("İ", "i").lower()


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
            kacak = [m for m in set(maddeler)
                     if not any(p in dogrulanmis for p in re.findall(r"\d+(?:/\d+)?", m))]
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

    # --- 6. HUKUKİ İÇERİKTE SORUMLULUK NOTU ---
    kategori = str(veri.get("kategori_kodu") or "")
    if kategori in ("TAPU_VE_HUKUK", "EV_SAHIBI_VE_KIRACI", "ARSA_IMAR_VE_TINY_HOUSE"):
        if "avukat" not in kucuk and "hukuki görüş" not in kucuk:
            uyarilar.append(
                "ℹ️ Hukuk içerikli kategori; kapanışta sorumluluk notu görünmüyor."
            )

    return uyarilar


def uyari_basligi(uyarilar: List[str]) -> str:
    """Uyarıları Telegram önizlemesinin başına konacak bloğa çevirir."""
    if not uyarilar:
        return "✅ <b>Denetim temiz</b>\n\n"
    kritik = sum(1 for u in uyarilar if u.startswith("⛔"))
    basligi = f"⛔ <b>{kritik} KRİTİK UYARI</b>" if kritik else f"⚠️ <b>{len(uyarilar)} uyarı</b>"
    return basligi + "\n" + "\n".join(uyarilar) + "\n\n"
