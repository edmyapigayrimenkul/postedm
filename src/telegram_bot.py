"""
telegram_bot.py — EDM Telegram Onay ve Yönetim Botu
Haber ve İlan önizlemelerini Telegram grubuna iletir, inline butonlarla onay alır.
Tek tıkla portföyden ilan seçip post üretme özelliğini yönetir.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from . import config, db, fetch_listings, generate_text, make_image, upload_image

log = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"


def _bot_bilgileri() -> tuple[str, str]:
    token = config.env_al("TELEGRAM_BOT_TOKEN")
    chat_id = config.env_al("TELEGRAM_CHAT_ID")
    return token, chat_id


def mesaj_gonder(metin: str, reply_markup: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    token, chat_id = _bot_bilgileri()
    if not token or not chat_id:
        log.warning("Telegram token veya chat_id eksik.")
        return None

    url = TELEGRAM_API_URL.format(token=token, method="sendMessage")
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": metin,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            return r.json().get("result")
        log.error("Telegram mesaj hatası [%d]: %s", r.status_code, r.text)
    except Exception as e:
        log.error("Telegram istek hatası: %s", e)
    return None


def fotograf_gonder(
    foto_yolu_veya_url: Path | str,
    caption: str = "",
    reply_markup: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
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
                r = requests.post(url, data=data, files={"photo": f}, timeout=30)
        else:
            data["photo"] = str(foto_yolu_veya_url)
            r = requests.post(url, data=data, timeout=30)

        if r.status_code == 200:
            return r.json().get("result")
        log.error("Telegram fotoğraf hatası [%d]: %s", r.status_code, r.text)
    except Exception as e:
        log.error("Telegram fotoğraf gönderme hatası: %s", e)
    return None


def medya_grubu_gonder(foto_yollari: List[Path | str], caption: str = "") -> bool:
    """Carousel önizlemesi için albüm (medya grubu) gönderir."""
    token, chat_id = _bot_bilgileri()
    if not token or not chat_id or not foto_yollari:
        return False

    url = TELEGRAM_API_URL.format(token=token, method="sendMediaGroup")
    media = []
    files = {}

    for idx, f_yol in enumerate(foto_yollari[:10]):
        attach_name = f"photo_{idx}"
        m_item: Dict[str, Any] = {"type": "photo", "media": f"attach://{attach_name}"}
        if idx == 0 and caption:
            m_item["caption"] = caption[:1024]
            m_item["parse_mode"] = "HTML"
        media.append(m_item)

        p = Path(str(f_yol))
        if p.exists():
            files[attach_name] = open(p, "rb")

    try:
        r = requests.post(url, data={"chat_id": chat_id, "media": json.dumps(media)}, files=files, timeout=45)
        for fp in files.values():
            fp.close()
        return r.status_code == 200
    except Exception as e:
        log.error("Telegram medya grubu hatası: %s", e)
        for fp in files.values():
            fp.close()
    return False


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

    # 2. Slayt görsellerini üret
    k1 = make_image.haber_slayti_1_ciz(
        manset=haber["manset"],
        spot=haber.get("detay_metni", "")[:120],
        kaynak=haber.get("kaynak", "EDM"),
        tarih=haber.get("yayin_tarihi", ""),
        foto_url=haber.get("gorsel_url"),
    )
    k2 = make_image.haber_slayti_2_ciz(
        manset=haber["manset"],
        detay_metni=haber.get("detay_metni", ""),
    )

    slayt_yollari = [str(k1), str(k2)]
    db.haber_guncelle(haber_id, slayt_yollari=json.dumps(slayt_yollari), durum="onay_bekliyor")

    # 3. Medya albümü gönder
    onizleme_metni = (
        f"🗞 <b>YENİ SEKTÖR HABERİ ONAY BEKLİYOR</b>\n\n"
        f"<b>Manşet:</b> {haber['manset']}\n"
        f"<b>Kaynak:</b> {haber['kaynak']}\n"
        f"<b>Önem Puanı:</b> {haber['onem_puani']}/10\n\n"
        f"<b>Instagram Caption:</b>\n{haber['ig_caption'][:300]}..."
    )
    medya_grubu_gonder(slayt_yollari, caption=onizleme_metni)

    # 4. Onay butonlarını gönder
    butonlar = {
        "inline_keyboard": [
            [
                {"text": "✅ Tümüne Yayınla (IG + Threads)", "callback_data": f"onayla:haber:hepsi:{haber_id}"},
            ],
            [
                {"text": "📸 Sadece Instagram", "callback_data": f"onayla:haber:ig:{haber_id}"},
                {"text": "🧵 Sadece Threads", "callback_data": f"onayla:haber:threads:{haber_id}"},
            ],
            [
                {"text": "❌ Pas Geç / Reddet", "callback_data": f"reddet:haber:{haber_id}"},
            ],
        ]
    }
    mesaj_gonder("Bu haberi sosyal medya hesaplarımızda paylaşalım mı?", reply_markup=butonlar)
    return True


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
                {"text": "✅ İlanı Yayınla (IG + Threads)", "callback_data": f"onayla:ilan:hepsi:{ilan_id}"},
            ],
            [
                {"text": "📸 Sadece Instagram", "callback_data": f"onayla:ilan:ig:{ilan_id}"},
                {"text": "🧵 Sadece Threads", "callback_data": f"onayla:ilan:threads:{ilan_id}"},
            ],
            [
                {"text": "❌ İptal Et", "callback_data": f"reddet:ilan:{ilan_id}"},
            ],
        ]
    }
    mesaj_gonder("Bu portföy ilanını sosyal medyada yayınlayalım mı?", reply_markup=butonlar)
    return True
