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
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple


from . import db, fetch_listings, generate_text, konu_bankasi, make_image, upload_image
# Eski adlar (testler ve diğer modüller `telegram_bot.mesaj_gonder` gibi kullanıyor; yamalar bu modülün adı üzerinden yapılıyor)
from .telegram.album import _album_istegi, _ayikla_medya_mesaj_idleri, _indir, _medya_hatasi_kaydet, _yerel_dosya_bul, medya_grubu_gonder, slaytlari_gonder, son_medya_grubu_mesaj_idleri  # noqa: F401,E501
from .telegram.ayarlar import bot_devam_et, bot_duraklat, bot_duraklatildi_mi, kanal_ayarla, kanal_toggle, secili_kanallari_cikar, varsayilan_kanallar  # noqa: F401,E501
from .telegram.durum_metni import canli_yayin_durumu_guncelle, yayin_durum_metni_olustur, KANAL_ETIKETLERI  # noqa: F401,E501
from .telegram.sonuc_mesaji import durum_guncelle, sonucu_yaz  # noqa: F401,E501
from .telegram.kaldir import yayindan_kaldir  # noqa: F401,E501
from .telegram.kartlar import havuz_mesaji, icerik_incele_gonder, icerik_incele_karti, son_postlar_raporu  # noqa: F401,E501
from .telegram.paneller import durum_raporu_gonder, komut_menusu_kaydet, kota_gonder, panel_gonder, yayin_kontrol_karti, detayli_rapor_gonder, kota  # noqa: F401,E501
from .telegram.istemci import TELEGRAM_API_URL, _bot_bilgileri, _istek, aciklama_metni_kutusu, menuyu_degistir, mesaj_gonder, mesaji_guncelle, mesaji_sil  # noqa: F401,E501
from .telegram.menuler import ana_menu, foto_menusu, foto_secim_menusu, kanal_butonlari, metin_menusu, metin_secim_menusu, onay_menusu, reels_onay_menusu, ses_menusu, sesli_yayin_zamani_menusu, yayin_zamani_menusu  # noqa: F401,E501
from .telegram.menuler_panel import ayar_menusu, duraklatma_secenekleri_menusu, format_secim_menusu, kontrol_merkezi_menusu, slayt_islem_menusu, slayt_secim_menusu  # noqa: F401,E501
from .telegram.medya_istek import MEDYA_DENEME, MEDYA_TOPLAM_SURE, MEDYA_ZAMAN_ASIMI, _MEDYA_UA, _bos, _cevap_ayrintisi, _cevap_json, _duz_metin, _foto_baytlari, _medya_post, fotograf_gonder, video_gonder  # noqa: F401,E501
from .telegram.temizlik import icerik_onceki_mesajlarini_temizle, son_mesajlari_sil  # noqa: F401

log = logging.getLogger(__name__)

KOK = Path(__file__).resolve().parent.parent





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

