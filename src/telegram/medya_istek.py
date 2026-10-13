"""
src/telegram/medya_istek.py — Tekil fotoğraf ve video gönderimi, medya isteği yeniden deneme motoru.

Katman 3 (etki). `_medya_post` hem tekil fotoğraf hem albüm (album.py) isteklerinin ortak, sınırlı süreli ve yeniden
denemeli HTTP çağrısıdır. Kardeş modül işlevleri `istemci.xxx()` biçiminde çağrılır (testlerin yamaları her yerde geçsin).
"""

from __future__ import annotations

import html
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from . import istemci

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------------------------------------------
# MEDYA GÖNDERİMİ (tekil fotoğraf ve albüm)
#
# NİYE (2026-10-12): günlük içeriğin albüm yüklemesi 60 sn okuma zaman aşımına uğradı (Actions logu: "Yerel medya grubu
# istisnası ... Read timed out"). Eski yedek yol yerel dosya yollarını Telegram'a "URL" diye gönderip sessizce 400 aldı;
# albüm hiç gelmedi, kimseye haber verilmedi. Artık: her istek sınırlı süreyle ve yeniden denenerek yapılır
# (429'da retry_after, 5xx/ağ hatasında artan bekleme), yerel albüm → URL albüm → indirip yükle → tek tek gönderim
# sırasıyla düşülür ve hiçbiri tutmazsa hata günlüğüne yazılır.
# ---------------------------------------------------------------------------------------------------------------
MEDYA_ZAMAN_ASIMI = (10, 40)   # (bağlanma, okuma) saniye — eskiden tek parça 60 sn'ydi, bir kez denenip bırakılıyordu
MEDYA_DENEME = 2               # tek istek için deneme sayısı
MEDYA_TOPLAM_SURE = 240        # albüm stratejileri için toplam bütçe (sn); tek tek gönderim ek 120 sn daha alabilir
_MEDYA_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}


def _cevap_json(r: Any) -> Dict[str, Any]:
    try:
        veri = r.json()
    except Exception:  # noqa: BLE001 — JSON olmayan cevap (HTML hata sayfası vb.)
        return {}
    return veri if isinstance(veri, dict) else {}


def _cevap_ayrintisi(r: Any) -> str:
    """Telegram'ın hata cevabından kısa, kayda geçecek metin: '[400] Bad Request: ...'."""
    aciklama = _cevap_json(r).get("description")
    if not isinstance(aciklama, str) or not aciklama:
        metin = getattr(r, "text", "")
        aciklama = metin if isinstance(metin, str) else ""
    return f"[{getattr(r, 'status_code', '?')}] {aciklama[:200]}"


def _duz_metin(metin: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", metin or ""))


def _medya_post(url: str, hazirla: Any, *, etiket: str, bitis: Optional[float] = None,
                deneme: int = MEDYA_DENEME) -> Tuple[Optional[Any], str]:
    """sendPhoto / sendMediaGroup isteğini yeniden deneyerek yapar. Döner: (cevap | None, hata_metni).

    `hazirla(duz_metin)` her denemede yeniden çağrılır ve (requests.post argümanları, kapat) döner: dosya tutamaçları
    her denemede baştan açılır (eski kod aynı tutamaçları geri sarıyordu). Başlık HTML'i Telegram'ca ayrıştırılamazsa
    bir sonraki deneme düz metinle yapılır ve deneme hakkı harcamaz.
    Kalıcı hatada (400 vb.) yeniden denemez: aynı istek aynı cevabı alır.
    """
    duz = False
    son_hata = ""
    n = 0
    while n < deneme:
        if n > 0 and bitis is not None and time.monotonic() > bitis:
            son_hata = son_hata or "süre bütçesi doldu"
            break
        n += 1
        try:
            argumanlar, kapat = hazirla(duz)
        except OSError as e:
            return None, f"dosya açılamadı: {e}"
        bekle = 3 * n
        try:
            r = requests.post(url, timeout=MEDYA_ZAMAN_ASIMI, **argumanlar)
        except requests.RequestException as e:
            son_hata = f"{type(e).__name__}: {e}"
            log.warning("Telegram %s ağ hatası (deneme %d/%d): %s", etiket, n, deneme, son_hata)
        else:
            if r.status_code == 200:
                return r, ""
            son_hata = _cevap_ayrintisi(r)
            if "can't parse entities" in son_hata.lower() and not duz:
                duz = True
                n -= 1
                continue
            if r.status_code == 429:
                retry_after = (_cevap_json(r).get("parameters") or {}).get("retry_after")
                bekle = min(int(retry_after) + 1, 30) if isinstance(retry_after, (int, float)) else bekle
                log.warning("Telegram %s hız sınırı (429), %d sn beklenecek (deneme %d/%d)", etiket, bekle, n, deneme)
            elif r.status_code >= 500:
                log.warning("Telegram %s sunucu hatası %s (deneme %d/%d)", etiket, son_hata, n, deneme)
            else:
                log.warning("Telegram %s reddedildi: %s", etiket, son_hata)
                return None, son_hata
        finally:
            try:
                kapat()
            except Exception:  # noqa: BLE001
                pass
        if n < deneme:
            time.sleep(bekle)
    return None, son_hata


def _bos() -> None:
    return None


def _foto_baytlari(kaynak: str) -> Optional[bytes]:
    """Yerel dosyanın ya da URL'nin baytları; alınamazsa None (çağıran URL'yi Telegram'a doğrudan verir)."""
    p = Path(kaynak)
    if p.exists() and p.is_file():
        try:
            return p.read_bytes()
        except OSError as e:
            log.warning("Yerel görsel dosyası okunamadı: %s", e)
            return None
    if kaynak.startswith(("http://", "https://")):
        try:
            r = requests.get(kaynak, headers=_MEDYA_UA, timeout=(10, 20))
            if r.status_code == 200 and r.content:
                return r.content
        except Exception as e:  # noqa: BLE001
            log.warning("Görsel URL indirilemedi (%s), Telegram'a doğrudan URL denenecek: %s", kaynak[:60], e)
    return None


def fotograf_gonder(
    foto_yolu_veya_url: Path | str,
    caption: str = "",
    reply_markup: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Tekil fotoğrafı Telegram'a gönderir (yerel dosya veya URL; zaman aşımı/429/5xx'te yeniden dener)."""
    token, chat_id = istemci._bot_bilgileri()
    if not token or not chat_id:
        return None

    url = istemci.TELEGRAM_API_URL.format(token=token, method="sendPhoto")
    url_str = str(foto_yolu_veya_url)
    foto_bytes = _foto_baytlari(url_str)

    def hazirla_fabrikasi(bayt: Optional[bytes]) -> Any:
        def hazirla(duz: bool) -> Tuple[Dict[str, Any], Any]:
            veri: Dict[str, Any] = {"chat_id": chat_id, "caption": _duz_metin(caption)[:1024] if duz else caption[:1024]}
            if not duz:
                veri["parse_mode"] = "HTML"
            if reply_markup:
                veri["reply_markup"] = json.dumps(reply_markup)
            if bayt:
                return {"data": veri, "files": {"photo": ("image.jpg", bayt, "image/jpeg")}}, _bos
            veri["photo"] = url_str
            return {"data": veri}, _bos
        return hazirla

    r, hata = _medya_post(url, hazirla_fabrikasi(foto_bytes), etiket="sendPhoto")
    if r is None and foto_bytes and url_str.startswith(("http://", "https://")):
        # İndirilen baytlar reddedildi (ör. boyut/biçim); Telegram'ın kendisi URL'den çekmeyi bir kez denesin
        r, hata = _medya_post(url, hazirla_fabrikasi(None), etiket="sendPhoto(url)", deneme=1)
    if r is None:
        log.error("Telegram fotoğraf gönderilemedi (%s): %s", url_str[:80], hata)
        return None
    return _cevap_json(r).get("result")


def video_gonder(
    video_yolu: Path | str,
    aciklama: Optional[str] = None,
    butonlar: Optional[Dict[str, Any] | List[List[Dict[str, Any]]]] = None,
) -> Optional[int]:
    """
    Üretilen MP4 Reels/video dosyasını Telegram grubuna gönderir.
    Instabot mimarisinden uyarlanmıştır.
    """
    token, chat_id = istemci._bot_bilgileri()
    if not token or not chat_id:
        return None

    p = Path(str(video_yolu))
    if not p.exists() or not p.is_file():
        log.error("Video dosyası bulunamadı: %s", video_yolu)
        return None

    url = istemci.TELEGRAM_API_URL.format(token=token, method="sendVideo")
    data: Dict[str, Any] = {"chat_id": chat_id}
    if aciklama:
        data["caption"] = aciklama[:1024]
        if "<" in aciklama and ">" in aciklama:
            data["parse_mode"] = "HTML"
    if butonlar:
        markup = butonlar if isinstance(butonlar, dict) and "inline_keyboard" in butonlar else {"inline_keyboard": butonlar}
        data["reply_markup"] = json.dumps(markup)

    for deneme in range(1, 4):
        try:
            with open(p, "rb") as f:
                r = requests.post(url, data=data, files={"video": f}, timeout=180)
            veri = r.json() if r.content else {}
            if not veri.get("ok"):
                if "can't parse entities" in (veri.get("description") or "").lower():
                    data.pop("parse_mode", None)
                    if data.get("caption"):
                        data["caption"] = html.unescape(re.sub(r"<[^>]+>", "", data["caption"]))
                    with open(p, "rb") as f2:
                        r2 = requests.post(url, data=data, files={"video": f2}, timeout=180)
                    veri2 = r2.json() if r2.content else {}
                    if veri2.get("ok"):
                        return veri2["result"]["message_id"]
                log.warning("Telegram video gönderme hatası (deneme %d/3): %s", deneme, veri.get("description", r.text[:200]))
                time.sleep(2 * deneme)
                continue
            return veri["result"]["message_id"]
        except Exception as e:
            log.warning("Telegram video gönderme istisnası (deneme %d/3): %s", deneme, e)
            if deneme < 3:
                time.sleep(2 * deneme)
    return None
