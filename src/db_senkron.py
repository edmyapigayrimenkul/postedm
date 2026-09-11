"""
db_senkron.py — Veritabanını (data/edm.db) GitHub'a güvenli commit+push eden modül.
Instabot mimarisinden uyarlanmıştır.

İkili SQLite dosyalarındaki çakışmaları (--theirs ile) otomatik çözer,
WAL dosyalarını ana db'ye boşaltır ve runner'ların detached HEAD'de kilitlenmesini engeller.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from . import db

log = logging.getLogger(__name__)

DAL = "main"
BIZIM_KAZANIR = ("data/edm.db",)

_DEGISIKLIK_YOK_KALIPLARI = (
    "nothing to commit",
    "nothing added to commit",
    "no changes added to commit",
    "working tree clean",
)


def _calistir(*komut: str, saniye: int = 60) -> Tuple[bool, str]:
    try:
        s = subprocess.run(komut, capture_output=True, text=True, timeout=saniye)
        return s.returncode == 0, (s.stderr or s.stdout).strip()
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _push() -> Tuple[bool, str]:
    """Açık refspec ile iter: HEAD:main (detached HEAD durumunda da çalışır)."""
    return _calistir("git", "push", "origin", f"HEAD:{DAL}", saniye=120)


def _birlestir() -> None:
    """
    Uzaktaki değişikliği üstümüze alır, ikili db çakışmasını çözer.
    İkili SQLite dosyasında birleştirme yapılamayacağı için taze tur (theirs) seçilir.
    """
    _calistir("git", "fetch", "origin", DAL, saniye=90)
    _calistir("git", "stash", "--include-untracked")

    tamam, _ = _calistir("git", "rebase", f"origin/{DAL}")
    if tamam:
        _calistir("git", "stash", "pop")
        return

    # Rebase sırasında "theirs" = yeniden uygulanan commit (yani bizim taze db'miz)
    for dosya in BIZIM_KAZANIR:
        _calistir("git", "checkout", "--theirs", "--", dosya)
        _calistir("git", "add", dosya)

    tamam, cikti = _calistir("git", "-c", "core.editor=true", "rebase", "--continue")
    if not tamam:
        log.warning("db_senkron: rebase çözülemedi, iptal ediliyor: %s", cikti[:200])
        _calistir("git", "rebase", "--abort")
    _calistir("git", "stash", "pop")


def _degisiklik_yok(cikti: str) -> bool:
    metin = (cikti or "").lower()
    return any(k in metin for k in _DEGISIKLIK_YOK_KALIPLARI)


def hemen_kaydet(mesaj: str, ek_yollar: Optional[List[str]] = None) -> bool:
    """
    data/edm.db'yi commit edip push eder.
    GitHub Actions runner'larında ve yerelde güvenle çalışır.
    """
    _calistir("git", "config", "user.name", "github-actions[bot]")
    _calistir("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")

    # 1. WAL dosyasını ana db'ye göm
    db.wal_bosalt()

    # 2. Dosyaları ekle
    yollar = ["data/edm.db"] + list(ek_yollar or [])
    tamam, _ = _calistir("git", "add", *yollar)
    if not tamam:
        log.warning("db_senkron: git add başarısız")
        return False

    # 3. Commit
    tamam, cikti = _calistir("git", "commit", "-m", mesaj)
    if not tamam and not _degisiklik_yok(cikti):
        log.warning("db_senkron: commit başarısız: %s", cikti[:200])
        return False

    # 4. Push (Çakışma varsa rebase ve tekrar push)
    tamam, cikti = _push()
    if not tamam:
        log.info("db_senkron: doğrudan push başarısız, rebase ile birleştiriliyor...")
        _birlestir()
        tamam, cikti = _push()

    if tamam:
        log.info("db_senkron: veritabanı başarıyla push edildi")
    else:
        log.warning("db_senkron: veritabanı push edilemedi: %s", cikti[:200])
    return tamam


def uzaktan_tazele() -> bool:
    """Uzaktaki en güncel veritabanını çeker."""
    _calistir("git", "stash", "push", "--", "data/edm.db")
    tamam, cikti = _calistir("git", "fetch", "origin", "main", saniye=90)
    if not tamam:
        log.warning("db_senkron: fetch başarısız: %s", cikti[:200])
        return False
    tamam, cikti = _calistir("git", "checkout", "origin/main", "--", "data/edm.db")
    if not tamam:
        log.warning("db_senkron: checkout başarısız: %s", cikti[:200])
    return tamam
