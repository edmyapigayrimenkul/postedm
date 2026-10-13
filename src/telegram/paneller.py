"""
src/telegram/paneller.py — Kontrol paneli, durum raporu, kota raporu, yayın kontrol kartı ve komut menüsü kaydı.

Katman 3-4: panel kartlarını kurar ve gönderir; `komut_menusu_kaydet` Telegram'ın setMyCommands uç noktasını çağırır.
"""

from __future__ import annotations

import html
import logging
from typing import Any, Dict, Optional, Tuple

import requests

from .. import db, komutlar, konu_bankasi
from . import ayarlar, istemci, menuler_panel

log = logging.getLogger(__name__)


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
    duraklatildi, kalan = ayarlar.bot_duraklatildi_mi()
    durum_str = f"⏸️ <b>DURAKLATILDI</b> ({kalan})" if duraklatildi else "🟢 <b>OTOMATİK AKIŞ AKTİF</b>"

    metin = (
        "🏢 <b>EDM YAPI & GAYRİMENKUL // KONTROL MERKEZİ</b>\n\n"
        f"<b>Sistem Durumu:</b> {durum_str}\n"
        "Aşağıdaki butonları kullanarak tek tıkla yeni içerik üretebilir, "
        "yayın akışını yönetebilir veya sistem durumunu denetleyebilirsiniz."
    )
    menu = menuler_panel.kontrol_merkezi_menusu(duraklatildi=duraklatildi, kalan_sure=kalan)

    if mesaj_id:
        istemci.mesaji_guncelle(mesaj_id, metin, reply_markup=menu)
        return None
    return istemci.mesaj_gonder(metin, reply_markup=menu)


def durum_raporu_gonder(mesaj_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Detaylı sistem ve yayın durumu raporu gönderir."""
    duraklatildi, kalan = ayarlar.bot_duraklatildi_mi()
    durum_str = f"⏸️ Duraklatıldı ({kalan})" if duraklatildi else "🟢 Aktif (Zamanlanmış Akış)"

    ozet = konu_bankasi.durum_ozeti()
    kanallar = ayarlar.varsayilan_kanallar()
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
        istemci.mesaji_guncelle(mesaj_id, metin, reply_markup=geri_menu)
        return None
    return istemci.mesaj_gonder(metin, reply_markup=geri_menu)


def kota_gonder(mesaj_id: Optional[int] = None, kategori: int | str = "menu") -> Optional[Dict[str, Any]]:
    """Detaylı GitHub Actions, yapay zeka ve sistem kota tablosu gönderir."""
    from .. import rapor_uretici
    return rapor_uretici.kota_gonder(mesaj_id=mesaj_id, kategori=kategori)


kota = kota_gonder
detayli_rapor_gonder = kota_gonder


def komut_menusu_kaydet() -> bool:
    """Telegram komut açılır menüsünü (setMyCommands) tüm kapsamlara ve gruba kaydeder."""
    token, chat_id = istemci._bot_bilgileri()
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
    url = istemci.TELEGRAM_API_URL.format(token=token, method="setMyCommands")
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
