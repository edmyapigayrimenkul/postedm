"""
src/telegram/akislar/ilan.py — Portföy ilanından post üretme: tek tıkla ilan menüsü ve ilan onay akışı.

Katman 4 (akış). İlan slaytlarını çizer, CDN'e yükler, albüm + onay kartını gönderir.
"""

from __future__ import annotations

import html
import logging

from ... import db, fetch_listings, generate_text, make_image, upload_image
from .. import album, istemci, menuler, temizlik
from . import onay_karti

log = logging.getLogger(__name__)


def tek_tikla_ilan_menusu_gonder() -> bool:
    """Portföydeki aktif ilanları buton listesi olarak Telegram'a gönderir."""
    ilanlar = fetch_listings.aktif_ilanlar(limit=6)
    if not ilanlar:
        istemci.mesaj_gonder("Portföyde paylaşılacak aktif ilan bulunamadı.")
        return False

    satirlar = []
    for i in ilanlar:
        fiyat_str = fetch_listings.ilan_fiyat_bicimlendir(float(i.get("fiyat", 0)), i.get("paraBirimi", "TRY"))
        kisa_baslik = i.get("baslik", "")[:35]
        buton_metni = f"🏡 {i.get('ilce')} {i.get('tip')} ({fiyat_str}) — {kisa_baslik}"
        satirlar.append([{"text": buton_metni, "callback_data": f"ilan_sec:{i.get('id')}"}])

    satirlar.append([{"text": "🔄 İlan Listesini Yenile", "callback_data": "ilan_menu_yenile"}])

    reply_markup = {"inline_keyboard": satirlar}
    istemci.mesaj_gonder(
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

    istemci.mesaj_gonder(f"⏳ <b>#{ilan_id}</b> nolu ilan için görseller ve açıklama hazırlanıyor...")

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
    temizlik.icerik_onceki_mesajlarini_temizle("ilan_album", ilan_id)
    temizlik.icerik_onceki_mesajlarini_temizle("ilan", ilan_id)

    # 3. Slayt görsellerini albüm olarak gönder
    album_caption = f"🏡 <b>EDM PORTFÖY // İLAN CAROUSEL (4:5)</b>\n📌 {html.escape(str(ilan.get('baslik') or ''), quote=False)}"
    album_res = album.medya_grubu_gonder(slayt_yollari, caption=album_caption, yedek_urller=slayt_urlleri)
    _, chat_id = istemci._bot_bilgileri()
    cid = int(str(chat_id).strip()) if str(chat_id).lstrip("-").isdigit() else None
    album_mids = album_res if isinstance(album_res, list) else []
    gorsel_notu = onay_karti._album_teslim_notu(album_res, min(len(slayt_yollari), 10), slayt_urlleri)
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
    butonlar = menuler.ana_menu(adet=len(slayt_yollari), kanallar=ilan_kanallari)
    res = onay_karti._onay_kartini_gonder(ilan_id, mesaj_metni, butonlar, html_lib.escape(str(ilan.get("baslik") or ""), quote=False), "ilan")
    if res and isinstance(res, dict) and "message_id" in res:
        try:
            db.onay_istegi_kaydet("ilan", str(ilan_id), res["message_id"], cid)
        except Exception as e:
            log.warning("İlan onay isteği kaydedilemedi: %s", e)

    try:
        from ... import db_senkron
        db_senkron.hemen_kaydet(f"db: ilan #{ilan_id} onaya sunuldu")
    except Exception as e:
        log.warning("Hemen kaydetme adımı atlandı: %s", e)

    return True
