"""
src/cizim/stok.py — Stok arka planlar, Pexels entegrasyonu, görsel indirme ve perde geçiş maskesi.
"""

from __future__ import annotations

import io
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from PIL import Image, ImageOps

from .. import config, db, upload_image
from . import kardes, sabitler

log = logging.getLogger(__name__)

# Geriye dönük uyumluluk takma adları
konu_imzasi = kardes.konu_imzasi
kardes_linkler = kardes.kardes_linkler
_haber_gorseli_alternatifi = kardes._haber_gorseli_alternatifi

_basarisiz_gorsel_urlleri: set[str] = set()

ARKA_PLAN_HAVUZU = {
    "ARSA": [
        "arsa_aerial_green.jpg",
        "arsa_green_drone.jpg",
        "arsa_plow_field.jpg",
        "arsa_suburban_parsel.jpg",
    ],
    "KONUT": [
        "villa_modern_pool.jpg",
        "villa_luxury_dusk.jpg",
        "villa_minimal_white.jpg",
        "villa_estate_garden.jpg",
        "clean_modern_villa.jpg",
        "icmekan_minimal_living.jpg",
        "arsa_suburban_parsel.jpg",
    ],
    "BINA": [
        "bina_modern_glass.jpg",
        "bina_facade_dusk.jpg",
        "arsa_suburban_parsel.jpg",
    ],
    "ICMEKAN": [
        "icmekan_luxury_penthouse.jpg",
        "icmekan_modern_lounge.jpg",
        "clean_interior.jpg",
        "clean_architecture.jpg",
        "villa_estate_contemporary.jpg",
    ],
    "INSAAT": [
        "bina_modern_glass.jpg",
        "bina_facade_dusk.jpg",
    ],
}

KONU_HAVUZLARI: List[Tuple[Tuple[str, ...], str]] = [
    (("kentsel dönüşüm", "riskli yapı"), "INSAAT"),
    (("tarla", "arsa", "imar", "ifraz", "parsel", "tarım", "zilyet", "tapusuz", "tiny house", "prefabrik", "bağ evi", "kadastro"), "ARSA"),
    (("inşaat", "müteahhit", "kat karşılığı", "ruhsat", "iskân", "iskan", "yapı kullanma"), "INSAAT"),
    (("kira", "kiracı", "ev sahibi", "tahliye", "depozito", "aidat", "apartman", "kat mülkiyeti", "site yönetimi"), "BINA"),
    (("kredi", "faiz", "banka", "dask", "ekspertiz", "vergi", "yatırım", "değer artış"), "BINA"),
    (("tapu", "önalım", "şufa", "miras", "hisse", "kaparo", "harç", "vekâlet", "satış"), "KONUT"),
]

PEXELS_SORGULARI = {
    "ARSA": "aerial view farmland fields drone",
    "INSAAT": "residential construction site building crane",
    "BINA": "apartment building facade city",
    "KONUT": "residential house exterior neighborhood",
}


def _foto_indir_veya_ac(foto_url_veya_yol: str, deneme_adedi: int = 2) -> Optional[Image.Image]:
    """URL veya yerel dosyadan görseli açar."""
    import sys
    mi = sys.modules.get("src.make_image")
    if mi is not None and getattr(mi, "_foto_indir_veya_ac", None) is not None and mi._foto_indir_veya_ac is not _foto_indir_veya_ac:
        return mi._foto_indir_veya_ac(foto_url_veya_yol)

    if not foto_url_veya_yol:
        return None

    s = str(foto_url_veya_yol).strip()
    if s in _basarisiz_gorsel_urlleri:
        return None

    yerel = upload_image.yerel_karsiligi(s)
    if yerel and yerel.exists() and yerel.is_file():
        try:
            with Image.open(yerel) as img:
                return ImageOps.exif_transpose(img).convert("RGB")
        except Exception as e:
            log.warning("Önbellekteki görsel açılamadı (%s): %s", yerel, e)

    if s.startswith(("http://", "https://")):
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        for deneme in range(1, deneme_adedi + 1):
            try:
                resp = requests.get(s, headers=headers, timeout=8)
                if resp.status_code == 200:
                    with Image.open(io.BytesIO(resp.content)) as img:
                        return ImageOps.exif_transpose(img).convert("RGB")
                if resp.status_code in (404, 410, 403):
                    _basarisiz_gorsel_urlleri.add(s)
                    break
            except Exception as e:
                log.warning("Görsel indirme hatası (%s, deneme %d/%d): %s", s, deneme, deneme_adedi, e)
            if deneme < deneme_adedi:
                time.sleep(1)
        _basarisiz_gorsel_urlleri.add(s)
        return None

    try:
        p = Path(s)
        if p.exists() and p.is_file():
            with Image.open(p) as img:
                return ImageOps.exif_transpose(img).convert("RGB")
    except Exception as e:
        log.warning("Yerel görsel açılamadı (%s): %s", s, e)
    return None


def _konu_havuzu(konu_metni: Optional[str], kategori_kodu: Optional[str]) -> str:
    kucuk = (konu_metni or "").replace("İ", "i").replace("I", "ı").lower()
    for kelimeler, havuz in KONU_HAVUZLARI:
        if any(k in kucuk for k in kelimeler):
            return havuz
    kat = (kategori_kodu or "").upper()
    if any(k in kat for k in ("ARSA", "IMAR", "PARSEL", "TARLA")):
        return "ARSA"
    if any(k in kat for k in ("INSAAT", "KENTSEL", "DONUSUM", "PROJE")):
        return "INSAAT"
    if any(k in kat for k in ("KIRACI", "EV_SAHIBI", "SITE", "APARTMAN", "YATIRIM", "FINANS", "VERGI", "DEGERLEME")):
        return "BINA"
    return "KONUT"


def _konu_stok_fotografi(havuz: str, tohum: Optional[Any]) -> Optional[Image.Image]:
    """Pexels anahtarı varsa konuya özel dikey fotoğraf (yoksa None)."""
    if config.test_modu() or not config.env_al("PEXELS_API_KEY"):
        return None
    try:
        from .. import fetch_stock
        yol = fetch_stock.stok_fotografi_ara(PEXELS_SORGULARI.get(havuz, PEXELS_SORGULARI["KONUT"]),
                                             tohum=str(tohum) if tohum is not None else None)
        if yol and Path(yol).exists():
            return ImageOps.fit(Image.open(yol).convert("RGB"), (sabitler.GENISLIK, sabitler.YUKSEKLIK), Image.Resampling.LANCZOS)
    except Exception as e:
        log.warning("Konu stok fotoğrafı alınamadı, yerel havuza dönülüyor: %s", e)
    return None


def _temiz_arkaplan_al(
    kategori_kodu: Optional[str] = None,
    ozel_url_veya_yol: Optional[str] = None,
    tohum: Optional[Any] = None,
    haric_tut: Optional[List[str]] = None,
    konu_metni: Optional[str] = None,
) -> Image.Image:
    """Kategoriye en uygun yüksek çözünürlüklü temiz mimari görseli yükler."""
    w, h = sabitler.GENISLIK, sabitler.YUKSEKLIK
    if ozel_url_veya_yol:
        foto = _foto_indir_veya_ac(ozel_url_veya_yol)
        if foto:
            return ImageOps.fit(foto, (w, h), Image.Resampling.LANCZOS)

    havuz_adi = _konu_havuzu(konu_metni, kategori_kodu)
    if konu_metni is not None:
        stok = _konu_stok_fotografi(havuz_adi, tohum)
        if stok is not None:
            return stok
    havuz = list(ARKA_PLAN_HAVUZU[havuz_adi])

    son_kullanilan = []
    try:
        raw = db.ayar_oku("son_arkaplanlar")
        if raw:
            son_kullanilan = json.loads(raw)
            if not isinstance(son_kullanilan, list):
                son_kullanilan = []
    except Exception:
        son_kullanilan = []

    if haric_tut:
        son_kullanilan.extend(haric_tut)

    mevcut_havuz = [b_ad for b_ad in havuz if config.yol_al(f"assets/backgrounds/{b_ad}").exists()] or havuz
    adaylar = [ad for ad in mevcut_havuz if ad not in son_kullanilan] or [ad for ad in mevcut_havuz if ad not in son_kullanilan[-2:]] or mevcut_havuz

    import hashlib
    idx = (int(hashlib.md5(str(tohum).encode("utf-8")).hexdigest(), 16) if tohum is not None else int(time.time() * 1000)) % len(adaylar)
    secilen_ad = adaylar[idx]

    try:
        yeni_liste = [ad for ad in son_kullanilan if ad != secilen_ad] + [secilen_ad]
        db.ayar_yaz("son_arkaplanlar", json.dumps(yeni_liste[-10:]))
    except Exception:
        pass

    yerel_bg = config.yol_al(f"assets/backgrounds/{secilen_ad}")
    if yerel_bg.exists():
        try:
            img = Image.open(yerel_bg).convert("RGB")
            return ImageOps.fit(img, (w, h), Image.Resampling.LANCZOS)
        except Exception as e:
            log.warning("Arka plan yüklenemedi: %s", e)

    return Image.new("RGB", (w, h), sabitler.RENK_MUREKKEP)


def _perde_maskesi_smoothstep(genislik: int, yukseklik: int, bas: int, son: int) -> Image.Image:
    """Fotoğraftan koyu zemine pürüzsüz geçiş maskesi."""
    seritler = []
    fark = max(1, son - bas)
    for y in range(yukseklik):
        if y <= bas:
            v = 0
        elif y >= son:
            v = 255
        else:
            t = (y - bas) / fark
            v = int(255 * (t * t * (3 - 2 * t)))
        seritler.append(v)
    serit = Image.new("L", (1, yukseklik))
    serit.putdata(seritler)
    return serit.resize((genislik, yukseklik), Image.BILINEAR)
