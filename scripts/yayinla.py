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
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import db, durum_kurali, facebook, generate_text, hata_bildir, instagram, linkedin, make_image, ses, telegram_bot, threads, tiktok, twitter, upload_image, video, youtube

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# Yalnızca yayında OLMAYAN içeriğe uygulanabilen işlemler.
TASLAK_ISLEMLERI = frozenset({
    "reddet", "iptal", "cope_at", "yenile",
    "metin_ozetle", "metin_detaylandir", "metin_yenile",
    "foto_degistir", "foto_editoryal", "foto_gercek", "foto_stok", "foto_ai", "foto_ilk", "foto_adaylar",
})
# Her durumda anlamlı olan yönetim işlemleri. "tamamla" elle paylaşılan içeriği
# kaydetmenin yolu; kaldırma ise kendi içinde yayında olup olmadığına bakar.
YONETIM_ISLEMLERI = frozenset({"ertele", "kaldir", "sil", "manuel_paket", "tamamla", "manuel_tamam"})


def _haber_yukle(ref_id: str):
    try:
        haber = db.haber_getir(int(ref_id))
    except (TypeError, ValueError):
        return None
    if not haber:
        from src import db_senkron
        db_senkron.uzaktan_tazele()
        haber = db.haber_getir(int(ref_id))
    return haber


def _site_taslagi_aktar(haber: dict | None) -> str:
    """Sosyal yayından sonra siteye yalnız inceleme taslağı bırakır.

    Yerel denemelerde veya henüz Worker tarafı kurulmadan bu yol kapalıdır;
    sosyal paylaşımın sonucunu değiştirmez. GitHub işinde OIDC kimliğiyle açılır.
    """
    if not haber or os.environ.get("EDM_SITE_ICERIK_AKTARIMI") != "1":
        return ""
    try:
        from src import site_icerik
        sonuc = site_icerik.site_taslagi_gonder(haber)
        return f"🌐 Site taslağı: incelemeye alındı (#{sonuc.get('id', '—')}) ✓"
    except Exception as hata:
        log.warning("Haber site taslağına aktarılamadı: %s", hata)
        return "🌐 Site taslağı: oluşturulamadı; sosyal yayın etkilenmedi."


def _url_canli_ve_uygun_mu(url: str) -> bool:
    """URL'nin erişilebilir ve Meta/Instagram için uygun olup olmadığını denetler."""
    if not url or not isinstance(url, str) or not url.startswith("http"):
        return False
    if os.environ.get("PYTEST_CURRENT_TEST") and ("example.com" in url or "test" in url):
        return True
    # uguu.se bağlantıları Meta Graph API tarafından reddedilir veya süresi 3 saatte biter
    if "uguu.se" in url:
        return False
    try:
        import requests
        r = requests.head(
            url,
            headers={"User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"},
            timeout=5,
            allow_redirects=True,
        )
        return r.status_code == 200
    except Exception:
        return False


def _urlleri_dogrula_ve_onar(
    public_urller: list[str],
    slayt_yollari: list[str],
    haber: dict | None,
    ref_id: str,
    tur: str,
) -> tuple[list[str], list[str]]:
    """Tüm görsel URL'lerini denetler; süresi dolmuş veya geçersiz URL'leri
    yerel dosyalardan veya gerekirse anında yeniden çizerek taze CDN'e yükler.
    """
    if not public_urller:
        return public_urller, slayt_yollari

    hepsi_canli = all(_url_canli_ve_uygun_mu(u) for u in public_urller)
    if hepsi_canli:
        return public_urller, slayt_yollari

    log.warning("Bazı görsel URL'leri süresi dolmuş veya erişilemez, otomatik onarma başlatılıyor...")

    # 1. Yerel dosyalar mevcutsa onları yükle
    if slayt_yollari and any(Path(p).exists() for p in slayt_yollari):
        mevcut_yollar = [p for p in slayt_yollari if Path(p).exists()]
        if len(mevcut_yollar) == len(slayt_yollari):
            try:
                taze_urller = upload_image.coklu_gorsel_yukle(mevcut_yollar)
                if taze_urller:
                    log.info("%d adet görsel yerel dosyalardan yeniden yüklendi.", len(taze_urller))
                    if tur in ("haber", "reels") and haber:
                        db.haber_guncelle(int(ref_id), slayt_urlleri=json.dumps(taze_urller))
                    return taze_urller, slayt_yollari
            except Exception as e:
                log.warning("Yerel görseller yüklenirken hata: %s", e)

    # 2. Yerel dosyalar yoksa detay_metni üzerinden yeniden çiz
    if tur in ("haber", "reels") and haber:
        detay_str = haber.get("detay_metni")
        if detay_str:
            from src import make_image, yeni_formatlar
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
                    taze_urller = upload_image.coklu_gorsel_yukle(slayt_yollari)
                    if taze_urller:
                        db.haber_guncelle(int(ref_id), slayt_urlleri=json.dumps(taze_urller), slayt_yollari=json.dumps(slayt_yollari))
                        return taze_urller, slayt_yollari
            except Exception as e:
                log.warning("Slaytlar yeniden çizilemedi: %s", e)

    return public_urller, slayt_yollari


_HABER_BICIMLERI = ("dailybrief", "haber", "haber_dailybrief")
_YENI_FORMATLAR = ("sozluk", "sozluk_uret", "nedir_dogrusu", "net_cevap", "vaka")


def story_kapagi_uret(detay: dict | None, haber: dict | None, ref_id: object, tur: str,
                      ilan: dict | None = None) -> Path | None:
    """Story için NATIVE 9:16 (1080x1920) kapak; üretilemezse None.

    Eskiden Story, onaylanan 4:5 besleme kapağını alıp `video._cercevele_9_16` ile 9:16'ya
    yerleştiriyordu: haberde fotoğraf kutunun üstünde/altında bulanık bir dolguyla bitiyordu ve
    tam boy fotoğraflı ana kare hiç gitmiyordu (2026-10-07 kullanıcı bildirimi: "story de 4:5'in
    üstü kesik hali gidiyor"). Reels/Shorts videosu zaten native 9:16 çiziliyor; Story de aynı
    kaynaktan çizilir. İçerik (4:5 kutunun içi) besleme ile aynıdır, fark kutunun dışındaki fotoğraftır.

    Onaylanan fotoğraf: `haberler.gorsel_url`. Onay anında `foto_yolu` olarak veriliyordu
    (`telegram_bot.haber_onayina_sun`); yayın anında detay_metni'nde yok, burada aynısı yapılır.
    """
    from src import config, make_image, yeni_formatlar
    try:
        if tur == "ilan" and ilan:
            with make_image.tuval("story"):
                yol = make_image.ilan_kapak_slayti_ciz(ilan)
            return Path(yol) if yol and Path(yol).exists() else None
        if not isinstance(detay, dict) or not detay:
            return None
        veri = dict(detay)
        veri.setdefault("id", ref_id)  # sabitlenen fotoğraf adı: haber_foto_<id>.jpg (başka haberin dosyası karışmasın)
        if not (veri.get("foto_yolu") or veri.get("gorsel_yolu")) and isinstance(haber, dict) and haber.get("gorsel_url"):
            veri["foto_yolu"] = haber["gorsel_url"]
        fmt = str(veri.get("format_turu") or "").lower()
        bicim = veri.get("bicim")
        if fmt in ("", "reels", "otorite"):
            fmt = ""  # asıl biçim `bicim` alanında
        onek = f"story_{ref_id}"
        if fmt in _HABER_BICIMLERI or (not fmt and bicim in ("haber", "B5")):
            slaytlar = yeni_formatlar.slaytlari_uret(veri, format_turu="dailybrief", cikti_onek=onek, olcu="story")
            return Path(slaytlar[0]) if slaytlar and Path(slaytlar[0]).exists() else None
        elif fmt in _YENI_FORMATLAR:
            slaytlar = yeni_formatlar.slaytlari_uret(veri, format_turu=fmt, cikti_onek=onek, olcu="story")
            return Path(slaytlar[0]) if slaytlar and Path(slaytlar[0]).exists() else None
        elif not fmt and bicim in ("B1", "B2", "B3", "B4", None, ""):
            cikti_kapak = config.yol_al(f"data/output/{onek}_01_kapak.jpg")
            with make_image.tuval("story"):
                slayt_yolu = make_image.otorite_slayt_1_kapak(veri, cikti_kapak)
            return Path(slayt_yolu) if Path(slayt_yolu).exists() else None
        else:
            return None
    except Exception as e:  # noqa: BLE001 — Story üretilemezse onaylı kapak çerçevelenir (yedek yol)
        log.warning("Native 9:16 Story kapağı üretilemedi: %s", e)
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="EDM Paylaşım Yayınlayıcı")
    parser.add_argument("--tur", default="haber", choices=["haber", "ilan", "reels"], help="İçerik türü")
    parser.add_argument("--id", default=None, help="Haber ID veya İlan ID")
    parser.add_argument("--mesaj-id", default=None, type=int, help="Telegram mesaj ID")
    parser.add_argument("--hedef", default="hepsi", help="Hedef platform veya işlem")
    parser.add_argument("--yeniden-ciz", action="store_true", help="İlan kartlarını güncel site verisiyle yeniden üret")
    parser.add_argument("--plan-an", default=None, help="hedef=planla: Worker'ın planladığı yayın zamanı (ISO)")
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

    # PLANLI YAYIN KAYDI (2026-09-26). Plan Worker'ın KV'sinde, yayını 10 dakikalık
    # Cloudflare cron'u tetikliyor. Burada yalnızca zamanı içeriğe yazılır: hatırlatıcı
    # plan bekleyen içeriğe "onay bekliyor" kartı atıp plan mesajını silmesin.
    if hedef in ("planla", "plan_iptal"):
        if tur in ("haber", "reels"):  # ilan kimlikleri başka tabloda; haberler'e yazılmaz
            an = None
            if hedef == "planla":
                try:
                    an = datetime.fromisoformat(str(args.plan_an).replace("Z", "+00:00")).isoformat()
                except ValueError:
                    log.warning("Geçersiz plan zamanı: %s", args.plan_an)
                    return
            db.haber_guncelle(int(ref_id), planlanan_yayin=an)
            db.wal_bosalt()
        return

    # DURUM KORUMASI — kurallar ve gerekçe: src/durum_kurali.py
    # Telegram'daki her buton, mesaj ne kadar eski olursa olsun buraya ulaşır.
    # Önce içeriğin bugünkü durumuna bakılır; butonun gösterdiği değil.
    if tur in ("haber", "reels"):
        mevcut = _haber_yukle(ref_id)
        if mevcut:
            if hedef in TASLAK_ISLEMLERI:
                engel = durum_kurali.taslak_islem_engeli(mevcut, hedef)
            elif hedef in YONETIM_ISLEMLERI:
                engel = None
            else:
                engel = durum_kurali.yayin_engeli(mevcut)
            if engel:
                log.warning("Durum koruması işlemi durdurdu: #%s durum=%s hedef=%s", ref_id, mevcut.get("durum"), hedef)
                telegram_bot.mesaj_gonder(engel)
                db.wal_bosalt()
                return

            # YAYIN KAPISI yayın anında da çalışır: kapıdan önce onaya sunulmuş,
            # ya da onaydan sonra elle düzenlenmiş içerik denetimsiz çıkmasın.
            # Elle paylaşım paketi de yayındır — insan onu doğrudan paylaşıyor.
            if hedef not in TASLAK_ISLEMLERI and (hedef not in YONETIM_ISLEMLERI or hedef == "manuel_paket"):
                try:
                    detay = json.loads(mevcut.get("detay_metni") or "null")
                except ValueError:
                    detay = None
                gecti, _ = telegram_bot.yayin_kapisi(
                    int(ref_id), mevcut, telegram_bot._denetim_verisi(mevcut, detay),
                    durum_yaz=not durum_kurali.yayinda_mi(mevcut),
                    anlam_denetimi=False,  # yayın anında uyarılar kullanılmaz; model çağrısı boşa gider
                )
                if not gecti:
                    db.wal_bosalt()
                    return

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

    # 0.25 Yayından Kaldır Aksiyonu
    if hedef in ("kaldir", "sil"):
        telegram_bot.yayindan_kaldir(tur, ref_id, mesaj_id=args.mesaj_id)
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
            caption = f"{baslik}\n\nEDM Yapı & Gayrimenkul · Yatırım Ortağınız\n0 212 727 2955 · {ilan_adresi}"
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
            # Reels de haber tablosunda tutuluyor; ancak siteye yalnız editoryal
            # haber metni gider. Video paylaşımı web bülteni oluşturmaz.
            site_notu = _site_taslagi_aktar(haber) if tur == "haber" else ""
            tur_adi = "Reels Videosu" if tur == "reels" else "İçerik"
            log.info("%s #%s kullanıcı tarafından manuel paylaşıldı ve tamamlandı olarak işaretlendi.", tur_adi, ref_id)
            site_notu_ek = f"\n{site_notu}" if site_notu else ""
            telegram_bot.mesaj_gonder(f"✅ <b>{tur_adi} #{ref_id} paylaşıldı ve tamamlandı olarak arşivlendi. Tebrikler! 🎉</b>{site_notu_ek}")
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
        telegram_bot.icerik_onceki_mesajlarini_temizle(tur, str(ref_id))
        if tur == "reels":
            log.info("Reels #%s için video ve metin yeniden üretiliyor...", ref_id)
            db.haber_guncelle(int(ref_id), durum="iptal")
            telegram_bot.reels_hazirla_ve_sun()
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
            db.haber_guncelle(int(ref_id), slayt_yollari=None, slayt_urlleri=None, video_yolu=None)
            telegram_bot.haber_onayina_sun(int(ref_id))
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
                    # "mevzuat maddeleri ekle" talimatı uydurma madde numarasına davetiyeydi.
                    ek_talimat = ("İçeriğe daha fazla hukuki derinlik ve hak arama yolları ekle. "
                                  "Brief'te veya kaynakta geçmeyen kanun/madde numarası YAZMA.")
                else:
                    ek_talimat = "Farklı bir anlatım açısı ve taze bir üslupla baştan hazırla."
                log.info("Metin eylemi (%s) uygulanıyor: #%s", hedef, ref_id)
                generate_text.haber_metinleri_uret(haber, ek_talimat=ek_talimat)
                db.haber_guncelle(int(ref_id), slayt_yollari=None, slayt_urlleri=None, video_yolu=None)
                if tur == "reels":
                    telegram_bot.reels_hazirla_ve_sun()
                else:
                    telegram_bot.haber_onayina_sun(int(ref_id))
                telegram_bot.mesaj_gonder(f"✍️ <b>Haber #{ref_id} metni güncellendi ({hedef}) ve onayınıza sunuldu.</b>")
        db.wal_bosalt()
        return

    # 0.7 Fotoğraf Özelleştirme Aksiyonları (Değiştir / Saf Editoryal / Stok / AI / Gerçek / İlk / 3 Aday / Aday Seçimi)
    if hedef in ("foto_degistir", "foto_editoryal", "foto_gercek", "foto_stok", "foto_ai", "foto_ilk", "foto_adaylar") or hedef.startswith("gorsel_sec:"):
        if tur in ("haber", "reels"):
            haber = db.haber_getir(int(ref_id))
            if not haber:
                from src import db_senkron
                db_senkron.uzaktan_tazele()
                haber = db.haber_getir(int(ref_id))
            if haber:
                detay = json.loads(haber["detay_metni"]) if haber.get("detay_metni") else {}

                # 3 Farklı Aday Sunma İstemi
                if hedef == "foto_adaylar":
                    from src import config
                    c_dir = config.yol_al("data/output/adaylar")
                    c_dir.mkdir(parents=True, exist_ok=True)
                    aday_slaytlari = []
                    etiketler = []

                    # 1. Aday: Gerçek / Kardeş Haber Fotoğrafı
                    h1 = dict(haber)
                    h1["foto_kaynak"] = "gercek"
                    p1 = c_dir / f"aday_{ref_id}_1.jpg"
                    make_image.haber_dailybrief_slayti_ciz(h1, cikti_yolu=p1, sayfa_no="1/3")
                    if p1.exists():
                        aday_slaytlari.append(p1)
                        etiketler.append("1️⃣ Basın / Kardeş Haber Görseli")

                    # 2. Aday: Mimari Stok Fotoğrafı (Pexels)
                    h2 = dict(haber)
                    h2["foto_kaynak"] = "stok"
                    p2 = c_dir / f"aday_{ref_id}_2.jpg"
                    make_image.haber_dailybrief_slayti_ciz(h2, cikti_yolu=p2, sayfa_no="2/3")
                    if p2.exists():
                        aday_slaytlari.append(p2)
                        etiketler.append("2️⃣ Mimari Stok Fotoğraf")

                    # 3. Aday: EDM Kurumsal Mimari Pafta Tasarımı
                    h3 = dict(haber)
                    h3["saf_editoryal"] = True
                    p3 = c_dir / f"aday_{ref_id}_3.jpg"
                    make_image.haber_dailybrief_slayti_ciz(h3, cikti_yolu=p3, sayfa_no="3/3")
                    if p3.exists():
                        aday_slaytlari.append(p3)
                        etiketler.append("3️⃣ EDM Kurumsal Pafta Tasarımı")

                    if aday_slaytlari:
                        telegram_bot.slaytlari_gonder(aday_slaytlari, etiketler)
                        secim_butonlari = [
                            [
                                {"text": "1️⃣", "callback_data": f"gorsel_sec:1:{ref_id}"},
                                {"text": "2️⃣", "callback_data": f"gorsel_sec:2:{ref_id}"},
                                {"text": "3️⃣", "callback_data": f"gorsel_sec:3:{ref_id}"},
                            ],
                            [
                                {"text": "🔄 Başka adaylar", "callback_data": f"foto_degistir:{ref_id}"},
                                {"text": "↩️ Mevcut Görsel Kalsın", "callback_data": f"kurtar_menu:2"},
                            ],
                        ]
                        telegram_bot.mesaj_gonder(
                            f"🎨 <b>3 Alternatif Kapak Görseli (#{ref_id})</b>\n\n"
                            f"1️⃣ Basın / Kardeş Haber Görseli\n"
                            f"2️⃣ Mimari Stok Fotoğraf (Pexels)\n"
                            f"3️⃣ EDM Kurumsal Pafta Tasarımı\n\n"
                            f"Beğendiğin numaraya basarak tek tıkla uygulayabilirsin.",
                            butonlar=secim_butonlari,
                        )
                        db.wal_bosalt()
                        return

                # Aday Seçimi Yapıldıysa
                if hedef.startswith("gorsel_sec:"):
                    secilen = hedef.split(":")[1]
                    if secilen == "1":
                        detay["foto_kaynak"] = "gercek"
                        detay.pop("saf_editoryal", None)
                    elif secilen == "2":
                        detay["foto_kaynak"] = "stok"
                        detay.pop("saf_editoryal", None)
                    elif secilen == "3":
                        detay["saf_editoryal"] = True
                        detay.pop("foto_kaynak", None)
                    detay["foto_degistir"] = True
                elif hedef == "foto_ilk":
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

                db.haber_guncelle(int(ref_id), detay_metni=json.dumps(detay, ensure_ascii=False), slayt_yollari=None, slayt_urlleri=None, video_yolu=None)
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
        caption = f"{baslik}\n\nEDM Yapı & Gayrimenkul · Yatırım Ortağınız\n0 212 727 2955 · {ilan_adresi}"

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
    linkedin_id = None
    twitter_id = None
    rapor_satirlari = []

    detay = json.loads(haber.get("detay_metni", "{}")) if (tur in ("haber", "reels") and haber and haber.get("detay_metni")) else {}
    reels_modu = ("reels" in hedefler) or (tur == "reels")

    # 1. Görselleri Hazırla ve CDN'e Yükle (Instagram, TikTok, Threads, Story için)
    if not public_urller:
        if slayt_yollari and any(Path(p).exists() for p in slayt_yollari):
            log.info("%d adet slayt görseli CDN'e yükleniyor...", len(slayt_yollari))
            public_urller = upload_image.coklu_gorsel_yukle(slayt_yollari)
    else:
        # Mevcut CDN URL'lerini denetle; süresi dolmuş/erişilemeyen varsa yerel dosyalardan onar
        public_urller, slayt_yollari = _urlleri_dogrula_ve_onar(public_urller, slayt_yollari, haber, ref_id, tur)

    if not public_urller and not slayt_yollari:
        raise RuntimeError("Paylaşılacak slayt görseli veya video bulunamadı.")

    tek_sayfa = (len(public_urller) <= 1) if public_urller else (len(slayt_yollari) <= 1)

    # 2. Dikey Video & Arkaplan Sesi Hazırlığı (YouTube Shorts, FB Reels, TikTok ve Telegram için)
    paylas_reels = ("reels" in hedefler or ("hepsi" in hedefler and tur == "reels"))
    paylas_ig = ("ig" in hedefler or "instagram" in hedefler or ("hepsi" in hedefler and tur != "reels"))
    if paylas_reels:
        # Kural: İçerik ya Reels ya da Gönderi olarak atılır. Reels aktifse Instagram Feed (görsel gönderi) deaktif edilir.
        paylas_ig = False

    # "🎙️ Sesli Yayınla" (2026-09-26): Worker hedefe ses_muzikli / ses_muziksiz ekler.
    # Seslendirme yalnızca video kanallarına uygulanır ve TikTok'u video kipine alır
    # (fotoğraf karuseli ses taşımaz). Düz "✅ Yayınla" eskisi gibi seslendirmesiz.
    ses_modu = "muzikli" if "ses_muzikli" in hedefler else ("muziksiz" if "ses_muziksiz" in hedefler else None)
    ses_sonucu: dict = {}

    video_lazim = (
        paylas_reels
        or hedef_mi("yt", "youtube", "shorts", "video")
        or ((reels_modu or ses_modu) and hedef_mi("fb", "facebook"))
        or ((reels_modu or ses_modu) and hedef_mi("tt", "tiktok"))
    )

    v_yolu = None
    sesli_video_yolu = None
    dikey_slaytlar: list[str] = []
    if video_lazim:
        log.info("Dikey video ve fon müziği hazırlanıyor (Shorts, Reels & Telegram video çıktısı)...")
        if haber and haber.get("video_yolu") and not ses_modu:  # onaydaki video seslendirmesiz
            vy = Path(haber["video_yolu"])
            if vy.exists() and vy.stat().st_size > 0:
                # Tazelik kontrolü: Video, onaylanan slaytlardan eski mi?
                slayt_mtimes = [Path(p).stat().st_mtime for p in slayt_yollari if Path(p).exists()]
                if slayt_mtimes and vy.stat().st_mtime < max(slayt_mtimes):
                    log.warning("Kayıtlı video dosyası (%s) slaytlardan eski; onaylı slaytlara göre yeniden üretilecek.", vy.name)
                    v_yolu = None
                else:
                    v_yolu = vy

        # 3.0. Video: düz yayında eskisi gibi sessiz video (fon müziği aşağıda eklenir);
        # sesli yayında kapak seslendirmesi + kapanış çağrısı (ses.anlatimli_video_uret).
        def _video(slaytlar, veri=None):
            if ses_modu:
                return ses.anlatimli_video_uret(slaytlar, veri=veri, muzik=(ses_modu == "muzikli"), sonuc=ses_sonucu)
            return video.slaytlardan_reels_uret(slaytlar, haber=veri)

        if not v_yolu or not v_yolu.exists():
            from src import make_image, yeni_formatlar
            haber_bilgi = {**(haber if isinstance(haber, dict) else {}), **(detay if isinstance(detay, dict) else {})}
            fmt = detay.get("format_turu") if isinstance(detay, dict) else None

            # ⚠️ INSTABOT STANDARDI (CLAUDE.md §242): ONAYLANAN GÖRSEL YAYINA ÇIKAN GÖRSEL OLMALI.
            # Video, kullanıcının Telegram'da görüp onayladığı slaytlardan derlenir.
            # Runner ortamında slaytlar sıfırdan üretilmez (aksi halde Pexels'ten bambaşka stok görsel çekebilir).

            # 1. Öncelik: Tam Ekran Native 9:16 Slaytlar (1080x1920)
            # Video (Reels/Shorts/TikTok) asla 4:5 kırpılmış ve tepesi boş bırakılmış zeminle üretilmez.
            # Onaylanan görsel/fotoğraf yolu kilitlenerek 2 ila 3 slaytlık native 9:16 akış hazırlanır.
            if detay and isinstance(detay, dict):
                try:
                    if fmt in ("dailybrief", "haber", "haber_dailybrief") or detay.get("bicim") in ("haber", "B5"):
                        uretim = yeni_formatlar.slaytlari_uret(detay, format_turu="dailybrief", cikti_onek=f"reels_{ref_id}", olcu="story")
                        if uretim:
                            dikey_slaytlar = [str(p) for p in uretim[:3]]
                    elif fmt in ("sozluk", "sozluk_uret"):
                        uretim = yeni_formatlar.slaytlari_uret(detay, format_turu="sozluk", cikti_onek=f"reels_{ref_id}", olcu="story")
                        if uretim:
                            dikey_slaytlar = [str(p) for p in uretim]
                    elif fmt in ("nedir_dogrusu", "net_cevap", "vaka"):
                        uretim = yeni_formatlar.slaytlari_uret(detay, format_turu=fmt, cikti_onek=f"reels_{ref_id}", olcu="story")
                        if uretim:
                            dikey_slaytlar = [str(uretim[0]), str(uretim[1]), str(uretim[-1])] if len(uretim) > 3 else [str(p) for p in uretim]
                    elif detay.get("bicim") in ("B1", "B2", "B3", "B4") or not fmt or fmt == "otorite":
                        detay_reels = dict(detay)
                        detay_reels["_video_modu"] = True
                        uretim = make_image.otorite_gonderi_slaytlari_uret(detay_reels, cikti_onek=f"reels_{ref_id}", olcu="story")
                        if uretim:
                            # 3 kilit slayt: Kapak + Özet/Detay + Kapanış CTA (Asla 7 slayt boca edilmez)
                            dikey_slaytlar = [str(uretim[0]), str(uretim[1]), str(uretim[-1])] if len(uretim) > 3 else [str(p) for p in uretim]
                except Exception as de:
                    log.warning("Native 9:16 dikey slayt üretimi başarısız: %s", de)

            if dikey_slaytlar and all(Path(p).exists() for p in dikey_slaytlar):
                try:
                    log.info("Native 9:16 slaytlardan (%d adet) dikey video derleniyor...", len(dikey_slaytlar))
                    v_yolu = _video(dikey_slaytlar, haber_bilgi)
                except Exception as ve:
                    log.warning("Native 9:16 slaytlardan video üretilemedi: %s", ve)

            # 2. Öncelik: İlan postu
            if (not v_yolu or not v_yolu.exists()) and tur == "ilan" and "ilan" in locals() and ilan:
                try:
                    ik1 = make_image.ilan_kapak_slayti_ciz(ilan)
                    ik2 = make_image.ilan_detay_slayti_ciz(ilan)
                    ik3 = make_image.ilan_kapanis_slayti_ciz(ilan)
                    v_yolu = _video([str(ik1), str(ik2), str(ik3)])
                except Exception as ve:
                    log.warning("İlan slaytlarından video üretilemedi: %s", ve)

            # 3. Son Çare Fallback: Yalnızca native 9:16 üretilemezse mevcut onaylı slaytları kullan (en fazla 3 slayt)
            if not v_yolu or not v_yolu.exists():
                kaynak_slaytlar = []
                if public_urller and len(public_urller) > 0:
                    kaynak_slaytlar = [str(u) for u in public_urller]
                elif haber and haber.get("slayt_urlleri"):
                    try:
                        db_urller = json.loads(haber["slayt_urlleri"])
                        if isinstance(db_urller, list) and len(db_urller) > 0:
                            kaynak_slaytlar = [str(u) for u in db_urller]
                    except Exception:
                        pass
                if not kaynak_slaytlar and slayt_yollari and any(Path(p).exists() for p in slayt_yollari):
                    kaynak_slaytlar = [str(p) for p in slayt_yollari if Path(p).exists()]

                if kaynak_slaytlar:
                    if len(kaynak_slaytlar) > 3:
                        kaynak_slaytlar = [kaynak_slaytlar[0], kaynak_slaytlar[1], kaynak_slaytlar[-1]]
                    try:
                        log.info("Fallback onaylı slaytlardan (%d adet) video derleniyor...", len(kaynak_slaytlar))
                        v_yolu = _video(kaynak_slaytlar, haber_bilgi)
                    except Exception as ve:
                        log.warning("Fallback onaylı slaytlardan video üretilemedi: %s", ve)

        if v_yolu and v_yolu.exists():
            try:
                # Sesli videoda ("_sesli") dokunulmaz; "fon müziksiz"de müzik eklenmez
                sesli_video_yolu = ses.sesli_video_hazirla(v_yolu, ses_seviyesi=0.20, muzik=(ses_modu != "muziksiz"))
            except Exception as se:
                log.warning("Fon müziği mikslenemedi: %s", se)
                sesli_video_yolu = v_yolu

    if video_lazim:
        # Seslendirme durumu raporu
        kip = "fon müziksiz" if ses_modu == "muziksiz" else "fon müzikli"
        if ses_sonucu.get("anlatim"):
            rapor_satirlari.append(f"🎙️ <b>Seslendirme ({kip}):</b> Eklendi (Alex)")
        elif ses_modu:
            rapor_satirlari.append("⚠️ <b>Seslendirme:</b> Üretilemedi (ElevenLabs anahtarı/kotası) — videolar seslendirmesiz çıktı")

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
    if ("li" in hedefler or "linkedin" in hedefler) or ("hepsi" in hedefler and linkedin.kullanilabilir_mi()):
        hedef_kanallar.append("linkedin")

    # Aynı kanala ikinci kez gönderme: "tekrar dene", "kurtar" ya da iki kez
    # basılan "Yayınla" yalnızca henüz yayında OLMAYAN kanallara gider.
    if haber:
        zaten_yayinda = durum_kurali.tekrar_gonderilmeyecekler(haber, hedef_kanallar)
        if zaten_yayinda:
            hedef_kanallar = [k for k in hedef_kanallar if k not in zaten_yayinda]
            log.info("#%s zaten yayında olan kanallar atlandı: %s", ref_id, zaten_yayinda)
            telegram_bot.mesaj_gonder(
                f"ℹ️ <b>#{ref_id}</b> şu kanallarda zaten yayında, tekrar gönderilmedi: "
                f"<code>{', '.join(zaten_yayinda)}</code>"
            )
        if not hedef_kanallar:
            db.wal_bosalt()
            return

    toplam_adim = max(1, len(hedef_kanallar))
    durum_haritasi: dict[str, str] = {k: "⏱️ Sırada" for k in hedef_kanallar}
    tamamlanan_adim = [0]
    son_edit = [0.0]
    baslangic_ts = time.time()
    _lock = threading.Lock()
    video_telegrama_gitti = False

    yt_res = {}
    tt_res = {}
    linkedin_id = None

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
        if reels_modu or ses_modu:
            tt_video = v_yolu if (v_yolu and v_yolu.exists()) else sesli_video_yolu
            if tt_video and tt_video.exists():
                try:
                    res = tiktok.video_yukle(tt_video, baslik=baslik)
                    with _lock:
                        tt_res = res
                        if tt_res.get("durum"):
                            if tt_res.get("taslak_mi"):
                                rapor_satirlari.append("🎵 <b>TikTok (Video):</b> Taslak Olarak Yüklendi (Uygulamadan Paylaşılacak) 📥")
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
                            rapor_satirlari.append("🎵 <b>TikTok:</b> Taslak Olarak Yüklendi (Uygulamadan Paylaşılacak) 📥")
                        else:
                            tur_etiket = "Tekil Resim" if tek_sayfa else "Carousel"
                            rapor_satirlari.append(f"🎵 <b>TikTok ({tur_etiket}):</b> Paylaşıldı ✓")
                    else:
                        rapor_satirlari.append(f"🎵 <b>TikTok:</b> {res.get('hata') or 'Hata'} ✗")
            except Exception as tt_e:
                log.warning("TikTok fotoğraf paylaşım hatası: %s", tt_e)
                with _lock:
                    rapor_satirlari.append(f"🎵 <b>TikTok:</b> Hata ({tt_e}) ✗")
        durum_tt = "❌ Hata"
        if tt_res.get("durum"):
            durum_tt = "📥 Taslak Yüklendi" if tt_res.get("taslak_mi") else "✅ Yayında"
        _bildir("tiktok", durum_tt, increment=True)

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
                    rapor_satirlari.append("🎬 <b>Instagram Reels:</b> Video ve açıklama Telegram'a iletildi (Elle Paylaşılacak) 📲")
                _bildir("reels", "📲 Telegram'a İletildi", increment=True)
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

            # 1. Öncelik: Video için üretilmiş native 9:16 dikey kapak varsa doğrudan kullan
            if dikey_slaytlar and Path(dikey_slaytlar[0]).exists():
                try:
                    with Image.open(dikey_slaytlar[0]) as d_im:
                        if d_im.size == (1080, 1920):
                            hazir_yol = Path(dikey_slaytlar[0])
                except Exception as de:
                    log.debug("Dikey slayt öncelik kontrolü: %s", de)

            # 2. Öncelik: Native 9:16 Story kapağı üret (1080x1920)
            if not hazir_yol or not hazir_yol.exists():
                hazir_yol = story_kapagi_uret(detay, haber, ref_id, tur, ilan if tur == "ilan" else None)

            # 3. Son Çare Yedek: Yalnızca native 9:16 hiçbir şekilde üretilemezse onaylanan 4:5 kapak çerçevelenir
            if not hazir_yol or not hazir_yol.exists():
                if public_urller and len(public_urller) > 0:
                    try:
                        import requests
                        resp = requests.get(public_urller[0], timeout=15)
                        if resp.status_code == 200:
                            with open(story_dosya, "wb") as f:
                                f.write(resp.content)
                            hazir_yol = story_dosya
                    except Exception as ue:
                        log.warning("Story public URL indirme hatası: %s", ue)
                elif haber and haber.get("slayt_urlleri"):
                    try:
                        import requests
                        db_urller = json.loads(haber["slayt_urlleri"])
                        if isinstance(db_urller, list) and len(db_urller) > 0:
                            resp = requests.get(db_urller[0], timeout=15)
                            if resp.status_code == 200:
                                with open(story_dosya, "wb") as f:
                                    f.write(resp.content)
                                hazir_yol = story_dosya
                    except Exception as ue:
                        log.warning("Story db URL indirme hatası: %s", ue)
                elif slayt_yollari and Path(slayt_yollari[0]).exists():
                    hazir_yol = Path(slayt_yollari[0])

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
                    zincir = threads.zincir_paylas_sonuc(sayfalar)
                    t_id = zincir["kok_id"]
                    with _lock:
                        threads_id = t_id
                        if t_id and not zincir["eksik"]:
                            rapor_satirlari.append(f"🧵 <b>Threads:</b> {zincir['yayinlanan']} parçalı 4:5 zincir paylaşıldı ✓")
                        elif t_id:
                            # Planlanan sayı değil, gerçekten yayınlanan sayı raporlanır
                            eksik = ", ".join(str(n) for n in zincir["eksik"])
                            rapor_satirlari.append(
                                f"🧵 <b>Threads:</b> zincir EKSİK — {zincir['yayinlanan']}/{zincir['toplam']} parça "
                                f"yayında, {eksik}. parça yayınlanamadı ✗"
                            )
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

    def _is_linkedin() -> None:
        nonlocal linkedin_id
        _bildir("linkedin", "⏳ Yükleniyor...")
        if not linkedin.kullanilabilir_mi():
            with _lock:
                rapor_satirlari.append("💼 <b>LinkedIn:</b> Yapılandırılmamış (LINKEDIN_ACCESS_TOKEN eksik) ✗")
            _bildir("linkedin", "❌ Hata", increment=True)
            return

        try:
            li_veri = detay if (detay and isinstance(detay, dict)) else (haber if isinstance(haber, dict) else {})
            li_metin = linkedin.linkedin_metni_hazirla(li_veri, manset=baslik)
            gorseller_li = [str(p) for p in slayt_yollari if Path(p).exists()]
            lid = linkedin.paylas(li_metin, dosya_yollari=gorseller_li)
            with _lock:
                linkedin_id = lid
                if lid:
                    rapor_satirlari.append("💼 <b>LinkedIn:</b> Paylaşıldı ✓")
                else:
                    rapor_satirlari.append("💼 <b>LinkedIn:</b> Hata oluştu ✗")
        except Exception as le:
            log.warning("LinkedIn paylaşım hatası: %s", le)
            with _lock:
                rapor_satirlari.append(f"💼 <b>LinkedIn:</b> Hata ({le}) ✗")
        _bildir("linkedin", "✅ Yayında" if linkedin_id else "❌ Hata", increment=True)

    def _is_twitter() -> None:
        nonlocal twitter_id
        _bildir("twitter", "⏳ Yükleniyor...")
        if not twitter.kullanilabilir_mi():
            with _lock:
                rapor_satirlari.append("🐦 <b>X (Twitter):</b> Yapılandırılmamış (API anahtarları eksik) ✗")
            _bildir("twitter", "❌ Hata", increment=True)
            return

        try:
            tw_haberler = [haber] if haber else [{"baslik_orj": baslik, "ig_baslik": baslik, "slayt_ozet": caption, "ig_caption": caption}]
            ayarlar: dict = {}
            if len(tw_haberler) > 1 or (public_urller and len(public_urller) > 1):
                tw_id, tw_adet = twitter.zincir_yayinla(tw_haberler, public_urller, ayarlar)
                with _lock:
                    twitter_id = tw_id
                    if tw_id:
                        rapor_satirlari.append(f"🐦 <b>X (Twitter):</b> {tw_adet} tweet zinciri paylaşıldı ✓")
                    else:
                        rapor_satirlari.append("🐦 <b>X (Twitter):</b> Hata oluştu ✗")
            else:
                tw_id = twitter.tekil_yayinla(tw_haberler[0], public_urller, ayarlar)
                with _lock:
                    twitter_id = tw_id
                    if tw_id:
                        rapor_satirlari.append("🐦 <b>X (Twitter):</b> Paylaşıldı ✓")
                    else:
                        rapor_satirlari.append("🐦 <b>X (Twitter):</b> Hata oluştu ✗")
        except Exception as te:
            log.warning("Twitter paylaşım hatası: %s", te)
            with _lock:
                rapor_satirlari.append(f"🐦 <b>X (Twitter):</b> Hata ({te}) ✗")
        _bildir("twitter", "✅ Yayında" if twitter_id else "❌ Hata", increment=True)

    kanal_islevleri = {
        "tiktok": _is_tiktok,
        "instagram": _is_instagram,
        "reels": _is_reels,
        "story": _is_story,
        "threads": _is_threads,
        "facebook": _is_facebook,
        "facebook_reels": _is_facebook,
        "youtube": _is_youtube,
        "linkedin": _is_linkedin,
        "twitter": _is_twitter,
        "x": _is_twitter,
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
        guncelleme = {"durum": durum_kurali.sonraki_durum(haber.get("durum") if haber else None, herhangi_biri_basarili),
                      "planlanan_yayin": None}
        if herhangi_biri_basarili and not (haber and haber.get("yayin_zamani")):
            guncelleme["yayin_zamani"] = datetime.now(timezone.utc).isoformat()
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
        if twitter_id:
            guncelleme["twitter_tweet_id"] = twitter_id
        if linkedin_id:
            guncelleme["linkedin_post_id"] = linkedin_id
        if v_yolu and v_yolu.exists():
            guncelleme["video_yolu"] = str(v_yolu)
        db.haber_guncelle(int(ref_id), **guncelleme)
        if herhangi_biri_basarili and tur == "haber":
            site_notu = _site_taslagi_aktar(haber)
            if site_notu:
                rapor_satirlari.append(site_notu)
    elif tur == "ilan" and herhangi_biri_basarili:
        db.ilan_paylasildi_isaretle(ref_id)

    db.onay_istegi_sonuclandir(tur, str(ref_id), "yayinlandi" if herhangi_biri_basarili else "hata")
    db.wal_bosalt()

    # 6. Telegram'a Sonuç Raporu, Canlı Linkler ve Telafi Butonları İlet
    if not rapor_satirlari:
        raise RuntimeError(f"Geçerli yayın hedefi bulunamadı: {hedef}")
    hata_var = any("✗" in satir for satir in rapor_satirlari)
    gecen_sure = (time.time() - baslangic_ts) if baslangic_ts > 0 else 0.0

    temiz_caption = html_lib.escape(caption.strip())
    caption_kutu = f"\n\n📝 <b>Açıklama Metni (Kopyalamak İçin Dokunun):</b>\n<pre><code>{temiz_caption}</code></pre>"

    baslik_icon = "⚠️" if hata_var else "🎉"
    baslik_durum = "YAYIN KISMEN TAMAMLANDI" if hata_var else "YAYIN BAŞARIYLA TAMAMLANDI"

    satirlar_sonuc = [
        f"{baslik_icon} <b>{baslik_durum}</b>\n",
        f"📌 <b>İçerik:</b> {html_lib.escape(baslik)}",
    ]
    if gecen_sure > 0:
        satirlar_sonuc.append(f"⏱️ <b>Dağıtım Süresi:</b> {gecen_sure:.1f} sn")
    satirlar_sonuc.append("\n📱 <b>Platform Sonuçları:</b>")
    for r in rapor_satirlari:
        satirlar_sonuc.append(f"• {r}")

    sonuc_metni = "\n".join(satirlar_sonuc)
    if len(sonuc_metni) + len(caption_kutu) <= 3900:
        sonuc_metni += caption_kutu
        caption_ayri_gonder = False
    else:
        caption_ayri_gonder = True

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
    if linkedin_id:
        canli_linkler.append({"text": "💼 LinkedIn'de Gör", "url": f"https://www.linkedin.com/feed/update/{linkedin_id}/"})
    if twitter_id:
        tw_url = twitter.post_baglantisi(twitter_id)
        if tw_url:
            canli_linkler.append({"text": "🐦 X'te Gör", "url": tw_url})

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
    if (("li" in hedefler or "linkedin" in hedefler) or ("hepsi" in hedefler and linkedin.kullanilabilir_mi())) and not linkedin_id:
        telafi_dugmeleri.append([{"text": "🔄 💼 LinkedIn'i Tekrar Dene", "callback_data": f"retry_kanal:linkedin:{ref_id}"}])
    if (("x" in hedefler or "twitter" in hedefler) or ("hepsi" in hedefler and twitter.kullanilabilir_mi())) and not twitter_id:
        telafi_dugmeleri.append([{"text": "🔄 🐦 X'i Tekrar Dene", "callback_data": f"retry_kanal:twitter:{ref_id}"}])

    if len(telafi_dugmeleri) > 1:
        telafi_dugmeleri.insert(0, [{"text": "🔄 Başarısız Tüm Kanalları Tekrar Dene", "callback_data": f"retry_kanal:hepsi:{ref_id}"}])

    kontrol_dugmesi = [[{"text": "🔍 Yayın durumunu kontrol et", "callback_data": f"yayin_kontrol:{ref_id}"}]]
    silme_dugmesi = [[{"text": "🗑️ Bu Yayını Kaldır", "callback_data": f"kaldir:{tur}:{ref_id}"}]]
    sonuc_tuslari = canli_link_dugmeleri + telafi_dugmeleri + kontrol_dugmesi + silme_dugmesi
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
        # Eğer bu içerik için hatırlatma atılmışsa ve birden fazla onay/hatırlatma mesajı varsa:
        # Sonucu yazdığımız mesaj hariç diğer eski mesajları temizle (chat kaosunu sıfırla)
        telegram_bot.icerik_onceki_mesajlarini_temizle(tur, ref_id, haric_mesaj_id=args.mesaj_id)
        try:
            Path("data/son_rapor_gonderildi.txt").write_text(str(ref_id), encoding="utf-8")
        except Exception:
            pass
        if temiz_caption:
            telegram_bot.mesaj_gonder(
                f"📝 <b>İçerik #{ref_id} Kopyalanabilir Açıklama Metni (Caption):</b>\n\n"
                f"<pre><code>{temiz_caption}</code></pre>"
            )
    except Exception as bildirim_hatasi:
        log.warning("Telegram sonuç bildirimi gönderilemedi: %s", bildirim_hatasi)

    # 7. Hazırlanan 9:16 Dikey Videoyu Telegram Grubuna İlet (Her yayında hazır video teslim edilir)
    gonderilecek_video = sesli_video_yolu if (sesli_video_yolu and Path(sesli_video_yolu).exists()) else (
        v_yolu if (v_yolu and Path(v_yolu).exists()) else None
    )
    if gonderilecek_video and gonderilecek_video.exists() and not video_telegrama_gitti:
        try:
            log.info("Hazırlanan dikey video Telegram grubuna iletiliyor: %s", gonderilecek_video)
            telegram_bot.video_gonder(
                gonderilecek_video,
                aciklama=f"🎬 <b>EDM Reels Videosu (1080x1920 MP4)</b>\n\n"
                         f"📌 <b>Konu:</b> {html_lib.escape(baslik)}\n\n"
                         f"💡 <i>Videoyu cihazınıza kaydedip Instagram / TikTok uygulamasından doğrudan paylaşabilirsiniz.</i>",
            )
            video_telegrama_gitti = True
        except Exception as ve:
            log.warning("Telegram'a video iletilemedi: %s", ve)

    # 8. Kopyalanabilir açıklama metni (Kullanıcı talebi: yayınla aşamasında video ve kopyalanabilir açıklama)
    if caption:
        try:
            telegram_bot.mesaj_gonder(
                f"📋 <b>Kopyalanabilir Açıklama (Reels / Post):</b>\n\n<code>{html_lib.escape(caption)}</code>"
            )
        except Exception as ce:
            log.warning("Telegram'a kopyalanabilir açıklama iletilemedi: %s", ce)
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
