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
    parser.add_argument("--format", dest="format_turu", choices=["sozluk", "nedir_dogrusu", "vaka", "net_cevap", "reels"],
                        help="Belirli bir formatta otorite içeriği üretir")
    parser.add_argument("--reels", action="store_true", help="Günün konusundan dikey Reels videosu üretir")
    parser.add_argument("--format-degistir", dest="format_degistir_id", type=int,
                        help="Mevcut bir haber/içerik kaydının formatını değiştirip yeniden sunar")
    args = parser.parse_args()

    # Bot duraklatma denetimi (Kullanıcı Telegram'dan duraklatmışsa atla)
    duraklatildi, kalan = telegram_bot.bot_duraklatildi_mi()
    if duraklatildi and not args.durum and not args.format_turu and not args.format_degistir_id and not args.reels:
        log.info("Bot kullanıcı tarafından duraklatılmış (%s). Otomatik hazırlık atlanıyor.", kalan)
        return

    # Havuz bakımı: 14 günden eski, yayınlanmamış kayıtlar her koşuda temizlenir
    silinen = db.eski_kayitlari_temizle(gun=14)
    if silinen:
        log.info("Havuzdan %d eski kayıt temizlendi.", silinen)

    if args.durum:
        ozet = konu_bankasi.durum_ozeti()
        log.info(
            "Konu bankası: %d konudan %d bakir (~%s hafta). Sütun dağılımı: %s",
            ozet["toplam"], ozet["bakir"], ozet["kalan_hafta"], ozet["bakir_sutun_dagilimi"],
        )
        bekleyen = konu_bankasi.bekleyen_adaylar()
        log.info("Onay bekleyen konu adayı: %d", len(bekleyen))
        for a in bekleyen[:8]:
            log.info("   [%s/%s] %s", a.get("sutun"), a.get("bicim"), (a.get("baslik") or "")[:64])
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

    # İlanlar kullanıcının isteği doğrultusunda şimdilik devre dışı bırakıldı
    # fetch_listings.portfoyu_senkronize_et()

    if args.ilan_menu:
        log.info("İlan menüsü geçici olarak devre dışı.")
        return

    # Mevcut haberin formatı değiştirilecekse
    if args.format_degistir_id and args.format_turu:
        log.info("Haber #%d '%s' formatına dönüştürülüyor...", args.format_degistir_id, args.format_turu)
        telegram_bot.format_degistir_ve_sun(haber_id=args.format_degistir_id, hedef_format=args.format_turu)
        return

    # Belirli bir format istendiyse doğrudan o formatı üret
    if args.format_turu:
        log.info("'%s' formatında içerik hazırlanıyor...", args.format_turu)
        telegram_bot.hizli_icerik_uret(format_turu=args.format_turu)
        return

    # Varsayılan akış: Konu bankasından günün takvimine uygun otorite içeriği üret
    if not args.haber_tara:
        log.info("Konu bankasından günün konusu hazırlanıyor...")
        telegram_bot.konu_bankasindan_hazirla(gun=args.gun)
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

    if args.haber_tara:
        log.info("Triyajı geçen haber yok ve --haber-tara verildi; konu bankasına başvurulmuyor.")
        return

    # 3. Varsayılan yol: konu bankası. Takvim RSS'e bağımlı olmadığı için aksamaz.
    log.info("Triyajı geçen haber yok. Konu bankasından üretiliyor...")
    telegram_bot.konu_bankasindan_hazirla(gun=args.gun)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.exception("İçerik hazırlama esnasında hata: %s", e)
        hata_bildir.telegrama_hata_bildir("İçerik Hazırlama", istisna=e)
        sys.exit(1)
