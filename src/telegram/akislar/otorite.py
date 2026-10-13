"""
src/telegram/akislar/otorite.py — Format değiştirme ve otorite postu: mevcut içeriği başka biçimde yeniden sunar / konudan otorite postu üretir.

Katman 4 (akış).
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from ... import db, generate_text
from .. import istemci
from . import onay

log = logging.getLogger(__name__)


def format_degistir_ve_sun(haber_id: int, hedef_format: str) -> bool:
    """Onay bekleyen bir içeriğin görsel formatını anında değiştirip yeni önizlemeyi sunar."""
    haber = db.haber_getir(haber_id)
    if not haber:
        return False

    detay_metni = haber.get("detay_metni")
    veri = json.loads(detay_metni) if detay_metni else {}
    veri["format_turu"] = hedef_format
    db.haber_guncelle(haber_id, detay_metni=json.dumps(veri, ensure_ascii=False), slayt_yollari=None, slayt_urlleri=None, video_yolu=None)
    istemci.mesaj_gonder(f"🎨 Haber #{haber_id} <b>{hedef_format.upper()}</b> formatına dönüştürülüyor...")
    return onay.haber_onayina_sun(haber_id)


def otorite_postu_hazirla_ve_sor(konu: str, kategori_kodu: Optional[str] = None) -> bool:
    """Belirtilen hukuki, finansal veya sektörel bir konudan 4 slaytlık otorite postu üretip Telegram'a sunar."""
    istemci.mesaj_gonder(f"⏳ <b>'{konu[:60]}...'</b> konusu için EDM Otorite Carousel içeriği hazırlanıyor...")

    # 1. Gemini ile 4 slaytlık otorite içeriği üret
    veri = generate_text.otorite_icerigi_uret(konu, kategori_kodu=kategori_kodu)
    if not veri:
        istemci.mesaj_gonder("❌ Otorite içeriği üretilemedi. Gemini API yanıt vermedi.")
        return False

    # 2. Veritabanına kaydet
    orijinal_url = f"edm://otorite/{int(time.time())}"
    simdi = datetime.now(timezone.utc).isoformat()
    with db._baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet, eklenme_tarihi, onem_puani, kategori, manset, detay_metni, ig_caption, threads_metin, durum)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'yeni')""",
            (
                "EDM Otorite Masası",
                konu,
                orijinal_url,
                veri.get("spot", ""),
                simdi,
                veri.get("onem_puani", 9),
                veri.get("kategori_kodu", "TAPU_VE_HUKUK"),
                generate_text.manset_birlestir(veri) or konu,
                json.dumps(veri, ensure_ascii=False),
                veri.get("caption_instagram", ""),
                veri.get("caption_threads", ""),
            ),
        )
        haber_id = cur.lastrowid
        conn.commit()

    # 3. Onaya sun
    return onay.haber_onayina_sun(haber_id)
