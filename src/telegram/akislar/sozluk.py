"""
src/telegram/akislar/sozluk.py — Gayrimenkul sözlüğü kartı: kart seçimi, onaya sunma / otomatik yayın kararı.

Katman 4 (akış). Kart `sozluk_arsivi`'ndeki hazır arşivden seçilir (kanunla hâlâ uyuşuyor mu sınanır), onay akışına (`onay.haber_onayina_sun`) verilir.
"""

from __future__ import annotations

import html
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from ... import db, generate_text, konu_bankasi
from .. import ayarlar, istemci
from . import onay, zamanli

log = logging.getLogger(__name__)


def sozluk_oto_yayin_acik_mi() -> bool:
    """Sözlük kartlarının onaysız yayını.
    1. DB ayarı: db.ayar_oku('sozluk_oto_yayin') '1' / 'acik' ise aktif.
    2. GitHub Actions değişkeni: SOZLUK_OTO_YAYIN ortam değişkeni '1' / 'acik' ise aktif.
    """
    db_deger = str(db.ayar_oku("sozluk_oto_yayin") or "").strip().lower()
    if db_deger in ("1", "true", "evet", "acik", "açık"):
        return True
    return os.environ.get("SOZLUK_OTO_YAYIN", "").strip().lower() in ("1", "true", "evet", "acik", "açık")


_OTO_YAYIN_KAPALI_DEGERLER = ("0", "false", "hayir", "hayır", "kapali", "kapalı")


def sozluk_oto_yayin_kapatildi_mi() -> bool:
    """Otomatik yayın AÇIKÇA kapatılmış mı: GitHub değişkeni `SOZLUK_OTO_YAYIN` ya da DB ayarı `sozluk_oto_yayin`
    '0' / 'kapali'. Tanımsız ya da boş = kapatılmamış.

    NİYE ayrı bir işlev: 12:30 çalıştırması `--oto-yayin` ile gelir; açık anahtarı beklemek zamanlamayı anlamsız
    kılar. Ama kod değiştirmeden, bir değişkenle durdurulabilen bir acil fren olmalı (yanlış kart yayınlandığında
    push ve dağıtım beklemeden)."""
    for deger in (os.environ.get("SOZLUK_OTO_YAYIN", ""), str(db.ayar_oku("sozluk_oto_yayin") or "")):
        if deger.strip().lower() in _OTO_YAYIN_KAPALI_DEGERLER:
            return True
    return False


def _sozluk_karti_sec() -> Tuple[Optional[Dict[str, Any]], Optional[bool]]:
    """(kart, taze). Kanunu değişmiş kart yayınlanmaz: Telegram'a bildirilir ve sıradakine geçilir.
    taze=None: kanun metni alınamadı (doğrulanamadı)."""
    from ... import sozluk_arsivi
    reddedilen: set = set()
    for _ in range(8):
        kart = sozluk_arsivi.sonraki_kart(haric=reddedilen)
        if kart is None:
            return None, None
        taze, sorunlar = sozluk_arsivi.kart_kanun_durumu(kart)
        if taze is False:
            reddedilen.add(kart["kod"])
            log.warning("Sözlük kartı %s kanunla uyuşmuyor: %s", kart["kod"], "; ".join(sorunlar))
            istemci.mesaj_gonder(
                f"🛑 <b>Sözlük kartı {kart['kod']} ({html.escape(kart['terim'])}) durduruldu</b>\n"
                f"<i>Kanun metniyle uyuşmuyor; madde değişmiş olabilir:</i>\n"
                + "\n".join(f"• {html.escape(s)}" for s in sorunlar[:3])
                + "\n<i>Kart bu çalıştırmada atlandı; data/sozluk_kartlari.yaml'da güncellenmeli.</i>"
            )
            continue
        return kart, taze
    return None, None


def sozluk_karti_hazirla_ve_sun(oto_yayin: Optional[bool] = None) -> Optional[bool]:
    """Hazır arşivden sıradaki sözlük kartını hazırlar. Kart yoksa None döner (çağıran modele geçer).

    `oto_yayin`: True = bu çalıştırma otomatik yayına yetkili (zamanlanmış 12:30 işi `--oto-yayin` ile gelir),
    False = hiçbir zaman otomatik değil, None = anahtara bak (`sozluk_oto_yayin_acik_mi`).

    Otomatik yayın YALNIZCA şu koşulların hepsi varsa olur; biri eksikse kart onaya düşer:
    anahtar açıkça kapatılmamış, kanun metni alındı ve kartla tutuyor, bot duraklatılmamış, bugün başka
    otomatik sözlük yayınlanmamış, denetim kapısı uyarısız. Model hiçbir aşamada çalışmaz."""
    from ... import sozluk_arsivi
    kart, taze = _sozluk_karti_sec()
    if kart is None:
        return None
    istenen = sozluk_oto_yayin_acik_mi() if oto_yayin is None else bool(oto_yayin)
    neden = ""
    if istenen:
        duraklatildi, _ = ayarlar.bot_duraklatildi_mi()
        if sozluk_oto_yayin_kapatildi_mi():
            neden = "otomatik yayın anahtarı kapatılmış (SOZLUK_OTO_YAYIN=0)"
        elif taze is not True:
            neden = "kanun metni alınamadığı için kart doğrulanamadı"
        elif duraklatildi:
            neden = "bot duraklatılmış"
        elif db.ayar_oku("sozluk_oto_son_gun") == zamanli._tr_bugun():
            neden = "bugün zaten bir sözlük kartı otomatik yayınlandı"
    otomatik = istenen and not neden
    if istenen and neden:
        istemci.mesaj_gonder(f"ℹ️ Sözlük kartı otomatik yayınlanmadı: {neden}. Onayınıza sunuluyor.")

    istemci.mesaj_gonder(f"📖 <b>Sözlük kartı</b> · {kart['kod']} · {html.escape(kart['terim'])}"
                 + (" · <b>otomatik yayın</b>" if otomatik else ""))
    kalan = sozluk_arsivi.stok_kalan(kart)
    if kalan <= sozluk_arsivi.STOK_UYARI_ESIGI:
        istemci.mesaj_gonder(
            f"📉 <b>Sözlük kartı stoğu azalıyor</b>: bu karttan sonra yayınlanmamış {kalan} kart kaldı "
            f"(günde bir kartla ≈{kalan} gün). Kartlar bitince sözlük her gün modelle üretilip onayınıza düşer; "
            f"tekrarsız {sozluk_arsivi.BEKLEME_GUN // 365} yıl için {sozluk_arsivi.HEDEF_KART} kart gerekir. Yeni kart yazılmalı."
        )
    veri = sozluk_arsivi.karttan_veri(kart)
    simdi = datetime.now(timezone.utc).isoformat()
    with db._baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet,
                                     eklenme_tarihi, onem_puani, kategori, manset, detay_metni,
                                     ig_caption, threads_metin, durum)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'yeni')""",
            (
                f"EDM Sözlük Kartı // {kart['kod']}",
                f"{kart['terim']} nedir?",
                f"edm://sozluk/{kart['kod']}/{int(time.time())}",
                veri.get("spot", ""),
                simdi,
                veri.get("onem_puani", 8),
                kart["kategori_kodu"],
                generate_text.manset_birlestir(veri),
                json.dumps(veri, ensure_ascii=False),
                veri.get("caption_instagram", ""),
                veri.get("caption_threads", ""),
            ),
        )
        haber_id = cur.lastrowid
        conn.commit()

    konu_bankasi.kullanildi_isaretle(kart["kod"], haber_id=haber_id, format_turu="sozluk")
    sonuc = onay.haber_onayina_sun(haber_id, oto_yayin=otomatik)
    if otomatik:
        from ... import durum_kurali
        if durum_kurali.yayinda_mi(db.haber_getir(haber_id) or {}):
            db.ayar_yaz("sozluk_oto_son_gun", zamanli._tr_bugun())
    return sonuc
