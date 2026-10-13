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
    insights_hatalari: list[str] = []

    for h in adaylar:
        hid = h.get("id")
        post_id = h.get("instagram_post_id")
        if not post_id:
            continue

        try:
            metrikler = instagram.medya_metrikleri_al(post_id)
            if not metrikler:
                log.warning("Haber #%d için Instagram metrikleri alınamadı (Post ID: %s)", hid, post_id)
                continue
            if metrikler.get("insights_hata"):
                insights_hatalari.append(metrikler["insights_hata"])

            # None = ölçülemedi. 0 yazmak "hiç erişim yok" demek olur — yanlış veri.
            reach = metrikler.get("reach")
            saved = metrikler.get("saved")
            shares = metrikler.get("shares")
            comments = metrikler.get("comments")
            likes = metrikler.get("likes")
            # `impressions` Meta'da kaldırıldı, yerine `views` geldi; DB sütun adı eski kaldı (şema değişmesin diye).
            # İkisi de ham_veri'de ayrı ayrı durur.
            impressions = metrikler.get("impressions")
            if impressions is None:
                impressions = metrikler.get("views")

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
            g = lambda v: "?" if v is None else v  # noqa: E731
            log.info(
                "İçerik #%d metrikleri kaydedildi: Erişim=%s, Kaydetme=%s, Paylaşım=%s, Beğeni=%s, Yorum=%s",
                hid, g(reach), g(saved), g(shares), g(likes), g(comments)
            )
        except Exception as e:
            log.warning("İçerik #%d için metrik toplama hatası: %s", hid, e)

    db.wal_bosalt()
    if "izin_yok" in insights_hatalari:
        _izin_uyarisi_gonder(insights_hatalari.count("izin_yok"))
    return toplanan_adet


def _izin_uyarisi_gonder(adet: int) -> None:
    """Ölçüm körlüğü sessiz kalmasın — bu sorun 12 gün fark edilmedi."""
    try:
        from src import telegram_bot
        telegram_bot.mesaj_gonder(
            "⚠️ <b>Instagram ölçümü çalışmıyor</b>\n"
            f"{adet} postun erişim/kayıt/paylaşım verisi alınamadı: jetonda "
            "<code>instagram_manage_insights</code> izni yok (#10).\n"
            "<i>Meta geliştirici panelinden bu izinle yeni jeton alınmalı; o zamana kadar "
            "hangi içeriğin işe yaradığı ölçülemez.</i>"
        )
    except Exception as e:
        log.warning("İzin uyarısı gönderilemedi: %s", e)


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
        g = lambda v: "?" if v is None else v  # noqa: E731 — None = ölçülemedi
        print(
            f"ID #{r['haber_id']} | {r['platform'].upper():9} | Erişim: {g(r['reach']):>4} | "
            f"Kaydetme: {g(r['saved']):>3} | Beğeni: {g(r['likes']):>3} | {baslik}"
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

    if not args.haber_id:
        # Günlük takipçi sayısı: gönderi metrikleri vardı, büyüme hiç ölçülmüyordu
        from src import takipci
        takipci.kaydet()


if __name__ == "__main__":
    main()
