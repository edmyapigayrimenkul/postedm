"""
yayin/sonuc.py — Kanal sonuçları: yayın raporunun YAPISAL hâli.

NİYE (2026-10-13): eski yayinla.py başarıyı rapor satırlarında "✓", hatayı "✗" karakteri arayarak anlıyordu
(`any("✓" in satir ...)`). Rapor metnine dokunan her değişiklik sessizce yayın durumunu bozabilirdi. Artık her satır
kendi durumunu taşır; metin yalnızca gösterim içindir.

Üç durum vardır, ikisi değil: TikTok taslağı ya da elle paylaşılacak Reels videosu ne "yayında" ne "hata"dır (eski satırlarda
ne ✓ ne ✗ vardı; durum makinesi onları başarı saymıyordu — bu korunur).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

YAYINDA = "yayinda"  # kanalda gerçekten yayında (eski satırlarda ✓)
HATA = "hata"        # başarısız (eski satırlarda ✗)
BILGI = "bilgi"      # ne yayın ne hata: TikTok taslağı, Telegram'a iletilen Reels videosu, seslendirme notu


@dataclass(frozen=True)
class Satir:
    metin: str   # Telegram raporundaki HTML satırı
    durum: str   # YAYINDA | HATA | BILGI


@dataclass
class KanalSonucu:
    """Bir kanal işçisinin çıktısı. `kimlik`: gönderi kimliği (Instagram, Threads, ...); `ham`: sağlayıcının sözlüğü
    (TikTok `publish_id`/`taslak_mi`, YouTube `video_id`/`url`); `etiket`: canlı durum göstergesindeki son etiket."""

    kanal: str
    etiket: str
    satirlar: List[Satir] = field(default_factory=list)
    kimlik: Any = None
    ham: Dict[str, Any] = field(default_factory=dict)

    def ekle(self, metin: str, durum: str) -> None:
        self.satirlar.append(Satir(metin, durum))


def yayinda_mi(satirlar: List[Satir]) -> bool:
    return any(s.durum == YAYINDA for s in satirlar)


def hata_var_mi(satirlar: List[Satir]) -> bool:
    return any(s.durum == HATA for s in satirlar)


@dataclass
class DagitimSonucu:
    """Tüm kanalların birleşik sonucu (kanal çalışma sırasıyla). Rapor, veritabanı kaydı ve telafi düğmeleri buradan beslenir."""

    kanallar: Dict[str, KanalSonucu] = field(default_factory=dict)
    on_satirlar: List[Satir] = field(default_factory=list)   # kanallardan önceki notlar (seslendirme durumu)
    son_satirlar: List[Satir] = field(default_factory=list)  # kanallardan sonraki notlar (site taslağı)

    @property
    def satirlar(self) -> List[Satir]:
        govde = [s for k in self.kanallar.values() for s in k.satirlar]
        return self.on_satirlar + govde + self.son_satirlar

    def kimlik(self, *adlar: str) -> Any:
        for ad in adlar:
            k = self.kanallar.get(ad)
            if k is not None and k.kimlik:
                return k.kimlik
        return None

    def ham(self, ad: str) -> Dict[str, Any]:
        k = self.kanallar.get(ad)
        return k.ham if (k is not None and isinstance(k.ham, dict)) else {}

    @property
    def ig_id(self) -> Any:
        return self.kimlik("instagram")

    @property
    def threads_id(self) -> Any:
        return self.kimlik("threads")

    @property
    def fb_id(self) -> Any:
        return self.kimlik("facebook", "facebook_reels")

    @property
    def linkedin_id(self) -> Any:
        return self.kimlik("linkedin")

    @property
    def twitter_id(self) -> Any:
        return self.kimlik("twitter", "x")

    @property
    def yt_res(self) -> Dict[str, Any]:
        return self.ham("youtube")

    @property
    def tt_res(self) -> Dict[str, Any]:
        return self.ham("tiktok")

    @property
    def video_telegrama_gitti(self) -> bool:
        return bool(self.ham("reels").get("video_telegrama_gitti"))

    @property
    def herhangi_yayinda(self) -> bool:
        return yayinda_mi(self.satirlar)

    @property
    def hata_var(self) -> bool:
        return hata_var_mi(self.satirlar)
