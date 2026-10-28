"""
src/cizim/kardes.py — Kardeş haber eşleştirme ve alternatif basın fotoğrafları.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from .. import db
from . import stok

log = logging.getLogger(__name__)

ETKISIZ_KELIMELER = {
    "icin", "olan", "gibi", "kadar", "sonra", "once", "veya", "gore",
    "biri", "yeni", "daha", "cok", "bazi", "tum", "her", "ile", "ve",
    "bir", "bu", "su", "o", "da", "de", "ta", "te", "mi", "mu", "mu",
}


def konu_imzasi(baslik: str) -> Tuple[set[str], set[str]]:
    """Tekrar denetimi ve kardeş haber eşleştirmesi için anahtar kelimeler ve isimler."""
    kelimeler = set()
    for ham in (baslik or "").lower().replace("'", " ").split():
        temiz = "".join(k for k in ham if k.isalnum())
        if len(temiz) >= 4 and temiz not in ETKISIZ_KELIMELER:
            kelimeler.add(temiz)

    isimler = set()
    for ham in (baslik or "").replace("'", " ").split():
        temiz = "".join(k for k in ham if k.isalnum())
        if len(temiz) >= 4 and temiz[:1].isupper() and temiz.lower() not in ETKISIZ_KELIMELER:
            isimler.add(temiz.lower())
    return kelimeler, isimler


def kardes_linkler(con, haber: Dict[str, Any], azami: int = 3) -> List[str]:
    """Aynı olayı işleyen kardeş haber linklerini toplar."""
    if con is None:
        try:
            con = db.baglanti_al()
        except Exception:
            return []

    baslik = haber.get("baslik") or haber.get("orijinal_baslik") or haber.get("manset") or ""
    if not baslik:
        return []

    k1, i1 = konu_imzasi(baslik)
    haber_id = haber.get("id") or 0

    try:
        satirlar = con.execute(
            """SELECT id, baslik, link, foto_url FROM haberler
               WHERE id != ? AND COALESCE(link, '') != ''
                 AND eklenme_tarihi > datetime('now', '-2 days')""",
            (haber_id,),
        ).fetchall()
    except Exception as e:
        log.debug("Kardeş haber sorgusu: %s", e)
        return []

    esler = []
    for r in satirlar:
        b2 = r["baslik"] if isinstance(r, dict) or hasattr(r, "keys") else r[1]
        link = r["link"] if isinstance(r, dict) or hasattr(r, "keys") else r[2]
        foto_url = (r["foto_url"] if isinstance(r, dict) or hasattr(r, "keys") else r[3]) or ""
        k2, i2 = konu_imzasi(b2 or "")
        ortak = len(k1 & k2)
        if ortak >= 3 or (ortak >= 2 and (i1 & i2)):
            esler.append((ortak, link, foto_url))

    esler.sort(key=lambda x: -x[0])
    return [link for _, link, _ in esler if link][:azami]


def _haber_gorseli_alternatifi(
    haber: Dict[str, Any],
    con=None,
    sira: int = 0,
) -> Tuple[Optional[Image.Image], Optional[str]]:
    """'Başka fotoğraf' için sıradaki haber görseli veya kardeş haber basın fotoğrafı."""
    from .. import fetch_article, gorsel_kalite
    aday_linkler = []
    ana_link = haber.get("link") or haber.get("orijinal_url") or haber.get("url")
    if ana_link:
        aday_linkler.append(ana_link)
    aday_linkler.extend(kardes_linkler(con, haber))

    if sira < len(aday_linkler):
        link = aday_linkler[sira]
        try:
            url = fetch_article.og_gorseli_cek(link) or ((fetch_article.tum_gorselleri_cek(link) or [None])[0])
            if url:
                foto = stok._foto_indir_veya_ac(url)
                if foto:
                    kaliteli, _ = gorsel_kalite.gorsel_kalite_denetle(foto)
                    if kaliteli:
                        return gorsel_kalite.kristal_netlestir(foto), f"Basın Kaynağı ({link[:30]}…)"
        except Exception as e:
            log.debug("Kardeş görsel çekilemedi (%s): %s", link, e)
    return None, None
