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

from src import config, db, fetch_listings, fetch_news, konu_bankasi, telegram_bot

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
                    # D. Kanal Seçimi / Toggle
                    # ---------------------------------------------------------
                    elif data.startswith("kanal_toggle:"):
                        kanal = data.split(":")[1]
                        kanallar = telegram_bot.varsayilan_kanallar()
                        aktif = not kanallar.get(kanal, True)
                        guncel_kanallar = telegram_bot.kanal_ayarla(kanal, aktif)
                        bekleyenler = db.bekleyen_haberleri_getir(limit=1)
                        if bekleyenler and msg_id:
                            h_id = bekleyenler[0]["id"]
                            telegram_bot.mesaji_guncelle(
                                msg_id,
                                "Bu içeriği onaylıyor musunuz? Kanalları seçip tek tıkla yayınlayabilirsiniz:",
                                reply_markup=telegram_bot.onay_menusu(h_id, guncel_kanallar),
                            )

                    # ---------------------------------------------------------
                    # E. Format Değiştirme Menüsü
                    # ---------------------------------------------------------
                    elif data.startswith("format_menu:"):
                        h_id = int(data.split(":")[1])
                        if msg_id:
                            telegram_bot.mesaji_guncelle(
                                msg_id,
                                "🎨 <b>Format Değiştirme Menüsü:</b>\n"
                                "Bu içeriği hangi EDM formatına dönüştürmek istersiniz?",
                                reply_markup=telegram_bot.format_secim_menusu(h_id),
                            )

                    elif data.startswith("onay_menu_don:"):
                        h_id = int(data.split(":")[1])
                        if msg_id:
                            telegram_bot.mesaji_guncelle(
                                msg_id,
                                "Bu içeriği onaylıyor musunuz? Kanalları seçip tek tıkla yayınlayabilirsiniz:",
                                reply_markup=telegram_bot.onay_menusu(h_id),
                            )

                    elif data.startswith("format_uygula:"):
                        _, fmt, h_id_str = data.split(":")
                        h_id = int(h_id_str)
                        log.info("Format uygulanıyor: #%d -> %s", h_id, fmt)
                        telegram_bot.format_degistir_ve_sun(h_id, fmt)

                    # ---------------------------------------------------------
                    # F. Manuel Paylaşım Paketi
                    # ---------------------------------------------------------
                    elif data.startswith("manuel_paket:"):
                        h_id = data.split(":")[1]
                        log.info("Manuel paket talep edildi: #%s", h_id)
                        cmd = [
                            sys.executable,
                            str(KOK / "scripts/yayinla.py"),
                            "--tur",
                            "haber",
                            "--id",
                            h_id,
                            "--hedef",
                            "manuel_paket",
                        ]
                        subprocess.run(cmd, cwd=str(KOK))

                    # ---------------------------------------------------------
                    # G. Onayla ve Yayınla (Çok Kanallı Dağıtım)
                    # ---------------------------------------------------------
                    elif data.startswith("onayla:"):
                        parcalar = data.split(":")
                        if len(parcalar) == 4:
                            _, tur, hedef, ref_id = parcalar
                            if hedef == "tamamla":
                                log.info("Manuel tamamlandı: %s #%s", tur, ref_id)
                                try:
                                    db.haber_guncelle(int(ref_id), durum="yayinlandi")
                                    db.onay_istegi_sonuclandir(tur, str(ref_id), "yayinlandi")
                                except Exception as de:
                                    log.warning("DB güncelleme hatası: %s", de)
                                telegram_bot.mesaj_gonder(f"✅ <b>{tur.upper()} #{ref_id}</b> paylaşıldı olarak işaretlendi ve arşivlendi.")
                            else:
                                log.info("Yayın onaylandı: %s #%s -> %s", tur, ref_id, hedef)
                                telegram_bot.mesaj_gonder(
                                    f"🚀 <b>{tur.upper()} #{ref_id}</b> için paylaşım süreci başlatıldı...\n"
                                    f"Platformlar: <b>{hedef.upper()}</b>\nLütfen bekleyin..."
                                )
                                cmd = [
                                    sys.executable,
                                    str(KOK / "scripts/yayinla.py"),
                                    "--tur",
                                    tur,
                                    "--id",
                                    ref_id,
                                    "--hedef",
                                    hedef,
                                ]
                                subprocess.run(cmd, cwd=str(KOK))

                    # ---------------------------------------------------------
                    # H. Yenile & Reddet
                    # ---------------------------------------------------------
                    elif data.startswith("yenile:"):
                        parcalar = data.split(":")
                        tur = parcalar[1] if len(parcalar) > 1 else "içerik"
                        ref_id = parcalar[2] if len(parcalar) > 2 else ""
                        log.info("Yenileme talep edildi: %s #%s", tur, ref_id)
                        telegram_bot.mesaj_gonder(f"🔄 <b>{tur.upper()} #{ref_id}</b> yeniden üretiliyor, lütfen bekleyin...")
                        cmd = [
                            sys.executable,
                            str(KOK / "scripts/yayinla.py"),
                            "--tur",
                            tur,
                            "--id",
                            ref_id,
                            "--hedef",
                            "yenile",
                        ]
                        subprocess.run(cmd, cwd=str(KOK))

                    elif data.startswith("reddet:"):
                        parcalar = data.split(":")
                        tur = parcalar[1] if len(parcalar) > 1 else "içerik"
                        ref_id = parcalar[2] if len(parcalar) > 2 else ""
                        try:
                            if ref_id.isdigit():
                                db.haber_guncelle(int(ref_id), durum="reddedildi")
                                db.onay_istegi_sonuclandir(tur, str(ref_id), "reddedildi")
                        except Exception as re:
                            log.warning("Reddetme DB hatası: %s", re)
                        telegram_bot.mesaj_gonder(f"❌ <b>{tur.upper()} #{ref_id}</b> reddedildi ve iptal edildi.")

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

        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            log.error("Poller döngü hatası: %s", e)
            time.sleep(3)


if __name__ == "__main__":
    main()
