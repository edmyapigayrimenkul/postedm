"""
yayin/akis.py — Yayın akışının ANA SIRASI. Tek bakışta okunabilsin diye burada yalnızca sıra var; ayrıntı alt modüllerde.

    istek → (plan kaydı) → durum koruması + yayın kapısı → (içerik işlemi: reddet/yenile/...) →
    içerik yükle → görselleri hazırla → video hazırla → kanalları seç → paralel dağıt → kaydet → Telegram'a raporla
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Optional

from .. import db, durum_kurali, telegram_bot
from . import aksiyonlar, dagitim, hedef, icerik, kayit, koruma, rapor, videolar
from .aksiyonlar import yonetim
from .baglam import Istek
from .ilerleme import Ilerleme

log = logging.getLogger(__name__)


def argumanlari_oku(argv=None):
    parser = argparse.ArgumentParser(description="EDM Paylaşım Yayınlayıcı")
    parser.add_argument("--tur", default="haber", choices=["haber", "ilan", "reels"], help="İçerik türü")
    parser.add_argument("--id", default=None, help="Haber ID veya İlan ID")
    parser.add_argument("--mesaj-id", default=None, type=int, help="Telegram mesaj ID")
    parser.add_argument("--hedef", default="hepsi", help="Hedef platform veya işlem")
    parser.add_argument("--yeniden-ciz", action="store_true", help="İlan kartlarını güncel site verisiyle yeniden üret")
    parser.add_argument("--plan-an", default=None, help="hedef=planla: Worker'ın planladığı yayın zamanı (ISO)")
    return parser.parse_args(argv)


def istek_coz(args) -> Optional[Istek]:
    """Komut satırından isteği kurar; kimlik verilmediyse Telegram mesajından (ya da son onay bekleyenden) bulur."""
    tur = args.tur
    ref_id = args.id
    if (not ref_id or ref_id == "None") and args.mesaj_id:
        bulunan = db.mesajdan_icerik_bul(args.mesaj_id)
        if bulunan:
            tur, ref_id_int, _ = bulunan
            ref_id = str(ref_id_int)
    elif not ref_id or ref_id == "None":
        bulunan = db.mesajdan_icerik_bul(None)
        if bulunan:
            tur, ref_id_int, _ = bulunan
            ref_id = str(ref_id_int)

    if not ref_id:
        log.error("İşlem yapılacak içerik ID'si bulunamadı.")
        return None
    return hedef.istek_olustur(tur, ref_id, args.hedef, mesaj_id=args.mesaj_id, yeniden_ciz=args.yeniden_ciz, plan_an=args.plan_an)


def yayinla(istek: Istek) -> None:
    """Kanallara yayın: içeriği yükle, görsel/video hazırla, seçilen kanallara paralel dağıt, kaydet, raporla."""
    b = icerik.yukle(istek)
    hedef.bayraklari_belirle(b)
    icerik.gorselleri_hazirla(b)
    on_satirlar = videolar.hazirla(b)

    kanallar = hedef.kanal_listesi(b)

    # Aynı kanala ikinci kez gönderme: "tekrar dene", "kurtar" ya da iki kez
    # basılan "Yayınla" yalnızca henüz yayında OLMAYAN kanallara gider.
    if b.haber:
        zaten_yayinda = durum_kurali.tekrar_gonderilmeyecekler(b.haber, kanallar)
        if zaten_yayinda:
            kanallar = [k for k in kanallar if k not in zaten_yayinda]
            log.info("#%s zaten yayında olan kanallar atlandı: %s", b.ref_id, zaten_yayinda)
            telegram_bot.mesaj_gonder(
                f"ℹ️ <b>#{b.ref_id}</b> şu kanallarda zaten yayında, tekrar gönderilmedi: "
                f"<code>{', '.join(zaten_yayinda)}</code>"
            )
        if not kanallar:
            db.wal_bosalt()
            return

    ilerleme = Ilerleme(kanallar, istek.mesaj_id, b.baslik)
    ilerleme.baslat()
    sonuc = dagitim.dagit(b, kanallar, ilerleme)
    sonuc.on_satirlar = on_satirlar

    kayit.veritabanini_guncelle(b, sonuc)

    if not sonuc.satirlar:
        raise RuntimeError(f"Geçerli yayın hedefi bulunamadı: {istek.hedef}")

    rapor.gonder(b, sonuc, ilerleme.gecen_sure())
    print("POSTEDM_SONUC=" + json.dumps({"hedefler": sorted(istek.hedefler), "rapor": [s.metin for s in sonuc.satirlar]}, ensure_ascii=False))
    if sonuc.hata_var:
        rapor.ham_hatayi_kaydet(sonuc)
        raise RuntimeError("Bir veya daha fazla sosyal medya yayını başarısız oldu.")
    log.info("Yayınlama süreci tamamlandı.")


def calistir(argv=None) -> None:
    args = argumanlari_oku(argv)
    istek = istek_coz(args)
    if istek is None:
        return

    log.info("Yayın süreci başlatılıyor: Tür=%s, ID=%s, Hedef=%s", istek.tur, istek.ref_id, istek.hedef)

    if istek.hedef in ("planla", "plan_iptal"):
        yonetim.plan_kaydi(istek)
        return

    devam, mevcut = koruma.kontrol(istek)
    if not devam:
        return

    if aksiyonlar.isle(istek, mevcut):
        return

    yayinla(istek)
