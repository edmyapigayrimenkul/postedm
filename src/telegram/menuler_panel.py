"""
src/telegram/menuler_panel.py — Slayt/format seçimi, kontrol merkezi, duraklatma ve ayar menüleri.

Katman 1 (kural): saf düğme üreticileri (`ayar_menusu` yalnız `src.ayar`dan okur).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


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
            [
                {"text": "⏰ Bekleyen Planlar", "callback_data": "planlar"},
                {"text": "📋 Komut Menüsü", "callback_data": "komut_guncelle"},
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
        from .. import ayar
        return ayar.ayar_menusu()
    except Exception as e:
        log.warning("Ayar menüsü üretilemedi: %s", e)
        return {"inline_keyboard": [[{"text": "← Kontrol Paneli", "callback_data": "panel"}]]}
