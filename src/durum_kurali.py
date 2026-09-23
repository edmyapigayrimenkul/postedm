"""
src/durum_kurali.py — İçerik durum geçişlerinin tek kaynağı.

NİYE VAR (2026-09-23 denetimi): Instagram'daki canlı postlarla DB karşılaştırıldı.
#123 DB'de 'iptal' ama Instagram'da yayında; #68 'reddedildi' ama yayında.
Kodda iki yönde de koruma yoktu:
  · yayinla.py yayından önce içeriğin durumunu okumuyordu — Telegram'da eski
    bir mesajdaki "Yayınla" butonu iptal edilmiş içeriği yayınlayabiliyordu;
  · iptal/reddet/çöpe at, içerik yayında olsa bile durumu koşulsuz eziyordu —
    üstelik ardından yeni içerik üretimini de tetikliyordu;
  · tek kanal için "tekrar dene" başarısız olunca, diğer kanallar canlıyken
    durum 'yayinlandi' → 'hata'ya düşüyordu.

Kural basit: kapalı içerik yayınlanmaz; yayındaki içerik taslak işlemlerine
(atla, çöpe at, yenile, metin/görsel düzenleme) kapalıdır; bir kanala ikinci kez
gönderilmez; yayındaki içerik hiçbir başarısız denemeyle 'hata'ya düşmez.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set

YAYINDA = "yayinlandi"

# Bu durumlardaki içerik bir daha yayına çıkamaz.
KAPALI = frozenset({"iptal", "reddedildi", "kaldirildi", "elendi", "engellendi"})

# Kanal → yayın kimliğinin tutulduğu sütun. Kimlik varsa kanal zaten yayında.
# Story ve elle paylaşılan Reels kimlik üretmediği için bu tabloda yok.
KANAL_KIMLIK = {
    "instagram": "instagram_post_id",
    "threads": "threads_post_id",
    "facebook": "facebook_post_id",
    "facebook_reels": "facebook_post_id",
    "youtube": "youtube_video_id",
    "tiktok": "tiktok_publish_id",
}


def yayinda_mi(haber: Dict[str, Any]) -> bool:
    """Durum ya da herhangi bir kanal kimliği içeriğin yayında olduğunu söylüyor mu."""
    return haber.get("durum") == YAYINDA or any(haber.get(s) for s in KANAL_KIMLIK.values())


def yayin_engeli(haber: Dict[str, Any]) -> Optional[str]:
    """Yayına izin yoksa kullanıcıya gösterilecek neden, varsa None."""
    durum = haber.get("durum")
    if durum in KAPALI:
        return (
            f"⛔ <b>İçerik #{haber.get('id')} yayınlanmadı.</b>\n"
            f"Durumu <code>{durum}</code> — bu içerik daha önce atlanmış, reddedilmiş "
            f"veya kaldırılmış. Eski bir mesajdaki butona basılmış olabilir."
        )
    return None


def taslak_islem_engeli(haber: Dict[str, Any], islem: str) -> Optional[str]:
    """Atla / çöpe at / yenile / metin-görsel düzenleme yalnızca yayında OLMAYAN içerikte."""
    if yayinda_mi(haber):
        return (
            f"⛔ <b>İçerik #{haber.get('id')} zaten yayında</b> — '{islem}' uygulanmadı.\n"
            f"Yayından kaldırmak için: <code>/sil {haber.get('id')}</code>"
        )
    return None


def yayindaki_kanallar(haber: Dict[str, Any]) -> Set[str]:
    return {k for k, sutun in KANAL_KIMLIK.items() if haber.get(sutun)}


def tekrar_gonderilmeyecekler(haber: Dict[str, Any], hedef_kanallar: Iterable[str]) -> List[str]:
    """Hedeflerden, kimliği zaten kayıtlı olanlar — ikinci kez gönderilmez."""
    yayinda = yayindaki_kanallar(haber)
    return [k for k in hedef_kanallar if k in yayinda]


def sonraki_durum(onceki: Optional[str], herhangi_biri_basarili: bool) -> str:
    """Yayın denemesinden sonra içeriğin durumu. Yayındaki içerik 'hata'ya düşmez."""
    if herhangi_biri_basarili or onceki == YAYINDA:
        return YAYINDA
    return "hata"
