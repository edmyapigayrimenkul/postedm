"""
src/cizim/haber_akis.py — Haber Detay Maddeleri Ayıklama ve DailyBrief Akışı
"""

from __future__ import annotations

import itertools
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .. import config
from .tipografi import _gorsel_girdisi
from .otorite_kapak import otorite_slayt_1_kapak
from .otorite_cozum import otorite_slayt_3_cozum, slayt_kapanis

log = logging.getLogger(__name__)


def haber_detay_maddelerini_ayikla(haber: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Haber verisinden editoryal Smart Brevity detay maddelerini normalize edilmiş liste olarak ayıklar."""
    if isinstance(haber, dict):
        dm = haber.get("detay_metni")
        if dm and isinstance(dm, str) and dm.strip().startswith("{"):
            try:
                parsed = json.loads(dm)
                if isinstance(parsed, dict):
                    for k, v in parsed.items():
                        if k not in haber or haber[k] is None:
                            haber[k] = v
            except Exception:
                pass

    if isinstance(haber, dict) and isinstance(haber.get("detay_yazisi"), str) and haber["detay_yazisi"].strip():
        from .. import haber_alanlari
        return [{"etiket": "", "metin": p, "renk": "kirec"} for p in haber_alanlari.detay_paragraflari(haber, kalin=False)]

    maddeler = haber.get("detay_maddeleri") or haber.get("maddeler") or []
    if not maddeler:
        if isinstance(haber.get("slayt_2_detay"), dict):
            s2 = haber["slayt_2_detay"]
            k1 = s2.get("kart_1")
            k2 = s2.get("kart_2")
            if k1 and k2:
                etiket_1 = k1.get("etiket") or k1.get("baslik") or "GÜNCEL GELİŞME"
                metin_1 = k1.get("aciklama") or k1.get("metin") or ""
                etiket_2 = k2.get("etiket") or k2.get("baslik") or "BÖLGESEL & SEKTÖREL ETKİ"
                metin_2 = k2.get("aciklama") or k2.get("metin") or ""
                if metin_1 and metin_2:
                    maddeler = [
                        {"etiket": etiket_1.upper(), "metin": metin_1, "renk": "kirmizi"},
                        {"etiket": etiket_2.upper(), "metin": metin_2, "renk": "kirec"},
                    ]
        if not maddeler:
            s3 = haber.get("slayt_3_cozum")
            if isinstance(s3, dict) and s3.get("maddeler"):
                renk_sira = ["kirmizi", "kirec", "kirec", "kirec", "kirec"]
                maddeler = [
                    {
                        "etiket": m.get("baslik", "DETAY").upper(),
                        "metin": m.get("aciklama", ""),
                        "renk": renk_sira[i % len(renk_sira)],
                    }
                    for i, m in enumerate(s3.get("maddeler", []))
                ]
    if not maddeler:
        detay_ham = haber.get("detay") or haber.get("detay_metni") or haber.get("spot") or haber.get("orijinal_ozet") or ""
        if isinstance(detay_ham, str) and not detay_ham.strip().startswith("{"):
            cumleler = [c.strip() for c in re.split(r"(?<=[.!?])\s+", detay_ham) if len(c.strip()) > 8]
            parcalar = cumleler[:4]
            maddeler = [
                {"etiket": f"AYRINTI {i:02d}", "metin": c, "renk": "kirmizi" if i == 1 else "kirec"}
                for i, c in enumerate(parcalar, start=1)
            ]

    varsayilan_etiketler = [f"AYRINTI {i:02d}" for i in range(1, 5)]
    KIREC = (228, 228, 225)
    renk_sozlugu = {
        "kirmizi": (240, 0, 13),
        "kirec": KIREC,
        "turkuaz": KIREC,
        "yesil": KIREC,
        "amber": KIREC,
        "sari": KIREC,
    }
    varsayilan_renk_listesi = [(240, 0, 13), KIREC, KIREC, KIREC]

    temiz = []
    for idx, m in enumerate(maddeler):
        if isinstance(m, dict):
            e = m.get("etiket") or m.get("baslik") or varsayilan_etiketler[idx % len(varsayilan_etiketler)]
            t = m.get("metin") or m.get("aciklama") or m.get("govde") or ""
            r_val = m.get("renk")
            if isinstance(r_val, tuple) and len(r_val) == 3:
                r = r_val
            else:
                r = renk_sozlugu.get(str(r_val).lower(), varsayilan_renk_listesi[idx % len(varsayilan_renk_listesi)])
        else:
            m_str = str(m).strip()
            if ":" in m_str:
                e_part, t_part = m_str.split(":", 1)
                e = e_part.strip().upper()
                t = t_part.strip()
            else:
                e = varsayilan_etiketler[idx % len(varsayilan_etiketler)]
                t = m_str
            r = varsayilan_renk_listesi[idx % len(varsayilan_renk_listesi)]
        temiz.append({"etiket": str(e).upper(), "metin": str(t).strip(), "renk": r})
    return temiz


def dailybrief_slayt_sayisi_belirle(
    haber: Dict[str, Any],
    maddeler: Optional[List[Dict[str, Any]]] = None,
) -> int:
    """Haberin kapsamına göre dinamik slayt sayısı belirler (2 veya 3)."""
    if haber.get("slayt_sayisi") in (2, 3):
        return int(haber["slayt_sayisi"])

    if maddeler is None:
        maddeler = haber_detay_maddelerini_ayikla(haber)

    sayi = len(maddeler)
    if sayi >= 3:
        return 3

    if sayi == 2:
        toplam_uzunluk = sum(len(m.get("metin", "")) for m in maddeler)
        anahtar_kelimeler = ["parsel", "ada", "imar", "askı", "kaks", "emsal", "yargıtay", "kanun", "madde", "resmi gazete", "ruhsat", "iskan"]
        tum_metin = " ".join(m.get("metin", "") + " " + m.get("etiket", "") for m in maddeler).lower()
        has_anahtar = any(k in tum_metin for k in anahtar_kelimeler)
        if toplam_uzunluk >= 130 or has_anahtar:
            return 3
        return 2

    detay_ham = (haber.get("detay") or haber.get("detay_metni") or haber.get("orijinal_ozet") or haber.get("spot") or "").strip()
    if len(detay_ham) >= 200:
        return 3
    return 2


def _sayfalari_dengeli_bol(
    maddeler: List[Dict[str, Any]],
    sayfa_sayisi: int = 2,
    has_uzman_notu_son_sayfa: bool = True,
) -> List[List[Dict[str, Any]]]:
    """Maddeleri detay sayfaları arasında dengeli biçimde paylaştırır."""
    if not maddeler:
        return [[] for _ in range(sayfa_sayisi)]
    n = len(maddeler)
    if sayfa_sayisi <= 1 or n <= 1:
        return [maddeler]

    if sayfa_sayisi == 2:
        uzman_agirligi = 90 if has_uzman_notu_son_sayfa else 0
        en_iyi_cut = 1
        en_iyi_fark = float("inf")

        for cut in range(1, n):
            p1 = maddeler[:cut]
            p2 = maddeler[cut:]
            h1 = sum(len(m.get("metin", "")) + 40 for m in p1)
            h2 = sum(len(m.get("metin", "")) + 40 for m in p2) + uzman_agirligi
            fark = abs(h1 - h2)
            if fark < en_iyi_fark:
                en_iyi_fark = fark
                en_iyi_cut = cut

        return [maddeler[:en_iyi_cut], maddeler[en_iyi_cut:]]

    en_iyi_bolum = None
    en_iyi_skor = float("inf")
    k = sayfa_sayisi
    for cuts in itertools.combinations(range(1, n), k - 1):
        idx = [0] + list(cuts) + [n]
        parts = [maddeler[idx[i]:idx[i + 1]] for i in range(k)]
        heights = []
        for i, p in enumerate(parts):
            h = sum(len(m.get("metin", "")) + 40 for m in p)
            if i == k - 1 and has_uzman_notu_son_sayfa:
                h += 90
            heights.append(h)

        h_avg = sum(heights) / k
        var_cost = sum((h - h_avg) ** 2 for h in heights)
        diff_cost = (max(heights) - min(heights)) * 50
        bos_ceza = sum(100000 for p in parts if len(p) == 0)
        skor = var_cost + diff_cost + bos_ceza
        if skor < en_iyi_skor:
            en_iyi_skor = skor
            en_iyi_bolum = parts

    return en_iyi_bolum if en_iyi_bolum is not None else [maddeler[:n//2], maddeler[n//2:]]


@_gorsel_girdisi
def haber_dailybrief_slaytlari_uret(
    haber: Dict[str, Any],
    cikti_dizini: Optional[Path] = None,
    cikti_onek: str = "dailybrief",
    olcu: str = "besleme",
    foto_yolu: Optional[Path | str] = None,
) -> List[Path]:
    """Haber carousel'i üretir."""
    if cikti_dizini is None:
        cikti_dizini = config.yol_al("data/output/gonderiler")
    cikti_dizini = Path(cikti_dizini)
    cikti_dizini.mkdir(parents=True, exist_ok=True)

    from .. import haber_tasarim
    return haber_tasarim.slaytlari_uret(haber, cikti_dizini, cikti_onek, olcu=olcu, foto_yolu=foto_yolu)


def haber_slayti_1_ciz(manset: str, spot: str, kaynak: str, tarih: str, foto_url: Optional[str] = None, cikti_yolu: Optional[Path] = None) -> Path:
    veri = {
        "manset": manset,
        "spot": spot,
        "kaynak": kaynak,
        "yasal_dayanak": f"KAYNAK: {kaynak.upper()} // TARİH: {tarih[:10] if tarih else ''}",
        "gorsel_url": foto_url,
    }
    return otorite_slayt_1_kapak(veri, cikti_yolu)


def haber_slayti_2_ciz(manset: str, maddeler: List[str], cikti_yolu: Optional[Path] = None) -> Path:
    veri = {
        "slayt_3_cozum": {
            "tip": "adim_adim_rehber",
            "baslik_ust": "Sektörel Değerlendirme ve",
            "baslik_vurgu": "PİYASA ÇIKARIMLARI",
            "maddeler": [
                {"no": f"0{idx}", "baslik": f"Önemli Not #{idx}", "aciklama": m}
                for idx, m in enumerate(maddeler[:3], start=1)
            ],
        }
    }
    return otorite_slayt_3_cozum(veri, cikti_yolu)


def haber_kapanis_slayti_ciz(cikti_yolu: Optional[Path] = None) -> Path:
    return slayt_kapanis({}, "03 / 03", cikti_yolu)

