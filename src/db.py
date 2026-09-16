"""
db.py — EDM Sosyal Medya Botu SQLite Veritabanı Yöneticisi
Haberleri, ilanları, onay kuyruğunu ve yayınlanan içerikleri yönetir.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from . import config

log = logging.getLogger(__name__)

DB_YOLU = config.yol_al("data/edm.db")


@contextmanager
def _baglanti_al() -> Iterator[sqlite3.Connection]:
    DB_YOLU.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_YOLU, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def wal_bosalt() -> None:
    """WAL dosyasındaki değişiklikleri ana veritabanına yazar (git commit öncesi zorunludur)."""
    try:
        with sqlite3.connect(DB_YOLU, timeout=30) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception as e:
        log.warning("WAL boşaltılamadı: %s", e)


def tablolari_olustur() -> None:
    """Veritabanı tablolarını yoksa oluşturur ve eksik sütunları göç ettirir."""
    with _baglanti_al() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS haberler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kaynak TEXT NOT NULL,
            orijinal_baslik TEXT NOT NULL,
            orijinal_url TEXT UNIQUE NOT NULL,
            orijinal_ozet TEXT,
            makale_metni TEXT,
            yayin_tarihi TEXT,
            eklenme_tarihi TEXT NOT NULL,
            onem_puani INTEGER DEFAULT 0,
            kategori TEXT,
            manset TEXT,
            detay_metni TEXT,
            ig_caption TEXT,
            threads_metin TEXT,
            gorsel_url TEXT,
            slayt_yollari TEXT,
            slayt_urlleri TEXT,
            video_yolu TEXT,
            durum TEXT DEFAULT 'yeni',
            yayin_zamani TEXT,
            instagram_post_id TEXT,
            threads_post_id TEXT,
            youtube_video_id TEXT,
            tiktok_publish_id TEXT,
            hatirlatma_sayisi INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS ilanlar (
            id TEXT PRIMARY KEY,
            baslik TEXT NOT NULL,
            fiyat REAL,
            para_birimi TEXT DEFAULT 'TRY',
            islem TEXT,
            kategori TEXT,
            tip TEXT,
            ilce TEXT,
            mahalle TEXT,
            m2 REAL,
            oda TEXT,
            kaynak_url TEXT,
            gorseller_json TEXT,
            ozellikler_json TEXT,
            danisman TEXT,
            durum TEXT DEFAULT 'aktif',
            son_paylasim_tarihi TEXT,
            paylasim_sayisi INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS onay_istekleri (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tur TEXT NOT NULL,
            referans_id TEXT NOT NULL,
            telegram_mesaj_id INTEGER,
            telegram_chat_id INTEGER,
            durum TEXT DEFAULT 'bekliyor',
            olusturma_tarihi TEXT NOT NULL,
            yanit_tarihi TEXT
        );

        CREATE TABLE IF NOT EXISTS ayarlar (
            anahtar TEXT PRIMARY KEY,
            deger TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_haber_durum ON haberler(durum);
        CREATE INDEX IF NOT EXISTS idx_haber_url ON haberler(orijinal_url);
        CREATE INDEX IF NOT EXISTS idx_ilan_durum ON ilanlar(durum);
        """)

        # Dinamik şema göçü: Git geçmişindeki eski SQLite dosyaları da yeni
        # site kuyruğundan gelen alanları kaybetmeden kullanabilsin.
        try:
            cursor = conn.execute("PRAGMA table_info(haberler)")
            kolonlar = [row["name"] for row in cursor.fetchall()]
            if "makale_metni" not in kolonlar:
                conn.execute("ALTER TABLE haberler ADD COLUMN makale_metni TEXT")
            if "hatirlatma_sayisi" not in kolonlar:
                conn.execute("ALTER TABLE haberler ADD COLUMN hatirlatma_sayisi INTEGER DEFAULT 0")
            ilan_kolonlari = [row["name"] for row in conn.execute("PRAGMA table_info(ilanlar)").fetchall()]
            if "kategori" not in ilan_kolonlari:
                conn.execute("ALTER TABLE ilanlar ADD COLUMN kategori TEXT")
            if "ozellikler_json" not in ilan_kolonlari:
                conn.execute("ALTER TABLE ilanlar ADD COLUMN ozellikler_json TEXT")
        except Exception as e:
            log.warning("Şema göçü hatası: %s", e)

        conn.commit()


# --- AYARLAR VE SAYAÇ İŞLEMLERİ ---


def ayar_oku(anahtar: str, varsayilan: Any = None) -> Any:
    """ayarlar tablosundan bir anahtarın değerini okur."""
    with _baglanti_al() as conn:
        satir = conn.execute("SELECT deger FROM ayarlar WHERE anahtar = ?", (anahtar,)).fetchone()
        return satir["deger"] if satir else varsayilan


def ayar_yaz(anahtar: str, deger: Any) -> None:
    """ayarlar tablosuna anahtar-değer kaydeder veya günceller."""
    with _baglanti_al() as conn:
        conn.execute(
            "INSERT INTO ayarlar (anahtar, deger) VALUES (?, ?) "
            "ON CONFLICT(anahtar) DO UPDATE SET deger = excluded.deger",
            (anahtar, str(deger)),
        )
        conn.commit()


# --- HABER İŞLEMLERİ ---


def haber_ekle_mi(orijinal_url: str) -> bool:
    """Haber veritabanında daha önce kaydedilmiş mi kontrol eder."""
    with _baglanti_al() as conn:
        row = conn.execute(
            "SELECT id FROM haberler WHERE orijinal_url = ?", (orijinal_url,)
        ).fetchone()
        return row is not None


def haber_kaydet(
    kaynak: str,
    orijinal_baslik: str,
    orijinal_url: str,
    orijinal_ozet: str = "",
    yayin_tarihi: str = "",
    kategori: str = "emlak",
    onem_puani: int = 0,
    makale_metni: str = "",
) -> int:
    """Yeni bir haber ekler, eklenen haberin id'sini döner."""
    simdi = datetime.now(timezone.utc).isoformat()
    with _baglanti_al() as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO haberler 
            (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet, makale_metni, yayin_tarihi, eklenme_tarihi, kategori, onem_puani)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                kaynak,
                orijinal_baslik,
                orijinal_url,
                orijinal_ozet,
                makale_metni,
                yayin_tarihi,
                simdi,
                kategori,
                onem_puani,
            ),
        )
        conn.commit()
        return cursor.lastrowid or 0


def eski_kayitlari_temizle(gun: int = 14) -> int:
    """
    Yayınlanmamış (yeni/reddedildi) ve 'gun' günden eski haber kayıtlarını temizler.
    'yayinlandi' durumundaki hiçbir kayıt silinmez.
    Silinen kayıt adedini döner.
    """
    esik = (datetime.now(timezone.utc) - timedelta(days=gun)).isoformat()
    with _baglanti_al() as conn:
        cursor = conn.execute(
            "DELETE FROM haberler WHERE durum != 'yayinlandi' AND eklenme_tarihi < ?",
            (esik,)
        )
        conn.execute(
            "DELETE FROM onay_istekleri WHERE olusturma_tarihi < ?",
            (esik,)
        )
        conn.commit()
        silinen = cursor.rowcount
        if silinen > 0:
            log.info("Veritabanı temizliği: %d adet eski kayıt silindi.", silinen)
        return silinen


def haber_guncelle(haber_id: int, **kwargs: Any) -> None:
    """Belirtilen haberin alanlarını günceller."""
    if not kwargs:
        return
    set_cumlesi = ", ".join(f"{k} = ?" for k in kwargs.keys())
    degerler = list(kwargs.values()) + [haber_id]
    with _baglanti_al() as conn:
        conn.execute(f"UPDATE haberler SET {set_cumlesi} WHERE id = ?", degerler)
        conn.commit()


def haber_getir(haber_id: int) -> Optional[Dict[str, Any]]:
    with _baglanti_al() as conn:
        row = conn.execute(
            "SELECT * FROM haberler WHERE id = ?", (haber_id,)
        ).fetchone()
        return dict(row) if row else None


def bekleyen_haberleri_getir(limit: int = 5) -> List[Dict[str, Any]]:
    with _baglanti_al() as conn:
        rows = conn.execute(
            "SELECT * FROM haberler WHERE durum = 'yeni' ORDER BY onem_puani DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def onay_bekleyen_haberleri_getir(limit: int = 5) -> List[Dict[str, Any]]:
    """Telegram'a gönderilmiş ancak henüz yayınlanmamış/reddedilmemiş onay bekleyen kayıtları döner."""
    with _baglanti_al() as conn:
        rows = conn.execute(
            "SELECT * FROM haberler WHERE durum IN ('onay_bekliyor', 'ertelendi') ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def hatirlatma_arttir(haber_id: int) -> int:
    """Haberin hatırlatma sayısını 1 artırır ve güncel sayıyı döner."""
    with _baglanti_al() as conn:
        conn.execute(
            "UPDATE haberler SET hatirlatma_sayisi = COALESCE(hatirlatma_sayisi, 0) + 1 WHERE id = ?",
            (haber_id,),
        )
        conn.commit()
        satir = conn.execute("SELECT hatirlatma_sayisi FROM haberler WHERE id = ?", (haber_id,)).fetchone()
        return int(satir["hatirlatma_sayisi"]) if satir and satir["hatirlatma_sayisi"] is not None else 1


def durum_zaman_asimi_yap(haber_id: int) -> None:
    """Onay bekleyen haberi ve onay isteğini zaman aşımına uğratır."""
    simdi = datetime.now(timezone.utc).isoformat()
    with _baglanti_al() as conn:
        conn.execute("UPDATE haberler SET durum = 'zaman_asimi' WHERE id = ?", (haber_id,))
        conn.execute(
            "UPDATE onay_istekleri SET durum = 'zaman_asimi', yanit_tarihi = ? WHERE tur = 'haber' AND referans_id = ?",
            (simdi, str(haber_id)),
        )
        conn.commit()


# --- İLAN İŞLEMLERİ ---


def ilan_kaydet_veya_guncelle(ilan: Dict[str, Any]) -> None:
    with _baglanti_al() as conn:
        conn.execute(
            """
            INSERT INTO ilanlar 
            (id, baslik, fiyat, para_birimi, islem, kategori, tip, ilce, mahalle, m2, oda, kaynak_url, gorseller_json, ozellikler_json, danisman, durum)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                baslik = excluded.baslik,
                fiyat = excluded.fiyat,
                para_birimi = excluded.para_birimi,
                islem = excluded.islem,
                kategori = excluded.kategori,
                tip = excluded.tip,
                ilce = excluded.ilce,
                mahalle = excluded.mahalle,
                m2 = excluded.m2,
                oda = excluded.oda,
                kaynak_url = excluded.kaynak_url,
                gorseller_json = excluded.gorseller_json,
                ozellikler_json = excluded.ozellikler_json,
                danisman = excluded.danisman,
                durum = excluded.durum
            """,
            (
                str(ilan.get("id")),
                ilan.get("baslik", ""),
                float(ilan.get("fiyat") or 0),
                ilan.get("paraBirimi", "TRY"),
                ilan.get("islem", ""),
                ilan.get("kategori", ""),
                ilan.get("tip", ""),
                ilan.get("ilce", ""),
                ilan.get("mahalle", ""),
                float(ilan.get("m2") or 0),
                ilan.get("oda", ""),
                ilan.get("kaynakUrl", ""),
                json.dumps(ilan.get("gorseller", []), ensure_ascii=False),
                json.dumps(ilan.get("ozellikler", {}), ensure_ascii=False),
                ilan.get("danismanSlug", ""),
                ilan.get("durum", "aktif"),
            ),
        )
        conn.commit()


def aktif_ilanlari_getir(limit: int = 50) -> List[Dict[str, Any]]:
    with _baglanti_al() as conn:
        rows = conn.execute(
            "SELECT * FROM ilanlar WHERE durum = 'aktif' ORDER BY paylasim_sayisi ASC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def ilan_getir(ilan_id: str) -> Optional[Dict[str, Any]]:
    with _baglanti_al() as conn:
        row = conn.execute("SELECT * FROM ilanlar WHERE id = ?", (str(ilan_id),)).fetchone()
        return dict(row) if row else None


def ilan_paylasildi_isaretle(ilan_id: str) -> None:
    simdi = datetime.now(timezone.utc).isoformat()
    with _baglanti_al() as conn:
        conn.execute(
            """
            UPDATE ilanlar 
            SET son_paylasim_tarihi = ?, paylasim_sayisi = paylasim_sayisi + 1 
            WHERE id = ?
            """,
            (simdi, str(ilan_id)),
        )
        conn.commit()


def ilan_reddedildi_isaretle(ilan_id: str) -> None:
    """İlanı reddedildi olarak işaretler, böylece otomatik seçimde tekrar öne çıkarılmaz."""
    with _baglanti_al() as conn:
        conn.execute("UPDATE ilanlar SET durum = 'reddedildi' WHERE id = ?", (str(ilan_id),))
        conn.commit()


def onay_istegi_kaydet(
    tur: str,
    referans_id: str,
    telegram_mesaj_id: Optional[int] = None,
    telegram_chat_id: Optional[int] = None,
) -> int:
    """Telegram grubuna gönderilen onay mesajını onay_istekleri tablosuna kaydeder."""
    simdi = datetime.now(timezone.utc).isoformat()
    with _baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO onay_istekleri (tur, referans_id, telegram_mesaj_id, telegram_chat_id, durum, olusturma_tarihi)
               VALUES (?, ?, ?, ?, 'bekliyor', ?)""",
            (tur, str(referans_id), telegram_mesaj_id, telegram_chat_id, simdi),
        )
        conn.commit()
        return cur.lastrowid


def onay_istegi_sonuclandir(tur: str, referans_id: str, durum: str) -> None:
    """Onay isteğini yayınlandı, reddedildi veya yenilendi olarak sonuçlandırır."""
    simdi = datetime.now(timezone.utc).isoformat()
    with _baglanti_al() as conn:
        conn.execute(
            """UPDATE onay_istekleri SET durum = ?, yanit_tarihi = ?
               WHERE tur = ? AND referans_id = ? AND durum = 'bekliyor'""",
            (durum, simdi, tur, str(referans_id)),
        )
        conn.commit()


# Başlangıçta tabloları hazırla
tablolari_olustur()
