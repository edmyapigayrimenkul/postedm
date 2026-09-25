#!/usr/bin/env python3
"""
scripts/metin_duzenle.py — Telegram Reply ile Başlık ve Metin Düzenleme
Telegram onay kartına gelen kullanıcı yanıtını (reply) işler:
  - İlgili haber, reels veya ilanı bulur
  - Yeni başlık ve varsa açıklamayı ayrıştırır
  - Veritabanını günceller
  - Slayt görsellerini yeni metinlerle yeniden derler
  - Güncellenen yeni onay kartını gruba iletir
"""

import argparse
import html
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import config, db, generate_text, make_image, telegram_bot, upload_image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("metin_duzenle")


def metin_ayristir(metin: str) -> Tuple[Optional[int], str, Optional[str]]:
    """
    Kullanıcının girdiği reply metnini analiz eder.
    Formatlar:
      - '3: Yeni Başlık'
      - '3: Yeni Başlık | Yeni Açıklama'
      - 'Yeni Başlık | Yeni Açıklama'
      - 'Yeni Başlık\nYeni Açıklama'
      - 'Yeni Başlık'
      - 'başlık: Yeni Başlık'  (Worker yalnızca açık sözdizimini iletir)
    """
    metin = re.sub(r"^ba[sş]l[ıi]k\s*:\s*", "", metin.strip(), flags=re.IGNORECASE)
    sira = None
    eslesme = re.match(r"^([1-9]|10)\s*[:\.\-]\s*(.+)$", metin, re.DOTALL)
    if eslesme:
        sira = int(eslesme.group(1))
        kalan = eslesme.group(2).strip()
    else:
        kalan = metin

    if "|" in kalan:
        parcalar = kalan.split("|", 1)
        yeni_baslik = parcalar[0].strip()
        yeni_aciklama = parcalar[1].strip() or None
    elif "\n" in kalan:
        parcalar = kalan.split("\n", 1)
        yeni_baslik = parcalar[0].strip()
        yeni_aciklama = parcalar[1].strip() or None
    else:
        yeni_baslik = kalan
        yeni_aciklama = None

    return sira, yeni_baslik, yeni_aciklama


def haber_metni_guncelle(
    haber_id: int,
    haber: Dict[str, Any],
    yeni_baslik: str,
    yeni_aciklama: Optional[str] = None,
    sira: Optional[int] = None,
) -> bool:
    """Haber veya reels kaydını günceller, slaytları yeniden çizer ve onaya sunar."""
    otorite_verisi = None
    if haber.get("detay_metni"):
        try:
            otorite_verisi = json.loads(haber["detay_metni"])
        except Exception:
            otorite_verisi = None

    if not isinstance(otorite_verisi, dict):
        otorite_verisi = {
            "kategori_kodu": haber.get("kategori") or "TAPU_VE_HUKUK",
            "manset_parca_1": yeni_baslik,
            "manset_vurgu": "",
            "manset_parca_2": "",
            "spot": yeni_aciklama or haber.get("orijinal_ozet", ""),
            "bicim": "B1",
        }

    format_turu = otorite_verisi.get("format_turu")

    # Slayt bazlı veya genel başlık güncelleme
    adimlar = otorite_verisi.get("adimlar") or []
    if sira and sira > 1 and adimlar and (sira - 2) < len(adimlar):
        # Spesifik bir slaytın (adımın) düzenlenmesi
        adim = adimlar[sira - 2]
        adim["baslik"] = yeni_baslik
        if yeni_aciklama:
            adim["aciklama"] = yeni_aciklama
            adim["spot"] = yeni_aciklama
    else:
        # Kapak veya genel başlık güncelleme
        if format_turu == "sozluk":
            otorite_verisi["terim"] = yeni_baslik
            if yeni_aciklama:
                otorite_verisi["aciklama"] = yeni_aciklama
        elif format_turu == "nedir_dogrusu":
            otorite_verisi["yanlis"] = yeni_baslik
            if yeni_aciklama:
                otorite_verisi["dogru"] = yeni_aciklama
        elif format_turu == "net_cevap":
            otorite_verisi["soru"] = yeni_baslik
            if yeni_aciklama:
                otorite_verisi["cevap"] = yeni_aciklama
        elif format_turu == "vaka":
            otorite_verisi["vaka"] = yeni_baslik
            if yeni_aciklama:
                otorite_verisi["cozum"] = yeni_aciklama
        else:
            otorite_verisi["manset_parca_1"] = yeni_baslik
            otorite_verisi["manset_vurgu"] = ""
            otorite_verisi["manset_parca_2"] = ""
            if yeni_aciklama:
                otorite_verisi["spot"] = yeni_aciklama

    # Eski geçici dosyaları temizle
    if haber.get("slayt_yollari"):
        try:
            eski_yollar = json.loads(haber["slayt_yollari"])
            for p in eski_yollar:
                Path(p).unlink(missing_ok=True)
        except Exception:
            pass

    # DB güncelle
    guncel_caption = yeni_aciklama if yeni_aciklama else haber.get("ig_caption")
    db.haber_guncelle(
        haber_id,
        manset=yeni_baslik if (not sira or sira == 1) else haber.get("manset"),
        detay_metni=json.dumps(otorite_verisi, ensure_ascii=False),
        ig_caption=guncel_caption,
        slayt_yollari=None,
        slayt_urlleri=None,
        durum="onay_bekliyor",
    )

    # İlgili onay sunumunu çağır
    if haber.get("kategori") == "REELS":
        slayt_yollari = make_image.otorite_gonderi_slaytlari_uret(
            otorite_verisi, cikti_onek=f"reels_{haber_id}", olcu="story"
        )
        slayt_urlleri = []
        try:
            slayt_urlleri = upload_image.coklu_gorsel_yukle(slayt_yollari)
        except Exception as e:
            log.warning("Reels slaytları CDN'e yüklenemedi: %s", e)

        db.haber_guncelle(
            haber_id,
            slayt_yollari=json.dumps([str(p) for p in slayt_yollari], ensure_ascii=False),
            slayt_urlleri=json.dumps(slayt_urlleri) if slayt_urlleri else None,
        )

        telegram_bot.medya_grubu_gonder(
            slayt_yollari,
            caption=f"🎬 <b>EDM REELS SLAYTLARI (9:16 Dikey - Güncellendi)</b>\n📌 {yeni_baslik}",
        )

        caption_metin = generate_text.caption_zenginlestir(
            guncel_caption or yeni_baslik,
            kategori_kodu="REELS",
            platform="instagram",
            manset=yeni_baslik,
        )
        temiz_caption = html.escape(caption_metin.strip())
        mesaj_metni = (
            f"🎬 <b>EDM REELS / VİDEO (GÜNCELLENDİ)</b>\n\n"
            f"📌 <b>Başlık:</b> {html.escape(yeni_baslik)}\n\n"
            f"<pre><code>{temiz_caption}</code></pre>\n\n"
            f"💡 <i>'🚀 Seçili Kanallarda Yayınla' butonuna bastığınızda 1080x1920 MP4 dikey videosu derlenip gruba iletilecektir.</i>"
        )
        reels_kanallari = {"ig": False, "reels": True, "story": True, "threads": True, "facebook": True, "youtube": True, "tiktok": True}
        res = telegram_bot.mesaj_gonder(
            mesaj_metni,
            reply_markup=telegram_bot.ana_menu(adet=len(slayt_yollari) if slayt_yollari else 7, kanallar=reels_kanallari),
        )
        if res and isinstance(res, dict) and "message_id" in res:
            token, chat_id = telegram_bot._bot_bilgileri()
            cid = int(str(chat_id).strip()) if str(chat_id).lstrip("-").isdigit() else None
            db.onay_istegi_kaydet("reels", str(haber_id), res["message_id"], cid)
        return True
    else:
        return telegram_bot.haber_onayina_sun(haber_id)


def ilan_metni_guncelle(
    ilan_id: str,
    yeni_baslik: str,
    yeni_aciklama: Optional[str] = None,
) -> bool:
    """İlan kaydını günceller ve slaytlarını yeniden hazırlayıp sunar."""
    with db._baglanti_al() as conn:
        if yeni_aciklama:
            conn.execute(
                "UPDATE ilanlar SET baslik = ?, aciklama = ? WHERE id = ?",
                (yeni_baslik, yeni_aciklama, ilan_id),
            )
        else:
            conn.execute(
                "UPDATE ilanlar SET baslik = ? WHERE id = ?",
                (yeni_baslik, ilan_id),
            )
        conn.commit()

    return telegram_bot.ilan_postunu_hazirla_ve_sor(ilan_id)


def main():
    parser = argparse.ArgumentParser(description="Telegram Reply ile Başlık ve Metin Düzenleme")
    parser.add_argument("--mesaj-id", default="", help="Yanıtlanan Telegram mesaj ID")
    parser.add_argument("--metin", required=True, help="Kullanıcının yazdığı yeni metin")
    parser.add_argument("--gonderen", default="", help="Mesajı gönderen kullanıcı adı")
    parser.add_argument("--tur", default="", help="Opsiyonel içerik türü (haber/reels/ilan)")
    parser.add_argument("--id", default="", help="Opsiyonel içerik referans ID")
    args = parser.parse_args()

    gelen_metin = (args.metin or "").strip()
    if not gelen_metin:
        telegram_bot.mesaj_gonder("⚠️ Boş metin ile düzenleme yapılamaz.")
        sys.exit(1)

    sira, yeni_baslik, yeni_aciklama = metin_ayristir(gelen_metin)
    if not yeni_baslik:
        telegram_bot.mesaj_gonder("⚠️ Geçerli bir başlık metni bulunamadı.")
        sys.exit(1)

    log.info("Metin düzenleme talebi: sira=%s, baslik=%s, aciklama=%s", sira, yeni_baslik, bool(yeni_aciklama))

    tur = args.tur
    ref_id = args.id
    icerik = None

    # Mesaj ID üzerinden içerik ara
    if args.mesaj_id and str(args.mesaj_id).isdigit():
        mid = int(args.mesaj_id)
        icerik_bilgi = db.mesajdan_icerik_bul(mid)
        if icerik_bilgi:
            tur, ref_id, icerik = icerik_bilgi

    # Bulunamadıysa doğrudan id üzerinden al
    if not icerik and ref_id:
        if tur == "ilan":
            icerik = db.ilan_getir(str(ref_id))
        else:
            icerik = db.haber_getir(int(ref_id) if str(ref_id).isdigit() else ref_id)

    # Hala bulunamadıysa onay bekleyen son kaydı al
    if not icerik:
        icerik_bilgi = db.mesajdan_icerik_bul(0)
        if icerik_bilgi:
            tur, ref_id, icerik = icerik_bilgi

    if not icerik:
        telegram_bot.mesaj_gonder("⚠️ Düzenlenecek aktif içerik bulunamadı.")
        log.error("Düzenlenecek içerik bulunamadı!")
        sys.exit(1)

    log.info("İçerik tespit edildi: tur=%s, ref_id=%s", tur, ref_id)

    basarili = False
    if tur == "ilan":
        basarili = ilan_metni_guncelle(str(ref_id), yeni_baslik, yeni_aciklama)
    else:
        basarili = haber_metni_guncelle(int(ref_id), icerik, yeni_baslik, yeni_aciklama, sira=sira)

    if basarili:
        kullanici_notu = f" ({args.gonderen})" if args.gonderen else ""
        bildirim = (
            f"✅ <b>Metin Düzenlendi{kullanici_notu}</b>\n\n"
            f"📌 <b>Başlık:</b> <i>{html.escape(yeni_baslik)}</i>\n"
        )
        if yeni_aciklama:
            bildirim += f"📝 <b>Açıklama:</b> <i>{html.escape(yeni_aciklama[:150])}...</i>\n"
        bildirim += "\n🎨 <i>Slayt görselleri yeniden çizildi ve güncel onay kartı gruba iletildi.</i>"
        telegram_bot.mesaj_gonder(bildirim)

        try:
            from src import db_senkron
            db_senkron.hemen_kaydet(f"db: metin duzenlendi #{ref_id} ({tur})")
        except Exception as e:
            log.warning("db_senkron hatası: %s", e)
    else:
        telegram_bot.mesaj_gonder("❌ Metin düzenlenirken bir hata oluştu.")
        sys.exit(1)


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
