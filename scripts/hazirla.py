#!/usr/bin/env python3
"""
scripts/hazirla.py — EDM Haber ve İlan Hazırlama Komutu
GitHub Actions cron'u veya elle çalıştırılır.
RSS'i tarar, sektörel haberleri seçer, Telegram grubuna onaya sunar.
Ayrıca --ilan-menu parametresiyle portföydeki ilanların seçim menüsünü gruba atar.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Kök dizini sys.path'e ekle
KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import (db, fetch_listings, fetch_news, haber_triyaj, hata_bildir,
                 konu_bankasi, telegram_bot)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# Haberin takvimin önüne geçmesi İKİ KAPIDAN geçmesini gerektirir:
#
#   1. Kural tabanlı puan (haber_puanlama) — ucuz ön eleme. Bu eşiği geçmeyen
#      haber LLM'e hiç gönderilmez; triyaj çağrısı bedava değil.
#   2. LLM triyajı (haber_triyaj) — "burada gerçek bir EDM açısı var mı?"
#      Model reddedebilir ve çoğu zaman reddetmelidir.
#
# Eşik neden bu kadar yüksek: 2026-09-11 ölçümünde 5 kaynaktan 175 haberin
# yalnızca 16'sı aday oldu ve en yükseği 11 puan aldı. Hazırlanmış bir konu
# brief'i pratikte çoğu haberden iyi içerik üretiyor; haber ancak gerçekten
# değerliyse araya girmeli.
HABER_ON_ELEME_ESIGI = 9
TRIYAJ_ASGARI_GUVEN = 7

# Havuzda bekleyen bir haber bu yaşı geçtiyse artık "haber" değildir.
# Tazelik süzgeci (config: haberler.haber_yasi_saat) yalnızca TARAMA anında
# çalışıyordu; havuzda günlerce bekleyen bir kayıt triyajı geçerse bayat
# içerik "haber" diye paylaşılırdı.
YAYIN_TAZELIK_SAAT = 72


def _konu_adayi_kaydet(haber: dict) -> None:
    """Haberi konu bankası adayına çevirip kaydeder."""
    oneri = haber_triyaj.konu_onerisi_uret(haber)
    if not oneri:
        return
    if konu_bankasi.aday_kaydet(oneri):
        log.info("Konu adayı kaydedildi: %s", oneri.get("baslik", "")[:60])


def _konu_adaylarini_madenle(limit: int = 4) -> int:
    """Rehber/açıklayıcı haberleri konu bankası adaylarına çevirir.

    Beslemenin asıl değeri burada: "Temellük nedir?" gibi başlıklar insanların
    ne aradığını gösteriyor ve bankamızda karşılığı yok. Haber olarak
    paylaşılmazlar; konu havuzunu besler ve takvimin ömrünü uzatırlar.
    """
    rehberler = [h for h in db.bekleyen_haberleri_getir(limit=20)
                 if (h.get("kategori") or "") == "rehber"][:limit]
    sayac = 0
    for h in rehberler:
        oneri = haber_triyaj.konu_onerisi_uret(h)
        if oneri and konu_bankasi.aday_kaydet(oneri):
            sayac += 1
            log.info("Konu adayı: %s", oneri.get("baslik", "")[:60])
            db.haber_guncelle(h["id"], durum="madenlendi")
        else:
            db.haber_guncelle(h["id"], durum="elendi")
    return sayac


def main() -> None:
    parser = argparse.ArgumentParser(description="EDM Paylaşım Hazırlayıcı")
    parser.add_argument("--ilan-menu", action="store_true", help="Telegram'a portföy ilan seçim menüsünü gönderir")
    parser.add_argument("--haber-tara", action="store_true", help="Yalnızca RSS tarar; konu bankasına başvurmaz")
    parser.add_argument("--konu", action="store_true", help="Yalnızca konu bankasından üretir; RSS'e bakmaz")
    parser.add_argument("--gun", type=int, default=None, help="Takvim günü (0=Pazartesi ... 4=Cuma). Test için")
    parser.add_argument("--durum", action="store_true", help="Konu bankası doluluk durumunu yazar ve çıkar")
    parser.add_argument("--konu-madenle", action="store_true",
                        help="Rehber haberleri konu bankası adaylarına çevirir")
    parser.add_argument("--slot", choices=["bilgilendirici", "sozluk", "haber"],
                        help="bilgilendirici = günün tek içeriği; sozluk = elle sözlük; haber = haber önerileri")
    parser.add_argument("--format", dest="format_turu", choices=["sozluk", "nedir_dogrusu", "vaka", "net_cevap", "b1", "reels"],
                        help="Belirli bir formatta otorite içeriği üretir")
    parser.add_argument("--reels", action="store_true", help="Günün konusundan dikey Reels videosu üretir")
    parser.add_argument("--finans", action="store_true", help="Finans, bankacılık, faiz ve konut kredisi konulu bülten üretir")
    parser.add_argument("--oto-yayin", action="store_true", help="Onay sormadan doğrudan tüm kanallarda otomatik yayınlar")
    parser.add_argument("--format-degistir", dest="format_degistir_id", type=int,
                        help="Mevcut bir haber/içerik kaydının formatını değiştirip yeniden sunar")
    parser.add_argument("--haber-oneri", action="store_true",
                        help="Taze haberleri tarihleriyle Telegram'a öneri olarak düşürür (içerik üretmez)")
    parser.add_argument("--haberden", dest="haberden_id",
                        help="Önerilen haber(ler)i triyajdan geçirip içerik olarak onaya sunar: 272 ya da 272,273")
    args = parser.parse_args()

    # İnsan "İçeriğe çevir" ya da "▶️ Hazırla" dediyse duraklatma sorulmaz: bu bir elle istek
    if args.haberden_id:
        from src import haber_oneri
        idler = [int(p) for p in str(args.haberden_id).split(",") if p.strip().isdigit()]
        if not idler:
            log.error("Geçersiz haber kimliği: %s", args.haberden_id)
            return
        haber_oneri.haberlerden_icerige(idler)
        return

    # Bot duraklatma denetimi (Kullanıcı Telegram'dan duraklatmışsa atla)
    duraklatildi, kalan = telegram_bot.bot_duraklatildi_mi()
    if duraklatildi and args.haber_oneri:
        log.info("Bot duraklatılmış (%s); haber önerisi atlanıyor.", kalan)
        return
    # Duraklatma ZAMANLANMIŞ koşuları da durdurur. Eskiden `--slot`/`--format` bayrağı "elle istek" sayılıp
    # duraklatmayı atlıyordu; 10:00 ve 12:30 cron'ları da `--slot` ile çalıştığı için bot duraklatılmışken
    # içerik üretiliyor, Gemini kotası ve konu harcanıyordu. Zamanlanmış koşuyu hazirla.yml `ZAMANLANMIS=true`
    # ile işaretler; elle tetiklenen (Telegram butonu, workflow_dispatch) koşular duraklatmayı aşar.
    zamanlanmis = os.environ.get("ZAMANLANMIS", "").strip().lower() == "true"
    elle_istek = bool(args.slot or args.format_turu or args.format_degistir_id or args.reels or args.finans)
    if duraklatildi and not args.durum and (zamanlanmis or not elle_istek):
        log.info("Bot kullanıcı tarafından duraklatılmış (%s). Otomatik hazırlık atlanıyor.", kalan)
        return

    # Havuz bakımı: 14 günden eski, yayınlanmamış kayıtlar her koşuda temizlenir
    silinen = db.eski_kayitlari_temizle(gun=14)
    if silinen:
        log.info("Havuzdan %d eski kayıt temizlendi.", silinen)
    bayat = db.bayat_haberleri_ayikla(saat=YAYIN_TAZELIK_SAAT)
    if bayat:
        log.info("Havuzdan %d bayat haber elendi.", bayat)

    if args.durum:
        ozet = konu_bankasi.durum_ozeti()
        log.info(
            "Konu bankası: %d konudan %d bakir (~%s hafta). Sütun dağılımı: %s",
            ozet["toplam"], ozet["bakir"], ozet["kalan_hafta"], ozet["bakir_sutun_dagilimi"],
        )
        from src import sozluk_arsivi
        kart = sozluk_arsivi.durum_ozeti()
        log.info("Sözlük kartı: %d kart, %d tanesi hiç yayınlanmadı (≈%d gün); %d yıl tekrarsız için %d kart gerekir, %d eksik "
                 "(zamanlanmış otomatik yayın: %s).",
                 kart["toplam"], kart["bakir"], kart["bakir"] * sozluk_arsivi.YAYIN_ARALIK_GUN, sozluk_arsivi.BEKLEME_GUN // 365, sozluk_arsivi.HEDEF_KART, kart["eksik"],
                 "KAPATILMIŞ (acil fren: SOZLUK_OTO_YAYIN)" if telegram_bot.sozluk_oto_yayin_kapatildi_mi() else "açık")
        from src import piyasa_verisi
        log.info(piyasa_verisi.durum_ozeti())
        bekleyen = konu_bankasi.bekleyen_adaylar()
        log.info("Onay bekleyen konu adayı: %d", len(bekleyen))
        for a in bekleyen[:8]:
            log.info("   [%s/%s] %s", a.get("sutun"), a.get("bicim"), (a.get("baslik") or "")[:64])
        return

    if args.haber_oneri:
        from src import haber_oneri
        haber_oneri.onerileri_gonder(tara=True)
        return

    if args.konu:
        log.info("Yalnızca konu bankasından üretiliyor (RSS taranmıyor)...")
        telegram_bot.konu_bankasindan_hazirla(gun=args.gun)
        return

    if args.slot:
        # Zamanlanmış tur Cloudflare cron'undan (asıl) ve GitHub cron'undan (gecikmeli yedek) gelebilir: aynı slot aynı
        # Türkiye gününde ikinci kez üretilmez. Elle tetiklenenler (Telegram, workflow_dispatch) bu korumaya takılmaz.
        if zamanlanmis and telegram_bot.zamanli_slot_bugun_yapildi(args.slot):
            log.info("Zamanlanmış '%s' turu bugün zaten çalışmış; yedek tetik atlanıyor.", args.slot)
            return
        log.info("Günlük slot çalıştırılıyor: '%s' (Otomatik yayın: %s)...", args.slot, args.oto_yayin)
        basarili = telegram_bot.slot_icerigi_hazirla_ve_sun(slot=args.slot, oto_yayin=args.oto_yayin)
        if zamanlanmis and basarili:
            telegram_bot.zamanli_slot_isaretle(args.slot)
        return

    if args.finans:
        log.info("Finans & Gayrimenkul bülteni hazırlanıyor (Otomatik yayın: %s)...", args.oto_yayin)
        telegram_bot.finans_icerigi_hazirla_ve_yayinla(oto_yayin=args.oto_yayin)
        return

    if args.reels or args.format_turu == "reels":
        log.info("Akşam Reels videosu hazırlanıyor...")
        telegram_bot.reels_hazirla_ve_sun()
        return

    if args.konu_madenle:
        fetch_news.rss_tara()
        n = _konu_adaylarini_madenle(limit=6)
        log.info("%d konu adayı eklendi. 'hazirla.py --durum' ile görebilirsin.", n)
        return

    if args.ilan_menu:
        log.info("Portföy senkronize ediliyor ve ilan menüsü gönderiliyor...")
        fetch_listings.portfoyu_senkronize_et()
        telegram_bot.tek_tikla_ilan_menusu_gonder()
        return

    # Mevcut haberin formatı değiştirilecekse
    if args.format_degistir_id and args.format_turu:
        log.info("Haber #%d '%s' formatına dönüştürülüyor...", args.format_degistir_id, args.format_turu)
        telegram_bot.format_degistir_ve_sun(haber_id=args.format_degistir_id, hedef_format=args.format_turu)
        return

    # Belirli bir format istendiyse doğrudan o formatı üret
    if args.format_turu:
        log.info("'%s' formatında içerik hazırlanıyor (Otomatik yayın: %s)...", args.format_turu, args.oto_yayin)
        if args.format_turu == "sozluk":
            telegram_bot.sozluk_karti_hazirla_ve_sun(oto_yayin=args.oto_yayin)
        else:
            telegram_bot.hizli_icerik_uret(format_turu=args.format_turu)
        return

    # Varsayılan akış: Günlük bilgilendirici slot rotasyonu veya belirtilen slot
    if not args.haber_tara:
        hedef_slot = args.slot or "bilgilendirici"
        log.info("Slot hazırlanıyor: '%s' (Otomatik yayın: %s)...", hedef_slot, args.oto_yayin)
        telegram_bot.slot_icerigi_hazirla_ve_sun(slot=hedef_slot, oto_yayin=args.oto_yayin)
        return

    # Yalnızca --haber-tara bayrağı verildiğinde RSS taranır
    log.info("Emlak ve ekonomi RSS kaynakları taranıyor...")
    yeni_haberler = fetch_news.rss_tara()
    log.info("%d adet yeni alakalı haber bulundu.", len(yeni_haberler))

    # Havuz bakımı: 14 günden eski, yayınlanmamış kayıtlar silinir.
    # Çağrılmadığı için havuz yalnızca büyüyordu.
    silinen = db.eski_kayitlari_temizle(gun=14)
    if silinen:
        log.info("Havuzdan %d eski kayıt temizlendi.", silinen)

    # 1. kapı: kural tabanlı ön eleme
    adaylar = []
    for h in db.bekleyen_haberleri_getir(limit=20):
        if (h.get("kategori") or "") == "rehber":
            continue
        # Yayın anı tazeliği: havuzda bayatlamış kayıt "haber" olarak paylaşılmaz
        yas = fetch_news._saat_farki_saat(h.get("yayin_tarihi") or "")
        if yas > YAYIN_TAZELIK_SAAT:
            log.info("Bayatladı (%.0f saat), eleniyor: %s", yas, h["orijinal_baslik"][:50])
            db.haber_guncelle(h["id"], durum="elendi")
            continue
        if h.get("onem_puani", 0) < HABER_ON_ELEME_ESIGI:
            continue
        adaylar.append(h)
        if len(adaylar) >= 6:
            break
    log.info("Ön elemeyi geçen haber adayı: %d", len(adaylar))

    # 2. kapı: LLM triyajı. Modelin reddetme yetkisi var ve çoğu zaman reddeder.
    for aday in adaylar:
        brief = haber_triyaj.triyaj_et(aday, asgari_guven=TRIYAJ_ASGARI_GUVEN)
        if not brief:
            # Red sebebi "kalıcı bilgi, haber değil" ise çöpe atma: bankaya aday yap
            if haber_triyaj.konu_adayi_mi(aday):
                _konu_adayi_kaydet(aday)
            # ELENDİ olarak işaretle. Aksi halde aynı haber HER GÜN yeniden
            # triyaja giriyordu: günde 6 boşa LLM çağrısı ve konu bankasına
            # hiç sıra gelmiyordu (üretimde konu_gecmisi tablosu bile oluşmamıştı).
            db.haber_guncelle(aday["id"], durum="elendi")
            continue
        log.info(
            "Haber takvimin önüne geçiyor (puan %d, güven %s): %s",
            aday["onem_puani"], brief["_guven"], aday["orijinal_baslik"][:60],
        )
        telegram_bot.haberden_icerik_hazirla(aday, brief)
        return

    # Bu noktaya yalnız `--haber-tara` ile gelinir (varsayılan yol yukarıda slot'a, `--konu` konu bankasına gider).
    log.info("Triyajı geçen haber yok; --haber-tara konu bankasına başvurmaz.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.exception("İçerik hazırlama esnasında hata: %s", e)
        hata_bildir.telegrama_hata_bildir("İçerik Hazırlama", istisna=e)
        sys.exit(1)
