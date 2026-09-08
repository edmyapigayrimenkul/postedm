"""
db.py — EDM Sosyal Medya Botu SQLite Veritabanı Yöneticisi
Haberleri, ilanları, onay kuyruğunu ve yayınlanan içerikleri yönetir.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config

log = logging.getLogger(__name__)

DB_YOLU = config.yol_al("data/edm.db")


def _baglanti_al() -> sqlite3.Connection:
    DB_YOLU.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_YOLU)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def tablolari_olustur() -> None:
    """Veritabanı tablolarını yoksa oluşturur."""
    with _baglanti_al() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS haberler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kaynak TEXT NOT NULL,
            orijinal_baslik TEXT NOT NULL,
            orijinal_url TEXT UNIQUE NOT NULL,
            orijinal_ozet TEXT,
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
            tiktok_publish_id TEXT
        );

        CREATE TABLE IF NOT EXISTS ilanlar (
            id TEXT PRIMARY KEY,
            baslik TEXT NOT NULL,
            fiyat REAL,
            para_birimi TEXT DEFAULT 'TRY',
            islem TEXT,
            tip TEXT,
            ilce TEXT,
            mahalle TEXT,
            m2 REAL,
            oda TEXT,
            kaynak_url TEXT,
            gorseller_json TEXT,
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

        CREATE INDEX IF NOT EXISTS idx_haber_durum ON haberler(durum);
        CREATE INDEX IF NOT EXISTS idx_haber_url ON haberler(orijinal_url);
        CREATE INDEX IF NOT EXISTS idx_ilan_durum ON ilanlar(durum);
        """)
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
) -> int:
    """Yeni bir haber ekler, eklenen haberin id'sini döner."""
    simdi = datetime.now(timezone.utc).isoformat()
    with _baglanti_al() as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO haberler 
            (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet, yayin_tarihi, eklenme_tarihi, kategori, onem_puani)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                kaynak,
                orijinal_baslik,
                orijinal_url,
                orijinal_ozet,
                yayin_tarihi,
                simdi,
                kategori,
                onem_puani,
            ),
        )
        conn.commit()
        return cursor.lastrowid or 0


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


# --- İLAN İŞLEMLERİ ---


def ilan_kaydet_veya_guncelle(ilan: Dict[str, Any]) -> None:
    with _baglanti_al() as conn:
        conn.execute(
            """
            INSERT INTO ilanlar 
            (id, baslik, fiyat, para_birimi, islem, tip, ilce, mahalle, m2, oda, kaynak_url, gorseller_json, danisman, durum)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                baslik = excluded.baslik,
                fiyat = excluded.fiyat,
                gorseller_json = excluded.gorseller_json,
                durum = excluded.durum
            """,
            (
                str(ilan.get("id")),
                ilan.get("baslik", ""),
                float(ilan.get("fiyat", 0)),
                ilan.get("paraBirimi", "TRY"),
                ilan.get("islem", ""),
                ilan.get("tip", ""),
                ilan.get("ilce", ""),
                ilan.get("mahalle", ""),
                float(ilan.get("m2", 0)),
                ilan.get("oda", ""),
                ilan.get("kaynakUrl", ""),
                json.dumps(ilan.get("gorseller", []), ensure_ascii=False),
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


# Başlangıçta tabloları hazırla
tablolari_olustur()
