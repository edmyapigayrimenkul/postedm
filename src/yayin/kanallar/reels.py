"""Instagram Reels: API ile yüklenemez; hazır video Telegram'a iletilir, kullanıcı uygulamadan (trend müzikle) paylaşır."""

from __future__ import annotations

import html as html_lib
import logging

from ... import telegram_bot
from ..baglam import YayinBaglami
from ..ilerleme import Ilerleme
from ..sonuc import BILGI, HATA, KanalSonucu

log = logging.getLogger(__name__)

KANAL = "reels"


def yayinla(b: YayinBaglami, ilerleme: Ilerleme) -> KanalSonucu:
    ilerleme.bildir(KANAL, "⏳ Yükleniyor...")
    s = KanalSonucu(KANAL, etiket="❌ Hata", ham={"video_telegrama_gitti": False})
    video_yolu = b.video_yolu_var()
    if video_yolu and video_yolu.exists():
        try:
            telegram_bot.video_gonder(
                video_yolu,
                aciklama=f"🎬 <b>EDM Reels Videosu (1080x1920 MP4)</b>\n\n"
                         f"📌 <b>Konu:</b> {html_lib.escape(b.baslik)}\n\n"
                         f"💡 <i>Videoyu cihazınıza kaydedip Instagram uygulamasından trend müzik ekleyerek Reels olarak paylaşabilirsiniz.</i>",
            )
            s.ham["video_telegrama_gitti"] = True
            s.ekle("🎬 <b>Instagram Reels:</b> Video ve açıklama Telegram'a iletildi (Elle Paylaşılacak) 📲", BILGI)
            s.etiket = "📲 Telegram'a İletildi"
        except Exception as re:  # noqa: BLE001
            log.warning("Instagram Reels teslim hatası: %s", re)
            s.ekle(f"🎬 <b>Instagram Reels:</b> Hata ({re}) ✗", HATA)
    else:
        s.ekle("🎬 <b>Instagram Reels:</b> Video üretilemedi ✗", HATA)
    ilerleme.bildir(KANAL, s.etiket, increment=True)
    return s
