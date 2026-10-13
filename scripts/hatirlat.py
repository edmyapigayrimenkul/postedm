#!/usr/bin/env python3
"""
scripts/hatirlat.py — Onay kuyruğu bakımı (2026-10-13'ten beri OTOMATİK HATIRLATMA YOK)
EDM Yapı & Gayrimenkul — Sosyal Medya Otomasyonu

Kullanıcı kararı (2026-10-13): hatırlatma mesajı gelmesin. Zamanlanmış koşular (Cloudflare cron'u 13:30 ve 21:30; GitHub yedeği) artık
YALNIZ sessiz kuyruk bakımı yapar: 1 günü (ZAMAN_ASIMI_DAKIKA) dolduran onaysız içeriği havuza alır, eski kartlarını gruptan siler.
  · Hazır içerik (konu bankasından modelle yazılmış; `konu_bankasi.HAVUZ_FORMATLARI`) `durum='havuzda'` olur ve aynı formatın bir sonraki
    turunda MODEL ÇAĞRILMADAN yeniden onaya sunulur (`uretim._havuzdan_sun`): "başka bir gün tekrar önerilir".
  · Diğerleri (haber, sözlük kartı, finans, reels) eskisi gibi arşive alınır (`zaman_asimi`) ve konusu havuza iade edilir.
Hatırlatma yalnız KULLANICI isterse gider: `--zorla` (Telegram "⏰ Onayları Hatırlat" düğmesi ve /hatirlat). Mesaj atılmaz, özet de yok.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from src import db, konu_bankasi, telegram_bot

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


import argparse


# Kullanıcı kuralı (2026-10-13): 1 gün = 24 saat. Önceden 5 gündü. Süre dolunca içerik silinmez: hazırsa havuza, değilse arşive alınır.
ZAMAN_ASIMI_DAKIKA = 24 * 60
HATIRLATMA_PENCERESI = 5      # tek turda hatırlatılacak en çok içerik (mesaj yağmurunu önler)
TUM_BEKLEYEN_SINIRI = 500


def _zaman_asimlarini_isle(bekleyenler: list[dict]) -> list[dict]:
    """1 günü dolduran bekleyenleri havuza ya da arşive alır; kalanları döner. SESSİZDİR (mesaj atmaz).

    Havuz: `konu_bankasi.havuza_alinabilir_mi` (evergreen, modelle yazılmış, hazır) → `durum='havuzda'`; konu havuza İADE EDİLMEZ
    çünkü hazır içerik havuzun kendisidir (aksi halde konu yeniden seçilir ve model ikinci kez çağrılırdı).
    Arşiv: diğerleri eskisi gibi `zaman_asimi` + konu iadesi. Her iki durumda eski albüm ve onay kartı gruptan silinir (ölü düğmeler kalmasın).
    Planlı yayını bekleyen içerik, plan penceresi bitene dek zaman aşımına girmez."""
    kalan: list[dict] = []
    for haber in bekleyenler:
        dakika = bekleme_suresi_dakika(haber)
        if planli_yayin_bekliyor(haber) or dakika is None or dakika < ZAMAN_ASIMI_DAKIKA:
            kalan.append(haber)
            continue
        try:
            havuza = konu_bankasi.havuza_alinabilir_mi(haber)
        except Exception as e:  # noqa: BLE001 — havuz kararı verilemezse eski davranış (arşiv) geçerli
            log.warning("Haber #%d havuz kararı verilemedi, arşive alınıyor: %s", haber["id"], e)
            havuza = False
        if havuza:
            log.info("Haber #%d 1 günü doldurdu (%d dakika): hazır içerik havuza alındı.", haber["id"], int(dakika))
            db.durum_havuza_al(haber["id"])
        else:
            log.info("Haber #%d zaman aşımına uğradı (%d dakika): arşive alındı.", haber["id"], int(dakika))
            db.durum_zaman_asimi_yap(haber["id"])
            try:
                konu_bankasi.konuyu_havuza_iade_et(haber["id"])
            except Exception as e:  # noqa: BLE001 — iade başarısızsa arşivleme yine de tamamlanır
                log.warning("Haber #%d konu iadesi yapılamadı: %s", haber["id"], e)
        for tur in ("haber", "haber_album"):
            try:
                telegram_bot.icerik_onceki_mesajlarini_temizle(tur, haber["id"])
            except Exception as e:  # noqa: BLE001 — kart silinemese de içerik durumu doğru kalır (48 saat sınırı, yetki)
                log.warning("Haber #%d eski mesajları silinemedi (%s): %s", haber["id"], tur, e)
    return kalan


def bekleme_suresi_dakika(haber: dict) -> float | None:
    ham = haber.get("eklenme_tarihi")
    if not ham:
        return None
    try:
        gonderim = datetime.fromisoformat(str(ham).strip().replace(" ", "T"))
        if gonderim.tzinfo is None:
            gonderim = gonderim.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - gonderim).total_seconds() / 60
    except Exception:
        return None


def planli_yayin_bekliyor(haber: dict, simdi: datetime | None = None) -> bool:
    try:
        an = datetime.fromisoformat(str(haber.get("planlanan_yayin") or ""))
    except ValueError:
        return False
    if an.tzinfo is None:
        an = an.replace(tzinfo=timezone.utc)
    return (simdi or datetime.now(timezone.utc)) < an + timedelta(hours=3)


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="EDM onay kuyruğu bakımı (1 gün kuralı); --zorla ile elle hatırlatma")
    parser.add_argument("--zorla", "-z", action="store_true", help="ELLE hatırlat: bekleyenleri 60 dk sınırı olmadan Telegram'a kart olarak yolla (otomatik koşular hatırlatmaz)")
    args = parser.parse_args(argv)

    # Zaman aşımı TÜM bekleyenlere uygulanır; hatırlatma yalnız en yeni HATIRLATMA_PENCERESI içeriğe gider.
    # Önceden tek sorgu `LIMIT 5` idi: altıncı ve daha eski içerikler zaman aşımına hiç girmiyor,
    # kuyruk büyüyordu (2026-10-12 ölçümü: 14 içerik, en eskisi 27 Eylül'den beri bekliyordu).
    tum_bekleyenler = db.onay_bekleyen_haberleri_getir(limit=TUM_BEKLEYEN_SINIRI)
    bekleyenler = _zaman_asimlarini_isle(tum_bekleyenler)[:HATIRLATMA_PENCERESI]
    if not args.zorla:
        # Otomatik koşu (cron) yalnız bakım yapar: hatırlatma mesajı YOK (kullanıcı kararı, 2026-10-13).
        log.info("Kuyruk bakımı bitti; %d içerik hâlâ onay bekliyor. Otomatik hatırlatma kapalı.", len(bekleyenler))
        db.wal_bosalt()
        return
    if not bekleyenler:
        log.info("Onay bekleyen içerik yok.")
        if args.zorla:
            telegram_bot.mesaj_gonder("✨ <b>Harika!</b> Şu anda onay bekleyen herhangi bir içerik bulunmuyor.\n\nTüm içerikler yayınlandı veya akış güncel.")
        return

    hatirlatilan_sayisi = 0
    for haber in bekleyenler:
        haber_id = haber["id"]
        dakika = bekleme_suresi_dakika(haber)
        baslik = haber.get("manset") or haber.get("orijinal_baslik") or "İçerik"
        mevcut_hatirlatma = haber.get("hatirlatma_sayisi") or 0

        # Planlı yayını bekleyen içerik hatırlatılmaz: hatırlatma eski onay mesajlarını
        # silip yeni kart attığı için "⏹ Planı iptal et" düğmesi kayboluyordu. Plan 3
        # saatten fazla geçmişse (cron çalışmadıysa) hatırlatma yeniden devreye girer.
        if planli_yayin_bekliyor(haber):
            log.info("Haber #%d planlı yayını bekliyor (%s); hatırlatılmadı.", haber_id, haber.get("planlanan_yayin"))
            continue

        if not args.zorla and dakika is not None and dakika < 60:
            log.info("Haber #%d henüz %d dakikadır bekliyor, hatırlatma için erken.", haber_id, int(dakika))
            continue

        # Azami bildirim kısıtı: Kullanıcıyı mesaj yağmuruna tutmamak için en fazla 3 hatırlatma gönderilir.
        # 3 hatırlatmadan sonra (elle hatırlatmada) içerik sessizce bekletilir; 1 günlük süre dolunca havuza ya da arşive alınır.
        if not args.zorla and mevcut_hatirlatma >= 3:
            log.info("Haber #%d azami hatırlatma adedine (%d) ulaştı; 1 günlük süre dolana kadar sessizce bekletiliyor.", haber_id, mevcut_hatirlatma)
            continue

        yeni_sayi = db.hatirlatma_arttir(haber_id)
        saat_str = f"{int(dakika // 60)} saat " if dakika and dakika >= 60 else ""
        sure_str = f"{saat_str}{int(dakika % 60) if dakika else 0} dakika" if dakika else "Kısa bir süre"

        is_reels = (haber.get("kategori") == "REELS" or (haber.get("kaynak") and "reels" in str(haber.get("kaynak")).lower()))
        tur = "reels" if is_reels else "haber"

        if is_reels:
            metin = (
                f"✨ <b>Sayın EDM Ekibi,</b> ({yeni_sayi}. Hatırlatma)\n\n"
                f"Yayına hazır 9:16 dikey Reels videomuz onayınızı beklemektedir:\n\n"
                f"🎬 <b>Başlık:</b> {baslik}\n"
                f"⏱️ <b>Hazırlanma:</b> {sure_str} önce tamamlandı.\n\n"
                f"<i>İçeriği inceleyip aşağıdaki seçeneklerden dilediğinizi tercih edebilirsiniz:</i>"
            )
            butonlar = {
                "inline_keyboard": [
                    [
                        {"text": "🚀 YouTube & TikTok'ta Otomatik Yayınla", "callback_data": f"onayla:reels:video:{haber_id}"},
                    ],
                    [
                        {"text": "✅ Instagram'da Paylaştım (Tamamlandı)", "callback_data": f"onayla:reels:tamamla:{haber_id}"},
                    ],
                    [
                        {"text": "🔄 Yeniden Üret", "callback_data": f"yenile:reels:{haber_id}"},
                        {"text": "❌ İptal Et", "callback_data": f"reddet:reels:{haber_id}"},
                    ],
                ]
            }
        else:
            metin = (
                f"✨ <b>Sayın EDM Ekibi,</b> ({yeni_sayi}. Hatırlatma)\n\n"
                f"Onayınızı bekleyen güncel içerik taslağımız hazır durumdadır:\n\n"
                f"📌 <b>Başlık:</b> {baslik}\n"
                f"⏱️ <b>Hazırlanma:</b> {sure_str} önce tamamlandı.\n\n"
                f"<i>İçeriği inceleyip aşağıdaki seçeneklerden dilediğinizi tercih edebilirsiniz:</i>"
            )
            butonlar = {
                "inline_keyboard": [
                    [
                        {"text": "🚀 Seçili Kanallarda Yayınla", "callback_data": f"onayla:haber:ig,threads:{haber_id}"},
                        {"text": "📲 Manuel Paket", "callback_data": f"manuel_paket:{haber_id}"},
                    ],
                    [
                        {"text": "🔄 Metinleri Yenile", "callback_data": f"yenile:haber:{haber_id}"},
                        {"text": "🎨 Formatı Değiştir", "callback_data": f"format_menu:{haber_id}"},
                    ],
                    [
                        {"text": "⏰ 1 Saat Ertele", "callback_data": f"ertele:haber:{haber_id}"},
                        {"text": "❌ İptal / Reddet", "callback_data": f"reddet:haber:{haber_id}"},
                    ],
                ]
            }

        # Chat kaosunu önle: Aynı içerik için daha önce atılmış olan onay veya hatırlatma kartlarını temizle
        telegram_bot.icerik_onceki_mesajlarini_temizle(tur, haber_id)

        res = telegram_bot.mesaj_gonder(metin, reply_markup=butonlar)
        if res and isinstance(res, dict) and "message_id" in res:
            _, chat_id = telegram_bot._bot_bilgileri()
            try:
                cid = int(str(chat_id).strip()) if str(chat_id).lstrip("-").isdigit() else None
                db.onay_istegi_kaydet(tur, str(haber_id), res["message_id"], cid)
            except Exception as e:
                log.warning("Hatırlatma mesaj ID kaydı hatası: %s", e)

        hatirlatilan_sayisi += 1
        log.info("Haber #%d için hatırlatma mesajı (%d.) Telegram'a iletildi.", haber_id, yeni_sayi)

    if hatirlatilan_sayisi == 0 and args.zorla:
        telegram_bot.mesaj_gonder("✨ <b>Bilgilendirme:</b> İçerik yakın zamanda hazırlandığı için henüz hatırlatma periyoduna (60 dk) girmedi.")

    db.wal_bosalt()


if __name__ == "__main__":
    main()
