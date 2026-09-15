#!/usr/bin/env python3
"""
scripts/gunluk_rapor.py — Sabah Durum Raporu

instabot dersi: bu sistemin en sık hata sınıfı "kod çalıştı ama iş yapılmadı
ve kimse bilmedi". Günlük rapor bunun panzehiri — her sabah dün ne olduğunu
yazıyor, sessiz bozulmalar birikmeden görünür oluyor.

Ayrıca ÖLÇÜM ALTYAPISININ başlangıcı: ICERIK-SISTEMI.md §9'daki kaydetme ve
paylaşım oranları buraya eklenecek. Şu an yalnızca üretim tarafını ölçüyor.

    python scripts/gunluk_rapor.py
    python scripts/gunluk_rapor.py --sessiz   # yalnızca ekrana yaz
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import config, db, konu_bankasi

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _sayi(conn: sqlite3.Connection, sorgu: str, *param) -> int:
    try:
        return conn.execute(sorgu, param).fetchone()[0]
    except sqlite3.Error:
        return 0


def rapor_uret() -> tuple[str, bool]:
    """Raporu ve 'müdahale gerekiyor mu' bayrağını döner."""
    dun = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    satirlar: List[str] = []
    uyari = False

    with db._baglanti_al() as conn:
        # --- Üretim ---
        yeni_haber = _sayi(conn, "SELECT COUNT(*) FROM haberler WHERE eklenme_tarihi > ?", dun)
        yayinlanan = _sayi(conn, "SELECT COUNT(*) FROM haberler WHERE durum='yayinlandi'")
        bekleyen = _sayi(conn, "SELECT COUNT(*) FROM haberler WHERE durum='onay_bekliyor'")
        havuz = _sayi(conn, "SELECT COUNT(*) FROM haberler WHERE durum='yeni'")

        elenen = _sayi(conn, "SELECT COUNT(*) FROM haberler WHERE durum='elendi'")

        satirlar.append("<b>ÜRETİM</b>")
        satirlar.append(f"  Dün taranan haber: {yeni_haber}")
        satirlar.append(f"  Toplam yayınlanan: {yayinlanan}")
        satirlar.append(f"  Onay bekleyen    : {bekleyen}")
        satirlar.append(f"  Havuzda bekleyen : {havuz}")
        satirlar.append(f"  Triyajda elenen  : {elenen}")

        # Havuz drene olmuyorsa boşa LLM çağrısı ve bayat içerik riski doğar.
        # 11 Eyl 2026: elenen haber işaretlenmiyordu, aynı 6 kayıt her gün
        # yeniden triyaja giriyordu.
        if havuz > 40:
            uyari = True
            satirlar.append(f"  ⚠️ Havuz {havuz} kayda çıktı — drenaj çalışmıyor olabilir")

        # Onay beklemede takılı kalan iş var mı — instabot'ta unutulan turlar oldu
        if bekleyen >= 3:
            uyari = True
            satirlar.append(f"  ⚠️ {bekleyen} içerik onay bekliyor, birikme var")

        # --- Yayınlanmış içeriğin platform dağılımı ---
        ig = _sayi(conn, "SELECT COUNT(*) FROM haberler WHERE instagram_post_id IS NOT NULL")
        th = _sayi(conn, "SELECT COUNT(*) FROM haberler WHERE threads_post_id IS NOT NULL")
        if ig or th:
            satirlar.append(f"  Instagram {ig} · Threads {th}")

    # --- Konu bankası ---
    ozet = konu_bankasi.durum_ozeti()
    satirlar.append("")
    satirlar.append("<b>KONU BANKASI</b>")
    satirlar.append(f"  Bakir konu: {ozet['bakir']}/{ozet['toplam']} (~{ozet['kalan_hafta']} hafta)")
    satirlar.append(f"  Dağılım   : {ozet['bakir_sutun_dagilimi']}")

    # Takvim tükenmeden önce uyar: yeni konu yazmak zaman ister
    if ozet["kalan_hafta"] < 3:
        uyari = True
        satirlar.append("  ⚠️ Konu bankası 3 haftanın altında — yeni konu eklenmeli")

    adaylar = konu_bankasi.bekleyen_adaylar()
    if adaylar:
        satirlar.append(f"  Onay bekleyen konu adayı: {len(adaylar)}")
        for a in adaylar[:3]:
            satirlar.append(f"    · [{a.get('sutun')}] {(a.get('baslik') or '')[:44]}")

    # --- Son 24 Saatin Hata Özeti (instabot hafızası: yazılıp okunmayan kayıt kalmasın) ---
    from src import hata_bildir
    son_hatalar = hata_bildir.son_hatalari_ozetle(saat=24)
    satirlar.append("")
    satirlar.append("<b>SİSTEM SAĞLIĞI & TEKNİK GÜNLÜK</b>")
    if son_hatalar:
        uyari = True
        satirlar.append(f"  ⚠️ Son 24 saatte {len(son_hatalar)} teknik hata kaydedildi:")
        for h in son_hatalar[:3]:
            satirlar.append(f"    · [{h.get('nerede', 'İşlem')}] {h.get('ne_oldu', '')[:50]}")
    else:
        satirlar.append("  Son 24 saatte teknik hata kaydedilmedi ✓")

    return "\n".join(satirlar), uyari


def main() -> int:
    ap = argparse.ArgumentParser(description="EDM günlük durum raporu")
    ap.add_argument("--sessiz", action="store_true", help="Telegram'a gönderme")
    args = ap.parse_args()

    govde, uyari = rapor_uret()
    baslik = "☀️ <b>GÜNLÜK RAPOR</b>" + ("  ⚠️" if uyari else "")
    rapor = f"{baslik}\n\n{govde}"

    print(rapor.replace("<b>", "").replace("</b>", ""))

    if not args.sessiz:
        try:
            from src import telegram_bot
            telegram_bot.mesaj_gonder(rapor)
            # Kendini onaran komut menüsü: her sabah açılır menüyü Telegram'a tazeler
            telegram_bot.komut_menusu_kaydet()
        except Exception as e:
            log.warning("Telegram raporu gönderilemedi: %s", e)

    # Rapor uyarı içerse bile job yeşil kalır: bu bir bilgilendirme,
    # başarısızlık değil. Kırmızı yapmak "her sabah kırmızı" körlüğü yaratır.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
