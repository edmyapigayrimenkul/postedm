"""
yayin/rapor.py — Telegram'a yayın sonucu: kanal kanal özet, canlı bağlantılar, hata veren kanallar için tek tıkla telafi düğmeleri,
kopyalanabilir açıklama ve hazır dikey videonun teslimi.
"""

from __future__ import annotations

import html as html_lib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from .. import facebook, hata_bildir, telegram_bot, threads, twitter
from .baglam import YayinBaglami
from .hedef import linkedin_istendi, twitter_istendi
from .sonuc import HATA, DagitimSonucu

log = logging.getLogger(__name__)

TELEGRAM_AZAMI = 3900


def _sonuc_metni(b: YayinBaglami, sonuc: DagitimSonucu, gecen_sure: float, temiz_caption: str) -> tuple[str, bool]:
    """(mesaj, caption_ayri_gonder). Açıklama kutusu sığıyorsa mesaja eklenir, sığmıyorsa ayrı mesaj olur."""
    caption_kutu = f"\n\n📝 <b>Açıklama Metni (Kopyalamak İçin Dokunun):</b>\n<pre><code>{temiz_caption}</code></pre>"
    hata_var = sonuc.hata_var
    baslik_icon = "⚠️" if hata_var else "🎉"
    baslik_durum = "YAYIN KISMEN TAMAMLANDI" if hata_var else "YAYIN BAŞARIYLA TAMAMLANDI"

    satirlar_sonuc = [
        f"{baslik_icon} <b>{baslik_durum}</b>\n",
        f"📌 <b>İçerik:</b> {html_lib.escape(b.baslik)}",
    ]
    if gecen_sure > 0:
        satirlar_sonuc.append(f"⏱️ <b>Dağıtım Süresi:</b> {gecen_sure:.1f} sn")
    satirlar_sonuc.append("\n📱 <b>Platform Sonuçları:</b>")
    for s in sonuc.satirlar:
        satirlar_sonuc.append(f"• {s.metin}")

    metin = "\n".join(satirlar_sonuc)
    if len(metin) + len(caption_kutu) <= TELEGRAM_AZAMI:
        return metin + caption_kutu, False
    return metin, True


def _canli_baglantilar(sonuc: DagitimSonucu) -> List[List[Dict[str, Any]]]:
    linkler: List[Dict[str, Any]] = []
    if sonuc.ig_id:
        linkler.append({"text": "📸 Instagram'da Gör", "url": f"https://www.instagram.com/p/{sonuc.ig_id}/"})
    if sonuc.threads_id:
        th_url = threads.post_baglantisi(sonuc.threads_id)
        if th_url:
            linkler.append({"text": "🧵 Threads'te Gör", "url": th_url})
    if sonuc.fb_id:
        fb_url = facebook.post_baglantisi(sonuc.fb_id)
        if fb_url:
            linkler.append({"text": "📘 Facebook'ta Gör", "url": fb_url})
    yt = sonuc.yt_res
    if yt.get("durum") and yt.get("url"):
        linkler.append({"text": "▶️ Shorts'ta İzle", "url": yt.get("url")})
    if sonuc.linkedin_id:
        linkler.append({"text": "💼 LinkedIn'de Gör", "url": f"https://www.linkedin.com/feed/update/{sonuc.linkedin_id}/"})
    if sonuc.twitter_id:
        tw_url = twitter.post_baglantisi(sonuc.twitter_id)
        if tw_url:
            linkler.append({"text": "🐦 X'te Gör", "url": tw_url})
    return [linkler[i:i + 2] for i in range(0, len(linkler), 2)]


def _telafi_dugmeleri(b: YayinBaglami, sonuc: DagitimSonucu) -> List[List[Dict[str, Any]]]:
    """Hata veren kanallar için anında tek tıkla telafi butonları."""
    ref = b.ref_id
    d: List[List[Dict[str, Any]]] = []
    if b.paylas_ig and not sonuc.ig_id:
        d.append([{"text": "🔄 📸 Instagram'ı Tekrar Dene", "callback_data": f"retry_kanal:ig:{ref}"}])
    if b.hedef_mi("threads", "th") and not sonuc.threads_id:
        d.append([{"text": "🔄 🧵 Threads'i Tekrar Gönder", "callback_data": f"retry_kanal:threads:{ref}"}])
    if b.hedef_mi("fb", "facebook") and not sonuc.fb_id:
        d.append([{"text": "🔄 📘 Facebook'a Tekrar Gönder", "callback_data": f"retry_kanal:facebook:{ref}"}])
    if b.hedef_mi("yt", "youtube", "shorts") and not sonuc.yt_res.get("durum"):
        d.append([{"text": "🔄 ▶️ Shorts'a Tekrar Yükle", "callback_data": f"retry_kanal:youtube:{ref}"}])
    if b.hedef_mi("tt", "tiktok") and not sonuc.tt_res.get("durum"):
        d.append([{"text": "🔄 🎵 TikTok'a Tekrar Yükle", "callback_data": f"retry_kanal:tiktok:{ref}"}])
    if b.paylas_reels and not sonuc.video_telegrama_gitti:
        d.append([{"text": "🔄 🎬 Reels'i Tekrar Gönder", "callback_data": f"retry_kanal:reels:{ref}"}])
    if linkedin_istendi(b.hedefler) and not sonuc.linkedin_id:
        d.append([{"text": "🔄 💼 LinkedIn'i Tekrar Dene", "callback_data": f"retry_kanal:linkedin:{ref}"}])
    if twitter_istendi(b.hedefler) and not sonuc.twitter_id:
        d.append([{"text": "🔄 🐦 X'i Tekrar Dene", "callback_data": f"retry_kanal:twitter:{ref}"}])

    if len(d) > 1:
        d.insert(0, [{"text": "🔄 Başarısız Tüm Kanalları Tekrar Dene", "callback_data": f"retry_kanal:hepsi:{ref}"}])
    return d


def gonder(b: YayinBaglami, sonuc: DagitimSonucu, gecen_sure: float) -> None:
    """Sonuç mesajı → eski kartların temizliği → kopyalanabilir caption → hazır dikey video → kopyalanabilir açıklama."""
    ref_id = b.ref_id
    mesaj_id = b.istek.mesaj_id
    caption = b.caption
    temiz_caption = html_lib.escape(caption.strip())

    sonuc_metni, _caption_ayri = _sonuc_metni(b, sonuc, gecen_sure, temiz_caption)

    kontrol_dugmesi = [[{"text": "🔍 Yayın durumunu kontrol et", "callback_data": f"yayin_kontrol:{ref_id}"}]]
    silme_dugmesi = [[{"text": "🗑️ Bu Yayını Kaldır", "callback_data": f"kaldir:{b.tur}:{ref_id}"}]]
    sonuc_tuslari = _canli_baglantilar(sonuc) + _telafi_dugmeleri(b, sonuc) + kontrol_dugmesi + silme_dugmesi
    reply_markup = {"inline_keyboard": sonuc_tuslari} if sonuc_tuslari else None

    try:
        # Instabot standardı: mesaj_id varsa onay kartı güncellenir; mükerrer 2. kart atılmaz.
        # Sadece mesaj_id yoksa (cron/otomatik yayın) yeni mesaj olarak bildirilir.
        telegram_bot.sonucu_yaz(
            mesaj_id,
            sonuc_metni,
            bildir=not bool(mesaj_id),
            reply_markup=reply_markup,
        )
        # Eğer bu içerik için hatırlatma atılmışsa ve birden fazla onay/hatırlatma mesajı varsa:
        # Sonucu yazdığımız mesaj hariç diğer eski mesajları temizle (chat kaosunu sıfırla)
        telegram_bot.icerik_onceki_mesajlarini_temizle(b.tur, ref_id, haric_mesaj_id=mesaj_id)
        try:
            hata_bildir.RAPOR_ISARET_YOLU.write_text(str(ref_id), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        if temiz_caption:
            telegram_bot.mesaj_gonder(
                f"📝 <b>İçerik #{ref_id} Kopyalanabilir Açıklama Metni (Caption):</b>\n\n"
                f"<pre><code>{temiz_caption}</code></pre>"
            )
    except Exception as bildirim_hatasi:  # noqa: BLE001
        log.warning("Telegram sonuç bildirimi gönderilemedi: %s", bildirim_hatasi)

    # 7. Hazırlanan 9:16 Dikey Videoyu Telegram Grubuna İlet (Her yayında hazır video teslim edilir)
    gonderilecek_video = b.sesli_video_yolu if (b.sesli_video_yolu and Path(b.sesli_video_yolu).exists()) else (
        b.v_yolu if (b.v_yolu and Path(b.v_yolu).exists()) else None
    )
    if gonderilecek_video and gonderilecek_video.exists() and not sonuc.video_telegrama_gitti:
        try:
            log.info("Hazırlanan dikey video Telegram grubuna iletiliyor: %s", gonderilecek_video)
            telegram_bot.video_gonder(
                gonderilecek_video,
                aciklama=f"🎬 <b>EDM Reels Videosu (1080x1920 MP4)</b>\n\n"
                         f"📌 <b>Konu:</b> {html_lib.escape(b.baslik)}\n\n"
                         f"💡 <i>Videoyu cihazınıza kaydedip Instagram / TikTok uygulamasından doğrudan paylaşabilirsiniz.</i>",
            )
        except Exception as ve:  # noqa: BLE001
            log.warning("Telegram'a video iletilemedi: %s", ve)

    # 8. Kopyalanabilir açıklama metni (Kullanıcı talebi: yayınla aşamasında video ve kopyalanabilir açıklama)
    if caption:
        try:
            telegram_bot.mesaj_gonder(
                f"📋 <b>Kopyalanabilir Açıklama (Reels / Post):</b>\n\n<code>{html_lib.escape(caption)}</code>"
            )
        except Exception as ce:  # noqa: BLE001
            log.warning("Telegram'a kopyalanabilir açıklama iletilemedi: %s", ce)


def ham_hatayi_kaydet(sonuc: DagitimSonucu) -> None:
    """Hata detayını kaydeder ki "🔍 Ham Hata Göster" ve teşhis modülü tam nedeni bilsin."""
    try:
        hata_satirlari = [s.metin for s in sonuc.satirlar if s.durum == HATA]
        if hata_satirlari:
            hata_bildir.son_ham_hata_kaydet("\n".join(hata_satirlari))
    except Exception:  # noqa: BLE001
        pass
