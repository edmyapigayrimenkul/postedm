"""
src/telegram/istemci.py — Telegram Bot API istemcisi (metin gönderme, düzenleme, silme).

Katman 3 (etki). Burası Telegram'a giden tek HTTP kapısıdır (`_istek`): 4096/1024 karakter ve 64 bayt düğme sınırı,
429/5xx yeniden deneme, HTML ayrıştırma hatasında düz metne düşme ve supergroup göçü burada çözülür.
Fotoğraf/video/albüm için `medya_istek.py` ve `album.py`; `telegram_bot` eski adları buradan yeniden dışa aktarır.
"""

from __future__ import annotations

import html
import logging
import re
import time
from typing import Any, Dict, Optional

import requests

from .. import config

log = logging.getLogger(__name__)
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"


def _bot_bilgileri() -> tuple[str, str]:
    token = config.env_al("TELEGRAM_BOT_TOKEN")
    chat_id = config.env_al("TELEGRAM_CHAT_ID")
    return token, chat_id


def _istek(metot: str, **parametreler: Any) -> Optional[Dict[str, Any]]:
    """Telegram API metotlarını çağırır; 429, 502/504 ve HTML ayrıştırma hatalarını otomatik kurtarır."""
    token, chat_id = _bot_bilgileri()
    if not token:
        log.warning("Telegram bot token eksik (.env kontrol edin).")
        return None

    if "chat_id" not in parametreler and chat_id:
        parametreler["chat_id"] = chat_id

    url = TELEGRAM_API_URL.format(token=token, method=metot)

    # 4096 ve 1024 karakter sınır koruması
    if "text" in parametreler and isinstance(parametreler["text"], str) and len(parametreler["text"]) > 4096:
        parametreler["text"] = parametreler["text"][:4093] + "..."
    if "caption" in parametreler and isinstance(parametreler["caption"], str) and len(parametreler["caption"]) > 1024:
        parametreler["caption"] = parametreler["caption"][:1021] + "..."

    # Buton 64-bayt koruması (BUTTON_DATA_INVALID önlemi)
    if "reply_markup" in parametreler and isinstance(parametreler["reply_markup"], dict):
        klavye = parametreler["reply_markup"].get("inline_keyboard")
        if isinstance(klavye, list):
            for satir in klavye:
                if isinstance(satir, list):
                    for btn in satir:
                        if isinstance(btn, dict) and "callback_data" in btn:
                            cb = str(btn["callback_data"])
                            cb_b = cb.encode("utf-8")
                            if len(cb_b) > 64:
                                log.warning("Telegram callback_data 64 bayt sınırını aştı (%d bayt): %s", len(cb_b), cb)
                                btn["callback_data"] = cb_b[:64].decode("utf-8", errors="ignore")

    # None değerli parametreleri payload'dan temizle (özellikle reply_markup=None Telegram API'de 400 Bad Request hatası verir)
    parametreler = {k: v for k, v in parametreler.items() if v is not None}

    for deneme in range(1, 4):
        try:
            cevap = requests.post(url, json=parametreler, timeout=25)
        except requests.RequestException as e:
            log.warning("Telegram ağ hatası (%s, deneme %d/3): %s", metot, deneme, e)
            time.sleep(2 * deneme)
            continue

        veri = cevap.json() if cevap.content else {}
        if veri.get("ok"):
            return veri.get("result")

        # 1. Supergroup göçü (migrate_to_chat_id)
        yeni_id = (veri.get("parameters") or {}).get("migrate_to_chat_id")
        if yeni_id:
            log.info("Telegram supergroup göçü: %s -> %s", chat_id, yeni_id)
            parametreler["chat_id"] = str(yeni_id)
            continue

        # 2. Rate limit (429) retry_after beklemesi
        retry_after = (veri.get("parameters") or {}).get("retry_after")
        if retry_after:
            bekle = min(int(retry_after) + 1, 60)
            log.warning("Telegram rate limit (429), %d sn bekleniyor...", bekle)
            time.sleep(bekle)
            continue

        # 3. Geçici ağ ve sunucu hataları (500, 502, 503, 504)
        if cevap.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 * deneme)
            continue

        aciklama = (veri.get("description") or "").lower()

        # 4. HTML parse hatası: parse_mode kaldırılıp düz metinle anında kurtarma
        if cevap.status_code == 400 and ("can't parse entities" in aciklama or "entity" in aciklama):
            if parametreler.get("parse_mode"):
                log.warning("Telegram HTML parse hatası (%s), düz metinle kurtarılıyor: %s", metot, veri.get("description"))
                parametreler.pop("parse_mode", None)
                if "text" in parametreler and isinstance(parametreler["text"], str):
                    parametreler["text"] = html.unescape(re.sub(r"<[^>]+>", "", parametreler["text"]))
                if "caption" in parametreler and isinstance(parametreler["caption"], str):
                    parametreler["caption"] = html.unescape(re.sub(r"<[^>]+>", "", parametreler["caption"]))
                continue

        # 5. Önemsiz/beklenen durum hataları
        if "message is not modified" in aciklama or "message to delete not found" in aciklama:
            return None

        log.error("Telegram API hatası [%d] (%s): %s", cevap.status_code, metot, veri.get("description"))
        break

    return None


def mesaj_gonder(
    metin: str,
    reply_markup: Optional[Dict[str, Any]] = None,
    butonlar: Optional[Dict[str, Any]] = None,
    html: bool = True,
) -> Optional[Dict[str, Any]]:
    """Telegram grubuna metin mesajı gönderir (HTML parse hatası ve karakter taşma korumalı)."""
    markup = reply_markup or butonlar
    guvenli_metin = metin[:4096] if isinstance(metin, str) else str(metin)[:4096]
    payload: Dict[str, Any] = {
        "text": guvenli_metin,
        "disable_web_page_preview": True,
    }
    if html:
        payload["parse_mode"] = "HTML"
    if markup:
        payload["reply_markup"] = markup

    return _istek("sendMessage", **payload)


def mesaji_sil(mesaj_id: int) -> bool:
    """Belirtilen mesajı siler; mesaj zaten silinmişse çökmeden False döner."""
    res = _istek("deleteMessage", message_id=mesaj_id)
    return bool(res)


def mesaji_guncelle(mesaj_id: int, metin: str, reply_markup: Optional[Dict[str, Any]] = None) -> bool:
    """Var olan mesajı günceller; 'message is not modified' durumunda çökmez."""
    payload: Dict[str, Any] = {
        "message_id": mesaj_id,
        "text": metin,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    res = _istek("editMessageText", **payload)
    return bool(res)


def menuyu_degistir(mesaj_id: int, reply_markup: Dict[str, Any]) -> bool:
    """Mesaj metnine dokunmadan yalnızca butonları (inline_keyboard) günceller."""
    res = _istek("editMessageReplyMarkup", message_id=mesaj_id, reply_markup=reply_markup)
    return bool(res)


def aciklama_metni_kutusu(metin: str) -> str:
    """Telegram'da tek dokunuşla panoya kopyalanabilir HTML kod bloğu oluşturur."""
    temiz = html.escape(metin.strip())
    return f"<pre><code>{temiz}</code></pre>"
