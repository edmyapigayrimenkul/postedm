"""Yönetim işlemleri: planlı yayın kaydı, erteleme, yayından kaldırma, elle paylaşım paketi, "paylaştım" işareti."""

from __future__ import annotations

import html as html_lib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ... import db, generate_text, linkedin, telegram_bot, threads
from ..baglam import Istek
from ..icerik import haber_taze, ilan_taze
from ..kayit import site_taslagi_aktar

log = logging.getLogger(__name__)


def tur_adi(tur: str) -> str:
    return "Reels Videosu" if tur == "reels" else ("İlan" if tur == "ilan" else "İçerik")


def plan_kaydi(istek: Istek) -> None:
    """PLANLI YAYIN KAYDI (2026-09-26). Plan Worker'ın KV'sinde, yayını 10 dakikalık Cloudflare cron'u tetikliyor. Burada yalnızca
    zamanı içeriğe yazılır: hatırlatıcı plan bekleyen içeriğe "onay bekliyor" kartı atıp plan mesajını silmesin."""
    if istek.tur not in ("haber", "reels"):  # ilan kimlikleri başka tabloda; haberler'e yazılmaz
        return
    an = None
    if istek.hedef == "planla":
        try:
            an = datetime.fromisoformat(str(istek.plan_an).replace("Z", "+00:00")).isoformat()
        except ValueError:
            log.warning("Geçersiz plan zamanı: %s", istek.plan_an)
            return
    db.haber_guncelle(int(istek.ref_id), planlanan_yayin=an)
    db.wal_bosalt()


def ertele(istek: Istek) -> None:
    """Onay isteğini 1 saat erteler (otomatik hatırlatma yok; 1 günlük havuz kuralı yine geçerlidir)."""
    db.onay_istegi_ertele(istek.tur, str(istek.ref_id), dakika=60)
    ad = tur_adi(istek.tur)
    log.info("%s #%s için onay süresi 1 saat ertelendi.", ad, istek.ref_id)
    telegram_bot.mesaj_gonder(f"⏰ <b>{ad} #{istek.ref_id} için yayın 1 saat ertelendi.</b>")


def kaldir(istek: Istek) -> None:
    telegram_bot.yayindan_kaldir(istek.tur, istek.ref_id, mesaj_id=istek.mesaj_id)


def manuel_paket(istek: Istek) -> None:
    tur, ref_id = istek.tur, istek.ref_id
    if tur in ("haber", "reels"):
        haber = haber_taze(ref_id)
        if not haber:
            log.error("Manuel paket için haber bulunamadı: #%s", ref_id)
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
        ilan = ilan_taze(ref_id)
        if not ilan:
            log.error("Manuel paket için ilan bulunamadı: #%s", ref_id)
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


def tamamla(istek: Istek) -> None:
    """Tamamlandı / manuel paylaşıldı olarak işaretle."""
    tur, ref_id = istek.tur, istek.ref_id
    if tur in ("haber", "reels"):
        haber = haber_taze(ref_id)
        simdi = datetime.now(timezone.utc).isoformat()
        db.haber_guncelle(int(ref_id), durum="yayinlandi", yayin_zamani=simdi)
        db.onay_istegi_sonuclandir(tur, str(ref_id), "yayinlandi")
        # Reels de haber tablosunda tutuluyor; ancak siteye yalnız editoryal
        # haber metni gider. Video paylaşımı web bülteni oluşturmaz.
        site_notu = site_taslagi_aktar(haber) if tur == "haber" else ""
        ad = "Reels Videosu" if tur == "reels" else "İçerik"
        log.info("%s #%s kullanıcı tarafından manuel paylaşıldı ve tamamlandı olarak işaretlendi.", ad, ref_id)
        site_notu_ek = f"\n{site_notu}" if site_notu else ""
        telegram_bot.mesaj_gonder(f"✅ <b>{ad} #{ref_id} paylaşıldı ve tamamlandı olarak arşivlendi. Tebrikler! 🎉</b>{site_notu_ek}")
    elif tur == "ilan":
        ilan_taze(ref_id)
        db.ilan_paylasildi_isaretle(ref_id)
        db.onay_istegi_sonuclandir(tur, str(ref_id), "yayinlandi")
        log.info("İlan #%s kullanıcı tarafından manuel paylaşıldı ve tamamlandı olarak işaretlendi.", ref_id)
        telegram_bot.mesaj_gonder(f"✅ <b>İlan #{ref_id} paylaşıldı ve tamamlandı olarak arşivlendi.</b>")


def metin_onizle(istek: Istek) -> None:
    """Telegram'da yöneticinin platform kanca ve açıklamalarını yayından önce tek tıkla incelemesini sağlar."""
    tur, ref_id = istek.tur, istek.ref_id
    if tur not in ("haber", "reels"):
        return
    haber = haber_taze(ref_id)
    if not haber:
        log.error("Metin önizleme için haber bulunamadı: #%s", ref_id)
        return

    detay = {}
    if haber.get("detay_metni"):
        try:
            detay = json.loads(haber["detay_metni"])
        except Exception:
            detay = {}

    manset = haber.get("manset") or haber.get("orijinal_baslik") or ""

    # 1. LinkedIn B2B ve Mevzuat Metni
    li_metin = linkedin.linkedin_metni_hazirla(detay or haber, manset=manset)

    # 2. Threads Kanca & Zincir Metni
    th_metin = haber.get("threads_metin") or manset

    # 3. Instagram Feed Kancası ve Açıklama
    raw_caption = haber.get("ig_caption") or manset
    ig_caption = generate_text.caption_zenginlestir(
        raw_caption,
        kategori_kodu=haber.get("kategori"),
        platform="instagram",
        manset=manset,
    )

    temiz_li = html_lib.escape(li_metin.strip())
    temiz_th = html_lib.escape(th_metin.strip())
    temiz_ig = html_lib.escape(ig_caption.strip())

    mesaj = (
        f"📝 <b>PLATFORM METİNLERİ VE KANCA ÖNİZLEMESİ (#{ref_id})</b>\n\n"
        f"💼 <b>LinkedIn (B2B Analiz & Mevzuat):</b>\n<pre><code>{temiz_li}</code></pre>\n\n"
        f"🧵 <b>Threads (Kanca & Mikro Akış):</b>\n<pre><code>{temiz_th}</code></pre>\n\n"
        f"📸 <b>Instagram (Feed Kancası & Etiketler):</b>\n<pre><code>{temiz_ig}</code></pre>"
    )
    butonlar = {
        "inline_keyboard": [
            [{"text": "← Onay Menüsüne Dön", "callback_data": f"onay_menu_don:{ref_id}"}],
        ]
    }
    if len(mesaj) <= 3900:
        telegram_bot.mesaj_gonder(mesaj, reply_markup=butonlar)
    else:
        m1 = f"📝 <b>PLATFORM METİNLERİ ÖNİZLEMESİ (#{ref_id})</b>\n\n💼 <b>LinkedIn (B2B Analiz):</b>\n<pre><code>{temiz_li}</code></pre>"
        m2 = (
            f"🧵 <b>Threads (Kanca):</b>\n<pre><code>{temiz_th}</code></pre>\n\n"
            f"📸 <b>Instagram (Açıklama):</b>\n<pre><code>{temiz_ig}</code></pre>"
        )
        telegram_bot.mesaj_gonder(m1)
        telegram_bot.mesaj_gonder(m2, reply_markup=butonlar)

