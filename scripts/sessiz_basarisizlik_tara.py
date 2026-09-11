#!/usr/bin/env python3
"""
scripts/sessiz_basarisizlik_tara.py — Sessiz Başarısızlık Tarayıcı

instabot'un en sık hata sınıfı: **kod başarıyla döndü ama iş yapılmadı ve
kullanıcıya hiçbir şey söylenmedi.** Testler bunu göremiyor — kod
"çalışıyor", yalnızca yanlış şeyi yapıyor.

Bu projede birebir yaşandı:
  · lxml eksikti → her RSS kaynağı `except` içinde yutuldu, tur "başarılı"
    sayıldı, üç gün hiçbir haber gelmedi
  · hazırlama işi yedi kez üst üste patladı, bildirim yoktu

Tarayıcı kodda üç deseni arar:
  1. Çıplak `except: pass` — hatayı sessizce yutar
  2. Bildirim göndermeden `return`/`return None` ile çıkan erken dallar
  3. Yakalanan istisnayı loglamayan `except` blokları

⚠️ YANLIŞ POZİTİF VERİR VE BU BİLİNÇLİDİR. Bildirim çağrılan fonksiyonun
içinde olabilir, bazı dallar bilerek sessizdir (denetim betikleri, saf
hesap fonksiyonları). Çıktı bir hata listesi DEĞİL, **incelenecek adaylar**
listesidir.

    python scripts/sessiz_basarisizlik_tara.py
    python scripts/sessiz_basarisizlik_tara.py --tum   # düşük öncelikliler dahil
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import List, NamedTuple

KOK = Path(__file__).resolve().parent.parent

# Bu fonksiyonlar "kullanıcıya haber verildi" sayılır.
BILDIRIM_ADLARI = {
    "mesaj_gonder", "telegrama_hata_bildir", "medya_grubu_gonder",
    "haber_onayina_sun", "sonucu_yaz", "uyari_basligi",
}

# Sessizliği bilinçli olan dosyalar — tarama dışı.
MUAF_DOSYALAR = {
    "sessiz_basarisizlik_tara.py",   # kendisi
    "metin_butcesi.py", "stres_testi.py", "kontakt_foy.py",  # denetim araçları
    "haber_puanlama.py", "dogrula.py",   # saf hesap, yan etkisiz
    "config.py",
}


class Bulgu(NamedTuple):
    dosya: str
    satir: int
    tur: str
    ayrinti: str
    oncelik: int   # 1 = yüksek


def _bildirim_var_mi(dugum: ast.AST) -> bool:
    for alt in ast.walk(dugum):
        if isinstance(alt, ast.Call):
            ad = ""
            if isinstance(alt.func, ast.Name):
                ad = alt.func.id
            elif isinstance(alt.func, ast.Attribute):
                ad = alt.func.attr
            if ad in BILDIRIM_ADLARI:
                return True
    return False


def _loglama_var_mi(dugum: ast.AST) -> bool:
    for alt in ast.walk(dugum):
        if isinstance(alt, ast.Call) and isinstance(alt.func, ast.Attribute):
            if alt.func.attr in ("debug", "info", "warning", "error", "exception", "critical"):
                return True
            if alt.func.attr == "print":
                return True
        if isinstance(alt, ast.Call) and isinstance(alt.func, ast.Name) and alt.func.id == "print":
            return True
    return False


def dosyayi_tara(yol: Path) -> List[Bulgu]:
    bulgular: List[Bulgu] = []
    try:
        agac = ast.parse(yol.read_text(encoding="utf-8"), filename=str(yol))
    except SyntaxError:
        return bulgular
    goreli = str(yol.relative_to(KOK))

    for dugum in ast.walk(agac):
        # --- 1 & 3: except blokları ---
        if isinstance(dugum, ast.ExceptHandler):
            sadece_pass = len(dugum.body) == 1 and isinstance(dugum.body[0], ast.Pass)
            if sadece_pass:
                bulgular.append(Bulgu(
                    goreli, dugum.lineno, "yutulan istisna",
                    "except: pass — hata tamamen kayboluyor", 1))
            elif not _loglama_var_mi(dugum) and not _bildirim_var_mi(dugum):
                bulgular.append(Bulgu(
                    goreli, dugum.lineno, "sessiz except",
                    "istisna yakalanıyor ama loglanmıyor", 2))

        # --- 2: bildirimsiz erken çıkış ---
        if isinstance(dugum, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if dugum.name.startswith("_") or dugum.name.startswith("test"):
                continue
            for alt in ast.walk(dugum):
                if not isinstance(alt, ast.Return):
                    continue
                # `return False` / `return None` / çıplak return: iş yapılmadı sinyali
                bos_donus = (
                    alt.value is None
                    or (isinstance(alt.value, ast.Constant) and alt.value.value in (None, False))
                )
                if not bos_donus:
                    continue
                # Fonksiyonun tamamında bildirim varsa sorun yok
                if _bildirim_var_mi(dugum):
                    continue
                bulgular.append(Bulgu(
                    goreli, alt.lineno, "bildirimsiz çıkış",
                    f"{dugum.name}() iş yapmadan dönüyor, bildirim yok", 2))
    return bulgular


def main() -> int:
    ap = argparse.ArgumentParser(description="Sessiz başarısızlık deseni tarayıcı")
    ap.add_argument("--tum", action="store_true", help="Düşük öncelikli bulguları da göster")
    args = ap.parse_args()

    dosyalar = [d for klasor in ("src", "scripts")
                for d in sorted((KOK / klasor).glob("*.py"))
                if d.name not in MUAF_DOSYALAR]

    tum: List[Bulgu] = []
    for d in dosyalar:
        tum.extend(dosyayi_tara(d))

    gosterilecek = tum if args.tum else [b for b in tum if b.oncelik == 1]

    print(f"{len(dosyalar)} dosya tarandı, {len(tum)} aday bulundu "
          f"({sum(1 for b in tum if b.oncelik == 1)} yüksek öncelikli)\n")

    if not gosterilecek:
        print("Yüksek öncelikli bulgu yok. Tümü için --tum kullan.")
        return 0

    for b in sorted(gosterilecek, key=lambda x: (x.oncelik, x.dosya, x.satir)):
        isaret = "‼️" if b.oncelik == 1 else "  "
        print(f"{isaret} {b.dosya}:{b.satir}  [{b.tur}]")
        print(f"     {b.ayrinti}")

    print("\n⚠️ Bunlar HATA DEĞİL, incelenecek adaylar. Yanlış pozitif beklenir:")
    print("   bildirim çağrılan fonksiyonun içinde olabilir, bazı dallar bilerek sessizdir.")
    # Bilgilendirme aracı; CI'ı kırmıyor.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
