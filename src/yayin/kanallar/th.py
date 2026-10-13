"""Threads: her zaman 4:5; tek görsel ise tek gönderi, çok parçalı ise zincir (kök gönderi + yanıtlar)."""

from __future__ import annotations

import logging

from ... import generate_text, instagram, make_image, threads, upload_image
from ..baglam import YayinBaglami
from ..ilerleme import Ilerleme
from ..sonuc import HATA, YAYINDA, KanalSonucu

log = logging.getLogger(__name__)

KANAL = "threads"


def _threads_gorselleri(b: YayinBaglami) -> list:
    """Threads için 4:5 görseller: detay'daki hazır adresler → reels için yeniden çizim → yerel dosyaları 4:5 kırp → CDN adresleri."""
    from pathlib import Path
    threads_urller = None
    if b.detay and isinstance(b.detay, dict) and b.detay.get("slayt_4x5_urlleri"):
        threads_urller = b.detay["slayt_4x5_urlleri"]

    if not threads_urller and (b.reels_modu or b.tur == "reels") and b.detay:
        try:
            besleme_slaytlar = make_image.otorite_gonderi_slaytlari_uret(
                b.detay, cikti_onek=f"threads_4x5_{b.ref_id}", olcu="besleme"
            )
            if besleme_slaytlar:
                threads_urller = upload_image.coklu_gorsel_yukle([str(p) for p in besleme_slaytlar])
                log.info("Threads için native 4:5 slaytlar üretildi ve yüklendi (%d adet)", len(threads_urller))
        except Exception as b_err:  # noqa: BLE001
            log.warning("Threads native 4:5 slayt üretim hatası: %s", b_err)

    if not threads_urller and b.slayt_yollari and any(Path(p).exists() for p in b.slayt_yollari):
        try:
            threads_urller = instagram.gorselleri_4_5_yap(b.slayt_yollari)
        except Exception as c_err:  # noqa: BLE001
            log.warning("Threads yerel dosya 4:5 kırpma hatası: %s", c_err)

    if not threads_urller:
        threads_urller = b.public_urller
    return threads_urller


def _metin(b: YayinBaglami) -> str:
    th_metin = (b.haber.get("threads_metin") if b.haber and b.haber_mi() else "") or b.caption
    return generate_text.caption_zenginlestir(
        th_metin,
        kategori_kodu=b.haber.get("kategori") if b.haber else None,
        platform="threads",
        manset=b.baslik,
    )


def yayinla(b: YayinBaglami, ilerleme: Ilerleme) -> KanalSonucu:
    ilerleme.bildir(KANAL, "⏳ Yükleniyor...")
    s = KanalSonucu(KANAL, etiket="❌ Hata")
    try:
        threads_urller = _threads_gorselleri(b)

        th_tek = (len(threads_urller) <= 1) if threads_urller else b.tek_sayfa
        if th_tek:
            t_id = threads.paylas(_metin(b), [threads_urller[0]] if threads_urller else None)
            s.kimlik = t_id
            if t_id:
                s.ekle("🧵 <b>Threads (Tekil Görsel):</b> 4:5 paylaşıldı ✓", YAYINDA)
            else:
                s.ekle("🧵 <b>Threads:</b> Hata oluştu ✗", HATA)
        else:
            sayfalar = threads.metinleri_slaytlara_dagit(
                b.haber if b.haber_mi() else {"manset": b.baslik, "spot": b.caption}, threads_urller)
            if len(sayfalar) > 1:
                zincir = threads.zincir_paylas_sonuc(sayfalar)
                t_id = zincir["kok_id"]
                s.kimlik = t_id
                if t_id and not zincir["eksik"]:
                    s.ekle(f"🧵 <b>Threads:</b> {zincir['yayinlanan']} parçalı 4:5 zincir paylaşıldı ✓", YAYINDA)
                elif t_id:
                    # Planlanan sayı değil, gerçekten yayınlanan sayı raporlanır
                    eksik = ", ".join(str(n) for n in zincir["eksik"])
                    s.ekle(
                        f"🧵 <b>Threads:</b> zincir EKSİK — {zincir['yayinlanan']}/{zincir['toplam']} parça "
                        f"yayında, {eksik}. parça yayınlanamadı ✗", HATA
                    )
                else:
                    s.ekle("🧵 <b>Threads:</b> Hata oluştu ✗", HATA)
            else:
                t_id = threads.paylas(_metin(b), threads_urller)
                s.kimlik = t_id
                if t_id:
                    s.ekle("🧵 <b>Threads:</b> 4:5 paylaşıldı ✓", YAYINDA)
                else:
                    s.ekle("🧵 <b>Threads:</b> Hata oluştu ✗", HATA)
    except Exception as yayin_hatasi:  # noqa: BLE001
        log.warning("Threads yayını hatası: %s", yayin_hatasi)
        s.ekle(f"🧵 <b>Threads:</b> Hata ({yayin_hatasi}) ✗", HATA)
    if s.kimlik:
        s.etiket = "✅ Yayında"
    ilerleme.bildir(KANAL, s.etiket, increment=True)
    return s
