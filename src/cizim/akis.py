"""
src/cizim/akis.py — Otorite Karusel Slayt Planlama ve Çizim Orkestrasyonu
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .. import config
from .sabitler import GENISLIK, YUKSEKLIK
from .hatalar import EksikIcerik
from .tuval import tuval
from .tipografi import _gorsel_girdisi
from .fikir import slayt_ikili_fikir, slayt_tek_fikir
from .adim import adim_blok_yuksekligi, adim_iri_mi, slayt_adim, slayt_adimlar_toplu
from .otorite_kapak import otorite_slayt_1_kapak
from .otorite_cozum import otorite_slayt_3_cozum, slayt_kapanis
from .normalize import veriyi_normalize_et

log = logging.getLogger(__name__)

ESIK_IKILI_FIKIR = 290
ESIK_ADIM_TOPLU = 330


def _slayt_plani(veri: Dict[str, Any]) -> List[Dict[str, Any]]:
    """İçerik yoğunluğuna göre slayt dizisini planlar (3 ↔ 8 slayt)."""
    plan: List[Dict[str, Any]] = [{"tur": "kapak"}]

    detay = veri.get("slayt_2_detay") or {}
    kartlar = detay.get("kartlar")
    if isinstance(kartlar, (list, tuple)) and kartlar:
        fikirler = [k for k in kartlar if isinstance(k, dict) and k.get("baslik")]
    else:
        k1, k2 = detay.get("kart_1"), detay.get("kart_2")
        fikirler = [k for k in (k1, k2) if isinstance(k, dict) and k.get("baslik")]

    if fikirler:
        yogunluk = sum(len(k.get("aciklama", "")) for k in fikirler)
        if len(fikirler) == 2 and yogunluk <= ESIK_IKILI_FIKIR:
            plan.append({"tur": "ikili_fikir", "fikirler": fikirler, "zemin": "murekkep"})
        else:
            for i, k in enumerate(fikirler):
                renk = k.get("renk", "")
                if renk == "kirmizi":
                    zemin = "kirmizi"
                elif renk in ("yesil", "beyaz"):
                    zemin = "kagit"
                else:
                    zemin = "kirmizi" if i == 0 else "kagit"
                plan.append({
                    "tur": "tek_fikir", "fikir": k,
                    "zemin": zemin,
                })

    cozum = veri.get("slayt_3_cozum") or {}
    maddeler = [m for m in (cozum.get("maddeler") or []) if isinstance(m, dict) and m.get("baslik")]
    if cozum.get("tip") == "finansal_tablo":
        plan.append({"tur": "finansal_tablo"})
    elif maddeler:
        iri = adim_iri_mi(maddeler)
        for m in maddeler:
            plan.append({"tur": "adim", "madde": m, "toplam": len(maddeler), "zemin": "murekkep", "iri": iri,
                         "tum_adimlar": maddeler})

    plan.append({"tur": "kapanis"})
    return plan


@_gorsel_girdisi
def otorite_gonderi_slaytlari_uret(
    veri: Dict[str, Any],
    cikti_onek: Optional[str] = None,
    olcu: Any = "besleme",
) -> List[Path]:
    """Carousel görsellerini üretir. Slayt sayısı içeriğe göre 4 ile 7 arasında değişir."""
    normal = veriyi_normalize_et(veri)
    if not any(normal.get(k) for k in ("manset_parca_1", "manset_vurgu", "manset_parca_2", "manset")):
        raise EksikIcerik("Carousel: manşet üretilmedi")
    with tuval(olcu):
        return _gonderi_slaytlarini_ciz(normal, cikti_onek)


def _gonderi_slaytlarini_ciz(veri: Dict[str, Any], cikti_onek: Optional[str]) -> List[Path]:
    onek = cikti_onek or f"gonderi_{os.getpid()}"
    plan = _slayt_plani(veri)
    toplam = len(plan)
    rozet = veri.get("rozet_metni") or "EDM ANALİZ // GAYRİMENKUL"
    alt_metin = "EDM YAPI & GAYRİMENKUL // BÜLTEN"

    yollar: List[Path] = []
    for i, adim in enumerate(plan, start=1):
        if YUKSEKLIK >= 1700 or veri.get("_video_modu"):
            sayfa = ""
        else:
            sayfa = f"{str(i).zfill(2)} / {str(toplam).zfill(2)}"
            if i < toplam and YUKSEKLIK != 1920 and GENISLIK != 1920:
                sayfa += "  ›"
        yol = config.yol_al(f"data/output/{onek}_{str(i).zfill(2)}_{adim['tur']}.jpg")
        tur = adim["tur"]

        veri["_toplam_slayt"] = toplam
        veri["_slayt_sirasi"] = i

        if tur == "kapak":
            yollar.append(otorite_slayt_1_kapak(veri, yol))

        elif tur == "ikili_fikir":
            yollar.append(slayt_ikili_fikir(
                adim["zemin"], rozet,
                [{"etiket": f.get("etiket", ""), "baslik": f.get("baslik", ""),
                  "govde": f.get("aciklama", ""), "renk": f.get("renk", "")}
                 for f in adim["fikirler"]],
                alt_metin, sayfa, yol,
            ))

        elif tur == "tek_fikir":
            f = adim["fikir"]
            yollar.append(slayt_tek_fikir(
                adim["zemin"], rozet, f.get("etiket", ""), f.get("baslik", ""),
                f.get("aciklama", ""), alt_metin, sayfa, yol,
            ))

        elif tur == "adimlar_toplu":
            yollar.append(slayt_adimlar_toplu(
                adim["zemin"], veri.get("slayt_3_cozum", {}).get("baslik_vurgu") or rozet,
                adim["maddeler"], "EDM YAPI & GAYRİMENKUL // DANIŞMANLIK", sayfa, yol,
            ))

        elif tur == "adim":
            m = adim["madde"]
            yollar.append(slayt_adim(
                adim["zemin"], veri.get("slayt_3_cozum", {}).get("baslik_vurgu") or rozet,
                m.get("no", "01"), m.get("baslik", ""), m.get("aciklama", ""),
                adim["toplam"], "EDM YAPI & GAYRİMENKUL // DANIŞMANLIK", sayfa, yol,
                iri=bool(adim.get("iri")),
                hiza_yuksekligi=adim_blok_yuksekligi(adim.get("tum_adimlar") or [m], bool(adim.get("iri"))),
            ))

        elif tur == "finansal_tablo":
            yollar.append(otorite_slayt_3_cozum(veri, yol))

        elif tur == "kapanis":
            veri["_toplam_slayt"] = toplam
            yollar.append(slayt_kapanis(veri, sayfa, yol))

    return yollar
