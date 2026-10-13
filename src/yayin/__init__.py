"""
src/yayin — Onaylanan içeriğin kanallara yayınlanması (eski scripts/yayinla.py'nin 1339 satırlık main()'inin bölünmüş hâli, 2026-10-13).

    akis.py        ana sıra (okumaya buradan başla)
    hedef.py       --hedef ayrıştırma, bayraklar, hangi kanallar
    icerik.py      haber/ilan yükleme, görsel adresleri (yükleme/onarım)
    videolar.py    dikey video + fon müziği/seslendirme
    kanallar/      her kanal için bir işçi (tt, ig, reels, story, th, fb, yt, li, tw)
    dagitim.py     paralel motor
    kayit.py       veritabanı sonucu, site taslağı
    rapor.py       Telegram sonuç raporu, telafi düğmeleri
    koruma.py      durum koruması + yayın kapısı
    aksiyonlar/    içerik işlemleri: reddet, çöpe at, ertele, kaldır, elle paket, yenile, metin, fotoğraf

Davranış tests/test_yayinla_altin.py ile (70 senaryo) donduruldu; bölme onu değiştirmedi.
"""

from .akis import calistir

__all__ = ["calistir"]
