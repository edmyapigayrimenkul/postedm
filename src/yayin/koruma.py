"""
yayin/koruma.py — Durum koruması ve yayın kapısı.

Telegram'daki her buton, mesaj ne kadar eski olursa olsun buraya ulaşır. Önce içeriğin BUGÜNKÜ durumuna bakılır; butonun gösterdiği
değil (kurallar ve gerekçe: src/durum_kurali.py). Yayın kapısı (denetim) yayın anında da çalışır: kapıdan önce onaya sunulmuş ya da
onaydan sonra elle düzenlenmiş içerik denetimsiz çıkmasın.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Tuple

from .. import db, durum_kurali, telegram_bot
from .baglam import Istek
from .icerik import haber_taze

log = logging.getLogger(__name__)

# Yalnızca yayında OLMAYAN içeriğe uygulanabilen işlemler.
TASLAK_ISLEMLERI = frozenset({
    "reddet", "iptal", "cope_at", "yenile",
    "metin_ozetle", "metin_detaylandir", "metin_yenile",
    "foto_degistir", "foto_editoryal", "foto_gercek", "foto_stok", "foto_ai", "foto_ilk", "foto_adaylar",
})
# Her durumda anlamlı olan yönetim işlemleri. "tamamla" elle paylaşılan içeriği
# kaydetmenin yolu; kaldırma ise kendi içinde yayında olup olmadığına bakar.
YONETIM_ISLEMLERI = frozenset({"ertele", "kaldir", "sil", "manuel_paket", "metin_onizle", "tamamla", "manuel_tamam"})


def kontrol(istek: Istek) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """(devam_edilsin_mi, mevcut_kayit). İlanlarda kayıt None döner (ilan kimlikleri ayrı tabloda; bu koruma haber/reels içindir)."""
    if istek.tur not in ("haber", "reels"):
        return True, None

    hedef = istek.hedef
    ref_id = istek.ref_id
    mevcut = haber_taze(ref_id)
    if not mevcut:
        return True, None

    if hedef in TASLAK_ISLEMLERI:
        engel = durum_kurali.taslak_islem_engeli(mevcut, hedef)
    elif hedef in YONETIM_ISLEMLERI:
        engel = None
    else:
        engel = durum_kurali.yayin_engeli(mevcut)
    if engel:
        log.warning("Durum koruması işlemi durdurdu: #%s durum=%s hedef=%s", ref_id, mevcut.get("durum"), hedef)
        telegram_bot.mesaj_gonder(engel)
        db.wal_bosalt()
        return False, mevcut

    # Elle paylaşım paketi de yayındır — insan onu doğrudan paylaşıyor.
    if hedef not in TASLAK_ISLEMLERI and (hedef not in YONETIM_ISLEMLERI or hedef == "manuel_paket"):
        try:
            detay = json.loads(mevcut.get("detay_metni") or "null")
        except ValueError:
            detay = None
        gecti, _ = telegram_bot.yayin_kapisi(
            int(ref_id), mevcut, telegram_bot._denetim_verisi(mevcut, detay),
            durum_yaz=not durum_kurali.yayinda_mi(mevcut),
            anlam_denetimi=False,  # yayın anında uyarılar kullanılmaz; model çağrısı boşa gider
        )
        if not gecti:
            db.wal_bosalt()
            return False, mevcut
    return True, mevcut
