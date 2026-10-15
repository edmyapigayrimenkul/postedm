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
from typing import Any, Dict, Iterator, List, Optional, Tuple

from . import config

log = logging.getLogger(__name__)

DB_YOLU = config.db_yolu()  # test modunda geçici kopya — bkz. config.db_yolu


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


baglanti_al = _baglanti_al


def baglan(ayarlar: Optional[Dict[str, Any]] = None) -> sqlite3.Connection:
    """Veritabanı bağlantısı açar (instabot uyumluluk köprüsü)."""
    tablolari_olustur()
    DB_YOLU.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_YOLU, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn



def wal_bosalt() -> None:
    """WAL dosyasındaki değişiklikleri ana veritabanına yazar (git commit öncesi zorunludur)."""
    conn = None
    try:
        conn = sqlite3.connect(DB_YOLU, timeout=30)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception as e:
        log.warning("WAL boşaltılamadı: %s", e)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


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

        CREATE TABLE IF NOT EXISTS icerik_metrikleri (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            haber_id INTEGER,
            platform TEXT NOT NULL,
            medya_id TEXT NOT NULL,
            reach INTEGER DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            saved INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            kayit_tarihi TEXT NOT NULL,
            ham_veri TEXT
        );

        CREATE TABLE IF NOT EXISTS hata_kayitlari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT NOT NULL,
            nerede TEXT,
            baslik TEXT,
            ne_oldu TEXT,
            neden TEXT,
            eylem TEXT,
            tanindi INTEGER DEFAULT 0,
            ham_hata TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_haber_durum ON haberler(durum);
        CREATE INDEX IF NOT EXISTS idx_haber_url ON haberler(orijinal_url);
        CREATE INDEX IF NOT EXISTS idx_ilan_durum ON ilanlar(durum);
        CREATE INDEX IF NOT EXISTS idx_metrik_haber ON icerik_metrikleri(haber_id);
        CREATE INDEX IF NOT EXISTS idx_metrik_medya ON icerik_metrikleri(medya_id);
        CREATE INDEX IF NOT EXISTS idx_onay_istekleri_ref ON onay_istekleri(referans_id, durum);
        """)

        # Dinamik şema göçü: Git geçmişindeki eski SQLite dosyaları da yeni
        # site kuyruğundan gelen alanları kaybetmeden kullanabilsin.
        try:
            cursor = conn.execute("PRAGMA table_info(haberler)")
            kolonlar = [row["name"] for row in cursor.fetchall()]
            haber_ek_kolonlar = [
                ("makale_metni", "TEXT"),
                ("hatirlatma_sayisi", "INTEGER DEFAULT 0"),
                ("threads_metin", "TEXT"),
                ("yayin_zamani", "TEXT"),
                ("instagram_post_id", "TEXT"),
                ("threads_post_id", "TEXT"),
                ("youtube_video_id", "TEXT"),
                ("tiktok_publish_id", "TEXT"),
                ("facebook_post_id", "TEXT"),
                ("twitter_tweet_id", "TEXT"),
                ("linkedin_post_id", "TEXT"),
                ("video_yolu", "TEXT"),
                ("sutun", "TEXT"),  # S1–S5, analiz için — bkz. src/sutun.py
                # Planlı yayının zamanı (ISO). Plan Worker KV'sinde; bu yalnızca hatırlatıcının
                # planı bekleyen içeriğe "onay bekliyor" kartı atmaması için (2026-09-26)
                ("planlanan_yayin", "TEXT"),
            ]
            for ad, tip in haber_ek_kolonlar:
                if ad not in kolonlar:
                    conn.execute(f"ALTER TABLE haberler ADD COLUMN {ad} {tip}")

            # Sütunu boş kayıtları doldur. INSERT'ler birçok yerde ham SQL ile
            # yapıldığı için tek tek yakalamak yerine burada tamamlanıyor.
            from . import sutun as _sutun
            for satir in conn.execute("SELECT id, kategori, kaynak FROM haberler WHERE sutun IS NULL").fetchall():
                s = _sutun.sutun_bul(satir["kategori"], satir["kaynak"])
                if s:
                    conn.execute("UPDATE haberler SET sutun = ? WHERE id = ?", (s, satir["id"]))

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
            "DELETE FROM haberler WHERE durum NOT IN ('yayinlandi', 'onay_bekliyor') AND eklenme_tarihi < ?",
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


def bayat_haberleri_ayikla(saat: int = 72) -> int:
    """72 saatten eski ve hala 'yeni' olan haberleri 'elendi' (bayat) olarak işaretler."""
    esik = (datetime.now(timezone.utc) - timedelta(hours=saat)).isoformat()
    with _baglanti_al() as conn:
        cursor = conn.execute(
            "UPDATE haberler SET durum = 'elendi' WHERE durum = 'yeni' AND eklenme_tarihi < ?",
            (esik,),
        )
        conn.commit()
        return cursor.rowcount


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
            """SELECT h.*,
                      (SELECT MAX(oi.olusturma_tarihi)
                         FROM onay_istekleri oi
                        WHERE oi.referans_id = CAST(h.id AS TEXT)
                          AND oi.durum = 'bekliyor') AS onay_istegi_tarihi
                 FROM haberler h
                WHERE h.durum IN ('onay_bekliyor', 'ertelendi')
                ORDER BY h.id DESC
                LIMIT ?""",
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


def durum_havuza_al(haber_id: int) -> None:
    """Onaylanmayan (1 günü doldurmuş) ama HAZIR içeriği havuza alır: satır silinmez, `durum='havuzda'`.

    Havuzdaki içerik aynı formatın bir sonraki turunda model çağrılmadan yeniden onaya sunulur
    (`konu_bankasi.havuzdaki_hazir_icerik` → `uretim._havuzdan_sun`). Onay isteği satırı da kapatılır."""
    simdi = datetime.now(timezone.utc).isoformat()
    with _baglanti_al() as conn:
        conn.execute("UPDATE haberler SET durum = 'havuzda' WHERE id = ?", (haber_id,))
        conn.execute(
            "UPDATE onay_istekleri SET durum = 'havuzda', yanit_tarihi = ? WHERE tur = 'haber' AND referans_id = ?",
            (simdi, str(haber_id)),
        )
        conn.commit()


# --- HATA KAYITLARI (2026-10-12) ---
# Hata günlüğü eskiden data/hata_kayitlari.jsonl'ye yazılıyordu; dosya .gitignore'da ve Actions makinesi
# iş bitince siliniyor: kayıt hiçbir zaman ertesi güne ulaşmıyordu. DB git'e commit edildiği için kalıcı olur.
# Metin ÖNCE maskelenir (src/gizlilik.py): requests istisnaları URL'deki access_token'ı taşır.
HATA_SAKLAMA_GUN = 30
HAM_HATA_AZAMI = 1500


def hata_kaydi_ekle(nerede: str, baslik: str, ne_oldu: str, neden: str, eylem: str,
                    tanindi: bool, ham_hata: str) -> int:
    """Hata kaydını DB'ye yazar; döner: kayıt kimliği. Eski (HATA_SAKLAMA_GUN gün) kayıtları siler."""
    from . import gizlilik
    simdi = datetime.now(timezone.utc)
    esik = (simdi - timedelta(days=HATA_SAKLAMA_GUN)).isoformat()
    with _baglanti_al() as conn:
        conn.execute("DELETE FROM hata_kayitlari WHERE tarih < ?", (esik,))
        cur = conn.execute(
            "INSERT INTO hata_kayitlari (tarih, nerede, baslik, ne_oldu, neden, eylem, tanindi, ham_hata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (simdi.isoformat(), gizlilik.maskele(nerede)[:120], gizlilik.maskele(baslik)[:200],
             gizlilik.maskele(ne_oldu)[:400], gizlilik.maskele(neden)[:400], str(eylem or "")[:60],
             1 if tanindi else 0, gizlilik.maskele(ham_hata)[:HAM_HATA_AZAMI]),
        )
        conn.commit()
        return int(cur.lastrowid)


def son_hata_kayitlari(saat: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
    """Son `saat` saatteki hata kayıtları (yeniden eskiye)."""
    esik = (datetime.now(timezone.utc) - timedelta(hours=saat)).isoformat()
    with _baglanti_al() as conn:
        satirlar = conn.execute(
            "SELECT * FROM hata_kayitlari WHERE tarih >= ? ORDER BY id DESC LIMIT ?", (esik, limit)
        ).fetchall()
        return [dict(s) for s in satirlar]


def son_hata_metni() -> Optional[str]:
    """En son kaydedilen ham hata metni (yoksa None)."""
    with _baglanti_al() as conn:
        s = conn.execute("SELECT tarih, nerede, baslik, ham_hata FROM hata_kayitlari ORDER BY id DESC LIMIT 1").fetchone()
    if not s:
        return None
    return f"[{s['tarih']}] {s['nerede']} -> {s['baslik']}\n\n{s['ham_hata']}"


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


def ilan_kaldirildi_isaretle(ilan_id: str) -> None:
    """İlanı yayından kaldırıldı olarak işaretler, havuza dönmez."""
    with _baglanti_al() as conn:
        conn.execute("UPDATE ilanlar SET durum = 'kaldirildi' WHERE id = ?", (str(ilan_id),))
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
    """Onay isteğini yayınlandı, reddedildi veya yenilendi olarak sonuçlandırır.

    haber ve reels aynı haberler tablosunda yaşar; onay kartında Reels seçilince
    yayın tur=reels ile çalışır ama kart tur=haber ile açılmıştır. Eskiden bu
    yüzden kayıt 'bekliyor'da kalıyordu (#221, 2026-09-23) ve hatırlatıcı
    yayınlanmış içerik için hatırlatmaya devam ediyordu.
    """
    simdi = datetime.now(timezone.utc).isoformat()
    turler = ("haber", "reels") if tur in ("haber", "reels") else (tur,)
    yer = ",".join("?" for _ in turler)
    with _baglanti_al() as conn:
        conn.execute(
            f"""UPDATE onay_istekleri SET durum = ?, yanit_tarihi = ?
                WHERE tur IN ({yer}) AND referans_id = ? AND durum = 'bekliyor'""",
            (durum, simdi, *turler, str(referans_id)),
        )
        conn.commit()


def onay_mesajlarini_getir(tur: str, referans_id: Any, sadece_bekleyen: bool = False) -> List[int]:
    """İçeriğe ait onay_istekleri tablosundaki tüm telegram_mesaj_id değerlerini döner."""
    turler = ("haber", "reels") if str(tur) in ("haber", "reels") else (str(tur),)
    yer = ",".join("?" for _ in turler)
    sorgu = (
        f"SELECT telegram_mesaj_id FROM onay_istekleri "
        f"WHERE tur IN ({yer}) AND referans_id = ? AND telegram_mesaj_id IS NOT NULL "
        f"AND durum != 'silindi'"
    )
    if sadece_bekleyen:
        sorgu += " AND durum = 'bekliyor'"
    sorgu += " ORDER BY id ASC"
    with _baglanti_al() as conn:
        rows = conn.execute(sorgu, (*turler, str(referans_id))).fetchall()
        return [int(r["telegram_mesaj_id"]) for r in rows if r["telegram_mesaj_id"]]


def onay_mesaj_silindi_isaretle(telegram_mesaj_id: int) -> None:
    """Silinen mesajı onay_istekleri tablosunda 'silindi' olarak işaretler."""
    with _baglanti_al() as conn:
        conn.execute(
            "UPDATE onay_istekleri SET durum = 'silindi' WHERE telegram_mesaj_id = ?",
            (telegram_mesaj_id,),
        )
        conn.commit()


def son_onay_istegi_mesajlarini_getir(adet: int = 1) -> List[int]:
    """Son onay isteklerine ait telegram_mesaj_id değerlerini döner."""
    with _baglanti_al() as conn:
        ref_rows = conn.execute(
            "SELECT DISTINCT tur, referans_id FROM onay_istekleri "
            "WHERE durum != 'silindi' AND telegram_mesaj_id IS NOT NULL "
            "ORDER BY id DESC LIMIT ?",
            (adet,),
        ).fetchall()
        if not ref_rows:
            return []
        tum_mids: List[int] = []
        for r in ref_rows:
            tur, ref_id = r["tur"], r["referans_id"]
            rows = conn.execute(
                "SELECT telegram_mesaj_id FROM onay_istekleri "
                "WHERE tur = ? AND referans_id = ? AND durum != 'silindi' AND telegram_mesaj_id IS NOT NULL "
                "ORDER BY id ASC",
                (tur, ref_id),
            ).fetchall()
            tum_mids.extend([int(row["telegram_mesaj_id"]) for row in rows if row["telegram_mesaj_id"]])
        return tum_mids


def onay_istegi_ertele(tur: str, referans_id: str, dakika: int = 60) -> bool:
    """
    Onay bekleyen bir içeriğin bekleme süresini belirtilen dakika kadar ileri öteler
    ve hatırlatma sayacını sıfırlar. Böylece '1 Saat Ertele' butonuna basıldığında
    hatırlatıcı bir sonraki periyoda kadar kullanıcıyı rahatsız etmez.
    """
    simdi = datetime.now(timezone.utc).isoformat()
    with _baglanti_al() as conn:
        conn.execute(
            """UPDATE onay_istekleri 
               SET olusturma_tarihi = ? 
               WHERE tur = ? AND referans_id = ? AND durum = 'bekliyor'""",
            (simdi, tur, str(referans_id)),
        )
        if tur in ("haber", "reels") and str(referans_id).isdigit():
            conn.execute(
                "UPDATE haberler SET hatirlatma_sayisi = 0 WHERE id = ?",
                (int(referans_id),),
            )
        conn.commit()
    return True


def son_onay_istegi_tarihi(referans_id: int | str) -> Optional[str]:
    """Haberin/içeriğin bekleyen en son onay isteği zamanını (ISO UTC) döner.

    Havuzdan yeniden sunulan içeriklerin bekleme süresi ilk oluşturulma gününden değil,
    Telegram'a yeniden sunuldukları andan hesaplanır."""
    with _baglanti_al() as conn:
        row = conn.execute(
            """SELECT MAX(olusturma_tarihi) AS son_tarih
                 FROM onay_istekleri
                WHERE referans_id = ? AND durum = 'bekliyor'""",
            (str(referans_id),),
        ).fetchone()
        return str(row["son_tarih"]) if row and row["son_tarih"] else None


def mesajdan_icerik_bul(mesaj_id: Optional[int] = None) -> Optional[Tuple[str, Any, Dict[str, Any]]]:
    """telegram_mesaj_id üzerinden ilgili haber/reels/ilan kaydını döner. (tur, ref_id, veri_dict)"""
    with _baglanti_al() as conn:
        if mesaj_id:
            row = conn.execute(
                "SELECT tur, referans_id FROM onay_istekleri WHERE telegram_mesaj_id = ? ORDER BY id DESC LIMIT 1",
                (mesaj_id,),
            ).fetchone()
            if row:
                tur = row["tur"]
                ref_id_str = str(row["referans_id"])
                if tur == "ilan":
                    i = conn.execute("SELECT * FROM ilanlar WHERE id = ?", (ref_id_str,)).fetchone()
                    if i:
                        return (tur, ref_id_str, dict(i))
                else:
                    ref_id = int(ref_id_str) if ref_id_str.isdigit() else ref_id_str
                    h = conn.execute("SELECT * FROM haberler WHERE id = ?", (ref_id,)).fetchone()
                    if h:
                        return (tur, ref_id, dict(h))

        # Yedek 1: son onay bekleyen haber kaydını al
        son = conn.execute(
            "SELECT * FROM haberler WHERE durum = 'onay_bekliyor' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if son:
            d_son = dict(son)
            tur = "reels" if d_son.get("kategori") == "REELS" else "haber"
            return (tur, d_son["id"], d_son)

        # Yedek 2: son onay bekleyen ilan kaydını al
        son_ilan = conn.execute(
            "SELECT * FROM ilanlar WHERE durum = 'onay_bekliyor' ORDER BY son_paylasim_tarihi DESC LIMIT 1"
        ).fetchone()
        if son_ilan:
            d_ilan = dict(son_ilan)
            return ("ilan", d_ilan["id"], d_ilan)

    return None


def askidaki_onaylari_temizle() -> int:
    """Askıda 'onay_bekliyor' durumundaki haber ve ilan onaylarını iptal eder."""
    adet = 0
    with _baglanti_al() as conn:
        c1 = conn.execute("UPDATE haberler SET durum = 'iptal' WHERE durum = 'onay_bekliyor'")
        adet += c1.rowcount
        c2 = conn.execute("UPDATE ilanlar SET durum = 'aktif' WHERE durum = 'onay_bekliyor'")
        adet += c2.rowcount
        conn.commit()
    return adet


def gunluk_yayin_ozeti() -> Dict[str, Any]:
    """Bugün yayınlanan içeriklerin ve bekleyen onayların özetini döner."""
    bugun_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _baglanti_al() as conn:
        yayinlananlar = conn.execute(
            "SELECT COUNT(*) FROM haberler WHERE durum IN ('yayinda', 'yayinlandi', 'tamamlandi') AND yayin_zamani LIKE ?",
            (f"{bugun_str}%",)
        ).fetchone()[0]
        bekleyenler = conn.execute(
            "SELECT COUNT(*) FROM haberler WHERE durum = 'onay_bekliyor'"
        ).fetchone()[0]
        toplam_haber = conn.execute("SELECT COUNT(*) FROM haberler").fetchone()[0]
        toplam_ilan = conn.execute("SELECT COUNT(*) FROM ilanlar").fetchone()[0]
    return {
        "bugun_yayinlanan": yayinlananlar,
        "bekleyen_onay": bekleyenler,
        "toplam_haber": toplam_haber,
        "toplam_ilan": toplam_ilan,
    }


# --- İÇERİK PERFORMANS METRİKLERİ (ANALİTİK VERİ TOPLAYICI) ---

def metrik_kaydet(
    haber_id: Optional[int],
    platform: str,
    medya_id: str,
    reach: int = 0,
    impressions: int = 0,
    saved: int = 0,
    shares: int = 0,
    comments: int = 0,
    likes: int = 0,
    ham_veri: Optional[Dict[str, Any]] = None,
) -> int:
    """Yayınlanmış içeriğin performans metriklerini sessizce kaydeder."""
    simdi = datetime.now(timezone.utc).isoformat()
    ham_str = json.dumps(ham_veri, ensure_ascii=False) if ham_veri else None
    with _baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO icerik_metrikleri (
                   haber_id, platform, medya_id, reach, impressions,
                   saved, shares, comments, likes, kayit_tarihi, ham_veri
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (haber_id, platform, str(medya_id), reach, impressions, saved, shares, comments, likes, simdi, ham_str)
        )
        conn.commit()
        return cur.lastrowid


def haber_metrikleri_getir(haber_id: int) -> List[Dict[str, Any]]:
    """Belirli bir haber için toplanan tüm metrik kayıtlarını döner."""
    with _baglanti_al() as conn:
        rows = conn.execute(
            "SELECT * FROM icerik_metrikleri WHERE haber_id = ? ORDER BY kayit_tarihi DESC",
            (haber_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def yayinlanmis_ve_metrik_bekleyenler(min_yas_saat: float = 24.0, max_yas_saat: float = 168.0) -> List[Dict[str, Any]]:
    """Son 24 saat ile 7 gün arasında yayınlanmış ve Instagram post ID'si olan haberleri döner."""
    simdi = datetime.now(timezone.utc)
    sonuclar = []
    with _baglanti_al() as conn:
        rows = conn.execute(
            """SELECT id, durum, yayin_zamani, instagram_post_id, threads_post_id, kategori, manset
               FROM haberler
               WHERE durum IN ('yayinda', 'yayinlandi', 'tamamlandi') AND instagram_post_id IS NOT NULL AND yayin_zamani IS NOT NULL
               ORDER BY yayin_zamani DESC"""
        ).fetchall()
        for r in rows:
            d = dict(r)
            yz = d.get("yayin_zamani")
            if not yz:
                continue
            try:
                dt = datetime.fromisoformat(yz)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                yas = (simdi - dt).total_seconds() / 3600.0
                if min_yas_saat <= yas <= max_yas_saat:
                    d["yas_saat"] = yas
                    sonuclar.append(d)
            except Exception:
                continue
    return sonuclar


# Başlangıçta tabloları hazırla
tablolari_olustur()
