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
    parser.add_argument("--hedef", default="hepsi", help="Hedef platform veya işlem (hepsi, ig, threads, video, reels, fb, reddet, iptal, yenile)")
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
                log.error("Yenilenecek haber bulunamadı: #%s", ref_id)
                return
            from src import generate_text
            generate_text.haber_metinleri_uret(haber)
            db.haber_guncelle(int(ref_id), slayt_yollari=None, slayt_urlleri=None)
            telegram_bot.haber_onayina_sun(int(ref_id))
            telegram_bot.mesaj_gonder(f"🔄 <b>Haber #{ref_id} yeniden üretildi ve onayınıza sunuldu.</b>")
        elif tur == "ilan":
            log.info("İlan #%s için önizleme yeniden hazırlanıyor...", ref_id)
            telegram_bot.ilan_postunu_hazirla_ve_sor(ref_id)
        return

    slayt_yollari = []
    public_urller = []
    caption = ""
    baslik = ""

    if tur in ("haber", "reels"):
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
                from src import yeni_formatlar
                try:
                    otorite_verisi = json.loads(detay_str)
                    if isinstance(otorite_verisi, dict):
                        slayt_listesi = yeni_formatlar.slaytlari_uret(otorite_verisi, cikti_onek=f"haber_{ref_id}")
                        slayt_yollari = [str(p) for p in slayt_listesi]
                except Exception as e:
                    log.warning("Slaytlar detay_metni'nden çizilemedi: %s", e)

    elif tur == "ilan":
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

        # 3. Threads Yayını
        if hedef_mi("threads"):
            log.info("Threads'te paylaşılıyor...")
            try:
                threads_id = threads.paylas(caption, public_urller)
                if threads_id:
                    rapor_satirlari.append("🧵 <b>Threads:</b> Paylaşıldı ✓")
                else:
                    rapor_satirlari.append("🧵 <b>Threads:</b> Hata oluştu ✗")
            except Exception as yayin_hatasi:
                log.warning("Threads yayını hatası: %s", yayin_hatasi)
                rapor_satirlari.append(f"🧵 <b>Threads:</b> Hata ({yayin_hatasi}) ✗")

        # 4. Facebook Yayını
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

    # 5. Video (YouTube Shorts, TikTok & Instagram Reels)
    reels_id = None
    if hedef_mi("video", "reels", "youtube", "tiktok"):
        log.info("Dikey video (Reels/Shorts) hazırlanıyor...")
        video_yolu = None
        if tur == "reels" and haber and haber.get("video_yolu"):
            vy = Path(haber["video_yolu"])
            if vy.exists():
                video_yolu = vy

        if not video_yolu or not video_yolu.exists():
            if not slayt_yollari or not any(Path(p).exists() for p in slayt_yollari):
                detay = json.loads(haber.get("detay_metni", "{}")) if haber and haber.get("detay_metni") else {}
                from src import yeni_formatlar
                slayt_listesi = yeni_formatlar.slaytlari_uret(detay, cikti_onek=f"reels_{ref_id}")
                slayt_yollari = [str(p) for p in slayt_listesi]
            video_girdisi = slayt_yollari if (slayt_yollari and all(Path(p).exists() for p in slayt_yollari)) else public_urller
            try:
                video_yolu = video.slaytlardan_reels_uret(video_girdisi)
            except Exception as video_hatasi:
                log.warning("Dikey video üretim hatası: %s", video_hatasi)
                video_yolu = None

        if video_yolu and video_yolu.exists():
            # Instagram Reels (Instabot Manuel Trend Müzik Modu: MP4 + Kopyalanabilir Caption Telegram'a İletilir)
            if hedef_mi("reels"):
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

            # YouTube Shorts
            if hedef_mi("video", "youtube"):
                try:
                    yt_res = youtube.shorts_yukle(video_yolu, baslik=baslik)
                    if yt_res.get("durum"):
                        rapor_satirlari.append(f"▶️ <b>YouTube Shorts:</b> <a href='{yt_res.get('url')}'>İzle</a> ✓")
                    else:
                        rapor_satirlari.append(f"▶️ <b>YouTube Shorts:</b> {yt_res.get('hata') or 'Hata oluştu'} ✗")
                except Exception as yayin_hatasi:
                    log.warning("YouTube Shorts yayını hatası: %s", yayin_hatasi)
                    rapor_satirlari.append(f"▶️ <b>YouTube Shorts:</b> Hata ({yayin_hatasi}) ✗")

            # TikTok
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
