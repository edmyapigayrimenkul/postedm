"""
src/telegram/akislar/reels.py — Reels içeriği hazırlama ve onaya sunma.

Katman 4 (akış). Konudan Reels metni üretir, slaytları çizer, `onay.haber_onayina_sun` ile onaya sunar.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from ... import db, generate_text, konu_bankasi
from .. import istemci
from . import kapi, onay

log = logging.getLogger(__name__)


def reels_hazirla_ve_sun(konu_kodu: Optional[str] = None) -> bool:
    """Konu bankasından dikey Reels videosu üretip onaya sunar (bkz. _reels_hazirla_ve_sun)."""
    from ... import yeni_formatlar
    try:
        return _reels_hazirla_ve_sun(konu_kodu)
    except yeni_formatlar.EksikIcerik as e:
        log.warning("Reels eksik alan yüzünden durdu: %s", e)
        kapi._eksik_icerik_bildir(None, e)
        return False


def _reels_hazirla_ve_sun(konu_kodu: Optional[str] = None) -> bool:
    """
    Konu bankasından sıradaki konudan 9:16 dikey Reels içeriği üretir,
    slaytları Telegram grubuna görsel olarak gönderir ve haberle birebir aynı
    onay kartı ve buton yapısıyla onaya sunar.
    """
    istemci.mesaj_gonder("⏳ <b>EDM Reels Videosu (9:16 Dikey)</b> hazırlanıyor, lütfen bekleyin...")

    konu = konu_bankasi.sonraki_konu(format_turu="reels") if not konu_kodu else next((k for k in konu_bankasi.havuzu_yukle() if k["kod"] == konu_kodu), None)
    if not konu:
        istemci.mesaj_gonder("⚠️ Konu bankasında uygun konu bulunamadı.")
        return False

    konu_reels = dict(konu)
    bicim = konu_reels.get("bicim") or "dailybrief"

    veri = generate_text.konudan_uret(konu_reels)
    if not veri:
        istemci.mesaj_gonder("❌ Gemini metin üretemedi.")
        return False

    veri["format_turu"] = "reels"
    konu_kodu_val = konu["kod"] if not konu_kodu else konu_kodu
    orijinal_url = f"edm://reels/{konu_kodu_val}/{int(time.time())}"
    simdi = datetime.now(timezone.utc).isoformat()
    manset = generate_text.manset_birlestir(veri) or konu["baslik"]

    with db._baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet,
                                     eklenme_tarihi, onem_puani, kategori, manset, detay_metni,
                                     ig_caption, threads_metin, durum)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'yeni')""",
            (
                f"EDM Reels // {konu_kodu_val}",
                konu["baslik"],
                orijinal_url,
                konu.get("aci", ""),
                simdi,
                konu.get("onem_puani", 8),
                "REELS",
                manset,
                json.dumps(veri, ensure_ascii=False),
                veri.get("caption_instagram", ""),
                veri.get("caption_threads", ""),
            ),
        )
        haber_id = cur.lastrowid
        conn.commit()

    konu_bankasi.kullanildi_isaretle(konu_kodu_val, haber_id=haber_id, format_turu="reels")
    return onay.haber_onayina_sun(haber_id)
