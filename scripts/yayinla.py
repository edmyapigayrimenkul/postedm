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
from datetime import datetime, timezone
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import db, facebook, hata_bildir, instagram, telegram_bot, threads, tiktok, upload_image, video, youtube

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="EDM Paylaşım Yayınlayıcı")
    parser.add_argument("--tur", required=True, choices=["haber", "ilan", "reels"], help="İçerik türü")
    parser.add_argument("--id", required=True, help="Haber ID veya İlan ID")
    parser.add_argument("--hedef", default="hepsi", help="Hedef platform veya işlem (hepsi, ig, threads, video, reels, fb, reddet, iptal, yenile, manuel_paket, tamamla)")
    parser.add_argument("--yeniden-ciz", action="store_true", help="İlan kartlarını güncel site verisiyle yeniden üret")
    args = parser.parse_args()

    tur = args.tur
    ref_id = args.id
    hedef = args.hedef.lower()
    hedefler = {parca.strip() for parca in hedef.split(",") if parca.strip()}

    def hedef_mi(*adaylar: str) -> bool:
        return "hepsi" in hedefler or bool(hedefler.intersection(adaylar))

    log.info("Yayın süreci başlatılıyor: Tür=%s, ID=%s, Hedef=%s", tur, ref_id, hedef)

    # 0. Reddet / İptal Aksiyonu
    if hedef in ("reddet", "iptal"):
        if tur in ("haber", "reels"):
            db.haber_guncelle(int(ref_id), durum="reddedildi")
            db.onay_istegi_sonuclandir(tur, str(ref_id), "reddedildi")
            tur_adi = "Reels Videosu" if tur == "reels" else "Haber"
            log.info("%s #%s reddedildi olarak işaretlendi.", tur_adi, ref_id)
            telegram_bot.mesaj_gonder(f"❌ <b>{tur_adi} #{ref_id} reddedildi ve arşive kaldırıldı.</b>")
        elif tur == "ilan":
            db.ilan_reddedildi_isaretle(ref_id)
            db.onay_istegi_sonuclandir(tur, str(ref_id), "reddedildi")
            log.info("İlan #%s reddedildi olarak işaretlendi.", ref_id)
            telegram_bot.mesaj_gonder(f"❌ <b>İlan #{ref_id} reddedildi ve arşive kaldırıldı.</b>")
        db.wal_bosalt()
        return

    # 0.1 Çöpe At Aksiyonu (Havuza asla geri dönmez, kalıcı kilitlenir)
    if hedef == "cope_at":
        import re
        if tur in ("haber", "reels"):
            haber = db.haber_getir(int(ref_id))
            db.haber_guncelle(int(ref_id), durum="engellendi")
            konu_kodu = None
            if haber:
                kaynak_str = haber.get("kaynak") or ""
                m = re.search(r"(S\d-\w+)", kaynak_str)
                if m:
                    konu_kodu = m.group(1)
                elif haber.get("orijinal_url"):
                    m2 = re.search(r"edm://(?:konu|reels)/([^/]+)", haber["orijinal_url"])
                    if m2:
                        konu_kodu = m2.group(1)
            if konu_kodu:
                from src import konu_bankasi
                konu_bankasi.kullanildi_isaretle(konu_kodu, haber_id=int(ref_id), sonuc="cope_at")
                log.info("Konu %s kalıcı olarak engellendi (cope_at).", konu_kodu)
            db.onay_istegi_sonuclandir(tur, str(ref_id), "engellendi")
            tur_adi = "Reels Videosu" if tur == "reels" else "İçerik"
            log.info("%s #%s çöpe atıldı ve kalıcı olarak engellendi.", tur_adi, ref_id)
            telegram_bot.mesaj_gonder(f"🗑️ <b>{tur_adi} #{ref_id} kalıcı olarak çöpe atıldı.</b>\n<i>Bu konu havuza bir daha dönmeyecek şekilde kilitlendi.</i>")
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
            caption = haber.get("ig_caption") or haber.get("manset") or haber.get("orijinal_baslik") or ""
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
                f"<pre>{temiz_caption}</pre>\n\n"
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
                f"<pre>{temiz_caption}</pre>\n\n"
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
            from src import generate_text
            generate_text.haber_metinleri_uret(haber)
            db.haber_guncelle(int(ref_id), slayt_yollari=None, slayt_urlleri=None)
            telegram_bot.haber_onayina_sun(int(ref_id))
            telegram_bot.mesaj_gonder(f"🔄 <b>Haber #{ref_id} yeniden üretildi ve onayınıza sunuldu.</b>")
        elif tur == "ilan":
            log.info("İlan #%s için önizleme yeniden hazırlanıyor...", ref_id)
            telegram_bot.ilan_postunu_hazirla_ve_sor(ref_id)
        db.wal_bosalt()
        return

    # 0.6 Metin Özelleştirme Aksiyonları (Özetle / Detaylandır)
    if hedef in ("metin_ozetle", "metin_detaylandir"):
        if tur in ("haber", "reels"):
            haber = db.haber_getir(int(ref_id))
            if not haber:
                from src import db_senkron
                db_senkron.uzaktan_tazele()
                haber = db.haber_getir(int(ref_id))
            if haber:
                from src import generate_text
                ek_talimat = "Metinleri daha vurucu, kısa ve özet olarak hazırla." if hedef == "metin_ozetle" else "İçeriğe daha fazla hukuki derinlik, kanun maddeleri ve hak arama yolları ekle."
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

    # 0.7 Fotoğraf Özelleştirme Aksiyonları (Değiştir / Saf Editoryal)
    if hedef in ("foto_degistir", "foto_editoryal"):
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
                else:
                    detay["foto_degistir"] = True
                db.haber_guncelle(int(ref_id), detay_metni=json.dumps(detay, ensure_ascii=False), slayt_yollari=None, slayt_urlleri=None)
                if tur == "reels":
                    telegram_bot.reels_hazirla_ve_sun()
                else:
                    telegram_bot.haber_onayina_sun(int(ref_id))
                tur_adi = "Reels Videosu" if tur == "reels" else "Haber"
                telegram_bot.mesaj_gonder(f"🖼️ <b>{tur_adi} #{ref_id} görseli güncellendi ve yeni önizleme sunuldu.</b>")
        db.wal_bosalt()
        return

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
        caption = haber.get("ig_caption") or baslik

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

        # 3. Eğer yerel dosyalar bu runner'da yoksa ve detay_metni varsa slaytları yeniden çiz
        if not slayt_yollari or not all(Path(p).exists() for p in slayt_yollari):
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

    # 4. Görselleri imgbb / catbox'a yükle (Sadece görsel gönderileri için)
    if tur in ("haber", "ilan"):
        if not public_urller:
            if slayt_yollari and any(Path(p).exists() for p in slayt_yollari):
                log.info("%d adet slayt görseli CDN'e yükleniyor...", len(slayt_yollari))
                public_urller = upload_image.coklu_gorsel_yukle(slayt_yollari)

        if not public_urller and not slayt_yollari:
            raise RuntimeError("Paylaşılacak slayt görseli bulunamadı.")

        if not public_urller:
            raise RuntimeError("Görseller public URL'e yüklenemedi.")

        # 2. Instagram Yayını (Carousel)
        if hedef_mi("ig", "instagram"):
            log.info("Instagram'da Carousel paylaşılıyor...")
            try:
                ig_id = instagram.carousel_yayinla(public_urller, caption)
                if ig_id:
                    rapor_satirlari.append("📸 <b>Instagram:</b> Paylaşıldı ✓")
                else:
                    rapor_satirlari.append("📸 <b>Instagram:</b> Hata oluştu ✗")
            except Exception as yayin_hatasi:
                log.warning("Instagram yayını hatası: %s", yayin_hatasi)
                rapor_satirlari.append(f"📸 <b>Instagram:</b> Hata ({yayin_hatasi}) ✗")

        # 3. Threads Yayını (4:5 Zincir veya Çoklu Gönderi)
        if hedef_mi("threads"):
            log.info("Threads'te paylaşılıyor...")
            try:
                sayfalar = threads.metinleri_slaytlara_dagit(haber if tur == "haber" else {"manset": baslik, "spot": caption}, public_urller)
                if len(sayfalar) > 1:
                    threads_id = threads.zincir_paylas(sayfalar)
                else:
                    th_metin = (haber.get("threads_metin") if tur in ("haber", "reels") else "") or caption
                    threads_id = threads.paylas(th_metin, public_urller)
                if threads_id:
                    rapor_satirlari.append("🧵 <b>Threads:</b> Paylaşıldı ✓")
                else:
                    rapor_satirlari.append("🧵 <b>Threads:</b> Hata oluştu ✗")
            except Exception as yayin_hatasi:
                log.warning("Threads yayını hatası: %s", yayin_hatasi)
                rapor_satirlari.append(f"🧵 <b>Threads:</b> Hata ({yayin_hatasi}) ✗")

        # 4. Facebook Yayını (Carousel / Albüm)
        if hedef_mi("fb", "facebook"):
            log.info("Facebook sayfasında paylaşılıyor...")
            try:
                fb_id = facebook.paylas(caption, public_urller)
                if fb_id:
                    rapor_satirlari.append("📘 <b>Facebook:</b> Paylaşıldı ✓")
                else:
                    rapor_satirlari.append("📘 <b>Facebook:</b> Hata oluştu ✗")
            except Exception as yayin_hatasi:
                log.warning("Facebook yayını hatası: %s", yayin_hatasi)
                rapor_satirlari.append(f"📘 <b>Facebook:</b> Hata ({yayin_hatasi}) ✗")

    # 5. Video (Sadece REELS için: YouTube Shorts, TikTok, Instagram Reels & Facebook Reels)
    reels_id = None
    if tur == "reels" and hedef_mi("video", "reels", "youtube", "tiktok", "fb", "threads"):
        log.info("Dikey video (Reels/Shorts) hazırlanıyor...")
        video_yolu = None
        if haber and haber.get("video_yolu"):
            vy = Path(haber["video_yolu"])
            if vy.exists():
                video_yolu = vy

        detay = json.loads(haber.get("detay_metni", "{}")) if haber and haber.get("detay_metni") else {}

        if not video_yolu or not video_yolu.exists():
            if not slayt_yollari or not any(Path(p).exists() for p in slayt_yollari):
                from src import make_image
                slayt_listesi = make_image.otorite_gonderi_slaytlari_uret(detay, cikti_onek=f"reels_{ref_id}", olcu="story")
                slayt_yollari = [str(p) for p in slayt_listesi]
            video_girdisi = slayt_yollari if (slayt_yollari and all(Path(p).exists() for p in slayt_yollari)) else public_urller
            try:
                video_yolu = video.slaytlardan_reels_uret(video_girdisi)
            except Exception as video_hatasi:
                log.warning("Dikey video üretim hatası: %s", video_hatasi)
                video_yolu = None

        if video_yolu and video_yolu.exists():
            # A. Instagram Reels (Manuel Trend Müzik Modu)
            if hedef_mi("reels", "ig", "instagram"):
                try:
                    import html as html_lib
                    temiz_metin = html_lib.escape(caption.strip())
                    telegram_bot.video_gonder(
                        video_yolu,
                        aciklama="🎬 <b>EDM Reels Videosu (1080x1920 MP4)</b>\n\n"
                                 "💡 <i>Videoyu cihazınıza kaydedip Instagram uygulamasından trend müzik ekleyerek Reels olarak paylaşabilirsiniz.</i>",
                    )
                    telegram_bot.mesaj_gonder(
                        "📝 <b>Reels Açıklama Metni (Kopyalamak için dokunun):</b>\n"
                        f"<pre>{temiz_metin}</pre>"
                    )
                    rapor_satirlari.append("🎬 <b>Instagram Reels:</b> Video ve metin Telegram'a iletildi (Müzikli paylaşıma hazır) ✓")
                except Exception as re:
                    log.warning("Instagram Reels teslim hatası: %s", re)
                    rapor_satirlari.append(f"🎬 <b>Instagram Reels:</b> Hata ({re}) ✗")

            # B. Facebook Reels (Sayfaya Video/Reels Olarak Yükle)
            if hedef_mi("reels", "fb", "facebook"):
                log.info("Facebook Reels yükleniyor...")
                try:
                    fb_vid_id = facebook.video_yayinla(video_yolu, description=caption)
                    if fb_vid_id:
                        rapor_satirlari.append("📘 <b>Facebook Reels:</b> Paylaşıldı ✓")
                    else:
                        rapor_satirlari.append("📘 <b>Facebook Reels:</b> Hata oluştu ✗")
                except Exception as fe:
                    log.warning("Facebook Reels yayını hatası: %s", fe)
                    rapor_satirlari.append(f"📘 <b>Facebook Reels:</b> Hata ({fe}) ✗")

            # C. YouTube Shorts (Sadece YouTube'a özel telifsiz ambiyans emlak fon müziği ile)
            if hedef_mi("video", "youtube"):
                try:
                    yt_res = youtube.shorts_yukle(video_yolu, baslik=baslik, aciklama=caption)
                    if yt_res.get("durum"):
                        rapor_satirlari.append(f"▶️ <b>YouTube Shorts:</b> <a href='{yt_res.get('url')}'>İzle</a> ✓")
                    else:
                        rapor_satirlari.append(f"▶️ <b>YouTube Shorts:</b> {yt_res.get('hata') or 'Hata oluştu'} ✗")
                except Exception as yayin_hatasi:
                    log.warning("YouTube Shorts yayını hatası: %s", yayin_hatasi)
                    rapor_satirlari.append(f"▶️ <b>YouTube Shorts:</b> Hata ({yayin_hatasi}) ✗")

            # D. TikTok (Sandbox / Inbox Draft Modu)
            if hedef_mi("video", "tiktok"):
                try:
                    tt_res = tiktok.video_yukle(video_yolu, baslik=baslik)
                    if tt_res.get("durum"):
                        if tt_res.get("taslak_mi"):
                            rapor_satirlari.append("🎵 <b>TikTok:</b> Taslak Olarak Yüklendi (Uygulamadan Onaylayın) ✓")
                        else:
                            rapor_satirlari.append("🎵 <b>TikTok:</b> Yüklendi ✓")
                    else:
                        rapor_satirlari.append(f"🎵 <b>TikTok:</b> {tt_res.get('hata') or 'Hata oluştu'} ✗")
                except Exception as yayin_hatasi:
                    log.warning("TikTok yayını hatası: %s", yayin_hatasi)
                    rapor_satirlari.append(f"🎵 <b>TikTok:</b> Hata ({yayin_hatasi}) ✗")

            # E. Threads (Kullanıcı Kuralı: Reels dahi olsa Threads'e 4:5 boyutunda zincir olarak parça parça atılır)
            if hedef_mi("threads"):
                log.info("Reels için Threads'e 4:5 formatında zincir hazırlanıyor...")
                try:
                    from src import make_image
                    slayt_4x5_listesi = make_image.otorite_gonderi_slaytlari_uret(detay, cikti_onek=f"threads_4x5_{ref_id}", olcu="besleme")
                    slayt_4x5_yollari = [str(p) for p in slayt_4x5_listesi]
                    urller_4x5 = upload_image.coklu_gorsel_yukle(slayt_4x5_yollari)
                    if urller_4x5:
                        sayfalar = threads.metinleri_slaytlara_dagit(detay or haber, urller_4x5)
                        threads_id = threads.zincir_paylas(sayfalar)
                        if threads_id:
                            rapor_satirlari.append(f"🧵 <b>Threads:</b> {len(sayfalar)} parçalı 4:5 zincir paylaşıldı ✓")
                        else:
                            rapor_satirlari.append("🧵 <b>Threads:</b> Zincir paylaşılamadı ✗")
                    else:
                        rapor_satirlari.append("🧵 <b>Threads:</b> 4:5 slaytlar CDN'e yüklenemedi ✗")
                except Exception as th_e:
                    log.warning("Reels Threads zincir hatası: %s", th_e)
                    rapor_satirlari.append(f"🧵 <b>Threads:</b> Hata ({th_e}) ✗")
        else:
            if hedef_mi("reels"):
                rapor_satirlari.append("🎬 <b>Instagram Reels:</b> Dikey video üretilemedi ✗")
            if hedef_mi("video", "youtube"):
                rapor_satirlari.append("▶️ <b>YouTube Shorts:</b> Dikey video üretilemedi ✗")
            if hedef_mi("video", "tiktok"):
                rapor_satirlari.append("🎵 <b>TikTok:</b> Dikey video üretilemedi ✗")

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

    # 7. Telegram'a sonuç raporu ilet
    if not rapor_satirlari:
        raise RuntimeError(f"Geçerli yayın hedefi bulunamadı: {hedef}")
    hata_var = any("✗" in satir for satir in rapor_satirlari)
    sonuc_metni = (
        ("⚠️ <b>YAYIN KISMEN TAMAMLANDI</b>\n\n" if hata_var else "🎉 <b>YAYIN BAŞARIYLA TAMAMLANDI</b>\n\n")
        + f"<b>İçerik:</b> {baslik}\n\n"
        + "\n".join(rapor_satirlari)
    )
    try:
        telegram_bot.mesaj_gonder(sonuc_metni)
    except Exception as bildirim_hatasi:
        # Platform yayını tamamlandıktan sonra ikincil Telegram raporu işi
        # başarısız gösterip aynı içeriğin yeniden yayınlanmasına yol açmasın.
        log.warning("Telegram sonuç bildirimi gönderilemedi: %s", bildirim_hatasi)
    print("POSTEDM_SONUC=" + json.dumps({"hedefler": sorted(hedefler), "rapor": rapor_satirlari}, ensure_ascii=False))
    if hata_var:
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
