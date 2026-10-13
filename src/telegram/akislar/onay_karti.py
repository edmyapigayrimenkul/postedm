"""
src/telegram/akislar/onay_karti.py — Haber onay kartının parçaları: başlık/rozet, gövde metni, düğmeler, albüm teslim notu, kart gönderimi.

Katman 1-3: ilk dört işlev saf metin/düğme üreticisidir; `_onay_kartini_gonder` kartı Telegram'a yollar (gitmezse kısa karta düşer).
"""

from __future__ import annotations

import html
import logging
from typing import Any, Dict, List, Optional, Tuple

from ... import db, generate_text
from .. import istemci, menuler

log = logging.getLogger(__name__)


def kart_basliklari(haber_id: int, haber: Dict[str, Any], otorite_verisi: Optional[Dict[str, Any]], format_turu: Optional[str],
                    is_reels: bool, is_haber: bool, manset_h: str) -> Tuple[str, str, str, str]:
    """Formata göre (rozet, dayanak, albüm_başlığı, kart_başlığı)."""
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
    return rozet, dayanak, album_caption, kart_baslik


def kart_metni(haber_id: int, haber: Dict[str, Any], uyarilar: List[str], gorsel_notu: str, kart_baslik: str,
               rozet: str, dayanak: str, manset_h: str) -> str:
    """Onay kartının gövdesi: görsel notu + denetim başlığı + künye + kopyalanabilir caption."""
    # 4. İnteraktif Onay Menüsü + Kopyalanabilir Caption (Görüntülerin hemen altına düşer)
    from ... import dogrula
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
    return mesaj_metni


def onay_butonlari(slayt_yollari: List[str], is_reels: bool, is_haber: bool) -> Dict[str, Any]:
    """Format türüne göre varsayılan kanal seçimli ana menü."""
    if is_reels or is_haber:
        # Haber ve Reels içeriklerinde varsayılan: Reels AÇIK, IG Besleme KAPALI
        reels_kanallari = {"ig": False, "reels": True, "story": True, "threads": True, "facebook": True, "youtube": True, "tiktok": True, "linkedin": True}
        butonlar = menuler.ana_menu(adet=len(slayt_yollari) if slayt_yollari else 3, kanallar=reels_kanallari)
    else:
        # Otorite, sözlük, rehber carousel içeriklerinde varsayılan: IG Besleme AÇIK, Reels KAPALI
        ig_kanallari = {"ig": True, "reels": False, "story": True, "threads": True, "facebook": True, "youtube": True, "tiktok": True, "linkedin": True}
        butonlar = menuler.ana_menu(adet=len(slayt_yollari) if slayt_yollari else 2, kanallar=ig_kanallari)
    return butonlar


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
    res = istemci.mesaj_gonder(metin, reply_markup=butonlar)
    if res:
        return res
    log.warning("Onay kartı gönderilemedi (%s #%s); kısa kart deneniyor", tur, kimlik)
    kisa = (f"📝 <b>İçerik #{kimlik} onay bekliyor</b>\n<b>Manşet:</b> {manset_h}\n\n"
            "<i>Ayrıntılı kart gönderilemedi; düğmeler aşağıda.</i>")
    res = istemci.mesaj_gonder(kisa, reply_markup=butonlar)
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
