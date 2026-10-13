"""
src/telegram/kartlar.py — İçerik inceleme kartı, havuz özeti ve son yayınlar raporu.

Katman 3-4: kart metinlerini DB'den kurar; `icerik_incele_gonder` Telegram'a fotoğraf/mesaj yollar.
"""

from __future__ import annotations

import html
import json
import logging
from typing import Any, Dict, Tuple

from .. import db, konu_bankasi
from ..sutun import SUTUN_ADLARI
from . import istemci, medya_istek

log = logging.getLogger(__name__)


def icerik_incele_karti(ref_id: int) -> Tuple[str, Dict[str, Any]]:
    """İçerik #ref_id için detaylı inceleme kartı ve yönetim butonları üretir."""
    haber = db.haber_getir(int(ref_id))
    if not haber:
        return f"⚠️ <b>#{ref_id} numaralı içerik veritabanında bulunamadı.</b>", {
            "inline_keyboard": [[{"text": "← Kontrol Paneli", "callback_data": "panel"}]]
        }
    from .. import haber_oneri
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
        return bool(istemci.mesaj_gonder(f"⚠️ <b>#{ref_id} numaralı içerik veritabanında bulunamadı.</b>"))

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
        res = medya_istek.fotograf_gonder(gorsel_adayi, caption=metin[:1024], reply_markup=butonlar)
        if res:
            return True

    # 3. Fotoğraf yoksa veya gönderilemediyse metinle gönder
    return bool(istemci.mesaj_gonder(metin, reply_markup=butonlar))


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
