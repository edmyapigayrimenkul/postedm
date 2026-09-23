"""
src/sutun.py — İçeriğin editoryal sütunu (S1–S5) için tek kaynak.

NİYE VAR: haberler.kategori alanı üç farklı adlandırmayla doldu — "S4",
"TAPU_VE_HUKUK", "S4-005" — ve üstüne tür bilgisi taşıyor ("REELS",
"rehber"). Sütun bazlı ölçüm (hangi konu türü kaydediliyor, paylaşılıyor)
bu haliyle yapılamıyordu. kategori'ye dokunulmuyor (görsel etiketi, stok
foto anahtarı ve reels/haber ayrımı ona bağlı); analiz için ayrı ve tutarlı
`sutun` alanı türetiliyor.

Öncelik: konu kodu (kaynak "EDM Konu Bankası // S3-007") > kategori içindeki
S-kodu > eski ad eşlemesi. Hiçbiri yoksa None — sütun uydurulmaz.
"""

from __future__ import annotations

import re
from typing import Optional

SUTUN_ADLARI = {
    "S1": "Tapu & Hukuk",
    "S2": "Kiracı & Ev Sahibi",
    "S3": "Arsa & İmar",
    "S4": "Rakam & Bölge",
    "S5": "Finans & Kredi",
}

_ESKI_ADLAR = {
    "TAPU_VE_HUKUK": "S1",
    "EV_SAHIBI_VE_KIRACI": "S2",
    "ARSA_VE_IMAR": "S3",
    "IMAR_VE_MEVZUAT": "S3",
    "YATIRIM_VE_PIYASA": "S4",
    "FINANS_VE_BANKACILIK": "S5",
}

_KOD = re.compile(r"(?<![A-Za-z0-9])S([1-5])(?:-\d+)?(?![0-9])")


def sutun_bul(kategori: Optional[str], kaynak: Optional[str] = None) -> Optional[str]:
    for deger in (kaynak, kategori):
        m = _KOD.search(str(deger or ""))
        if m:
            return f"S{m.group(1)}"
    return _ESKI_ADLAR.get(str(kategori or "").strip().upper())
