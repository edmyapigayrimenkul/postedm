"""
src/cizim/normalize.py — Model Verisini Çizim Katmanına Uyarlama / Normalizasyon
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from .fikir import _adim_numarasi

log = logging.getLogger(__name__)

_METIN_ALANLARI = (
    "id", "manset", "baslik", "manset_parca_1", "manset_vurgu",
    "manset_parca_2", "spot", "soru", "kategori_kodu", "bicim", "kaynak",
    "gorsel_url", "foto_url", "caption_instagram", "caption_facebook", "caption_threads",
)


def _metin(deger: Any) -> str:
    """Herhangi bir değeri güvenli bir metne çevirir."""
    if deger is None:
        return ""
    if isinstance(deger, str):
        return deger
    if isinstance(deger, bool):
        return ""
    if isinstance(deger, (int, float)):
        return str(deger)
    if isinstance(deger, (list, tuple)):
        return " ".join(_metin(x) for x in deger if not isinstance(x, (dict, list, tuple))).strip()
    return ""


def _sozluk(deger: Any) -> Dict[str, Any]:
    return deger if isinstance(deger, dict) else {}


def _kart_normalize(ham: Any) -> Dict[str, Any]:
    k = _sozluk(ham)
    return {
        "etiket": _metin(k.get("etiket")),
        "renk": _metin(k.get("renk")) or "kirmizi",
        "baslik": _metin(k.get("baslik")),
        "aciklama": _metin(k.get("aciklama")),
    }


def veriyi_normalize_et(ham: Any) -> Dict[str, Any]:
    """Model çıktısını çizim katmanının beklediği şekle sokar."""
    v = _sozluk(ham)
    veri: Dict[str, Any] = {a: _metin(v.get(a)) for a in _METIN_ALANLARI}

    onem = v.get("onem_puani")
    veri["onem_puani"] = onem if isinstance(onem, (int, float)) and not isinstance(onem, bool) else 8

    detay = _sozluk(v.get("slayt_2_detay"))
    ham_kartlar = detay.get("kartlar")
    kartlar = []
    if isinstance(ham_kartlar, (list, tuple)):
        for k in ham_kartlar:
            kn = _kart_normalize(k)
            if kn.get("baslik"):
                kartlar.append(kn)

    k1 = _kart_normalize(detay.get("kart_1"))
    k2 = _kart_normalize(detay.get("kart_2"))

    if not kartlar:
        for k in (k1, k2):
            if k.get("baslik"):
                kartlar.append(k)

    if not k1.get("baslik") and len(kartlar) >= 1:
        k1 = kartlar[0]
    if not k2.get("baslik") and len(kartlar) >= 2:
        k2 = kartlar[1]

    veri["slayt_2_detay"] = {
        "baslik_satir_1": _metin(detay.get("baslik_satir_1")),
        "baslik_vurgu": _metin(detay.get("baslik_vurgu")),
        "kart_1": k1,
        "kart_2": k2,
        "kartlar": kartlar,
    }

    cozum = _sozluk(v.get("slayt_3_cozum"))
    ham_maddeler = cozum.get("maddeler")
    maddeler = []
    if isinstance(ham_maddeler, (list, tuple)):
        for i, m in enumerate(ham_maddeler, start=1):
            md = _sozluk(m)
            baslik = _metin(md.get("baslik"))
            if not baslik:
                continue
            maddeler.append({
                "no": _adim_numarasi(md.get("no") if md.get("no") not in (None, "") else i),
                "baslik": baslik,
                "aciklama": _metin(md.get("aciklama")),
            })

    def _kolon(ham_kolon: Any) -> List[Tuple[str, str]]:
        if not isinstance(ham_kolon, (list, tuple)):
            return []
        cikti = []
        for satir in ham_kolon:
            if isinstance(satir, (list, tuple)) and len(satir) >= 2:
                cikti.append((_metin(satir[0]), _metin(satir[1])))
            elif isinstance(satir, dict):
                anahtarlar = list(satir.items())
                if anahtarlar:
                    cikti.append((_metin(anahtarlar[0][0]), _metin(anahtarlar[0][1])))
        return cikti[:5]

    veri["slayt_3_cozum"] = {
        "tip": _metin(cozum.get("tip")) or "adim_adim_rehber",
        "baslik_ust": _metin(cozum.get("baslik_ust")),
        "baslik_vurgu": _metin(cozum.get("baslik_vurgu")),
        "alt_baslik": _metin(cozum.get("alt_baslik")),
        "maddeler": maddeler,
        "sol_kolon_baslik": _metin(cozum.get("sol_kolon_baslik")),
        "sag_kolon_baslik": _metin(cozum.get("sag_kolon_baslik")),
        "sol_kolon_veriler": _kolon(cozum.get("sol_kolon_veriler")),
        "sag_kolon_veriler": _kolon(cozum.get("sag_kolon_veriler")),
        "stratejist_notu": _metin(cozum.get("stratejist_notu")),
    }

    cta = _sozluk(v.get("slayt_4_cta"))
    veri["slayt_4_cta"] = {
        "slogan_parca_1": _metin(cta.get("slogan_parca_1")),
        "slogan_vurgu": _metin(cta.get("slogan_vurgu")),
        "aciklama": _metin(cta.get("aciklama")),
        "kaydet_metni": _metin(cta.get("kaydet_metni")),
    }

    for anahtar in ("saf_editoryal", "foto_degistir"):
        if v.get(anahtar) is True:
            veri[anahtar] = True
    for anahtar in ("onceki_foto", "foto_kaynak", "kapanis_stili", "konu_kodu"):
        if _metin(v.get(anahtar)):
            veri[anahtar] = _metin(v.get(anahtar))
    return veri
