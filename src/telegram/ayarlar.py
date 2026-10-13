"""
src/telegram/ayarlar.py — Botun duraklatılması ve yayın kanallarının açık/kapalı ayarı.

Katman 0-1 (durum + kural): yalnız `db.ayar_*` okur/yazar ve düğme klavyesi üzerinde mantık yürütür; Telegram'a hiç yazmaz.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .. import db


# =========================================================================
# BOT YÖNETİMİ & DURAKLATMA (DATABASE DESTEKLİ)
# =========================================================================

def bot_duraklat(saat: int = 0) -> str:
    """Botu belirtilen saat kadar veya süresiz duraklatır."""
    if saat > 0:
        bitis = datetime.now(timezone.utc) + timedelta(hours=saat)
        db.ayar_yaz("bot_duraklatildi_bitis", bitis.isoformat())
        return f"{saat} saat"
    else:
        db.ayar_yaz("bot_duraklatildi_bitis", "suresiz")
        return "süresiz"


def bot_devam_et() -> bool:
    """Duraklatılmış botu tekrar aktif eder."""
    db.ayar_yaz("bot_duraklatildi_bitis", "")
    return True


def bot_duraklatildi_mi() -> Tuple[bool, str]:
    """Botun duraklatılma durumunu ve kalan süreyi döner."""
    deger = db.ayar_oku("bot_duraklatildi_bitis")
    if not deger:
        return False, ""
    if deger == "suresiz":
        return True, "Süresiz"
    try:
        bitis = datetime.fromisoformat(deger)
        simdi = datetime.now(timezone.utc)
        if simdi >= bitis:
            db.ayar_yaz("bot_duraklatildi_bitis", "")
            return False, ""
        fark = bitis - simdi
        toplam_dakika = int(fark.total_seconds() / 60)
        saat = toplam_dakika // 60
        dakika = toplam_dakika % 60
        kalan = f"{saat} sa {dakika} dk" if saat > 0 else f"{dakika} dk"
        return True, kalan
    except Exception:
        return False, ""


# =========================================================================
# KANAL TOGGLE & MENÜ SİSTEMİ (INSTABOT MİMARİSİ)
# =========================================================================

def varsayilan_kanallar() -> Dict[str, bool]:
    """Aktif kanalları ayarlar tablosundan okur veya varsayılanı döner."""
    kayitli = db.ayar_oku("aktif_kanallar")
    if kayitli:
        try:
            return json.loads(kayitli)
        except Exception:
            pass
    return {
        "ig": True, "reels": False, "story": True, "threads": True,
        "facebook": True, "youtube": True, "tiktok": True, "linkedin": True,
    }


def kanal_ayarla(kanal: str, aktif: bool) -> Dict[str, bool]:
    """Kanal durumunu günceller ve kaydeder.
    Kural: Bir içerik ya gönderi (ig) ya da Reels olarak paylaşılır.
    """
    kanallar = varsayilan_kanallar()
    kanallar[kanal] = aktif
    if aktif and kanal == "reels":
        kanallar["ig"] = False
    elif aktif and kanal == "ig":
        kanallar["reels"] = False
    db.ayar_yaz("aktif_kanallar", json.dumps(kanallar))
    return kanallar


def secili_kanallari_cikar(klavye: Optional[List[List[Dict[str, Any]]]]) -> List[str]:
    """Inline keyboard'dan seçili kanalları (✅ ile başlayan) listeler."""
    if not klavye:
        return ["ig", "story", "threads", "facebook", "youtube", "tiktok", "linkedin"]
    secili = []
    bulundu = False
    for satir in klavye:
        for btn in satir:
            cb = str(btn.get("callback_data", ""))
            if cb.startswith("kanal:") or cb.startswith("kanal_toggle:"):
                bulundu = True
                if str(btn.get("text", "")).startswith("✅"):
                    kanal_adi = cb.replace("kanal_toggle:", "").replace("kanal:", "")
                    secili.append(kanal_adi)
    if not bulundu:
        return ["ig", "story", "threads", "facebook", "youtube", "tiktok", "linkedin"]
    return secili


def kanal_toggle(klavye: List[List[Dict[str, Any]]], hedef_kanal: str) -> List[List[Dict[str, Any]]]:
    """Klavye içerisindeki hedef kanalın onay durumunu (✅ <-> ⬜) tersine çevirir.
    Instagram Kuralı: Bir içerik ya gönderi (IG) ya da Reels olarak paylaşılır.
    Reels aktif edilirse IG kapatılır, IG aktif edilirse Reels kapatılır.
    """
    hedef_suan_secili = False
    for satir in klavye:
        for btn in satir:
            cb = str(btn.get("callback_data", ""))
            if cb in (f"kanal:{hedef_kanal}", f"kanal_toggle:{hedef_kanal}"):
                text = str(btn.get("text", ""))
                hedef_suan_secili = text.startswith("✅")
                break

    hedef_yeni_secili = not hedef_suan_secili

    yeni_klavye = []
    for satir in klavye:
        yeni_satir = []
        for btn in satir:
            b = dict(btn)
            cb = str(b.get("callback_data", ""))
            bu_kanal = cb.replace("kanal_toggle:", "").replace("kanal:", "")
            if cb.startswith("kanal:") or cb.startswith("kanal_toggle:"):
                text = str(b.get("text", ""))
                label = text.lstrip("✅⬜ ").strip()
                if bu_kanal == hedef_kanal:
                    b["text"] = f"{'✅' if hedef_yeni_secili else '⬜'} {label}"
                elif hedef_yeni_secili and hedef_kanal == "reels" and bu_kanal == "ig":
                    # Kural: Reels seçilince IG gönderi deaktif edilir
                    b["text"] = f"⬜ {label}"
                elif hedef_yeni_secili and hedef_kanal == "ig" and bu_kanal == "reels":
                    # Kural: IG gönderi seçilince Reels deaktif edilir
                    b["text"] = f"⬜ {label}"
            yeni_satir.append(b)
        yeni_klavye.append(yeni_satir)
    return yeni_klavye
