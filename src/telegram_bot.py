"""
telegram_bot.py — EDM Telegram Onay ve Yönetim Botu
Haber ve İlan önizlemelerini Telegram grubuna iletir, inline butonlarla onay alır.
Tek tıkla portföyden ilan seçip post üretme özelliğini yönetir.
"""

from __future__ import annotations

import html
import json
import logging
import re
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from . import config, db, fetch_listings, generate_text, komutlar, konu_bankasi, make_image, upload_image

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
                    parametreler["text"] = re.sub(r"<[^>]+>", "", parametreler["text"])
                if "caption" in parametreler and isinstance(parametreler["caption"], str):
                    parametreler["caption"] = re.sub(r"<[^>]+>", "", parametreler["caption"])
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
    payload: Dict[str, Any] = {
        "text": metin,
        "disable_web_page_preview": True,
    }
    if html:
        payload["parse_mode"] = "HTML"
    if markup:
        payload["reply_markup"] = markup

    return _istek("sendMessage", **payload)


def fotograf_gonder(
    foto_yolu_veya_url: Path | str,
    caption: str = "",
    reply_markup: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Tekil fotoğrafı Telegram'a gönderir (yerel dosya veya URL desteğiyle)."""
    token, chat_id = _bot_bilgileri()
    if not token or not chat_id:
        return None

    url = TELEGRAM_API_URL.format(token=token, method="sendPhoto")
    data: Dict[str, Any] = {
        "chat_id": chat_id,
        "caption": caption[:1024],
        "parse_mode": "HTML",
    }
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)

    p = Path(str(foto_yolu_veya_url))
    try:
        if p.exists() and p.is_file():
            with open(p, "rb") as f:
                r = requests.post(url, data=data, files={"photo": f}, timeout=35)
        else:
            data["photo"] = str(foto_yolu_veya_url)
            r = requests.post(url, data=data, timeout=35)

        if r.status_code == 200:
            return r.json().get("result")

        # HTML entity parse hatası durumunda düz metinle kurtar
        resp_json = r.json() if r.content else {}
        if "can't parse entities" in (resp_json.get("description") or "").lower():
            data.pop("parse_mode", None)
            data["caption"] = re.sub(r"<[^>]+>", "", caption[:1024])
            if p.exists() and p.is_file():
                with open(p, "rb") as f:
                    r2 = requests.post(url, data=data, files={"photo": f}, timeout=35)
            else:
                r2 = requests.post(url, data=data, timeout=35)
            if r2.status_code == 200:
                return r2.json().get("result")

        log.error("Telegram fotoğraf hatası [%d]: %s", r.status_code, r.text)
    except Exception as e:
        log.error("Telegram fotoğraf gönderme hatası: %s", e)
    return None


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

    try:
        with open(p, "rb") as f:
            r = requests.post(url, data=data, files={"video": f}, timeout=180)
        veri = r.json() if r.content else {}
        if not veri.get("ok"):
            if "can't parse entities" in (veri.get("description") or "").lower():
                data.pop("parse_mode", None)
                with open(p, "rb") as f2:
                    r2 = requests.post(url, data=data, files={"video": f2}, timeout=180)
                veri2 = r2.json() if r2.content else {}
                if veri2.get("ok"):
                    return veri2["result"]["message_id"]
            log.warning("Telegram video gönderme hatası: %s", veri.get("description", r.text[:200]))
            return None
        return veri["result"]["message_id"]
    except Exception as e:
        log.exception("Telegram video gönderme istisnası: %s", e)
        return None


def medya_grubu_gonder(foto_yollari: List[Path | str], caption: str = "") -> bool:
    """Carousel önizlemesi için albüm (medya grubu) gönderir.

    WEBPAGE_CURL_FAILED ve ağ zaman aşımına karşı instabot koruması içerir:
    1. Yerel dosya varsa doğrudan yerel dosyadan açıp multipart/form-data ile gönderir (sıfır ağ gecikmesi).
    2. Uzak URL verilmişse ve yerelde kopyası yoksa, URL ile dener; Telegram WEBPAGE_CURL_FAILED verirse
       arka planda indirip BytesIO üzerinden multipart stream ile anında kurtarır.
    """
    token, chat_id = _bot_bilgileri()
    if not token or not chat_id or not foto_yollari:
        return False

    import io
    url = TELEGRAM_API_URL.format(token=token, method="sendMediaGroup")
    foto_yollari = foto_yollari[:10]

    def _yerel_dosya_bul(f_yol: Path | str) -> Optional[Path]:
        p = Path(str(f_yol))
        if p.exists() and p.is_file():
            return p
        # upload_image önbelleğinden bak
        try:
            yerel = upload_image.yerel_karsiligi(str(f_yol))
            if yerel and yerel.exists() and yerel.is_file():
                return yerel
        except Exception:
            pass
        # data/output veya output altında isim eşleşmesi ara
        temiz_ad = Path(str(f_yol).split("?")[0]).name
        for klasor in [Path("data/output"), Path("output")]:
            olasi = klasor / temiz_ad
            if olasi.exists() and olasi.is_file():
                return olasi
        return None

    # Strateji 1: Tüm görseller yerelde var mı veya yerel karşılıkları bulunabiliyor mu?
    yereller = [_yerel_dosya_bul(fy) for fy in foto_yollari]
    hepsi_yerel = all(y is not None for y in yereller)

    if hepsi_yerel:
        files = {}
        handles = []
        media = []
        try:
            for idx, yerel_p in enumerate(yereller):
                attach_name = f"photo_{idx}"
                m_item: Dict[str, Any] = {"type": "photo", "media": f"attach://{attach_name}"}
                if idx == 0 and caption:
                    m_item["caption"] = caption[:1024]
                    m_item["parse_mode"] = "HTML"
                media.append(m_item)
                fh = open(yerel_p, "rb")
                handles.append(fh)
                files[attach_name] = (yerel_p.name, fh, "image/jpeg")

            r = requests.post(url, data={"chat_id": chat_id, "media": json.dumps(media)}, files=files, timeout=60)
            if r.status_code == 200:
                return True

            # Caption parse hatası varsa parse_mode kaldırıp tekrar dene
            if "can't parse entities" in r.text.lower() and caption:
                for m in media:
                    m.pop("parse_mode", None)
                    if "caption" in m:
                        m["caption"] = re.sub(r"<[^>]+>", "", m["caption"])
                for fh in handles:
                    fh.seek(0)
                r_fallback = requests.post(url, data={"chat_id": chat_id, "media": json.dumps(media)}, files=files, timeout=60)
                if r_fallback.status_code == 200:
                    return True

            log.warning("Yerel multipart medya grubu gönderimi başarısız [%d]: %s", r.status_code, r.text[:200])
        except Exception as e:
            log.warning("Yerel medya grubu istisnası: %s", e)
        finally:
            for fh in handles:
                try:
                    fh.close()
                except Exception:
                    pass

    # Strateji 2: URL tabanlı gönderim dene
    media_url = []
    for idx, f_yol in enumerate(foto_yollari):
        m_item = {"type": "photo", "media": str(f_yol)}
        if idx == 0 and caption:
            m_item["caption"] = caption[:1024]
            m_item["parse_mode"] = "HTML"
        media_url.append(m_item)

    try:
        r = requests.post(url, json={"chat_id": chat_id, "media": media_url}, timeout=30)
        if r.status_code == 200:
            return True

        hata_aciklama = r.text.lower()
        if "can't parse entities" in hata_aciklama and caption:
            for m in media_url:
                m.pop("parse_mode", None)
                if "caption" in m:
                    m["caption"] = re.sub(r"<[^>]+>", "", m["caption"])
            r_fb = requests.post(url, json={"chat_id": chat_id, "media": media_url}, timeout=30)
            if r_fb.status_code == 200:
                return True

        # Telegram WEBPAGE_CURL_FAILED veya indirme zaman aşımı verdiyse:
        if "webpage_curl_failed" in hata_aciklama or "failed to send message" in hata_aciklama:
            log.warning("Telegram URL'den indiremedi (WEBPAGE_CURL_FAILED), acil indirme ve stream yüklemeye geçiliyor...")
            stream_files = {}
            stream_media = []
            headers_dl = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

            for idx, f_yol in enumerate(foto_yollari):
                attach_name = f"photo_{idx}"
                s_item = {"type": "photo", "media": f"attach://{attach_name}"}
                if idx == 0 and caption:
                    s_item["caption"] = re.sub(r"<[^>]+>", "", caption[:1024])
                stream_media.append(s_item)

                yerel_var = _yerel_dosya_bul(f_yol)
                if yerel_var:
                    stream_files[attach_name] = (yerel_var.name, open(yerel_var, "rb"), "image/jpeg")
                else:
                    dl_resp = requests.get(str(f_yol), headers=headers_dl, timeout=25)
                    if dl_resp.status_code == 200:
                        stream_files[attach_name] = (f"foto_{idx}.jpg", io.BytesIO(dl_resp.content), "image/jpeg")

            if len(stream_files) == len(foto_yollari):
                r_dl = requests.post(url, data={"chat_id": chat_id, "media": json.dumps(stream_media)}, files=stream_files, timeout=60)
                for f_tuple in stream_files.values():
                    if hasattr(f_tuple[1], "close"):
                        f_tuple[1].close()
                if r_dl.status_code == 200:
                    log.info("WEBPAGE_CURL_FAILED hatası stream multipart ile başarıyla kurtarıldı.")
                    return True
    except Exception as e:
        log.error("Telegram medya grubu gönderme hatası: %s", e)

    return False


def mesaji_sil(mesaj_id: int) -> bool:
    """Belirtilen mesajı siler; mesaj zaten silinmişse çökmeden False döner."""
    res = _istek("deleteMessage", message_id=mesaj_id)
    return bool(res)


def mesaji_guncelle(mesaj_id: int, metin: str, reply_markup: Optional[Dict[str, Any]] = None) -> bool:
    """Var olan mesajı günceller; 'message is not modified' durumunda çökmez."""
    res = _istek(
        "editMessageText",
        message_id=mesaj_id,
        text=metin,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=reply_markup,
    )
    return bool(res)


def sonucu_yaz(mesaj_id: int, metin: str, reply_markup: Optional[Dict[str, Any]] = None) -> bool:
    """İşlem tamamlandığında butonları kaldırır veya sonucu yazar."""
    return mesaji_guncelle(mesaj_id, metin, reply_markup=reply_markup)


def durum_guncelle(mesaj_id: int, baslik: str, adim: int, toplam_adim: int = 4, detay: str = "") -> None:
    """İşlem sürerken Telegram'da görsel progress bar günceller."""
    dolu = "█" * adim
    bos = "░" * max(0, toplam_adim - adim)
    yuzde = int((adim / max(1, toplam_adim)) * 100)
    metin = (
        f"⏳ <b>{baslik}</b>\n\n"
        f"<code>[{dolu}{bos}] %{yuzde}</code>\n"
        f"<i>{detay}</i>"
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
    return {"ig": True, "threads": True, "fb": False}


def kanal_ayarla(kanal: str, aktif: bool) -> Dict[str, bool]:
    """Kanal durumunu günceller ve kaydeder."""
    kanallar = varsayilan_kanallar()
    kanallar[kanal] = aktif
    db.ayar_yaz("aktif_kanallar", json.dumps(kanallar))
    return kanallar


def kanal_butonlari(kanallar: Optional[Dict[str, bool]] = None) -> List[List[Dict[str, str]]]:
    """Tek tıkla açılıp kapanabilen kompakt kanal toggle butonları döner."""
    if kanallar is None:
        kanallar = varsayilan_kanallar()

    def _simge(k: str) -> str:
        return "✅" if kanallar.get(k, False) else "⬜"

    return [
        [
            {"text": f"{_simge('ig')} Instagram", "callback_data": "kanal_toggle:ig"},
            {"text": f"{_simge('threads')} Threads", "callback_data": "kanal_toggle:threads"},
            {"text": f"{_simge('fb')} Facebook", "callback_data": "kanal_toggle:fb"},
        ]
    ]


def onay_menusu(haber_id: int, kanallar: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    """İçerik onayına sunulduğunda gösterilen tam yetkili kontrol menüsü."""
    if kanallar is None:
        kanallar = varsayilan_kanallar()

    aktif_list = [k for k, v in kanallar.items() if v]
    hedef_param = ",".join(aktif_list) if aktif_list else "ig,threads"

    return {
        "inline_keyboard": [
            *kanal_butonlari(kanallar),
            [
                {"text": "🚀 Seçili Kanallarda Yayınla", "callback_data": f"onayla:haber:{hedef_param}:{haber_id}"},
            ],
            [
                {"text": "🔄 Metinleri Yenile", "callback_data": f"yenile:haber:{haber_id}"},
                {"text": "🎨 Formatı Değiştir", "callback_data": f"format_menu:{haber_id}"},
            ],
            [
                {"text": "⏰ 1 Saat Ertele", "callback_data": f"ertele:haber:{haber_id}"},
                {"text": "❌ İptal / Reddet", "callback_data": f"reddet:haber:{haber_id}"},
            ],
        ]
    }


def format_secim_menusu(haber_id: int) -> Dict[str, Any]:
    """İçeriğin görsel formatını tek tıkla değiştirmek için sunulan menü."""
    return {
        "inline_keyboard": [
            [
                {"text": "📖 EDM Sözlük", "callback_data": f"format_uygula:sozluk:{haber_id}"},
                {"text": "⚖️ Nedir Doğrusu?", "callback_data": f"format_uygula:nedir_dogrusu:{haber_id}"},
            ],
            [
                {"text": "📂 Vaka Analizi", "callback_data": f"format_uygula:vaka:{haber_id}"},
                {"text": "❓ Net Cevap", "callback_data": f"format_uygula:net_cevap:{haber_id}"},
            ],
            [
                {"text": "← Onay Menüsüne Dön", "callback_data": f"onay_menu_don:{haber_id}"},
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
                {"text": "📖 Sözlük Üret", "callback_data": "hizli_uret:sozluk"},
                {"text": "⚖️ Nedir Doğrusu?", "callback_data": "hizli_uret:nedir_dogrusu"},
            ],
            [
                {"text": "📂 Vaka Analizi", "callback_data": "hizli_uret:vaka"},
                {"text": "❓ Net Cevap", "callback_data": "hizli_uret:net_cevap"},
            ],
            [
                {"text": "🎬 Reels Videosu Üret (9:16)", "callback_data": "hizli_uret:reels"},
            ],
            [
                {"text": "📊 Sıradaki Post & Durum", "callback_data": "durum"},
                duraklat_butonu,
            ],
            [
                {"text": "🩺 Sistem Sağlık Testi", "callback_data": "saglik_testi"},
                {"text": "🔄 Konu Havuzu Durumu", "callback_data": "havuz_durum"},
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


def komut_menusu_kaydet() -> bool:
    """Telegram komut açılır menüsünü (setMyCommands) 3 kapsama birden kaydeder."""
    kapsamlar = [
        None,
        {"type": "all_private_chats"},
        {"type": "all_group_chats"},
    ]
    basarili = 0
    token, _ = _bot_bilgileri()
    if not token:
        return False

    url = TELEGRAM_API_URL.format(token=token, method="setMyCommands")
    for kapsam in kapsamlar:
        payload: Dict[str, Any] = {"commands": komutlar.KOMUT_MENUSU}
        if kapsam:
            payload["scope"] = json.dumps(kapsam)
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


def haber_onayina_sun(haber_id: int) -> bool:
    """Haberin görselini ve metnini hazırlayıp Telegram onayına sunar."""
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

    # 2. Slayt görsellerini al veya üret
    slayt_yollari = []
    if haber.get("slayt_yollari"):
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

    if not slayt_yollari:
        from . import yeni_formatlar
        if otorite_verisi and isinstance(otorite_verisi, dict):
            slayt_listesi = yeni_formatlar.slaytlari_uret(otorite_verisi, cikti_onek=f"gonderi_{haber_id}")
            slayt_yollari = [str(p) for p in slayt_listesi]
        else:
            # Fallback durumunda da yeni format motorunu kullan
            fallback_veri = {
                "kategori_kodu": haber.get("kategori") or "TAPU_VE_HUKUK",
                "manset_parca_1": haber.get("manset") or haber.get("orijinal_baslik", ""),
                "manset_vurgu": "",
                "manset_parca_2": "",
                "spot": haber.get("detay_metni") or haber.get("orijinal_ozet", ""),
                "bicim": "B1",
            }
            slayt_listesi = yeni_formatlar.slaytlari_uret(fallback_veri, cikti_onek=f"gonderi_{haber_id}")
            slayt_yollari = [str(p) for p in slayt_listesi]

    rozet = "HUKUK & YATIRIM REHBERİ"
    dayanak = haber.get("kaynak", "EDM Yapı & Gayrimenkul")
    if otorite_verisi and isinstance(otorite_verisi, dict):
        rozet = otorite_verisi.get("rozet_metni", rozet)
        dayanak = otorite_verisi.get("yasal_dayanak", dayanak)

    # 2.5 Slaytları Public CDN'e yükle (Runner bağımsızlığı ve API'ler için)
    slayt_urlleri = []
    try:
        slayt_urlleri = upload_image.coklu_gorsel_yukle(slayt_yollari)
    except Exception as e:
        log.warning("Görseller CDN'e yüklenemedi: %s", e)

    db.haber_guncelle(
        haber_id,
        slayt_yollari=json.dumps(slayt_yollari),
        slayt_urlleri=json.dumps(slayt_urlleri) if slayt_urlleri else None,
        durum="onay_bekliyor"
    )

    # 3. Medya albümü gönder
    caption_ozeti = (haber.get("ig_caption") or "")[:350]

    # Yayın öncesi denetim. Otomatik eleme yapmıyor; onaylayan kişiye
    # "şuna bir daha bak" diyor. En kritik denetim uydurma kanun maddesi:
    # gerçek bir emlak ofisinin hesabında bu ciddi bir sorumluluk.
    denetim_basligi = ""
    if otorite_verisi and isinstance(otorite_verisi, dict):
        try:
            from . import dogrula
            uyarilar = dogrula.denetle(otorite_verisi, otorite_verisi.get("_brief"))
            denetim_basligi = dogrula.uyari_basligi(uyarilar)
            if uyarilar:
                log.info("Denetim uyarıları (#%d): %s", haber_id, "; ".join(uyarilar))
        except Exception as e:
            log.warning("Denetim çalıştırılamadı: %s", e)

    onizleme_metni = (
        denetim_basligi
        + f"🏛 <b>YENİ OTORİTE İÇERİĞİ ONAY BEKLİYOR</b>\n\n"
        f"<b>Kategori:</b> {rozet}\n"
        f"<b>Dayanak:</b> {dayanak}\n"
        f"<b>Manşet:</b> {haber['manset']}\n"
        f"<b>Önem Puanı:</b> {haber.get('onem_puani', 8)}/10\n\n"
        f"<b>Açıklama (Instagram/Facebook):</b>\n{caption_ozeti}..."
    )

    medya_grubu_gonder(slayt_yollari, caption=onizleme_metni)

    # 4. İnteraktif Onay Menüsü (Kanal Toggle, Format Değiştirme, Yenileme, Erteleme)
    butonlar = onay_menusu(haber_id)
    res = mesaj_gonder("Bu içeriği onaylıyor musunuz? Kanalları seçip tek tıkla yayınlayabilirsiniz:", reply_markup=butonlar)
    if res and isinstance(res, dict) and "message_id" in res:
        _, chat_id = _bot_bilgileri()
        try:
            cid = int(str(chat_id).strip()) if str(chat_id).lstrip("-").isdigit() else None
            db.onay_istegi_kaydet("haber", str(haber_id), res["message_id"], cid)
        except Exception as e:
            log.warning("Onay isteği kaydedilemedi: %s", e)
    return True


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

    veri = generate_text.konudan_uret(brief)
    if not veri:
        mesaj_gonder("❌ Haber içeriği üretilemedi.")
        return False

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
    konu = konu_bankasi.sonraki_konu(gun=gun)
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
        konu_bankasi.kullanildi_isaretle(konu["kod"], sonuc="hata")
        mesaj_gonder("❌ İçerik üretilemedi. Gemini API yanıt vermedi.")
        return False

    orijinal_url = f"edm://konu/{konu['kod']}/{int(time.time())}"
    with db._baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet,
                                     eklenme_tarihi, onem_puani, kategori, manset, detay_metni,
                                     ig_caption, threads_metin, durum)
               VALUES (?, ?, ?, ?, datetime('now'), ?, ?, ?, ?, ?, ?, 'yeni')""",
            (
                f"EDM Konu Bankası // {konu['kod']}",
                konu["baslik"],
                orijinal_url,
                veri.get("spot", ""),
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

    konu_bankasi.kullanildi_isaretle(konu["kod"], haber_id=haber_id)
    return haber_onayina_sun(haber_id)


def hizli_icerik_uret(format_turu: Optional[str] = None) -> bool:
    """Belirtilen formata (sozluk, nedir_dogrusu, vaka, net_cevap, reels) göre sıradaki konuyu üretir ve onaya sunar."""
    if format_turu == "reels":
        return reels_hazirla_ve_sun()

    etiketler = {
        "sozluk": "📖 EDM Gayrimenkul Sözlüğü",
        "nedir_dogrusu": "⚖️ Nedir Doğrusu?",
        "vaka": "📂 Hukuki Vaka Analizi",
        "net_cevap": "❓ Net Cevap Rehberi",
    }
    format_etiketi = etiketler.get(format_turu or "", "Otorite İçeriği")
    mesaj_gonder(f"⏳ <b>{format_etiketi}</b> için sıradaki konu hazırlanıyor...")

    konu = konu_bankasi.sonraki_konu()
    if not konu:
        mesaj_gonder("⚠️ Konu bankasında bakir konu kalmadı.")
        return False

    veri = generate_text.konudan_uret(konu)
    if not veri:
        mesaj_gonder("❌ İçerik üretilemedi. Gemini API yanıt vermedi.")
        return False

    if format_turu:
        veri["format_turu"] = format_turu

    orijinal_url = f"edm://konu/{konu['kod']}/{int(time.time())}"
    with db._baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet,
                                     eklenme_tarihi, onem_puani, kategori, manset, detay_metni,
                                     ig_caption, threads_metin, durum)
               VALUES (?, ?, ?, ?, datetime('now'), ?, ?, ?, ?, ?, ?, 'yeni')""",
            (
                f"EDM Konu Bankası // {konu['kod']}",
                konu["baslik"],
                orijinal_url,
                konu.get("aci", ""),
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

    konu_bankasi.kullanildi_isaretle(konu["kod"], haber_id=haber_id)
    return haber_onayina_sun(haber_id)


def reels_hazirla_ve_sun(konu_kodu: Optional[str] = None) -> bool:
    """
    Konu bankasından sıradaki konudan 9:16 dikey MP4 Reels videosu üretir,
    videoyu Telegram grubuna gönderir, kopyalanabilir açıklama metnini iletir
    ve YouTube Shorts / TikTok otomatik yayın butonlarını sunar.
    Instabot mimarisinden uyarlanmıştır.
    """
    mesaj_gonder("⏳ <b>EDM Reels Videosu (9:16 Dikey)</b> hazırlanıyor, lütfen bekleyin...")

    konu = konu_bankasi.sonraki_konu() if not konu_kodu else next((k for k in konu_bankasi.havuzu_yukle() if k["kod"] == konu_kodu), None)
    if not konu:
        mesaj_gonder("⚠️ Konu bankasında uygun konu bulunamadı.")
        return False

    veri = generate_text.konudan_uret(konu)
    if not veri:
        mesaj_gonder("❌ Gemini metin üretemedi.")
        return False

    from . import yeni_formatlar, video
    format_turu = konu_bankasi.gun_icin_format()
    veri["format_turu"] = format_turu

    slayt_yollari = yeni_formatlar.slaytlari_uret(veri, format_turu=format_turu, cikti_onek=f"reels_{konu['kod']}")
    if not slayt_yollari:
        mesaj_gonder("❌ Reels için slayt görselleri üretilemedi.")
        return False

    # Eğer tek slayt üretildiyse, arkasına şık bir EDM Kapanış Slaytı ekle (Akıcı 2 slaytlı sinematik Reels)
    if len(slayt_yollari) == 1:
        from . import kapanis_stilleri
        kapanis_yolu = Path(slayt_yollari[0]).parent / f"reels_{konu['kod']}_kapanis.jpg"
        try:
            kapanis_slayti = kapanis_stilleri.kapanis_ciz(
                stil="editoryal",
                veri=veri,
                sayfa="02 / 02",
                cikti_yolu=kapanis_yolu,
            )
            if kapanis_slayti and Path(kapanis_slayti).exists():
                slayt_yollari.append(kapanis_slayti)
        except Exception as e:
            log.warning("Reels kapanış slaytı eklenemedi: %s", e)

    # 1080x1920 MP4 Dikey Video Üret
    video_yolu = video.slaytlardan_reels_uret(slayt_yollari, fps=30, slayt_suresi=3.5, gecis_suresi=0.5)
    if not video_yolu or not Path(video_yolu).exists():
        mesaj_gonder("❌ 1080x1920 MP4 Reels videosu üretilemedi.")
        return False

    # Veritabanına kaydet
    orijinal_url = f"edm://reels/{konu['kod']}/{int(time.time())}"
    with db._baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet,
                                     eklenme_tarihi, onem_puani, kategori, manset, detay_metni,
                                     ig_caption, threads_metin, durum, slayt_yollari)
               VALUES (?, ?, ?, ?, datetime('now'), ?, ?, ?, ?, ?, ?, 'onay_bekliyor', ?)""",
            (
                f"EDM Reels // {konu['kod']}",
                konu["baslik"],
                orijinal_url,
                konu.get("aci", ""),
                konu.get("onem_puani", 8),
                "REELS",
                generate_text.manset_birlestir(veri) or konu["baslik"],
                json.dumps(veri, ensure_ascii=False),
                veri.get("caption_instagram", ""),
                veri.get("caption_threads", ""),
                json.dumps([str(p) for p in slayt_yollari], ensure_ascii=False),
            ),
        )
        haber_id = cur.lastrowid
        conn.commit()

    konu_bankasi.kullanildi_isaretle(konu["kod"], haber_id=haber_id)

    # 1. MP4 Videosunu Gönder
    video_gonder(
        video_yolu,
        aciklama=f"🎬 <b>EDM Reels Videosu (1080x1920 MP4)</b>\n\n"
                 f"📌 <b>Konu:</b> {konu['baslik']}\n\n"
                 f"💡 <i>Videoyu cihazınıza kaydedip Instagram uygulamasından trend müzikle kolayca paylaşabilirsiniz.</i>",
    )

    # 2. Kopyalanabilir Caption'ı Gönder
    import html as html_lib
    caption_metin = veri.get("caption_instagram") or konu["baslik"]
    temiz_caption = html_lib.escape(caption_metin.strip())
    res = mesaj_gonder(
        "📝 <b>Reels Açıklama Metni (Kopyalamak için dokunun):</b>\n"
        f"<pre>{temiz_caption}</pre>",
        reply_markup={
            "inline_keyboard": [
                [
                    {"text": "🚀 YouTube & TikTok'ta Otomatik Yayınla", "callback_data": f"onayla:reels:video:{haber_id}"},
                ],
                [
                    {"text": "🔄 Yeniden Üret", "callback_data": f"yenile:reels:{haber_id}"},
                    {"text": "❌ İptal Et", "callback_data": f"reddet:reels:{haber_id}"},
                ],
            ]
        }
    )
    if res and isinstance(res, dict) and "message_id" in res:
        _, chat_id = _bot_bilgileri()
        try:
            cid = int(str(chat_id).strip()) if str(chat_id).lstrip("-").isdigit() else None
            db.onay_istegi_kaydet("reels", str(haber_id), res["message_id"], cid)
        except Exception as e:
            log.warning("Reels onay isteği kaydedilemedi: %s", e)
    return True


def format_degistir_ve_sun(haber_id: int, hedef_format: str) -> bool:
    """Onay bekleyen bir içeriğin görsel formatını anında değiştirip yeni önizlemeyi sunar."""
    haber = db.haber_getir(haber_id)
    if not haber:
        return False

    detay_metni = haber.get("detay_metni")
    veri = json.loads(detay_metni) if detay_metni else {}
    veri["format_turu"] = hedef_format
    db.haber_guncelle(haber_id, detay_metni=json.dumps(veri, ensure_ascii=False), slayt_yollari=None, slayt_urlleri=None)
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
    with db._baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet, eklenme_tarihi, onem_puani, kategori, manset, detay_metni, ig_caption, threads_metin, durum)
               VALUES (?, ?, ?, ?, datetime('now'), ?, ?, ?, ?, ?, ?, 'yeni')""",
            (
                "EDM Otorite Masası",
                konu,
                orijinal_url,
                veri.get("spot", ""),
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

    caption = (metinler.get("ig_caption") if metinler else "") or (
        f"{ilan.get('baslik')}\n\n"
        f"📍 Konum: {ilan.get('ilce')} / {ilan.get('mahalle')}\n"
        f"💰 Fiyat: {fetch_listings.ilan_fiyat_bicimlendir(float(ilan.get('fiyat', 0)))}\n\n"
        f"EDM Yapı & Gayrimenkul · 0536 343 41 97\nedmyapigayrimenkul.com"
    )

    onizleme_metni = (
        f"🏡 <b>İLAN PAYLAŞIM ÖNİZLEMESİ</b>\n\n"
        f"<b>Başlık:</b> {ilan.get('baslik')}\n"
        f"<b>Fiyat:</b> {fetch_listings.ilan_fiyat_bicimlendir(float(ilan.get('fiyat', 0)))}\n"
        f"<b>Lokasyon:</b> {ilan.get('ilce')} / {ilan.get('mahalle')}\n\n"
        f"<b>Açıklama:</b>\n{caption[:350]}..."
    )

    medya_grubu_gonder(slayt_yollari, caption=onizleme_metni)

    butonlar = {
        "inline_keyboard": [
            [
                {"text": "✅ İlanı Yayınla (Tüm Kanallar)", "callback_data": f"onayla:ilan:hepsi:{ilan_id}"},
            ],
            [
                {"text": "📸 Instagram", "callback_data": f"onayla:ilan:ig:{ilan_id}"},
                {"text": "📘 Facebook", "callback_data": f"onayla:ilan:fb:{ilan_id}"},
                {"text": "🧵 Threads", "callback_data": f"onayla:ilan:threads:{ilan_id}"},
            ],
            [
                {"text": "🎬 Sadece Video (Reels/Shorts/TikTok)", "callback_data": f"onayla:ilan:video:{ilan_id}"},
            ],
            [
                {"text": "🔄 Yeniden Hazırla", "callback_data": f"yenile:ilan:{ilan_id}"},
                {"text": "❌ İptal Et", "callback_data": f"reddet:ilan:{ilan_id}"},
            ],
        ]
    }
    mesaj_gonder("Bu portföy ilanını sosyal medyada yayınlayalım mı?", reply_markup=butonlar)
    return True
