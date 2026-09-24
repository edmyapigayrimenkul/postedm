"""
db_senkron.py — Veritabanını (data/edm.db) GitHub'a güvenli commit+push eden modül.
Instabot mimarisinden uyarlanmıştır.

Push çakışırsa uzaktaki değişiklik üstümüze alınır ve data/edm.db SATIR DÜZEYİNDE
üç yönlü birleştirilir (src/db_birlestir.py). Önceki sürüm ikili dosyayı "--theirs"
ile seçiyordu: bir tarafın bütün değişiklikleri siliniyordu (geçmişte 6 geri sarma,
birinde 28 haber kaydı). Birleştirme tamamlanamazsa push YAPILMAZ ve hata yükselir —
sessizce veri ezmek yerine görünür şekilde durmak.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from . import config, db, db_birlestir

log = logging.getLogger(__name__)

DAL = "main"
DB_GORELI = "data/edm.db"

# Bot kimliği süreç ortamıyla, yalnızca bu modülün git çağrılarına verilir.
# Önceden `git config user.name` KALICI yazılıyordu: yerelde bir betik bir kez
# çalışınca, sonraki TÜM kod commit'leri "github-actions[bot]" adıyla atılıyordu.
# commit, rebase ve stash commit ürettiği için üçü de kimlik ister (CI'da global
# git kimliği yok).
_BOT_AD = "github-actions[bot]"
_BOT_EPOSTA = "41898282+github-actions[bot]@users.noreply.github.com"
BOT_ORTAMI = {
    "GIT_AUTHOR_NAME": _BOT_AD, "GIT_AUTHOR_EMAIL": _BOT_EPOSTA,
    "GIT_COMMITTER_NAME": _BOT_AD, "GIT_COMMITTER_EMAIL": _BOT_EPOSTA,
}

_DEGISIKLIK_YOK_KALIPLARI = (
    "nothing to commit",
    "nothing added to commit",
    "no changes added to commit",
    "working tree clean",
)


def _calistir(*komut: str, saniye: int = 60, ortam: Optional[dict] = None) -> Tuple[bool, str]:
    try:
        s = subprocess.run(komut, capture_output=True, text=True, timeout=saniye,
                           cwd=config.KOK_DIZIN, env={**os.environ, **BOT_ORTAMI, **(ortam or {})})
        return s.returncode == 0, (s.stderr or s.stdout).strip()
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _blob_yaz(nesne: str, hedef: Path) -> bool:
    """git show <nesne> çıktısını ikili olarak dosyaya yazar."""
    try:
        s = subprocess.run(["git", "show", nesne], capture_output=True, timeout=60, cwd=config.KOK_DIZIN)
        if s.returncode != 0:
            return False
        hedef.write_bytes(s.stdout)
        return True
    except Exception:
        return False


def _push() -> Tuple[bool, str]:
    """Açık refspec ile iter: HEAD:main (detached HEAD durumunda da çalışır)."""
    return _calistir("git", "push", "origin", f"HEAD:{DAL}", saniye=120)


def _rebase_devam_ediyor() -> bool:
    git_dir = Path(config.KOK_DIZIN) / ".git"
    return (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists()


def _db_catismasini_coz() -> bool:
    """Rebase ortasındaki data/edm.db çakışmasını satır düzeyinde çözer.

    Rebase'de indeks aşamaları: :1 ortak ata, :2 yukarı akış (uzak), :3 yeniden
    uygulanan commit (bizim). Sonuç = uzak + bizim tabandan beri değişikliklerimiz.
    """
    with tempfile.TemporaryDirectory() as g:
        taban, uzak, bizim = Path(g) / "o.db", Path(g) / "a.db", Path(g) / "b.db"
        taban_var = _blob_yaz(f":1:{DB_GORELI}", taban)
        if not (_blob_yaz(f":2:{DB_GORELI}", uzak) and _blob_yaz(f":3:{DB_GORELI}", bizim)):
            log.error("db_senkron: çakışma aşamaları okunamadı")
            return False
        try:
            rapor = db_birlestir.birlestir(taban if taban_var else None, uzak, bizim, config.yol_al(DB_GORELI))
        except Exception as e:
            log.error("db_senkron: satır birleştirmesi başarısız: %s", e)
            return False
    log.info("db_senkron: data/edm.db birleştirildi — %s", rapor.ozet())
    if rapor.yeniden_numaralanan:
        _yeniden_numaralamayi_bildir(rapor)
    return _calistir("git", "add", DB_GORELI)[0]


def _yeniden_numaralamayi_bildir(rapor: db_birlestir.Rapor) -> None:
    try:
        from . import telegram_bot
        haberler = rapor.yeniden_numaralanan.get("haberler")
        if haberler:
            ciftler = ", ".join(f"#{e} → #{y}" for e, y in haberler.items())
            telegram_bot.mesaj_gonder(
                "ℹ️ <b>Eşzamanlı iki çalışma aynı içerik numarasını üretti.</b>\n"
                f"Veri kaybı olmadı; bu çalışmanın içeriği yeni numara aldı: {ciftler}\n"
                "<i>Eski onay mesajındaki butonlar Telegram mesaj kimliğiyle doğru içeriği bulur.</i>"
            )
    except Exception as e:
        log.warning("db_senkron: yeniden numaralama bildirimi gönderilemedi: %s", e)


def _birlestir() -> bool:
    """Uzaktaki değişikliği üstümüze alır; DB çakışmasını satır düzeyinde çözer."""
    _calistir("git", "fetch", "origin", DAL, saniye=90)
    # Yalnızca gerçekten bir şey saklandıysa geri alınır: saklanacak değişiklik
    # yokken koşulsuz "stash pop", yereldeki eski ve ilgisiz bir stash'i uygular.
    once = _stash_sayisi()
    _calistir("git", "stash", "push", "--include-untracked", "-m", "db_senkron")
    saklandi = _stash_sayisi() > once
    try:
        tamam, cikti = _calistir("git", "rebase", f"origin/{DAL}", ortam={"GIT_EDITOR": "true"})
        # Her yeniden uygulanan commit için çakışma çıkabilir
        for _ in range(20):
            if tamam or not _rebase_devam_ediyor():
                break
            catisan = _calistir("git", "diff", "--name-only", "--diff-filter=U")[1].split()
            if catisan != [DB_GORELI]:
                log.error("db_senkron: veritabanı dışında çakışma var, rebase iptal: %s", catisan)
                _calistir("git", "rebase", "--abort")
                return False
            if not _db_catismasini_coz():
                _calistir("git", "rebase", "--abort")
                return False
            tamam, cikti = _calistir("git", "rebase", "--continue", ortam={"GIT_EDITOR": "true"})
        if not tamam and _rebase_devam_ediyor():
            log.error("db_senkron: rebase tamamlanamadı: %s", cikti[:200])
            _calistir("git", "rebase", "--abort")
            return False
        return True
    finally:
        if saklandi:
            _calistir("git", "stash", "pop")


def _stash_sayisi() -> int:
    tamam, cikti = _calistir("git", "stash", "list")
    return len([s for s in cikti.splitlines() if s.strip()]) if tamam else 0


def _degisiklik_yok(cikti: str) -> bool:
    metin = (cikti or "").lower()
    return any(k in metin for k in _DEGISIKLIK_YOK_KALIPLARI)


def veritabani_saglam_mi(db_yolu: str | Path | None = None) -> bool:
    """
    Veritabanı dosyasının fiziksel olarak var olduğunu, SQLite formatında olduğunu
    ve bozuk olmadığını doğrular. Bozuk (0 bayt, sıfırlanmış ilk sayfa vb.) bir veritabanının
    git'e commit edilip diğer tüm runner'ları zehirlemesini engeller.
    """
    try:
        import sqlite3
        yol = Path(db_yolu or config.db_yolu())
        if not yol.exists() or yol.stat().st_size < 100:
            log.critical("db_senkron: '%s' dosyası mevcut değil veya çok küçük (<100 bayt)!", yol)
            return False
        with open(yol, "rb") as f:
            baslik = f.read(16)
            if baslik != b"SQLite format 3\x00":
                log.critical("db_senkron: '%s' SQLite başlığı geçersiz (ilk 16 bayt bozuk)!", yol)
                return False
        with sqlite3.connect(yol, timeout=10) as con:
            res = con.execute("PRAGMA quick_check").fetchone()
            if not res or res[0] != "ok":
                log.critical("db_senkron: '%s' quick_check başarısız: %s", yol, res)
                return False
        return True
    except Exception as e:
        log.critical("db_senkron: veritabanı kontrol hatası: %s", e)
        return False


def hemen_kaydet(mesaj: str, ek_yollar: Optional[List[str]] = None) -> bool:
    """
    data/edm.db'yi commit edip push eder.
    GitHub Actions runner'larında ve yerelde güvenle çalışır.
    """
    if config.test_modu():
        log.info("[TEST MODU] db_senkron.hemen_kaydet atlandı: %s", mesaj)
        return True

    # 0. Sağlamlık kontrolü (bozuk DB asla commit/push edilemez)
    if not veritabani_saglam_mi():
        log.critical("db_senkron: Veritabanı sağlamlık kontrolünden GEÇEMEDİ! Commit iptal edildi.")
        return False

    # 1. WAL dosyasını ana db'ye göm
    db.wal_bosalt()

    # 2. Dosyaları ekle
    yollar = [DB_GORELI] + list(ek_yollar or [])
    tamam, _ = _calistir("git", "add", *yollar)
    if not tamam:
        log.warning("db_senkron: git add başarısız")
        return False

    # 3. Commit — POSTEDM_DB_COMMIT, yerel pre-commit kancasına bunun meşru bir
    #    veritabanı commit'i olduğunu söyler (bkz. scripts/git_kancalari_kur.py)
    tamam, cikti = _calistir("git", "commit", "-m", mesaj, ortam={"POSTEDM_DB_COMMIT": "1"})
    if not tamam and not _degisiklik_yok(cikti):
        log.warning("db_senkron: commit başarısız: %s", cikti[:200])
        return False

    # 4. Push (çakışma varsa satır düzeyinde birleştirip tekrar dene)
    tamam, cikti = _push()
    for deneme in range(3):
        if tamam:
            break
        log.info("db_senkron: push reddedildi, uzak değişiklik birleştiriliyor (deneme %d)...", deneme + 1)
        if not _birlestir():
            break
        tamam, cikti = _push()

    if tamam:
        log.info("db_senkron: veritabanı başarıyla push edildi")
    else:
        log.error("db_senkron: veritabanı push EDİLEMEDİ: %s", cikti[:200])
    return tamam


def uzaktan_tazele() -> bool:
    """Uzaktaki en güncel veritabanını, yereldeki kaydedilmemiş değişiklikleri
    KAYBETMEDEN çalışma kopyasına birleştirir.

    Önceki sürüm yerel değişiklikleri `git stash`'e atıp bir daha geri almıyordu.
    """
    if config.test_modu():
        log.info("[TEST MODU] db_senkron.uzaktan_tazele atlandı")
        return True

    tamam, cikti = _calistir("git", "fetch", "origin", DAL, saniye=90)
    if not tamam:
        log.warning("db_senkron: fetch başarısız: %s", cikti[:200])
        return False

    db.wal_bosalt()
    with tempfile.TemporaryDirectory() as g:
        taban, uzak = Path(g) / "o.db", Path(g) / "b.db"
        if not _blob_yaz(f"origin/{DAL}:{DB_GORELI}", uzak):
            log.warning("db_senkron: uzak veritabanı okunamadı")
            return False
        taban_var = _blob_yaz(f"HEAD:{DB_GORELI}", taban)
        calisan = config.yol_al(DB_GORELI)
        try:
            rapor = db_birlestir.birlestir(taban if taban_var else None, calisan, uzak, calisan)
        except Exception as e:
            log.warning("db_senkron: uzak veritabanı birleştirilemedi: %s", e)
            return False
    log.info("db_senkron: uzak veritabanı yerel kopyaya birleştirildi — %s", rapor.ozet())
    return True
