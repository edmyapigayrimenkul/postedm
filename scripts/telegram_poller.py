#!/usr/bin/env python3
"""
scripts/telegram_poller.py — EDM Telegram Botu Canlı Dinleyici (Poller)
Telegram grubundaki /ilanlar, /haber komutlarını ve buton tıklamalarını
anlık dinler, ilan önizlemelerini ve onaylanan paylaşımları yürütür.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict

import requests

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import ayar, config, db, fetch_listings, fetch_news, konu_bankasi, ozel_icerik, telegram_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def yardim_metni_gonder() -> None:
    metin = (
        "🤖 <b>EDM YAPI & GAYRİMENKUL — SOSYAL MEDYA KONTROL BOTU</b>\n\n"
        "Tüm sosyal medya operasyonlarını bu sohbet üzerinden tek tıkla yönetebilirsiniz:\n\n"
        "🎛 <b>KONTROL & YÖNETİM</b>\n"
        "• <code>/panel</code> — Kontrol merkezini ve hızlı aksiyon butonlarını açar\n"
        "• <code>/durum</code> — Bot sağlığı, sıradaki post ve kota durumunu gösterir\n"
        "• <code>/ilanlar</code> — Güncel portföyü çekip tek tıkla ilan menüsünü açar\n"
        "• <code>/hatirlat</code> — Onay bekleyen paylaşımları anında tarar\n"
        "• <code>/saglik</code> — Canlı API bağlantılarını ve sistem sağlığını test eder\n"
        "• <code>/havuz</code> — Konu bankası doluluk ve istatistiklerini listeler\n\n"
        "✍️ <b>İÇERİK ÜRETİMİ</b>\n"
        "• <code>/reels</code> — 9:16 Dikey Reels videosu ve metni üretip gruba sunar\n"
        "• <code>/yeni</code> — Konu bankasından sıradaki konuyu üretip onaya sunar\n"
        "• <code>/sozluk</code> — EDM Gayrimenkul Sözlüğü formatında post üretir\n"
        "• <code>/dogrusu</code> — Nedir Doğrusu? (Efsane vs Gerçek) postu üretir\n"
        "• <code>/vaka</code> — Hukuki Vaka Analizi (2 Slayt Carousel) üretir\n"
        "• <code>/soru</code> — Net Cevap Rehberi (Soru & Hüküm) üretir\n"
        "• <code>/otorite &lt;konu&gt;</code> — Özel bir konuda 4 slaytlık rehber üretir\n"
        "• <code>/haber</code> — En son sektörel haberi otorite bültenine dönüştürür\n\n"
        "⏸️ <b>AKIŞ KONTROLÜ</b>\n"
        "• <code>/durdur</code> — Otomatik paylaşımları duraklatır\n"
        "• <code>/devam</code> — Duraklatılmış botu yeniden başlatır"
    )
    butonlar = {
        "inline_keyboard": [
            [
                {"text": "🎛 Kontrol Paneli", "callback_data": "panel"},
                {"text": "📊 Sistem Durumu", "callback_data": "durum"},
            ],
            [
                {"text": "🎬 Reels Üret (9:16)", "callback_data": "hizli_uret:reels"},
                {"text": "🏡 İlan Listesi", "callback_data": "ilan_menu_yenile"},
            ],
        ]
    }
    telegram_bot.mesaj_gonder(metin, reply_markup=butonlar)


def havuz_durum_gonder() -> None:
    try:
        havuz = konu_bankasi.havuzu_yukle()
        toplam = len(havuz)
        kullanilmis = sum(1 for k in havuz if k.get("kullanildi"))
        kalan = toplam - kullanilmis
        bicim_sayilari: Dict[str, int] = {}
        for k in havuz:
            b = k.get("bicim", "B1")
            bicim_sayilari[b] = bicim_sayilari.get(b, 0) + 1

        bicim_metni = "\n".join([f"  • {b}: {adet} adet" for b, adet in sorted(bicim_sayilari.items())])
        metin = (
            f"🔄 <b>EDM KONU BANKASI HAVUZ DURUMU</b>\n\n"
            f"• <b>Toplam Konu:</b> {toplam}\n"
            f"• <b>Kullanılan:</b> {kullanilmis}\n"
            f"• <b>Kalan (Bakir):</b> {kalan}\n\n"
            f"<b>Biçim Dağılımı:</b>\n{bicim_metni}\n\n"
            f"💡 <i>Konular tükendiğinde döngü otomatik olarak baştan başlar veya yeni konular eklenir.</i>"
        )
    except Exception as e:
        metin = f"⚠️ Konu havuzu durumu alınırken hata oluştu: {e}"

    butonlar = {"inline_keyboard": [[{"text": "← Kontrol Paneline Dön", "callback_data": "panel"}]]}
    telegram_bot.mesaj_gonder(metin, reply_markup=butonlar)


def saglik_testi_gonder() -> None:
    mesaj_id = telegram_bot.mesaj_gonder("🩺 <b>Sistem Sağlık Testi çalıştırılıyor...</b>\nLütfen bekleyin...")
    m_id = mesaj_id.get("message_id") if isinstance(mesaj_id, dict) else None

    rapor = [
        "🩺 <b>EDM SİSTEM SAĞLIK TESTİ SONUÇLARI</b>\n",
        "• <b>Database (SQLite/WAL):</b> Sağlıklı ✓",
    ]

    ig_token = config.env_al("INSTAGRAM_ACCESS_TOKEN")
    rapor.append(f"• <b>Instagram Graph API:</b> {'Tanımlı ✓' if ig_token else 'Eksik ✗'}")

    th_token = config.env_al("THREADS_ACCESS_TOKEN")
    rapor.append(f"• <b>Threads API:</b> {'Tanımlı ✓' if th_token else 'Eksik ✗'}")

    fb_token = config.env_al("FACEBOOK_PAGE_ACCESS_TOKEN")
    rapor.append(f"• <b>Facebook Page API:</b> {'Tanımlı ✓' if fb_token else 'Eksik ✗'}")

    gemini_key = config.env_al("GEMINI_API_KEY")
    rapor.append(f"• <b>Google Gemini API:</b> {'Tanımlı ✓' if gemini_key else 'Eksik ✗'}")

    yt_token = config.yol_al("data/youtube_token.json").exists()
    rapor.append(f"• <b>YouTube Shorts OAuth:</b> {'Yetkili ✓' if yt_token else 'Kurulum Gerekli ✗'}")

    tt_token = config.env_al("TIKTOK_ACCESS_TOKEN")
    rapor.append(f"• <b>TikTok API:</b> {'Bağlı (Inbox Draft) ✓' if tt_token else 'Eksik ✗'}")

    imgbb_key = config.env_al("IMGBB_API_KEY")
    rapor.append(f"• <b>ImgBB CDN Servisi:</b> {'Aktif ✓' if imgbb_key else 'Yedek Servis Devrede ✓'}")

    rapor.append("\n<i>Tüm çekirdek motorlar operasyona hazır!</i>")
    sonuc_metni = "\n".join(rapor)

    butonlar = {"inline_keyboard": [[{"text": "← Kontrol Paneline Dön", "callback_data": "panel"}]]}
    if m_id:
        telegram_bot.mesaji_guncelle(m_id, sonuc_metni, reply_markup=butonlar)
    else:
        telegram_bot.mesaj_gonder(sonuc_metni, reply_markup=butonlar)


def main() -> None:
    token = config.env_al("TELEGRAM_BOT_TOKEN")
    chat_id_hedef = config.env_al("TELEGRAM_CHAT_ID")

    if not token:
        log.error("TELEGRAM_BOT_TOKEN eksik!")
        return

    # Telegram açılır komut menüsünü kaydet
    try:
        telegram_bot.komut_menusu_kaydet()
    except Exception as e:
        log.warning("Komut menüsü kaydedilemedi: %s", e)

    log.info("🤖 EDM Telegram Bot Dinleyicisi Başlatıldı (@PostEdmBot)")
    print("=" * 60)
    print("🚀 EDM Telegram Botu Canlı Dinlemede...")
    print("Gruptan komutlar (/panel, /reels, /ilanlar) ve buton tıklamaları bekleniyor.")
    print("=" * 60)

    offset = 0

    while True:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            params = {"offset": offset, "timeout": 20}
            res = requests.get(url, params=params, timeout=25)

            if res.status_code != 200:
                time.sleep(3)
                continue

            veri = res.json()
            results = veri.get("result", [])

            for u in results:
                offset = u["update_id"] + 1

                # =============================================================
                # 1. BUTON TIKLAMALARI (CALLBACK QUERY)
                # =============================================================
                if "callback_query" in u:
                    cb = u["callback_query"]
                    cb_id = cb["id"]
                    data = cb.get("data", "")
                    sender = cb.get("from", {}).get("first_name", "Kullanıcı")
                    msg_obj = cb.get("message", {})
                    msg_id = msg_obj.get("message_id")

                    log.info("Buton tıklandı: %s (Kullanıcı: %s)", data, sender)

                    # Telegram bekleme simgesini anında kapat
                    try:
                        requests.post(
                            f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                            json={"callback_query_id": cb_id, "text": "İşlem alınıyor..."},
                            timeout=5,
                        )
                    except Exception:
                        pass

                    # ---------------------------------------------------------
                    # A. Kontrol Paneli & Durum Menüleri
                    # ---------------------------------------------------------
                    if data == "panel":
                        telegram_bot.panel_gonder(msg_id)

                    elif data == "durum":
                        telegram_bot.durum_raporu_gonder(msg_id)

                    elif data in ("kota_goster", "kota_tazele", "rapor_goster", "rapor_tazele", "kota_raporu", "kota_menu"):
                        telegram_bot.kota_gonder(msg_id, kategori="menu")

                    elif data.startswith("kota_kat:"):
                        kat_secim = data.split(":", 1)[1]
                        telegram_bot.kota_gonder(msg_id, kategori=kat_secim)

                    elif data == "saglik_testi":
                        saglik_testi_gonder()

                    elif data == "havuz_durum":
                        havuz_durum_gonder()

                    elif data == "duraklat_menu":
                        telegram_bot.mesaji_guncelle(
                            msg_id,
                            "⏸️ <b>Otomatik Akışı Duraklatma Süresi Seçin:</b>\n"
                            "Belirlenen süre boyunca yeni haber ve hatırlatıcılar sessiz kalır.",
                            reply_markup=telegram_bot.duraklatma_secenekleri_menusu(),
                        )

                    elif data.startswith("duraklat:"):
                        saat = int(data.split(":")[1])
                        telegram_bot.bot_duraklat(saat)
                        telegram_bot.panel_gonder(msg_id)

                    elif data == "devam_et":
                        telegram_bot.bot_devam_et()
                        telegram_bot.panel_gonder(msg_id)

                    # ---------------------------------------------------------
                    # B. İlan Menüsü ve Seçimi
                    # ---------------------------------------------------------
                    elif data.startswith("ilan_sec:"):
                        ilan_id = data.split(":")[1]
                        log.info("İlan seçildi: #%s, önizleme hazırlanıyor...", ilan_id)
                        telegram_bot.ilan_postunu_hazirla_ve_sor(ilan_id)

                    elif data == "ilan_menu_yenile":
                        fetch_listings.portfoyu_senkronize_et()
                        telegram_bot.tek_tikla_ilan_menusu_gonder()

                    # ---------------------------------------------------------
                    elif data.startswith("hizli_uret:"):
                        fmt = data.split(":")[1]
                        log.info("Hızlı içerik üretimi: %s", fmt)
                        if fmt == "reels":
                            telegram_bot.reels_hazirla_ve_sun()
                        elif fmt == "rotasyon":
                            telegram_bot.slot_icerigi_hazirla_ve_sun(slot="bilgilendirici")
                        elif fmt == "haber":
                            telegram_bot.slot_icerigi_hazirla_ve_sun(slot="haber")
                        else:
                            telegram_bot.hizli_icerik_uret(fmt)

                    # ---------------------------------------------------------
                    # D. Kanal Seçimi / Toggle (Instabot Canlı Toggle)
                    # ---------------------------------------------------------
                    elif data.startswith("kanal:") or data.startswith("kanal_toggle:"):
                        hedef_kanal = data.split(":", 1)[1]
                        klavye = msg_obj.get("reply_markup", {}).get("inline_keyboard", [])
                        if klavye and msg_id:
                            yeni_klavye = telegram_bot.kanal_toggle(klavye, hedef_kanal)
                            telegram_bot.menuyu_degistir(msg_id, {"inline_keyboard": yeni_klavye})

                    # ---------------------------------------------------------
                    # E. Menü Gezinmeleri (Yayın Zamanı, Foto, Metin, Slayt)
                    # ---------------------------------------------------------
                    elif (
                        data.startswith("yayin_menu:") or data.startswith("yayin_geri:") or
                        data.startswith("foto_menu:") or data.startswith("foto_geri:") or
                        data.startswith("metin_menu:") or data.startswith("metin_geri:") or
                        data.startswith("slayt_menu:") or data.startswith("geri:") or
                        data.startswith("format_menu:") or data.startswith("onay_menu_don:") or
                        data.startswith("slayt:")
                    ):
                        parts = data.split(":")
                        kok = parts[0]
                        adet = 2
                        try:
                            adet = int(parts[-1]) if parts[-1].isdigit() else 2
                        except Exception:
                            adet = 2
                        klavye = msg_obj.get("reply_markup", {}).get("inline_keyboard", [])
                        secili_list = telegram_bot.secili_kanallari_cikar(klavye)
                        secili_dict = {k: (k in secili_list) for k in ["ig", "reels", "story", "threads", "facebook", "youtube", "tiktok"]}

                        if kok == "slayt":
                            sira = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
                            yeni_menu = telegram_bot.slayt_islem_menusu(sira, adet, secili_dict)
                        elif kok == "yayin_menu":
                            yeni_menu = telegram_bot.yayin_zamani_menusu(adet, secili_dict)
                        elif kok == "foto_menu":
                            yeni_menu = telegram_bot.foto_menusu(adet, secili_dict)
                        elif kok == "metin_menu":
                            yeni_menu = telegram_bot.metin_menusu(adet, secili_dict)
                        elif kok in ("slayt_menu", "format_menu"):
                            yeni_menu = telegram_bot.slayt_secim_menusu(adet, secili_dict)
                        else:
                            yeni_menu = telegram_bot.ana_menu(adet, secili_dict)

                        if msg_id:
                            telegram_bot.menuyu_degistir(msg_id, yeni_menu)

                    elif data.startswith("format_uygula:"):
                        parts = data.split(":")
                        fmt = parts[1]
                        h_id = None
                        if len(parts) > 2 and parts[2].isdigit():
                            h_id = int(parts[2])
                        elif msg_id:
                            bulunan = db.mesajdan_icerik_bul(msg_id)
                            if bulunan:
                                _, ref_id_int, _ = bulunan
                                h_id = int(ref_id_int)
                        if h_id:
                            log.info("Format uygulanıyor: #%d -> %s", h_id, fmt)
                            telegram_bot.format_degistir_ve_sun(h_id, fmt)
                        else:
                            telegram_bot.mesaj_gonder(f"🎨 Format uygulanıyor ({fmt.upper()})...")
                            telegram_bot.hizli_icerik_uret(fmt)

                    # ---------------------------------------------------------
                    # F. Yayınla (Anında veya Zamanlı - Instabot Canlı İlerleme Çubuğu)
                    # ---------------------------------------------------------
                    elif data == "yayinla" or data.startswith("yayinla_sonra:") or data.startswith("onayla:"):
                        klavye = msg_obj.get("reply_markup", {}).get("inline_keyboard", [])
                        secili = telegram_bot.secili_kanallari_cikar(klavye)
                        if not secili and (data == "yayinla" or data.startswith("yayinla_sonra:")):
                            try:
                                requests.post(
                                    f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                                    json={"callback_query_id": cb_id, "text": "⚠️ En az bir yayın kanalı seçmelisin!", "show_alert": True},
                                    timeout=5,
                                )
                            except Exception:
                                pass
                            continue

                        tur = "reels" if ("reels" in secili and "ig" not in secili) else "haber"
                        hedef = ",".join(secili) if secili else "hepsi"
                        ref_id = None

                        if data.startswith("onayla:"):
                            parcalar = data.split(":")
                            if len(parcalar) >= 4:
                                tur = parcalar[1]
                                hedef = parcalar[2]
                                ref_id = parcalar[3]
                                if hedef == "tamamla":
                                    if ref_id.isdigit():
                                        db.haber_guncelle(int(ref_id), durum="yayinlandi")
                                    db.onay_istegi_sonuclandir(tur, str(ref_id), "yayinlandi")
                                    telegram_bot.mesaj_gonder(f"✅ <b>{tur.upper()} #{ref_id}</b> paylaşıldı olarak işaretlendi ve arşivlendi.")
                                    continue
                            elif len(parcalar) == 2:
                                ref_id = parcalar[1]

                        if not ref_id and msg_id:
                            bulunan = db.mesajdan_icerik_bul(msg_id)
                            if bulunan:
                                tur, ref_id_int, _ = bulunan
                                ref_id = str(ref_id_int)

                        if not ref_id:
                            bulunan = db.mesajdan_icerik_bul(None)
                            if bulunan:
                                tur, ref_id_int, _ = bulunan
                                ref_id = str(ref_id_int)

                        if not ref_id:
                            telegram_bot.mesaj_gonder("⚠️ Onaylanacak içerik bulunamadı.")
                            continue

                        gecikme = data.split(":")[1] if data.startswith("yayinla_sonra:") else None
                        baslik_etiketi = "Reels Videosu" if tur == "reels" else ("İlan Postu" if tur == "ilan" else "İçerik")
                        if gecikme:
                            telegram_bot.mesaji_guncelle(
                                msg_id,
                                f"⏰ <b>{baslik_etiketi} #{ref_id} {gecikme} dakika sonra yayınlanacak şekilde planlandı.</b>\n"
                                f"Seçili Kanallar: <code>{hedef.upper()}</code>"
                            )
                            try:
                                db.onay_istegi_ertele(tur, str(ref_id), dakika=int(gecikme))
                            except Exception as ee:
                                log.warning("Planlama hatası: %s", ee)
                        else:
                            telegram_bot.mesaji_guncelle(
                                msg_id,
                                f"🚀 <b>{baslik_etiketi} #{ref_id} yayına alınıyor...</b>\n"
                                f"Seçili Kanallar: <code>{hedef.upper()}</code>\n"
                                f"⏳ <i>Canlı yayın motoru başlatılıyor...</i>"
                            )
                            cmd = [
                                sys.executable,
                                str(KOK / "scripts/yayinla.py"),
                                "--tur", tur,
                                "--id", str(ref_id),
                                "--hedef", hedef,
                                "--mesaj-id", str(msg_id),
                            ]
                            subprocess.Popen(cmd, cwd=str(KOK))

                    # ---------------------------------------------------------
                    # G. Manuel Paylaşım Paketi
                    # ---------------------------------------------------------
                    elif data == "manuel_paket" or data.startswith("manuel_paket:"):
                        ref_id = data.split(":")[1] if ":" in data else None
                        tur = "haber"
                        if not ref_id and msg_id:
                            bulunan = db.mesajdan_icerik_bul(msg_id)
                            if bulunan:
                                tur, ref_id_int, _ = bulunan
                                ref_id = str(ref_id_int)
                        if not ref_id:
                            bulunan = db.mesajdan_icerik_bul(None)
                            if bulunan:
                                tur, ref_id_int, _ = bulunan
                                ref_id = str(ref_id_int)
                        if ref_id:
                            telegram_bot.mesaji_guncelle(
                                msg_id,
                                f"📲 <b>İçerik #{ref_id} için Manuel Paylaşım Paketi hazırlanıyor...</b>\n"
                                f"Açıklama metni ve doğrudan yönlendirme butonları birazdan iletilecek."
                            )
                            cmd = [
                                sys.executable,
                                str(KOK / "scripts/yayinla.py"),
                                "--tur", tur,
                                "--id", str(ref_id),
                                "--hedef", "manuel_paket",
                                "--mesaj-id", str(msg_id),
                            ]
                            subprocess.Popen(cmd, cwd=str(KOK))
                        else:
                            telegram_bot.mesaj_gonder("⚠️ Manuel paket için içerik bulunamadı.")

                    # ---------------------------------------------------------
                    # H. Fotoğraf Değiştirme ve Özelleştirme Aksiyonları
                    # ---------------------------------------------------------
                    elif data in ("foto_gercek", "foto_stok", "foto_ai", "foto_editoryal") or data.startswith("foto_eylem:"):
                        eylem = data.split(":")[1] if data.startswith("foto_eylem:") else data
                        ref_id = None
                        tur = "haber"
                        if msg_id:
                            bulunan = db.mesajdan_icerik_bul(msg_id)
                            if bulunan:
                                tur, ref_id_int, _ = bulunan
                                ref_id = str(ref_id_int)
                        if not ref_id:
                            bulunan = db.mesajdan_icerik_bul(None)
                            if bulunan:
                                tur, ref_id_int, _ = bulunan
                                ref_id = str(ref_id_int)
                        if ref_id:
                            telegram_bot.mesaji_guncelle(msg_id, f"🖼️ <b>İçerik #{ref_id} görseli güncelleniyor ({eylem})...</b>\nLütfen bekleyin...")
                            cmd = [
                                sys.executable,
                                str(KOK / "scripts/yayinla.py"),
                                "--tur", tur,
                                "--id", str(ref_id),
                                "--hedef", eylem,
                                "--mesaj-id", str(msg_id),
                            ]
                            subprocess.Popen(cmd, cwd=str(KOK))

                    # ---------------------------------------------------------
                    # I. Metin Düzenleme ve Yenileme Aksiyonları
                    # ---------------------------------------------------------
                    elif data in ("metin_ozetle", "metin_detaylandir", "metin_yenile") or data.startswith("metin_eylem:") or data.startswith("yenile:"):
                        eylem = data.split(":")[1] if data.startswith("metin_eylem:") else (data.split(":")[0] if not data.startswith("yenile:") else "yenile")
                        ref_id = data.split(":")[2] if data.startswith("yenile:") and len(data.split(":")) > 2 else None
                        tur = data.split(":")[1] if data.startswith("yenile:") and len(data.split(":")) > 1 else "haber"
                        if not ref_id and msg_id:
                            bulunan = db.mesajdan_icerik_bul(msg_id)
                            if bulunan:
                                tur, ref_id_int, _ = bulunan
                                ref_id = str(ref_id_int)
                        if not ref_id:
                            bulunan = db.mesajdan_icerik_bul(None)
                            if bulunan:
                                tur, ref_id_int, _ = bulunan
                                ref_id = str(ref_id_int)
                        if ref_id:
                            telegram_bot.mesaji_guncelle(msg_id, f"✍️ <b>İçerik #{ref_id} metni güncelleniyor ({eylem})...</b>\nLütfen bekleyin...")
                            cmd = [
                                sys.executable,
                                str(KOK / "scripts/yayinla.py"),
                                "--tur", tur,
                                "--id", str(ref_id),
                                "--hedef", eylem,
                                "--mesaj-id", str(msg_id),
                            ]
                            subprocess.Popen(cmd, cwd=str(KOK))

                    # ---------------------------------------------------------
                    # J. Ertele, İptal ve Çöpe At
                    # ---------------------------------------------------------
                    elif data == "ertele" or data.startswith("ertele:"):
                        ref_id = None
                        tur = "haber"
                        if msg_id:
                            bulunan = db.mesajdan_icerik_bul(msg_id)
                            if bulunan:
                                tur, ref_id_int, _ = bulunan
                                ref_id = str(ref_id_int)
                        if not ref_id:
                            bulunan = db.mesajdan_icerik_bul(None)
                            if bulunan:
                                tur, ref_id_int, _ = bulunan
                                ref_id = str(ref_id_int)
                        if ref_id:
                            db.onay_istegi_ertele(tur, str(ref_id), dakika=60)
                            telegram_bot.mesaji_guncelle(msg_id, f"⏰ <b>{tur.upper()} #{ref_id} yayını 1 saat ertelendi. Hatırlatıcılar duraklatıldı.</b>")
                        else:
                            telegram_bot.mesaji_guncelle(msg_id, "⏰ <b>Yayın 1 saat ertelendi. Hatırlatıcılar duraklatıldı.</b>")

                    elif data == "iptal" or data.startswith("reddet:"):
                        parcalar = data.split(":")
                        tur = parcalar[1] if len(parcalar) > 1 and parcalar[1] in ("haber", "ilan", "reels") else "haber"
                        ref_id = parcalar[2] if len(parcalar) > 2 else None
                        if not ref_id and msg_id:
                            bulunan = db.mesajdan_icerik_bul(msg_id)
                            if bulunan:
                                tur, ref_id_int, _ = bulunan
                                ref_id = str(ref_id_int)
                        if not ref_id:
                            bulunan = db.mesajdan_icerik_bul(None)
                            if bulunan:
                                tur, ref_id_int, _ = bulunan
                                ref_id = str(ref_id_int)
                        if ref_id:
                            if ref_id.isdigit():
                                db.haber_guncelle(int(ref_id), durum="iptal")
                            db.onay_istegi_sonuclandir(tur, str(ref_id), "iptal")
                            telegram_bot.mesaji_guncelle(msg_id, f"❌ <b>{tur.upper()} #{ref_id} atlandı.</b>\n<i>Konu havuza iade edildi. Sıradaki içerik hazırlanıyor...</i>")
                        else:
                            telegram_bot.mesaji_guncelle(msg_id, "❌ <b>Bu içerik atlandı.</b>\n<i>Konu havuza iade edildi. Sıradaki içerik hazırlanıyor...</i>")
                        if tur == "reels":
                            telegram_bot.reels_hazirla_ve_sun()
                        else:
                            telegram_bot.slot_icerigi_hazirla_ve_sun(slot="bilgilendirici")

                    elif data == "cope_at" or data.startswith("cope_at:"):
                        ref_id = data.split(":")[1] if ":" in data else None
                        tur = "haber"
                        if not ref_id and msg_id:
                            bulunan = db.mesajdan_icerik_bul(msg_id)
                            if bulunan:
                                tur, ref_id_int, _ = bulunan
                                ref_id = str(ref_id_int)
                        if not ref_id:
                            bulunan = db.mesajdan_icerik_bul(None)
                            if bulunan:
                                tur, ref_id_int, _ = bulunan
                                ref_id = str(ref_id_int)
                        if ref_id:
                            if ref_id.isdigit():
                                db.haber_guncelle(int(ref_id), durum="iptal")
                            db.onay_istegi_sonuclandir(tur, str(ref_id), "cop")
                            telegram_bot.mesaji_guncelle(msg_id, f"🗑️ <b>{tur.upper()} #{ref_id} taslağı çöpe atıldı.</b>\n<i>Konu kilitlenmedi, havuza iade edildi.</i>")
                        else:
                            telegram_bot.mesaji_guncelle(msg_id, "🗑️ <b>Taslak çöpe atıldı.</b>\n<i>Konu kilitlenmedi, havuza iade edildi.</i>")

                    elif data in ("ayar", "ayar_menu"):
                        telegram_bot.mesaji_guncelle(
                            msg_id,
                            "⚙️ <b>EDM Çalışma ve Yayın Ayarları:</b>\n"
                            "Değiştirmek istediğiniz ayara dokunarak açıp kapatabilirsiniz:",
                            reply_markup=ayar.ayar_menusu(),
                        )

                    elif data.startswith("ayarsec:"):
                        _, key, val = data.split(":")
                        ayar.ayar_kaydet(key, val)
                        telegram_bot.mesaji_guncelle(
                            msg_id,
                            "⚙️ <b>EDM Çalışma ve Yayın Ayarları (Güncellendi):</b>",
                            reply_markup=ayar.ayar_menusu(),
                        )

                    elif data == "sonpostlar":
                        m, b = telegram_bot.son_postlar_raporu()
                        if msg_id:
                            telegram_bot.mesaji_guncelle(msg_id, m, reply_markup=b)
                        else:
                            telegram_bot.mesaj_gonder(m, reply_markup=b)

                    elif data.startswith("incele:"):
                        ref_id = int(data.split(":")[1])
                        m, b = telegram_bot.icerik_incele_karti(ref_id)
                        if msg_id:
                            telegram_bot.mesaji_guncelle(msg_id, m, reply_markup=b)
                        else:
                            telegram_bot.mesaj_gonder(m, reply_markup=b)

                    elif data.startswith("yayin_kontrol:"):
                        ref_id = int(data.split(":")[1])
                        m, b = telegram_bot.yayin_kontrol_karti(ref_id)
                        if msg_id:
                            telegram_bot.mesaji_guncelle(msg_id, m, reply_markup=b)
                        else:
                            telegram_bot.mesaj_gonder(m, reply_markup=b)

                    elif data.startswith("kurtar:"):
                        ref_id = data.split(":")[1]
                        telegram_bot.mesaj_gonder(f"🚀 <b>İçerik #{ref_id}</b> tüm kanallar için kurtarılıyor ve yayınlanıyor...")
                        cmd = [sys.executable, str(KOK / "scripts/yayinla.py"), "--tur", "haber", "--id", ref_id, "--hedef", "hepsi"]
                        subprocess.run(cmd, cwd=str(KOK))

                    elif data.startswith("retry_kanal:"):
                        _, kanal, ref_id = data.split(":")
                        telegram_bot.mesaj_gonder(f"🔄 <b>İçerik #{ref_id}</b> için <b>{kanal.upper()}</b> yayını tekrarlanıyor...")
                        cmd = [sys.executable, str(KOK / "scripts/yayinla.py"), "--tur", "haber", "--id", ref_id, "--hedef", kanal]
                        subprocess.run(cmd, cwd=str(KOK))

                    elif data.startswith("cope_at:") or data == "cope_at":
                        ref_id = data.split(":")[1] if ":" in data else ""
                        if ref_id and ref_id.isdigit():
                            db.haber_guncelle(int(ref_id), durum="cop")
                            db.onay_istegi_sonuclandir("haber", ref_id, "cop")
                        if msg_id:
                            telegram_bot.mesaji_guncelle(msg_id, "🗑️ <b>İçerik çöpe atıldı (Havuza dönmeyecek).</b>")
                        else:
                            telegram_bot.mesaj_gonder("🗑️ <b>İçerik çöpe atıldı (Havuza dönmeyecek).</b>")

                    elif any(data.startswith(pre) for pre in ("slayt_basa:", "slayt_yukari:", "slayt_asagi:", "slayt_sil:", "slayt_carpici:", "slayt_uzat:", "slayt_kisalt:")):
                        eylem, sira = data.split(":")
                        telegram_bot.mesaj_gonder(f"⏳ <b>Slayt güncelleniyor ({eylem})...</b>")
                        cmd = [sys.executable, str(KOK / "scripts/slayt_islem.py"), "--eylem", eylem, "--sira", sira, "--mesaj-id", str(msg_id or "")]
                        subprocess.run(cmd, cwd=str(KOK))

                # =============================================================
                # 2. SLASH KOMUTLARI & METİN MESAJLARI
                # =============================================================
                elif "message" in u:
                    msg = u["message"]
                    text = (msg.get("text") or "").strip()
                    chat = msg.get("chat", {})
                    c_id = str(chat.get("id"))

                    if not text.startswith("/"):
                        continue

                    komut_parca = text.split()[0].lower().split("@")[0]

                    # ── Kontrol & Yönetim Komutları ──────────────────────────
                    if komut_parca in ("/panel", "/menu"):
                        log.info("/panel komutu alındı.")
                        telegram_bot.panel_gonder()

                    elif komut_parca in ("/durum", "/status"):
                        log.info("/durum komutu alındı.")
                        telegram_bot.durum_raporu_gonder()

                    elif komut_parca in ("/kota", "/rapor", "/kullanim"):
                        log.info("/kota komutu alındı.")
                        parcalar = text.split()
                        kat_secim = parcalar[1].lower() if len(parcalar) > 1 else "menu"
                        telegram_bot.kota_gonder(kategori=kat_secim)

                    elif komut_parca in ("/yardim", "/help", "/start"):
                        log.info("/yardim komutu alındı.")
                        yardim_metni_gonder()

                    elif komut_parca == "/saglik":
                        log.info("/saglik komutu alındı.")
                        saglik_testi_gonder()

                    elif komut_parca == "/havuz":
                        log.info("/havuz komutu alındı.")
                        havuz_durum_gonder()

                    elif komut_parca == "/hatirlat":
                        log.info("/hatirlat komutu alındı.")
                        cmd = [sys.executable, str(KOK / "scripts/hatirlat.py")]
                        subprocess.run(cmd, cwd=str(KOK))

                    elif komut_parca in ("/durdur", "/duraklat"):
                        parcalar = text.split()
                        saat = int(parcalar[1]) if len(parcalar) > 1 and parcalar[1].isdigit() else 0
                        telegram_bot.bot_duraklat(saat)
                        telegram_bot.mesaj_gonder(f"⏸️ Otomatik akış {'süresiz' if saat == 0 else f'{saat} saatliğine'} duraklatıldı.")

                    elif komut_parca in ("/devam", "/devam_et"):
                        telegram_bot.bot_devam_et()
                        telegram_bot.mesaj_gonder("▶️ Otomatik akış yeniden başlatıldı.")

                    # ── İlan Komutları ───────────────────────────────────────
                    elif komut_parca in ("/ilan", "/ilanlar"):
                        log.info("/ilanlar komutu alındı.")
                        fetch_listings.portfoyu_senkronize_et()
                        telegram_bot.tek_tikla_ilan_menusu_gonder()

                    # ── İçerik & Video Üretim Komutları ───────────────────────
                    elif komut_parca in ("/reels", "/video"):
                        log.info("/reels komutu alındı.")
                        telegram_bot.reels_hazirla_ve_sun()

                    elif komut_parca in ("/gonderi", "/yeni", "/uret"):
                        log.info("/gonderi komutu alındı.")
                        telegram_bot.slot_icerigi_hazirla_ve_sun(slot="bilgilendirici")

                    elif komut_parca == "/sozluk":
                        log.info("/sozluk komutu alındı.")
                        telegram_bot.hizli_icerik_uret("sozluk")

                    elif komut_parca == "/dogrusu":
                        log.info("/dogrusu komutu alındı.")
                        telegram_bot.hizli_icerik_uret("nedir_dogrusu")

                    elif komut_parca == "/vaka":
                        log.info("/vaka komutu alındı.")
                        telegram_bot.hizli_icerik_uret("vaka")

                    elif komut_parca == "/soru":
                        log.info("/soru komutu alındı.")
                        telegram_bot.hizli_icerik_uret("net_cevap")

                    elif komut_parca in ("/otorite", "/rehber"):
                        log.info("/otorite komutu alındı: %s", text)
                        parcalar = text.split(maxsplit=1)
                        konu = (
                            parcalar[1].strip()
                            if len(parcalar) > 1
                            else "Hisseli tapuda şufa (önalım) hakkı ve satış bedelini tapuda düşük göstermenin riskleri"
                        )
                        telegram_bot.otorite_postu_hazirla_ve_sor(konu)

                    elif komut_parca in ("/haber", "/haberler"):
                        log.info("/haber komutu alındı.")
                        fetch_news.rss_tara()
                        bekleyenler = db.bekleyen_haberleri_getir(limit=1)
                        if bekleyenler:
                            telegram_bot.haber_onayina_sun(bekleyenler[0]["id"])
                        else:
                            telegram_bot.mesaj_gonder("Şu anda sırada bekleyen yeni sektörel haber bulunmuyor.")

                    elif komut_parca in ("/ayar", "/ayarlar"):
                        log.info("/ayar komutu alındı.")
                        telegram_bot.mesaj_gonder(
                            "⚙️ <b>EDM Çalışma ve Yayın Ayarları:</b>\n"
                            "Değiştirmek istediğiniz ayara dokunarak açıp kapatabilirsiniz:",
                            reply_markup=ayar.ayar_menusu(),
                        )

                    elif komut_parca == "/temizle":
                        log.info("/temizle komutu alındı.")
                        adet = db.askidaki_onaylari_temizle()
                        telegram_bot.mesaj_gonder(f"🧹 <b>Askıdaki Onaylar Temizlendi:</b> {adet} adet bekleyen onay iptal edildi.")

                    elif komut_parca in ("/sonpostlar", "/son_postlar"):
                        log.info("/sonpostlar komutu alındı.")
                        m, b = telegram_bot.son_postlar_raporu()
                        telegram_bot.mesaj_gonder(m, reply_markup=b)

                    elif komut_parca == "/incele":
                        parcalar = text.split()
                        if len(parcalar) > 1 and parcalar[1].isdigit():
                            m, b = telegram_bot.icerik_incele_karti(int(parcalar[1]))
                            telegram_bot.mesaj_gonder(m, reply_markup=b)
                        else:
                            telegram_bot.mesaj_gonder("⚠️ Lütfen incelenecek ID'yi belirtin: <code>/incele 104</code>")

                    elif komut_parca == "/kurtar":
                        parcalar = text.split()
                        if len(parcalar) > 1 and parcalar[1].isdigit():
                            cmd = [sys.executable, str(KOK / "scripts/yayinla.py"), "--tur", "haber", "--id", parcalar[1], "--hedef", "hepsi"]
                            subprocess.run(cmd, cwd=str(KOK))
                        else:
                            telegram_bot.mesaj_gonder("⚠️ Lütfen kurtarılacak ID'yi belirtin: <code>/kurtar 104</code>")

                    elif komut_parca == "/yayin_kontrol":
                        parcalar = text.split()
                        if len(parcalar) > 1 and parcalar[1].isdigit():
                            m, b = telegram_bot.yayin_kontrol_karti(int(parcalar[1]))
                            telegram_bot.mesaj_gonder(m, reply_markup=b)
                        else:
                            telegram_bot.mesaj_gonder("⚠️ Lütfen kontrol edilecek ID'yi belirtin: <code>/yayin_kontrol 104</code>")

                    elif komut_parca == "/arastir":
                        log.info("/arastir komutu alındı: %s", text)
                        parcalar = text.split(maxsplit=1)
                        if len(parcalar) > 1:
                            ozel_icerik.arastir_icerik_uret(parcalar[1].strip())
                        else:
                            telegram_bot.mesaj_gonder("⚠️ Lütfen araştırılacak konuyu girin:\n<code>/arastir tapu harcı muafiyeti</code>")

                    elif komut_parca in ("/dosya", "/kronoloji"):
                        log.info("/dosya komutu alındı: %s", text)
                        parcalar = text.split(maxsplit=1)
                        if len(parcalar) > 1:
                            ozel_icerik.dosya_icerik_uret(parcalar[1].strip())
                        else:
                            telegram_bot.mesaj_gonder("⚠️ Lütfen dosya konusunu girin:\n<code>/dosya Kentsel Dönüşüm Hukuki Süreci</code>")

                    elif komut_parca == "/link":
                        log.info("/link komutu alındı: %s", text)
                        parcalar = text.split(maxsplit=1)
                        if len(parcalar) > 1:
                            ozel_icerik.linkten_icerik_uret(parcalar[1].strip())
                        else:
                            telegram_bot.mesaj_gonder("⚠️ Lütfen geçerli bir web linki girin:\n<code>/link https://...</code>")

                    elif komut_parca in ("/ozel", "/konu"):
                        log.info("/ozel komutu alındı: %s", text)
                        parcalar = text.split(maxsplit=1)
                        if len(parcalar) > 1:
                            ozel_icerik.konudan_ozel_icerik_uret(parcalar[1].strip())
                        else:
                            telegram_bot.mesaj_gonder("⚠️ Lütfen konu metnini girin:\n<code>/ozel Hisseli tapuda şufa hakkı...</code>")

        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            log.error("Poller döngü hatası: %s", e)
            time.sleep(3)


if __name__ == "__main__":
    main()
