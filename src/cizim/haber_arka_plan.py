"""
src/cizim/haber_arka_plan.py — Haber Arka Plan Fotoğrafı Çekme, Önbellekleme ve Kilitleme
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image, ImageOps

from .. import config
from .stok import _foto_indir_veya_ac
from .kardes import _haber_gorseli_alternatifi

log = logging.getLogger(__name__)


def _haber_arkaplan_hazirla(
    haber: Dict[str, Any],
    foto_yolu: Optional[Path | str] = None,
    cikti_yolu: Optional[Path] = None,
) -> Optional[Image.Image]:
    """Haber için en yüksek kalitede arka plan fotoğrafını temin eder ve kilitler."""
    bg_img: Optional[Image.Image] = None

    # 1.0. Önceden belirlenmiş/önbelleğe alınmış fotoğraf veya haberin orijinal görseli
    secilen_fp = foto_yolu or haber.get("foto_yolu") or haber.get("gorsel_yolu") or haber.get("gorsel_url")
    if secilen_fp:
        try:
            foto_ham = _foto_indir_veya_ac(str(secilen_fp))
            if foto_ham:
                from .. import gorsel_kalite
                bg_img = gorsel_kalite.kristal_netlestir(foto_ham)
                try:
                    c_dir = cikti_yolu.parent if cikti_yolu else config.yol_al("data/output/gonderiler")
                    c_dir.mkdir(parents=True, exist_ok=True)
                    h_id = haber.get("id") or os.getpid()
                    cache_p = c_dir / f"haber_foto_{h_id}.jpg"
                    if not cache_p.exists():
                        bg_img.save(cache_p, "JPEG", quality=95)
                    haber["foto_yolu"] = str(cache_p)
                    haber["gorsel_yolu"] = str(cache_p)
                except Exception as ce:
                    log.debug("Haber görseli diske sabitlenemedi: %s", ce)
                log.info("Haberin orijinal görseli başarıyla yüklendi ve kilitlendi: %s", str(secilen_fp)[:60])
        except Exception as pe:
            log.warning("Haber görseli açılamadı (%s): %s", secilen_fp, pe)

    # 1.1. Görsel bulunamadıysa doğrudan haberin orijinal web sayfasından çek
    if not bg_img:
        makale_link = haber.get("orijinal_url") or haber.get("link") or haber.get("url")
        if makale_link and str(makale_link).startswith("http"):
            try:
                from .. import fetch_article, gorsel_kalite
                og_u = fetch_article.og_gorseli_cek(makale_link)
                if not og_u:
                    tum_u = fetch_article.tum_gorselleri_cek(makale_link)
                    if tum_u:
                        og_u = tum_u[0]
                if og_u:
                    foto_og = _foto_indir_veya_ac(og_u)
                    if foto_og:
                        bg_img = gorsel_kalite.kristal_netlestir(foto_og)
                        haber["gorsel_url"] = og_u
                        log.info("Haberin web sayfasından görsel temin edildi: %s", og_u[:60])
            except Exception as oe:
                log.debug("Orijinal web linkinden görsel çekilemedi: %s", oe)

    # 1.2. Kardeş haber görsel havuzu
    if not bg_img:
        try:
            sira = int(haber.get("foto_sira") or 0)
            alt_foto, alt_kaynak = _haber_gorseli_alternatifi(haber, sira=sira)
            if alt_foto:
                bg_img = alt_foto
                if alt_kaynak:
                    haber["foto_atif"] = alt_kaynak
                log.info("Kardeş haber havuzundan HD görsel kullanılıyor (%s).", alt_kaynak)
        except Exception as ke:
            log.debug("Kardeş haber havuzu hatası: %s", ke)

    # 1.3. Pexels API'den emlak stok görseli ara
    if not bg_img:
        try:
            from .. import fetch_stock, gorsel_kalite
            kat = haber.get("kategori") or haber.get("kategori_kodu") or "SEKTOREL_HABER_VE_ANALIZ"
            baslik_ham = (haber.get("orijinal_baslik") or haber.get("manset") or haber.get("baslik") or "").lower()
            if any(w in baslik_ham for w in ("arsa", "arazi", "tarla", "parsel", "hazine", "milli emlak", "çatalca", "silivri")):
                arama_sorgu = "real estate land field plot aerial"
            elif any(w in baslik_ham for w in ("kira", "kiracı", "tahliye", "ev sahibi", "daire", "konut")):
                arama_sorgu = "modern apartment house keys interior real estate"
            elif any(w in baslik_ham for w in ("toki", "sosyal konut", "inşaat", "şantiye", "proje", "kentsel dönüşüm")):
                arama_sorgu = "modern residential buildings construction architecture"
            else:
                arama_sorgu = "modern luxury architecture real estate villa"
            stok_p = fetch_stock.stok_fotografi_ara(arama_sorgu, kategori_kodu=kat)
            if stok_p and stok_p.exists():
                stok_img = ImageOps.exif_transpose(Image.open(stok_p)).convert("RGB")
                bg_img = gorsel_kalite.kristal_netlestir(stok_img)
                haber["foto_yolu"] = str(stok_p)
                haber["gorsel_yolu"] = str(stok_p)
        except Exception as se:
            log.warning("Stok fotoğraf aranamadı: %s", se)

    return bg_img
