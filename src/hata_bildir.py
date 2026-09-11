"""
hata_bildir.py — EDM Sosyal Medya Botu Akıllı Hata Bildirim ve Raporlama Modülü
Instabot / Daily Brief mimarisinden uyarlanmıştır.
İşlemler sırasında hata oluşursa, çirkin traceback yerine Telegram grubuna
"Ne Oldu / Neden / Ne Yapılır" kartı gönderir ve loglara kaydeder.
"""

from __future__ import annotations

import logging
import re
import sys
import traceback
from typing import Any, Dict, Optional

from . import telegram_bot

log = logging.getLogger(__name__)

# Yaygın Hata Kataloğu (RegEx Desenleri & Türkçe Teşhisler)
HATA_KATALOGU = [
    {
        "desen": r"database is locked|database table is locked",
        "ne_oldu": "Veritabanı meşgul olduğu için işlem tamamlanamadı.",
        "neden": "Aynı anda iki farklı işlem SQLite veritabanına yazmaya çalıştı.",
        "ne_yapilir": "1-2 saniye bekleyip butona tekrar basabilirsiniz.",
    },
    {
        "desen": r"Error validating access token|Session has expired|OAuthException",
        "ne_oldu": "Sosyal medya erişim yetkisinin (Token) süresi dolmuş.",
        "neden": "Meta veya Threads güvenlik politikaları gereği jeton yenilemesi gerekiyor.",
        "ne_yapilir": "Terminalden 'python scripts/token_kontrol.py --threads-yenile' çalıştırın.",
    },
    {
        "desen": r"IMGBB|imgbb\.com|catbox\.moe|Görseller public URL'e yüklenemedi",
        "ne_oldu": "Görseller sunucuya (CDN) yüklenemedi.",
        "neden": "Görsel barındırıcıda anlık erişim veya kota sorunu yaşandı.",
        "ne_yapilir": "Birkaç dakika sonra tekrar deneyin, Catbox yedeği otomatik devreye girecektir.",
    },
    {
        "desen": r"GEMINI_API_KEY|generativelanguage\.googleapis\.com|ResourceExhausted|429",
        "ne_oldu": "Gemini yapay zeka servisine erişilemedi.",
        "neden": "API kotası aşılmış veya anlık Google sunucu yoğunluğu oluşmuş olabilir.",
        "ne_yapilir": "1-2 dakika sonra işlemi tekrarlayın.",
    },
    {
        "desen": r"WEBPAGE_CURL_FAILED|failed to get HTTP URL content",
        "ne_oldu": "Telegram görseli indirmeye çalışırken zaman aşımına uğradı.",
        "neden": "Görsel CDN sunucusu Telegram bot sunucularına geç yanıt verdi.",
        "ne_yapilir": "Butona tekrar tıklayarak gönderimi yeniden deneyin.",
    },
]


def hatayi_analiz_et(hata_metni: str) -> Dict[str, str]:
    """Hata metnini katalogdaki desenlerle eşleştirerek teşhis koyar."""
    for k in HATA_KATALOGU:
        if re.search(k["desen"], hata_metni, re.IGNORECASE):
            return {
                "ne_oldu": k["ne_oldu"],
                "neden": k["neden"],
                "ne_yapilir": k["ne_yapilir"],
            }

    return {
        "ne_oldu": "Beklenmeyen bir teknik hata oluştu.",
        "neden": "Sistem çalıştırma esnasında öngörülmeyen bir istisna ile karşılaştı.",
        "ne_yapilir": "Hata detayını geliştiriciye bildirebilir veya işlemi tekrar deneyebilirsiniz.",
    }


def telegrama_hata_bildir(
    islem_adi: str,
    istisna: Optional[Exception] = None,
    ek_bilgi: str = "",
) -> bool:
    """Hatayı analiz eder, Telegram grubuna anlaşılır bir özet kartı gönderir."""
    hata_str = str(istisna) if istisna else ek_bilgi
    tb_str = traceback.format_exc() if istisna else ""

    tehis = hatayi_analiz_et(f"{hata_str}\n{tb_str}")

    kisa_hata = (hata_str[:150] + "...") if len(hata_str) > 150 else hata_str

    mesaj = (
        f"⚠️ <b>BİR SORUN OLUŞTU ({islem_adi})</b>\n\n"
        f"🔴 <b>Durum:</b> {tehis['ne_oldu']}\n"
        f"💡 <b>Neden:</b> {tehis['neden']}\n"
        f"👉 <b>Ne Yapılır:</b> {tehis['ne_yapilir']}\n\n"
        f"🔍 <i>Teknik Hata:</i> <code>{kisa_hata}</code>"
    )

    try:
        telegram_bot.mesaj_gonder(mesaj)
        return True
    except Exception as e:
        log.error("Telegram'a hata bildirimi iletilemedi: %s", e)
        return False
