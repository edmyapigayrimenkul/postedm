#!/usr/bin/env python3
"""
scripts/kanun_oku.py — Kanun metnini okuma aracı (sözlük kartı yazarları ve incelemecileri için).

Kartı yazan kişi/ajan kanun bilgisini hafızasından değil, bu aracın çıktısından almalı (kanunlar değişir:
TMK 733–734 24/12/2025'te değişti). Metin mevzuat.gov.tr'den çekilir ve 7 gün önbelleğe alınır;
ağ gerekir (önbellekte yoksa).

    python scripts/kanun_oku.py kanunlar                      # okunabilir kanunlar ve önbellek durumu
    python scripts/kanun_oku.py kanunlar --dene               # her kanunu ağdan çekmeyi dener (tertip doğrulaması)
    python scripts/kanun_oku.py madde "Türk Medeni Kanunu md. 826-830"   # maddelerin TAM metni (aralık sınırı yok)
    python scripts/kanun_oku.py ara 4721 ipotek "rehin hakkı"             # kelime geçişleri: madde no + bağlam

Çıkış kodu: 0 = tamam, 1 = en az bir madde/kanun okunamadı (çıktıda nedeni yazar).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import kanun_okuma, mevzuat  # noqa: E402


def _kanunlar(dene: bool, json_cikti: bool) -> int:
    liste = kanun_okuma.kanun_listesi()
    hatali = 0
    if dene:
        for k in liste:
            metin = mevzuat.kanun_metni(k["no"])
            k["onbellekte"] = bool(metin)
            k["denendi"] = bool(metin)
            if not metin:
                hatali += 1
                k["onerilen_tertip"] = mevzuat.tertip_kesfet(k["no"])  # KANUNLAR'daki aday tutmadı: sitede hangisi var?
    if json_cikti:
        print(json.dumps(liste, ensure_ascii=False, indent=1))
        return 1 if hatali else 0
    for k in liste:
        durum = "önbellekte" if k["onbellekte"] else "önbellekte yok"
        if dene:
            durum = "ÇEKİLDİ ✓" if k["denendi"] else "ÇEKİLEMEDİ ✗ (tertip ya da ağ)"
            if not k["denendi"]:
                oneri = k.get("onerilen_tertip")
                durum += f" → sitede çalışan tertip: {oneri} (src/mevzuat.py KANUNLAR'a yaz)" if oneri else " → hiçbir tertip (1-8) tutmadı; ağ ya da kanun numarası"
        print(f"{k['no']:>5}  {k['ad']}  [tertip {','.join(map(str, k['tertipler']))}]  {durum}")
    return 1 if hatali else 0


def _madde(atif: str, json_cikti: bool) -> int:
    okunan, bulunamayan = kanun_okuma.maddeleri_oku(atif)
    if json_cikti:
        print(json.dumps({"okunan": okunan, "bulunamayan": bulunamayan}, ensure_ascii=False, indent=1))
        return 1 if bulunamayan else 0
    for m in okunan:
        print(f"=== {m['kanun_no']} sayılı {m['kanun_adi']} · {m['etiket']} ===")
        print(m["metin"])
        if m["degisiklikler"]:
            print(f"[değişiklik tarihleri: {', '.join(m['degisiklikler'])}]")
        print(f"▶ BU MADDE BURADA BİTER. Sonraki madde: {m['sonraki']}")
        print()
    for b in bulunamayan:
        print(f"✗ OKUNAMADI: {b}", file=sys.stderr)
    return 1 if bulunamayan else 0


def _ara(no: int, kelimeler: list, baglam: int, json_cikti: bool) -> int:
    sonuc, hata = kanun_okuma.ara(no, kelimeler, baglam=baglam)
    if hata:
        print(f"✗ {hata}", file=sys.stderr)
        return 1
    if json_cikti:
        print(json.dumps(sonuc, ensure_ascii=False, indent=1))
        return 0
    for s in sonuc:
        print(f"--- \"{s['kelime']}\": {s['toplam']} geçiş" + (f" (ilk {len(s['sonuclar'])} gösteriliyor)" if s["toplam"] > len(s["sonuclar"]) else ""))
        for r in s["sonuclar"]:
            print(f"  {r['etiket']}: {r['parca']}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Kanun metnini oku (mevzuat.gov.tr, 7 gün önbellekli)")
    ap.add_argument("--json", action="store_true", help="makine okunur çıktı")
    alt = ap.add_subparsers(dest="komut", required=True)

    k = alt.add_parser("kanunlar", help="okunabilir kanunları listele")
    k.add_argument("--dene", action="store_true", help="her kanunu ağdan çekmeyi dene (tertip doğrulaması)")

    m = alt.add_parser("madde", help="atıftaki maddelerin TAM metni")
    m.add_argument("atif", help='örn: "Türk Medeni Kanunu md. 826, 827 ve 828" ya da "2942 sayılı Kanun md. 11"')

    a = alt.add_parser("ara", help="kanunda kelime ara")
    a.add_argument("kanun_no", type=int)
    a.add_argument("kelime", nargs="+")
    a.add_argument("--baglam", type=int, default=kanun_okuma.BAGLAM_VARSAYILAN, help="eşleşmenin iki yanında gösterilecek karakter")

    args = ap.parse_args(argv)
    if args.komut == "kanunlar":
        return _kanunlar(args.dene, args.json)
    if args.komut == "madde":
        return _madde(args.atif, args.json)
    return _ara(args.kanun_no, args.kelime, args.baglam, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
