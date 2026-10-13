"""
telegram_bot.py — EDM Telegram Onay ve Yönetim Botu
Haber ve İlan önizlemelerini Telegram grubuna iletir, inline butonlarla onay alır.
Tek tıkla portföyden ilan seçip post üretme özelliğini yönetir.
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from . import config, db, fetch_listings, generate_text, komutlar, konu_bankasi, make_image, upload_image
from .sutun import SUTUN_ADLARI

log = logging.getLogger(__name__)

KOK = Path(__file__).resolve().parent.parent
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
    token, chat_id = _bot_bilgileri()
    if not token or not chat_id:
        return None

    url = TELEGRAM_API_URL.format(token=token, method="sendPhoto")
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
    token, chat_id = _bot_bilgileri()
    if not token or not chat_id:
        return None

    p = Path(str(video_yolu))
    if not p.exists() or not p.is_file():
        log.error("Video dosyası bulunamadı: %s", video_yolu)
        return None

    url = TELEGRAM_API_URL.format(token=token, method="sendVideo")
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


_son_medya_grubu_mesaj_idleri: List[int] = []


def son_medya_grubu_mesaj_idleri() -> List[int]:
    """Son BAŞARILI sendMediaGroup çağrısında dönen telegram message_id listesi (her çağrının başında sıfırlanır)."""
    return list(_son_medya_grubu_mesaj_idleri)


def _ayikla_medya_mesaj_idleri(resp: requests.Response) -> List[int]:
    global _son_medya_grubu_mesaj_idleri
    try:
        data = resp.json()
        if data.get("ok") and isinstance(data.get("result"), list):
            mids = [m["message_id"] for m in data["result"] if isinstance(m, dict) and "message_id" in m]
            if mids:
                _son_medya_grubu_mesaj_idleri = mids
                return mids
    except Exception:
        pass
    return []


def _yerel_dosya_bul(f_yol: Path | str) -> Optional[Path]:
    """Görselin bu makinedeki dosyası: doğrudan yol, yüklenen URL'nin yerel karşılığı ya da çıktı klasörlerinde ad eşleşmesi."""
    p = Path(str(f_yol))
    if p.exists() and p.is_file():
        return p
    try:
        yerel = upload_image.yerel_karsiligi(str(f_yol))
        if yerel and yerel.exists() and yerel.is_file():
            return yerel
    except Exception:  # noqa: BLE001
        pass
    temiz_ad = Path(str(f_yol).split("?")[0]).name
    for klasor in [Path("data/output"), Path("output")]:
        olasi = klasor / temiz_ad
        if olasi.exists() and olasi.is_file():
            return olasi
    return None


def _indir(url: str) -> Optional[bytes]:
    try:
        r = requests.get(url, headers=_MEDYA_UA, timeout=(10, 25))
        if r.status_code == 200 and r.content:
            return r.content
    except Exception as e:  # noqa: BLE001
        log.warning("Görsel indirilemedi (%s): %s", url[:60], e)
    return None


def _album_istegi(url: str, chat_id: str, ogeler: List[Tuple[str, Any]], caption: str, *,
                  etiket: str, bitis: float, deneme: int = MEDYA_DENEME) -> Tuple[Optional[Any], str]:
    """Bir sendMediaGroup isteği. `ogeler`: ('dosya', Path) | ('bayt', bytes) | ('url', str) çiftleri.
    Dosya ve bayt öğeleri multipart ile yüklenir (attach://), URL öğeleri Telegram'a çektirilir; ikisi karışabilir."""
    import io

    def hazirla(duz: bool) -> Tuple[Dict[str, Any], Any]:
        media: List[Dict[str, Any]] = []
        files: Dict[str, Any] = {}
        tutamaclar: List[Any] = []

        def kapat() -> None:
            for fh in tutamaclar:
                try:
                    fh.close()
                except Exception:  # noqa: BLE001
                    pass

        try:
            for idx, (tur, deger) in enumerate(ogeler):
                oge: Dict[str, Any] = {"type": "photo"}
                if tur == "url":
                    oge["media"] = str(deger)
                else:
                    ad = f"photo_{idx}"
                    oge["media"] = f"attach://{ad}"
                    if tur == "dosya":
                        fh = open(deger, "rb")
                        tutamaclar.append(fh)
                        files[ad] = (Path(deger).name, fh, "image/jpeg")
                    else:
                        files[ad] = (f"foto_{idx}.jpg", io.BytesIO(deger), "image/jpeg")
                if idx == 0 and caption:
                    oge["caption"] = _duz_metin(caption)[:1024] if duz else caption[:1024]
                    if not duz:
                        oge["parse_mode"] = "HTML"
                media.append(oge)
        except OSError:
            kapat()
            raise
        if files:
            return {"data": {"chat_id": chat_id, "media": json.dumps(media)}, "files": files}, kapat
        return {"json": {"chat_id": chat_id, "media": media}}, kapat

    return _medya_post(url, hazirla, etiket=etiket, bitis=bitis, deneme=deneme)


def medya_grubu_gonder(foto_yollari: List[Path | str], caption: str = "",
                       yedek_urller: Optional[List[str]] = None) -> List[int] | bool:
    """Carousel önizlemesi için albüm (medya grubu) gönderir. Döner: mesaj kimlikleri (başarı) ya da False.

    `yedek_urller`: aynı görsellerin herkese açık adresleri (ImgBB/R2), `foto_yollari` ile aynı sırada. Yerel yükleme
    tutmazsa Telegram bu adreslerden çeker; sayı eşleşmiyorsa (kısmi yükleme) güvenilmez, kullanılmaz.

    Sırayla denenir, biri tutunca durulur:
      1. Yerel dosyalar multipart ile (yeniden denemeli)
      2. URL albümü (Telegram görselleri kendisi çeker)
      3. URL'lerden indirip multipart yükleme (WEBPAGE_CURL_FAILED kurtarma)
      4. Fotoğrafları TEK TEK gönderme (başlık ilk giden fotoğrafta). Hepsi gitmezse gidenlerin kimlikleri döner;
         çağıran `len(sonuc) < len(foto_yollari)` ile eksik teslimi anlar.
    Zaman aşımı belirsizdir (Telegram isteği işlemiş ama cevap gelmemiş olabilir), bu yüzden nadiren aynı albüm iki kez
    düşebilir; albüm kaybolmasından iyidir. Hiçbiri tutmazsa hata günlüğüne yazılır ve False döner.
    """
    global _son_medya_grubu_mesaj_idleri
    _son_medya_grubu_mesaj_idleri = []  # eski çağrının kimlikleri bu içeriğe karışmasın
    token, chat_id = _bot_bilgileri()
    if not token or not chat_id or not foto_yollari:
        return False
    foto_yollari = list(foto_yollari)[:10]
    yedek = [str(u) for u in (yedek_urller or [])][:10]
    if len(yedek) != len(foto_yollari):
        yedek = []

    # Telegram sendMediaGroup minimum 2 medya gerektirir; tekil görsel (ör. sözlük kartı) sendPhoto ile gider.
    if len(foto_yollari) == 1:
        res = fotograf_gonder(foto_yollari[0], caption=caption)
        if not res and yedek:
            res = fotograf_gonder(yedek[0], caption=caption)
        if res and isinstance(res, dict) and "message_id" in res:
            _son_medya_grubu_mesaj_idleri = [res["message_id"]]
            return [res["message_id"]]
        if not res:
            _medya_hatasi_kaydet("tekil fotoğraf gönderilemedi")
        return bool(res)

    url = TELEGRAM_API_URL.format(token=token, method="sendMediaGroup")
    bitis = time.monotonic() + MEDYA_TOPLAM_SURE
    yereller = [_yerel_dosya_bul(fy) for fy in foto_yollari]
    hepsi_yerel = all(y is not None for y in yereller)
    hatalar: List[str] = []

    def basari(r: Any) -> List[int] | bool:
        mids = _ayikla_medya_mesaj_idleri(r)
        return mids if mids else True

    # 1. Yerel dosyalar. Yedek adres varsa tek deneme yeter: yükleme zaman aşımı çoğunlukla çıkış hattının yavaşlığıdır,
    # ikinci deneme de aynı hatta takılır; Telegram'ın görselleri kendi çekeceği URL yolu (2.) çoğu zaman anında tutar.
    if hepsi_yerel:
        r, hata = _album_istegi(url, chat_id, [("dosya", y) for y in yereller], caption, etiket="albüm(yerel)", bitis=bitis,
                                deneme=1 if yedek else MEDYA_DENEME)
        if r is not None:
            return basari(r)
        hatalar.append(f"yerel albüm: {hata}")

    # 2. URL albümü: girdinin kendisi URL ise o, değilse yedek adresler
    girdi_url_mi = all(str(f).startswith(("http://", "https://")) for f in foto_yollari)
    urller = [str(f) for f in foto_yollari] if girdi_url_mi else yedek
    if urller and time.monotonic() < bitis:
        r, hata = _album_istegi(url, chat_id, [("url", u) for u in urller], caption, etiket="albüm(url)", bitis=bitis)
        if r is not None:
            return basari(r)
        hatalar.append(f"url albümü: {hata}")

    # 3. URL'lerden indirip yükle (yerel dosya eksikse; hepsi yerelse 1. adım zaten aynı şeyi denedi)
    if urller and not hepsi_yerel and time.monotonic() < bitis:
        ogeler: List[Tuple[str, Any]] = []
        for yerel, u in zip(yereller, urller):
            if yerel is not None:
                ogeler.append(("dosya", yerel))
                continue
            bayt = _indir(u)
            if bayt is None:
                break
            ogeler.append(("bayt", bayt))
        if len(ogeler) == len(urller):
            r, hata = _album_istegi(url, chat_id, ogeler, caption, etiket="albüm(indir-yükle)", bitis=bitis)
            if r is not None:
                log.info("Albüm URL yerine indirilip yüklenerek iletildi.")
                return basari(r)
            hatalar.append(f"indir-yükle: {hata}")
        else:
            hatalar.append("indir-yükle: görseller indirilemedi")

    # 4. Tek tek
    teslim: List[int] = []
    ilk_basliksiz = True
    for i, yerel in enumerate(yereller):
        if time.monotonic() > bitis + 120:
            hatalar.append("tek tek: süre bütçesi doldu")
            break
        kaynak = yerel if yerel is not None else (urller[i] if urller else None)
        if kaynak is None:
            continue
        res = fotograf_gonder(kaynak, caption=caption if ilk_basliksiz else "")
        if res and isinstance(res, dict) and "message_id" in res:
            teslim.append(res["message_id"])
            ilk_basliksiz = False
    if teslim:
        _son_medya_grubu_mesaj_idleri = teslim
        if len(teslim) < len(foto_yollari):
            _medya_hatasi_kaydet(f"albüm eksik iletildi ({len(teslim)}/{len(foto_yollari)} fotoğraf): " + " | ".join(hatalar))
        else:
            log.warning("Albüm toplu gönderilemedi; fotoğraflar tek tek iletildi (%s)", " | ".join(hatalar))
        return teslim

    _medya_hatasi_kaydet("albüm hiçbir yolla iletilemedi: " + " | ".join(hatalar))
    return False


def _medya_hatasi_kaydet(ayrinti: str) -> None:
    """Teslim edilemeyen/eksik görseli kalıcı hata günlüğüne yazar (günlük rapor ve 'Ham Hata' düğmesi görsün)."""
    log.error("Telegram medya teslimi: %s", ayrinti)
    try:
        db.hata_kaydi_ekle("telegram.medya", "Görseller Telegram'a iletilemedi", "Slayt görselleri Telegram'a ulaşmadı.",
                           "Telegram yükleme/URL isteği zaman aşımı ya da reddedilme.", "yeniden_yayinla", False, ayrinti)
    except Exception as e:  # noqa: BLE001 — günlük yazılamasa da gönderim akışı sürsün
        log.warning("Medya hatası DB'ye yazılamadı: %s", e)


def slaytlari_gonder(foto_yollari: List[Path | str], basliklar: Optional[List[str]] = None) -> bool:
    """Instabot uyumluluk yardımcısı: Fotoğraf albümü (medya grubu) gönderir."""
    caption = basliklar[0] if basliklar else ""
    return medya_grubu_gonder(foto_yollari, caption=caption)


def mesaji_sil(mesaj_id: int) -> bool:
    """Belirtilen mesajı siler; mesaj zaten silinmişse çökmeden False döner."""
    res = _istek("deleteMessage", message_id=mesaj_id)
    return bool(res)


def icerik_onceki_mesajlarini_temizle(tur: str, referans_id: Any, haric_mesaj_id: Optional[int] = None) -> int:
    """
    Aynı içerik için daha önce Telegram grubuna gönderilmiş olan onay kartı
    ve hatırlatma mesajlarını siler; böylece chatte mükerrer kartlar ve kaos oluşmaz.
    """
    try:
        eski_idler = db.onay_mesajlarini_getir(tur, str(referans_id))
        silinen = 0
        for mid in eski_idler:
            if haric_mesaj_id and mid == haric_mesaj_id:
                continue
            try:
                if mesaji_sil(mid):
                    silinen += 1
                db.onay_mesaj_silindi_isaretle(mid)
            except Exception as e:
                log.warning("Mesaj #%d silinemedi: %s", mid, e)
        if silinen > 0:
            log.info("İçerik (%s #%s) için önceki %d adet mesaj Telegram'dan temizlendi.", tur, referans_id, silinen)
        return silinen
    except Exception as e:
        log.warning("Önceki mesajlar temizlenirken hata: %s", e)
        return 0


def son_mesajlari_sil(adet: int = 1) -> int:
    """
    Son onay isteklerine ait tüm Telegram mesajlarını (albüm slaytları ve onay kartları) siler.
    /sil komutu veya bot yönetim aksiyonu ile tetiklenir.
    """
    try:
        mids = db.son_onay_istegi_mesajlarini_getir(adet=adet)
        silinen = 0
        for mid in mids:
            try:
                if mesaji_sil(mid):
                    silinen += 1
                db.onay_mesaj_silindi_isaretle(mid)
            except Exception as e:
                log.warning("Mesaj #%d silinemedi: %s", mid, e)
        if silinen > 0:
            log.info("Son onay isteklerinden %d adet Telegram mesajı silindi.", silinen)
        return silinen
    except Exception as e:
        log.warning("Son mesajlar silinirken hata: %s", e)
        return 0



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


KANAL_ETIKETLERI = {
    "instagram": "Instagram Akış (4:5)",
    "ig": "Instagram Akış (4:5)",
    "instagram_story": "Instagram Story",
    "story": "Instagram Story",
    "facebook_story": "Facebook Story",
    "reels": "Instagram Reels (9:16)",
    "facebook_reels": "Facebook Reels",
    "facebook": "Facebook (Gönderi)",
    "threads": "Threads (@edmyapigayrimenkul)",
    "youtube": "YouTube Shorts",
    "shorts": "YouTube Shorts",
    "tiktok": "TikTok (@edmyapigayrimenkul)",
    "tt": "TikTok (@edmyapigayrimenkul)",
    "linkedin": "LinkedIn (@edmyapigayrimenkul)",
    "li": "LinkedIn (@edmyapigayrimenkul)",
}


def yayin_durum_metni_olustur(
    baslik: str,
    adim: int,
    toplam_adim: int,
    durum_haritasi: Dict[str, str],
    baslangic_ts: float = 0.0,
    is_telafi: bool = False,
) -> str:
    """
    Canlı paralel yayın ilerleme metnini ve platform durum listesini oluşturur.
    Instabot standardında: Her kanalın durumunu (⏳ Yükleniyor... / ✅ Yayında / ❌ Hata / ⏱️ Sırada) ve
    canlı ilerleme çubuğunu ([▰▰▱▱] %50) gösterir.
    """
    toplam = max(1, toplam_adim)
    ad = max(0, min(adim, toplam))
    dolu = "▰" * ad
    bos = "▱" * (toplam - ad)
    yuzde = int((ad / toplam) * 100)
    bar = f"<code>[{dolu}{bos}] %{yuzde} ({ad}/{toplam})</code>"

    tamamlandi = (ad == toplam and all(v not in ("⏱️ Sırada", "⏳ Yükleniyor...") for v in durum_haritasi.values()))

    if is_telafi:
        baslik_satiri = "⏳ <b>TELAFİ DAĞITIMI SÜRÜYOR...</b>"
    elif tamamlandi:
        baslik_satiri = "✅ <b>TÜM PLATFORMLARA AKTARIM TAMAMLANDI!</b>"
    else:
        baslik_satiri = "⏳ <b>YAYIN DAĞITIMI SÜRÜYOR (Paralel Motor)...</b>"

    satirlar = [baslik_satiri]
    if baslik:
        satirlar.append(f"📌 <b>{html.escape(baslik[:100])}</b>")
    satirlar.append("")
    satirlar.append(bar)
    satirlar.append("")
    satirlar.append("📱 <b>Platform Durumları:</b>")

    for k, durum in durum_haritasi.items():
        isim = KANAL_ETIKETLERI.get(k, k.upper())
        satirlar.append(f"• <b>{isim}:</b> {durum}")

    if baslangic_ts > 0:
        gecen = time.time() - baslangic_ts
        if tamamlandi:
            satirlar.append(f"\n⏱️ <i>Toplam Dağıtım Süresi: {gecen:.1f} sn • Tebrikler! 🎉</i>")
        else:
            satirlar.append(f"\n⏱️ <i>Geçen Süre: {gecen:.1f} sn</i>")

    return "\n".join(satirlar)


def canli_yayin_durumu_guncelle(
    mesaj_id: Optional[int],
    baslik: str,
    adim: int,
    toplam_adim: int,
    durum_haritasi: Dict[str, str],
    baslangic_ts: float = 0.0,
    is_telafi: bool = False,
) -> bool:
    """Paralel dağıtım sırasında onay mesajını anlık platform durumları ve ilerleme çubuğuyla canlı günceller."""
    if not mesaj_id:
        return False
    metin = yayin_durum_metni_olustur(
        baslik=baslik,
        adim=adim,
        toplam_adim=toplam_adim,
        durum_haritasi=durum_haritasi,
        baslangic_ts=baslangic_ts,
        is_telafi=is_telafi,
    )
    return mesaji_guncelle(mesaj_id, metin)


def sonucu_yaz(
    mesaj_id: Optional[int],
    metin: str,
    bildir: bool = False,
    reply_markup: Optional[Dict[str, Any]] = None,
    ek_dugmeler: Optional[List[List[Dict[str, str]]]] = None,
) -> bool:
    """
    Onay mesajını sonuçla günceller, butonları canlı linkler veya telafi tuşlarıyla değiştirir.
    bildir=True ise ayrıca grupta yeni bir mesaj olarak iletir.
    """
    if not reply_markup and ek_dugmeler:
        reply_markup = {"inline_keyboard": ek_dugmeler}

    duzenlendi = False
    if mesaj_id:
        duzenlendi = mesaji_guncelle(mesaj_id, metin, reply_markup=reply_markup)

    if bildir:
        try:
            mesaj_gonder(metin, reply_markup=reply_markup)
        except Exception as e:
            log.warning("Sonuç bildirimi gönderilemedi: %s", e)

    return duzenlendi


def yayindan_kaldir(
    tur: str,
    ref_id: str | int,
    mesaj_id: Optional[int] = None,
    basan: Optional[str] = None,
) -> bool:
    """
    Yayınlanmış bir içeriği (haber, ilan, reels) geri alır (Instabot standardı).

    * Facebook API'den gönderi/video silinir (facebook.postu_sil).
    * Threads API'den gönderi/zincir silinir (threads.zinciri_sil).
    * Instagram Graph API silmeye izin vermediği için ("#10 Insufficient permissions")
      kullanıcıya gönderi linki sunulur ve mobil uygulamadan elle silmesi istenir.
    * Veritabanında durum='kaldirildi' yapılır, havuza DÖNMEZ (tekrar ertesi gün çıkmasın).
    """
    from . import facebook, threads, db

    ref_str = str(ref_id)
    haber = None
    ilan = None
    baslik = f"İçerik #{ref_str}"

    if tur in ("haber", "reels") or ref_str.isdigit():
        haber = db.haber_getir(int(ref_str))
        if haber:
            baslik = haber.get("manset") or haber.get("orijinal_baslik") or f"Haber #{ref_str}"
    elif tur == "ilan":
        ilan = db.ilan_getir(ref_str)
        if ilan:
            baslik = ilan.get("baslik") or f"İlan #{ref_str}"

    if not haber and not ilan:
        mesaj_gonder(f"⚠️ Yayından kaldırılacak içerik bulunamadı (#{ref_str}).")
        return False

    icerik_obj = haber if haber else ilan
    durum = icerik_obj.get("durum")
    if durum not in ("yayinlandi", "hata", "onay_bekliyor"):
        mesaj_gonder(f"⚠️ Bu içerik kaldırılmaya uygun bir durumda değil (durum: {durum}).")
        return False

    satirlar = []

    # 1. Facebook
    fb_id = icerik_obj.get("facebook_post_id")
    if fb_id:
        if facebook.postu_sil(fb_id):
            satirlar.append("📘 Facebook gönderisi silindi ✓")
        else:
            satirlar.append("⚠️ Facebook gönderisi silinemedi")
    else:
        satirlar.append("· Facebook: Kayıtlı gönderi ID yok")

    # 2. Threads
    th_id = icerik_obj.get("threads_post_id")
    if th_id:
        silinen, toplam = threads.zinciri_sil(th_id)
        if silinen > 0:
            satirlar.append(f"🧵 Threads zinciri silindi ({silinen}/{toplam} gönderi) ✓")
        else:
            satirlar.append("⚠️ Threads gönderisi silinemedi")
    else:
        satirlar.append("· Threads: Kayıtlı gönderi ID yok")

    # 3. Instagram (Elle silinmeli)
    ig_id = icerik_obj.get("instagram_post_id")
    if ig_id:
        ig_link = f"https://www.instagram.com/p/{ig_id}/"
        satirlar.append(
            "\n📷 <b>Instagram'dan ELLE silmeniz gerekiyor:</b>\n"
            "<i>(Meta Graph API yayınlanmış postların silinmesine izin vermemektedir)</i>\n"
            f"🔗 <a href='{ig_link}'>{ig_link}</a>"
        )
    else:
        satirlar.append("· Instagram: Kayıtlı gönderi ID yok")

    # 4. YouTube & TikTok
    yt_id = icerik_obj.get("youtube_video_id")
    if yt_id:
        satirlar.append(f"▶️ YouTube Shorts: YouTube Studio üzerinden kaldırabilirsiniz (ID: {yt_id})")

    # 5. LinkedIn
    li_id = icerik_obj.get("linkedin_post_id")
    if li_id:
        satirlar.append(f"💼 LinkedIn: Şirket sayfasından kaldırabilirsiniz (ID: {li_id})")
    else:
        satirlar.append("· LinkedIn: Kayıtlı gönderi ID yok")

    # 6. Veritabanını güncelle: havuza DÖNMEMESİ için durum='kaldirildi'
    if haber:
        # (2026-10-13) Eskiden buraya `atlanma_zamani` da yazılıyordu; haberler tablosunda bu sütun hiç yok,
        # UPDATE "no such column" ile çöküyor, gönderiler silinmiş hâlde kayıt "yayında" kalıyordu.
        db.haber_guncelle(int(ref_str), durum="kaldirildi")
    elif ilan:
        db.ilan_kaldirildi_isaretle(ref_str)

    db.onay_istegi_sonuclandir(tur, ref_str, "kaldirildi")
    db.wal_bosalt()

    rapor_metni = (
        f"🗑️ <b>YAYINDAN KALDIRILDI</b>\n\n"
        f"<b>İçerik:</b> {html.escape(baslik)} (#{ref_str})\n"
        f"<b>Kaldıran:</b> {html.escape(basan or 'Kullanıcı')}\n\n"
        + "\n".join(satirlar)
    )

    if mesaj_id:
        mesaji_guncelle(mesaj_id, rapor_metni, reply_markup=None)

    mesaj_gonder(rapor_metni)
    log.info("İçerik yayından kaldırıldı: tur=%s, ref_id=%s, basan=%s", tur, ref_str, basan)
    return True


def durum_guncelle(mesaj_id: int, baslik: str, adim: int, toplam_adim: int = 4, detay: str = "") -> None:
    """İşlem sürerken Telegram'da görsel progress bar günceller."""
    if toplam_adim < 1:
        toplam_adim = 1
    adim = max(1, min(adim, toplam_adim))
    dolu = "▰" * adim
    bos = "▱" * max(0, toplam_adim - adim)
    yuzde = int((adim / max(1, toplam_adim)) * 100)
    metin = (
        f"⏳ <b>{html.escape(baslik)}</b>\n\n"
        f"<code>[{dolu}{bos}] %{yuzde} ({adim}/{toplam_adim})</code>\n"
        f"<i>{html.escape(detay)}</i>"
    )
    mesaji_guncelle(mesaj_id, metin)


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


def kanal_butonlari(kanallar: Optional[Dict[str, bool]] = None) -> List[List[Dict[str, str]]]:
    """
    Yayın kanallarını açıp kapamak için 2 satırlı kompakt toggle butonları üretir.
    Satır 1: [✅ IG] [⬜ Reels] [✅ Story] [✅ Threads]
    Satır 2: [✅ FB] [✅ YT] [✅ TT]
    """
    if kanallar is None:
        kanallar = {
            "ig": True, "reels": False, "story": True, "threads": True,
            "facebook": True, "youtube": True, "tiktok": True, "linkedin": True,
        }

    def _simge(k: str) -> str:
        varsayilan_kapali = k in ("reels",)
        return "✅" if kanallar.get(k, False if varsayilan_kapali else True) else "⬜"

    return [
        [
            {"text": f"{_simge('ig')} IG", "callback_data": "kanal:ig"},
            {"text": f"{_simge('reels')} Reels", "callback_data": "kanal:reels"},
            {"text": f"{_simge('story')} Story", "callback_data": "kanal:story"},
            {"text": f"{_simge('threads')} Threads", "callback_data": "kanal:threads"},
        ],
        [
            {"text": f"{_simge('facebook')} FB", "callback_data": "kanal:facebook"},
            {"text": f"{_simge('youtube')} YT", "callback_data": "kanal:youtube"},
            {"text": f"{_simge('tiktok')} TT", "callback_data": "kanal:tiktok"},
            {"text": f"{_simge('linkedin')} LI", "callback_data": "kanal:linkedin"},
        ],
    ]


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


def ana_menu(adet: int = 2, kanallar: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    """Onay mesajının ilk buton seti — Instabot ile birebir aynı."""
    return {
        "inline_keyboard": [
            *kanal_butonlari(kanallar),
            [
                {"text": "✅ Yayınla", "callback_data": f"yayin_menu:{adet}"},
                {"text": "🎙️ Sesli Yayınla", "callback_data": f"ses_menu:{adet}"},
            ],
            [
                {"text": "📲 Manuel Paylaşım Paketi", "callback_data": "manuel_paket"},
            ],
            [
                {"text": "🔄 Başka Fotoğraf Bul", "callback_data": f"foto_menu:{adet}"},
                {"text": "✍️ Metinleri Yenile", "callback_data": f"metin_menu:{adet}"},
            ],
            [
                {"text": f"🎨 Slayt düzenle ({adet} slayt)", "callback_data": f"slayt_menu:{adet}"},
            ],
            [
                {"text": "🔄 Sıfırdan Yeniden Üret", "callback_data": f"yenile:{adet}"},
                {"text": "🗑️ Mesajı Sil", "callback_data": "mesaji_sil"},
            ],
            [
                {"text": "⏰ 1 saat ertele", "callback_data": "ertele"},
            ],
            [
                {"text": "❌ Bu turu atla (Havuza döner)", "callback_data": "iptal"},
                {"text": "🗑️ Çöpe At", "callback_data": "cope_at"},
            ],
        ]
    }



def yayin_zamani_menusu(adet: int = 2, kanallar: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    """Instabot yayın zamanı seçim alt menüsü."""
    return {
        "inline_keyboard": [
            *kanal_butonlari(kanallar),
            [
                {"text": "▶️ Şimdi", "callback_data": "yayinla"},
                {"text": "30 dk", "callback_data": "yayinla_sonra:30"},
            ],
            [
                {"text": "1 saat", "callback_data": "yayinla_sonra:60"},
                {"text": "2 saat", "callback_data": "yayinla_sonra:120"},
            ],
            [
                {"text": "3 saat", "callback_data": "yayinla_sonra:180"},
                {"text": "4 saat", "callback_data": "yayinla_sonra:240"},
            ],
            [
                {"text": "← Geri", "callback_data": f"yayin_geri:{adet}"},
            ],
        ]
    }


def ses_menusu(adet: int = 2, kanallar: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    """"🎙️ Sesli Yayınla" alt menüsü: fon müzikli mi, müziksiz mi (kullanıcı kararı 2026-09-26).

    Düz "✅ Yayınla" eskisi gibi seslendirmesiz; seslendirme yalnızca video
    kanallarına (Reels, FB, YT, TT) uygulanır. Menü gezinmesini Worker yapar;
    worker/index.js › sesMenusu ile birebir aynı kalmalı.
    """
    return {
        "inline_keyboard": [
            *kanal_butonlari(kanallar),
            [
                {"text": "🎵 Fon müzikli", "callback_data": f"ses_zaman:muzikli:{adet}"},
                {"text": "🔇 Fon müziksiz", "callback_data": f"ses_zaman:muziksiz:{adet}"},
            ],
            [
                {"text": "← Geri", "callback_data": f"yayin_geri:{adet}"},
            ],
        ]
    }


def sesli_yayin_zamani_menusu(mod: str = "muzikli", adet: int = 2,
                              kanallar: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    """Sesli yayının zaman menüsü: "Yayınla"nınkiyle aynı yapı, seslendirme kipi düğmede."""
    mod = "muziksiz" if mod == "muziksiz" else "muzikli"
    simge = "🔇" if mod == "muziksiz" else "🎵"
    return {
        "inline_keyboard": [
            *kanal_butonlari(kanallar),
            [
                {"text": f"▶️ Şimdi {simge}", "callback_data": f"yayinla_ses:{mod}"},
                {"text": "30 dk", "callback_data": f"yayinla_ses_sonra:{mod}:30"},
            ],
            [
                {"text": "1 saat", "callback_data": f"yayinla_ses_sonra:{mod}:60"},
                {"text": "2 saat", "callback_data": f"yayinla_ses_sonra:{mod}:120"},
            ],
            [
                {"text": "3 saat", "callback_data": f"yayinla_ses_sonra:{mod}:180"},
                {"text": "4 saat", "callback_data": f"yayinla_ses_sonra:{mod}:240"},
            ],
            [
                {"text": "← Geri", "callback_data": f"ses_menu:{adet}"},
            ],
        ]
    }


def foto_menusu(adet: int = 2, kanallar: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    """Instabot fotoğraf / görsel değiştirme alt menüsü."""
    return {
        "inline_keyboard": [
            *kanal_butonlari(kanallar),
            [
                {"text": "✨ 3 Farklı Aday Göster", "callback_data": "foto_adaylar"},
            ],
            [
                {"text": "📸 Gerçek Fotoğraf Ara", "callback_data": "foto_gercek"},
                {"text": "🖼️ Stok Fotoğraf (Pexels)", "callback_data": "foto_stok"},
            ],
            [
                {"text": "🎨 Yapay Zeka ile Üret", "callback_data": "foto_ai"},
                {"text": "🏛️ Saf Editoryal Zemin", "callback_data": "foto_editoryal"},
            ],
            [
                {"text": "↩️ İlk Görsele Dön", "callback_data": "foto_ilk"},
                {"text": "← Ana Menü", "callback_data": f"foto_geri:{adet}"},
            ],
        ]
    }


def metin_menusu(adet: int = 2, kanallar: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    """Instabot metin yenileme alt menüsü."""
    return {
        "inline_keyboard": [
            *kanal_butonlari(kanallar),
            [
                {"text": "✂️ Haberi Daha da Özetle", "callback_data": "metin_ozetle"},
                {"text": "📖 Hukuki Detay Ekle", "callback_data": "metin_detaylandir"},
            ],
            [
                {"text": "🔄 Standart Yeniden Yaz", "callback_data": "metin_yenile"},
            ],
            [
                {"text": "← Ana Menü", "callback_data": f"metin_geri:{adet}"},
            ],
        ]
    }


def slayt_secim_menusu(adet: int = 2, kanallar: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    """Instabot slayt düzenleme ve format seçim alt menüsü."""
    tuslar = []
    if adet > 1:
        satir = [{"text": str(i), "callback_data": f"slayt:{i}:{adet}"} for i in range(1, min(adet, 5) + 1)]
        tuslar.append(satir)
    tuslar.extend([
        [
            {"text": "📰 DailyBrief Haber", "callback_data": "format_uygula:dailybrief"},
            {"text": "📖 Sözlük Formatı", "callback_data": "format_uygula:sozluk"},
        ],
        [
            {"text": "⚖️ Nedir Doğrusu?", "callback_data": "format_uygula:nedir_dogrusu"},
            {"text": "📂 Örnek Olay", "callback_data": "format_uygula:vaka"},
        ],
        [
            {"text": "❓ Net Cevap", "callback_data": "format_uygula:net_cevap"},
            {"text": "🎬 9:16 Dikey Reels", "callback_data": "format_uygula:reels"},
        ],
        [
            {"text": "🏛️ Klasik Otorite (B1)", "callback_data": "format_uygula:b1"},
            {"text": "← Geri", "callback_data": f"geri:{adet}"},
        ],
    ])
    return {"inline_keyboard": tuslar}


def slayt_islem_menusu(sira: int, adet: int, kanallar: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    """Seçilen slayt için yapılabilecekler (sıralama, silme, metin ve başlık aksiyonları)."""
    tuslar: List[List[Dict[str, str]]] = []
    if adet > 1:
        if sira > 1:
            tuslar.append([{"text": f"🔝 {sira}. Slaytı EN BAŞA Al (Manşet Yap)", "callback_data": f"slayt_basa:{sira}"}])
        sira_satiri = []
        if sira > 1:
            sira_satiri.append({"text": "⬆️ 1 Yukarı Taşı", "callback_data": f"slayt_yukari:{sira}"})
        if sira < adet:
            sira_satiri.append({"text": "⬇️ 1 Aşağı Taşı", "callback_data": f"slayt_asagi:{sira}"})
        if sira_satiri:
            tuslar.append(sira_satiri)

    tuslar.extend([
        [{"text": f"🔥 {sira}. Slayt: Başlığı Daha Çarpıcı Yap", "callback_data": f"slayt_carpici:{sira}"}],
        [{"text": f"✍️ {sira}. Slayt: Başlığı Elle Düzenle (Reply)", "callback_data": f"slayt_elle:{sira}"}],
        [
            {"text": f"➕ {sira}. Slayt: Metni Uzat", "callback_data": f"slayt_uzat:{sira}"},
            {"text": f"➖ {sira}. Slayt: Metni Kısalt", "callback_data": f"slayt_kisalt:{sira}"},
        ],
    ])
    if adet > 2:
        tuslar.append([{"text": f"🗑 {sira}. Slaytı Çıkar", "callback_data": f"slayt_sil:{sira}"}])

    tuslar.append([{"text": "← Slayt Seçimine Dön", "callback_data": f"slayt_menu:{adet}"}])
    return {"inline_keyboard": tuslar}


def onay_menusu(haber_id: int, kanallar: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    """Geriye dönük uyumluluk: ana_menu çağırır."""
    return ana_menu(adet=2, kanallar=kanallar)


def reels_onay_menusu(haber_id: int, kanallar: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    """Geriye dönük uyumluluk: Reels varsayılan kanallarıyla ana_menu çağırır."""
    if kanallar is None:
        kanallar = {
            "ig": False, "reels": True, "story": True, "threads": True,
            "facebook": True, "youtube": True, "tiktok": True,
        }
    return ana_menu(adet=2, kanallar=kanallar)


def metin_secim_menusu(haber_id: int, tur: str = "haber") -> Dict[str, Any]:
    """Geriye dönük uyumluluk: metin_menusu çağırır."""
    return metin_menusu(adet=2)


def foto_secim_menusu(haber_id: int, tur: str = "haber") -> Dict[str, Any]:
    """Geriye dönük uyumluluk: foto_menusu çağırır."""
    return foto_menusu(adet=2)


def format_secim_menusu(haber_id: int) -> Dict[str, Any]:
    """İçeriğin görsel formatını tek tıkla değiştirmek için sunulan menü."""
    return {
        "inline_keyboard": [
            [
                {"text": "📰 DailyBrief Haber", "callback_data": f"format_uygula:dailybrief:{haber_id}"},
                {"text": "📖 EDM Sözlük", "callback_data": f"format_uygula:sozluk:{haber_id}"},
            ],
            [
                {"text": "⚖️ Nedir Doğrusu?", "callback_data": f"format_uygula:nedir_dogrusu:{haber_id}"},
                {"text": "📂 Örnek Olay", "callback_data": f"format_uygula:vaka:{haber_id}"},
            ],
            [
                {"text": "❓ Net Cevap", "callback_data": f"format_uygula:net_cevap:{haber_id}"},
                {"text": "🎬 9:16 Dikey Reels", "callback_data": f"format_uygula:reels:{haber_id}"},
            ],
            [
                {"text": "🏛️ Klasik Otorite (B1)", "callback_data": f"format_uygula:b1:{haber_id}"},
            ],
            [
                {"text": "← Onay Menüsüne Dön", "callback_data": f"onay_menu_don:haber:{haber_id}"},
            ],
        ]
    }


def kontrol_merkezi_menusu(duraklatildi: bool = False, kalan_sure: str = "") -> Dict[str, Any]:
    """Telegram /panel ve /menu komutları için interaktif kontrol paneli."""
    duraklat_butonu = (
        {"text": f"▶️ Botu Devam Ettir ({kalan_sure})", "callback_data": "devam_et"}
        if duraklatildi
        else {"text": "⏸️ Otomatik Akışı Duraklat", "callback_data": "duraklat_menu"}
    )
    return {
        "inline_keyboard": [
            [
                {"text": "📰 Günün Gönderisi (Rotasyon)", "callback_data": "hizli_uret:rotasyon"},
                {"text": "🎬 Reels Videosu (9:16)", "callback_data": "hizli_uret:reels"},
            ],
            [
                {"text": "📖 Sözlük Üret", "callback_data": "hizli_uret:sozluk"},
                {"text": "⚖️ Nedir Doğrusu?", "callback_data": "hizli_uret:nedir_dogrusu"},
            ],
            [
                {"text": "📂 Örnek Olay", "callback_data": "hizli_uret:vaka"},
                {"text": "❓ Net Cevap", "callback_data": "hizli_uret:net_cevap"},
            ],
            [
                {"text": "🌐 Taze Haber Tara & Post Yap", "callback_data": "hizli_uret:haber"},
                {"text": "🏛️ Klasik Otorite (B1)", "callback_data": "hizli_uret:b1"},
            ],
            [
                {"text": "📊 Sıradaki Post & Durum", "callback_data": "durum"},
                {"text": "📰 Son Postlar", "callback_data": "sonpostlar"},
            ],
            [
                {"text": "📈 Detaylı Kota Raporu", "callback_data": "kota_goster"},
                {"text": "⚙️ Çalışma Ayarları", "callback_data": "ayar"},
            ],
            [
                {"text": "🩺 Sistem Sağlık Testi", "callback_data": "saglik_testi"},
                duraklat_butonu,
            ],
            [
                {"text": "🔄 Konu Havuzu Durumu", "callback_data": "havuz_durum"},
                {"text": "⏰ Onayları Hatırlat", "callback_data": "hatirlat_tetikle"},
            ],
        ]
    }


def duraklatma_secenekleri_menusu() -> Dict[str, Any]:
    """Duraklatma süresi seçim menüsü."""
    return {
        "inline_keyboard": [
            [
                {"text": "⏸️ 1 Saat Duraklat", "callback_data": "duraklat:1"},
                {"text": "⏸️ 6 Saat Duraklat", "callback_data": "duraklat:6"},
            ],
            [
                {"text": "⏸️ 24 Saat Duraklat", "callback_data": "duraklat:24"},
                {"text": "⏸️ Süresiz Duraklat", "callback_data": "duraklat:0"},
            ],
            [
                {"text": "← Kontrol Paneline Dön", "callback_data": "panel"},
            ],
        ]
    }


def ayar_menusu() -> Dict[str, Any]:
    """Çalışma ayarları interaktif toggle menüsü."""
    try:
        from . import ayar
        return ayar.ayar_menusu()
    except Exception as e:
        log.warning("Ayar menüsü üretilemedi: %s", e)
        return {"inline_keyboard": [[{"text": "← Kontrol Paneli", "callback_data": "panel"}]]}


def icerik_incele_karti(ref_id: int) -> Tuple[str, Dict[str, Any]]:
    """İçerik #ref_id için detaylı inceleme kartı ve yönetim butonları üretir."""
    haber = db.haber_getir(int(ref_id))
    if not haber:
        return f"⚠️ <b>#{ref_id} numaralı içerik veritabanında bulunamadı.</b>", {
            "inline_keyboard": [[{"text": "← Kontrol Paneli", "callback_data": "panel"}]]
        }
    from . import haber_oneri
    if haber_oneri.ham_haber_mi(haber):
        # Öneri listesindeki 🔍 / /incele_272: henüz içerik değil, haber. İçerik kartı
        # "▶️ Şimdi Yayınla" sunardı — içeriği üretilmemiş bir haber için.
        return haber_oneri.haber_detay_karti(haber)

    manset = haber.get("manset") or haber.get("orijinal_baslik") or "Başlıksız"
    durum = haber.get("durum", "bilinmiyor")
    kategori = haber.get("kategori", "Genel")
    tarih = (haber.get("eklenme_tarihi") or "")[:16].replace("T", " ")
    kaynak = haber.get("kaynak", "EDM")

    durum_ikon = {
        "yayinlandi": "✅ Yayında",
        "onay_bekliyor": "⏳ Onay Bekliyor",
        "iptal": "❌ Atlandı / İptal",
        "cop": "🗑️ Çöpte",
    }.get(durum, f"ℹ️ {durum}")

    detay = {}
    try:
        detay = json.loads(haber.get("detay_metni") or "{}")
    except Exception:
        pass

    spot = detay.get("spot") or haber.get("orijinal_ozet") or ""
    slayt_sayisi = len(json.loads(haber.get("slayt_yollari") or "[]")) if haber.get("slayt_yollari") else 0

    metin = (
        f"🔍 <b>İÇERİK İNCELEME: #{ref_id}</b>\n\n"
        f"📌 <b>Manşet:</b> {html.escape(manset)}\n"
        f"🏷️ <b>Kategori:</b> {kategori} · <b>Kaynak:</b> {kaynak}\n"
        f"📊 <b>Durum:</b> {durum_ikon}\n"
        f"📅 <b>Tarih:</b> {tarih}\n"
        f"🖼️ <b>Slaytlar:</b> {slayt_sayisi} adet görsel hazır\n\n"
        f"📝 <b>Spot:</b>\n<i>{html.escape(spot[:200])}...</i>"
    )

    butonlar = {
        "inline_keyboard": [
            [
                {"text": "▶️ Şimdi Yayınla", "callback_data": f"yayinla:{ref_id}"},
                {"text": "🔄 Yeniden Üret", "callback_data": f"yenile:{ref_id}"},
            ],
            [
                {"text": "🔍 Yayın Kontrolü", "callback_data": f"yayin_kontrol:{ref_id}"},
                {"text": "🗑️ Çöpe At", "callback_data": f"cope_at:{ref_id}"},
            ],
            [
                {"text": "← Kontrol Paneli", "callback_data": "panel"},
            ],
        ]
    }
    return metin, butonlar


def icerik_incele_gonder(ref_id: int) -> bool:
    """İçerik #ref_id kartını görseliyle (fotoğraf varsa fotoğraflı kart, yoksa metin) Telegram'a gönderir."""
    haber = db.haber_getir(int(ref_id))
    if not haber:
        return bool(mesaj_gonder(f"⚠️ <b>#{ref_id} numaralı içerik veritabanında bulunamadı.</b>"))

    metin, butonlar = icerik_incele_karti(ref_id)

    # 1. Görsel adayını belirle (slayt varsa slayt 1, yoksa haberin gorsel_url'i)
    gorsel_adayi = None
    if haber.get("slayt_urlleri"):
        try:
            urls = json.loads(haber["slayt_urlleri"])
            if urls and isinstance(urls, list):
                gorsel_adayi = urls[0]
        except Exception:
            pass
    elif haber.get("slayt_yollari"):
        try:
            yollar = json.loads(haber["slayt_yollari"])
            if yollar and isinstance(yollar, list):
                gorsel_adayi = yollar[0]
        except Exception:
            pass

    if not gorsel_adayi and haber.get("gorsel_url"):
        gorsel_adayi = haber["gorsel_url"]

    # 2. Fotoğraflı kart olarak göndermeyi dene
    if gorsel_adayi:
        res = fotograf_gonder(gorsel_adayi, caption=metin[:1024], reply_markup=butonlar)
        if res:
            return True

    # 3. Fotoğraf yoksa veya gönderilemediyse metinle gönder
    return bool(mesaj_gonder(metin, reply_markup=butonlar))


def havuz_mesaji() -> str:
    """Konu havuzunun GERÇEK durumu. Worker'daki eski /havuz yanıtı sabit ve
    yanlış etiketli sayılar basıyordu ("S2 İmar & Parsel 25+ konu")."""
    o = konu_bankasi.durum_ozeti()
    satirlar = [
        "📚 <b>EDM KONU HAVUZU</b>\n",
        f"• Toplam: <b>{o['toplam']}</b> · Kullanılmış: <b>{o['kullanilmis']}</b> · Bakir: <b>{o['bakir']}</b>\n",
        "<b>Bakir konuların sütunlara dağılımı:</b>",
    ]
    for kod, adet in o["bakir_sutun_dagilimi"].items():
        satirlar.append(f"• {kod} {SUTUN_ADLARI.get(kod, '')}: <b>{adet}</b>")
    if o.get("kalan_gun"):
        satirlar.append(
            f"\n⏳ Son 14 günde günde ~{o['gunluk_tuketim']} konu tüketildi; "
            f"bu hızla havuz <b>~{o['kalan_gun']} gün</b> yeter."
        )
    else:
        satirlar.append("\n⏳ Son 14 günde konu tüketilmedi.")
    return "\n".join(satirlar)


def son_postlar_raporu() -> Tuple[str, Dict[str, Any]]:
    """Son 5 içeriği ve yayın durumlarını listeler."""
    with db._baglanti_al() as conn:
        satirlar = conn.execute(
            """SELECT id, manset, orijinal_baslik, durum, eklenme_tarihi
               FROM haberler
               ORDER BY id DESC
               LIMIT 5"""
        ).fetchall()

    if not satirlar:
        return "ℹ️ <b>Henüz kayıtlı içerik bulunmuyor.</b>", {
            "inline_keyboard": [[{"text": "← Kontrol Paneli", "callback_data": "panel"}]]
        }

    satir_metinleri = []
    tuslar = []
    for h in satirlar:
        hid = h["id"]
        baslik = h["manset"] or h["orijinal_baslik"] or f"İçerik #{hid}"
        durum = h["durum"]
        ikon = "✅" if durum == "yayinlandi" else ("⏳" if durum == "onay_bekliyor" else "❌")
        tarih = (h["eklenme_tarihi"] or "")[:10]
        satir_metinleri.append(f"{ikon} <b>#{hid}</b> ({tarih}) — {html.escape(baslik[:45])}...")
        tuslar.append({"text": f"🔍 #{hid}", "callback_data": f"incele:{hid}"})

    metin = (
        "📰 <b>SON İÇERİKLER & YAYIN DURUMU</b>\n\n"
        + "\n".join(satir_metinleri)
        + "\n\n💡 <i>Detayları incelemek ve aksiyon almak için butonları kullanabilirsiniz.</i>"
    )

    inline_rows = []
    for i in range(0, len(tuslar), 3):
        inline_rows.append(tuslar[i:i+3])
    inline_rows.append([{"text": "← Kontrol Paneli", "callback_data": "panel"}])

    return metin, {"inline_keyboard": inline_rows}


def yayin_kontrol_karti(ref_id: int) -> Tuple[str, Dict[str, Any]]:
    """İçerik #ref_id için platform bazlı yayın durumu ve tek tıkla retry butonları üretir."""
    haber = db.haber_getir(int(ref_id))
    if not haber:
        return f"⚠️ <b>#{ref_id} numaralı içerik bulunamadı.</b>", {
            "inline_keyboard": [[{"text": "← Kontrol Paneli", "callback_data": "panel"}]]
        }

    manset = haber.get("manset") or haber.get("orijinal_baslik") or f"İçerik #{ref_id}"
    durum = haber.get("durum")
    yayinlandi = (durum == "yayinlandi")

    ig_id = haber.get("instagram_post_id")
    th_id = haber.get("threads_post_id")
    fb_id = haber.get("facebook_post_id")
    yt_id = haber.get("youtube_video_id")
    tt_id = haber.get("tiktok_publish_id")
    li_id = haber.get("linkedin_post_id")

    ig_durum = "✅ Yayında" if ig_id else "⚪ Yayınlanmadı / Bilgi Yok"
    th_durum = "✅ Yayında" if th_id else "⚪ Yayınlanmadı / Bilgi Yok"
    fb_durum = "✅ Yayında" if fb_id else "⚪ Yayınlanmadı / Bilgi Yok"
    yt_durum = "✅ Yayında" if yt_id else "⚪ Yayınlanmadı / Bilgi Yok"
    tt_durum = "✅ Yayında / Taslak" if tt_id else "⚪ Yayınlanmadı / Bilgi Yok"
    li_durum = "✅ Yayında" if li_id else "⚪ Yayınlanmadı / Bilgi Yok"

    metin = (
        f"📡 <b>YAYIN DOĞRULAMA & KONTROL: #{ref_id}</b>\n\n"
        f"📌 <b>Başlık:</b> {html.escape(manset)}\n"
        f"📊 <b>Genel Durum:</b> {'✅ Başarıyla Paylaşıldı' if yayinlandi else '⚠️ Paylaşım Bekleniyor / Kısmi'}\n\n"
        f"<b>Platform Durumları:</b>\n"
        f"• 📸 Instagram: {ig_durum}\n"
        f"• 🧵 Threads: {th_durum}\n"
        f"• 📘 Facebook: {fb_durum}\n"
        f"• 🎵 TikTok: {tt_durum}\n"
        f"• ▶️ YouTube Shorts: {yt_durum}\n"
        f"• 💼 LinkedIn: {li_durum}\n\n"
        f"💡 <i>Eksik kalan veya tekrar yayınlamak istediğiniz kanallar için aşağıdaki butonları kullanabilirsiniz:</i>"
    )

    retry_butonlari = []
    tekil_siralar = []
    if not ig_id:
        tekil_siralar.append({"text": "🔄 IG Gönderi", "callback_data": f"retry_kanal:ig:{ref_id}"})
    tekil_siralar.append({"text": "🔄 Reels Video", "callback_data": f"retry_kanal:reels:{ref_id}"})
    if not th_id:
        tekil_siralar.append({"text": "🔄 Threads", "callback_data": f"retry_kanal:threads:{ref_id}"})
    if not fb_id:
        tekil_siralar.append({"text": "🔄 Facebook", "callback_data": f"retry_kanal:facebook:{ref_id}"})
    if not yt_id:
        tekil_siralar.append({"text": "🔄 YouTube", "callback_data": f"retry_kanal:youtube:{ref_id}"})
    if not tt_id:
        tekil_siralar.append({"text": "🔄 TikTok", "callback_data": f"retry_kanal:tiktok:{ref_id}"})
    if not li_id:
        tekil_siralar.append({"text": "🔄 LinkedIn", "callback_data": f"retry_kanal:linkedin:{ref_id}"})

    for i in range(0, len(tekil_siralar), 3):
        retry_butonlari.append(tekil_siralar[i:i + 3])

    alt_butonlar = [
        [{"text": "🚀 Tüm Kanalları Kurtar & Yayınla", "callback_data": f"kurtar:{ref_id}"}],
        [{"text": f"← #{ref_id} İnceleme Kartı", "callback_data": f"incele:{ref_id}"}],
    ]

    return metin, {"inline_keyboard": retry_butonlari + alt_butonlar}


def panel_gonder(mesaj_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Telegram Kontrol Merkezini gönderir veya günceller."""
    duraklatildi, kalan = bot_duraklatildi_mi()
    durum_str = f"⏸️ <b>DURAKLATILDI</b> ({kalan})" if duraklatildi else "🟢 <b>OTOMATİK AKIŞ AKTİF</b>"

    metin = (
        "🏢 <b>EDM YAPI & GAYRİMENKUL // KONTROL MERKEZİ</b>\n\n"
        f"<b>Sistem Durumu:</b> {durum_str}\n"
        "Aşağıdaki butonları kullanarak tek tıkla yeni içerik üretebilir, "
        "yayın akışını yönetebilir veya sistem durumunu denetleyebilirsiniz."
    )
    menu = kontrol_merkezi_menusu(duraklatildi=duraklatildi, kalan_sure=kalan)

    if mesaj_id:
        mesaji_guncelle(mesaj_id, metin, reply_markup=menu)
        return None
    return mesaj_gonder(metin, reply_markup=menu)


def durum_raporu_gonder(mesaj_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Detaylı sistem ve yayın durumu raporu gönderir."""
    duraklatildi, kalan = bot_duraklatildi_mi()
    durum_str = f"⏸️ Duraklatıldı ({kalan})" if duraklatildi else "🟢 Aktif (Zamanlanmış Akış)"

    ozet = konu_bankasi.durum_ozeti()
    kanallar = varsayilan_kanallar()
    kanal_str = " · ".join([f"{'✅' if v else '⬜'} {k.upper()}" for k, v in kanallar.items()])

    # Son yayınlanan post
    son_yayinlanan = None
    with db._baglanti_al() as conn:
        row = conn.execute("SELECT id, orijinal_baslik, manset, yayin_tarihi FROM haberler WHERE durum = 'yayinlandi' ORDER BY id DESC LIMIT 1").fetchone()
        if row:
            son_yayinlanan = dict(row)

    son_post_str = (
        f"#{son_yayinlanan['id']} — {son_yayinlanan.get('manset') or son_yayinlanan.get('orijinal_baslik', '')}"
        if son_yayinlanan else "Henüz kayıt yok"
    )

    metin = (
        "📊 <b>EDM SİSTEM & YAYIN DURUMU</b>\n\n"
        f"• <b>Otomasyon:</b> {durum_str}\n"
        f"• <b>Yayın Kanalları:</b> {kanal_str}\n"
        f"• <b>Konu Bankası:</b> {ozet['bakir']}/{ozet['toplam']} bakir konu (~{ozet['kalan_hafta']} hafta)\n"
        f"• <b>Sütun Dağılımı:</b> S1:{ozet['bakir_sutun_dagilimi'].get('S1',0)} · S2:{ozet['bakir_sutun_dagilimi'].get('S2',0)} · S3:{ozet['bakir_sutun_dagilimi'].get('S3',0)} · S4:{ozet['bakir_sutun_dagilimi'].get('S4',0)}\n"
        f"• <b>Son Yayın:</b> {son_post_str}\n\n"
        "<i>Otomatik paylaşımlar haftalık plan doğrultusunda belirlenen günlerde sabah 10:00'da onaya sunulur.</i>"
    )

    geri_menu = {"inline_keyboard": [[{"text": "← Kontrol Paneline Dön", "callback_data": "panel"}]]}
    if mesaj_id:
        mesaji_guncelle(mesaj_id, metin, reply_markup=geri_menu)
        return None
    return mesaj_gonder(metin, reply_markup=geri_menu)


def kota_gonder(mesaj_id: Optional[int] = None, kategori: int | str = "menu") -> Optional[Dict[str, Any]]:
    """Detaylı GitHub Actions, yapay zeka ve sistem kota tablosu gönderir."""
    from . import rapor_uretici
    return rapor_uretici.kota_gonder(mesaj_id=mesaj_id, kategori=kategori)


kota = kota_gonder
detayli_rapor_gonder = kota_gonder


def komut_menusu_kaydet() -> bool:
    """Telegram komut açılır menüsünü (setMyCommands) tüm kapsamlara ve gruba kaydeder."""
    token, chat_id = _bot_bilgileri()
    if not token:
        return False

    kapsamlar = [
        None,
        {"type": "all_private_chats"},
        {"type": "all_group_chats"},
    ]
    if chat_id:
        try:
            cid = int(str(chat_id).strip())
            kapsamlar.extend([
                {"type": "chat", "chat_id": cid},
                {"type": "chat_administrators", "chat_id": cid},
            ])
        except Exception:
            pass

    basarili = 0
    url = TELEGRAM_API_URL.format(token=token, method="setMyCommands")
    for kapsam in kapsamlar:
        payload: Dict[str, Any] = {"commands": komutlar.KOMUT_MENUSU}
        if kapsam:
            payload["scope"] = kapsam
        try:
            r = requests.post(url, json=payload, timeout=15)
            res = r.json() if r.content else {}
            if res.get("ok"):
                basarili += 1
            else:
                log.warning("Komut menüsü kaydedilemedi (%s): %s", kapsam or "varsayılan", res)
        except Exception as e:
            log.warning("setMyCommands isteği başarısız (%s): %s", kapsam or "varsayılan", e)

    log.info("Telegram komut menüsü %d/%d kapsama yazıldı.", basarili, len(kapsamlar))
    return basarili == len(kapsamlar)


# =========================================================================
# ONAY AKIŞLARI (HABER VE İLAN)
# =========================================================================


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
    from . import dogrula
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
    mesaj_gonder(
        dogrula.yayin_engeli_metni(haber_id, uyarilar),
        reply_markup={"inline_keyboard": [[
            {"text": "🔄 Sıradaki konudan üret", "callback_data": "hizli_uret:rotasyon"},
        ]]},
    )
    try:
        from . import db_senkron
        db_senkron.hemen_kaydet(f"db: icerik #{haber_id} denetimde durduruldu")
    except Exception as e:
        log.warning("Hemen kaydetme adımı atlandı: %s", e)
    return False, uyarilar


def _eksik_icerik_bildir(haber_id: Optional[int], hata: Exception) -> None:
    from . import make_image
    if haber_id:
        db.haber_guncelle(haber_id, durum="engellendi")
    if isinstance(hata, make_image.TasmaHatasi):
        aciklama = ("<i>Metin okunabilir en küçük puntoda bile karta sığmadı. Kutunun altına "
                    "giren ya da kırpılan metin yayınlanmaz (#243'te tanımın son satırları "
                    "kutunun arkasında kalmıştı).</i>")
    else:
        aciklama = ("<i>Model formatın zorunlu alanını üretmedi. Boş alan koddaki genel bir "
                    "cümleyle doldurulmaz — o yol #157'de alakasız bir 'Yargıtay hükmü' yayınlatmıştı.</i>")
    mesaj_gonder(
        f"🛑 <b>İçerik{f' #{haber_id}' if haber_id else ''} durduruldu:</b> {html.escape(str(hata))}.\n"
        + aciklama,
        reply_markup={"inline_keyboard": [[
            {"text": "🔄 Sıradaki konudan üret", "callback_data": "hizli_uret:rotasyon"},
        ]]},
    )


def haber_onayina_sun(haber_id: int, yeniden_ciz: bool = True, oto_yayin: bool = False) -> bool:
    """Haberin görselini ve metnini hazırlayıp Telegram onayına sunar.

    `oto_yayin=True`: kapıdan uyarısız geçerse onay beklenmeden yayınlanır; yayın ya da koşullardan biri
    tutmazsa içerik her zamanki gibi onaya düşer (otomatik yol hiçbir zaman içeriği kaybettirmez)."""
    from . import yeni_formatlar
    try:
        return _haber_onayina_sun(haber_id, yeniden_ciz=yeniden_ciz, oto_yayin=oto_yayin)
    except yeni_formatlar.EksikIcerik as e:
        log.warning("İçerik #%s eksik alan yüzünden durdu: %s", haber_id, e)
        _eksik_icerik_bildir(haber_id, e)
        return False


def _album_teslim_notu(album_res: Any, adet: int, slayt_urlleri: Optional[List[str]]) -> str:
    """Albüm Telegram'a tam ulaşmadıysa onay kartının başına konacak uyarı (boş metin = sorun yok).

    Görseller gelmediyse kullanıcı kartı kör onaylamasın; ImgBB bağlantıları varsa oradan açabilsin."""
    if album_res is True or (isinstance(album_res, list) and len(album_res) >= adet):
        return ""
    if isinstance(album_res, list) and album_res:
        satirlar = [f"⚠️ <b>Slaytların yalnız {len(album_res)}/{adet} tanesi iletilebildi.</b>"]
    else:
        satirlar = ["⚠️ <b>Slayt görselleri Telegram'a iletilemedi.</b>"]
    linkler = [f'<a href="{html.escape(str(u), quote=True)}">{i}. slayt</a>' for i, u in enumerate(slayt_urlleri or [], 1)]
    if linkler:
        satirlar.append("Görselleri buradan açabilirsiniz: " + " · ".join(linkler))
    satirlar.append("<i>Yayınlamadan önce görselleri kontrol edin; sorun varsa “🔄 Sıfırdan Yeniden Üret”.</i>")
    return "\n".join(satirlar) + "\n\n"


def _onay_kartini_gonder(kimlik: int | str, metin: str, butonlar: Dict[str, Any], manset_h: str,
                         tur: str) -> Optional[Dict[str, Any]]:
    """Düğmeli onay kartını gönderir. Uzun/bozuk metin yüzünden gitmezse kısa karta düşer: düğmeler HİÇBİR durumda
    kaybolmaz (kullanıcı kartı görmeden içerik onay kuyruğunda beklerdi). Yine de gitmezse hata günlüğüne yazar."""
    res = mesaj_gonder(metin, reply_markup=butonlar)
    if res:
        return res
    log.warning("Onay kartı gönderilemedi (%s #%s); kısa kart deneniyor", tur, kimlik)
    kisa = (f"📝 <b>İçerik #{kimlik} onay bekliyor</b>\n<b>Manşet:</b> {manset_h}\n\n"
            "<i>Ayrıntılı kart gönderilemedi; düğmeler aşağıda.</i>")
    res = mesaj_gonder(kisa, reply_markup=butonlar)
    if res:
        return res
    log.error("Onay kartı (%s #%s) Telegram'a iletilemedi", tur, kimlik)
    try:
        db.hata_kaydi_ekle("telegram.onay_karti", f"Onay kartı iletilemedi ({tur} #{kimlik})",
                           "Düğmeli onay kartı Telegram'a ulaşmadı.", "Telegram API cevap vermedi ya da kartı reddetti.",
                           "tur_tekrar", False, f"{tur} #{kimlik}")
    except Exception as e:  # noqa: BLE001
        log.warning("Kart hatası DB'ye yazılamadı: %s", e)
    return None


def _haber_onayina_sun(haber_id: int, yeniden_ciz: bool = True, oto_yayin: bool = False) -> bool:
    haber = db.haber_getir(haber_id)
    if not haber:
        return False

    # 1. Metin yoksa üret
    if not haber.get("manset"):
        metin_sonuc = generate_text.haber_metinleri_uret(haber)
        if not metin_sonuc:
            log.error("Haber metni üretilemedi (#%d)", haber_id)
            return False
        haber = db.haber_getir(haber_id)

    # 2. Slayt görsellerini al veya üret (yeniden_ciz=True ise bayat dosyaları kullanma)
    slayt_yollari = []
    if not yeniden_ciz and haber.get("slayt_yollari"):
        try:
            mevcut = json.loads(haber["slayt_yollari"])
            if isinstance(mevcut, list) and len(mevcut) > 0 and all(Path(p).exists() for p in mevcut):
                slayt_yollari = [str(p) for p in mevcut]
        except Exception:
            slayt_yollari = []

    otorite_verisi = None
    if haber.get("detay_metni"):
        try:
            otorite_verisi = json.loads(haber["detay_metni"])
        except Exception:
            otorite_verisi = None

    format_turu = None
    if otorite_verisi and isinstance(otorite_verisi, dict):
        format_turu = otorite_verisi.get("format_turu")

    # YAYIN KAPISI — slayt ve video üretiminden ÖNCE: durdurulacak içerik için
    # görsel üretmek boşa dakika.
    # Hazır arşiv kartı kanun metniyle ve hakemle BİR KEZ doğrulandı (sozluk_arsivi); her yayında yeniden
    # model çağırmak kota harcar ve hakem gürültüsü kartı boşuna durdurur. Kanunun hâlâ aynı olduğu
    # kart seçilirken sınanır.
    kart_mi = bool(isinstance(otorite_verisi, dict) and (otorite_verisi.get("_brief") or {}).get("kart"))
    gecti, uyarilar = yayin_kapisi(haber_id, haber, _denetim_verisi(haber, otorite_verisi), anlam_denetimi=not kart_mi)
    if not gecti:
        return False
    if oto_yayin and uyarilar:
        # Finanstaki kural: otomatik yayın insan onayını atlıyor, bu yüzden EN UFAK uyarıda durur
        log.warning("İçerik #%s otomatik yayını durduruldu: %s", haber_id, "; ".join(uyarilar))
        mesaj_gonder(
            f"🛑 <b>Otomatik yayın durduruldu (#{haber_id})</b> — {len(uyarilar)} denetim uyarısı.\n"
            "<i>İçerik onayınıza sunuluyor; uyarıları kontrol edip elle yayınlayın.</i>"
        )
        oto_yayin = False

    if not slayt_yollari:
        from . import yeni_formatlar, make_image

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

    # 2.5 Slaytları Public CDN'e yükle (Runner bağımsızlığı ve API'ler için)
    slayt_urlleri = []
    try:
        slayt_urlleri = upload_image.coklu_gorsel_yukle(slayt_yollari)
    except Exception as e:
        log.warning("Görseller CDN'e yüklenemedi: %s", e)

    # 2.6 Veritabanına kaydet (Video onaya sunulmaz; kullanıcı 'Yayınla' dediğinde derlenir - Instabot standardı)
    is_reels = (format_turu == "reels") or (haber.get("kategori") == "REELS")
    is_haber = (format_turu in ("dailybrief", "haber", "haber_dailybrief")) or (otorite_verisi and otorite_verisi.get("bicim") in ("haber", "B5")) or (not otorite_verisi and not is_reels)

    db.haber_guncelle(
        haber_id,
        slayt_yollari=json.dumps(slayt_yollari),
        slayt_urlleri=json.dumps(slayt_urlleri) if slayt_urlleri else None,
        video_yolu=None,
        durum="onay_bekliyor"
    )

    if oto_yayin:
        if _oto_yayinla(haber_id, slayt_yollari, haber, slayt_urlleri):
            return True
        mesaj_gonder(f"⚠️ #{haber_id} otomatik yayınlanamadı; içerik onayınıza sunuluyor.")

    # 2.7 Önceki tüm mesajları (eski onay kartı ve albüm slaytları) temizle
    icerik_onceki_mesajlarini_temizle("haber_album", haber_id)
    icerik_onceki_mesajlarini_temizle("haber", haber_id)

    # 3. Format bazlı başlık ve rozet belirleme (Haberle Birebir Aynı Standart)
    manset_h = html.escape(str(haber.get("manset") or ""), quote=False)
    rozet = "HUKUK & YATIRIM REHBERİ"
    dayanak = haber.get("kaynak", "EDM Yapı & Gayrimenkul")
    if otorite_verisi and isinstance(otorite_verisi, dict):
        rozet = otorite_verisi.get("rozet_metni", rozet)
        dayanak = otorite_verisi.get("yasal_dayanak", dayanak)

    if is_reels:
        rozet = "REELS & VİDEO (9:16)"
        dayanak = (otorite_verisi.get("yasal_dayanak") if (otorite_verisi and isinstance(otorite_verisi, dict) and otorite_verisi.get("yasal_dayanak")) else None) or (haber.get("kaynak") or "EDM Video Prodüksiyon")
        album_caption = f"🎬 <b>EDM 9:16 REELS SLAYTLARI</b>\n📌 {manset_h}"
        kart_baslik = f"🎬 <b>GÜNCEL REELS İÇERİĞİ ONAY BEKLİYOR (#{haber_id})</b>\n\n"
    elif format_turu == "sozluk":
        rozet = "GAYRİMENKUL SÖZLÜĞÜ"
        dayanak = (otorite_verisi.get("yasal_dayanak") if (otorite_verisi and isinstance(otorite_verisi, dict) and otorite_verisi.get("yasal_dayanak")) else None) or (haber.get("kaynak") or "EDM Gayrimenkul Terminolojisi")
        album_caption = f"📖 <b>EDM GAYRİMENKUL SÖZLÜĞÜ (4:5)</b>\n📌 {manset_h}"
        kart_baslik = f"📖 <b>GAYRİMENKUL SÖZLÜĞÜ ONAY BEKLİYOR (#{haber_id})</b>\n\n"
    elif format_turu == "nedir_dogrusu":
        rozet = "NEDİR DOĞRUSU?"
        dayanak = (otorite_verisi.get("yasal_dayanak") if (otorite_verisi and isinstance(otorite_verisi, dict) and otorite_verisi.get("yasal_dayanak")) else None) or (haber.get("kaynak") or "EDM Hukuk & Doğrulama")
        album_caption = f"⚖️ <b>EDM NEDİR DOĞRUSU? (4:5)</b>\n📌 {manset_h}"
        kart_baslik = f"⚖️ <b>NEDİR DOĞRUSU İÇERİĞİ ONAY BEKLİYOR (#{haber_id})</b>\n\n"
    elif format_turu == "vaka":
        rozet = "HUKUKİ VAKA ANALİZİ"
        dayanak = (otorite_verisi.get("yasal_dayanak") if (otorite_verisi and isinstance(otorite_verisi, dict) and otorite_verisi.get("yasal_dayanak")) else None) or (haber.get("kaynak") or "Emsal Karar & Yargıtay İçtihadı")
        album_caption = f"📂 <b>EDM HUKUKİ VAKA ANALİZİ (4:5)</b>\n📌 {manset_h}"
        kart_baslik = f"📂 <b>VAKA ANALİZİ ONAY BEKLİYOR (#{haber_id})</b>\n\n"
    elif format_turu == "net_cevap":
        rozet = "NET CEVAP REHBERİ"
        dayanak = (otorite_verisi.get("yasal_dayanak") if (otorite_verisi and isinstance(otorite_verisi, dict) and otorite_verisi.get("yasal_dayanak")) else None) or (haber.get("kaynak") or "EDM Danışmanlık Masası")
        album_caption = f"❓ <b>EDM NET CEVAP REHBERİ (4:5)</b>\n📌 {manset_h}"
        kart_baslik = f"❓ <b>NET CEVAP REHBERİ ONAY BEKLİYOR (#{haber_id})</b>\n\n"
    elif is_haber:
        rozet = rozet if rozet != "HUKUK & YATIRIM REHBERİ" else "GÜNCEL HABER & GÜNDEM"
        album_caption = f"📰 <b>EDM GÜNDEM // HABER BÜLTENİ (4:5)</b>\n📌 {manset_h}"
        kart_baslik = f"📰 <b>GÜNCEL HABER BÜLTENİ ONAY BEKLİYOR (#{haber_id})</b>\n\n"
    else:
        album_caption = f"🏛 <b>EDM OTORİTE CAROUSEL (4:5)</b>\n📌 {manset_h}"
        kart_baslik = f"🏛 <b>YENİ OTORİTE İÇERİĞİ ONAY BEKLİYOR (#{haber_id})</b>\n\n"

    # 3.1 Slayt görsellerini albüm (veya tek görsel) olarak gönder
    album_res = medya_grubu_gonder(slayt_yollari, caption=album_caption, yedek_urller=slayt_urlleri)
    _, chat_id = _bot_bilgileri()
    cid = int(str(chat_id).strip()) if str(chat_id).lstrip("-").isdigit() else None
    # Başarısız çağrıda "son albümün" kimliklerine bakılmaz: önceki içeriğin mesajları bu içeriğe yazılıp
    # sonraki temizlikte yanlışlıkla silinirdi.
    album_mids = album_res if isinstance(album_res, list) else []
    gorsel_notu = _album_teslim_notu(album_res, min(len(slayt_yollari), 10), slayt_urlleri)
    for mid in album_mids:
        try:
            db.onay_istegi_kaydet("haber_album", str(haber_id), mid, cid)
        except Exception as e:
            log.warning("Albüm mesaj ID kaydedilemedi: %s", e)

    # 4. İnteraktif Onay Menüsü + Kopyalanabilir Caption (Görüntülerin hemen altına düşer)
    from . import dogrula
    denetim_basligi = dogrula.uyari_basligi(uyarilar)
    if uyarilar:
        log.info("Denetim uyarıları (#%d): %s", haber_id, "; ".join(uyarilar))

    import html as html_lib
    ham_caption = (haber.get("ig_caption") or haber.get("manset") or "").strip()
    try:
        caption_metin = generate_text.caption_zenginlestir(
            ham_caption,
            kategori_kodu=haber.get("kategori"),
            platform="instagram",
            manset=haber.get("manset"),
        )
    except Exception as e:  # noqa: BLE001 — caption süsü yüzünden onay kartı (düğmeler) hiç gitmesin
        log.warning("Caption zenginleştirilemedi (#%d), ham metin kullanılıyor: %s", haber_id, e)
        caption_metin = ham_caption
    temiz_caption = html_lib.escape(caption_metin) if caption_metin else ""

    puan_degeri = min(10, int(haber.get("onem_puani", 8))) if str(haber.get("onem_puani", "")).isdigit() else 8
    mesaj_metni = (
        gorsel_notu
        + denetim_basligi
        + kart_baslik
        + f"<b>Kategori:</b> {html.escape(str(rozet), quote=False)}\n"
        f"<b>Dayanak:</b> {html.escape(str(dayanak), quote=False)}\n"
        f"<b>Manşet:</b> {manset_h}\n"
        f"<b>Önem Puanı:</b> {puan_degeri}/10\n"
        f"<b>İçerik No:</b> #{haber_id}\n\n"
    )
    if temiz_caption:
        mesaj_metni += f"<pre><code>{temiz_caption}</code></pre>\n\n"
    mesaj_metni += "<i>Bu içeriği onaylıyor musunuz? Kanalları seçip tek tıkla yayınlayabilirsiniz:</i>"

    if is_reels or is_haber:
        # Haber ve Reels içeriklerinde varsayılan: Reels AÇIK, IG Besleme KAPALI
        reels_kanallari = {"ig": False, "reels": True, "story": True, "threads": True, "facebook": True, "youtube": True, "tiktok": True, "linkedin": True}
        butonlar = ana_menu(adet=len(slayt_yollari) if slayt_yollari else 3, kanallar=reels_kanallari)
    else:
        # Otorite, sözlük, rehber carousel içeriklerinde varsayılan: IG Besleme AÇIK, Reels KAPALI
        ig_kanallari = {"ig": True, "reels": False, "story": True, "threads": True, "facebook": True, "youtube": True, "tiktok": True, "linkedin": True}
        butonlar = ana_menu(adet=len(slayt_yollari) if slayt_yollari else 2, kanallar=ig_kanallari)
    res = _onay_kartini_gonder(haber_id, mesaj_metni, butonlar, manset_h, "haber")
    if res and isinstance(res, dict) and "message_id" in res:
        try:
            db.onay_istegi_kaydet("haber", str(haber_id), res["message_id"], cid)
        except Exception as e:
            log.warning("Onay isteği kaydedilemedi: %s", e)

    # Instabot tecrübesi (1c): Kullanıcı Telegram'da butona saniyeler içinde basabilir.
    # Onay mesajı gittiği an veritabanını GitHub'a güvenle kaydet (arka planda commit+push).
    try:
        from . import db_senkron
        db_senkron.hemen_kaydet(f"db: haber #{haber_id} onaya sunuldu")
    except Exception as e:
        log.warning("Hemen kaydetme adımı atlandı: %s", e)

    return True


# Otomatik yayında kullanılan kanallar: finans bülteniyle aynı (hazirla.yml'deki sırlarla yayınlanabilenler;
# LinkedIn sırları yalnız yayinla.yml'de var)
OTO_YAYIN_HEDEFLERI = "ig,threads,story,tiktok,facebook,youtube"


def _oto_yayinla(haber_id: int, slayt_yollari: List[str], haber: Dict[str, Any],
                 slayt_urlleri: Optional[List[str]] = None) -> bool:
    """Onay beklemeden `scripts/yayinla.py` ile yayınlar. Yayın betiği kanal kanal sonucu Telegram'a kendisi
    raporlar ve durumu günceller. Betik hiç sonuç üretmeden çökerse False döner: çağıran içeriği onaya düşürür.
    """
    manset = html.escape(str(haber.get("manset") or haber.get("orijinal_baslik") or ""))
    fmt = ""
    try:
        detay = json.loads(haber.get("detay_metni") or "{}")
        fmt = str(detay.get("format_turu") or "").lower()
    except Exception:
        detay = {}

    is_sozluk = fmt in ("sozluk", "sozluk_uret") or str(haber.get("kaynak", "")).startswith("EDM Sözlük Kartı")
    baslik_etiket = "📖 <b>EDM EMLAK SÖZLÜĞÜ // OTOMATİK YAYIN</b>" if is_sozluk else "🚀 <b>OTOMATİK YAYIN</b>"

    try:
        medya_grubu_gonder(
            slayt_yollari,
            caption=f"{baslik_etiket} (#{haber_id})\n📌 <b>{manset}</b>\n⏳ <i>Kanallara dağıtılıyor, canlı yayın durumu birazdan iletilecek...</i>",
            yedek_urller=slayt_urlleri,
        )
    except Exception as e:  # noqa: BLE001 — görünürlük için; yayını durdurmaz
        log.warning("Otomatik yayın görseli Telegram'a iletilemedi: %s", e)

    # Sözlük kartı statik bilgi kartıdır; YouTube Shorts video kanalı hariç tutulur:
    hedefler = "ig,threads,story,tiktok,facebook" if is_sozluk else OTO_YAYIN_HEDEFLERI
    komut = [sys.executable, str(KOK / "scripts/yayinla.py"), "--tur", "haber", "--id", str(haber_id), "--hedef", hedefler]
    log.info("İçerik #%s otomatik yayınlanıyor: %s", haber_id, komut)
    try:
        calisma = subprocess.run(komut, cwd=KOK, capture_output=True, text=True, timeout=15 * 60)
    except subprocess.TimeoutExpired:
        log.error("İçerik #%s otomatik yayını zaman aşımına uğradı", haber_id)
        return False
    if calisma.returncode == 0 or "POSTEDM_SONUC=" in calisma.stdout:
        return True
    log.error("İçerik #%s otomatik yayınlanamadı: %s\n%s", haber_id, calisma.stdout[-600:], calisma.stderr[-600:])
    return False


def _tr_bugun() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=3)).date().isoformat()


# Zamanlanmış günlük turu iki yerden tetiklenebilir: Cloudflare cron'u (asıl yol, dakikasında çalışır) ve GitHub cron'u
# (yedek; 6-10 saat gecikebiliyor). Aynı slot aynı Türkiye gününde ikinci kez ÜRETİLMEZ: aksi halde geç gelen GitHub
# koşusu ikinci içerik, ikinci konu tüketimi ve (sözlükte) onay kuyruğuna ikinci kart demek olurdu.
ZAMANLI_GUNLUK_SLOTLAR = ("bilgilendirici", "sozluk")


def _zamanli_slot_anahtari(slot: str) -> str:
    return f"zamanli_slot_son_gun:{slot}"


def zamanli_slot_bugun_yapildi(slot: str) -> bool:
    """Bu slotun zamanlanmış turu bugün (TR) zaten başarıyla çalıştı mı?"""
    if slot not in ZAMANLI_GUNLUK_SLOTLAR:
        return False
    return db.ayar_oku(_zamanli_slot_anahtari(slot)) == _tr_bugun()


def zamanli_slot_isaretle(slot: str) -> None:
    """Zamanlanmış turun bugün başarıyla çalıştığını kaydeder (başarısız tur işaretlenmez: yedek tetik yeniden dener)."""
    if slot in ZAMANLI_GUNLUK_SLOTLAR:
        db.ayar_yaz(_zamanli_slot_anahtari(slot), _tr_bugun())


def sozluk_oto_yayin_acik_mi() -> bool:
    """Sözlük kartlarının onaysız yayını.
    1. DB ayarı: db.ayar_oku('sozluk_oto_yayin') '1' / 'acik' ise aktif.
    2. GitHub Actions değişkeni: SOZLUK_OTO_YAYIN ortam değişkeni '1' / 'acik' ise aktif.
    """
    db_deger = str(db.ayar_oku("sozluk_oto_yayin") or "").strip().lower()
    if db_deger in ("1", "true", "evet", "acik", "açık"):
        return True
    return os.environ.get("SOZLUK_OTO_YAYIN", "").strip().lower() in ("1", "true", "evet", "acik", "açık")


_OTO_YAYIN_KAPALI_DEGERLER = ("0", "false", "hayir", "hayır", "kapali", "kapalı")


def sozluk_oto_yayin_kapatildi_mi() -> bool:
    """Otomatik yayın AÇIKÇA kapatılmış mı: GitHub değişkeni `SOZLUK_OTO_YAYIN` ya da DB ayarı `sozluk_oto_yayin`
    '0' / 'kapali'. Tanımsız ya da boş = kapatılmamış.

    NİYE ayrı bir işlev: 12:30 çalıştırması `--oto-yayin` ile gelir; açık anahtarı beklemek zamanlamayı anlamsız
    kılar. Ama kod değiştirmeden, bir değişkenle durdurulabilen bir acil fren olmalı (yanlış kart yayınlandığında
    push ve dağıtım beklemeden)."""
    for deger in (os.environ.get("SOZLUK_OTO_YAYIN", ""), str(db.ayar_oku("sozluk_oto_yayin") or "")):
        if deger.strip().lower() in _OTO_YAYIN_KAPALI_DEGERLER:
            return True
    return False


def _sozluk_karti_sec() -> Tuple[Optional[Dict[str, Any]], Optional[bool]]:
    """(kart, taze). Kanunu değişmiş kart yayınlanmaz: Telegram'a bildirilir ve sıradakine geçilir.
    taze=None: kanun metni alınamadı (doğrulanamadı)."""
    from . import sozluk_arsivi
    reddedilen: set = set()
    for _ in range(8):
        kart = sozluk_arsivi.sonraki_kart(haric=reddedilen)
        if kart is None:
            return None, None
        taze, sorunlar = sozluk_arsivi.kart_kanun_durumu(kart)
        if taze is False:
            reddedilen.add(kart["kod"])
            log.warning("Sözlük kartı %s kanunla uyuşmuyor: %s", kart["kod"], "; ".join(sorunlar))
            mesaj_gonder(
                f"🛑 <b>Sözlük kartı {kart['kod']} ({html.escape(kart['terim'])}) durduruldu</b>\n"
                f"<i>Kanun metniyle uyuşmuyor; madde değişmiş olabilir:</i>\n"
                + "\n".join(f"• {html.escape(s)}" for s in sorunlar[:3])
                + "\n<i>Kart bu çalıştırmada atlandı; data/sozluk_kartlari.yaml'da güncellenmeli.</i>"
            )
            continue
        return kart, taze
    return None, None


def sozluk_karti_hazirla_ve_sun(oto_yayin: Optional[bool] = None) -> Optional[bool]:
    """Hazır arşivden sıradaki sözlük kartını hazırlar. Kart yoksa None döner (çağıran modele geçer).

    `oto_yayin`: True = bu çalıştırma otomatik yayına yetkili (zamanlanmış 12:30 işi `--oto-yayin` ile gelir),
    False = hiçbir zaman otomatik değil, None = anahtara bak (`sozluk_oto_yayin_acik_mi`).

    Otomatik yayın YALNIZCA şu koşulların hepsi varsa olur; biri eksikse kart onaya düşer:
    anahtar açıkça kapatılmamış, kanun metni alındı ve kartla tutuyor, bot duraklatılmamış, bugün başka
    otomatik sözlük yayınlanmamış, denetim kapısı uyarısız. Model hiçbir aşamada çalışmaz."""
    from . import sozluk_arsivi
    kart, taze = _sozluk_karti_sec()
    if kart is None:
        return None
    istenen = sozluk_oto_yayin_acik_mi() if oto_yayin is None else bool(oto_yayin)
    neden = ""
    if istenen:
        duraklatildi, _ = bot_duraklatildi_mi()
        if sozluk_oto_yayin_kapatildi_mi():
            neden = "otomatik yayın anahtarı kapatılmış (SOZLUK_OTO_YAYIN=0)"
        elif taze is not True:
            neden = "kanun metni alınamadığı için kart doğrulanamadı"
        elif duraklatildi:
            neden = "bot duraklatılmış"
        elif db.ayar_oku("sozluk_oto_son_gun") == _tr_bugun():
            neden = "bugün zaten bir sözlük kartı otomatik yayınlandı"
    otomatik = istenen and not neden
    if istenen and neden:
        mesaj_gonder(f"ℹ️ Sözlük kartı otomatik yayınlanmadı: {neden}. Onayınıza sunuluyor.")

    mesaj_gonder(f"📖 <b>Sözlük kartı</b> · {kart['kod']} · {html.escape(kart['terim'])}"
                 + (" · <b>otomatik yayın</b>" if otomatik else ""))
    kalan = sozluk_arsivi.stok_kalan(kart)
    if kalan <= sozluk_arsivi.STOK_UYARI_ESIGI:
        mesaj_gonder(
            f"📉 <b>Sözlük kartı stoğu azalıyor</b>: bu karttan sonra yayınlanmamış {kalan} kart kaldı "
            f"(günde bir kartla ≈{kalan} gün). Kartlar bitince sözlük her gün modelle üretilip onayınıza düşer; "
            f"tekrarsız {sozluk_arsivi.BEKLEME_GUN // 365} yıl için {sozluk_arsivi.HEDEF_KART} kart gerekir. Yeni kart yazılmalı."
        )
    veri = sozluk_arsivi.karttan_veri(kart)
    simdi = datetime.now(timezone.utc).isoformat()
    with db._baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet,
                                     eklenme_tarihi, onem_puani, kategori, manset, detay_metni,
                                     ig_caption, threads_metin, durum)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'yeni')""",
            (
                f"EDM Sözlük Kartı // {kart['kod']}",
                f"{kart['terim']} nedir?",
                f"edm://sozluk/{kart['kod']}/{int(time.time())}",
                veri.get("spot", ""),
                simdi,
                veri.get("onem_puani", 8),
                kart["kategori_kodu"],
                generate_text.manset_birlestir(veri),
                json.dumps(veri, ensure_ascii=False),
                veri.get("caption_instagram", ""),
                veri.get("caption_threads", ""),
            ),
        )
        haber_id = cur.lastrowid
        conn.commit()

    konu_bankasi.kullanildi_isaretle(kart["kod"], haber_id=haber_id, format_turu="sozluk")
    sonuc = haber_onayina_sun(haber_id, oto_yayin=otomatik)
    if otomatik:
        from . import durum_kurali
        if durum_kurali.yayinda_mi(db.haber_getir(haber_id) or {}):
            db.ayar_yaz("sozluk_oto_son_gun", _tr_bugun())
    return sonuc


def _sozluk_slotu(oto_yayin: Optional[bool] = None) -> bool:
    """Günün sözlüğü: önce hazır kart; kart kalmadıysa modelle üretilip HER ZAMAN onaya sunulur."""
    if oto_yayin is None:
        sonuc = sozluk_karti_hazirla_ve_sun()
    else:
        sonuc = sozluk_karti_hazirla_ve_sun(oto_yayin=oto_yayin)
    if sonuc is None:
        mesaj_gonder("ℹ️ Yayınlanabilir hazır sözlük kartı kalmadı; konu bankasından üretilip onayınıza sunuluyor.")
        return hizli_icerik_uret(format_turu="sozluk")
    return sonuc


def haberden_icerik_hazirla(haber: Dict[str, Any], brief: Dict[str, Any]) -> bool:
    """Triyajdan geçmiş haberi, konu bankası akışıyla AYNI yoldan içeriğe çevirir.

    Haber ham metin olarak değil, triyajın ürettiği brief olarak işleniyor —
    konu bankası girdisiyle aynı şekilde. Model artık açıyı kendisi uydurmuyor,
    hazır bir brief işliyor; kaliteyi yükselten şey bu.
    """
    mesaj_gonder(
        f"📰 <b>Haber içeriği</b> · {brief['sutun']} · {brief['bicim']} · puan {brief['_guven']}\n"
        f"<i>{haber.get('orijinal_baslik', '')[:120]}</i>\n\nİçerik hazırlanıyor..."
    )

    if not brief.get("_dayanak"):
        brief["_dayanak"] = haber.get("orijinal_ozet") or haber.get("orijinal_baslik") or ""
    # Model haberin tam metniyle çalışır (bkz. konu_bankasi.brief_metni). Eski
    # kayıtlarda gövdenin sonunda çerez/KVKK şablonu var; kuyruk burada da kesilir.
    from . import fetch_article
    makale = fetch_article.kuyrugu_kes(haber.get("makale_metni"))
    if len(makale) >= fetch_article.ASGARI_UZUNLUK:
        brief["_makale"] = makale[:fetch_article.AZAMI_UZUNLUK]
    if haber.get("orijinal_baslik") and not brief.get("baslik"):
        brief["baslik"] = haber["orijinal_baslik"]
    if haber.get("kaynak"):
        brief["kaynak"] = haber["kaynak"]

    veri = generate_text.konudan_uret(brief, format_turu="dailybrief")
    if not veri:
        mesaj_gonder("❌ Haber içeriği üretilemedi.")
        return False
    veri["format_turu"] = "dailybrief"
    if haber.get("gorsel_url"):
        veri["gorsel_url"] = haber["gorsel_url"]
        veri["gorsel_yolu"] = haber["gorsel_url"]
        veri["foto_yolu"] = haber["gorsel_url"]
    if haber.get("orijinal_url"):
        veri["orijinal_url"] = haber["orijinal_url"]
    if haber.get("kaynak"):
        veri["kaynak"] = haber["kaynak"]

    db.haber_guncelle(
        haber["id"],
        kategori=veri.get("kategori_kodu"),
        manset=generate_text.manset_birlestir(veri),
        detay_metni=json.dumps(veri, ensure_ascii=False),
        ig_caption=veri.get("caption_instagram"),
        threads_metin=veri.get("caption_threads"),
    )
    return haber_onayina_sun(haber["id"])


def konu_bankasindan_hazirla(gun: Optional[int] = None) -> bool:
    """Günün takvimine uygun konuyu bankadan alıp içerik üretir ve onaya sunar.

    Faz 1'in ana giriş noktası (ICERIK-SISTEMI.md §2). RSS'e bağımlı değildir:
    yüksek etkileşimli emlak içeriğinin çoğu haber değil evergreen bilgidir ve
    her gün üretilebilir olması takvimin aksamamasını sağlar.
    """
    konu = konu_bankasi.sonraki_konu(gun=gun, format_turu="b1")
    if not konu:
        mesaj_gonder(
            "⚠️ Konu bankasında uygun konu kalmadı. "
            "<code>data/konu_bankasi.yaml</code> dosyasına yeni konu eklenmeli."
        )
        return False

    mesaj_gonder(
        f"⏳ <b>{konu['kod']}</b> · {konu['sutun']} · {konu['bicim']}\n"
        f"<i>{konu['baslik']}</i>\n\nİçerik hazırlanıyor..."
    )

    veri = generate_text.konudan_uret(konu)
    if not veri:
        # Geçici API hatasında konuyu 3 gün kilitlemek yerine bakir tut
        mesaj_gonder("❌ İçerik üretilemedi. Gemini API yanıt vermedi. Konu bankadaki yerini koruyor.")
        return False

    orijinal_url = f"edm://konu/{konu['kod']}/{int(time.time())}"
    simdi = datetime.now(timezone.utc).isoformat()
    with db._baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet,
                                     eklenme_tarihi, onem_puani, kategori, manset, detay_metni,
                                     ig_caption, threads_metin, durum)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'yeni')""",
            (
                f"EDM Konu Bankası // {konu['kod']}",
                konu["baslik"],
                orijinal_url,
                veri.get("spot", ""),
                simdi,
                veri.get("onem_puani", 8),
                veri.get("kategori_kodu", "TAPU_VE_HUKUK"),
                generate_text.manset_birlestir(veri),
                json.dumps(veri, ensure_ascii=False),
                veri.get("caption_instagram", ""),
                veri.get("caption_threads", ""),
            ),
        )
        haber_id = cur.lastrowid
        conn.commit()

    konu_bankasi.kullanildi_isaretle(konu["kod"], haber_id=haber_id, format_turu="b1")
    return haber_onayina_sun(haber_id)


def slot_icerigi_hazirla_ve_sun(slot: str = "bilgilendirici", oto_yayin: Optional[bool] = None) -> bool:
    """Günün içeriği ve elle tetiklenen slotlar.

    - 'bilgilendirici': 10:00 TR'nin içeriği. Format dört günlük döngüde döner: b1, nedir_dogrusu,
      net_cevap, b1 (konu_bankasi.BILGILENDIRICI_FORMATLAR). Sözlük bu döngüde DEĞİL: her gün 12:30'da
      'sozluk' slotuyla ayrıca yayınlanır.
    - 'sozluk': sözlük içeriği (oto_yayin aktifse doğrudan yayınlanır).
    - 'haber': içerik ÜRETMEZ; taze haberleri tarihleriyle öneri olarak düşürür
      (haber_oneri). Hangisinin içeriğe çevrileceğine insan karar verir.
    """
    slot = (slot or "bilgilendirici").lower()

    if slot == "sozluk":
        log.info("Sözlük içeriği hazırlanıyor (Otomatik yayın: %s)...", oto_yayin)
        return _sozluk_slotu(oto_yayin=oto_yayin)

    if slot == "haber":
        from . import haber_oneri
        haber_oneri.onerileri_gonder(tara=True, bos_ise_bildir=True)
        return True

    secilen_format = konu_bankasi.siradaki_bilgilendirici_format()
    log.info("Günün içeriği — döngüdeki format: %s", secilen_format)
    if secilen_format == "b1":
        basarili = konu_bankasindan_hazirla()
    elif secilen_format == "sozluk":
        basarili = _sozluk_slotu(oto_yayin=oto_yayin)
    else:
        basarili = hizli_icerik_uret(format_turu=secilen_format)

    if basarili:
        konu_bankasi.bilgilendirici_format_kaydet(secilen_format)
    return basarili


def hizli_icerik_uret(format_turu: Optional[str] = None) -> bool:
    """Belirtilen formata (sozluk, nedir_dogrusu, vaka, net_cevap, b1, reels, rotasyon, haber) göre konuyu üretir ve onaya sunar."""
    if format_turu == "reels":
        return reels_hazirla_ve_sun()
    if format_turu == "rotasyon":
        return slot_icerigi_hazirla_ve_sun(slot="bilgilendirici")
    if format_turu == "haber":
        return slot_icerigi_hazirla_ve_sun(slot="haber")
    if format_turu == "b1":
        return konu_bankasindan_hazirla()

    etiketler = {
        "sozluk": "📖 EDM Gayrimenkul Sözlüğü",
        "nedir_dogrusu": "⚖️ Nedir Doğrusu?",
        "vaka": "📂 Örnek Olay",
        "net_cevap": "❓ Net Cevap Rehberi",
    }
    format_etiketi = etiketler.get(format_turu or "", "Otorite İçeriği")
    mesaj_gonder(f"⏳ <b>{format_etiketi}</b> için sıradaki konu hazırlanıyor...")

    konu = konu_bankasi.sonraki_konu(format_turu=format_turu)
    if not konu:
        mesaj_gonder("⚠️ Konu bankasında bakir konu kalmadı.")
        return False

    veri = generate_text.konudan_uret(konu, format_turu=format_turu)
    if not veri:
        mesaj_gonder("❌ İçerik üretilemedi. Gemini API yanıt vermedi.")
        return False

    if format_turu:
        veri["format_turu"] = format_turu

    orijinal_url = f"edm://konu/{konu['kod']}/{int(time.time())}"
    simdi = datetime.now(timezone.utc).isoformat()
    with db._baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet,
                                     eklenme_tarihi, onem_puani, kategori, manset, detay_metni,
                                     ig_caption, threads_metin, durum)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'yeni')""",
            (
                f"EDM Konu Bankası // {konu['kod']}",
                konu["baslik"],
                orijinal_url,
                konu.get("aci", ""),
                simdi,
                konu.get("onem_puani", 8),
                konu.get("sutun", "S1"),
                generate_text.manset_birlestir(veri) or konu["baslik"],
                json.dumps(veri, ensure_ascii=False),
                veri.get("caption_instagram", ""),
                veri.get("caption_threads", ""),
            ),
        )
        haber_id = cur.lastrowid
        conn.commit()

    konu_bankasi.kullanildi_isaretle(konu["kod"], haber_id=haber_id, format_turu=format_turu)
    return haber_onayina_sun(haber_id)


def reels_hazirla_ve_sun(konu_kodu: Optional[str] = None) -> bool:
    """Konu bankasından dikey Reels videosu üretip onaya sunar (bkz. _reels_hazirla_ve_sun)."""
    from . import yeni_formatlar
    try:
        return _reels_hazirla_ve_sun(konu_kodu)
    except yeni_formatlar.EksikIcerik as e:
        log.warning("Reels eksik alan yüzünden durdu: %s", e)
        _eksik_icerik_bildir(None, e)
        return False


def _reels_hazirla_ve_sun(konu_kodu: Optional[str] = None) -> bool:
    """
    Konu bankasından sıradaki konudan 9:16 dikey Reels içeriği üretir,
    slaytları Telegram grubuna görsel olarak gönderir ve haberle birebir aynı
    onay kartı ve buton yapısıyla onaya sunar.
    """
    mesaj_gonder("⏳ <b>EDM Reels Videosu (9:16 Dikey)</b> hazırlanıyor, lütfen bekleyin...")

    konu = konu_bankasi.sonraki_konu(format_turu="reels") if not konu_kodu else next((k for k in konu_bankasi.havuzu_yukle() if k["kod"] == konu_kodu), None)
    if not konu:
        mesaj_gonder("⚠️ Konu bankasında uygun konu bulunamadı.")
        return False

    konu_reels = dict(konu)
    bicim = konu_reels.get("bicim") or "dailybrief"

    veri = generate_text.konudan_uret(konu_reels)
    if not veri:
        mesaj_gonder("❌ Gemini metin üretemedi.")
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
    return haber_onayina_sun(haber_id)


def format_degistir_ve_sun(haber_id: int, hedef_format: str) -> bool:
    """Onay bekleyen bir içeriğin görsel formatını anında değiştirip yeni önizlemeyi sunar."""
    haber = db.haber_getir(haber_id)
    if not haber:
        return False

    detay_metni = haber.get("detay_metni")
    veri = json.loads(detay_metni) if detay_metni else {}
    veri["format_turu"] = hedef_format
    db.haber_guncelle(haber_id, detay_metni=json.dumps(veri, ensure_ascii=False), slayt_yollari=None, slayt_urlleri=None, video_yolu=None)
    mesaj_gonder(f"🎨 Haber #{haber_id} <b>{hedef_format.upper()}</b> formatına dönüştürülüyor...")
    return haber_onayina_sun(haber_id)


def otorite_postu_hazirla_ve_sor(konu: str, kategori_kodu: Optional[str] = None) -> bool:
    """Belirtilen hukuki, finansal veya sektörel bir konudan 4 slaytlık otorite postu üretip Telegram'a sunar."""
    mesaj_gonder(f"⏳ <b>'{konu[:60]}...'</b> konusu için EDM Otorite Carousel içeriği hazırlanıyor...")

    # 1. Gemini ile 4 slaytlık otorite içeriği üret
    veri = generate_text.otorite_icerigi_uret(konu, kategori_kodu=kategori_kodu)
    if not veri:
        mesaj_gonder("❌ Otorite içeriği üretilemedi. Gemini API yanıt vermedi.")
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
    return haber_onayina_sun(haber_id)


def tek_tikla_ilan_menusu_gonder() -> bool:
    """Portföydeki aktif ilanları buton listesi olarak Telegram'a gönderir."""
    ilanlar = fetch_listings.aktif_ilanlar(limit=6)
    if not ilanlar:
        mesaj_gonder("Portföyde paylaşılacak aktif ilan bulunamadı.")
        return False

    satirlar = []
    for i in ilanlar:
        fiyat_str = fetch_listings.ilan_fiyat_bicimlendir(float(i.get("fiyat", 0)), i.get("paraBirimi", "TRY"))
        kisa_baslik = i.get("baslik", "")[:35]
        buton_metni = f"🏡 {i.get('ilce')} {i.get('tip')} ({fiyat_str}) — {kisa_baslik}"
        satirlar.append([{"text": buton_metni, "callback_data": f"ilan_sec:{i.get('id')}"}])

    satirlar.append([{"text": "🔄 İlan Listesini Yenile", "callback_data": "ilan_menu_yenile"}])

    reply_markup = {"inline_keyboard": satirlar}
    mesaj_gonder(
        "<b>EDM PORTFÖYÜ — TEK TIKLA İLAN PAYLAŞ</b>\n\n"
        "Aşağıdaki aktif ilanlarımızdan birini seçin, anında 4:5 kartları ve metni üretilip onayınıza sunulsun:",
        reply_markup=reply_markup,
    )
    return True


def ilan_postunu_hazirla_ve_sor(ilan_id: str) -> bool:
    """Seçilen ilanın slaytlarını ve metnini üretip onay butonlarıyla gruba gönderir."""
    ilan = db.ilan_getir(ilan_id)
    if not ilan:
        return False

    mesaj_gonder(f"⏳ <b>#{ilan_id}</b> nolu ilan için görseller ve açıklama hazırlanıyor...")

    # 1. Metin üret
    metinler = generate_text.ilan_metinleri_uret(ilan)

    # 2. Slayt görsellerini üret (3'lü Prestij Carousel)
    k1 = make_image.ilan_kapak_slayti_ciz(ilan)
    k2 = make_image.ilan_detay_slayti_ciz(ilan)
    k3 = make_image.ilan_kapanis_slayti_ciz(ilan)

    slayt_yollari = [str(k1), str(k2), str(k3)]

    # 2.5 CDN yükleme
    slayt_urlleri = []
    try:
        slayt_urlleri = upload_image.coklu_gorsel_yukle(slayt_yollari)
    except Exception as e:
        log.warning("İlan slaytları CDN'e yüklenemedi: %s", e)

    raw_caption = (metinler.get("ig_caption") if metinler else "") or (
        f"{ilan.get('baslik')}\n\n"
        f"📍 Konum: {ilan.get('ilce')} / {ilan.get('mahalle')}\n"
        f"💰 Fiyat: {fetch_listings.ilan_fiyat_bicimlendir(float(ilan.get('fiyat', 0)))}\n\n"
        f"EDM Yapı & Gayrimenkul · 0212 727 29 55\nedmyapigayrimenkul.com"
    )
    caption = generate_text.caption_zenginlestir(
        raw_caption,
        kategori_kodu="ILAN",
        platform="instagram",
        manset=ilan.get("baslik"),
    )

    # 2.7 Önceki tüm mesajları temizle
    icerik_onceki_mesajlarini_temizle("ilan_album", ilan_id)
    icerik_onceki_mesajlarini_temizle("ilan", ilan_id)

    # 3. Slayt görsellerini albüm olarak gönder
    album_caption = f"🏡 <b>EDM PORTFÖY // İLAN CAROUSEL (4:5)</b>\n📌 {html.escape(str(ilan.get('baslik') or ''), quote=False)}"
    album_res = medya_grubu_gonder(slayt_yollari, caption=album_caption, yedek_urller=slayt_urlleri)
    _, chat_id = _bot_bilgileri()
    cid = int(str(chat_id).strip()) if str(chat_id).lstrip("-").isdigit() else None
    album_mids = album_res if isinstance(album_res, list) else []
    gorsel_notu = _album_teslim_notu(album_res, min(len(slayt_yollari), 10), slayt_urlleri)
    for mid in album_mids:
        try:
            db.onay_istegi_kaydet("ilan_album", str(ilan_id), mid, cid)
        except Exception as e:
            log.warning("İlan albüm mesaj ID kaydedilemedi: %s", e)

    # 4. İnteraktif Onay Menüsü + Kopyalanabilir Caption (Haberle Birebir Aynı Standart)
    import html as html_lib
    temiz_caption = html_lib.escape(caption.strip())
    rozet = "PORTFÖY İLANI"
    dayanak = f"{ilan.get('ilce', '')} / {ilan.get('mahalle', '')}".strip(" /") or "EDM Portföy"
    fiyat_str = fetch_listings.ilan_fiyat_bicimlendir(float(ilan.get("fiyat", 0)))

    kart_baslik = f"🏡 <b>PORTFÖY İLANI ONAY BEKLİYOR (#{ilan_id})</b>\n\n"
    mesaj_metni = (
        gorsel_notu
        + kart_baslik
        + f"<b>Kategori:</b> {rozet}\n"
        f"<b>Dayanak:</b> {html_lib.escape(dayanak, quote=False)} · {fiyat_str}\n"
        f"<b>Manşet:</b> {html_lib.escape(str(ilan.get('baslik') or ''), quote=False)}\n"
        f"<b>Önem Puanı:</b> 10/10\n"
        f"<b>İçerik No:</b> #{ilan_id}\n\n"
    )
    if temiz_caption:
        mesaj_metni += f"<pre><code>{temiz_caption}</code></pre>\n\n"
    mesaj_metni += "<i>Bu içeriği onaylıyor musunuz? Kanalları seçip tek tıkla yayınlayabilirsiniz:</i>"

    ilan_kanallari = {"ig": True, "reels": False, "story": True, "threads": True, "facebook": True, "youtube": False, "tiktok": False, "linkedin": True}
    butonlar = ana_menu(adet=len(slayt_yollari), kanallar=ilan_kanallari)
    res = _onay_kartini_gonder(ilan_id, mesaj_metni, butonlar, html_lib.escape(str(ilan.get("baslik") or ""), quote=False), "ilan")
    if res and isinstance(res, dict) and "message_id" in res:
        try:
            db.onay_istegi_kaydet("ilan", str(ilan_id), res["message_id"], cid)
        except Exception as e:
            log.warning("İlan onay isteği kaydedilemedi: %s", e)

    try:
        from . import db_senkron
        db_senkron.hemen_kaydet(f"db: ilan #{ilan_id} onaya sunuldu")
    except Exception as e:
        log.warning("Hemen kaydetme adımı atlandı: %s", e)

    return True


def finans_icerigi_hazirla_ve_yayinla(oto_yayin: bool = True) -> bool:
    """Finans, bankacılık, faiz, konut kredisi veya yakın sektörleri ele alan bülteni hazırlar.
    
    Kullanıcı Kuralı:
      - oto_yayin=True ise Telegram onayına takılmadan doğrudan canlı yayınlanır.
      - YouTube: Her zaman Shorts (Sesli dikey video).
      - YouTube dışındaki tüm kanallar (IG, FB, Threads, Story, TT): Standart gönderi!
    """
    konu = konu_bankasi.sonraki_finans_konusu(format_turu="finans")
    if not konu:
        mesaj_gonder("⚠️ Konu bankasında uygun finans / bankacılık konusu bulunamadı.")
        return False

    bilgi_baslik = "🚀 <b>GÜNLÜK FİNANS & EMLAK BÜLTENİ (OTOMATİK YAYIN)</b>" if oto_yayin else "⏳ <b>GÜNLÜK FİNANS & EMLAK BÜLTENİ</b>"
    mesaj_gonder(
        f"{bilgi_baslik}\n\n"
        f"📌 <b>{konu['kod']}</b> · {konu['sutun']} · {konu['bicim']}\n"
        f"<i>{konu['baslik']}</i>\n\n"
        f"İçerik, görseller ve video hazırlanıyor..."
    )

    veri = generate_text.konudan_uret(konu)
    if not veri:
        mesaj_gonder("❌ Finans içeriği üretilemedi. Gemini API yanıt vermedi.")
        return False

    orijinal_url = f"edm://finans/{konu['kod']}/{int(time.time())}"
    simdi = datetime.now(timezone.utc).isoformat()
    with db._baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet,
                                     eklenme_tarihi, onem_puani, kategori, manset, detay_metni,
                                     ig_caption, threads_metin, durum)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'yeni')""",
            (
                f"EDM Finans // {konu['kod']}",
                konu["baslik"],
                orijinal_url,
                veri.get("spot", ""),
                simdi,
                veri.get("onem_puani", 9),
                "FINANS_VE_BANKACILIK",
                generate_text.manset_birlestir(veri) or konu["baslik"],
                json.dumps(veri, ensure_ascii=False),
                veri.get("caption_instagram", ""),
                veri.get("caption_threads", ""),
            ),
        )
        haber_id = cur.lastrowid
        conn.commit()

    konu_bankasi.kullanildi_isaretle(konu["kod"], haber_id=haber_id, format_turu="finans")

    # 1. 4:5 Slaytları Üret (Instagram, Facebook, Threads, TikTok için)
    from . import make_image, video, ses
    try:
        slayt_yollari = make_image.otorite_gonderi_slaytlari_uret(veri, cikti_onek=f"haber_{haber_id}")
    except make_image.EksikIcerik as e:
        # Otomatik yayın yolu da yarım/taşan görseli yayınlamaz
        log.warning("Finans #%d görseli üretilemedi: %s", haber_id, e)
        _eksik_icerik_bildir(haber_id, e)
        return False
    slayt_str_yollari = [str(p) for p in slayt_yollari]

    # CDN yükleme
    slayt_urlleri = []
    try:
        slayt_urlleri = upload_image.coklu_gorsel_yukle(slayt_yollari)
    except Exception as ue:
        log.warning("Finans slaytları CDN'e yüklenemedi: %s", ue)

    # 2. YouTube Shorts için dikey 9:16 video ve fon müziği hazırla
    v_yolu = None
    try:
        v_yolu = video.slaytlardan_reels_uret(slayt_str_yollari)
        if v_yolu and v_yolu.exists():
            sesli_v = ses.sesli_video_hazirla(v_yolu, ses_seviyesi=0.20)
            if sesli_v and sesli_v.exists():
                v_yolu = sesli_v
    except Exception as ve:
        log.warning("YouTube Shorts dikey videosu üretilemedi: %s", ve)

    db.haber_guncelle(
        haber_id,
        slayt_yollari=json.dumps(slayt_str_yollari, ensure_ascii=False),
        slayt_urlleri=json.dumps(slayt_urlleri) if slayt_urlleri else None,
        video_yolu=str(v_yolu) if v_yolu else None,
    )

    # DOĞRULAMA KAPISI: otomatik yayın insan onayını atlıyor; bu yüzden en ufak
    # denetim uyarısında (doğrulanmamış madde numarası, kaynaksız faiz/oran,
    # abartı) yayın DURUR ve içerik onaya düşer. Finansta "dayanaksız rakam"
    # da kritiktir: faiz ve kredi koşulları okuyanın parasını etkiler.
    # Model yazdığı için kapı iki ayaklıdır (dogrula.otomatik_yayina_uygun_mu): hiç uyarı olmamalı VE anlam
    # hakemi (ikinci model) gerçekten çalışıp temiz demiş olmalı. Hakem kota/kaynak yüzünden çalışamadıysa
    # "temiz" varsayılmaz; içerik onaya düşer.
    from . import dogrula
    if oto_yayin:
        uygun, uyarilar = dogrula.otomatik_yayina_uygun_mu(veri)
        if not uygun:
            log.warning("Finans #%d otomatik yayını durduruldu: %s", haber_id, "; ".join(uyarilar))
            mesaj_gonder(
                f"🛑 <b>Otomatik yayın durduruldu (#{haber_id})</b> — {len(uyarilar)} denetim bulgusu.\n"
                + "\n".join(html.escape(u) for u in uyarilar[:3])
                + "\n<i>İçerik onayına sunuluyor; uyarıları kontrol edip elle yayınla.</i>"
            )
            oto_yayin = False

    if not oto_yayin:
        return haber_onayina_sun(haber_id)

    # Önce slayt görsellerini Telegram grubuna ilet
    try:
        medya_grubu_gonder(
            slayt_yollari,
            caption=f"📊 <b>GÜNLÜK FİNANS & BANKACILIK POSTU</b>\n📌 {veri.get('manset') or konu['baslik']}"
        )
    except Exception as me:
        log.warning("Finans albümü Telegram'a iletilemedi: %s", me)

    # Otomatik Yayın Akışı (Bana sormadan paylaşılsın)
    # Hedefler: ig,threads,story,tiktok,facebook,youtube
    # reels_modu = False olduğu için YouTube video alır, Facebook dahil diğer tüm kanallar standart post alır.
    komut = [
        sys.executable,
        str(KOK / "scripts/yayinla.py"),
        "--tur", "haber",
        "--id", str(haber_id),
        "--hedef", "ig,threads,story,tiktok,facebook,youtube",
    ]
    log.info("Finans bülteni otomatik yayınlanıyor: %s", komut)
    calisma = subprocess.run(komut, cwd=KOK, capture_output=True, text=True, timeout=15 * 60)
    
    # yayinla.py kendi içinde rapor gönderir ve DB'yi günceller
    if calisma.returncode == 0 or "POSTEDM_SONUC=" in calisma.stdout:
        log.info("Finans bülteni otomatik yayını tamamlandı.")
        return True
    else:
        log.error("Finans bülteni otomatik yayınlanamadı: %s\n%s", calisma.stdout, calisma.stderr)
        mesaj_gonder(
            f"⚠️ <b>Finans bülteni otomatik yayınlanırken hata oluştu:</b>\n"
            f"<pre>{html.escape(calisma.stderr[-1000:])}</pre>"
        )
        return False

