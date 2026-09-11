#!/usr/bin/env python3
"""
scripts/kaynak_dogrula.py — RSS Kaynak Sağlığı Denetimi

Emlakkulisi tek gerçek kaynağımız: 50 haberin 16'sı ondan geliyor, diğer dört
kaynak toplam 4 alakalı haber veriyor. Beslemesi ölse veya yapısı değişse fark
etmeyiz — sistem sessizce konu bankasına düşer ve "bugün haber yokmuş" sanırız.

Hürriyet vakası bu testin var oluş sebebi: "Emlak Haberleri" beslemesi 100
haber döndürüyordu ama hiçbiri emlak değildi ("Proforma Fatura Nedir",
"Şirket Nasıl Kapatılır"). Bunu ancak elle ölçünce gördük.

Denetlenenler:
  1. Besleme erişilebiliyor mu (HTTP)
  2. Ayrıştırılabiliyor mu (lxml/xml)
  3. Kaç haber döndü
  4. Kaçı içerik süzgecini geçti  ← asıl sinyal

    python scripts/kaynak_dogrula.py
    python scripts/kaynak_dogrula.py --sessiz   # Telegram'a rapor gönderme
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

import requests
from bs4 import BeautifulSoup

from src import config, fetch_news, haber_puanlama

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Bir kaynağın "sağlıklı" sayılması için besleme bu kadar haber döndürmeli.
ASGARI_HABER = 5
# Kaynak bu kadar haberde HİÇ alakalı içerik vermiyorsa yapılandırma hatalıdır.
# Hürriyet 100 haberde 0 veriyordu.
ALAKASIZ_ESIGI = 40


def kaynagi_olc(kaynak: Dict[str, Any]) -> Dict[str, Any]:
    ad = kaynak.get("ad", "?")
    url = kaynak.get("url", "")
    sonuc: Dict[str, Any] = {"ad": ad, "url": url, "durum": "?", "haber": 0, "aday": 0, "rehber": 0}

    try:
        r = requests.get(url, headers={"User-Agent": fetch_news.USER_AGENT}, timeout=20)
    except Exception as e:
        sonuc["durum"] = "ERİŞİLEMİYOR"
        sonuc["not"] = type(e).__name__
        return sonuc

    if r.status_code != 200:
        sonuc["durum"] = "HTTP HATASI"
        sonuc["not"] = str(r.status_code)
        return sonuc

    try:
        soup = fetch_news._besle_ayristir(r.content)
    except Exception as e:
        sonuc["durum"] = "AYRIŞTIRILAMIYOR"
        sonuc["not"] = type(e).__name__
        return sonuc

    items = soup.find_all("item") or soup.find_all("entry")
    sonuc["haber"] = len(items)

    for it in items:
        b = (it.find("title").text or "").strip() if it.find("title") else ""
        d = it.find("description") or it.find("summary")
        o = BeautifulSoup(d.text, "html.parser").get_text().strip() if d else ""
        deg = haber_puanlama.degerlendir(b, o, yas_saat=6)
        if deg.gecti:
            if deg.rehber_mi:
                sonuc["rehber"] += 1
            else:
                sonuc["aday"] += 1

    if sonuc["haber"] < ASGARI_HABER:
        sonuc["durum"] = "BESLEME BOŞ"
        sonuc["not"] = f"yalnızca {sonuc['haber']} haber"
    elif sonuc["aday"] + sonuc["rehber"] == 0 and sonuc["haber"] >= ALAKASIZ_ESIGI:
        sonuc["durum"] = "ALAKASIZ"
        sonuc["not"] = f"{sonuc['haber']} haberin hiçbiri süzgeci geçmiyor"
    else:
        sonuc["durum"] = "SAĞLIKLI"
    return sonuc


def main() -> int:
    ap = argparse.ArgumentParser(description="RSS kaynak sağlığı")
    ap.add_argument("--sessiz", action="store_true", help="Telegram'a rapor gönderme")
    args = ap.parse_args()

    kaynaklar = config.ayar_al("haberler.kaynaklar", [])
    sonuclar: List[Dict[str, Any]] = [kaynagi_olc(k) for k in kaynaklar]

    print(f"{'KAYNAK':24} {'DURUM':16} {'HABER':>6} {'ADAY':>5} {'REHBER':>7}")
    print("-" * 64)
    for s in sonuclar:
        print(f"{s['ad'][:24]:24} {s['durum']:16} {s['haber']:>6} {s['aday']:>5} {s['rehber']:>7}"
              + (f"  ({s['not']})" if s.get("not") else ""))

    sorunlu = [s for s in sonuclar if s["durum"] != "SAĞLIKLI"]
    toplam_aday = sum(s["aday"] for s in sonuclar)
    toplam_rehber = sum(s["rehber"] for s in sonuclar)

    print()
    print(f"toplam haber adayı: {toplam_aday} · konu adayı: {toplam_rehber}")

    # Hiçbir kaynak aday üretmiyorsa haber kolu tamamen ölmüş demektir.
    haber_kolu_olu = toplam_aday == 0 and toplam_rehber == 0

    if not args.sessiz and (sorunlu or haber_kolu_olu):
        satirlar = [f"{'❌' if s['durum'] != 'SAĞLIKLI' else '✅'} <b>{s['ad']}</b> — "
                    f"{s['durum']}{' (' + s['not'] + ')' if s.get('not') else ''}"
                    for s in sonuclar]
        basligi = "📡 <b>KAYNAK SAĞLIĞI</b>"
        if haber_kolu_olu:
            basligi += "  ⚠️ HABER KOLU ÖLÜ"
        try:
            from src import telegram_bot
            telegram_bot.mesaj_gonder(
                basligi + "\n\n" + "\n".join(satirlar)
                + f"\n\nToplam haber adayı: {toplam_aday}, konu adayı: {toplam_rehber}"
            )
        except Exception as e:
            log.warning("Telegram raporu gönderilemedi: %s", e)

    if haber_kolu_olu:
        print("\n⚠️ Hiçbir kaynak aday üretmiyor — haber kolu ölü.")
        return 1
    if sorunlu:
        print(f"\n{len(sorunlu)} kaynakta sorun var.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
