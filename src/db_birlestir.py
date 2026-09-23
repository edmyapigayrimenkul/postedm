"""
src/db_birlestir.py — data/edm.db için satır düzeyinde üç yönlü birleştirme.

NİYE VAR (2026-09-23 denetimi): Veritabanı git'te duruyor ve birden çok yazar var
(hazirla, yayinla, site kuyruğu, hatırlatıcı ve yerel çalıştırmalar). Push
çakıştığında db_senkron bütün dosyayı "--theirs" ile seçiyordu: son yazan, öbür
tarafın TÜM değişikliklerini siliyordu. Geçmişte 143 DB commit'inin 6'sında
kayıt geri gitti — biri 28 haber kaydını birden sildi, ikisi yayınlanmış bir
içeriği yeniden "yayınlanmamış" yaptı.

Yaklaşım git'in metin birleştirmesiyle aynı, satır = tablo satırı:
    sonuç = A + (B'nin tabandan bu yana yaptığı değişiklikler)
Taban (O) iki tarafın ortak atası. A'nın tabandan farkı zaten A'da; B'nin farkı
(ekleme / sütun bazında güncelleme / silme) A'nın üstüne uygulanır.

Çakışma kuralları:
  · aynı satırın aynı sütununu iki taraf farklı değiştirdiyse B kazanır — ama
    `durum` için 'yayinlandi' her zaman kazanır, *_post_id / *_video_id /
    *_publish_id sütunlarında dolu değer boşa yenilmez. Gerçekte yayında olan
    bir içerik hiçbir birleştirmede "yayınlanmamış"a dönmez.
  · iki taraf aynı birincil anahtarla FARKLI satır eklediyse (iki eşzamanlı
    çalıştırma da #205'i üretti) B'nin satırı yeni numara alır; haberler için
    ona bağlı onay/konu/metrik satırları da taşınır. Rapor bunu bildirir.
  · B'nin sildiği satırı A güncellediyse silme kazanır (temizlik işleri).

Git birleştirme sürücüsü olarak da çalışır (bkz. scripts/git_kancalari_kur.py):
    python scripts/db_birlestir.py %O %A %B   → sonuç %A'ya yazılır
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

YAYINDA = "yayinlandi"
KIMLIK_SONEKLERI = ("_post_id", "_video_id", "_publish_id")

# haberler.id'ye başvuran sütunlar: (tablo, sütun, ek koşul)
HABER_BASVURULARI: List[Tuple[str, str, str]] = [
    ("onay_istekleri", "referans_id", "tur IN ('haber', 'reels')"),
    ("konu_gecmisi", "haber_id", "1=1"),
    ("icerik_metrikleri", "haber_id", "1=1"),
]


@dataclass
class Rapor:
    eklenen: int = 0
    guncellenen: int = 0
    silinen: int = 0
    cakisma: List[str] = field(default_factory=list)
    yeniden_numaralanan: Dict[str, Dict[Any, Any]] = field(default_factory=dict)

    def ozet(self) -> str:
        parca = [f"+{self.eklenen} ekleme", f"~{self.guncellenen} güncelleme", f"-{self.silinen} silme"]
        if self.cakisma:
            parca.append(f"{len(self.cakisma)} sütun çakışması")
        for tablo, harita in self.yeniden_numaralanan.items():
            parca.append(f"{tablo}: " + ", ".join(f"#{e}→#{y}" for e, y in harita.items()))
        return " · ".join(parca)


def _tablolar(conn: sqlite3.Connection) -> Dict[str, str]:
    return {
        ad: sql
        for ad, sql in conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    }


def _sutunlar(conn: sqlite3.Connection, tablo: str) -> List[Tuple[str, str, int]]:
    """(ad, tür, pk_sırası) listesi."""
    return [(r[1], r[2], r[5]) for r in conn.execute(f'PRAGMA table_info("{tablo}")')]


def _satirlar(conn: Optional[sqlite3.Connection], tablo: str, pk: List[str]) -> Dict[tuple, Dict[str, Any]]:
    if conn is None or tablo not in _tablolar(conn):
        return {}
    conn.row_factory = sqlite3.Row
    sonuc = {}
    for r in conn.execute(f'SELECT * FROM "{tablo}"'):
        d = dict(r)
        sonuc[tuple(d[k] for k in pk)] = d
    return sonuc


def _sutun_coz(sutun: str, a_deger: Any, b_deger: Any) -> Any:
    """Aynı sütunu iki taraf farklı değiştirdi: hangisi kalır."""
    if sutun == "durum" and YAYINDA in (a_deger, b_deger):
        return YAYINDA
    if sutun.endswith(KIMLIK_SONEKLERI):
        return b_deger if b_deger else a_deger
    return b_deger


def _yeni_numara(conn: sqlite3.Connection, tablo: str, pk: str, b_satirlari: Dict[tuple, Dict[str, Any]]) -> int:
    en_buyuk = conn.execute(f'SELECT COALESCE(MAX("{pk}"), 0) FROM "{tablo}"').fetchone()[0] or 0
    b_max = max((k[0] for k in b_satirlari if isinstance(k[0], int)), default=0)
    return max(int(en_buyuk), int(b_max)) + 1


def birlestir(taban: Optional[Path], a: Path, b: Path, cikti: Path) -> Rapor:
    """taban→b değişikliklerini a'nın üstüne uygulayıp sonucu cikti'ya yazar."""
    rapor = Rapor()
    with tempfile.TemporaryDirectory() as gecici:
        hedef = Path(gecici) / "sonuc.db"
        shutil.copy2(a, hedef)
        c_out = sqlite3.connect(hedef)
        c_out.row_factory = sqlite3.Row
        c_o = sqlite3.connect(taban) if taban and Path(taban).exists() and Path(taban).stat().st_size else None
        c_b = sqlite3.connect(b)
        try:
            _uygula(c_o, c_b, c_out, rapor)
            c_out.commit()
        finally:
            for c in (c_out, c_o, c_b):
                if c is not None:
                    c.close()
        shutil.copy2(hedef, cikti)
    return rapor


def _uygula(c_o, c_b, c_out, rapor: Rapor) -> None:
    out_tablolar = _tablolar(c_out)
    b_tablolar = _tablolar(c_b)

    # Şema: B'de olup A'da olmayan tablo ve sütunlar önce eklenir
    # (kod bir tarafta migrasyon yapmış olabilir).
    for tablo, sql in b_tablolar.items():
        if tablo not in out_tablolar:
            c_out.execute(sql)
            out_tablolar[tablo] = sql
        out_sutun = {s[0] for s in _sutunlar(c_out, tablo)}
        for ad, tur, _ in _sutunlar(c_b, tablo):
            if ad not in out_sutun:
                c_out.execute(f'ALTER TABLE "{tablo}" ADD COLUMN "{ad}" {tur or ""}')

    # haberler önce: yeniden numaralanan haber kimlikleri bağlı tablolara taşınır
    sira = sorted(b_tablolar, key=lambda t: (t != "haberler", t))
    haber_haritasi: Dict[Any, Any] = {}
    for tablo in sira:
        _tablo_uygula(tablo, c_o, c_b, c_out, rapor, haber_haritasi)

    # AUTOINCREMENT sayacı hiçbir tarafın gerisinde kalmasın
    try:
        for tablo in out_tablolar:
            pk = [s for s in _sutunlar(c_out, tablo) if s[2]]
            if len(pk) == 1 and "INT" in (pk[0][1] or "").upper():
                en_buyuk = c_out.execute(f'SELECT MAX("{pk[0][0]}") FROM "{tablo}"').fetchone()[0]
                if en_buyuk is not None:
                    c_out.execute("UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name = ?", (en_buyuk, tablo))
    except sqlite3.OperationalError:
        pass  # sqlite_sequence yoksa AUTOINCREMENT kullanan tablo da yok


def _tablo_uygula(tablo, c_o, c_b, c_out, rapor: Rapor, haber_haritasi: Dict[Any, Any]) -> None:
    sutunlar = _sutunlar(c_b, tablo)
    pk = [ad for ad, _, sira in sorted(sutunlar, key=lambda s: s[2]) if sira]
    if not pk:
        log.warning("db_birlestir: '%s' tablosunda birincil anahtar yok, atlandı", tablo)
        return

    O = _satirlar(c_o, tablo, pk)
    B = _satirlar(c_b, tablo, pk)
    A = _satirlar(c_out, tablo, pk)
    kosul = " AND ".join(f'"{k}" = ?' for k in pk)

    # Bu tabloda B tarafında yeniden numaralanan haberlere başvuran satırlar
    basvuru = next(((s, k) for t, s, k in HABER_BASVURULARI if t == tablo), None)

    for anahtar, b_satir in B.items():
        b_satir = dict(b_satir)
        if basvuru and haber_haritasi:
            sutun, _ = basvuru
            eski = b_satir.get(sutun)
            for aday in (eski, str(eski) if eski is not None else None):
                if aday in haber_haritasi:
                    b_satir[sutun] = type(eski)(haber_haritasi[aday]) if eski is not None else eski
                    break

        o_satir = O.get(anahtar)
        a_satir = A.get(anahtar)

        if o_satir is None:
            # B'de yeni satır
            if a_satir is None:
                _ekle(c_out, tablo, b_satir)
                rapor.eklenen += 1
            elif _esit(a_satir, b_satir):
                continue
            elif len(pk) == 1 and isinstance(anahtar[0], int):
                # İki taraf aynı numarayla farklı satır üretti → B'ninki yeni numara alır
                yeni = _yeni_numara(c_out, tablo, pk[0], B)
                rapor.yeniden_numaralanan.setdefault(tablo, {})[anahtar[0]] = yeni
                if tablo == "haberler":
                    haber_haritasi[anahtar[0]] = yeni
                    haber_haritasi[str(anahtar[0])] = yeni
                b_satir[pk[0]] = yeni
                _ekle(c_out, tablo, b_satir)
                rapor.eklenen += 1
                log.warning("db_birlestir: %s #%s iki tarafta da üretildi; B'ninki #%s oldu", tablo, anahtar[0], yeni)
            else:
                # Metin anahtar (ör. ayarlar): B kazanır
                _guncelle(c_out, tablo, pk, kosul, anahtar, {k: v for k, v in b_satir.items() if k not in pk})
                rapor.guncellenen += 1
            continue

        # Tabanda vardı: B'nin sütun bazında değişiklikleri
        degisen = {k: v for k, v in b_satir.items() if k not in pk and o_satir.get(k) != v}
        if not degisen:
            continue
        if a_satir is None:
            # A silmiş, B güncellemiş → silme kazanır
            continue
        uygulanacak = {}
        for k, b_deger in degisen.items():
            a_deger = a_satir.get(k)
            if a_deger == b_deger:
                continue
            if a_deger != o_satir.get(k):
                cozum = _sutun_coz(k, a_deger, b_deger)
                rapor.cakisma.append(f"{tablo}{list(anahtar)}.{k}")
                if cozum != a_deger:
                    uygulanacak[k] = cozum
            else:
                uygulanacak[k] = b_deger
        if uygulanacak:
            _guncelle(c_out, tablo, pk, kosul, anahtar, uygulanacak)
            rapor.guncellenen += 1

    # B'nin sildikleri
    for anahtar in O.keys() - B.keys():
        if anahtar in A:
            if tablo == "haberler" and A[anahtar].get("durum") == YAYINDA and O[anahtar].get("durum") != YAYINDA:
                continue  # B'nin haberi olmadan yayına girmiş kaydı silme
            c_out.execute(f'DELETE FROM "{tablo}" WHERE {kosul}', anahtar)
            rapor.silinen += 1


def _esit(x: Dict[str, Any], y: Dict[str, Any]) -> bool:
    return all(x.get(k) == y.get(k) for k in set(x) | set(y))


def _ekle(conn, tablo, satir: Dict[str, Any]) -> None:
    mevcut = {s[0] for s in _sutunlar(conn, tablo)}
    satir = {k: v for k, v in satir.items() if k in mevcut}
    sutunlar = ", ".join(f'"{k}"' for k in satir)
    yer = ", ".join("?" for _ in satir)
    conn.execute(f'INSERT INTO "{tablo}" ({sutunlar}) VALUES ({yer})', list(satir.values()))


def _guncelle(conn, tablo, pk, kosul, anahtar, degerler: Dict[str, Any]) -> None:
    if not degerler:
        return
    atama = ", ".join(f'"{k}" = ?' for k in degerler)
    conn.execute(f'UPDATE "{tablo}" SET {atama} WHERE {kosul}', [*degerler.values(), *anahtar])
