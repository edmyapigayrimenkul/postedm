"""
haber_alanlari.py — Haber içeriğinin alanları: iki şema yan yana okunur.

2026-10-07 kararı: haber içeriği Instabot'la aynı şemayla üretilir. Yeni alanlar:
`manset` (başlık), `spot` (özet), `detay_yazisi` (4-5 paragraf), `kanca`, `vurgu_sayi`,
`vurgu_etiket`, `alinti`, `alinti_sahibi`, `neden_onemli`, `sana_etkisi`, `sirada_ne_var`,
`ulke_kodu`, `ulke_adi`. Başlık ve özet anahtarları (`manset`, `spot`) bilerek korundu:
veritabanı, Telegram, LinkedIn, site ve seslendirme hep bunları okuyor.

Eski B5 kayıtları (`detay_maddeleri`, `uzman_notu`) onay bekleyen kuyrukta ve geçmişte
duruyor; onlar da okunabilir kalır. Bu modül iki şemanın tek okuma noktasıdır: tüketici
(çizici, denetim, LinkedIn, site, video, kanca) şemayı bilmek zorunda değildir.

Bu modül resim/ağ/model kullanmaz; her yerden içe aktarılabilir.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# `**kalın**` vurgusunun korunduğu alanlar (Instabot: detay_metni, slayt_ozet).
# Diğer her alanda markdown işareti temizlenir: caption düz metindir, başlıkta kalın yok.
KALIN_ALANLAR = ("detay_yazisi", "spot")

# Eski şemanın alanları: yeni içerikte üretilmez ama eski kayıtta okunur.
ESKI_ALANLAR = ("detay_maddeleri", "uzman_notu")

# Gövdede yer alan (modelin yazdığı) tek satırlık alanlar
TEK_SATIR_ALANLARI = ("manset", "spot", "kanca", "vurgu_sayi", "vurgu_etiket", "alinti", "alinti_sahibi",
                      "neden_onemli", "sana_etkisi", "sirada_ne_var")


def kalin_sil(metin: Any) -> str:
    """`**vurgu**` işaretlerini kaldırır (yalnız metni döner)."""
    return str(metin or "").replace("**", "")


def _bosluk_duzelt(metin: str) -> str:
    return " ".join(metin.split())


def detay_paragraflari(veri: Dict[str, Any], kalin: bool = True) -> List[str]:
    """Detay metni, paragraf listesi olarak.

    `detay_yazisi` varsa boş satırlarla ayrılmış paragraflarıdır; yoksa eski şemanın
    madde metinleri sırayla paragraf sayılır (etiketler çizilmez, Instabot'ta yok).
    `kalin=False`: `**` işaretleri atılır (denetim ve düz metin tüketicileri için).
    """
    yazi = veri.get("detay_yazisi")
    paragraflar: List[str] = []
    if isinstance(yazi, str) and yazi.strip():
        for p in re.split(r"\n\s*\n|\n", yazi.strip()):
            p = _bosluk_duzelt(p)
            if p:
                paragraflar.append(p)
    else:
        for m in veri.get("detay_maddeleri") or []:
            metin = m.get("metin") if isinstance(m, dict) else m
            if isinstance(metin, str) and metin.strip():
                paragraflar.append(_bosluk_duzelt(metin))
    return paragraflar if kalin else [kalin_sil(p) for p in paragraflar]


def kelime_sayisi(metin: Any) -> int:
    return len(kalin_sil(metin).split())


def vurgu(veri: Dict[str, Any]) -> Tuple[str, str]:
    """(sayı, etiket); yoksa ("", "")."""
    sayi = _bosluk_duzelt(kalin_sil(veri.get("vurgu_sayi")))
    if not sayi:
        return "", ""
    return sayi, _bosluk_duzelt(kalin_sil(veri.get("vurgu_etiket")))


def alinti(veri: Dict[str, Any]) -> Tuple[str, str]:
    """(söz, sahibi); yoksa ("", "")."""
    soz = _bosluk_duzelt(kalin_sil(veri.get("alinti"))).strip('"“”')
    if not soz:
        return "", ""
    return soz, _bosluk_duzelt(kalin_sil(veri.get("alinti_sahibi")))


def sana_etkisi(veri: Dict[str, Any]) -> str:
    """Okuyucuya etkisi. Eski şemada karşılığı "EDM uzman notu"ydu."""
    for ad in ("sana_etkisi", "uzman_notu"):
        d = veri.get(ad)
        if isinstance(d, str) and d.strip():
            return _bosluk_duzelt(kalin_sil(d))
    return ""


def duz_metin(veri: Dict[str, Any]) -> str:
    """Haberin görselde okunan bütün metni, `**` işaretsiz ve tek dizede
    (LinkedIn/site/video süresi gibi düz metin tüketicileri için)."""
    parcalar = [kalin_sil(veri.get(a)) for a in ("manset", "spot", "vurgu_etiket", "neden_onemli",
                                                  "sana_etkisi", "sirada_ne_var")]
    parcalar.extend(detay_paragraflari(veri, kalin=False))
    soz, sahibi = alinti(veri)
    if soz:
        parcalar.append(soz)
    if not veri.get("sana_etkisi") and veri.get("uzman_notu"):
        parcalar.append(kalin_sil(veri.get("uzman_notu")))
    return "\n".join(p for p in parcalar if p and p.strip())
