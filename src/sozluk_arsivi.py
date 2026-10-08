"""
sozluk_arsivi.py — Hazır, doğrulanmış sözlük kartları (bilgi arşivi).

NİYE (2026-10-08 incelemesi): modelin her seferinde yeniden yazdığı sözlük otomatik yayına uygun değil.
Gerçek modelle, kanun alıntısıyla doğrulanmış 12 konuda üretildi ve çizildi: 12/12 çizim sorunsuz, ama
içeriğin en az 4'ünde ince bir yanlışlık vardı (S2-001 "teslim" yerine "sözleşme", S3-005 "Bakanlık izni
olmadan ifraz yapılamaz", S3-007 "plansız alanda ifraz yapılamaz", S2-006 belirsiz iade süresi). Düzenli
ifade kapısı bunların hiçbirini göremez (yalnız sayı ve özel isim bakar); anlam hakemi (capraz_denetim)
ise ücretsiz katman kotası bitince sessizce hiç çalışmaz. İnsan onayı varken bu kabul edilebilir;
onay kalkınca değildir.

ÇÖZÜM: kartlar bir kez yazılır, kanun metniyle doğrulanır ve hakemden geçirilir; yayın anında modele
HİÇ ihtiyaç yoktur. Otomatik yayında içerik değişmez, yalnız kanunun hâlâ aynı olduğu yeniden sınanır:
alıntı güncel metinde birebir bulunmuyorsa kart durur (kanun değişmiştir). Kart tanımı için
data/sozluk_kartlari.yaml başlığına bakın.
"""

from __future__ import annotations

import logging
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from . import config

log = logging.getLogger(__name__)

ARSIV_YOLU = config.yol_al("data/sozluk_kartlari.yaml")
BEKLEME_GUN = 180            # aynı kart bu süre geçmeden yeniden yayınlanmaz
KOD_KALIBI = re.compile(r"^SZ-\d{3}$")
ZORUNLU = ("kod", "terim", "kategori_kodu", "tanim", "puf", "mevzuat", "dayanak_alintisi", "kontrol")
YASAKLI_ISARETLER = ("**", "#", "\n", "!", "<", ">")

_onbellek: Optional[List[Dict[str, Any]]] = None


# ---------------------------------------------------------------------------
# Yükleme ve yapısal denetim
# ---------------------------------------------------------------------------

def _butce() -> Dict[str, int]:
    from . import generate_text
    return generate_text.BUTCE


def kart_yapisal_sorunlari(kart: Dict[str, Any]) -> List[str]:
    """Kanun metnine bakmadan kartın biçimi: alanlar, karakter bütçeleri, yasaklı işaretler."""
    from . import yeni_formatlar
    sorunlar: List[str] = []
    for alan in ZORUNLU:
        if not kart.get(alan):
            sorunlar.append(f"{alan} eksik")
    if sorunlar:
        return sorunlar
    butce = _butce()
    if not KOD_KALIBI.match(str(kart["kod"])):
        sorunlar.append("kod SZ-000 biçiminde olmalı")
    terim = str(kart["terim"])
    if len(terim) > butce["terim"]:
        sorunlar.append(f"terim {len(terim)}/{butce['terim']} karakter")
    tanim = str(kart["tanim"])
    if not 40 <= len(tanim) <= butce["tanim"]:
        sorunlar.append(f"tanim {len(tanim)} karakter (40-{butce['tanim']})")
    puf = kart["puf"]
    if not isinstance(puf, list) or not 2 <= len(puf) <= 3:
        sorunlar.append("puf 2 ya da 3 madde olmalı")
    else:
        for i, m in enumerate(puf):
            if not isinstance(m, str) or not 15 <= len(m) <= butce["puf_madde"]:
                sorunlar.append(f"puf[{i}] {len(str(m))} karakter (15-{butce['puf_madde']})")
    if len(str(kart["dayanak_alintisi"])) < 40:
        sorunlar.append("dayanak_alintisi 40 karakterden kısa")
    if str(kart["kategori_kodu"]).upper() not in yeni_formatlar.KATEGORI_HARITASI:
        sorunlar.append(f"kategori_kodu haritada yok: {kart['kategori_kodu']}")
    metinler = [terim, tanim, *(puf if isinstance(puf, list) else [])]
    for m in metinler:
        for isaret in YASAKLI_ISARETLER:
            if isinstance(m, str) and isaret in m:
                sorunlar.append(f"yasaklı işaret {isaret!r}: {m[:40]}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(kart["kontrol"])):
        sorunlar.append("kontrol YYYY-AA-GG olmalı")
    return sorunlar


def kartlari_yukle(tazele: bool = False) -> List[Dict[str, Any]]:
    """Geçerli kartlar. Biçimi bozuk ya da tekrar eden kart atlanır ve günlüğe yazılır."""
    global _onbellek
    if _onbellek is not None and not tazele:
        return _onbellek
    if not ARSIV_YOLU.exists():
        log.warning("Sözlük kart arşivi bulunamadı: %s", ARSIV_YOLU)
        _onbellek = []
        return _onbellek
    ham = yaml.safe_load(Path(ARSIV_YOLU).read_text(encoding="utf-8")) or {}
    gecerli: List[Dict[str, Any]] = []
    kodlar, terimler = set(), set()
    for kart in ham.get("kartlar", []):
        sorunlar = kart_yapisal_sorunlari(kart)
        if kart.get("kod") in kodlar:
            sorunlar.append("kod tekrar ediyor")
        if str(kart.get("terim", "")).upper() in terimler:
            sorunlar.append("terim tekrar ediyor")
        if sorunlar:
            log.warning("Sözlük kartı atlandı (%s): %s", kart.get("kod", "?"), "; ".join(sorunlar))
            continue
        kodlar.add(kart["kod"])
        terimler.add(str(kart["terim"]).upper())
        gecerli.append(kart)
    _onbellek = gecerli
    return gecerli


# ---------------------------------------------------------------------------
# Kanun metnine karşı denetim
# ---------------------------------------------------------------------------

def _konu_gibi(kart: Dict[str, Any]) -> Dict[str, Any]:
    """Kartı konu bankası denetiminin anlayacağı biçime çevirir: kartta yazan her süre, oran ve çoğunluk
    atıf yapılan maddenin güncel metninde bulunmalı."""
    return {
        "kod": kart["kod"],
        "mevzuat": kart["mevzuat"],
        "aci": " ".join([str(kart["tanim"]), *[str(m) for m in kart["puf"]]]),
        "dayanak_alintisi": kart["dayanak_alintisi"],
    }


def kart_kanun_durumu(kart: Dict[str, Any]) -> Tuple[Optional[bool], List[str]]:
    """(taze, sorunlar). taze: True = alıntı güncel metinde birebir var ve sayılar tutuyor; False = kanun
    değişmiş ya da kart yanlış; None = kanun metni alınamadı (doğrulanamadı: otomatik yayın durur)."""
    from . import mevzuat
    ozet = mevzuat.brief_mevzuati(kart["mevzuat"], azami_toplam=200000)
    if not ozet.get("metin"):
        return None, ["kanun metni alınamadı: " + "; ".join(ozet.get("cozulemeyen") or [])[:120]]
    sorunlar = mevzuat.konu_dayanagi_sorunlari(_konu_gibi(kart))
    return (not sorunlar), sorunlar


# ---------------------------------------------------------------------------
# Seçim
# ---------------------------------------------------------------------------

def _son_kart_kategorisi() -> Optional[str]:
    """En son yayınlanan kartın kategorisi: art arda aynı konudan kart çıkmasın."""
    from . import db
    try:
        with db._baglanti_al() as conn:
            satir = conn.execute(
                "SELECT konu_kodu FROM konu_gecmisi WHERE konu_kodu LIKE 'SZ-%' AND sonuc != 'hata' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if satir:
            kart = next((k for k in kartlari_yukle() if k["kod"] == satir["konu_kodu"]), None)
            return kart["kategori_kodu"] if kart else None
    except Exception as e:  # noqa: BLE001 — seçim çeşitliliği için; hata seçimi durdurmaz
        log.debug("Son kart kategorisi okunamadı: %s", e)
    return None


def sonraki_kart(gecmis: Optional[Dict[str, str]] = None, son_kategori: Optional[str] = None,
                 haric: Optional[set] = None) -> Optional[Dict[str, Any]]:
    """Yayınlanacak sıradaki kart: hiç kullanılmamışlar önce (art arda aynı kategori mümkünse seçilmez),
    bittiyse `BEKLEME_GUN` geçmiş en eski kart. `haric`: bu çalıştırmada kanun denetiminden kalanlar."""
    from . import konu_bankasi
    kartlar = [k for k in kartlari_yukle() if not k.get("pasif") and k["kod"] not in (haric or set())]
    if gecmis is None:
        gecmis = konu_bankasi._kullanim_gecmisi()
    if son_kategori is None:
        son_kategori = _son_kart_kategorisi()
    bakir = [k for k in kartlar if k["kod"] not in gecmis]
    if bakir:
        farkli = [k for k in bakir if k["kategori_kodu"] != son_kategori]
        return random.choice(farkli or bakir)
    uygun = [(k, konu_bankasi._gun_farki(gecmis[k["kod"]])) for k in kartlar]
    uygun = [(k, g) for k, g in uygun if g >= BEKLEME_GUN]
    return max(uygun, key=lambda t: t[1])[0] if uygun else None


def durum_ozeti(gecmis: Optional[Dict[str, str]] = None) -> Dict[str, int]:
    """Arşivin doluluğu: kaç kart var, kaçı hiç yayınlanmadı."""
    from . import konu_bankasi
    kartlar = [k for k in kartlari_yukle() if not k.get("pasif")]
    if gecmis is None:
        gecmis = konu_bankasi._kullanim_gecmisi()
    bakir = sum(1 for k in kartlar if k["kod"] not in gecmis)
    return {"toplam": len(kartlar), "bakir": bakir}


# ---------------------------------------------------------------------------
# Karttan içerik kaydı
# ---------------------------------------------------------------------------

def _ilk_cumle(metin: str, azami: int = 180) -> str:
    from . import generate_text
    return generate_text._ilk_cumle(metin, azami)


def karttan_veri(kart: Dict[str, Any]) -> Dict[str, Any]:
    """Kartı, modelin ürettiği sözlük kaydıyla AYNI biçimde içerik kaydına çevirir (çizici, yayın, Telegram
    önizlemesi ve veritabanı değişmeden çalışsın). Hiçbir alan model çıktısı değildir."""
    from . import generate_text
    terim = str(kart["terim"]).strip()
    tanim = str(kart["tanim"]).strip()
    puf = [str(m).strip() for m in kart["puf"]]
    govde = "\n\n".join([
        f"{terim} nedir?",
        tanim,
        "\n".join(puf),
        f"Dayanak: {kart['mevzuat']}.",
    ])
    veri: Dict[str, Any] = {
        "bicim": "B1",
        "format_turu": "sozluk",
        "terim": terim,
        "tanim_metni": tanim,
        "puf_maddeleri": puf,
        "kategori_kodu": kart["kategori_kodu"],
        "rozet_metni": "EMLAK SÖZLÜĞÜ",
        "yasal_dayanak": kart["mevzuat"],
        "manset_parca_1": "",
        "manset_vurgu": terim,
        "manset_parca_2": "nedir?",
        "spot": _ilk_cumle(tanim),
        "onem_puani": 8,
        "caption_instagram": govde,
        "konu_kodu": kart["kod"],
        # `kart`: bu kaydın hazır arşivden geldiği (model yazmadığı) işareti; otomatik yayın buna bakar
        "_brief": {"mevzuat": kart["mevzuat"], "yerel": None, "veri_kaynagi": None, "kart": True},
    }
    generate_text._captionlari_zenginlestir(veri)
    return veri
