"""
yayin/baglam.py — Bir yayın isteğinin bağlamı.

Eski main() bu değerleri 1300 satırlık bir kapanışta ortak YEREL DEĞİŞKENLER olarak tutuyor, kanal işçileri `nonlocal` ile
değiştiriyordu. Burada açık bir nesnedir: yükleme adımı doldurur, kanal işçileri okur, hiçbiri başkasının alanını yazmaz.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class Istek:
    """Komut satırından gelen istek (içerik henüz yüklenmedi)."""

    tur: str                      # haber | ilan | reels
    ref_id: str
    hedef: str                    # ham, küçük harfli "ig,threads" ya da bir işlem adı ("reddet", "yenile", ...)
    hedefler: Set[str]
    mesaj_id: Optional[int] = None
    yeniden_ciz: bool = False
    plan_an: Optional[str] = None

    def hedef_mi(self, *adaylar: str) -> bool:
        return "hepsi" in self.hedefler or bool(self.hedefler.intersection(adaylar))


@dataclass
class YayinBaglami:
    """Yayına hazır içerik: kanal işçilerinin okuduğu her şey."""

    istek: Istek
    haber: Optional[Dict[str, Any]] = None
    ilan: Optional[Dict[str, Any]] = None
    detay: Any = field(default_factory=dict)  # haberler.detay_metni (JSON); dict olmayabilir (null/liste) — işçiler `isinstance` bakar
    baslik: Any = ""
    caption: str = ""
    slayt_yollari: List[str] = field(default_factory=list)
    public_urller: List[str] = field(default_factory=list)
    tek_sayfa: bool = False

    # Hedef bayrakları
    reels_modu: bool = False
    paylas_reels: bool = False
    paylas_ig: bool = False
    ses_modu: Optional[str] = None   # "muzikli" | "muziksiz" | None
    ses_sonucu: Dict[str, Any] = field(default_factory=dict)

    # Video (yalnız video_lazim ise doldurulur)
    video_lazim: bool = False
    v_yolu: Optional[Path] = None
    sesli_video_yolu: Optional[Path] = None
    dikey_slaytlar: List[str] = field(default_factory=list)

    # --- kısayollar ---------------------------------------------------------------------------------------------
    @property
    def tur(self) -> str:
        return self.istek.tur

    @property
    def ref_id(self) -> str:
        return self.istek.ref_id

    @property
    def hedefler(self) -> Set[str]:
        return self.istek.hedefler

    def hedef_mi(self, *adaylar: str) -> bool:
        return self.istek.hedef_mi(*adaylar)

    def haber_mi(self) -> bool:
        return self.tur in ("haber", "reels")

    def video_yolu_var(self) -> Optional[Path]:
        """Reels / TikTok / Telegram için tercih edilen video: onay anında derlenen, yoksa fon müzikli."""
        if self.v_yolu and self.v_yolu.exists():
            return self.v_yolu
        return self.sesli_video_yolu
