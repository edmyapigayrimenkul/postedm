#!/usr/bin/env python3
"""
scripts/metrik_topla.py — EDM Sessiz Analitik Veri Toplayıcı (Analytics Harvester)

Paylaşılan gönderilerin 24 saat ile 7 gün arasındaki performans verilerini
(erişim, kaydedilme, paylaşım, beğeni, yorum) Instagram Graph API'den sessizce
çeker ve veritabanına kaydeder.

Kullanım:
    python scripts/metrik_topla.py
    python scripts/metrik_topla.py --rapor
    python scripts/metrik_topla.py --haber-id 123
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Proje kökünü sys.path'e ekle
KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from src import db, instagram

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("metrik_topla")


def metrikleri_topla(haber_id_filtre: int | None = None) -> int:
    """Yayınlanmış içeriklerin metriklerini çekip veritabanına yazar."""
    if haber_id_filtre:
        haber = db.haber_getir(haber_id_filtre)
        if not haber or not haber.get("instagram_post_id"):
            log.warning("Haber #%s bulunamadı veya Instagram post ID'si yok.", haber_id_filtre)
            return 0
        adaylar = [haber]
    else:
        adaylar = db.yayinlanmis_ve_metrik_bekleyenler(min_yas_saat=12.0, max_yas_saat=168.0)

    if not adaylar:
        log.info("Metrik toplanacak taze yayınlanmış içerik bulunamadı (12-168 saat arası).")
        return 0

    log.info("%d adet yayınlanmış içerik için metrik toplama başlatılıyor...", len(adaylar))
    toplanan_adet = 0

    for h in adaylar:
        hid = h.get("id")
        post_id = h.get("instagram_post_id")
        if not post_id:
            continue

        try:
            metrikler = instagram.medya_metrikleri_al(post_id)
            if not metrikler:
                log.debug("Haber #%d için Instagram metrikleri alınamadı (Post ID: %s)", hid, post_id)
                continue

            reach = metrikler.get("reach", 0)
            saved = metrikler.get("saved", 0)
            shares = metrikler.get("shares", 0)
            comments = metrikler.get("comments", 0)
            likes = metrikler.get("likes", 0)
            impressions = metrikler.get("impressions", 0)

            db.metrik_kaydet(
                haber_id=hid,
                platform="instagram",
                medya_id=post_id,
                reach=reach,
                impressions=impressions,
                saved=saved,
                shares=shares,
                comments=comments,
                likes=likes,
                ham_veri=metrikler,
            )
            toplanan_adet += 1
            log.info(
                "İçerik #%d metrikleri kaydedildi: Erişim=%d, Kaydetme=%d, Paylaşım=%d, Beğeni=%d, Yorum=%d",
                hid, reach, saved, shares, likes, comments
            )
        except Exception as e:
            log.warning("İçerik #%d için metrik toplama hatası: %s", hid, e)

    db.wal_bosalt()
    return toplanan_adet


def metrik_raporu_bas():
    """Veritabanında toplanan son metrikleri listeler."""
    with db._baglanti_al() as conn:
        rows = conn.execute(
            """SELECT m.haber_id, m.platform, m.reach, m.saved, m.shares, m.likes, m.comments, m.kayit_tarihi,
                      h.manset, h.kategori
               FROM icerik_metrikleri m
               LEFT JOIN haberler h ON m.haber_id = h.id
               ORDER BY m.id DESC LIMIT 30"""
        ).fetchall()

    if not rows:
        print("Henüz kaydedilmiş metrik bulunmuyor.")
        return

    print("\n" + "=" * 80)
    print("  EDM SOSYAL MEDYA İÇERİK PERFORMANS RAPORU")
    print("=" * 80)
    for r in rows:
        baslik = (r["manset"] or "Başlıksız")[:40]
        print(
            f"ID #{r['haber_id']} | {r['platform'].upper():9} | Erişim: {r['reach']:4} | "
            f"Kaydetme: {r['saved']:3} | Beğeni: {r['likes']:3} | {baslik}"
        )
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="EDM Sessiz Analitik Veri Toplayıcı")
    parser.add_argument("--rapor", action="store_true", help="Toplanan metrikleri listele")
    parser.add_argument("--haber-id", type=int, default=None, help="Belirli bir haberin metriğini topla")
    args = parser.parse_args()

    if args.rapor:
        metrik_raporu_bas()
        return

    adet = metrikleri_topla(haber_id_filtre=args.haber_id)
    log.info("İşlem tamamlandı. Toplam %d içerik metriği kaydedildi.", adet)


if __name__ == "__main__":
    main()
