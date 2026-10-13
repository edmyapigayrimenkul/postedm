#!/usr/bin/env python3
"""
scripts/yayinla.py — Onaylanan İçeriği Platformlarda Yayınlama Komutu
Telegram'dan gelen onay butonuna tıklandığında Cloudflare Worker veya Actions tarafından tetiklenir.

2026-10-13: 1571 satırlık tek dosya `src/yayin/` paketine bölündü (okumaya `src/yayin/akis.py`tan başla). Bu dosya yalnızca
komut satırı girişidir; iş mantığı yoktur.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

# Bu modül adlarını testler `yayinla.<modul>` üzerinden yama ile değiştiriyor (modül nesnesinin özniteliği, yani her yerde geçerli);
# kaldırılırsa o testler kırılır.
from src import db, durum_kurali, facebook, generate_text, hata_bildir, instagram, konu_bankasi, linkedin, make_image, ses, telegram_bot, threads, tiktok, twitter, upload_image, video, youtube  # noqa: F401,E501
from src.yayin import calistir
from src.yayin.kanallar.story import story_kapagi_uret  # noqa: F401 — tests/test_story_native.py doğrudan çağırır
from src.yayin.koruma import TASLAK_ISLEMLERI, YONETIM_ISLEMLERI  # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    calistir()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.exception("Yayınlama esnasında kritik hata: %s", e)
        # Eğer zaten özet sonuç raporu (rapor_satirlari) Telegram'a iletildiyse,
        # ikinci bir mükerrer teknik hata kartı gönderip grubu kirletme.
        if "Bir veya daha fazla sosyal medya yayını başarısız oldu" not in str(e):
            hata_bildir.telegrama_hata_bildir("Sosyal Medya Yayını", istisna=e)
        sys.exit(1)
    finally:
        db.wal_bosalt()
