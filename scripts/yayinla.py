#!/usr/bin/env python3
"""
scripts/yayinla.py — Onaylanan İçeriği Platformlarda Yayınlama Komutu
Telegram'dan gelen onay butonuna tıklandığında Cloudflare Worker veya Actions tarafından tetiklenir.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import db, instagram, telegram_bot, threads, tiktok, upload_image, video, youtube

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="EDM Paylaşım Yayınlayıcı")
    parser.add_argument("--tur", required=True, choices=["haber", "ilan"], help="İçerik türü")
    parser.add_argument("--id", required=True, help="Haber ID veya İlan ID")
    parser.add_argument("--hedef", default="hepsi", choices=["hepsi", "ig", "threads", "video"], help="Hedef platform")
    args = parser.parse_args()

    tur = args.tur
    ref_id = args.id
    hedef = args.hedef

    log.info("Yayın süreci başlatılıyor: Tür=%s, ID=%s, Hedef=%s", tur, ref_id, hedef)

    slayt_yollari = []
    caption = ""
    baslik = ""

    if tur == "haber":
        haber = db.haber_getir(int(ref_id))
        if not haber:
            log.error("Haber bulunamadı: #%s", ref_id)
            return

        baslik = haber.get("manset") or haber.get("orijinal_baslik")
        caption = haber.get("ig_caption") or baslik
        slayt_json = haber.get("slayt_yollari")
        if slayt_json:
            try:
                slayt_yollari = json.loads(slayt_json)
            except Exception:
                pass

    elif tur == "ilan":
        ilan = db.ilan_getir(ref_id)
        if not ilan:
            log.error("İlan bulunamadı: #%s", ref_id)
            return

        baslik = ilan.get("baslik")
        caption = f"{baslik}\n\nEDM Yapı & Gayrimenkul · Yatırım Ortağınız\n0536 343 41 97 · edmyapigayrimenkul.com"
        
        # Slaytları bul veya üret (3'lü Prestij Carousel)
        k1 = KOK / f"data/output/ilan_kapak_{ref_id}.jpg"
        k2 = KOK / f"data/output/ilan_detay_{ref_id}.jpg"
        k3 = KOK / f"data/output/ilan_kapanis_{ref_id}.jpg"
        
        if not (k1.exists() and k2.exists() and k3.exists()):
            from src import make_image
            k1 = make_image.ilan_kapak_slayti_ciz(ilan)
            k2 = make_image.ilan_detay_slayti_ciz(ilan)
            k3 = make_image.ilan_kapanis_slayti_ciz(ilan)

        slayt_yollari = [str(k1), str(k2), str(k3)]

    if not slayt_yollari:
        log.error("Paylaşılacak slayt görseli bulunamadı.")
        return

    # 1. Görselleri imgbb / catbox'a yükle (Public URL'ler al)
    log.info("%d adet slayt görseli yükleniyor...", len(slayt_yollari))
    public_urller = upload_image.coklu_gorsel_yukle(slayt_yollari)
    if not public_urller:
        log.error("Görseller public URL'e yüklenemedi!")
        return

    ig_id = None
    threads_id = None
    rapor_satirlari = []

    # 2. Instagram Yayını
    if hedef in ("hepsi", "ig"):
        log.info("Instagram'da Carousel paylaşılıyor...")
        ig_id = instagram.carousel_yayinla(public_urller, caption)
        if ig_id:
            rapor_satirlari.append("📸 <b>Instagram:</b> Paylaşıldı ✓")
        else:
            rapor_satirlari.append("📸 <b>Instagram:</b> Hata oluştu ✗")

    # 3. Threads Yayını
    if hedef in ("hepsi", "threads"):
        log.info("Threads'te paylaşılıyor...")
        threads_id = threads.paylas(caption, public_urller)
        if threads_id:
            rapor_satirlari.append("🧵 <b>Threads:</b> Paylaşıldı ✓")
        else:
            rapor_satirlari.append("🧵 <b>Threads:</b> Hata oluştu ✗")

    # 4. Video (YouTube Shorts & TikTok)
    if hedef in ("hepsi", "video"):
        log.info("Dikey video üretiliyor...")
        video_yolu = video.slaytlardan_video_uret(slayt_yollari)
        if video_yolu and video_yolu.exists():
            yt_res = youtube.shorts_yukle(video_yolu, baslik=baslik)
            if yt_res.get("durum"):
                rapor_satirlari.append(f"▶️ <b>YouTube Shorts:</b> <a href='{yt_res.get('url')}'>İzle</a> ✓")

            tt_res = tiktok.video_yukle(video_yolu, baslik=baslik)
            if tt_res.get("durum"):
                rapor_satirlari.append("🎵 <b>TikTok:</b> Yüklendi ✓")

    # 5. Veritabanını güncelle
    if tur == "haber":
        db.haber_guncelle(int(ref_id), durum="yayinlandi", instagram_post_id=ig_id, threads_post_id=threads_id)
    elif tur == "ilan":
        db.ilan_paylasildi_isaretle(ref_id)

    # 6. Telegram'a sonuç raporu ilet
    sonuc_metni = (
        f"🎉 <b>YAYIN BAŞARIYLA TAMAMLANDI</b>\n\n"
        f"<b>İçerik:</b> {baslik}\n\n"
        + "\n".join(rapor_satirlari)
    )
    telegram_bot.mesaj_gonder(sonuc_metni)
    log.info("Yayınlama süreci tamamlandı.")


if __name__ == "__main__":
    main()
