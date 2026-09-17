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
    video_lazim = (
        reels_modu
        or hedef_mi("yt", "youtube", "shorts")
        or (reels_modu and hedef_mi("fb", "facebook"))
        or (reels_modu and hedef_mi("tt", "tiktok"))
    )
    sesli_video_yolu = None
    if video_lazim:
        log.info("Dikey video ve fon müziği hazırlanıyor (FB/YT standart video kuralı)...")
        v_yolu = None
        if haber and haber.get("video_yolu"):
            vy = Path(haber["video_yolu"])
            if vy.exists():
                v_yolu = vy

        if not v_yolu or not v_yolu.exists():
            from src import make_image
            # Önce varsa 9:16 dikey slaytları dene
            if detay:
                try:
                    dikey_slaytlar = make_image.otorite_gonderi_slaytlari_uret(detay, cikti_onek=f"reels_{ref_id}", olcu="story")
                    dikey_yollar = [str(p) for p in dikey_slaytlar]
                    v_yolu = video.slaytlardan_reels_uret(dikey_yollar)
                except Exception as ve:
                    log.warning("Dikey otorite slaytlarından video üretilemedi: %s", ve)

            # Yedek: Normal slayt yollarından video üret (tek sayfa ise 6.5 sn sinematik zoom otomatik uygulanır)
            if (not v_yolu or not v_yolu.exists()) and slayt_yollari:
                try:
                    v_yolu = video.slaytlardan_reels_uret(slayt_yollari)
                except Exception as ve:
                    log.warning("Slayt yollarından video üretilemedi: %s", ve)

        if v_yolu and v_yolu.exists():
            # YouTube ve Facebook'a özel telifsiz kurumsal emlak fon müziği miksle
            sesli_video_yolu = ses.sesli_video_hazirla(v_yolu, ses_seviyesi=0.20)
        else:
            log.error("Video üretimi başarısız oldu!")

    # -------------------------------------------------------------
    # KANAL 1: TIKTOK (Öncelikli Kanal: Reels seçilmediği sürece Carousel/Foto, tek sayfaysa Resim)
    # -------------------------------------------------------------
    if hedef_mi("tt", "tiktok"):
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
                tt_res = tiktok.foto_yayinla(public_urller, baslik=baslik)
                if tt_res.get("durum"):
                    if tt_res.get("taslak_mi"):
                        rapor_satirlari.append("🎵 <b>TikTok:</b> Taslak Olarak Yüklendi ✓")
                    else:
                        tur_etiket = "Tekil Resim" if tek_sayfa else "Carousel"
                        rapor_satirlari.append(f"🎵 <b>TikTok ({tur_etiket}):</b> Paylaşıldı ✓")
                else:
                    rapor_satirlari.append(f"🎵 <b>TikTok:</b> {tt_res.get('hata') or 'Hata'} ✗")
            except Exception as tt_e:
                log.warning("TikTok fotoğraf paylaşım hatası: %s", tt_e)
                rapor_satirlari.append(f"🎵 <b>TikTok:</b> Hata ({tt_e}) ✗")

    # -------------------------------------------------------------
    # KANAL 2: INSTAGRAM (Kullanıcı Kuralı: Reels seçilmediği sürece Carousel, tek sayfaysa Resim)
    # -------------------------------------------------------------
    if hedef_mi("ig", "instagram", "reels"):
        if reels_modu:
            # Instagram Reels için Telegram'a iletilen video:
            # Kullanıcı Instagram uygulamasından trend müzik ekleyeceği için arkaplan sesi olmamalıdır!
            ig_reels_video = v_yolu if (v_yolu and v_yolu.exists()) else sesli_video_yolu
            if ig_reels_video and ig_reels_video.exists():
                try:
                    import html as html_lib
                    temiz_metin = html_lib.escape(caption.strip())
                    telegram_bot.video_gonder(
                        ig_reels_video,
                        aciklama=f"🎬 <b>EDM Reels Videosu (1080x1920 MP4)</b>\n\n"
                                 f"📌 <b>Konu:</b> {baslik}\n\n"
                                 f"💡 <i>Videoyu cihazınıza kaydedip Instagram uygulamasından trend müzik ekleyerek Reels olarak paylaşabilirsiniz.</i>",
                    )
                    telegram_bot.mesaj_gonder(
                        "📝 <b>Reels Açıklama Metni (Kopyalamak için dokunun):</b>\n"
                        f"<pre><code>{temiz_metin}</code></pre>"
                    )
                    rapor_satirlari.append("🎬 <b>Instagram Reels:</b> Video ve açıklama Telegram'a iletildi ✓")
                except Exception as re:
                    log.warning("Instagram Reels teslim hatası: %s", re)
                    rapor_satirlari.append(f"🎬 <b>Instagram Reels:</b> Hata ({re}) ✗")
            else:
                rapor_satirlari.append("🎬 <b>Instagram Reels:</b> Video üretilemedi ✗")
        else:
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

    # -------------------------------------------------------------
    # KANAL 3: STORY (Instagram & Facebook Story — 9:16 Dikey Format)
    # -------------------------------------------------------------
    if hedef_mi("story"):
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

            # 2. Eğer detay (içerik sözlüğü) varsa, doğrudan native 9:16 Story kapağı üret (en kaliteli & hatasız yol)
            elif detay:
                try:
                    with make_image.tuval("story"):
                        hazir_yol = Path(make_image.otorite_slayt_1_kapak(detay, str(story_dosya)))
                except Exception as de:
                    log.warning("Story native 9:16 üretim hatası: %s", de)

            # 3. Eğer ilan ise, ilan kapak slaytı üret
            elif tur == "ilan" and ilan:
                try:
                    ilan_kapak = make_image.ilan_kapak_slayti_ciz(ilan)
                    if ilan_kapak and Path(ilan_kapak).exists():
                        hazir_yol = Path(ilan_kapak)
                except Exception as ie:
                    log.warning("İlan story kapak hatası: %s", ie)

            # 4. Yerel ilk slayt dosyası diskte varsa
            elif slayt_yollari and Path(slayt_yollari[0]).exists():
                hazir_yol = Path(slayt_yollari[0])

            # 5. Disk boş ama CDN/public URL varsa indir
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

    # -------------------------------------------------------------
    # KANAL 4: THREADS (Kullanıcı Kuralı: Her zaman 4:5 Fotoğraf ve Zincir yapısında)
    # -------------------------------------------------------------
    if hedef_mi("threads"):
        log.info("Threads'te paylaşılıyor (Tek sayfa: %s)...", tek_sayfa)
        try:
            if tek_sayfa:
                th_metin = (haber.get("threads_metin") if haber and tur in ("haber", "reels") else "") or caption
                th_metin = generate_text.caption_zenginlestir(
                    th_metin,
                    kategori_kodu=haber.get("kategori") if haber else None,
                    platform="threads",
                    manset=baslik,
                )
                threads_id = threads.paylas(th_metin, [public_urller[0]])
                if threads_id:
                    rapor_satirlari.append("🧵 <b>Threads (Tekil Görsel):</b> Paylaşıldı ✓")
                else:
                    rapor_satirlari.append("🧵 <b>Threads:</b> Hata oluştu ✗")
            else:
                sayfalar = threads.metinleri_slaytlara_dagit(haber if tur == "haber" else {"manset": baslik, "spot": caption}, public_urller)
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
                    threads_id = threads.paylas(th_metin, public_urller)
                    if threads_id:
                        rapor_satirlari.append("🧵 <b>Threads:</b> Paylaşıldı ✓")
                    else:
                        rapor_satirlari.append("🧵 <b>Threads:</b> Hata oluştu ✗")
        except Exception as yayin_hatasi:
            log.warning("Threads yayını hatası: %s", yayin_hatasi)
            rapor_satirlari.append(f"🧵 <b>Threads:</b> Hata ({yayin_hatasi}) ✗")

    # -------------------------------------------------------------
    # KANAL 5: FACEBOOK (Kullanıcı Kuralı: Standart gönderide Albüm/Fotoğraf, Reels seçildiyse Reels videosu)
    # -------------------------------------------------------------
    if hedef_mi("fb", "facebook"):
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

    # -------------------------------------------------------------
    # KANAL 6: YOUTUBE (Kullanıcı Kuralı: YouTube Shorts HER ZAMAN paylaşılır ve arkaplan sesli)
    # -------------------------------------------------------------
    if hedef_mi("yt", "youtube", "shorts", "video"):
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
