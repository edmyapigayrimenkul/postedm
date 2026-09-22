#!/usr/bin/env python3
"""
scripts/yayinla.py — Onaylanan İçeriği Platformlarda Yayınlama Komutu
Telegram'dan gelen onay butonuna tıklandığında Cloudflare Worker veya Actions tarafından tetiklenir.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import html as html_lib
import json
import logging
import sys
import threading
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

    # 0.7 Fotoğraf Özelleştirme Aksiyonları (Değiştir / Saf Editoryal / Stok / AI / Gerçek / İlk)
    if hedef in ("foto_degistir", "foto_editoryal", "foto_gercek", "foto_stok", "foto_ai", "foto_ilk"):
        if tur in ("haber", "reels"):
            haber = db.haber_getir(int(ref_id))
            if not haber:
                from src import db_senkron
                db_senkron.uzaktan_tazele()
                haber = db.haber_getir(int(ref_id))
            if haber:
                detay = json.loads(haber["detay_metni"]) if haber.get("detay_metni") else {}
                if hedef == "foto_ilk":
                    detay.pop("foto_kaynak", None)
                    detay.pop("saf_editoryal", None)
                    detay.pop("foto_degistir", None)
                elif hedef == "foto_editoryal":
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
                        if (
                            format_turu in ("sozluk", "nedir_dogrusu", "net_cevap", "vaka", "dailybrief", "haber", "haber_dailybrief")
                            or otorite_verisi.get("bicim") in ("haber", "B5")
                        ):
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

    # 2. Dikey Video & Arkaplan Sesi Hazırlığı (YouTube Shorts, FB Reels, TikTok ve Telegram için)
    paylas_reels = ("reels" in hedefler or ("hepsi" in hedefler and tur == "reels"))
    paylas_ig = ("ig" in hedefler or "instagram" in hedefler or ("hepsi" in hedefler and tur != "reels"))
    if paylas_reels:
        # Kural: İçerik ya Reels ya da Gönderi olarak atılır. Reels aktifse Instagram Feed (görsel gönderi) deaktif edilir.
        paylas_ig = False

    video_lazim = (
        paylas_reels
        or hedef_mi("yt", "youtube", "shorts", "video")
        or (reels_modu and hedef_mi("fb", "facebook"))
        or (reels_modu and hedef_mi("tt", "tiktok"))
    )

    v_yolu = None
    sesli_video_yolu = None
    if video_lazim:
        log.info("Dikey video ve fon müziği hazırlanıyor (Shorts, Reels & Telegram video çıktısı)...")
        if haber and haber.get("video_yolu"):
            vy = Path(haber["video_yolu"])
            if vy.exists():
                v_yolu = vy

        # 3.0. AI Seslendirme (ElevenLabs Voiceover - Dikey Videolar İçin)
        konusma_sesi_yolu = None
        ses_hedef_sure = None
        if video_lazim and (not v_yolu or not v_yolu.exists()):
            try:
                ses_metni = ""
                if baslik:
                    ses_metni = str(baslik)
                if detay and isinstance(detay, dict):
                    spot_txt = detay.get("spot") or ""
                    if spot_txt and spot_txt != baslik:
                        ses_metni = f"{ses_metni}. {spot_txt}" if ses_metni else spot_txt
                elif haber.get("spot"):
                    spot_val = str(haber.get("spot"))
                    ses_metni = f"{ses_metni}. {spot_val}" if ses_metni else spot_val

                if ses_metni and len(ses_metni.strip()) > 10:
                    konusma_sesi_yolu = ses.metin_seslendir(ses_metni)
                    if konusma_sesi_yolu and konusma_sesi_yolu.exists():
                        ses_hedef_sure = ses.ses_suresi_ogren(konusma_sesi_yolu)
                        log.info("ElevenLabs seslendirmesi hazır: %s (%.1f sn)", konusma_sesi_yolu.name, ses_hedef_sure)
            except Exception as tts_e:
                log.warning("AI seslendirme üretilemedi, müzik moduyla devam: %s", tts_e)

        if not v_yolu or not v_yolu.exists():
            from src import make_image, yeni_formatlar
            haber_bilgi = detay if (detay and isinstance(detay, dict)) else (haber if isinstance(haber, dict) else None)
            if detay and isinstance(detay, dict) and detay.get("format_turu") in ("sozluk", "nedir_dogrusu", "net_cevap", "vaka"):
                try:
                    fmt = detay["format_turu"]
                    d_slaytlar = yeni_formatlar.slaytlari_uret(detay, format_turu=fmt, cikti_onek=f"reels_{ref_id}")
                    v_yolu = video.slaytlardan_reels_uret([str(p) for p in d_slaytlar], hedef_sure=ses_hedef_sure, haber=haber_bilgi)
                except Exception as ve:
                    log.warning("Yeni formatlardan dikey video üretilemedi: %s", ve)

            elif detay:
                try:
                    dikey_slaytlar = make_image.otorite_gonderi_slaytlari_uret(detay, cikti_onek=f"reels_{ref_id}", olcu="story")
                    dikey_yollar = [str(p) for p in dikey_slaytlar]
                    v_yolu = video.slaytlardan_reels_uret(dikey_yollar, hedef_sure=ses_hedef_sure, haber=haber_bilgi)
                except Exception as ve:
                    log.warning("Dikey otorite slaytlarından video üretilemedi: %s", ve)

            if (not v_yolu or not v_yolu.exists()) and slayt_yollari:
                try:
                    v_yolu = video.slaytlardan_reels_uret(slayt_yollari, hedef_sure=ses_hedef_sure, haber=haber_bilgi)
                except Exception as ve:
                    log.warning("Slayt yollarından video üretilemedi: %s", ve)

            if (not v_yolu or not v_yolu.exists()) and public_urller:
                try:
                    v_yolu = video.slaytlardan_reels_uret(public_urller, hedef_sure=ses_hedef_sure, haber=haber_bilgi)
                except Exception as ve:
                    log.warning("Public URL'lerden video üretilemedi: %s", ve)

            if (not v_yolu or not v_yolu.exists()) and tur == "ilan" and "ilan" in locals() and ilan:
                try:
                    from src import make_image
                    ik1 = make_image.ilan_kapak_slayti_ciz(ilan)
                    ik2 = make_image.ilan_detay_slayti_ciz(ilan)
                    ik3 = make_image.ilan_kapanis_slayti_ciz(ilan)
                    v_yolu = video.slaytlardan_reels_uret([str(ik1), str(ik2), str(ik3)], hedef_sure=ses_hedef_sure)
                except Exception as ve:
                    log.warning("İlan slaytlarından video üretilemedi: %s", ve)

        if v_yolu and v_yolu.exists():
            try:
                sesli_video_yolu = ses.sesli_video_hazirla(
                    v_yolu,
                    konusma_sesi=konusma_sesi_yolu,
                    ses_seviyesi=0.14 if konusma_sesi_yolu else 0.20,
                )
            except Exception as se:
                log.warning("Fon müziği mikslenemedi: %s", se)
                sesli_video_yolu = v_yolu

    # -------------------------------------------------------------
    # 4. INSTABOT PARİTELİ PARALEL DAĞITIM MOTORU (ThreadPoolExecutor)
    # -------------------------------------------------------------
    hedef_kanallar: list[str] = []
    if hedef_mi("tt", "tiktok"):
        hedef_kanallar.append("tiktok")
    if paylas_reels:
        hedef_kanallar.append("reels")
    elif paylas_ig:
        hedef_kanallar.append("instagram")
    if hedef_mi("story"):
        hedef_kanallar.append("story")
    if hedef_mi("threads", "th"):
        hedef_kanallar.append("threads")
    if hedef_mi("fb", "facebook"):
        hedef_kanallar.append("facebook_reels" if reels_modu else "facebook")
    if hedef_mi("yt", "youtube", "shorts", "video"):
        hedef_kanallar.append("youtube")

    toplam_adim = max(1, len(hedef_kanallar))
    durum_haritasi: dict[str, str] = {k: "⏱️ Sırada" for k in hedef_kanallar}
    tamamlanan_adim = [0]
    son_edit = [0.0]
    baslangic_ts = time.time()
    _lock = threading.Lock()
    video_telegrama_gitti = False

    yt_res = {}
    tt_res = {}

    def _bildir(kanal: str, durum: str, increment: bool = False) -> None:
        with _lock:
            if kanal in durum_haritasi:
                durum_haritasi[kanal] = durum
            if increment:
                tamamlanan_adim[0] = min(toplam_adim, tamamlanan_adim[0] + 1)
            ad = tamamlanan_adim[0]
            snap = dict(durum_haritasi)

        if not args.mesaj_id:
            return

        simdi = time.time()
        if (ad < toplam_adim) and (simdi - son_edit[0] < 1.2):
            return

        son_edit[0] = simdi
        try:
            telegram_bot.canli_yayin_durumu_guncelle(
                mesaj_id=args.mesaj_id,
                baslik=baslik,
                adim=ad,
                toplam_adim=toplam_adim,
                durum_haritasi=snap,
                baslangic_ts=baslangic_ts,
            )
        except Exception as de:
            log.debug("Canlı durum güncelleme hatası: %s", de)

    # Kanal İşlevleri (Thread Workers)
    def _is_tiktok() -> None:
        nonlocal tt_res
        _bildir("tiktok", "⏳ Yükleniyor...")
        if reels_modu:
            tt_video = v_yolu if (v_yolu and v_yolu.exists()) else sesli_video_yolu
            if tt_video and tt_video.exists():
                try:
                    res = tiktok.video_yukle(tt_video, baslik=baslik)
                    with _lock:
                        tt_res = res
                        if tt_res.get("durum"):
                            if tt_res.get("taslak_mi"):
                                rapor_satirlari.append("🎵 <b>TikTok (Video):</b> Taslak Olarak Yüklendi ✓")
                                tt_baslik = tiktok.baslik_kur(baslik)
                                telegram_bot.mesaj_gonder(
                                    f"🎵 <b>TikTok Taslağı Gelen Kutusuna Yüklendi</b>\n\n"
                                    f"📝 <i>Uygulamadan paylaşırken kullanabileceğiniz metin (kopyalamak için dokunun):</i>\n"
                                    f"<pre><code>{html_lib.escape(tt_baslik)}</code></pre>"
                                )
                            else:
                                rapor_satirlari.append("🎵 <b>TikTok (Video):</b> Paylaşıldı ✓")
                        else:
                            rapor_satirlari.append(f"🎵 <b>TikTok:</b> {res.get('hata') or 'Hata'} ✗")
                except Exception as tt_e:
                    log.warning("TikTok video yükleme hatası: %s", tt_e)
                    with _lock:
                        rapor_satirlari.append(f"🎵 <b>TikTok:</b> Hata ({tt_e}) ✗")
            else:
                with _lock:
                    rapor_satirlari.append("🎵 <b>TikTok:</b> Video üretilemedi ✗")
        else:
            try:
                res = tiktok.foto_yayinla(public_urller, baslik=baslik, hazir_video_yolu=v_yolu)
                with _lock:
                    tt_res = res
                    if tt_res.get("durum"):
                        if tt_res.get("taslak_mi"):
                            rapor_satirlari.append("🎵 <b>TikTok:</b> Taslak Olarak Yüklendi ✓")
                            tt_baslik = tiktok.baslik_kur(baslik)
                            telegram_bot.mesaj_gonder(
                                f"🎵 <b>TikTok Taslağı Gelen Kutusuna Yüklendi</b>\n\n"
                                f"📝 <i>Uygulamadan paylaşırken kullanabileceğiniz metin (kopyalamak için dokunun):</i>\n"
                                f"<pre><code>{html_lib.escape(tt_baslik)}</code></pre>"
                            )
                        else:
                            tur_etiket = "Tekil Resim" if tek_sayfa else "Carousel"
                            rapor_satirlari.append(f"🎵 <b>TikTok ({tur_etiket}):</b> Paylaşıldı ✓")
                    else:
                        rapor_satirlari.append(f"🎵 <b>TikTok:</b> {res.get('hata') or 'Hata'} ✗")
            except Exception as tt_e:
                log.warning("TikTok fotoğraf paylaşım hatası: %s", tt_e)
                with _lock:
                    rapor_satirlari.append(f"🎵 <b>TikTok:</b> Hata ({tt_e}) ✗")
        _bildir("tiktok", "✅ Yayında" if tt_res.get("durum") else "❌ Hata", increment=True)

    def _is_instagram() -> None:
        nonlocal ig_id
        _bildir("instagram", "⏳ Yükleniyor...")
        try:
            gorseller_ig = public_urller
            if tek_sayfa:
                p_id = instagram.tekil_gorsel_yayinla(gorseller_ig[0], caption)
                with _lock:
                    ig_id = p_id
                    if p_id:
                        rapor_satirlari.append("📸 <b>Instagram (Tekil Resim):</b> Paylaşıldı ✓")
                    else:
                        rapor_satirlari.append("📸 <b>Instagram:</b> Hata oluştu ✗")
            else:
                p_id = instagram.carousel_yayinla(gorseller_ig, caption)
                with _lock:
                    ig_id = p_id
                    if p_id:
                        rapor_satirlari.append("📸 <b>Instagram (Carousel):</b> Paylaşıldı ✓")
                    else:
                        rapor_satirlari.append("📸 <b>Instagram:</b> Hata oluştu ✗")
        except Exception as yayin_hatasi:
            log.warning("Instagram yayını hatası: %s", yayin_hatasi)
            with _lock:
                rapor_satirlari.append(f"📸 <b>Instagram:</b> Hata ({yayin_hatasi}) ✗")
        _bildir("instagram", "✅ Yayında" if ig_id else "❌ Hata", increment=True)

    def _is_reels() -> None:
        nonlocal video_telegrama_gitti
        _bildir("reels", "⏳ Yükleniyor...")
        ig_reels_video = v_yolu if (v_yolu and v_yolu.exists()) else sesli_video_yolu
        if ig_reels_video and ig_reels_video.exists():
            try:
                telegram_bot.video_gonder(
                    ig_reels_video,
                    aciklama=f"🎬 <b>EDM Reels Videosu (1080x1920 MP4)</b>\n\n"
                             f"📌 <b>Konu:</b> {html_lib.escape(baslik)}\n\n"
                             f"💡 <i>Videoyu cihazınıza kaydedip Instagram uygulamasından trend müzik ekleyerek Reels olarak paylaşabilirsiniz.</i>",
                )
                with _lock:
                    video_telegrama_gitti = True
                    rapor_satirlari.append("🎬 <b>Instagram Reels:</b> Video ve açıklama Telegram'a iletildi ✓")
                _bildir("reels", "✅ Yayında", increment=True)
            except Exception as re:
                log.warning("Instagram Reels teslim hatası: %s", re)
                with _lock:
                    rapor_satirlari.append(f"🎬 <b>Instagram Reels:</b> Hata ({re}) ✗")
                _bildir("reels", "❌ Hata", increment=True)
        else:
            with _lock:
                rapor_satirlari.append("🎬 <b>Instagram Reels:</b> Video üretilemedi ✗")
            _bildir("reels", "❌ Hata", increment=True)

    def _is_story() -> None:
        _bildir("story", "⏳ Yükleniyor...")
        story_url = None
        try:
            from PIL import Image
            from src import make_image
            story_dosya = KOK / f"data/output/story_{ref_id}.jpg"
            story_dosya.parent.mkdir(parents=True, exist_ok=True)
            hazir_yol = None

            if detay and isinstance(detay, dict) and (
                detay.get("format_turu") in ("sozluk", "nedir_dogrusu", "net_cevap", "vaka", "dailybrief", "haber", "haber_dailybrief")
                or detay.get("bicim") in ("haber", "B5")
            ):
                try:
                    from src import yeni_formatlar
                    fmt = detay.get("format_turu") or "dailybrief"
                    d_slaytlar = yeni_formatlar.slaytlari_uret(detay, format_turu=fmt, cikti_onek=f"story_{ref_id}", olcu="story")
                    if d_slaytlar and Path(d_slaytlar[0]).exists():
                        hazir_yol = Path(d_slaytlar[0])
                except Exception as de:
                    log.warning("Yeni format story üretim hatası: %s", de)
            elif detay:
                try:
                    with make_image.tuval("story"):
                        hazir_yol = Path(make_image.otorite_slayt_1_kapak(detay, str(story_dosya)))
                except Exception as de:
                    log.warning("Story native 9:16 üretim hatası: %s", de)
            elif tur == "ilan" and ilan:
                try:
                    ilan_kapak = make_image.ilan_kapak_slayti_ciz(ilan)
                    if ilan_kapak and Path(ilan_kapak).exists():
                        hazir_yol = Path(ilan_kapak)
                except Exception as ie:
                    log.warning("İlan story kapak hatası: %s", ie)
            elif slayt_yollari and Path(slayt_yollari[0]).exists():
                hazir_yol = Path(slayt_yollari[0])
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

        st_basarili = False
        if story_url:
            try:
                ig_story_id = instagram.story_yayinla(story_url)
                with _lock:
                    if ig_story_id:
                        st_basarili = True
                        rapor_satirlari.append("📱 <b>Instagram Story:</b> Paylaşıldı ✓")
                    else:
                        rapor_satirlari.append("📱 <b>Instagram Story:</b> Hata oluştu ✗")
            except Exception as ise:
                log.warning("Instagram Story hatası: %s", ise)
                with _lock:
                    rapor_satirlari.append(f"📱 <b>Instagram Story:</b> Hata ({ise}) ✗")

            try:
                fb_story_id = facebook.story_yayinla(story_url)
                with _lock:
                    if fb_story_id:
                        st_basarili = True
                        rapor_satirlari.append("📘 <b>Facebook Story:</b> Paylaşıldı ✓")
                    else:
                        rapor_satirlari.append("📘 <b>Facebook Story:</b> Hata oluştu ✗")
            except Exception as fse:
                log.warning("Facebook Story hatası: %s", fse)
                with _lock:
                    rapor_satirlari.append(f"📘 <b>Facebook Story:</b> Hata ({fse}) ✗")
        else:
            with _lock:
                rapor_satirlari.append("📱 <b>Story:</b> Görsel hazırlanamadı ✗")
        _bildir("story", "✅ Yayında" if st_basarili else "❌ Hata", increment=True)

    def _is_threads() -> None:
        nonlocal threads_id
        _bildir("threads", "⏳ Yükleniyor...")
        try:
            threads_urller = None
            if detay and isinstance(detay, dict) and detay.get("slayt_4x5_urlleri"):
                threads_urller = detay["slayt_4x5_urlleri"]

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

            if not threads_urller and slayt_yollari and any(Path(p).exists() for p in slayt_yollari):
                try:
                    threads_urller = instagram.gorselleri_4_5_yap(slayt_yollari)
                except Exception as c_err:
                    log.warning("Threads yerel dosya 4:5 kırpma hatası: %s", c_err)

            if not threads_urller:
                threads_urller = public_urller

            th_tek = (len(threads_urller) <= 1) if threads_urller else tek_sayfa
            if th_tek:
                th_metin = (haber.get("threads_metin") if haber and tur in ("haber", "reels") else "") or caption
                th_metin = generate_text.caption_zenginlestir(
                    th_metin,
                    kategori_kodu=haber.get("kategori") if haber else None,
                    platform="threads",
                    manset=baslik,
                )
                t_id = threads.paylas(th_metin, [threads_urller[0]] if threads_urller else None)
                with _lock:
                    threads_id = t_id
                    if t_id:
                        rapor_satirlari.append("🧵 <b>Threads (Tekil Görsel):</b> 4:5 paylaşıldı ✓")
                    else:
                        rapor_satirlari.append("🧵 <b>Threads:</b> Hata oluştu ✗")
            else:
                sayfalar = threads.metinleri_slaytlara_dagit(haber if tur in ("haber", "reels") else {"manset": baslik, "spot": caption}, threads_urller)
                if len(sayfalar) > 1:
                    t_id = threads.zincir_paylas(sayfalar)
                    with _lock:
                        threads_id = t_id
                        if t_id:
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
                    t_id = threads.paylas(th_metin, threads_urller)
                    with _lock:
                        threads_id = t_id
                        if t_id:
                            rapor_satirlari.append("🧵 <b>Threads:</b> 4:5 paylaşıldı ✓")
                        else:
                            rapor_satirlari.append("🧵 <b>Threads:</b> Hata oluştu ✗")
        except Exception as yayin_hatasi:
            log.warning("Threads yayını hatası: %s", yayin_hatasi)
            with _lock:
                rapor_satirlari.append(f"🧵 <b>Threads:</b> Hata ({yayin_hatasi}) ✗")
        _bildir("threads", "✅ Yayında" if threads_id else "❌ Hata", increment=True)

    def _is_facebook() -> None:
        nonlocal fb_id
        k_fb = "facebook_reels" if reels_modu else "facebook"
        _bildir(k_fb, "⏳ Yükleniyor...")
        fb_caption = (detay.get("caption_facebook") if isinstance(detay, dict) else "") or caption
        fb_caption = generate_text.caption_zenginlestir(
            fb_caption,
            kategori_kodu=haber.get("kategori") if haber else None,
            platform="facebook",
            manset=baslik,
        )
        if reels_modu:
            if sesli_video_yolu and sesli_video_yolu.exists():
                try:
                    f_id = facebook.video_yayinla(sesli_video_yolu, description=fb_caption)
                    with _lock:
                        fb_id = f_id
                        if f_id:
                            rapor_satirlari.append("📘 <b>Facebook (Reels):</b> Paylaşıldı ✓")
                        else:
                            rapor_satirlari.append("📘 <b>Facebook Reels:</b> Hata oluştu ✗")
                except Exception as fe:
                    log.warning("Facebook Reels yayını hatası: %s", fe)
                    with _lock:
                        rapor_satirlari.append(f"📘 <b>Facebook Reels:</b> Hata ({fe}) ✗")
            else:
                with _lock:
                    rapor_satirlari.append("📘 <b>Facebook Reels:</b> Dikey video üretilemedi ✗")
        else:
            try:
                gorseller_fb = public_urller
                f_id = facebook.paylas(fb_caption, gorseller_fb)
                with _lock:
                    fb_id = f_id
                    if f_id:
                        rapor_satirlari.append("📘 <b>Facebook (Standart Gönderi):</b> Paylaşıldı ✓")
                    else:
                        rapor_satirlari.append("📘 <b>Facebook:</b> Hata oluştu ✗")
            except Exception as fe:
                log.warning("Facebook standart paylaşım hatası: %s", fe)
                with _lock:
                    rapor_satirlari.append(f"📘 <b>Facebook:</b> Hata ({fe}) ✗")
        _bildir(k_fb, "✅ Yayında" if fb_id else "❌ Hata", increment=True)

    def _is_youtube() -> None:
        nonlocal yt_res
        _bildir("youtube", "⏳ Yükleniyor...")
        if sesli_video_yolu and sesli_video_yolu.exists():
            try:
                res = youtube.shorts_yukle(sesli_video_yolu, baslik=baslik, aciklama=caption)
                with _lock:
                    yt_res = res
                    if res.get("durum"):
                        rapor_satirlari.append(f"▶️ <b>YouTube Shorts:</b> <a href='{res.get('url')}'>İzle</a> ✓")
                    else:
                        rapor_satirlari.append(f"▶️ <b>YouTube Shorts:</b> {res.get('hata') or 'Hata oluştu'} ✗")
            except Exception as yayin_hatasi:
                log.warning("YouTube Shorts yayını hatası: %s", yayin_hatasi)
                with _lock:
                    rapor_satirlari.append(f"▶️ <b>YouTube Shorts:</b> Hata ({yayin_hatasi}) ✗")
        else:
            with _lock:
                rapor_satirlari.append("▶️ <b>YouTube Shorts:</b> Dikey video üretilemedi ✗")
        _bildir("youtube", "✅ Yayında" if yt_res.get("durum") else "❌ Hata", increment=True)

    kanal_islevleri = {
        "tiktok": _is_tiktok,
        "instagram": _is_instagram,
        "reels": _is_reels,
        "story": _is_story,
        "threads": _is_threads,
        "facebook": _is_facebook,
        "facebook_reels": _is_facebook,
        "youtube": _is_youtube,
    }

    # Başlangıç ilerleme durumunu Telegram'da göster
    if args.mesaj_id and hedef_kanallar:
        try:
            telegram_bot.canli_yayin_durumu_guncelle(
                mesaj_id=args.mesaj_id,
                baslik=baslik,
                adim=0,
                toplam_adim=toplam_adim,
                durum_haritasi=durum_haritasi,
                baslangic_ts=baslangic_ts,
            )
        except Exception as e_bas:
            log.debug("Canlı yayın başlangıç bildirimi gönderilemedi: %s", e_bas)

    # 🚀 Paralel Dağıtım Motorunu Çalıştır
    gorevler = [kanal_islevleri[k] for k in hedef_kanallar if k in kanal_islevleri]
    if gorevler:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(gorevler))) as executor:
            futures = [executor.submit(fn) for fn in gorevler]
            concurrent.futures.wait(futures)

    # 5. Veritabanını Güncelle
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
        if fb_id:
            guncelleme["facebook_post_id"] = fb_id
        if yt_res.get("durum") and yt_res.get("video_id"):
            guncelleme["youtube_video_id"] = yt_res.get("video_id")
        if tt_res.get("durum") and tt_res.get("publish_id"):
            guncelleme["tiktok_publish_id"] = tt_res.get("publish_id")
        if v_yolu and v_yolu.exists():
            guncelleme["video_yolu"] = str(v_yolu)
        db.haber_guncelle(int(ref_id), **guncelleme)
    elif tur == "ilan" and herhangi_biri_basarili:
        db.ilan_paylasildi_isaretle(ref_id)

    db.onay_istegi_sonuclandir(tur, str(ref_id), "yayinlandi" if herhangi_biri_basarili else "hata")
    db.wal_bosalt()

    # 6. Telegram'a Sonuç Raporu, Canlı Linkler ve Telafi Butonları İlet
    if not rapor_satirlari:
        raise RuntimeError(f"Geçerli yayın hedefi bulunamadı: {hedef}")
    hata_var = any("✗" in satir for satir in rapor_satirlari)

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
    if fb_id:
        fb_url = facebook.post_baglantisi(fb_id)
        if fb_url:
            canli_linkler.append({"text": "📘 Facebook'ta Gör", "url": fb_url})
    if yt_res.get("durum") and yt_res.get("url"):
        canli_linkler.append({"text": "▶️ Shorts'ta İzle", "url": yt_res.get("url")})

    canli_link_dugmeleri = [canli_linkler[i:i + 2] for i in range(0, len(canli_linkler), 2)]

    # Hata veren kanallar için anında tek tıkla telafi butonları
    telafi_dugmeleri = []
    if paylas_ig and not ig_id:
        telafi_dugmeleri.append([{"text": "🔄 📸 Instagram'ı Tekrar Dene", "callback_data": f"retry_kanal:ig:{ref_id}"}])
    if hedef_mi("threads", "th") and not threads_id:
        telafi_dugmeleri.append([{"text": "🔄 🧵 Threads'i Tekrar Gönder", "callback_data": f"retry_kanal:threads:{ref_id}"}])
    if hedef_mi("fb", "facebook") and not fb_id:
        telafi_dugmeleri.append([{"text": "🔄 📘 Facebook'a Tekrar Gönder", "callback_data": f"retry_kanal:facebook:{ref_id}"}])
    if hedef_mi("yt", "youtube", "shorts") and not yt_res.get("durum"):
        telafi_dugmeleri.append([{"text": "🔄 ▶️ Shorts'a Tekrar Yükle", "callback_data": f"retry_kanal:youtube:{ref_id}"}])
    if hedef_mi("tt", "tiktok") and not tt_res.get("durum"):
        telafi_dugmeleri.append([{"text": "🔄 🎵 TikTok'a Tekrar Yükle", "callback_data": f"retry_kanal:tiktok:{ref_id}"}])
    if paylas_reels and not video_telegrama_gitti:
        telafi_dugmeleri.append([{"text": "🔄 🎬 Reels'i Tekrar Gönder", "callback_data": f"retry_kanal:reels:{ref_id}"}])

    if len(telafi_dugmeleri) > 1:
        telafi_dugmeleri.insert(0, [{"text": "🔄 Başarısız Tüm Kanalları Tekrar Dene", "callback_data": f"retry_kanal:hepsi:{ref_id}"}])

    kontrol_dugmesi = [[{"text": "🔍 Yayın durumunu kontrol et", "callback_data": f"yayin_kontrol:{ref_id}"}]]
    sonuc_tuslari = canli_link_dugmeleri + telafi_dugmeleri + kontrol_dugmesi
    reply_markup = {"inline_keyboard": sonuc_tuslari} if sonuc_tuslari else None

    try:
        # Instabot standardı: mesaj_id varsa onay kartı güncellenir; mükerrer 2. kart atılmaz.
        # Sadece mesaj_id yoksa (cron/otomatik yayın) yeni mesaj olarak bildirilir.
        telegram_bot.sonucu_yaz(
            args.mesaj_id,
            sonuc_metni,
            bildir=not bool(args.mesaj_id),
            reply_markup=reply_markup,
        )
    except Exception as bildirim_hatasi:
        log.warning("Telegram sonuç bildirimi gönderilemedi: %s", bildirim_hatasi)

    # 7. Hazırlanan 9:16 Dikey Videoyu Telegram Grubuna İlet (Her yayında hazır video teslim edilir)
    # Instabot standardı (21 Eyl): Telegram Reels videosu sessiz teslim edilir (kullanıcı trend müzik ekleyebilsin).
    gonderilecek_video = v_yolu if (v_yolu and v_yolu.exists()) else sesli_video_yolu
    if gonderilecek_video and gonderilecek_video.exists() and not video_telegrama_gitti:
        try:
            log.info("Hazırlanan dikey video Telegram grubuna iletiliyor: %s", gonderilecek_video)
            telegram_bot.video_gonder(
                gonderilecek_video,
                aciklama=f"🎬 <b>EDM Reels Videosu (1080x1920 MP4)</b>\n\n"
                         f"📌 <b>Konu:</b> {html_lib.escape(baslik)}\n\n"
                         f"💡 <i>Videoyu cihazınıza kaydedip Instagram uygulamasından trend müzik ekleyerek Reels olarak paylaşabilirsiniz.</i>",
            )
            video_telegrama_gitti = True
        except Exception as ve:
            log.warning("Telegram'a video iletilemedi: %s", ve)

    # 8. Mükerrer açıklama metni kaldırıldı (Instabot commit 19355f4 referansı — onay kartında zaten mevcut)
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
