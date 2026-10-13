"""
src/telegram/kaldir.py — "Yayından Kaldır": Facebook/Threads gönderilerini siler, Instagram/YouTube/LinkedIn için elle adım bildirir, kaydı "kaldirildi" yapar.

Katman 4 (akış): birden çok kanal modülünü ve DB'yi sırayla yönetir; sonucu Telegram'a raporlar.
"""

from __future__ import annotations

import html
import logging
from typing import Optional

from . import istemci

log = logging.getLogger(__name__)


def yayindan_kaldir(
    tur: str,
    ref_id: str | int,
    mesaj_id: Optional[int] = None,
    basan: Optional[str] = None,
) -> bool:
    """
    Yayınlanmış bir içeriği (haber, ilan, reels) geri alır (Instabot standardı).

    * Facebook API'den gönderi/video silinir (facebook.postu_sil).
    * Threads API'den gönderi/zincir silinir (threads.zinciri_sil).
    * Instagram Graph API silmeye izin vermediği için ("#10 Insufficient permissions")
      kullanıcıya gönderi linki sunulur ve mobil uygulamadan elle silmesi istenir.
    * Veritabanında durum='kaldirildi' yapılır, havuza DÖNMEZ (tekrar ertesi gün çıkmasın).
    """
    from .. import facebook, threads, db

    ref_str = str(ref_id)
    haber = None
    ilan = None
    baslik = f"İçerik #{ref_str}"

    if tur in ("haber", "reels") or ref_str.isdigit():
        haber = db.haber_getir(int(ref_str))
        if haber:
            baslik = haber.get("manset") or haber.get("orijinal_baslik") or f"Haber #{ref_str}"
    elif tur == "ilan":
        ilan = db.ilan_getir(ref_str)
        if ilan:
            baslik = ilan.get("baslik") or f"İlan #{ref_str}"

    if not haber and not ilan:
        istemci.mesaj_gonder(f"⚠️ Yayından kaldırılacak içerik bulunamadı (#{ref_str}).")
        return False

    icerik_obj = haber if haber else ilan
    durum = icerik_obj.get("durum")
    if durum not in ("yayinlandi", "hata", "onay_bekliyor"):
        istemci.mesaj_gonder(f"⚠️ Bu içerik kaldırılmaya uygun bir durumda değil (durum: {durum}).")
        return False

    satirlar = []

    # 1. Facebook
    fb_id = icerik_obj.get("facebook_post_id")
    if fb_id:
        if facebook.postu_sil(fb_id):
            satirlar.append("📘 Facebook gönderisi silindi ✓")
        else:
            satirlar.append("⚠️ Facebook gönderisi silinemedi")
    else:
        satirlar.append("· Facebook: Kayıtlı gönderi ID yok")

    # 2. Threads
    th_id = icerik_obj.get("threads_post_id")
    if th_id:
        silinen, toplam = threads.zinciri_sil(th_id)
        if silinen > 0:
            satirlar.append(f"🧵 Threads zinciri silindi ({silinen}/{toplam} gönderi) ✓")
        else:
            satirlar.append("⚠️ Threads gönderisi silinemedi")
    else:
        satirlar.append("· Threads: Kayıtlı gönderi ID yok")

    # 3. Instagram (Elle silinmeli)
    ig_id = icerik_obj.get("instagram_post_id")
    if ig_id:
        ig_link = f"https://www.instagram.com/p/{ig_id}/"
        satirlar.append(
            "\n📷 <b>Instagram'dan ELLE silmeniz gerekiyor:</b>\n"
            "<i>(Meta Graph API yayınlanmış postların silinmesine izin vermemektedir)</i>\n"
            f"🔗 <a href='{ig_link}'>{ig_link}</a>"
        )
    else:
        satirlar.append("· Instagram: Kayıtlı gönderi ID yok")

    # 4. YouTube & TikTok
    yt_id = icerik_obj.get("youtube_video_id")
    if yt_id:
        satirlar.append(f"▶️ YouTube Shorts: YouTube Studio üzerinden kaldırabilirsiniz (ID: {yt_id})")

    # 5. LinkedIn
    li_id = icerik_obj.get("linkedin_post_id")
    if li_id:
        satirlar.append(f"💼 LinkedIn: Şirket sayfasından kaldırabilirsiniz (ID: {li_id})")
    else:
        satirlar.append("· LinkedIn: Kayıtlı gönderi ID yok")

    # 6. Veritabanını güncelle: havuza DÖNMEMESİ için durum='kaldirildi'
    if haber:
        # (2026-10-13) Eskiden buraya `atlanma_zamani` da yazılıyordu; haberler tablosunda bu sütun hiç yok,
        # UPDATE "no such column" ile çöküyor, gönderiler silinmiş hâlde kayıt "yayında" kalıyordu.
        db.haber_guncelle(int(ref_str), durum="kaldirildi")
    elif ilan:
        db.ilan_kaldirildi_isaretle(ref_str)

    db.onay_istegi_sonuclandir(tur, ref_str, "kaldirildi")
    db.wal_bosalt()

    rapor_metni = (
        f"🗑️ <b>YAYINDAN KALDIRILDI</b>\n\n"
        f"<b>İçerik:</b> {html.escape(baslik)} (#{ref_str})\n"
        f"<b>Kaldıran:</b> {html.escape(basan or 'Kullanıcı')}\n\n"
        + "\n".join(satirlar)
    )

    if mesaj_id:
        istemci.mesaji_guncelle(mesaj_id, rapor_metni, reply_markup=None)

    istemci.mesaj_gonder(rapor_metni)
    log.info("İçerik yayından kaldırıldı: tur=%s, ref_id=%s, basan=%s", tur, ref_str, basan)
    return True
