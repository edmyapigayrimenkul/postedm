"""
src/telegram/menuler.py — Onay kartının inline düğme setleri (kanal seçimi, yayın zamanı, sesli yayın, fotoğraf, metin).

Katman 1 (kural): saf işlevler — yalnız sözlük/liste üretir, ağa ya da diske çıkmaz.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


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
                {"text": "📝 Metinleri Gör", "callback_data": f"metin_onizle:{adet}"},
                {"text": "📲 Manuel Paket", "callback_data": "manuel_paket"},
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
