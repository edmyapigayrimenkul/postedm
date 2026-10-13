"""
telegram_bot.py — `src/telegram/` paketinin geriye uyumlu CEPHESİ (facade).

Gerçek kod 2026-10-13'te `src/telegram/` paketine bölündü (bkz. ARCHITECTURE.md §4 Faz 2). Bu dosya 22 kaynak dosyasının,
workflow'lardaki `python -c "from src import telegram_bot; ..."` satırlarının ve testlerin kullandığı `telegram_bot.mesaj_gonder`
gibi adları korur; HİÇBİR kod barındırmaz.

CANLI TAKMA AD: bir ad istendiğinde (PEP 562 `__getattr__`) gerçek evinden O AN okunur. Sonuçları:
  * Gerçek evdeki bir yama (`patch("src.telegram.istemci.mesaj_gonder")`) cepheden çağıranları da kapsar — testler HER ZAMAN gerçek evi yamalar.
  * Cephede yapılan yama (`patch("src.telegram_bot.mesaj_gonder")`) yalnızca cepheden çağıranları (scripts/, src/yayin/ ...) etkiler;
    paket içindeki akışlar kardeşlerini doğrudan çağırdığı için etkilenmez.
  * Taşınan durum (ör. son albüm kimlikleri) kopyalanmaz, bayatlamaz.

Yeni bir işlev eklediğinde `tests/test_telegram_paketi.py` bu tabloyu paketle karşılaştırır; eksik adı ve çift tanımı yakalar.
"""

from __future__ import annotations

import importlib
from typing import Any

# ad -> src/telegram/ altındaki modül (noktalı yol). Elle düzenlenmez: tests/test_telegram_paketi.py paketle karşılaştırır.
_EV = {
    # akislar.finans
    "finans_icerigi_hazirla_ve_yayinla": "akislar.finans",
    # akislar.ilan
    "ilan_postunu_hazirla_ve_sor": "akislar.ilan",
    "tek_tikla_ilan_menusu_gonder": "akislar.ilan",
    # akislar.kapi
    "_denetim_verisi": "akislar.kapi",
    "_eksik_icerik_bildir": "akislar.kapi",
    "yayin_kapisi": "akislar.kapi",
    # akislar.onay
    "_haber_onayina_sun": "akislar.onay",
    "haber_onayina_sun": "akislar.onay",
    # akislar.onay_karti
    "_album_teslim_notu": "akislar.onay_karti",
    "_onay_kartini_gonder": "akislar.onay_karti",
    "kart_basliklari": "akislar.onay_karti",
    "kart_metni": "akislar.onay_karti",
    "onay_butonlari": "akislar.onay_karti",
    # akislar.onay_slayt
    "cdn_yukle": "akislar.onay_slayt",
    "mevcut_slaytlar": "akislar.onay_slayt",
    "otorite_verisini_oku": "akislar.onay_slayt",
    "slaytlari_ciz": "akislar.onay_slayt",
    # akislar.otomatik
    "OTO_YAYIN_HEDEFLERI": "akislar.otomatik",
    "_oto_yayinla": "akislar.otomatik",
    # akislar.otorite
    "format_degistir_ve_sun": "akislar.otorite",
    "otorite_postu_hazirla_ve_sor": "akislar.otorite",
    # akislar.reels
    "_reels_hazirla_ve_sun": "akislar.reels",
    "reels_hazirla_ve_sun": "akislar.reels",
    # akislar.sozluk
    "_OTO_YAYIN_KAPALI_DEGERLER": "akislar.sozluk",
    "_sozluk_karti_sec": "akislar.sozluk",
    "sozluk_karti_hazirla_ve_sun": "akislar.sozluk",
    "sozluk_oto_yayin_acik_mi": "akislar.sozluk",
    "sozluk_oto_yayin_kapatildi_mi": "akislar.sozluk",
    "sozluk_zamanli_gunu_mu": "akislar.sozluk",
    "sozluk_zamanli_isaretle": "akislar.sozluk",
    # akislar.uretim
    "_sozluk_slotu": "akislar.uretim",
    "haberden_icerik_hazirla": "akislar.uretim",
    "hizli_icerik_uret": "akislar.uretim",
    "konu_bankasindan_hazirla": "akislar.uretim",
    "slot_icerigi_hazirla_ve_sun": "akislar.uretim",
    # akislar.zamanli
    "ZAMANLI_GUNLUK_SLOTLAR": "akislar.zamanli",
    "_tr_bugun": "akislar.zamanli",
    "_zamanli_slot_anahtari": "akislar.zamanli",
    "zamanli_slot_bugun_yapildi": "akislar.zamanli",
    "zamanli_slot_isaretle": "akislar.zamanli",
    # album
    "_album_istegi": "album",
    "_ayikla_medya_mesaj_idleri": "album",
    "_indir": "album",
    "_medya_hatasi_kaydet": "album",
    "_yerel_dosya_bul": "album",
    "medya_grubu_gonder": "album",
    "slaytlari_gonder": "album",
    "son_medya_grubu_mesaj_idleri": "album",
    # ayarlar
    "bot_devam_et": "ayarlar",
    "bot_duraklat": "ayarlar",
    "bot_duraklatildi_mi": "ayarlar",
    "kanal_ayarla": "ayarlar",
    "kanal_toggle": "ayarlar",
    "secili_kanallari_cikar": "ayarlar",
    "varsayilan_kanallar": "ayarlar",
    # durum_metni
    "KANAL_ETIKETLERI": "durum_metni",
    "canli_yayin_durumu_guncelle": "durum_metni",
    "yayin_durum_metni_olustur": "durum_metni",
    # istemci
    "TELEGRAM_API_URL": "istemci",
    "_bot_bilgileri": "istemci",
    "_istek": "istemci",
    "aciklama_metni_kutusu": "istemci",
    "menuyu_degistir": "istemci",
    "mesaj_gonder": "istemci",
    "mesaji_guncelle": "istemci",
    "mesaji_sil": "istemci",
    # kaldir
    "yayindan_kaldir": "kaldir",
    # kartlar
    "havuz_mesaji": "kartlar",
    "icerik_incele_gonder": "kartlar",
    "icerik_incele_karti": "kartlar",
    "son_postlar_raporu": "kartlar",
    # medya_istek
    "MEDYA_DENEME": "medya_istek",
    "MEDYA_TOPLAM_SURE": "medya_istek",
    "MEDYA_ZAMAN_ASIMI": "medya_istek",
    "_MEDYA_UA": "medya_istek",
    "_bos": "medya_istek",
    "_cevap_ayrintisi": "medya_istek",
    "_cevap_json": "medya_istek",
    "_duz_metin": "medya_istek",
    "_foto_baytlari": "medya_istek",
    "_medya_post": "medya_istek",
    "fotograf_gonder": "medya_istek",
    "video_gonder": "medya_istek",
    # menuler
    "ana_menu": "menuler",
    "foto_menusu": "menuler",
    "foto_secim_menusu": "menuler",
    "kanal_butonlari": "menuler",
    "metin_menusu": "menuler",
    "metin_secim_menusu": "menuler",
    "onay_menusu": "menuler",
    "reels_onay_menusu": "menuler",
    "ses_menusu": "menuler",
    "sesli_yayin_zamani_menusu": "menuler",
    "yayin_zamani_menusu": "menuler",
    # menuler_panel
    "ayar_menusu": "menuler_panel",
    "duraklatma_secenekleri_menusu": "menuler_panel",
    "format_secim_menusu": "menuler_panel",
    "kontrol_merkezi_menusu": "menuler_panel",
    "slayt_islem_menusu": "menuler_panel",
    "slayt_secim_menusu": "menuler_panel",
    # paneller
    "detayli_rapor_gonder": "paneller",
    "durum_raporu_gonder": "paneller",
    "komut_menusu_kaydet": "paneller",
    "kota": "paneller",
    "kota_gonder": "paneller",
    "panel_gonder": "paneller",
    "yayin_kontrol_karti": "paneller",
    # sonuc_mesaji
    "durum_guncelle": "sonuc_mesaji",
    "sonucu_yaz": "sonuc_mesaji",
    # temizlik
    "icerik_onceki_mesajlarini_temizle": "temizlik",
    "son_mesajlari_sil": "temizlik",
}


def __getattr__(ad: str) -> Any:
    modul = _EV.get(ad)
    if modul is None:
        raise AttributeError(f"module {__name__!r} has no attribute {ad!r}")
    return getattr(importlib.import_module(f"{__package__}.telegram.{modul}"), ad)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EV))
