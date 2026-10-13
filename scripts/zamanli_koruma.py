#!/usr/bin/env python3
"""
scripts/zamanli_koruma.py — Zamanlanmış işlerin "bugün çalıştı mı" koruması (workflow adımı)

Hatırlatma, haber önerisi ve günlük rapor iki yerden tetiklenir: Cloudflare cron'u (asıl; Worker `repository_dispatch` yollar,
yükte `zamanli: true` ve `slot` vardır) ve GitHub `schedule` (gecikmeli yedek; 6-10 saat geç gelebilir). İkisi de çalışırsa
gruba çift hatırlatma, çift haber önerisi, çift rapor düşerdi. Bu betik aynı slotu aynı TÜRKİYE gününde bir kez çalıştırır
(hazirla.py'deki günlük tur korumasıyla aynı işaret: `ayarlar › zamanli_slot_son_gun:<slot>`).

    python scripts/zamanli_koruma.py kontrol    # bugün yapılmışsa GITHUB_OUTPUT'a atla=true yazar (sonraki adımlar `if` ile atlanır)
    python scripts/zamanli_koruma.py isaretle   # işi başarıyla bitiren workflow son adımda çağırır; başarısız tur işaretlenmez

Ortam: ZAMANLANMIS=true (schedule ya da payload.zamanli) ve ZAMANLI_SLOT. ZAMANLANMIS değilse (elle tetikleme: Telegram butonu,
workflow_dispatch) HİÇBİR ŞEY denetlenmez ve işaretlenmez: insanın isteği korumaya takılmaz, korumayı da tüketmez.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import telegram_bot

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def _zamanlanmis(env) -> bool:
    return str(env.get("ZAMANLANMIS", "")).strip().lower() == "true"


def _slot(env) -> str:
    return str(env.get("ZAMANLI_SLOT", "")).strip()


def _slot_bilinir_mi(slot: str) -> bool:
    if slot in telegram_bot.ZAMANLI_GUNLUK_SLOTLAR:
        return True
    # Bilinmeyen slot korumasız çalışır: yazım hatası işi sessizce İPTAL etmemeli, ama sessiz de kalmamalı.
    log.warning("Bilinmeyen zamanlı slot %r: koruma uygulanmıyor (bilinenler: %s).", slot, telegram_bot.ZAMANLI_GUNLUK_SLOTLAR)
    return False


def kontrol(env=os.environ) -> bool:
    """True = bu slot bugün zaten çalışmış, iş ATLANMALI."""
    if not _zamanlanmis(env):
        return False
    slot = _slot(env)
    if not slot or not _slot_bilinir_mi(slot):
        return False
    if telegram_bot.zamanli_slot_bugun_yapildi(slot):
        log.info("Zamanlanmış '%s' işi bugün zaten çalışmış; yedek tetik atlanıyor.", slot)
        return True
    return False


def isaretle(env=os.environ) -> bool:
    """Zamanlanmış işin bugün başarıyla çalıştığını kaydeder. True = işaret yazıldı."""
    if not _zamanlanmis(env):
        return False
    slot = _slot(env)
    if not slot or not _slot_bilinir_mi(slot):
        return False
    telegram_bot.zamanli_slot_isaretle(slot)
    log.info("Zamanlanmış '%s' işi bugün için işaretlendi.", slot)
    return True


def main(argv: list[str] | None = None, env=os.environ) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or argv[0] not in ("kontrol", "isaretle"):
        print("Kullanım: zamanli_koruma.py kontrol|isaretle", file=sys.stderr)
        return 2
    if argv[0] == "isaretle":
        isaretle(env)
        return 0
    atla = kontrol(env)
    cikti = env.get("GITHUB_OUTPUT")
    if cikti:
        with open(cikti, "a", encoding="utf-8") as f:
            f.write(f"atla={'true' if atla else 'false'}\n")
    print(f"atla={'true' if atla else 'false'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
