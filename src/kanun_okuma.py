"""
kanun_okuma.py — Kanun metnini OKUMA araçlarının kitaplığı (CLI: scripts/kanun_oku.py).

NİYE (2026-10-12): sözlük kartlarını yazan alt ajanlar (SOZLUK-KART-URETIMI.md) kanun metnini kendi
hafızalarından değil, bu araçla okuyup yazmalı: model eğitim bilgisiyle yazınca TMK 733–734'ün
24/12/2025'te değiştiğini bilmiyor (bkz. mevzuat.py başlığı). Bu modül ağ ve önbellek işini
`mevzuat.kanun_metni` ile yapar; burada yalnızca metni maddelere bölme, atıftaki maddeleri TAM okuma
(aralık sınırı yok) ve kelime arama vardır.

Her işlev saftır (metin alır, metin döner) ve ağa kendisi çıkmaz; testler sahte kanun metniyle çalışır.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from . import filtre, mevzuat

# "MADDE 683 -", "GEÇİCİ MADDE 2 -" ve "Ek Madde 6 -". Kanun metni düz yazıya çevrildiğinde başlıklar satır içinde kalır.
# Ek maddeler normal maddeyle AYNI numarayı taşır (3402'de Madde 6 ve Ek Madde 6): ayrı tür olarak izlenmezse arama
# sonuçları "md. 6" diye yanlış etiketlenir ve ek maddeye atıf yapılamaz (2026-10-13 pilotunda bir inceleme ajanı yakaladı).
_BASLIK = re.compile(
    r"(?<![A-Za-zÇĞİÖŞÜçğıöşü])(?P<tur>GE[ÇC][İI]C[İI]\s+|Ge[çc]ici\s+|EK\s+|Ek\s+)?(?:MADDE|Madde)\s*(?P<no>\d+)\s*[-–]"
)

BAGLAM_VARSAYILAN = 90
ARAMA_AZAMI_SONUC = 20


def madde_etiketi(gecici: bool, no: str, ek: bool = False) -> str:
    if ek:
        return f"ek md. {no}"
    return f"geçici md. {no}" if gecici else f"md. {no}"


def anahtar_etiketi(anahtar: str) -> str:
    """mevzuat.atiflari_coz anahtarından ('733', 'geçici 2', 'ek 6') okunur etiket."""
    no = anahtar.split()[-1]
    return madde_etiketi(anahtar.startswith("geçici"), no, ek=anahtar.startswith("ek"))


def maddelere_bol(metin: str) -> List[Dict[str, Any]]:
    """Kanun metnini maddelere böler: [{etiket, gecici, ek, no, bas, govde_bas, bit}]. `bas` başlığın başlangıcı,
    `bit` bir sonraki madde başlığının başlangıcıdır (son maddede metin sonu)."""
    basliklar = list(_BASLIK.finditer(metin or ""))
    sonuc: List[Dict[str, Any]] = []
    for i, m in enumerate(basliklar):
        tur = (m.group("tur") or "").strip().lower()
        gecici = tur.startswith("ge")
        ek = tur == "ek"
        bit = basliklar[i + 1].start() if i + 1 < len(basliklar) else len(metin)
        sonuc.append({
            "etiket": madde_etiketi(gecici, m.group("no"), ek=ek),
            "gecici": gecici,
            "ek": ek,
            "no": m.group("no"),
            "bas": m.start(),
            "govde_bas": m.end(),
            "bit": bit,
        })
    return sonuc


def _madde_bul(maddeler: List[Dict[str, Any]], madde: str) -> Optional[Dict[str, Any]]:
    """`madde`: '733', 'geçici 2' ya da 'ek 6' (mevzuat.atiflari_coz anahtarları)."""
    gecici = madde.startswith("geçici")
    ek = madde.startswith("ek")
    no = madde.split()[-1]
    for m in maddeler:
        if m["gecici"] == gecici and m.get("ek", False) == ek and m["no"] == no:
            return m
    return None


def sonraki_baslik(metin: str, maddeler: List[Dict[str, Any]], madde: Dict[str, Any], uzunluk: int = 70) -> str:
    """Okunan maddeden hemen SONRA gelen maddenin başlığı ve ilk sözcükleri. Madde metni burada biter; yazar
    sonraki maddenin cümlesini bu maddeye ait sanmasın diye okuma çıktısında ayrıca işaretlenir."""
    sira = maddeler.index(madde)
    if sira + 1 >= len(maddeler):
        return "(kanunun son maddesi)"
    s = maddeler[sira + 1]
    return " ".join(metin[s["bas"]:s["bas"] + uzunluk].split()) + " …"


def maddeleri_oku(atif: str, *, aralik_azami: int = 10_000,
                  kanun_metni=None) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Atıftaki maddelerin TAM metni (aralıkta üst sınır yok). Döner: (okunanlar, bulunamayanlar).

    okunan = {kanun_no, kanun_adi, etiket, metin, sonraki, degisiklikler(ISO tarih listesi)}.
    `kanun_metni`: test için enjekte edilir; varsayılan (çağrı anında çözülür) önbellekli, ağa çıkan gerçek işlevdir."""
    kanun_metni = kanun_metni or mevzuat.kanun_metni
    atiflar, cozulemeyen = mevzuat.atiflari_coz(atif, aralik_azami=aralik_azami)
    okunan: List[Dict[str, Any]] = []
    bulunamayan: List[str] = list(cozulemeyen)
    for no, maddeler_anahtar in atiflar:
        ad = mevzuat.KANUNLAR.get(no, ((), str(no)))[1]
        metin = kanun_metni(no)
        if not metin:
            bulunamayan.append(f"{no} sayılı {ad}: kanun metni alınamadı")
            continue
        bolunmus = maddelere_bol(metin)
        for anahtar in maddeler_anahtar:
            m = _madde_bul(bolunmus, anahtar)
            if not m:
                bulunamayan.append(f"{no} sayılı {ad} {anahtar_etiketi(anahtar)}")
                continue
            govde = metin[m["bas"]:m["bit"]].strip()
            okunan.append({
                "kanun_no": no,
                "kanun_adi": ad,
                "etiket": m["etiket"],
                "metin": govde,
                "sonraki": sonraki_baslik(metin, bolunmus, m),
                "degisiklikler": [t.isoformat() for t in mevzuat.degisiklik_tarihleri(govde)],
            })
    return okunan, bulunamayan


def ara(no: int, kelimeler: List[str], *, baglam: int = BAGLAM_VARSAYILAN, azami: int = ARAMA_AZAMI_SONUC,
        kanun_metni=None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Kanundaki kelime/ifade geçişleri: [{kelime, sonuclar:[{etiket, parca}], toplam}]. Türkçe İ/I duyarlı,
    büyük/küçük harf ayırmaz. Her geçiş, içinde bulunduğu maddenin etiketiyle verilir (madde no + bağlam).
    Döner: (sonuçlar, hata). `hata`: kanun metni alınamadıysa nedeni."""
    metin = (kanun_metni or mevzuat.kanun_metni)(no)
    if not metin:
        return [], f"{no} sayılı kanunun metni alınamadı"
    maddeler = maddelere_bol(metin)
    kucuk = filtre.kucult(metin)
    if len(kucuk) != len(metin):  # küçültme uzunluğu değiştirirse konumlar kayar; güvenli yol
        kucuk = metin.lower()
    sonuc: List[Dict[str, Any]] = []
    for kelime in kelimeler:
        aranan = filtre.kucult(kelime.strip())
        if not aranan:
            continue
        bulunanlar: List[Dict[str, str]] = []
        toplam = 0
        for eslesme in re.finditer(re.escape(aranan), kucuk):
            toplam += 1
            if len(bulunanlar) >= azami:
                continue
            etiket = "(madde başlığından önce)"
            for m in maddeler:
                if m["bas"] <= eslesme.start():
                    etiket = m["etiket"]
                else:
                    break
            bas = max(0, eslesme.start() - baglam)
            bit = min(len(metin), eslesme.end() + baglam)
            parca = " ".join(metin[bas:bit].split())
            bulunanlar.append({"etiket": etiket, "parca": ("…" if bas else "") + parca + ("…" if bit < len(metin) else "")})
        sonuc.append({"kelime": kelime, "sonuclar": bulunanlar, "toplam": toplam})
    return sonuc, None


def kanun_listesi() -> List[Dict[str, Any]]:
    """Okunabilir kanunlar: [{no, ad, tertipler, onbellekte}]. `onbellekte`: metin yerelde var (ağ gerekmez)."""
    sonuc = []
    for no, (tertipler, ad) in sorted(mevzuat.KANUNLAR.items()):
        sonuc.append({
            "no": no,
            "ad": ad,
            "tertipler": list(tertipler),
            "onbellekte": (mevzuat.ONBELLEK / f"{no}.txt").exists(),
        })
    return sonuc
