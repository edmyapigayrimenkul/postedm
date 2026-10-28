"""
src/make_image.py — EDM Marka Paftası Görsel Motoru (Facade Cephesi)

Bu modül, görsel üretim motorunun ortak giriş noktasıdır (Facade Pattern).
Tüm temel çizim fonksiyonları, tipografi motoru, sabitler ve format üreticileri
`src/cizim/` paketi altında modülerleştirilmiştir.

Dış modüller ve geriye dönük test uyumluluğu için tüm semboller bu modülden
şeffaf olarak dışa aktarılır.
"""

from __future__ import annotations

import logging
from typing import Any

from .cizim import (
    # Sabitler
    AZAMI_SARILACAK,
    BUYUKLUK_KELIMELERI,
    GENISLIK,
    YUKSEKLIK,
    TUVAL_OLCULERI,
    OPTIK_KALDIRMA,
    ZEMINLER,
    RENK_BEYAZ,
    RENK_CIZGI,
    RENK_CIZGI_ACIK,
    RENK_CIZGI_KOYU,
    RENK_KAGIT,
    RENK_KAGIT_KUTU,
    RENK_KIREC,
    RENK_KIRMIZI,
    RENK_KIRMIZI_CANLI,
    RENK_KIRMIZI_DERIN,
    RENK_KIRMIZI_VURGU,
    RENK_KURSUN,
    RENK_KURSUN_ACIK,
    RENK_METIN_GOVDE,
    RENK_MUREKKEP,
    RENK_MUREKKEP_2,
    RENK_MUREKKEP_3,
    RENK_UZMAN_CUBUK,
    RENK_UZMAN_ETIKET,
    RENK_YESIL,
    FONT_FRAUNCES,
    FONT_INTER_BOLD,
    FONT_INTER_MEDIUM,
    FONT_MONO,
    FONT_MONO_BOLD,
    FONT_SANS,
    FONT_SANS_BOLD,
    FONT_SANS_MEDIUM,
    FONT_SANS_REGULAR,
    FONT_SANS_SEMIBOLD,
    LOGO_AMBLEM,
    LOGO_PIN,
    LOGO_SLOGAN,
    LOGO_YATAY,
    LOGO_YATAY_ACIK,
    LOGO_YATAY_BEYAZ,
    # Hatalar
    EksikIcerik,
    TasmaHatasi,
    # Tipografi
    _difuzyon_golgeli_metin,
    _etiketi_sigdir,
    _gorsel_girdisi,
    _is_para_birimi,
    _is_sayi,
    _is_unvan_veya_on_ek,
    _kaynak_etiketi,
    _kelimeyi_bol,
    _metin_sar,
    _ortak_glifler,
    _temizle_tipografi,
    gorsel_metni,
    gorsel_verisi_temizle,
    tr_buyuk,
    tr_ilk_buyuk,
    # Fontlar
    _dikey_dagit,
    _ek_dolgu_hesapla,
    _font,
    _font_yukle,
    _govde_sigdir,
    _sigdir_font,
    # Tuval & Düzen
    tuval,
    _yerlesim,
    _rozet_kirp,
    _sayfa_etiketi,
    _zemin_uret,
    # İkonlar & Bileşenler
    _edm_pin_al,
    _vektor_ikon_uret,
    _arti_isareti_ciz,
    _filigran_uygula,
    _logo_yerlestir,
    _rozet_ciz,
    _slayt_cercevesi,
    kanal_ikonlari_bas,
    # Stok & Kardeş Haber
    ARKA_PLAN_HAVUZU,
    KONU_HAVUZLARI,
    PEXELS_SORGULARI,
    _foto_indir_veya_ac,
    _konu_havuzu,
    _konu_stok_fotografi,
    _perde_maskesi_smoothstep,
    _temiz_arkaplan_al,
    _haber_gorseli_alternatifi,
    kardes_linkler,
    konu_imzasi,
    # İlan
    ilan_kapak_slayti_ciz,
    ilan_detay_slayti_ciz,
    ilan_kapanis_slayti_ciz,
    # Fikir & Adım
    _fikir_blogu_olc,
    _blogu_sigdir,
    _fikir_blogu_ciz,
    _adim_numarasi,
    slayt_tek_fikir,
    slayt_ikili_fikir,
    ADIM_IRI_BASLIK,
    ADIM_IRI_GOVDE,
    _adim_olcusu,
    adim_blok_yuksekligi,
    adim_iri_mi,
    slayt_adim,
    slayt_adimlar_toplu,
    # Otorite
    otorite_slayt_1_kapak,
    otorite_slayt_2_detay,
    _finansal_tablo_ciz,
    otorite_slayt_3_cozum,
    slayt_kapanis,
    otorite_slayt_4_kapanis,
    # Normalizasyon & Akış
    _metin,
    _sozluk,
    _kart_normalize,
    veriyi_normalize_et,
    ESIK_IKILI_FIKIR,
    ESIK_ADIM_TOPLU,
    _slayt_plani,
    otorite_gonderi_slaytlari_uret,
    _gonderi_slaytlarini_ciz,
    # Haber
    haber_slayti_1_ciz,
    haber_slayti_2_ciz,
    haber_kapanis_slayti_ciz,
    haber_dailybrief_slayti_ciz,
    haber_dailybrief_detay_slayti_ciz,
    haber_detay_maddelerini_ayikla,
    dailybrief_slayt_sayisi_belirle,
    _sayfalari_dengeli_bol,
    haber_dailybrief_slaytlari_uret,
)
from .cizim.tuval import _tuval_lock

log = logging.getLogger(__name__)
