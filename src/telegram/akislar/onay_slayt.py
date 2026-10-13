"""
src/telegram/akislar/onay_slayt.py — Onay kartı için slayt hazırlığı: mevcut slaytlar, otorite verisi, format başına çizim, CDN yükleme.

Katman 2-3: çizim `make_image`/`yeni_formatlar`'a, yükleme `upload_image`'a devredilir; bu modül yalnız hangisinin çağrılacağına karar verir.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ... import upload_image

log = logging.getLogger(__name__)


def mevcut_slaytlar(haber: Dict[str, Any], yeniden_ciz: bool) -> List[str]:
    """Daha önce çizilmiş slaytlar (yeniden_ciz=True ise bayat dosyalar kullanılmaz). Hepsi diskte yoksa boş liste."""
    slayt_yollari = []
    if not yeniden_ciz and haber.get("slayt_yollari"):
        try:
            mevcut = json.loads(haber["slayt_yollari"])
            if isinstance(mevcut, list) and len(mevcut) > 0 and all(Path(p).exists() for p in mevcut):
                slayt_yollari = [str(p) for p in mevcut]
        except Exception:
            slayt_yollari = []
    return slayt_yollari


def otorite_verisini_oku(haber: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Haberin `detay_metni` JSON'undan (otorite verisi, format türü)."""
    otorite_verisi = None
    if haber.get("detay_metni"):
        try:
            otorite_verisi = json.loads(haber["detay_metni"])
        except Exception:
            otorite_verisi = None

    format_turu = None
    if otorite_verisi and isinstance(otorite_verisi, dict):
        format_turu = otorite_verisi.get("format_turu")
    return otorite_verisi, format_turu


def slaytlari_ciz(haber_id: int, haber: Dict[str, Any], otorite_verisi: Optional[Dict[str, Any]],
                  format_turu: Optional[str]) -> List[str]:
    """Formata göre slaytları çizer, yollarını döndürür. `otorite_verisi` yerinde tamamlanır (sonraki adımlar okur)."""
    slayt_yollari: List[str] = []
    from ... import make_image, yeni_formatlar

    if otorite_verisi and isinstance(otorite_verisi, dict):
        if not otorite_verisi.get("foto_yolu") and not otorite_verisi.get("gorsel_yolu"):
            otorite_verisi["foto_yolu"] = haber.get("gorsel_url")
            otorite_verisi["gorsel_yolu"] = haber.get("gorsel_url")
        if not otorite_verisi.get("orijinal_baslik"):
            otorite_verisi["orijinal_baslik"] = haber.get("orijinal_baslik")
        if not otorite_verisi.get("kaynak"):
            otorite_verisi["kaynak"] = haber.get("kaynak")
        if not otorite_verisi.get("manset"):
            otorite_verisi["manset"] = haber.get("manset") or haber.get("orijinal_baslik")
        if not otorite_verisi.get("spot"):
            otorite_verisi["spot"] = haber.get("orijinal_ozet")

    dm_raw = str(haber.get("detay_metni") or "").strip()
    spot_val = haber.get("orijinal_ozet") or (dm_raw if not dm_raw.startswith("{") else "")
    veri_icin = {
        "manset": haber.get("manset") or haber.get("orijinal_baslik", ""),
        "spot": spot_val,
        "kategori": haber.get("kategori") or "TAPU_VE_HUKUK",
        "kaynak": haber.get("kaynak", "EDM Yapı & Gayrimenkul"),
        "gorsel_yolu": haber.get("gorsel_url"),
        "format_turu": format_turu or "dailybrief",
        "detay_maddeleri": haber.get("detay_maddeleri"),
        "uzman_notu": haber.get("uzman_notu"),
    }
    aktif_veri = otorite_verisi if (otorite_verisi and isinstance(otorite_verisi, dict)) else veri_icin

    # Instagram ve Sosyal Medya Standartı:
    # Feed Carousel gönderileri kırpılma/taşma yaşamaması için NATIVE 4:5 ("besleme", 1080x1350) üretilir.
    # Yalnızca dikey video/Reels veya Hikaye içerikleri 9:16 ("story", 1080x1920) üretilir.
    is_reels = (format_turu == "reels") or (haber.get("kategori") == "REELS")
    olcu = "story" if is_reels else "besleme"

    if format_turu == "reels":
        fmt = aktif_veri.get("bicim") or "dailybrief"
        if fmt in ("dailybrief", "haber", "sozluk", "nedir_dogrusu", "net_cevap", "vaka"):
            slayt_listesi = yeni_formatlar.slaytlari_uret(aktif_veri, format_turu=fmt, cikti_onek=f"gonderi_{haber_id}", olcu="story")
        else:
            slayt_listesi = make_image.otorite_gonderi_slaytlari_uret(aktif_veri, cikti_onek=f"gonderi_{haber_id}", olcu="story")
        slayt_yollari = [str(p) for p in slayt_listesi]
    elif format_turu in ("sozluk", "nedir_dogrusu", "net_cevap", "vaka", "dailybrief", "haber", "haber_dailybrief") or (otorite_verisi and otorite_verisi.get("bicim") in ("haber", "B5")):
        f_tur = format_turu if format_turu in ("sozluk", "nedir_dogrusu", "net_cevap", "vaka", "dailybrief", "haber", "haber_dailybrief") else (aktif_veri.get("bicim") or "dailybrief")
        if f_tur in ("dailybrief", "haber", "sozluk", "nedir_dogrusu", "net_cevap", "vaka"):
            slayt_listesi = yeni_formatlar.slaytlari_uret(aktif_veri, format_turu=f_tur, cikti_onek=f"gonderi_{haber_id}", olcu=olcu)
        else:
            slayt_listesi = make_image.otorite_gonderi_slaytlari_uret(aktif_veri, cikti_onek=f"gonderi_{haber_id}", olcu=olcu)
        slayt_yollari = [str(p) for p in slayt_listesi]
    elif not otorite_verisi and (haber.get("orijinal_baslik") or haber.get("manset")):
        # Doğrudan haber/gündem akışından gelen kayıt
        slayt_listesi = yeni_formatlar.slaytlari_uret(veri_icin, format_turu="dailybrief", cikti_onek=f"gonderi_{haber_id}", olcu=olcu)
        slayt_yollari = [str(p) for p in slayt_listesi]
    else:
        # Standart carousel / otorite postu: native 4:5 besleme
        slayt_listesi = make_image.otorite_gonderi_slaytlari_uret(aktif_veri, cikti_onek=f"gonderi_{haber_id}", olcu=olcu)
        slayt_yollari = [str(p) for p in slayt_listesi]
    return slayt_yollari


def cdn_yukle(slayt_yollari: List[str]) -> List[str]:
    """Slaytları herkese açık CDN'e yükler (runner bağımsızlığı, kanal API'leri için); başarısızsa boş liste."""
    slayt_urlleri = []
    try:
        slayt_urlleri = upload_image.coklu_gorsel_yukle(slayt_yollari)
    except Exception as e:
        log.warning("Görseller CDN'e yüklenemedi: %s", e)
    return slayt_urlleri
