"""Taslak işlemleri: atla/reddet, çöpe at, yenile, metin özelleştirme. Yalnızca yayında OLMAYAN içeriğe uygulanır (bkz. koruma.TASLAK_ISLEMLERI)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ... import db, generate_text, konu_bankasi, telegram_bot
from ..baglam import Istek
from ..icerik import haber_taze

log = logging.getLogger(__name__)


def taslagi_at(tur: str, ref_id: str, mevcut: Optional[Dict[str, Any]], fiil: str, simge: str) -> None:
    """Atla / çöpe at: taslağı kapatır, konuyu havuza geri verir, gerekirse yerine yenisini üretir.

    Önceki sürüm iki şeyi yanlış yapıyordu: (1) "konu havuza iade edildi" diyordu ama konu üretim anında
    tüketilmişti ve geri verilmiyordu; (2) içeriğin ne olduğuna bakmadan HER durumda yeni bir B1 üretiyordu
    (reddedilen sözlük kartı ya da haber öneri taslağı da karusel doğuruyordu).

    Yenisi yalnız `EDM Konu Bankası` içeriklerinde (ve Reels'te) üretilir: sözlük 12:30'da, haber önerisi
    09:17/18:17'de kendi saatinde gelir."""
    db.haber_guncelle(int(ref_id), durum="iptal")
    db.onay_istegi_sonuclandir(tur, str(ref_id), "iptal")
    iade = konu_bankasi.konuyu_havuza_iade_et(int(ref_id))
    kaynak = str((mevcut or {}).get("kaynak") or "")
    yenisi_uretilsin = tur == "reels" or kaynak.startswith("EDM Konu Bankası")
    tur_adi = "Reels Videosu" if tur == "reels" else "İçerik"
    notlar = []
    if iade:
        notlar.append(f"Konu {konu_bankasi.HATA_BEKLEME_GUNU} gün sonra yeniden sıraya girer.")
    if yenisi_uretilsin:
        notlar.append("Sıradaki içerik hazırlanıyor...")
    log.info("%s #%s %s (konu iadesi: %d, yenisi üretilecek: %s).", tur_adi, ref_id, fiil, iade, yenisi_uretilsin)
    telegram_bot.mesaj_gonder(
        f"{simge} <b>{tur_adi} #{ref_id} {fiil}.</b>" + (f"\n<i>{' '.join(notlar)}</i>" if notlar else "")
    )
    if yenisi_uretilsin:
        if tur == "reels":
            telegram_bot.reels_hazirla_ve_sun()
        else:
            telegram_bot.konu_bankasindan_hazirla()


def reddet(istek: Istek, mevcut: Optional[Dict[str, Any]]) -> None:
    """Reddet / iptal (konu havuza döner, yerine yenisi yalnız konu bankası içeriğinde üretilir)."""
    tur, ref_id = istek.tur, istek.ref_id
    if tur in ("haber", "reels"):
        taslagi_at(tur, ref_id, mevcut, "atlandı", "❌")
    elif tur == "ilan":
        db.ilan_reddedildi_isaretle(ref_id)
        db.onay_istegi_sonuclandir(tur, str(ref_id), "reddedildi")
        log.info("İlan #%s reddedildi olarak işaretlendi.", ref_id)
        telegram_bot.mesaj_gonder(f"❌ <b>İlan #{ref_id} reddedildi ve arşive kaldırıldı.</b>")


def cope_at(istek: Istek, mevcut: Optional[Dict[str, Any]]) -> None:
    """Taslak atılır; kullanıcı isteğiyle KONU ASLA KİLİTLENMEZ, havuza iade edilir."""
    tur, ref_id = istek.tur, istek.ref_id
    if tur in ("haber", "reels"):
        taslagi_at(tur, ref_id, mevcut, "taslağı çöpe atıldı", "🗑️")
    elif tur == "ilan":
        db.ilan_reddedildi_isaretle(ref_id)
        db.onay_istegi_sonuclandir(tur, str(ref_id), "engellendi")
        log.info("İlan #%s çöpe atıldı ve arşivlendi.", ref_id)
        telegram_bot.mesaj_gonder(f"🗑️ <b>İlan #{ref_id} çöpe atıldı ve arşive kaldırıldı.</b>")


def yenile(istek: Istek) -> None:
    """Gemini metinlerini ve slaytları yeniden üretip onaya sunar."""
    tur, ref_id = istek.tur, istek.ref_id
    db.onay_istegi_sonuclandir(tur, str(ref_id), "yenilendi")
    telegram_bot.icerik_onceki_mesajlarini_temizle(tur, str(ref_id))
    if tur == "reels":
        log.info("Reels #%s için video ve metin yeniden üretiliyor...", ref_id)
        db.haber_guncelle(int(ref_id), durum="iptal")
        telegram_bot.reels_hazirla_ve_sun()
    elif tur == "haber":
        log.info("Haber #%s için metinler ve slaytlar yeniden hazırlanıyor...", ref_id)
        haber = haber_taze(ref_id)
        if not haber:
            log.error("Yenilenecek haber bulunamadı: #%s", ref_id)
            return
        generate_text.haber_metinleri_uret(haber)
        db.haber_guncelle(int(ref_id), slayt_yollari=None, slayt_urlleri=None, video_yolu=None)
        telegram_bot.haber_onayina_sun(int(ref_id))
    elif tur == "ilan":
        log.info("İlan #%s için önizleme yeniden hazırlanıyor...", ref_id)
        telegram_bot.ilan_postunu_hazirla_ve_sor(ref_id)


def metin(istek: Istek) -> None:
    """Metin özelleştirme: özetle / detaylandır / baştan yaz."""
    tur, ref_id, hedef = istek.tur, istek.ref_id, istek.hedef
    if tur not in ("haber", "reels"):
        return
    haber = haber_taze(ref_id)
    if not haber:
        return
    if hedef == "metin_ozetle":
        ek_talimat = "Metinleri daha vurucu, kısa ve net bir özet olarak hazırla."
    elif hedef == "metin_detaylandir":
        # "mevzuat maddeleri ekle" talimatı uydurma madde numarasına davetiyeydi.
        ek_talimat = ("İçeriğe daha fazla hukuki derinlik ve hak arama yolları ekle. "
                      "Brief'te veya kaynakta geçmeyen kanun/madde numarası YAZMA.")
    else:
        ek_talimat = "Farklı bir anlatım açısı ve taze bir üslupla baştan hazırla."
    log.info("Metin eylemi (%s) uygulanıyor: #%s", hedef, ref_id)
    generate_text.haber_metinleri_uret(haber, ek_talimat=ek_talimat)
    db.haber_guncelle(int(ref_id), slayt_yollari=None, slayt_urlleri=None, video_yolu=None)
    if tur == "reels":
        telegram_bot.reels_hazirla_ve_sun()
    else:
        telegram_bot.haber_onayina_sun(int(ref_id))
    telegram_bot.mesaj_gonder(f"✍️ <b>Haber #{ref_id} metni güncellendi ({hedef}) ve onayınıza sunuldu.</b>")
