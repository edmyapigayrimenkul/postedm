#!/usr/bin/env python3
"""
scripts/yayinla.py — Onaylanan İçeriği Platformlarda Yayınlama Komutu
Telegram'dan gelen onay butonuna tıklandığında Cloudflare Worker veya Actions tarafından tetiklenir.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import db, facebook, generate_text, hata_bildir, instagram, ses, telegram_bot, threads, tiktok, upload_image, video, youtube

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="EDM Paylaşım Yayınlayıcı")
    parser.add_argument("--tur", default="haber", choices=["haber", "ilan", "reels"], help="İçerik türü")
    parser.add_argument("--id", default=None, help="Haber ID veya İlan ID")
    parser.add_argument("--mesaj-id", default=None, type=int, help="Telegram mesaj ID")
    parser.add_argument("--hedef", default="hepsi", help="Hedef platform veya işlem")
    parser.add_argument("--yeniden-ciz", action="store_true", help="İlan kartlarını güncel site verisiyle yeniden üret")
    args = parser.parse_args()

    tur = args.tur
    ref_id = args.id
    if (not ref_id or ref_id == "None") and args.mesaj_id:
        bulunan = db.mesajdan_icerik_bul(args.mesaj_id)
        if bulunan:
            tur, ref_id_int, _ = bulunan
            ref_id = str(ref_id_int)
    elif not ref_id or ref_id == "None":
        bulunan = db.mesajdan_icerik_bul(None)
        if bulunan:
            tur, ref_id_int, _ = bulunan
            ref_id = str(ref_id_int)

    if not ref_id:
        log.error("İşlem yapılacak içerik ID'si bulunamadı.")
        return

    hedef = args.hedef.lower()
    hedefler = {parca.strip() for parca in hedef.split(",") if parca.strip()}

    def hedef_mi(*adaylar: str) -> bool:
        return "hepsi" in hedefler or bool(hedefler.intersection(adaylar))

    log.info("Yayın süreci başlatılıyor: Tür=%s, ID=%s, Hedef=%s", tur, ref_id, hedef)

    # 0. Reddet / İptal Aksiyonu (Havuza döner)
    if hedef in ("reddet", "iptal"):
        if tur in ("haber", "reels"):
            db.haber_guncelle(int(ref_id), durum="iptal")
            db.onay_istegi_sonuclandir(tur, str(ref_id), "iptal")
            tur_adi = "Reels Videosu" if tur == "reels" else "İçerik"
            log.info("%s #%s atlandı, konu havuza iade edildi.", tur_adi, ref_id)
            telegram_bot.mesaj_gonder(f"❌ <b>{tur_adi} #{ref_id} atlandı.</b>\n<i>Konu havuza iade edildi. Sıradaki içerik hazırlanıyor...</i>")
            if tur == "reels":
                telegram_bot.reels_hazirla_ve_sun()
            else:
                telegram_bot.konu_bankasindan_hazirla()
        elif tur == "ilan":
            db.ilan_reddedildi_isaretle(ref_id)
            db.onay_istegi_sonuclandir(tur, str(ref_id), "reddedildi")
            log.info("İlan #%s reddedildi olarak işaretlendi.", ref_id)
            telegram_bot.mesaj_gonder(f"❌ <b>İlan #{ref_id} reddedildi ve arşive kaldırıldı.</b>")
        db.wal_bosalt()
        return

    # 0.1 Çöpe At Aksiyonu (Taslak atılır, kullanıcı isteğiyle KONU ASLA KİLİTLENMEZ, havuza iade edilir)
    if hedef == "cope_at":
        if tur in ("haber", "reels"):
            db.haber_guncelle(int(ref_id), durum="iptal")
            db.onay_istegi_sonuclandir(tur, str(ref_id), "iptal")
            tur_adi = "Reels Videosu" if tur == "reels" else "İçerik"
            log.info("%s #%s taslağı çöpe atıldı, konu havuza iade edildi.", tur_adi, ref_id)
            telegram_bot.mesaj_gonder(f"🗑️ <b>{tur_adi} #{ref_id} taslağı çöpe atıldı.</b>\n<i>Konu kilitlenmedi, havuza iade edildi. Sıradaki içerik hazırlanıyor...</i>")
            if tur == "reels":
                telegram_bot.reels_hazirla_ve_sun()
            else:
                telegram_bot.konu_bankasindan_hazirla()
        elif tur == "ilan":
            db.ilan_reddedildi_isaretle(ref_id)
            db.onay_istegi_sonuclandir(tur, str(ref_id), "engellendi")
            log.info("İlan #%s çöpe atıldı ve arşivlendi.", ref_id)
            telegram_bot.mesaj_gonder(f"🗑️ <b>İlan #{ref_id} çöpe atıldı ve arşive kaldırıldı.</b>")
        db.wal_bosalt()
        return

    # 0.2 Ertele Aksiyonu (Hatırlatma sayacını ve süresini sıfırlar)
    if hedef == "ertele":
        db.onay_istegi_ertele(tur, str(ref_id), dakika=60)
        tur_adi = "Reels Videosu" if tur == "reels" else ("İlan" if tur == "ilan" else "İçerik")
        log.info("%s #%s için onay süresi 1 saat ertelendi.", tur_adi, ref_id)
        telegram_bot.mesaj_gonder(f"⏰ <b>{tur_adi} #{ref_id} için yayın 1 saat ertelendi. Hatırlatıcılar duraklatıldı.</b>")
        db.wal_bosalt()
        return

    # 0.3 Manuel Paylaşım Paketi Aksiyonu
    if hedef == "manuel_paket":
        if tur in ("haber", "reels"):
            haber = db.haber_getir(int(ref_id))
            if not haber:
                from src import db_senkron
                db_senkron.uzaktan_tazele()
                haber = db.haber_getir(int(ref_id))
            if not haber:
                log.error("Manuel paket için haber bulunamadı: #%s", ref_id)
                db.wal_bosalt()
                return
            raw_caption = haber.get("ig_caption") or haber.get("manset") or haber.get("orijinal_baslik") or ""
            caption = generate_text.caption_zenginlestir(
                raw_caption,
                kategori_kodu=haber.get("kategori"),
                platform="instagram",
                manset=haber.get("manset") or haber.get("orijinal_baslik"),
            )
            import html as html_lib
            temiz_caption = html_lib.escape(caption.strip())
            butonlar = {
                "inline_keyboard": [
                    [{"text": "📸 Instagram'ı Aç", "url": "https://instagram.com"}],
                    [{"text": "🚀 Diğer Kanallarda Yayınla (Threads, FB)", "callback_data": f"onayla:haber:threads,fb:{ref_id}"}],
                    [{"text": "✅ Paylaştım (Tamamlandı Olarak İşaretle)", "callback_data": f"onayla:haber:tamamla:{ref_id}"}],
                    [{"text": "← Onay Menüsüne Dön", "callback_data": f"onay_menu_don:{ref_id}"}],
                ]
            }
            mesaj = (
                f"📲 <b>MANUEL INSTAGRAM PAYLAŞIM PAKETİ</b>\n\n"
                f"Aşağıdaki açıklama metnini tek tıkla kopyalayıp Instagram uygulamasında veya webde paylaşabilirsiniz:\n\n"
                f"<pre><code>{temiz_caption}</code></pre>\n\n"
                f"💡 <i>Görseller yukarıdaki Telegram albümünde hazır. Tek tıkla telefonunuzun galerisine kaydedebilirsiniz.</i>\n\n"
                f"Paylaşımı tamamladıktan sonra lütfen aşağıdaki <b>Paylaştım</b> butonuna basınız."
            )
            telegram_bot.mesaj_gonder(mesaj, reply_markup=butonlar)
        elif tur == "ilan":
            ilan = db.ilan_getir(ref_id)
            if not ilan:
                from src import db_senkron
                db_senkron.uzaktan_tazele()
                ilan = db.ilan_getir(ref_id)
            if not ilan:
                log.error("Manuel paket için ilan bulunamadı: #%s", ref_id)
                db.wal_bosalt()
                return
            import html as html_lib
            baslik = ilan.get("baslik", "")
            ilan_adresi = ilan.get("kaynak_url") or "https://edmyapigayrimenkul.com/ilanlar"
            caption = f"{baslik}\n\nEDM Yapı & Gayrimenkul · Yatırım Ortağınız\n0536 343 41 97 · {ilan_adresi}"
            temiz_caption = html_lib.escape(caption.strip())
            butonlar = {
                "inline_keyboard": [
                    [{"text": "📸 Instagram'ı Aç", "url": "https://instagram.com"}],
                    [{"text": "✅ Paylaştım (Tamamlandı Olarak İşaretle)", "callback_data": f"onayla:ilan:tamamla:{ref_id}"}],
                ]
            }
            mesaj = (
                f"📲 <b>MANUEL İLAN PAYLAŞIM PAKETİ</b>\n\n"
                f"<pre><code>{temiz_caption}</code></pre>\n\n"
                f"💡 <i>Görseller yukarıdaki albümde hazır. Paylaşımı yaptıktan sonra 'Paylaştım' butonuna dokununuz.</i>"
            )
            telegram_bot.mesaj_gonder(mesaj, reply_markup=butonlar)
        db.wal_bosalt()
        return

    # 0.4 Tamamlandı / Manuel Paylaşıldı Olarak İşaretle
    if hedef in ("tamamla", "manuel_tamam"):
        if tur in ("haber", "reels"):
            haber = db.haber_getir(int(ref_id))
            if not haber:
                from src import db_senkron
                db_senkron.uzaktan_tazele()
                haber = db.haber_getir(int(ref_id))
            simdi = datetime.now(timezone.utc).isoformat()
            db.haber_guncelle(int(ref_id), durum="yayinlandi", yayin_zamani=simdi)
            db.onay_istegi_sonuclandir(tur, str(ref_id), "yayinlandi")
            tur_adi = "Reels Videosu" if tur == "reels" else "İçerik"
            log.info("%s #%s kullanıcı tarafından manuel paylaşıldı ve tamamlandı olarak işaretlendi.", tur_adi, ref_id)
            telegram_bot.mesaj_gonder(f"✅ <b>{tur_adi} #{ref_id} paylaşıldı ve tamamlandı olarak arşivlendi. Tebrikler! 🎉</b>")
        elif tur == "ilan":
            ilan = db.ilan_getir(ref_id)
            if not ilan:
                from src import db_senkron
                db_senkron.uzaktan_tazele()
                ilan = db.ilan_getir(ref_id)
            db.ilan_paylasildi_isaretle(ref_id)
            db.onay_istegi_sonuclandir(tur, str(ref_id), "yayinlandi")
            log.info("İlan #%s kullanıcı tarafından manuel paylaşıldı ve tamamlandı olarak işaretlendi.", ref_id)
            telegram_bot.mesaj_gonder(f"✅ <b>İlan #{ref_id} paylaşıldı ve tamamlandı olarak arşivlendi.</b>")
        db.wal_bosalt()
        return

    # 0.5 Yenile Aksiyonu (Gemini metinleri ve slaytları yeniden üretip onaya sunar)
    if hedef == "yenile":
        db.onay_istegi_sonuclandir(tur, str(ref_id), "yenilendi")
        if tur == "reels":
            log.info("Reels #%s için video ve metin yeniden üretiliyor...", ref_id)
            db.haber_guncelle(int(ref_id), durum="iptal")
            telegram_bot.reels_hazirla_ve_sun()
            telegram_bot.mesaj_gonder(f"🔄 <b>Reels #{ref_id} yerine yeni dikey video hazırlanıp gruba iletildi.</b>")
        elif tur == "haber":
            log.info("Haber #%s için metinler ve slaytlar yeniden hazırlanıyor...", ref_id)
            haber = db.haber_getir(int(ref_id))
            if not haber:
                from src import db_senkron
                db_senkron.uzaktan_tazele()
                haber = db.haber_getir(int(ref_id))
            if not haber:
                log.error("Yenilenecek haber bulunamadı: #%s", ref_id)
                db.wal_bosalt()
                return
            generate_text.haber_metinleri_uret(haber)
            db.haber_guncelle(int(ref_id), slayt_yollari=None, slayt_urlleri=None)
            telegram_bot.haber_onayina_sun(int(ref_id))
            telegram_bot.mesaj_gonder(f"🔄 <b>Haber #{ref_id} yeniden üretildi ve onayınıza sunuldu.</b>")
        elif tur == "ilan":
            log.info("İlan #%s için önizleme yeniden hazırlanıyor...", ref_id)
            telegram_bot.ilan_postunu_hazirla_ve_sor(ref_id)
        db.wal_bosalt()
        return

    # 0.6 Metin Özelleştirme Aksiyonları (Özetle / Detaylandır / Baştan Yaz)
    if hedef in ("metin_ozetle", "metin_detaylandir", "metin_yenile"):
        if tur in ("haber", "reels"):
            haber = db.haber_getir(int(ref_id))
            if not haber:
                from src import db_senkron
                db_senkron.uzaktan_tazele()
                haber = db.haber_getir(int(ref_id))
            if haber:
                if hedef == "metin_ozetle":
                    ek_talimat = "Metinleri daha vurucu, kısa ve net bir özet olarak hazırla."
                elif hedef == "metin_detaylandir":
                    ek_talimat = "İçeriğe daha fazla hukuki derinlik, mevzuat maddeleri ve hak arama yolları ekle."
                else:
                    ek_talimat = "Farklı bir anlatım açısı ve taze bir üslupla baştan hazırla."
                log.info("Metin eylemi (%s) uygulanıyor: #%s", hedef, ref_id)
                generate_text.haber_metinleri_uret(haber, ek_talimat=ek_talimat)
                db.haber_guncelle(int(ref_id), slayt_yollari=None, slayt_urlleri=None)
                if tur == "reels":
                    telegram_bot.reels_hazirla_ve_sun()
                else:
                    telegram_bot.haber_onayina_sun(int(ref_id))
                telegram_bot.mesaj_gonder(f"✍️ <b>Haber #{ref_id} metni güncellendi ({hedef}) ve onayınıza sunuldu.</b>")
        db.wal_bosalt()
        return

    # 0.7 Fotoğraf Özelleştirme Aksiyonları (Değiştir / Saf Editoryal / Stok / AI / Gerçek)
    if hedef in ("foto_degistir", "foto_editoryal", "foto_gercek", "foto_stok", "foto_ai"):
        if tur in ("haber", "reels"):
            haber = db.haber_getir(int(ref_id))
            if not haber:
                from src import db_senkron
                db_senkron.uzaktan_tazele()
                haber = db.haber_getir(int(ref_id))
            if haber:
                detay = json.loads(haber["detay_metni"]) if haber.get("detay_metni") else {}
                if hedef == "foto_editoryal":
                    detay["saf_editoryal"] = True
                elif hedef == "foto_stok":
                    detay["foto_kaynak"] = "stok"
                    detay["foto_degistir"] = True
                elif hedef == "foto_ai":
                    detay["foto_kaynak"] = "ai"
                    detay["foto_degistir"] = True
                elif hedef == "foto_gercek":
                    detay["foto_kaynak"] = "gercek"
                    detay["foto_degistir"] = True
                else:
                    detay["foto_degistir"] = True
                db.haber_guncelle(int(ref_id), detay_metni=json.dumps(detay, ensure_ascii=False), slayt_yollari=None, slayt_urlleri=None)
                if tur == "reels":
                    telegram_bot.reels_hazirla_ve_sun()
                else:
                    telegram_bot.haber_onayina_sun(int(ref_id))
                tur_adi = "Reels Videosu" if tur == "reels" else "Haber"
                telegram_bot.mesaj_gonder(f"🖼️ <b>{tur_adi} #{ref_id} görseli güncellendi ({hedef}) ve yeni önizleme sunuldu.</b>")
        db.wal_bosalt()
        return

    haber = None
    ilan = None
    slayt_yollari = []
    public_urller = []
    caption = ""
    baslik = ""

    if tur in ("haber", "reels"):
        haber = db.haber_getir(int(ref_id))
        if not haber:
            from src import db_senkron
            db_senkron.uzaktan_tazele()
            haber = db.haber_getir(int(ref_id))
        if not haber:
            raise RuntimeError(f"Haber bulunamadı: #{ref_id}")

        baslik = haber.get("manset") or haber.get("orijinal_baslik")
        raw_caption = haber.get("ig_caption") or baslik
        caption = generate_text.caption_zenginlestir(
            raw_caption,
            kategori_kodu=haber.get("kategori"),
            platform="instagram",
            manset=baslik,
        )

        # 1. Önceden yüklenmiş Public URL'leri kontrol et
        urller_json = haber.get("slayt_urlleri")
        if urller_json:
            try:
                public_urller = json.loads(urller_json)
            except Exception:
                public_urller = []

        # 2. Slayt yollarını al
        slayt_json = haber.get("slayt_yollari")
        if slayt_json:
            try:
                slayt_yollari = json.loads(slayt_json)
            except Exception:
                slayt_yollari = []

        # 3. Eğer yerel dosyalar bu runner'da yoksa ve henüz CDN URL'leri de yoksa detay_metni'nden slaytları çiz
        if (not public_urller) and (not slayt_yollari or not all(Path(p).exists() for p in slayt_yollari)):
            detay_str = haber.get("detay_metni")
            if detay_str:
                from src import yeni_formatlar, make_image
                try:
                    otorite_verisi = json.loads(detay_str)
                    if isinstance(otorite_verisi, dict):
                        format_turu = otorite_verisi.get("format_turu")
                        if format_turu in ("sozluk", "nedir_dogrusu", "net_cevap", "vaka"):
                            slayt_listesi = yeni_formatlar.slaytlari_uret(otorite_verisi, format_turu=format_turu, cikti_onek=f"haber_{ref_id}")
                        else:
                            slayt_listesi = make_image.otorite_gonderi_slaytlari_uret(otorite_verisi, cikti_onek=f"haber_{ref_id}", olcu="besleme")
                        slayt_yollari = [str(p) for p in slayt_listesi]
                except Exception as e:
                    log.warning("Slaytlar detay_metni'nden çizilemedi: %s", e)

    elif tur == "ilan":
        ilan = db.ilan_getir(ref_id)
        if not ilan:
            from src import db_senkron
            db_senkron.uzaktan_tazele()
            ilan = db.ilan_getir(ref_id)
        if not ilan:
            raise RuntimeError(f"İlan bulunamadı: #{ref_id}")

        baslik = ilan.get("baslik")
        ilan_adresi = ilan.get("kaynak_url") or "https://edmyapigayrimenkul.com/ilanlar"
        caption = f"{baslik}\n\nEDM Yapı & Gayrimenkul · Yatırım Ortağınız\n0536 343 41 97 · {ilan_adresi}"

        # Slaytları bul veya üret (3'lü Prestij Carousel)
        k1 = KOK / f"data/output/ilan_kapak_{ref_id}.jpg"
        k2 = KOK / f"data/output/ilan_detay_{ref_id}.jpg"
        k3 = KOK / f"data/output/ilan_kapanis_{ref_id}.jpg"

        if args.yeniden_ciz or not (k1.exists() and k2.exists() and k3.exists()):
            from src import make_image
            k1 = make_image.ilan_kapak_slayti_ciz(ilan)
            k2 = make_image.ilan_detay_slayti_ciz(ilan)
            k3 = make_image.ilan_kapanis_slayti_ciz(ilan)

        slayt_yollari = [str(k1), str(k2), str(k3)]

    ig_id = None
    threads_id = None
    fb_id = None
    rapor_satirlari = []

    detay = json.loads(haber.get("detay_metni", "{}")) if (tur in ("haber", "reels") and haber and haber.get("detay_metni")) else {}
    reels_modu = ("reels" in hedefler) or (tur == "reels")

    # 1. Görselleri Hazırla ve CDN'e Yükle (Instagram, TikTok, Threads, Story için)
    if not public_urller:
        if slayt_yollari and any(Path(p).exists() for p in slayt_yollari):
            log.info("%d adet slayt görseli CDN'e yükleniyor...", len(slayt_yollari))
            public_urller = upload_image.coklu_gorsel_yukle(slayt_yollari)

    if not public_urller and not slayt_yollari:
        raise RuntimeError("Paylaşılacak slayt görseli veya video bulunamadı.")

    tek_sayfa = (len(public_urller) <= 1) if public_urller else (len(slayt_yollari) <= 1)

    # 2. Dikey Video & Arkaplan Sesi Hazırlığı (YouTube Shorts her zaman, FB/TT/IG ise Reels modunda)
    paylas_reels = ("reels" in hedefler or ("hepsi" in hedefler and tur == "reels"))
    paylas_ig = ("ig" in hedefler or "instagram" in hedefler or ("hepsi" in hedefler and tur != "reels"))
    if paylas_reels:
        # Kural: İçerik ya Reels ya da Gönderi olarak atılır. Reels aktifse Instagram Feed (görsel gönderi) deaktif edilir.
        paylas_ig = False

    video_lazim = (
        paylas_reels
        or hedef_mi("yt", "youtube", "shorts")
        or (reels_modu and hedef_mi("fb", "facebook"))
        or (reels_modu and hedef_mi("tt", "tiktok"))
    )
    v_yolu = None
    sesli_video_yolu = None
    if video_lazim:
        log.info("Dikey video ve fon müziği hazırlanıyor (FB/YT standart video kuralı)...")
        if haber and haber.get("video_yolu"):
            vy = Path(haber["video_yolu"])
            if vy.exists():
                v_yolu = vy

        if not v_yolu or not v_yolu.exists():
            from src import make_image, yeni_formatlar
            # Önce varsa yeni formatlar (sozluk, nedir_dogrusu, net_cevap, vaka)
            if detay and isinstance(detay, dict) and detay.get("format_turu") in ("sozluk", "nedir_dogrusu", "net_cevap", "vaka"):
                try:
                    fmt = detay["format_turu"]
                    d_slaytlar = yeni_formatlar.slaytlari_uret(detay, format_turu=fmt, cikti_onek=f"reels_{ref_id}")
                    v_yolu = video.slaytlardan_reels_uret([str(p) for p in d_slaytlar])
                except Exception as ve:
                    log.warning("Yeni formatlardan dikey video üretilemedi: %s", ve)

            # Klasik otorite B1
            elif detay:
                try:
                    dikey_slaytlar = make_image.otorite_gonderi_slaytlari_uret(detay, cikti_onek=f"reels_{ref_id}", olcu="story")
                    dikey_yollar = [str(p) for p in dikey_slaytlar]
                    v_yolu = video.slaytlardan_reels_uret(dikey_yollar)
                except Exception as ve:
                    log.warning("Dikey otorite slaytlarından video üretilemedi: %s", ve)

            # Yedek 1: Normal yerel slayt yollarından video üret (tek sayfa ise 6.5 sn sinematik zoom otomatik uygulanır)
            if (not v_yolu or not v_yolu.exists()) and slayt_yollari:
                try:
                    v_yolu = video.slaytlardan_reels_uret(slayt_yollari)
                except Exception as ve:
                    log.warning("Slayt yollarından video üretilemedi: %s", ve)

            # Yedek 2: CDN Public URL'lerinden video üret (Runner diskinde yerel dosya yoksa indirip üretir)
            if (not v_yolu or not v_yolu.exists()) and public_urller:
                try:
                    v_yolu = video.slaytlardan_reels_uret(public_urller)
                except Exception as ve:
                    log.warning("Public URL'lerden video üretilemedi: %s", ve)

            # Yedek 3: İlan ise ve slaytlar diskte yoksa anında çiz ve video üret
            if (not v_yolu or not v_yolu.exists()) and tur == "ilan" and "ilan" in locals() and ilan:
                try:
                    from src import make_image
                    ik1 = make_image.ilan_kapak_slayti_ciz(ilan)
                    ik2 = make_image.ilan_detay_slayti_ciz(ilan)
                    ik3 = make_image.ilan_kapanis_slayti_ciz(ilan)
                    v_yolu = video.slaytlardan_reels_uret([str(ik1), str(ik2), str(ik3)])
                except Exception as ve:
                    log.warning("İlan slaytlarından video üretilemedi: %s", ve)

        if v_yolu and v_yolu.exists():
            # YouTube ve Facebook'a özel telifsiz kurumsal emlak fon müziği miksle
            sesli_video_yolu = ses.sesli_video_hazirla(v_yolu, ses_seviyesi=0.20)
        else:
            log.error("Video üretimi başarısız oldu!")

    # -------------------------------------------------------------
    # CANLI YAYIN DURUMU TAKİBİ HAZIRLIĞI (INSTABOT STANDARDI)
    # -------------------------------------------------------------
    durum_haritasi: dict[str, str] = {}
    if hedef_mi("tt", "tiktok"):
        durum_haritasi["tiktok"] = "⏱️ Sırada"
    if paylas_ig:
        durum_haritasi["instagram"] = "⏱️ Sırada"
    if paylas_reels:
        durum_haritasi["reels"] = "⏱️ Sırada"
    if hedef_mi("story"):
        durum_haritasi["story"] = "⏱️ Sırada"
    if hedef_mi("threads", "th"):
        durum_haritasi["threads"] = "⏱️ Sırada"
    if hedef_mi("fb", "facebook"):
        k_fb = "facebook_reels" if reels_modu else "facebook"
        durum_haritasi[k_fb] = "⏱️ Sırada"
    if hedef_mi("yt", "youtube", "shorts", "video"):
        durum_haritasi["youtube"] = "⏱️ Sırada"

    toplam_yayin_adimi = max(1, len(durum_haritasi))
    guncel_yayin_adimi = 0
    baslangic_ts = time.time()

    def _durum_bildir(kanal: str, durum: str, ilerlet: bool = False) -> None:
        nonlocal guncel_yayin_adimi
        if kanal in durum_haritasi:
            durum_haritasi[kanal] = durum
        if ilerlet:
            guncel_yayin_adimi = min(toplam_yayin_adimi, guncel_yayin_adimi + 1)
        if args.mesaj_id:
            try:
                telegram_bot.canli_yayin_durumu_guncelle(
                    mesaj_id=args.mesaj_id,
                    baslik=baslik,
                    adim=guncel_yayin_adimi,
                    toplam_adim=toplam_yayin_adimi,
                    durum_haritasi=durum_haritasi,
                    baslangic_ts=baslangic_ts,
                )
            except Exception as de:
                log.debug("Canlı durum güncelleme hatası: %s", de)

    if args.mesaj_id and durum_haritasi:
        ilk_k = next(iter(durum_haritasi.keys()))
        _durum_bildir(ilk_k, "⏳ Yükleniyor...", ilerlet=False)

    # -------------------------------------------------------------
    # KANAL 1: TIKTOK (Öncelikli Kanal: Reels seçilmediği sürece Carousel/Foto, tek sayfaysa Resim)
    # -------------------------------------------------------------
    if hedef_mi("tt", "tiktok"):
        _durum_bildir("tiktok", "⏳ Yükleniyor...")
        if reels_modu:
            # TikTok için arkaplan müziksiz (sessiz stereo AAC kanallı) video kullanılır;
            # trend sesler TikTok uygulamasından eklenir.
            tt_video = v_yolu if (v_yolu and v_yolu.exists()) else sesli_video_yolu
            if tt_video and tt_video.exists():
                try:
                    tt_res = tiktok.video_yukle(tt_video, baslik=baslik)
                    if tt_res.get("durum"):
                        if tt_res.get("taslak_mi"):
                            rapor_satirlari.append("🎵 <b>TikTok (Video):</b> Taslak Olarak Yüklendi ✓")
                            tt_baslik = tiktok.baslik_kur(baslik)
                            import html as html_lib
                            telegram_bot.mesaj_gonder(
                                f"🎵 <b>TikTok Taslağı Gelen Kutusuna Yüklendi</b>\n\n"
                                f"📝 <i>Uygulamadan paylaşırken kullanabileceğiniz metin (kopyalamak için dokunun):</i>\n"
                                f"<pre><code>{html_lib.escape(tt_baslik)}</code></pre>"
                            )
                        else:
                            rapor_satirlari.append("🎵 <b>TikTok (Video):</b> Paylaşıldı ✓")
                    else:
                        rapor_satirlari.append(f"🎵 <b>TikTok:</b> {tt_res.get('hata') or 'Hata'} ✗")
                except Exception as tt_e:
                    log.warning("TikTok video yükleme hatası: %s", tt_e)
                    rapor_satirlari.append(f"🎵 <b>TikTok:</b> Hata ({tt_e}) ✗")
            else:
                rapor_satirlari.append("🎵 <b>TikTok:</b> Video üretilemedi ✗")
        else:
            log.info("TikTok'ta fotoğraf/carousel paylaşılıyor (Tek sayfa: %s)...", tek_sayfa)
            try:
                tt_res = tiktok.foto_yayinla(public_urller, baslik=baslik, hazir_video_yolu=v_yolu)
                if tt_res.get("durum"):
                    if tt_res.get("taslak_mi"):
                        rapor_satirlari.append("🎵 <b>TikTok:</b> Taslak Olarak Yüklendi ✓")
                        tt_baslik = tiktok.baslik_kur(baslik)
                        import html as html_lib
                        telegram_bot.mesaj_gonder(
                            f"🎵 <b>TikTok Taslağı Gelen Kutusuna Yüklendi</b>\n\n"
                            f"📝 <i>Uygulamadan paylaşırken kullanabileceğiniz metin (kopyalamak için dokunun):</i>\n"
                            f"<pre><code>{html_lib.escape(tt_baslik)}</code></pre>"
                        )
                    else:
                        tur_etiket = "Tekil Resim" if tek_sayfa else "Carousel"
                        rapor_satirlari.append(f"🎵 <b>TikTok ({tur_etiket}):</b> Paylaşıldı ✓")
                else:
                    rapor_satirlari.append(f"🎵 <b>TikTok:</b> {tt_res.get('hata') or 'Hata'} ✗")
            except Exception as tt_e:
                log.warning("TikTok fotoğraf paylaşım hatası: %s", tt_e)
                rapor_satirlari.append(f"🎵 <b>TikTok:</b> Hata ({tt_e}) ✗")
        _durum_bildir("tiktok", "✅ Yayında" if ("tt_res" in locals() and tt_res.get("durum")) else "❌ Hata", ilerlet=True)

    # -------------------------------------------------------------
    # KANAL 2: INSTAGRAM GÖNDERİ (Feed - Carousel veya Tekil Resim)
    # -------------------------------------------------------------
    paylas_ig = ("ig" in hedefler or "instagram" in hedefler or ("hepsi" in hedefler and tur != "reels"))
    if paylas_ig:
        _durum_bildir("instagram", "⏳ Yükleniyor...")
        log.info("Instagram'da görsel post paylaşılıyor (Tek sayfa: %s)...", tek_sayfa)
        try:
            if tek_sayfa:
                ig_id = instagram.tekil_gorsel_yayinla(public_urller[0], caption)
                if ig_id:
                    rapor_satirlari.append("📸 <b>Instagram (Tekil Resim):</b> Paylaşıldı ✓")
                else:
                    rapor_satirlari.append("📸 <b>Instagram:</b> Hata oluştu ✗")
            else:
                ig_id = instagram.carousel_yayinla(public_urller, caption)
                if ig_id:
                    rapor_satirlari.append("📸 <b>Instagram (Carousel):</b> Paylaşıldı ✓")
                else:
                    rapor_satirlari.append("📸 <b>Instagram:</b> Hata oluştu ✗")
        except Exception as yayin_hatasi:
            log.warning("Instagram yayını hatası: %s", yayin_hatasi)
            rapor_satirlari.append(f"📸 <b>Instagram:</b> Hata ({yayin_hatasi}) ✗")
        _durum_bildir("instagram", "✅ Yayında" if ig_id else "❌ Hata", ilerlet=True)

    # -------------------------------------------------------------
    # KANAL 2.1: INSTAGRAM REELS (9:16 Dikey Video)
    # -------------------------------------------------------------
    video_telegrama_gitti = False
    if paylas_reels:
        _durum_bildir("reels", "⏳ Yükleniyor...")
        # Instagram Reels için Telegram'a iletilen video:
        # Kullanıcı Instagram uygulamasından trend müzik ekleyeceği için arkaplan sesi olmamalıdır!
        ig_reels_video = v_yolu if (v_yolu and v_yolu.exists()) else sesli_video_yolu
        if ig_reels_video and ig_reels_video.exists():
            try:
                import html as html_lib
                telegram_bot.video_gonder(
                    ig_reels_video,
                    aciklama=f"🎬 <b>EDM Reels Videosu (1080x1920 MP4)</b>\n\n"
                             f"📌 <b>Konu:</b> {html_lib.escape(baslik)}\n\n"
                             f"💡 <i>Videoyu cihazınıza kaydedip Instagram uygulamasından trend müzik ekleyerek Reels olarak paylaşabilirsiniz.</i>",
                )
                video_telegrama_gitti = True
                rapor_satirlari.append("🎬 <b>Instagram Reels:</b> Video ve açıklama Telegram'a iletildi ✓")
            except Exception as re:
                log.warning("Instagram Reels teslim hatası: %s", re)
                rapor_satirlari.append(f"🎬 <b>Instagram Reels:</b> Hata ({re}) ✗")
        else:
            rapor_satirlari.append("🎬 <b>Instagram Reels:</b> Video üretilemedi ✗")
        _durum_bildir("reels", "✅ Yayında" if video_telegrama_gitti else "❌ Hata", ilerlet=True)

    # -------------------------------------------------------------
    # KANAL 3: STORY (Instagram & Facebook Story — 9:16 Dikey Format)
    # -------------------------------------------------------------
    if hedef_mi("story"):
        _durum_bildir("story", "⏳ Yükleniyor...")
        log.info("Instagram ve Facebook Story paylaşılıyor...")
        story_url = None
        try:
            from PIL import Image
            from src import make_image
            story_dosya = KOK / f"data/output/story_{ref_id}.jpg"
            story_dosya.parent.mkdir(parents=True, exist_ok=True)

            hazir_yol = None

            # 1. Eğer bu oturumda dikey_slaytlar üretildiyse (Reels modunda), ilk slayt tam 1080x1920'dir
            if "dikey_slaytlar" in locals() and dikey_slaytlar and Path(dikey_slaytlar[0]).exists():
                hazir_yol = Path(dikey_slaytlar[0])

            # 2. Eğer detay yeni formatlardansa, ilk slaytı al ve 9:16'ya uyarla
            elif detay and isinstance(detay, dict) and detay.get("format_turu") in ("sozluk", "nedir_dogrusu", "net_cevap", "vaka"):
                try:
                    from src import yeni_formatlar
                    fmt = detay["format_turu"]
                    d_slaytlar = yeni_formatlar.slaytlari_uret(detay, format_turu=fmt, cikti_onek=f"story_{ref_id}")
                    if d_slaytlar and Path(d_slaytlar[0]).exists():
                        hazir_yol = Path(d_slaytlar[0])
                except Exception as de:
                    log.warning("Yeni format story üretim hatası: %s", de)

            # 3. Eğer detay (içerik sözlüğü) varsa, doğrudan native 9:16 Story kapağı üret (en kaliteli & hatasız yol)
            elif detay:
                try:
                    with make_image.tuval("story"):
                        hazir_yol = Path(make_image.otorite_slayt_1_kapak(detay, str(story_dosya)))
                except Exception as de:
                    log.warning("Story native 9:16 üretim hatası: %s", de)

            # 4. Eğer ilan ise, ilan kapak slaytı üret
            elif tur == "ilan" and ilan:
                try:
                    ilan_kapak = make_image.ilan_kapak_slayti_ciz(ilan)
                    if ilan_kapak and Path(ilan_kapak).exists():
                        hazir_yol = Path(ilan_kapak)
                except Exception as ie:
                    log.warning("İlan story kapak hatası: %s", ie)

            # 5. Yerel ilk slayt dosyası diskte varsa
            elif slayt_yollari and Path(slayt_yollari[0]).exists():
                hazir_yol = Path(slayt_yollari[0])

            # 6. Disk boş ama CDN/public URL varsa indir
            elif public_urller:
                try:
                    import requests
                    resp = requests.get(public_urller[0], timeout=15)
                    if resp.status_code == 200:
                        with open(story_dosya, "wb") as f:
                            f.write(resp.content)
                        hazir_yol = story_dosya
                except Exception as ue:
                    log.warning("Story public URL indirme hatası: %s", ue)

            # Son dokunuş: Görsel varsa ve (1080, 1920) değilse 9:16'ya orantılı uyarla
            if hazir_yol and hazir_yol.exists():
                with Image.open(hazir_yol) as im:
                    if im.size == (1080, 1920):
                        im.save(story_dosya, "JPEG", quality=95, optimize=True)
                    else:
                        s_img = video._cercevele_9_16(im)
                        s_img.save(story_dosya, "JPEG", quality=95, optimize=True)
                story_url = upload_image.gorsel_yukle(story_dosya)
        except Exception as se:
            log.warning("Story görseli hazırlanamadı: %s", se)

        if story_url:
            # A. Instagram Story
            try:
                ig_story_id = instagram.story_yayinla(story_url)
                if ig_story_id:
                    rapor_satirlari.append("📱 <b>Instagram Story:</b> Paylaşıldı ✓")
                else:
                    rapor_satirlari.append("📱 <b>Instagram Story:</b> Hata oluştu ✗")
            except Exception as ise:
                log.warning("Instagram Story hatası: %s", ise)
                rapor_satirlari.append(f"📱 <b>Instagram Story:</b> Hata ({ise}) ✗")

            # B. Facebook Story
            try:
                fb_story_id = facebook.story_yayinla(story_url)
                if fb_story_id:
                    rapor_satirlari.append("📘 <b>Facebook Story:</b> Paylaşıldı ✓")
                else:
                    rapor_satirlari.append("📘 <b>Facebook Story:</b> Hata oluştu ✗")
            except Exception as fse:
                log.warning("Facebook Story hatası: %s", fse)
                rapor_satirlari.append(f"📘 <b>Facebook Story:</b> Hata ({fse}) ✗")
        else:
            rapor_satirlari.append("📱 <b>Story:</b> Görsel hazırlanamadı ✗")
        _durum_bildir("story", "✅ Yayında" if story_url else "❌ Hata", ilerlet=True)

    # -------------------------------------------------------------
    # KANAL 4: THREADS (Kullanıcı Kuralı: Her zaman 4:5 Fotoğraf ve Zincir yapısında)
    # -------------------------------------------------------------
    if hedef_mi("threads"):
        _durum_bildir("threads", "⏳ Yükleniyor...")
        try:
            threads_urller = None

            # 1. Eğer detay içinde önceden üretilmiş 4:5 URL'ler varsa doğrudan kullan
            if detay and isinstance(detay, dict) and detay.get("slayt_4x5_urlleri"):
                threads_urller = detay["slayt_4x5_urlleri"]

            # 2. Eğer Reels modundaysa (veya tur == "reels") slaytlar 9:16 dikey üretilmiştir;
            # Threads için detay metninden native 4:5 (1080x1350) besleme slaytları üret ve CDN'e yükle
            if not threads_urller and (reels_modu or tur == "reels") and detay:
                try:
                    from src import make_image
                    besleme_slaytlar = make_image.otorite_gonderi_slaytlari_uret(
                        detay, cikti_onek=f"threads_4x5_{ref_id}", olcu="besleme"
                    )
                    if besleme_slaytlar:
                        threads_urller = upload_image.coklu_gorsel_yukle([str(p) for p in besleme_slaytlar])
                        log.info("Threads için native 4:5 slaytlar üretildi ve yüklendi (%d adet)", len(threads_urller))
                except Exception as b_err:
                    log.warning("Threads native 4:5 slayt üretim hatası: %s", b_err)

            # 3. Eğer yerel slayt yolları varsa ve dikey 9:16 ise 4:5'e kırpıp yükle
            if not threads_urller and slayt_yollari and any(Path(p).exists() for p in slayt_yollari):
                try:
                    threads_urller = instagram.gorselleri_4_5_yap(slayt_yollari)
                except Exception as c_err:
                    log.warning("Threads yerel dosya 4:5 kırpma hatası: %s", c_err)

            # 4. Standart haber / ilan durumunda veya yedek olarak public_urller'i kullan
            if not threads_urller:
                threads_urller = public_urller

            th_tek_sayfa = (len(threads_urller) <= 1) if threads_urller else tek_sayfa
            log.info("Threads'te paylaşılıyor (Tek sayfa: %s, Görsel sayısı: %d, 4:5 formatında)...", th_tek_sayfa, len(threads_urller) if threads_urller else 0)

            if th_tek_sayfa:
                th_metin = (haber.get("threads_metin") if haber and tur in ("haber", "reels") else "") or caption
                th_metin = generate_text.caption_zenginlestir(
                    th_metin,
                    kategori_kodu=haber.get("kategori") if haber else None,
                    platform="threads",
                    manset=baslik,
                )
                threads_id = threads.paylas(th_metin, [threads_urller[0]] if threads_urller else None)
                if threads_id:
                    rapor_satirlari.append("🧵 <b>Threads (Tekil Görsel):</b> 4:5 paylaşıldı ✓")
                else:
                    rapor_satirlari.append("🧵 <b>Threads:</b> Hata oluştu ✗")
            else:
                sayfalar = threads.metinleri_slaytlara_dagit(haber if tur in ("haber", "reels") else {"manset": baslik, "spot": caption}, threads_urller)
                if len(sayfalar) > 1:
                    threads_id = threads.zincir_paylas(sayfalar)
                    if threads_id:
                        rapor_satirlari.append(f"🧵 <b>Threads:</b> {len(sayfalar)} parçalı 4:5 zincir paylaşıldı ✓")
                    else:
                        rapor_satirlari.append("🧵 <b>Threads:</b> Hata oluştu ✗")
                else:
                    th_metin = (haber.get("threads_metin") if haber and tur in ("haber", "reels") else "") or caption
                    th_metin = generate_text.caption_zenginlestir(
                        th_metin,
                        kategori_kodu=haber.get("kategori") if haber else None,
                        platform="threads",
                        manset=baslik,
                    )
                    threads_id = threads.paylas(th_metin, threads_urller)
                    if threads_id:
                        rapor_satirlari.append("🧵 <b>Threads:</b> 4:5 paylaşıldı ✓")
                    else:
                        rapor_satirlari.append("🧵 <b>Threads:</b> Hata oluştu ✗")
        except Exception as yayin_hatasi:
            log.warning("Threads yayını hatası: %s", yayin_hatasi)
            rapor_satirlari.append(f"🧵 <b>Threads:</b> Hata ({yayin_hatasi}) ✗")
        _durum_bildir("threads", "✅ Yayında" if ("threads_id" in locals() and threads_id) else "❌ Hata", ilerlet=True)

    # -------------------------------------------------------------
    # KANAL 5: FACEBOOK (Kullanıcı Kuralı: Standart gönderide Albüm/Fotoğraf, Reels seçildiyse Reels videosu)
    # -------------------------------------------------------------
    if hedef_mi("fb", "facebook"):
        k_fb = "facebook_reels" if reels_modu else "facebook"
        _durum_bildir(k_fb, "⏳ Yükleniyor...")
        fb_caption = (detay.get("caption_facebook") if isinstance(detay, dict) else "") or caption
        fb_caption = generate_text.caption_zenginlestir(
            fb_caption,
            kategori_kodu=haber.get("kategori") if haber else None,
            platform="facebook",
            manset=baslik,
        )
        if reels_modu:
            log.info("Facebook Reels yükleniyor (Arkaplan sesli)...")
            if sesli_video_yolu and sesli_video_yolu.exists():
                try:
                    fb_id = facebook.video_yayinla(sesli_video_yolu, description=fb_caption)
                    if fb_id:
                        rapor_satirlari.append("📘 <b>Facebook (Reels):</b> Paylaşıldı ✓")
                    else:
                        rapor_satirlari.append("📘 <b>Facebook Reels:</b> Hata oluştu ✗")
                except Exception as fe:
                    log.warning("Facebook Reels yayını hatası: %s", fe)
                    rapor_satirlari.append(f"📘 <b>Facebook Reels:</b> Hata ({fe}) ✗")
            else:
                rapor_satirlari.append("📘 <b>Facebook Reels:</b> Dikey video üretilemedi ✗")
        else:
            log.info("Facebook'ta standart gönderi paylaşılıyor (Albüm/Görsel)...")
            try:
                fb_id = facebook.paylas(fb_caption, public_urller)
                if fb_id:
                    rapor_satirlari.append("📘 <b>Facebook (Standart Gönderi):</b> Paylaşıldı ✓")
                else:
                    rapor_satirlari.append("📘 <b>Facebook:</b> Hata oluştu ✗")
            except Exception as fe:
                log.warning("Facebook standart paylaşım hatası: %s", fe)
                rapor_satirlari.append(f"📘 <b>Facebook:</b> Hata ({fe}) ✗")
        _durum_bildir(k_fb, "✅ Yayında" if ("fb_id" in locals() and fb_id) else "❌ Hata", ilerlet=True)

    # -------------------------------------------------------------
    # KANAL 6: YOUTUBE (Kullanıcı Kuralı: YouTube Shorts HER ZAMAN paylaşılır ve arkaplan sesli)
    # -------------------------------------------------------------
    if hedef_mi("yt", "youtube", "shorts", "video"):
        _durum_bildir("youtube", "⏳ Yükleniyor...")
        log.info("YouTube Shorts yükleniyor (Arkaplan sesli)...")
        if sesli_video_yolu and sesli_video_yolu.exists():
            try:
                yt_res = youtube.shorts_yukle(sesli_video_yolu, baslik=baslik, aciklama=caption)
                if yt_res.get("durum"):
                    rapor_satirlari.append(f"▶️ <b>YouTube Shorts:</b> <a href='{yt_res.get('url')}'>İzle</a> ✓")
                else:
                    rapor_satirlari.append(f"▶️ <b>YouTube Shorts:</b> {yt_res.get('hata') or 'Hata oluştu'} ✗")
            except Exception as yayin_hatasi:
                log.warning("YouTube Shorts yayını hatası: %s", yayin_hatasi)
                rapor_satirlari.append(f"▶️ <b>YouTube Shorts:</b> Hata ({yayin_hatasi}) ✗")
        else:
            rapor_satirlari.append("▶️ <b>YouTube Shorts:</b> Dikey video üretilemedi ✗")
        _durum_bildir("youtube", "✅ Yayında" if ("yt_res" in locals() and yt_res.get("durum")) else "❌ Hata", ilerlet=True)


    # 6. Veritabanını güncelle
    herhangi_biri_basarili = any("✓" in satir for satir in rapor_satirlari)
    if tur in ("haber", "reels"):
        guncelleme = {}
        if herhangi_biri_basarili:
            guncelleme["durum"] = "yayinlandi"
            guncelleme["yayin_zamani"] = datetime.now(timezone.utc).isoformat()
        else:
            guncelleme["durum"] = "hata"
        if ig_id:
            guncelleme["instagram_post_id"] = ig_id
        if threads_id:
            guncelleme["threads_post_id"] = threads_id
        if "yt_res" in locals() and yt_res.get("durum") and yt_res.get("video_id"):
            guncelleme["youtube_video_id"] = yt_res.get("video_id")
        if "tt_res" in locals() and tt_res.get("durum") and tt_res.get("publish_id"):
            guncelleme["tiktok_publish_id"] = tt_res.get("publish_id")
        db.haber_guncelle(int(ref_id), **guncelleme)
    elif tur == "ilan" and herhangi_biri_basarili:
        db.ilan_paylasildi_isaretle(ref_id)

    db.onay_istegi_sonuclandir(tur, str(ref_id), "yayinlandi" if herhangi_biri_basarili else "hata")
    db.wal_bosalt()

    # 7. Telegram'a sonuç raporu, canlı linkler ve telafi butonları ilet
    if not rapor_satirlari:
        raise RuntimeError(f"Geçerli yayın hedefi bulunamadı: {hedef}")
    hata_var = any("✗" in satir for satir in rapor_satirlari)

    import html as html_lib
    temiz_caption = html_lib.escape(caption.strip())

    sonuc_metni = (
        ("⚠️ <b>YAYIN KISMEN TAMAMLANDI</b>\n\n" if hata_var else "🎉 <b>YAYIN BAŞARIYLA TAMAMLANDI</b>\n\n")
        + f"<b>İçerik:</b> {html_lib.escape(baslik)}\n\n"
        + "\n".join(rapor_satirlari)
    )

    # Canlı bağlantı butonları
    canli_linkler = []
    if ig_id:
        canli_linkler.append({"text": "📸 Instagram'da Gör", "url": f"https://www.instagram.com/p/{ig_id}/"})
    if threads_id:
        th_url = threads.post_baglantisi(threads_id)
        if th_url:
            canli_linkler.append({"text": "🧵 Threads'te Gör", "url": th_url})
    if "fb_id" in locals() and fb_id:
        fb_url = facebook.post_baglantisi(fb_id)
        if fb_url:
            canli_linkler.append({"text": "📘 Facebook'ta Gör", "url": fb_url})
    if "yt_res" in locals() and yt_res.get("durum") and yt_res.get("url"):
        canli_linkler.append({"text": "▶️ Shorts'ta İzle", "url": yt_res.get("url")})

    canli_link_dugmeleri = [canli_linkler[i:i + 2] for i in range(0, len(canli_linkler), 2)]

    # Hata veren kanallar için anında tek tıkla telafi butonları
    telafi_dugmeleri = []
    if paylas_ig and not ig_id:
        telafi_dugmeleri.append([{"text": "🔄 📸 Instagram'ı Tekrar Dene", "callback_data": f"retry_kanal:ig:{ref_id}"}])
    if hedef_mi("threads", "th") and not threads_id:
        telafi_dugmeleri.append([{"text": "🔄 🧵 Threads'i Tekrar Gönder", "callback_data": f"retry_kanal:threads:{ref_id}"}])
    if hedef_mi("fb", "facebook") and not locals().get("fb_id"):
        telafi_dugmeleri.append([{"text": "🔄 📘 Facebook'a Tekrar Gönder", "callback_data": f"retry_kanal:facebook:{ref_id}"}])
    if hedef_mi("yt", "youtube", "shorts") and not locals().get("yt_res", {}).get("durum"):
        telafi_dugmeleri.append([{"text": "🔄 ▶️ Shorts'a Tekrar Yükle", "callback_data": f"retry_kanal:youtube:{ref_id}"}])
    if hedef_mi("tt", "tiktok") and not locals().get("tt_res", {}).get("durum"):
        telafi_dugmeleri.append([{"text": "🔄 🎵 TikTok'a Tekrar Yükle", "callback_data": f"retry_kanal:tiktok:{ref_id}"}])
    if paylas_reels and (not locals().get("ig_reels_video") or not Path(ig_reels_video).exists()):
        telafi_dugmeleri.append([{"text": "🔄 🎬 Reels'i Tekrar Gönder", "callback_data": f"retry_kanal:reels:{ref_id}"}])

    if len(telafi_dugmeleri) > 1:
        telafi_dugmeleri.insert(0, [{"text": "🔄 Başarısız Tüm Kanalları Tekrar Dene", "callback_data": f"retry_kanal:hepsi:{ref_id}"}])

    sonuc_tuslari = canli_link_dugmeleri + telafi_dugmeleri
    reply_markup = {"inline_keyboard": sonuc_tuslari} if sonuc_tuslari else None

    try:
        telegram_bot.sonucu_yaz(
            args.mesaj_id,
            sonuc_metni,
            bildir=True,
            reply_markup=reply_markup,
        )
    except Exception as bildirim_hatasi:
        # Platform yayını tamamlandıktan sonra ikincil Telegram raporu işi
        # başarısız gösterip aynı içeriğin yeniden yayınlanmasına yol açmasın.
        log.warning("Telegram sonuç bildirimi gönderilemedi: %s", bildirim_hatasi)

    # 8. Hazırlanan 9:16 Dikey Videoyu Telegram Grubuna İlet (Henüz iletilmediyse)
    gonderilecek_video = v_yolu if (v_yolu and v_yolu.exists()) else sesli_video_yolu
    if gonderilecek_video and gonderilecek_video.exists() and not video_telegrama_gitti:
        try:
            log.info("Hazırlanan dikey video Telegram grubuna iletiliyor: %s", gonderilecek_video)
            telegram_bot.video_gonder(
                gonderilecek_video,
                aciklama=f"🎬 <b>EDM Hazır Dikey Video (1080x1920 MP4)</b>\n\n"
                         f"📌 <b>Konu:</b> {html_lib.escape(baslik)}\n\n"
                         f"💡 <i>Videoyu telefonunuza kaydedip Instagram uygulamasından trend müzik ekleyerek Reels olarak paylaşabilirsiniz.</i>",
            )
            video_telegrama_gitti = True
        except Exception as ve:
            log.warning("Telegram'a video iletilemedi: %s", ve)

    # 9. Kopyalanabilir Açıklama Metnini Ayrı ve Eksiksiz İlet (Instabot Standardı)
    try:
        telegram_bot.mesaj_gonder(
            f"📝 <b>Açıklama Metni (Kopyalamak için dokunun):</b>\n\n"
            f"<pre><code>{temiz_caption}</code></pre>"
        )
    except Exception as ce:
        log.warning("Kopyalanabilir açıklama metni iletilemedi: %s", ce)
    print("POSTEDM_SONUC=" + json.dumps({"hedefler": sorted(hedefler), "rapor": rapor_satirlari}, ensure_ascii=False))
    if hata_var:
        # Hata detayını son_hata.txt'ye yaz ki teşhis modülü tam nedenini bilsin
        try:
            hata_satirlari = [r for r in rapor_satirlari if "✗" in r or "Hata" in r]
            if hata_satirlari:
                from src import hata_bildir
                hata_bildir.son_ham_hata_kaydet("\n".join(hata_satirlari))
        except Exception:
            pass
        raise RuntimeError("Bir veya daha fazla sosyal medya yayını başarısız oldu.")
    log.info("Yayınlama süreci tamamlandı.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.exception("Yayınlama esnasında kritik hata: %s", e)
        # Eğer zaten özet sonuç raporu (rapor_satirlari) Telegram'a iletildiyse,
        # ikinci bir mükerrer teknik hata kartı gönderip grubu kirletme.
        if "Bir veya daha fazla sosyal medya yayını başarısız oldu" not in str(e):
            hata_bildir.telegrama_hata_bildir("Sosyal Medya Yayını", istisna=e)
        sys.exit(1)
    finally:
        db.wal_bosalt()
