"""
takipci.py — Kanal başına günlük takipçi sayısı.

2026-09-24 denetiminde büyüme ölçülemedi: gönderi metrikleri vardı ama takipçi
sayısı hiçbir yerde tutulmuyordu. "Bu ay kaç takipçi kazandık, hangi kanal
büyüyor" sorusunun cevabı bu tabloda.

Okunamayan kanal None yazılır, 0 değil — izin eksikliği "takipçi sıfıra
düştü" gibi görünmesin (instagram insights körlüğünün dersi).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import requests

from . import db

log = logging.getLogger(__name__)

TR = timezone(timedelta(hours=3))


def tabloyu_kur() -> None:
    with db._baglanti_al() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS takipci_gecmisi (
                   tarih TEXT NOT NULL,
                   kanal TEXT NOT NULL,
                   sayi INTEGER,
                   PRIMARY KEY (tarih, kanal)
               )"""
        )
        conn.commit()


def _get(url: str, **params: str) -> Optional[dict]:
    try:
        r = requests.get(url, params=params, timeout=20)
    except requests.RequestException as e:
        log.warning("Takipçi isteği başarısız (%s): %s", url.split("?")[0], type(e).__name__)
        return None
    if r.status_code != 200:
        log.warning("Takipçi isteği %s → HTTP %s", url.split("?")[0], r.status_code)
        return None
    try:
        return r.json()
    except ValueError:
        return None


def instagram() -> Optional[int]:
    from . import instagram as ig
    hesap_id, token = ig._hesap_bilgileri()
    if not (hesap_id and token):
        return None
    veri = _get(f"{ig.GRAPH_TABAN}/{hesap_id}", fields="followers_count", access_token=token)
    return (veri or {}).get("followers_count")


def threads() -> Optional[int]:
    from . import threads as th
    kullanici_id, token = th._hesap_bilgileri()
    if not (kullanici_id and token):
        return None
    veri = _get(f"{th.THREADS_TABAN}/{kullanici_id}/threads_insights", metric="followers_count", access_token=token)
    for m in (veri or {}).get("data", []):
        if m.get("name") == "followers_count":
            deger = (m.get("total_value") or {}).get("value")
            return int(deger) if deger is not None else None
    return None


def youtube() -> Optional[int]:
    from . import youtube as yt
    token = yt.access_token_al()
    if not token:
        return None
    try:
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "statistics", "mine": "true"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
        ogeler = r.json().get("items", []) if r.status_code == 200 else []
    except (requests.RequestException, ValueError):
        return None
    if not ogeler:
        return None
    sayi = ogeler[0].get("statistics", {}).get("subscriberCount")
    return int(sayi) if sayi is not None else None


def facebook() -> Optional[int]:
    from . import facebook as fb
    token, sayfa_id = fb._page_bilgileri()
    if not token:
        return None
    veri = _get(f"{fb.GRAPH_API_URL}/{sayfa_id}", fields="followers_count", access_token=token)
    return (veri or {}).get("followers_count")


KANALLAR = {"instagram": instagram, "threads": threads, "youtube": youtube, "facebook": facebook}


def kaydet(simdi: Optional[datetime] = None) -> Dict[str, Optional[int]]:
    """Bugünün takipçi sayılarını çeker ve yazar (aynı gün ikinci kez çalışırsa günceller)."""
    tabloyu_kur()
    tarih = (simdi or datetime.now(timezone.utc)).astimezone(TR).date().isoformat()
    sonuc: Dict[str, Optional[int]] = {}
    for kanal, cek in KANALLAR.items():
        try:
            sonuc[kanal] = cek()
        except Exception as e:  # bir kanalın hatası diğerlerini durdurmasın
            log.warning("%s takipçi sayısı okunamadı: %s", kanal, e)
            sonuc[kanal] = None
    with db._baglanti_al() as conn:
        for kanal, sayi in sonuc.items():
            conn.execute(
                "INSERT INTO takipci_gecmisi (tarih, kanal, sayi) VALUES (?, ?, ?) "
                "ON CONFLICT(tarih, kanal) DO UPDATE SET sayi = excluded.sayi",
                (tarih, kanal, sayi),
            )
        conn.commit()
    log.info("Takipçi sayıları (%s): %s", tarih, sonuc)
    return sonuc


def degisim(gun: int = 7) -> Dict[str, Dict[str, Optional[int]]]:
    """Kanal başına bugünkü sayı ve `gun` gün önceye göre fark."""
    tabloyu_kur()
    with db._baglanti_al() as conn:
        satirlar = conn.execute(
            "SELECT tarih, kanal, sayi FROM takipci_gecmisi WHERE sayi IS NOT NULL ORDER BY tarih"
        ).fetchall()
    kanallar: Dict[str, list] = {}
    for s in satirlar:
        kanallar.setdefault(s["kanal"], []).append((s["tarih"], s["sayi"]))
    sonuc: Dict[str, Dict[str, Optional[int]]] = {}
    for kanal, seri in kanallar.items():
        son_tarih, son = seri[-1]
        esik = (datetime.fromisoformat(son_tarih) - timedelta(days=gun)).date().isoformat()
        onceki = [s for t, s in seri if t <= esik]
        sonuc[kanal] = {"sayi": son, "fark": (son - onceki[-1]) if onceki else None}
    return sonuc
