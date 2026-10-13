"""
src/telegram/akislar/kapi.py — Yayın kapısı: denetimden geçmeyen içerik onaya bile sunulmaz; eksik alan bildirimi.

Katman 4 (akış). Kapı KAPALI başarısız olur (denetim çalışamazsa içerik sunulmaz) — bkz. MEMORY.md §8.
"""

from __future__ import annotations

import html
import logging
from typing import Any, Dict, List, Optional, Tuple

from ... import db
from .. import istemci

log = logging.getLogger(__name__)


def _denetim_verisi(haber: Dict[str, Any], otorite_verisi: Any) -> Dict[str, Any]:
    """Denetlenecek içerik: görsel verisi + YAYINLANACAK caption'lar.

    Caption DB'den okunur; elle düzenlenmiş olabilir ve yayına giden odur.
    """
    veri = dict(otorite_verisi) if isinstance(otorite_verisi, dict) else {
        "manset": haber.get("manset") or haber.get("orijinal_baslik") or "",
        "spot": haber.get("orijinal_ozet") or "",
    }
    if haber.get("ig_caption"):
        veri["caption_instagram"] = haber["ig_caption"]
    if haber.get("threads_metin"):
        veri["caption_threads"] = haber["threads_metin"]
    return veri


def yayin_kapisi(haber_id: int, haber: Dict[str, Any], veri: Dict[str, Any],
                 durum_yaz: bool = True, anlam_denetimi: bool = True) -> Tuple[bool, List[str]]:
    """Kritik bulgu varsa içeriği durdurur. Döner: (geçti_mi, uyarılar).

    Kapı KAPALI başarısız olur: denetim çalışamazsa içerik de sunulmaz.
    Yalan bilgiye müsamaha yok (2026-09-24). `durum_yaz=False`: içerik bazı
    kanallarda zaten yayındaysa durumu ezilmez, yalnızca yeni kanala gitmez.
    `anlam_denetimi=False`: yayın anında yalnız ⛔ bakılır, ikinci modele (anlam kayması) sorulmaz.
    """
    from ... import dogrula
    try:
        uyarilar = dogrula.icerigi_denetle(veri, haber, anlam=anlam_denetimi)
    except Exception as e:
        log.exception("Denetim çalıştırılamadı (#%s)", haber_id)
        uyarilar = [f"⛔ DENETİM ÇALIŞMADI: {type(e).__name__} — denetlenmemiş içerik sunulmaz."]
    if not dogrula.kritik_var(uyarilar):
        return True, uyarilar
    log.warning("İçerik #%s yayın kapısında durdu: %s", haber_id, "; ".join(uyarilar))
    if durum_yaz:
        db.haber_guncelle(haber_id, durum="engellendi")
    istemci.mesaj_gonder(
        dogrula.yayin_engeli_metni(haber_id, uyarilar),
        reply_markup={"inline_keyboard": [[
            {"text": "🔄 Sıradaki konudan üret", "callback_data": "hizli_uret:rotasyon"},
        ]]},
    )
    try:
        from ... import db_senkron
        db_senkron.hemen_kaydet(f"db: icerik #{haber_id} denetimde durduruldu")
    except Exception as e:
        log.warning("Hemen kaydetme adımı atlandı: %s", e)
    return False, uyarilar


def _eksik_icerik_bildir(haber_id: Optional[int], hata: Exception) -> None:
    from ... import make_image
    if haber_id:
        db.haber_guncelle(haber_id, durum="engellendi")
    if isinstance(hata, make_image.TasmaHatasi):
        aciklama = ("<i>Metin okunabilir en küçük puntoda bile karta sığmadı. Kutunun altına "
                    "giren ya da kırpılan metin yayınlanmaz (#243'te tanımın son satırları "
                    "kutunun arkasında kalmıştı).</i>")
    else:
        aciklama = ("<i>Model formatın zorunlu alanını üretmedi. Boş alan koddaki genel bir "
                    "cümleyle doldurulmaz — o yol #157'de alakasız bir 'Yargıtay hükmü' yayınlatmıştı.</i>")
    istemci.mesaj_gonder(
        f"🛑 <b>İçerik{f' #{haber_id}' if haber_id else ''} durduruldu:</b> {html.escape(str(hata))}.\n"
        + aciklama,
        reply_markup={"inline_keyboard": [[
            {"text": "🔄 Sıradaki konudan üret", "callback_data": "hizli_uret:rotasyon"},
        ]]},
    )
