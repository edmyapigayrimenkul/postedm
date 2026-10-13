"""
yayin/kayit.py — Yayın sonucunun veritabanına işlenmesi ve siteye inceleme taslağı bırakma.

Durum makinesi kararı (`durum_kurali.sonraki_durum`) yalnızca "herhangi bir kanalda gerçekten yayında mı" bilgisine bakar; bu bilgi artık
rapor metninde ✓ aranarak değil `KanalSonucu.satirlar[].durum == YAYINDA` ile gelir.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from .. import db, durum_kurali
from .baglam import YayinBaglami
from .sonuc import BILGI, DagitimSonucu, Satir

log = logging.getLogger(__name__)


def site_taslagi_aktar(haber: Optional[dict]) -> str:
    """Sosyal yayından sonra siteye yalnız inceleme taslağı bırakır.

    Yerel denemelerde veya henüz Worker tarafı kurulmadan bu yol kapalıdır;
    sosyal paylaşımın sonucunu değiştirmez. GitHub işinde OIDC kimliğiyle açılır.
    """
    if not haber or os.environ.get("EDM_SITE_ICERIK_AKTARIMI") != "1":
        return ""
    try:
        from .. import site_icerik
        sonuc = site_icerik.site_taslagi_gonder(haber)
        return f"🌐 Site taslağı: incelemeye alındı (#{sonuc.get('id', '—')}) ✓"
    except Exception as hata:  # noqa: BLE001
        log.warning("Haber site taslağına aktarılamadı: %s", hata)
        return "🌐 Site taslağı: oluşturulamadı; sosyal yayın etkilenmedi."


def veritabanini_guncelle(b: YayinBaglami, sonuc: DagitimSonucu) -> None:
    """Haber/ilan durumunu ve kanal kimliklerini yazar, onay isteğini sonuçlandırır; site taslağı notunu rapora ekler."""
    basarili = sonuc.herhangi_yayinda
    haber = b.haber
    if b.haber_mi():
        guncelleme = {"durum": durum_kurali.sonraki_durum(haber.get("durum") if haber else None, basarili),
                      "planlanan_yayin": None}
        if basarili and not (haber and haber.get("yayin_zamani")):
            guncelleme["yayin_zamani"] = datetime.now(timezone.utc).isoformat()
        if sonuc.ig_id:
            guncelleme["instagram_post_id"] = sonuc.ig_id
        if sonuc.threads_id:
            guncelleme["threads_post_id"] = sonuc.threads_id
        if sonuc.fb_id:
            guncelleme["facebook_post_id"] = sonuc.fb_id
        yt = sonuc.yt_res
        if yt.get("durum") and yt.get("video_id"):
            guncelleme["youtube_video_id"] = yt.get("video_id")
        tt = sonuc.tt_res
        if tt.get("durum") and tt.get("publish_id"):
            guncelleme["tiktok_publish_id"] = tt.get("publish_id")
        if sonuc.twitter_id:
            guncelleme["twitter_tweet_id"] = sonuc.twitter_id
        if sonuc.linkedin_id:
            guncelleme["linkedin_post_id"] = sonuc.linkedin_id
        if b.v_yolu and b.v_yolu.exists():
            guncelleme["video_yolu"] = str(b.v_yolu)
        db.haber_guncelle(int(b.ref_id), **guncelleme)
        if basarili and b.tur == "haber":
            site_notu = site_taslagi_aktar(haber)
            if site_notu:
                sonuc.son_satirlar.append(Satir(site_notu, BILGI))
    elif b.tur == "ilan" and basarili:
        db.ilan_paylasildi_isaretle(b.ref_id)

    db.onay_istegi_sonuclandir(b.tur, str(b.ref_id), "yayinlandi" if basarili else "hata")
    db.wal_bosalt()
