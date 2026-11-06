"""
src/ayar.py — Telegram çalışma ayarları ve Tam Otomatik ⇄ Yarı Otomatik (Onaylı) mod yönetimi.

`.github/workflows/yayinla.yml` (`bot_yonetim` › `ayar_degistir`) ve `src/telegram/menuler_panel.py`
(`ayar_menusu`) bu modülü çağırır.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from . import db
from .telegram import ayarlar, istemci

log = logging.getLogger(__name__)

DEGISTIRILEBILIR: Dict[str, Tuple[str, list[Any]]] = {
    "oto_yayin": ("🤖 Otomatik Yayın Modu", [True, False]),
    "reels_varsayilan": ("🎬 Varsayılan Reels Modu", [True, False]),
    "kanal_threads": ("🧵 Threads Paylaşımı", [True, False]),
    "kanal_fb": ("📘 Facebook Paylaşımı", [True, False]),
    "kanal_tiktok": ("🎵 TikTok Paylaşımı", [True, False]),
    "kanal_youtube": ("▶️ YouTube Shorts", [True, False]),
    "kanal_linkedin": ("💼 LinkedIn Paylaşımı", [True, False]),
}

VARSAYILANLAR: Dict[str, Any] = {
    "oto_yayin": True,
    "reels_varsayilan": False,
    "kanal_threads": True,
    "kanal_fb": True,
    "kanal_tiktok": True,
    "kanal_youtube": True,
    "kanal_linkedin": True,
}

_ACIK_DEGERLER = ("1", "true", "evet", "acik", "açık", "otomatik", "on")

_KANAL_HARITASI = {
    "kanal_threads": "threads",
    "kanal_fb": "facebook",
    "kanal_tiktok": "tiktok",
    "kanal_youtube": "youtube",
    "kanal_linkedin": "linkedin",
}


def _bool_coz(deger: Any, varsayilan: bool = True) -> bool:
    if isinstance(deger, bool):
        return deger
    metin = str(deger or "").strip().lower()
    if not metin:
        return varsayilan
    return metin in _ACIK_DEGERLER


def ayar_oku(anahtar: str) -> Any:
    """Belirtilen ayarın güncel değerini döner."""
    temiz = str(anahtar or "").strip().lower()
    if temiz not in DEGISTIRILEBILIR and temiz not in ("oto_yayin_modu", "mod"):
        return None
    if temiz in ("oto_yayin", "oto_yayin_modu", "mod"):
        return ayarlar.oto_yayin_modu_acik_mi()
    if temiz in _KANAL_HARITASI:
        kanallar = ayarlar.varsayilan_kanallar()
        return bool(kanallar.get(_KANAL_HARITASI[temiz], True))
    varsayilan = VARSAYILANLAR.get(temiz, False)
    kayitli = db.ayar_oku(f"ayar_{temiz}", varsayilan=None)
    if kayitli is None:
        kayitli = db.ayar_oku(temiz, varsayilan=None)
    if kayitli is None:
        return varsayilan
    return _bool_coz(kayitli, varsayilan)


def ayar_menusu() -> Dict[str, Any]:
    """Telegram /ayar komutu için veritabanındaki gerçek durumu yansıtan interaktif menü."""
    oto_acik = ayarlar.oto_yayin_modu_acik_mi()
    kanallar = ayarlar.varsayilan_kanallar()
    reels_varsayilan = _bool_coz(db.ayar_oku("ayar_reels_varsayilan"), False)

    def _satir(etiket: str, anahtar: str, acik: bool) -> list[dict[str, str]]:
        simge = "✅ AÇIK" if acik else "⬜ KAPALI"
        hedef = "false" if acik else "true"
        return [{"text": f"{simge} {etiket}", "callback_data": f"ayarsec:{anahtar}:{hedef}"}]

    mod_etiketi = (
        "🤖 Otomatik Yayın Modu (Tıkla → Yarı Otomatik)"
        if oto_acik
        else "👤 Yarı Otomatik / Onaylı Mod (Tıkla → Otomatik)"
    )
    mod_simge = "✅ AÇIK" if oto_acik else "⬜ KAPALI"
    mod_hedef = "false" if oto_acik else "true"

    return {
        "inline_keyboard": [
            [{"text": f"{mod_simge} {mod_etiketi}", "callback_data": f"ayarsec:oto_yayin:{mod_hedef}"}],
            _satir("🎬 Varsayılan Reels Modu", "reels_varsayilan", reels_varsayilan),
            _satir("🧵 Threads Paylaşımı", "kanal_threads", bool(kanallar.get("threads", True))),
            _satir("📘 Facebook Paylaşımı", "kanal_fb", bool(kanallar.get("facebook", True))),
            _satir("🎵 TikTok Paylaşımı", "kanal_tiktok", bool(kanallar.get("tiktok", True))),
            _satir("▶️ YouTube Shorts", "kanal_youtube", bool(kanallar.get("youtube", True))),
            _satir("💼 LinkedIn Paylaşımı", "kanal_linkedin", bool(kanallar.get("linkedin", True))),
            [{"text": "← Kontrol Paneli", "callback_data": "panel"}],
        ]
    }


def ayar_kaydet(anahtar: str, deger: Any, bildir: bool = True) -> bool:
    """Telegram'dan gelen çalışma ayarını veritabanına kaydeder ve durumu gruba bildirir."""
    temiz_anahtar = str(anahtar or "").strip().lower()
    if not temiz_anahtar or (temiz_anahtar not in DEGISTIRILEBILIR and temiz_anahtar not in ("oto_yayin_modu", "mod")):
        log.warning("İzin verilmeyen ayar anahtarı: %s", anahtar)
        return False

    acik = _bool_coz(deger, True)

    if temiz_anahtar in ("oto_yayin", "oto_yayin_modu", "mod"):
        ayarlar.oto_yayin_modu_ayarla(acik)
        if bildir:
            if acik:
                istemci.mesaj_gonder(
                    "🤖 <b>Çalışma Modu: TAM OTOMATİK</b>\n\n"
                    "Zamanlanmış içerikler (<b>10:00 Gönderi</b> · <b>12:30 Sözlük</b> · <b>19:00 Reels</b>) "
                    "denetim kapısından temiz geçerse doğrudan tüm kanallarda yayınlanır; görseller, "
                    "açıklama metni ve üretilen MP4 video her yayında gruba düşmeye devam eder.\n\n"
                    "<i>Yarı otomatik (onaylı) moda geçmek için <code>/onayli</code> yazabilir veya Panel/Ayarlar düğmesini kullanabilirsiniz.</i>"
                )
            else:
                istemci.mesaj_gonder(
                    "👤 <b>Çalışma Modu: YARI OTOMATİK (ONAYLI)</b>\n\n"
                    "Zamanlanmış tüm içerikler doğrudan yayınlanmaz; görseller ve butonlu onay kartı olarak bu gruba düşer. "
                    "Yalnızca siz onayladığınızda yayına çıkar.\n\n"
                    "<i>Tam otomatik moda dönmek için <code>/otomatik</code> yazabilir veya Panel/Ayarlar düğmesini kullanabilirsiniz.</i>"
                )
        return True

    if temiz_anahtar in _KANAL_HARITASI:
        kanal = _KANAL_HARITASI[temiz_anahtar]
        ayarlar.kanal_ayarla(kanal, acik)
        if bildir:
            istemci.mesaj_gonder(f"⚙️ <b>Varsayılan kanal ayarı güncellendi:</b> {kanal.upper()} → {'✅ Açık' if acik else '⬜ Kapalı'}")
        return True

    db.ayar_yaz(f"ayar_{temiz_anahtar}", "1" if acik else "0")
    if temiz_anahtar == "reels_varsayilan":
        ayarlar.kanal_ayarla("reels" if acik else "ig", True)
    if bildir:
        istemci.mesaj_gonder(f"⚙️ <b>Ayar kaydedildi:</b> <code>{temiz_anahtar}</code> → {'✅ Açık' if acik else '⬜ Kapalı'}")
    return True
