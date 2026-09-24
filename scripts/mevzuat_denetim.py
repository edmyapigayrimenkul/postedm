#!/usr/bin/env python3
"""
scripts/mevzuat_denetim.py — Konu bankasını güncel kanun metnine karşı denetler.

NİYE VAR (2026-09-24): Konu bankası "kalıcı" konulardan oluşuyor ama kanunlar
değişiyor. S1-001 (önalım) brief'i "iki yıl" diyordu; TMK 733, 24/12/2025'te
7571 ile "bir yıl" olmuştu. S5-014 konut kredisine tüketici kredisinin cayma
maddesini atfediyordu. İkisi de canlıya çıktı.

Yaptığı:
  1. Her konunun brief'indeki (başlık, açı, kanca) süre ve çoğunluk ifadelerini
     atıf yapılan maddenin GÜNCEL metnine karşı denetler.
  2. Son 30 günde değişen maddelere atıf yapan konuları işaretler.
  3. Çözülemeyen / bulunamayan atıfları listeler.
Sorun varsa Telegram'a rapor gider ve iş kırmızı biter.

    python scripts/mevzuat_denetim.py            # denetle ve raporla
    python scripts/mevzuat_denetim.py --sessiz   # yalnızca konsol
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from src import konu_bankasi, mevzuat  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

YENI_DEGISIKLIK_GUN = 30


def konu_denetle(konu: dict) -> tuple[list[str], list[str]]:
    """(kritik, bilgi) döner. Kritik: brief güncel metinle çelişiyor ya da madde yeni değişti."""
    ozet = mevzuat.brief_mevzuati(konu["mevzuat"])
    kritik, bilgi = [], []
    if ozet["cozulemeyen"]:
        bilgi.append("otomatik doğrulanamayan atıf: " + "; ".join(ozet["cozulemeyen"])[:100])
    if not ozet["metin"]:
        return kritik, bilgi
    brief = " ".join(str(konu.get(k) or "") for k in ("baslik", "aci", "kanca_kalip"))
    kacak = sorted(mevzuat.sure_ifadeleri(brief) - mevzuat.sure_ifadeleri(ozet["metin"]))
    if kacak:
        kritik.append("brief'teki süre güncel metinde yok: " + ", ".join(f"{n} {b}" for n, b in kacak))
    brief_k = brief.replace("İ", "i").replace("I", "ı").lower()
    metin_k = ozet["metin"].replace("İ", "i").replace("I", "ı").lower()
    for c in mevzuat.CUNLUK_IFADELERI:
        if c in brief_k and c not in metin_k:
            kritik.append(f"brief'teki çoğunluk güncel metinde yok: {c}")
    if ozet["son_degisiklik"]:
        degisti = date.fromisoformat(ozet["son_degisiklik"])
        if degisti >= date.today() - timedelta(days=YENI_DEGISIKLIK_GUN):
            kritik.append(f"madde {degisti:%d.%m.%Y}'de değişti — brief yeniden okunmalı")
    return kritik, bilgi


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessiz", action="store_true")
    args = ap.parse_args()

    konular = konu_bankasi.havuzu_yukle()
    engelli = sorted(k["kod"] for k in konular if k.get("engel"))
    atifli = [k for k in konular if k.get("mevzuat") and not k.get("engel")]
    kritikler, bilgiler = {}, {}
    for k in atifli:
        kritik, bilgi = konu_denetle(k)
        if kritik:
            kritikler[k["kod"]] = (k["baslik"], kritik)
        if bilgi:
            bilgiler[k["kod"]] = bilgi

    satirlar = [f"{len(konular)} konu · {len(atifli)} atıflı · {len(kritikler)} kritik · "
                f"{len(bilgiler)} otomatik doğrulanamayan"]
    for kod, (baslik, sorunlar) in sorted(kritikler.items()):
        satirlar.append(f"\n⛔ {kod} — {baslik}")
        satirlar += [f"   • {s}" for s in sorunlar]
    if engelli:
        satirlar.append("\n🚫 Üretimden çıkarılmış (engel alanı, gerekçe konu bankasında): " + ", ".join(engelli))
    if bilgiler:
        satirlar.append("\nℹ️ Madde numarası olmayan ya da yönetmelik/tebliğe dayanan (elle doğrulanmalı): "
                        + ", ".join(sorted(bilgiler)))
    print("\n".join(satirlar))

    if kritikler and not args.sessiz:
        try:
            import html
            from src import telegram_bot
            telegram_bot.mesaj_gonder(
                "⚖️ <b>MEVZUAT DENETİMİ</b> — konu bankası güncel kanun metinleriyle karşılaştırıldı\n\n"
                + html.escape("\n".join(satirlar))[:3800]
            )
        except Exception as e:
            print(f"Telegram raporu gönderilemedi: {e}", file=sys.stderr)
    return 1 if kritikler else 0


if __name__ == "__main__":
    raise SystemExit(main())
