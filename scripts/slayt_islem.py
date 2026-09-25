#!/usr/bin/env python3
"""
scripts/slayt_islem.py — Telegram Üzerinden Slayt Sıralama, Silme ve AI Düzenleme İşlemleri
Telegram onay kartında seçilen slayt operasyonlarını yürütür:
  - slayt_basa: Slaytı en başa (manşet) taşır
  - slayt_yukari / slayt_asagi: Slayt sırasını yer değiştirir
  - slayt_sil: Slaytı carousel'den çıkarır
  - slayt_carpici: AI ile başlığı daha dikkat çekici yapar
  - slayt_uzat / slayt_kisalt: Slayt metnini genişletir veya özetler
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import config, db, db_senkron, generate_text, make_image, telegram_bot, upload_image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("slayt_islem")


def slayt_carpici_yap(mevcut_baslik: str, konu_alani: str = "Gayrimenkul") -> str:
    """Gemini kullanarak başlığı clickbait olmadan daha vurucu ve merak uyandırıcı yapar."""
    prompt = (
        f"Aşağıdaki emlak ve gayrimenkul başlığını sosyal medya carousel paylaşımı için "
        f"daha vurucu, merak uyandırıcı ancak hukuken doğru ve profesyonel tek bir cümlelik başlığa dönüştür.\n\n"
        f"Mevcut Başlık: {mevcut_baslik}\n"
        f"Kategori: {konu_alani}\n\n"
        f"Sadece yeni başlığı tırnaksız olarak yaz. Başka açıklama ekleme."
    )
    sistem = "Sen EDM Yapı & Gayrimenkul'ün kıdemli gayrimenkul hukuku ve içerik uzmanısın."
    try:
        yanit = generate_text._gemini_cagri(prompt, sistem_talimati=sistem, sicaklik=0.7)
        if yanit:
            yeni = yanit.strip().strip('"').strip("'")
            return yeni if len(yeni) > 5 else mevcut_baslik
    except Exception as e:
        log.warning("AI başlık üretimi başarısız: %s", e)
    return mevcut_baslik


def slayt_metni_boyutlandir(mevcut_metin: str, uzat: bool = True) -> str:
    """Gemini kullanarak slayt spot metnini uzatır veya kısaltır."""
    hedef = "daha detaylı ve somut hukuki/mali açıklamalar ekleyerek 2-3 cümle yap" if uzat else "tek bir kısa, net ve vurucu cümleye özetle"
    prompt = (
        f"Aşağıdaki emlak bilgilendirme slayt metnini {hedef}.\n\n"
        f"Mevcut Metin: {mevcut_metin}\n\n"
        f"Sadece yeni metni yaz. Ekstra açıklama ekleme."
    )
    sistem = "Sen EDM Yapı & Gayrimenkul'ün kıdemli gayrimenkul hukuku ve içerik uzmanısın."
    try:
        yanit = generate_text._gemini_cagri(prompt, sistem_talimati=sistem, sicaklik=0.7)
        if yanit:
            yeni = yanit.strip().strip('"')
            return yeni if len(yeni) > 10 else mevcut_metin
    except Exception as e:
        log.warning("AI metin boyutlandırma başarısız: %s", e)
    return mevcut_metin


def main():
    parser = argparse.ArgumentParser(description="EDM Slayt İçi Detay Operasyonları")
    parser.add_argument("--eylem", required=True, help="slayt_basa, slayt_yukari, slayt_asagi, slayt_sil, slayt_carpici, slayt_uzat, slayt_kisalt")
    parser.add_argument("--sira", type=int, required=True, help="1-indexed slayt numarası")
    parser.add_argument("--mesaj-id", default="", help="Telegram mesaj ID")
    parser.add_argument("--id", default="", help="İçerik referans ID")
    parser.add_argument("--tur", default="haber", help="İçerik türü")
    args = parser.parse_args()

    eylem = args.eylem
    sira = args.sira
    log.info("Slayt işlemi başlatıldı: eylem=%s, sira=%d, mesaj_id=%s", eylem, sira, args.mesaj_id)

    tur = args.tur
    ref_id = args.id
    icerik = None

    if args.mesaj_id and str(args.mesaj_id).isdigit():
        mid = int(args.mesaj_id)
        bilgi = db.mesajdan_icerik_bul(mid)
        if bilgi:
            tur, ref_id, icerik = bilgi

    if not icerik and ref_id:
        icerik = db.haber_getir(int(ref_id) if str(ref_id).isdigit() else ref_id)

    if not icerik:
        bilgi = db.mesajdan_icerik_bul(0)
        if bilgi:
            tur, ref_id, icerik = bilgi

    if not icerik:
        telegram_bot.mesaj_gonder("⚠️ Düzenlenecek aktif slayt veya içerik bulunamadı.")
        sys.exit(1)

    haber_id = icerik["id"]
    slayt_yollari: List[str] = []
    if icerik.get("slayt_yollari"):
        try:
            slayt_yollari = json.loads(icerik["slayt_yollari"])
        except Exception:
            slayt_yollari = []

    if not slayt_yollari:
        telegram_bot.mesaj_gonder("⚠️ Bu içerikte düzenlenecek hazır slayt görseli bulunamadı.")
        sys.exit(1)

    toplam_slayt = len(slayt_yollari)
    if sira < 1 or sira > toplam_slayt:
        telegram_bot.mesaj_gonder(f"⚠️ {sira}. slayt bulunamadı (Toplam {toplam_slayt} slayt var).")
        sys.exit(1)

    otorite_verisi = None
    if icerik.get("detay_metni"):
        try:
            otorite_verisi = json.loads(icerik["detay_metni"])
        except Exception:
            otorite_verisi = None

    bildirim = ""

    # 1. SLAYT EN BAŞA AL (MANŞET YAP)
    if eylem == "slayt_basa":
        if sira == 1:
            telegram_bot.mesaj_gonder("ℹ️ Bu slayt zaten 1. sırada (Kapak).")
            sys.exit(0)
        hedef_yol = slayt_yollari.pop(sira - 1)
        slayt_yollari.insert(0, hedef_yol)
        if otorite_verisi and isinstance(otorite_verisi.get("adimlar"), list):
            adimlar = otorite_verisi["adimlar"]
            if (sira - 2) < len(adimlar) and (sira - 2) >= 0:
                hedef_adim = adimlar.pop(sira - 2)
                adimlar.insert(0, hedef_adim)
        bildirim = f"🔝 <b>{sira}. slayt en başa (Kapak) alındı.</b>"

    # 2. SLAYT YUKARI TAŞI
    elif eylem == "slayt_yukari":
        if sira == 1:
            telegram_bot.mesaj_gonder("ℹ️ Bu slayt zaten en üst sırada.")
            sys.exit(0)
        slayt_yollari[sira - 2], slayt_yollari[sira - 1] = slayt_yollari[sira - 1], slayt_yollari[sira - 2]
        if otorite_verisi and isinstance(otorite_verisi.get("adimlar"), list):
            adimlar = otorite_verisi["adimlar"]
            idx = sira - 2
            if idx > 0 and idx < len(adimlar):
                adimlar[idx - 1], adimlar[idx] = adimlar[idx], adimlar[idx - 1]
        bildirim = f"⬆️ <b>{sira}. slayt {sira - 1}. sıraya taşındı.</b>"

    # 3. SLAYT AŞAĞI TAŞI
    elif eylem == "slayt_asagi":
        if sira == toplam_slayt:
            telegram_bot.mesaj_gonder("ℹ️ Bu slayt zaten son sırada.")
            sys.exit(0)
        slayt_yollari[sira - 1], slayt_yollari[sira] = slayt_yollari[sira], slayt_yollari[sira - 1]
        if otorite_verisi and isinstance(otorite_verisi.get("adimlar"), list):
            adimlar = otorite_verisi["adimlar"]
            idx = sira - 2
            if idx >= 0 and idx < (len(adimlar) - 1):
                adimlar[idx], adimlar[idx + 1] = adimlar[idx + 1], adimlar[idx]
        bildirim = f"⬇️ <b>{sira}. slayt {sira + 1}. sıraya taşındı.</b>"

    # 4. SLAYT ÇIKAR (SİL)
    elif eylem == "slayt_sil":
        if toplam_slayt <= 2:
            telegram_bot.mesaj_gonder("⚠️ Carousel bütünlüğü için en az 2 slayt bulunmalıdır.")
            sys.exit(1)
        silinen = slayt_yollari.pop(sira - 1)
        Path(silinen).unlink(missing_ok=True)
        if otorite_verisi and isinstance(otorite_verisi.get("adimlar"), list):
            adimlar = otorite_verisi["adimlar"]
            if (sira - 2) < len(adimlar) and (sira - 2) >= 0:
                adimlar.pop(sira - 2)
        bildirim = f"🗑 <b>{sira}. slayt carousel'den çıkarıldı.</b> (Kalan: {len(slayt_yollari)} slayt)"

    # 5. BAŞLIĞI ÇARPICI YAP
    elif eylem == "slayt_carpici":
        mevcut_baslik = icerik.get("manset") or ""
        if sira > 1 and otorite_verisi and isinstance(otorite_verisi.get("adimlar"), list):
            adimlar = otorite_verisi["adimlar"]
            if (sira - 2) < len(adimlar) and (sira - 2) >= 0:
                mevcut_baslik = adimlar[sira - 2].get("baslik") or mevcut_baslik

        yeni_baslik = slayt_carpici_yap(mevcut_baslik, konu_alani=icerik.get("kategori") or "Gayrimenkul")
        if sira == 1:
            icerik["manset"] = yeni_baslik
            if otorite_verisi:
                otorite_verisi["manset_parca_1"] = yeni_baslik
        elif otorite_verisi and isinstance(otorite_verisi.get("adimlar"), list):
            adimlar = otorite_verisi["adimlar"]
            if (sira - 2) < len(adimlar) and (sira - 2) >= 0:
                adimlar[sira - 2]["baslik"] = yeni_baslik

        # Yeniden çiz
        if otorite_verisi:
            yeni_slaytlar = make_image.otorite_gonderi_slaytlari_uret(
                otorite_verisi,
                cikti_onek=f"gonderi_{haber_id}",
                olcu="story" if icerik.get("kategori") == "REELS" else "besleme",
            )
            slayt_yollari = [str(p) for p in yeni_slaytlar]
        bildirim = f"🔥 <b>{sira}. slaytın başlığı daha çarpıcı hale getirildi:</b>\n<i>{html.escape(yeni_baslik)}</i>"

    # 6. METNİ UZAT / KISALT
    elif eylem in ("slayt_uzat", "slayt_kisalt"):
        uzat = (eylem == "slayt_uzat")
        mevcut_metin = icerik.get("detay_metni") or icerik.get("orijinal_ozet") or ""
        if sira > 1 and otorite_verisi and isinstance(otorite_verisi.get("adimlar"), list):
            adimlar = otorite_verisi["adimlar"]
            if (sira - 2) < len(adimlar) and (sira - 2) >= 0:
                mevcut_metin = adimlar[sira - 2].get("aciklama") or adimlar[sira - 2].get("spot") or mevcut_metin

        yeni_metin = slayt_metni_boyutlandir(str(mevcut_metin), uzat=uzat)
        if sira == 1 and otorite_verisi:
            otorite_verisi["spot"] = yeni_metin
        elif otorite_verisi and isinstance(otorite_verisi.get("adimlar"), list):
            adimlar = otorite_verisi["adimlar"]
            if (sira - 2) < len(adimlar) and (sira - 2) >= 0:
                adimlar[sira - 2]["aciklama"] = yeni_metin
                adimlar[sira - 2]["spot"] = yeni_metin

        if otorite_verisi:
            yeni_slaytlar = make_image.otorite_gonderi_slaytlari_uret(
                otorite_verisi,
                cikti_onek=f"gonderi_{haber_id}",
                olcu="story" if icerik.get("kategori") == "REELS" else "besleme",
            )
            slayt_yollari = [str(p) for p in yeni_slaytlar]
        eylem_adi = "genişletildi" if uzat else "özetlendi"
        bildirim = f"📝 <b>{sira}. slaytın metni {eylem_adi}:</b>\n<i>{html.escape(yeni_metin[:150])}...</i>"

    # CDN'e yükle
    slayt_urlleri = []
    try:
        slayt_urlleri = upload_image.coklu_gorsel_yukle(slayt_yollari)
    except Exception as e:
        log.warning("Slaytlar CDN'e yüklenemedi: %s", e)

    # DB güncelle
    db.haber_guncelle(
        haber_id,
        slayt_yollari=json.dumps(slayt_yollari, ensure_ascii=False),
        slayt_urlleri=json.dumps(slayt_urlleri) if slayt_urlleri else None,
        detay_metni=json.dumps(otorite_verisi, ensure_ascii=False) if otorite_verisi else None,
    )

    # Telegram albüm ve onay kartını gönder
    telegram_bot.medya_grubu_gonder(
        slayt_yollari,
        caption=f"🎨 <b>GÜNCELLENEN SLAYTLAR ({len(slayt_yollari)} Slayt)</b>\n📌 {icerik.get('manset')}",
    )
    yeni_menu = telegram_bot.ana_menu(adet=len(slayt_yollari))
    telegram_bot.mesaj_gonder(
        f"{bildirim}\n\n<i>Slayt sıralaması ve görseller güncellendi. Yayına hazır olduğunda onaylayabilirsiniz:</i>",
        reply_markup=yeni_menu,
    )

    db_senkron.hemen_kaydet(f"db: slayt islemi {eylem} #{haber_id} (sira {sira})")
    log.info("Slayt işlemi başarıyla tamamlandı: %s", eylem)


if __name__ == "__main__":
    from src import make_image as _mi
    try:
        main()
    except _mi.EksikIcerik as _e:
        # Elle düzenlenen metin karta sığmadıysa genel "hata" yerine ne yapılacağını söyle
        telegram_bot.mesaj_gonder(
            f"✂️ <b>Düzenleme uygulanmadı:</b> {_e}.\n"
            "<i>Metin karta sığmadığı için slayt çizilmedi; daha kısa yazıp tekrar deneyin.</i>"
        )
        sys.exit(1)
