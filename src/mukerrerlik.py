"""
src/mukerrerlik.py — Hukuki Madde ve Semantik Mükerrerlik Kalkanı.

Bu modül, aynı hukuki konunun, kanun maddesinin veya semantik açıdan eşdeğer bir içeriğin
farklı başlıklarla kısa süre içinde (45-60 gün) tekrar yayınlanmasını engeller.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from . import db

log = logging.getLogger(__name__)

STOP_WORDS = {
    "ve", "veya", "ile", "için", "bir", "bu", "şu", "o", "da", "de", "ise", "gibi",
    "kadar", "olan", "olarak", "nasıl", "neden", "ne", "zaman", "mi", "mı", "mu", "mü",
    "dair", "hakkında", "tüm", "her", "en", "çok", "daha", "ancak", "çünkü", "göre",
    "madde", "md", "sayılı", "kanun", "kanunu", "kanununun", "yönelik", "üzerine",
}

KANUN_KODLARI = [
    (r"(?:türk medeni kanun|tmk|medeni kanun)", "TMK"),
    (r"(?:türk borçlar kanun|tbk|borçlar kanun)", "TBK"),
    (r"(?:kat mülkiyeti kanun|kmk|kat mülkiyeti)", "KMK"),
    (r"(?:imar kanun|imar|3194)", "IMAR"),
    (r"(?:tapu kanun|tapu|2644)", "TK"),
    (r"(?:kadastro kanun|kadastro|3402)", "KK"),
    (r"(?:toprak koruma|5403)", "5403"),
    (r"(?:afet riski|kentsel dönüşüm|6306)", "6306"),
    (r"(?:harçlar kanun|harçlar|492)", "HARC"),
    (r"(?:emlak vergisi|1319)", "EMLAK"),
    (r"(?:veraset ve intikal|7338)", "VIV"),
    (r"(?:tüketicinin korunması|6502)", "TKHK"),
    (r"(?:turizm amaçlı kiralan|7464)", "7464"),
]


def mevzuat_maddeleri_cikar(mevzuat_metni: Optional[str]) -> List[str]:
    """Mevzuat metninden kanun ve normalize edilmiş madde anahtarlarını üretir.
    Örn: 'Türk Medeni Kanunu md. 732-734' -> ['TMK:732', 'TMK:733', 'TMK:734']
    """
    if not mevzuat_metni:
        return []
    metin = str(mevzuat_metni).strip().replace("İ", "i").replace("I", "ı").lower()
    sonuclar: List[str] = []

    # Kanun adını tespit et
    kanun_kodu = "GENEL"
    for kalip, kod in KANUN_KODLARI:
        if re.search(kalip, metin):
            kanun_kodu = kod
            break

    # Maddeleri ayıkla
    madde_kismi = re.search(r"(?:md\.?|madde(?:si)?)\s*([\d\s,/veya\-–a-z]+)", metin)
    if not madde_kismi:
        return [f"{kanun_kodu}:GENEL"] if kanun_kodu != "GENEL" else []

    ham_maddeler = madde_kismi.group(1)
    # Aralıkları aç: 732-734 -> 732, 733, 734
    aralik = re.search(r"(\d+)\s*[-–]\s*(\d+)", ham_maddeler)
    if aralik:
        bas = int(aralik.group(1))
        son = int(aralik.group(2))
        if son >= bas and (son - bas) <= 10:
            for m in range(bas, son + 1):
                sonuclar.append(f"{kanun_kodu}:{m}")

    # Tekil maddeleri bul
    for parca in re.findall(r"\b(\d+(?:/[a-z0-9]+)?)\b", ham_maddeler):
        anahtar = f"{kanun_kodu}:{parca.upper()}"
        if anahtar not in sonuclar:
            sonuclar.append(anahtar)

    return sonuclar or ([f"{kanun_kodu}:GENEL"] if kanun_kodu != "GENEL" else [])


def _kelimeleri_ayikla(metin: str) -> Set[str]:
    """Metni temizler, küçük harfe çevirir ve stop-words ayıklar."""
    if not metin:
        return set()
    temiz = re.sub(r"[^\w\s]", " ", str(metin).replace("İ", "i").replace("I", "ı").lower())
    kelimeler = set(temiz.split())
    return {k for k in kelimeler if len(k) > 2 and k not in STOP_WORDS}


def _ngrams(kelimeler: List[str], n: int = 2) -> Set[str]:
    """Kelime n-gram kümesi oluşturur."""
    if len(kelimeler) < n:
        return set(kelimeler)
    return {" ".join(kelimeler[i:i + n]) for i in range(len(kelimeler) - n + 1)}


def metin_jaccard_benzerlik(metin1: str, metin2: str) -> float:
    """İki metin arasındaki kelime ve 2-gram Jaccard benzerliğini (0.0-1.0) hesaplar."""
    k1 = _kelimeleri_ayikla(metin1)
    k2 = _kelimeleri_ayikla(metin2)
    if not k1 or not k2:
        return 0.0

    # 1-gram Jaccard
    k_kesisim = len(k1 & k2)
    k_birlesim = len(k1 | k2)
    skor_1g = k_kesisim / max(1, k_birlesim)

    # 2-gram Jaccard (bağlam sırası için)
    liste1 = [w for w in re.sub(r"[^\w\s]", " ", metin1.replace("İ", "i").replace("I", "ı").lower()).split() if w not in STOP_WORDS]
    liste2 = [w for w in re.sub(r"[^\w\s]", " ", metin2.replace("İ", "i").replace("I", "ı").lower()).split() if w not in STOP_WORDS]
    ng1 = _ngrams(liste1, 2)
    ng2 = _ngrams(liste2, 2)
    skor_2g = len(ng1 & ng2) / max(1, len(ng1 | ng2)) if (ng1 and ng2) else 0.0

    # Başlıklar genelde kısa olduğu için kelime kesişimi (1-gram) esastır: %80 1g, %20 2g
    return round((0.80 * skor_1g) + (0.20 * skor_2g), 3)


def son_kullanilan_mevzuatlar(gun_sayisi: int = 45) -> Set[str]:
    """Son gun_sayisi gün içinde yayınlanan/üretilen konuların mevzuat maddelerini döner."""
    aktif_maddeler: Set[str] = set()
    try:
        from . import konu_bankasi
        havuz = {k["kod"]: k for k in konu_bankasi.havuzu_yukle()}
        esik = (datetime.now(timezone.utc) - timedelta(days=gun_sayisi)).isoformat()
        with db._baglanti_al() as conn:
            satirlar = conn.execute(
                """SELECT DISTINCT konu_kodu FROM konu_gecmisi
                   WHERE kullanim_tarihi >= ? AND COALESCE(sonuc, 'uretildi') NOT IN ('hata', 'cope_at', 'engellendi')""",
                (esik,),
            ).fetchall()
        for s in satirlar:
            konu = havuz.get(s["konu_kodu"])
            if konu and konu.get("mevzuat"):
                for m in mevzuat_maddeleri_cikar(konu["mevzuat"]):
                    aktif_maddeler.add(m)
    except Exception as e:
        log.warning("Son mevzuat maddeleri okunamadı: %s", e)
    return aktif_maddeler


def son_kullanilan_konulari_getir(gun_sayisi: int = 45) -> List[Dict[str, Any]]:
    """Son gun_sayisi içinde kullanılmış konu kayıtlarını getirir."""
    konular: List[Dict[str, Any]] = []
    try:
        from . import konu_bankasi
        havuz = {k["kod"]: k for k in konu_bankasi.havuzu_yukle()}
        esik = (datetime.now(timezone.utc) - timedelta(days=gun_sayisi)).isoformat()
        with db._baglanti_al() as conn:
            satirlar = conn.execute(
                """SELECT DISTINCT konu_kodu FROM konu_gecmisi
                   WHERE kullanim_tarihi >= ? AND COALESCE(sonuc, 'uretildi') NOT IN ('hata', 'cope_at', 'engellendi')""",
                (esik,),
            ).fetchall()
        for s in satirlar:
            if s["konu_kodu"] in havuz:
                konular.append(havuz[s["konu_kodu"]])
    except Exception as e:
        log.warning("Son kullanılan konular okunamadı: %s", e)
    return konular


def konu_mukerrer_mi(
    aday_konu: Dict[str, Any],
    son_konular: Optional[List[Dict[str, Any]]] = None,
    aktif_maddeler: Optional[Set[str]] = None,
    semantik_esik: float = 0.60,
) -> Tuple[bool, str]:
    """Aday konunun son günlerdeki yayınlarla kanun maddesi veya semantik başlık
    açısından çakışıp çakışmadığını denetler.
    Dönüş: (mukerrer_mi, gerekce)
    """
    if son_konular is None:
        son_konular = son_kullanilan_konulari_getir(45)
    if aktif_maddeler is None:
        aktif_maddeler = son_kullanilan_mevzuatlar(45)

    # 1. Mevzuat Maddesi Çakışması Kontrolü
    aday_maddeler = mevzuat_maddeleri_cikar(aday_konu.get("mevzuat"))
    for m in aday_maddeler:
        if m in aktif_maddeler and not m.endswith(":GENEL"):
            return True, f"Mevzuat çakışması: {m} son 45 günde zaten işlendi"

    # 2. Semantik Başlık ve Açı Benzerliği Kontrolü
    aday_baslik = aday_konu.get("baslik") or ""
    aday_aci = aday_konu.get("aci") or ""

    for eski in son_konular:
        if eski.get("kod") == aday_konu.get("kod"):
            continue
        eski_baslik = eski.get("baslik") or ""
        b_skor = metin_jaccard_benzerlik(aday_baslik, eski_baslik)
        if b_skor >= semantik_esik:
            return True, f"Başlık semantik çakışması (%{int(b_skor*100)}): '{eski_baslik}'"

        # Açı benzerliği (daha yüksek eşik: 0.75)
        eski_aci = eski.get("aci") or ""
        a_skor = metin_jaccard_benzerlik(aday_aci, eski_aci)
        if a_skor >= 0.75:
            return True, f"Açı semantik çakışması (%{int(a_skor*100)}): '{eski.get('kod')}'"

    return False, ""
