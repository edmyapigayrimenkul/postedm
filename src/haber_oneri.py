"""
haber_oneri.py — Taze emlak haberlerini Telegram'a ÖNERİ olarak düşürür.

2026-09-24 kararı: içerik günde bir; emlak haberleri içerikten bağımsız, günde
birkaç kez taranıp gruba öneri olarak gelir. Hangi haberin içeriğe çevrileceğine
insan karar verir ("📝 İçeriğe çevir"), sistem değil.

Neden triyaj burada yok: eski akışta LLM triyajı haberi hem süzüyor hem içeriğe
çeviriyordu ve 14 günde 98 haberin hiçbiri geçmedi; tek "haber" diye çıkanlar
iki deneme kaydıydı (#170, #171). Öneri ucuz ve kural tabanlı; triyaj yalnızca
insan "İçeriğe çevir" dediğinde çalışır ve orada da haberde doğrulanabilir bir
kural/süre/oran yoksa içerik üretmeyi reddeder.

Tarih her öneride yazılır: haberin yaşı, içeriğe çevirip çevirmeme kararının
yarısıdır.
"""

from __future__ import annotations

import html
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from . import db, fetch_news, sutun

log = logging.getLogger(__name__)

# Kural tabanlı önem puanı (haber_puanlama). Eski içerik eşiği 9'du; öneriye
# insan baktığı için eşik daha düşük — config'deki haberler.onem_puani_esigi.
ONERI_ESIGI = 7
TAZELIK_SAAT = 36
TUR_BASI_AZAMI = 4
GUNLUK_AZAMI = 12

_AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
          "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
_GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
TR = timezone(timedelta(hours=3))


def tarih_metni(iso: Optional[str], simdi: Optional[datetime] = None) -> str:
    """'2026-09-24T11:05:00+00:00' → '24 Eylül 2026 Perşembe, 14:05 · 3 saat önce' (TR saati)."""
    try:
        dt = datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return "tarih bilinmiyor"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    yerel = dt.astimezone(TR)
    simdi = simdi or datetime.now(timezone.utc)
    fark = simdi - dt
    saat = int(fark.total_seconds() // 3600)
    if fark.total_seconds() < 3600:
        yas = f"{max(1, int(fark.total_seconds() // 60))} dakika önce"
    elif saat < 48:
        yas = f"{saat} saat önce"
    else:
        yas = f"{saat // 24} gün önce"
    return (f"{yerel.day} {_AYLAR[yerel.month - 1]} {yerel.year} {_GUNLER[yerel.weekday()]}, "
            f"{yerel:%H:%M} · {yas}")


def _gunluk_sayac_anahtari(simdi: datetime) -> str:
    return simdi.astimezone(TR).date().isoformat()


def _bugun_onerilen(simdi: datetime) -> int:
    ham = str(db.ayar_oku("haber_oneri_gunluk") or "")
    gun, _, sayi = ham.partition(":")
    return int(sayi) if gun == _gunluk_sayac_anahtari(simdi) and sayi.isdigit() else 0


def _sayaci_artir(simdi: datetime, adet: int) -> None:
    db.ayar_yaz("haber_oneri_gunluk", f"{_gunluk_sayac_anahtari(simdi)}:{_bugun_onerilen(simdi) + adet}")


def adaylari_sec(limit: int) -> List[Dict[str, Any]]:
    """Önerilecek haberler: taze, rehber değil, eşiği geçen; en yüksek puan önce."""
    adaylar = []
    for h in db.bekleyen_haberleri_getir(limit=60):
        if (h.get("kategori") or "") == "rehber":
            continue  # rehber makaleleri haftalık konu madenciliğine gidiyor
        if fetch_news._saat_farki_saat(h.get("yayin_tarihi") or "") > TAZELIK_SAAT:
            continue
        if int(h.get("onem_puani") or 0) < ONERI_ESIGI:
            continue
        adaylar.append(h)
    adaylar.sort(key=lambda h: (int(h.get("onem_puani") or 0), h.get("yayin_tarihi") or ""), reverse=True)
    return adaylar[:max(0, limit)]


def oneri_mesaji(haber: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    sutun_adi = sutun.SUTUN_ADLARI.get(sutun.sutun_bul(haber.get("kategori")) or "", "")
    ozet = (haber.get("orijinal_ozet") or haber.get("makale_metni") or "").strip()
    if len(ozet) > 320:
        ozet = ozet[:320].rsplit(" ", 1)[0] + "…"
    etiket = " · ".join(x for x in (html.escape(haber.get("kaynak") or ""), html.escape(sutun_adi),
                                    f"puan {haber.get('onem_puani')}") if x)
    metin = (
        f"📰 <b>Haber önerisi</b> · #{haber['id']}\n"
        f"<b>{html.escape(haber.get('orijinal_baslik') or '')}</b>\n\n"
        f"🗓 {tarih_metni(haber.get('yayin_tarihi'))}\n"
        f"🏷 {etiket}\n"
    )
    if ozet:
        metin += f"\n{html.escape(ozet)}\n"
    if haber.get("orijinal_url"):
        metin += f"\n🔗 <a href=\"{html.escape(haber['orijinal_url'], quote=True)}\">Haberi kaynağında aç</a>"
    klavye = {"inline_keyboard": [[
        {"text": "📝 İçeriğe çevir", "callback_data": f"haber_uret:{haber['id']}"},
        {"text": "✖ Geç", "callback_data": f"haber_gec:{haber['id']}"},
    ]]}
    return metin, klavye


def onerileri_gonder(tara: bool = True, bos_ise_bildir: bool = False) -> int:
    """RSS'i tarar, taze adayları gruba öneri olarak gönderir. Gönderilen adedi döner."""
    from . import telegram_bot

    if tara:
        yeni = fetch_news.rss_tara()
        log.info("RSS taraması: %d yeni kayıt", len(yeni))

    simdi = datetime.now(timezone.utc)
    kalan = GUNLUK_AZAMI - _bugun_onerilen(simdi)
    if kalan <= 0:
        log.info("Günlük öneri sınırı (%d) doldu.", GUNLUK_AZAMI)
        return 0

    gonderilen = 0
    for h in adaylari_sec(min(TUR_BASI_AZAMI, kalan)):
        metin, klavye = oneri_mesaji(h)
        if telegram_bot.mesaj_gonder(metin, reply_markup=klavye):
            db.haber_guncelle(h["id"], durum="onerildi")
            gonderilen += 1
    if gonderilen:
        _sayaci_artir(simdi, gonderilen)
    elif bos_ise_bildir:
        telegram_bot.mesaj_gonder(
            f"📭 Şu an önerilecek taze haber yok (son {TAZELIK_SAAT} saat, puan ≥ {ONERI_ESIGI})."
        )
    log.info("%d haber önerisi gönderildi.", gonderilen)
    return gonderilen


def haberden_icerige(haber_id: int) -> bool:
    """"📝 İçeriğe çevir": triyaj haberden brief çıkarır, içerik onaya sunulur.

    Triyaj reddederse içerik ÜRETİLMEZ ve gerekçe gruba yazılır: haberde metinden
    alıntılanabilir somut bir kural, süre ya da oran yoksa yazılacak her şey
    modelin tahmini olur.
    """
    from . import haber_triyaj, telegram_bot

    haber = db.haber_getir(haber_id)
    if not haber:
        telegram_bot.mesaj_gonder(f"⚠️ Haber #{haber_id} bulunamadı (14 günden eskiyse havuzdan silinmiş olabilir).")
        return False
    if haber.get("durum") not in ("onerildi", "yeni"):
        telegram_bot.mesaj_gonder(
            f"ℹ️ Haber #{haber_id} zaten işlenmiş (durum: <code>{html.escape(str(haber.get('durum')))}</code>)."
        )
        return False

    brief = haber_triyaj.triyaj_et(haber, asgari_guven=0)
    if not brief:
        gerekce = haber.get("_red_gerekcesi") or "triyaj yanıtı alınamadı"
        db.haber_guncelle(haber_id, durum="elendi")
        telegram_bot.mesaj_gonder(
            f"🚫 <b>Haber #{haber_id} içeriğe çevrilmedi.</b>\n"
            f"Neden: {html.escape(gerekce)}.\n"
            "<i>Haberde metinden alıntılanabilecek somut bir kural, süre ya da oran yoksa "
            "yazılacak her şey tahmin olur; yayınlamıyoruz.</i>"
        )
        return False
    return telegram_bot.haberden_icerik_hazirla(haber, brief)
