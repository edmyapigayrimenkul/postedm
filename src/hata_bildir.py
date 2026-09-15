"""
hata_bildir.py — EDM Sosyal Medya Botu Akıllı Hata Bildirim ve Teşhis Modülü
Instabot / Daily Brief mimarisinden eksiksiz uyarlanmıştır.

İşlemler sırasında hata oluşursa, çirkin traceback yerine Telegram grubuna
"Ne Oldu / Neden / Ne Yapılır" kartı gönderir, kurtarma butonları sunar
ve hataları kalıcı olarak data/hata_kayitlari.jsonl ve data/son_hata.txt'ye kaydeder.
"""

from __future__ import annotations

import html as html_lib
import json
import logging
import os
import re
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import telegram_bot

log = logging.getLogger(__name__)

HATA_LOG_YOLU = Path("data") / "hata_kayitlari.jsonl"
SON_HATA_YOLU = Path("data") / "son_hata.txt"

# ----------------------------------------------------------------------
# Kapsamlı Hata Kataloğu (RegEx Desenleri, Teşhisler ve Kurtarma Eylemleri)
# ----------------------------------------------------------------------
HATA_KATALOGU = [
    {
        "desen": r"sqlite3\.Row.*has no attribute|'sqlite3\.Row' object has no attribute",
        "ne_oldu": "Veritabanı satır nesnesinde sözlük fonksiyonu (.get) çağrıldı.",
        "neden": "Veritabanından dönen satır doğrudan sözlük gibi kullanılmak istendi.",
        "ne_yapilir": "'🔄 Haberi Tekrar Hazırla' veya '🔄 Yeniden Dene' butonuyla işlemi tamamlayabilirsiniz.",
        "eylem": "tur_tekrar",
    },
    {
        "desen": r"database is locked|database table is locked",
        "ne_oldu": "Veritabanı meşgul olduğu için işlem tamamlanamadı.",
        "neden": "Aynı anda iki farklı işlem SQLite veritabanına yazmaya çalıştı.",
        "ne_yapilir": "1-2 saniye bekleyip butona tekrar basabilirsiniz.",
        "eylem": "yeniden_yayinla",
    },
    {
        "desen": r"2207052|2207003|Only photo or video can be accepted",
        "ne_oldu": "Instagram görselleri indirirken geçici zaman aşımına uğradı.",
        "neden": "Instagram sunucuları görsel barındırma adresinden görseli çekerken anlık gecikme yaşadı.",
        "ne_yapilir": "Görseller sağlamdır. '🔄 Tekrar Yayınla' butonuyla işlemi doğrudan tekrar deneyebilirsiniz.",
        "eylem": "yeniden_yayinla",
    },
    {
        "desen": r"WEBPAGE_CURL_FAILED|failed to send message #\d+",
        "ne_oldu": "Telegram slayt görsellerini sunucudan indiremedi.",
        "neden": "Telegram API, görsel barındırıcıdaki bağlantı zaman aşımına uğradığı için albümü indiremedi.",
        "ne_yapilir": "Sistem yerel dosyadan doğrudan yükleme yedeğiyle tekrar deneyecektir.",
        "eylem": "tur_tekrar",
    },
    {
        "desen": r"GEMINI_API_KEY|generativelanguage\.googleapis\.com|ResourceExhausted|429.*(quota|Quota)|KOTASI DOLDU",
        "ne_oldu": "Gemini yapay zeka servisine erişilemedi veya günlük kota doldu.",
        "neden": "API kotası aşılmış veya anlık Google sunucu yoğunluğu oluşmuş olabilir.",
        "ne_yapilir": "1-2 dakika sonra işlemi tekrarlayın veya havuzdaki hazır içerikleri kullanın.",
        "eylem": "tur_tekrar",
    },
    {
        "desen": r"Error validating access token|Session has expired|OAuthException",
        "ne_oldu": "Sosyal medya erişim yetkisinin (Token) süresi dolmuş veya geçersiz.",
        "neden": "Meta veya Threads güvenlik politikaları gereği jeton yenilemesi gerekiyor.",
        "ne_yapilir": "GitHub Secrets veya .env üzerinden ilgili platform jetonunu yenileyin.",
        "eylem": "durum",
    },
    {
        "desen": r"graph\.threads\.net|THREADS_ACCESS_TOKEN",
        "ne_oldu": "Threads paylaşımı başarısız oldu.",
        "neden": "Threads API jetonunun süresi dolmuş veya geçici ağ hatası oluşmuş.",
        "ne_yapilir": "Instagram ve Facebook paylaşımları etkilenmez. Threads jetonunu kontrol edin.",
        "eylem": "durum",
    },
    {
        "desen": r"carousel.*(2-10|10 görsel)|children.*(limit|invalid)",
        "ne_oldu": "Carousel paylaşımına izin verilen sınırların dışında görsel verildi.",
        "neden": "Carousel'e 10'dan fazla veya 2'den az görsel eklenmeye çalışıldı.",
        "ne_yapilir": "İçeriği yeniden hazırlamak görsel listesini sıfırlar.",
        "eylem": "tur_tekrar",
    },
    {
        "desen": r"IMGBB|imgbb\.com|catbox\.moe|litterbox|Görseller public URL'e yüklenemedi",
        "ne_oldu": "Görseller sunucuya (CDN) yüklenemedi.",
        "neden": "Görsel barındırıcıda anlık erişim veya kota sorunu yaşandı.",
        "ne_yapilir": "Litterbox/Catbox yedeği devreye girecektir; butona basarak tekrar deneyebilirsiniz.",
        "eylem": "yeniden_yayinla",
    },
    {
        "desen": r"Application request limit|throttl|instagram.*429",
        "ne_oldu": "Instagram API geçici istek sınırı koydu.",
        "neden": "Kısa sürede çok fazla istek yapıldı. Sınır genelde 15-30 dakika içinde kalkar.",
        "ne_yapilir": "15 dakika bekleyip '🔄 Tekrar Yayınla' düğmesine basın.",
        "eylem": "yeniden_yayinla",
    },
    {
        "desen": r"UnboundLocalError|cannot access local variable",
        "ne_oldu": "Python fonksiyonunda değişken kapsamı (scope) hatası oluştu.",
        "neden": "Fonksiyon içerisinde yerel değişken ataması global değişkeni gölgeledi.",
        "ne_yapilir": "İşlemi tekrar başlatabilirsiniz.",
        "eylem": "tur_tekrar",
    },
    {
        "desen": r"NameError|name '.*' is not defined",
        "ne_oldu": "Tanımlanmamış bir değişken çağrıldı (NameError).",
        "neden": "Kod içi değişken ismi uyuşmazlığı oluştu.",
        "ne_yapilir": "İşlemi tekrar başlatabilirsiniz.",
        "eylem": "tur_tekrar",
    },
    {
        "desen": r"AttributeError|KeyError|IndexError|TypeError|ValueError",
        "ne_oldu": "Beklenmeyen bir veri tipi veya alan uyuşmazlığı oluştu.",
        "neden": "Veri yapısı beklenenden farklıydı. Hata kalıcı loga kaydedildi.",
        "ne_yapilir": "'🔄 Tekrar Yayınla' veya '🔄 Yeniden Hazırla' butonuna basabilirsiniz.",
        "eylem": "yeniden_yayinla",
    },
    {
        "desen": r"unaudited_client|unaudited_client_can_only_post_to_private_accounts",
        "ne_oldu": "TikTok Sandbox/Denetim kısıtı nedeniyle video gelen kutusu taslağı olarak yüklendi.",
        "neden": "TikTok Developer uygulamasının App Audit incelemesi henüz onaylanmadığı için doğrudan herkese açık paylaşım kısıtlıdır.",
        "ne_yapilir": "Video hesabınıza 'Gelen Kutusu Taslağı' olarak iletildi. TikTok uygulamasından Gelen Kutusu > Sistem Bildirimleri bölümünden tek tıkla yayınlayabilirsiniz.",
        "eylem": "durum",
    },
    {
        "desen": r"tiktok.*(token|access_token|expired|invalid_grant|invalid_request)",
        "ne_oldu": "TikTok API erişim yetkisinin (Token) süresi dolmuş veya geçersiz.",
        "neden": "TikTok 24 saatlik erişim jetonunun yenilenmesi gerekiyor.",
        "ne_yapilir": "Sistem refresh_token ile otomatik yenilemeyi dener. '🔄 Tekrar Yayınla' butonuyla işlemi tekrarlayabilirsiniz.",
        "eylem": "yeniden_yayinla",
    },
    {
        "desen": r"tiktok.*(init|upload|publish_id|500|502|503)",
        "ne_oldu": "TikTok video sunucularına erişirken geçici ağ gecikmesi yaşandı.",
        "neden": "TikTok yükleme uç noktası video paketini alırken zaman aşımına uğradı.",
        "ne_yapilir": "Video hazırdır. 1 dakika bekleyip '🔄 Tekrar Yayınla' butonuna basabilirsiniz.",
        "eylem": "yeniden_yayinla",
    },
]


def _sadelestir(metin: str) -> str:
    """Fazla boşlukları ve satır sonlarını temizler."""
    return re.sub(r"\s+", " ", (metin or "")).strip()


def hata_kaydet(nerede: str, baslik: str, ham_hata: str, teshis: Dict[str, Any]) -> None:
    """Her hatayı kalıcı olarak data/hata_kayitlari.jsonl ve data/son_hata.txt dosyalarına yazar."""
    try:
        HATA_LOG_YOLU.parent.mkdir(parents=True, exist_ok=True)
        simdi = datetime.now(timezone.utc)
        kayit = {
            "tarih": simdi.isoformat(),
            "tarih_tr": simdi.strftime("%d.%m.%Y %H:%M (UTC)"),
            "nerede": nerede,
            "baslik": baslik,
            "ne_oldu": teshis.get("ne_oldu", ""),
            "neden": teshis.get("neden", ""),
            "ne_yapilir": teshis.get("ne_yapilir", ""),
            "eylem": teshis.get("eylem", ""),
            "tanindi": teshis.get("tanindi", False),
            "ham_hata": ham_hata,
        }
        with open(HATA_LOG_YOLU, "a", encoding="utf-8") as f:
            f.write(json.dumps(kayit, ensure_ascii=False) + "\n")

        with open(SON_HATA_YOLU, "w", encoding="utf-8") as f:
            f.write(f"[{kayit['tarih_tr']}] {nerede} -> {baslik}\n\n{ham_hata[:3000]}")
    except Exception as e:
        log.warning("Hata loguna yazılamadı: %s", e)


def hatayi_analiz_et(hata_metni: str) -> Dict[str, Any]:
    """Hata metnini katalogdaki desenlerle eşleştirerek teşhis koyar."""
    ham = _sadelestir(hata_metni)
    for k in HATA_KATALOGU:
        if re.search(k["desen"], ham, re.IGNORECASE):
            return {
                "ne_oldu": k["ne_oldu"],
                "neden": k["neden"],
                "ne_yapilir": k["ne_yapilir"],
                "eylem": k.get("eylem", "yeniden_yayinla"),
                "tanindi": True,
                "ham": ham,
            }

    return {
        "ne_oldu": "Beklenmeyen bir teknik hata oluştu.",
        "neden": "Sistem çalıştırma esnasında öngörülmeyen bir istisna ile karşılaştı.",
        "ne_yapilir": "Hata detayını inceleyip işlemi aşağıdaki butonlarla tekrar deneyebilirsiniz.",
        "eylem": "yeniden_yayinla",
        "tanindi": False,
        "ham": ham,
    }


def tani(hata: Any) -> Dict[str, Any]:
    """instabot API uyumluluğu için alias."""
    return hatayi_analiz_et(str(hata))


def _butonlar(eylem: str, nerede: str = "", mesaj_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Hataya uygun tek tıkla kurtarma inline butonları üretir."""
    inline_keyboard: List[List[Dict[str, str]]] = []
    m_id = str(mesaj_id or "")

    if eylem == "yeniden_yayinla":
        cb = f"onayla:{m_id}" if m_id else "onayla:haber:hepsi:son"
        inline_keyboard.append([{"text": "🔄 Tekrar Yayınla", "callback_data": cb}])
    elif eylem == "tur_tekrar":
        cb = f"yenile:{m_id}" if m_id else "ilan_menu_yenile"
        inline_keyboard.append([{"text": "🔄 Yeniden Hazırla", "callback_data": cb}])

    inline_keyboard.append([
        {"text": "🔍 Sistem Durumu", "callback_data": "durum"},
        {"text": "📋 İlan Menüsü", "callback_data": "ilan_menu_yenile"},
    ])

    return {"inline_keyboard": inline_keyboard}


def mesaji_kur(baslik: str, teshis: Dict[str, Any], nerede: str = "") -> str:
    """Telegram mesaj metnini güvenli ve zengin HTML kartı olarak oluşturur."""
    b_esc = html_lib.escape(baslik or "")
    n_esc = html_lib.escape(nerede or "")
    ne_oldu = html_lib.escape(teshis.get("ne_oldu", "") or "")
    neden = html_lib.escape(teshis.get("neden", "") or "")
    ne_yapilir = html_lib.escape(teshis.get("ne_yapilir", "") or "")
    ham = html_lib.escape(str(teshis.get("ham", ""))[:350] or "")

    p = [f"⚠️ <b>BİR SORUN OLUŞTU: {b_esc}</b>"]
    if nerede:
        p.append(f"📍 <b>İşlem / Konum:</b> <code>{n_esc}</code>")
    p.append("")
    p.append(f"🔴 <b>NE OLDU?</b>\n{ne_oldu}")
    p.append("")
    p.append(f"💡 <b>NEDEN?</b>\n{neden}")
    p.append("")
    p.append(f"🛠️ <b>ÇÖZÜM / NE YAPILMALI?</b>\n{ne_yapilir}")
    if ham:
        p.append("")
        p.append(f"🔍 <i>Hata Detayı:</i> <code>{ham}</code>")

    return "\n".join(p)


def telegrama_hata_bildir(
    islem_adi: str,
    istisna: Optional[Exception] = None,
    ek_bilgi: str = "",
    mesaj_id: Optional[str] = None,
) -> bool:
    """Hatayı analiz eder, kalıcı loga yazar ve Telegram grubuna interaktif kart gönderir."""
    hata_str = str(istisna) if istisna else ek_bilgi
    tb_str = traceback.format_exc() if istisna else ""
    tum_hata = f"{hata_str}\n{tb_str}" if tb_str and "NoneType: None" not in tb_str else hata_str

    teshis = hatayi_analiz_et(tum_hata)
    hata_kaydet(islem_adi, islem_adi, tum_hata, teshis)

    mesaj = mesaji_kur(islem_adi, teshis, islem_adi)
    reply_markup = _butonlar(teshis["eylem"], islem_adi, mesaj_id=mesaj_id)

    try:
        telegram_bot.mesaj_gonder(mesaj, reply_markup=reply_markup)
        return True
    except Exception as e:
        log.error("Telegram'a hata bildirimi iletilemedi: %s", e)
        return False


def bildir(baslik: str, hata: Any, nerede: str = "", mesaj_id: Optional[str] = None) -> bool:
    """instabot API uyumluluğu için alias fonksiyon."""
    return telegrama_hata_bildir(
        islem_adi=baslik,
        istisna=hata if isinstance(hata, Exception) else None,
        ek_bilgi=str(hata) if not isinstance(hata, Exception) else "",
        mesaj_id=mesaj_id,
    )


def son_ham_hata_kaydet(metin: str) -> None:
    """Ham hatayı anlık olarak son_hata.txt'ye yazar."""
    try:
        SON_HATA_YOLU.parent.mkdir(parents=True, exist_ok=True)
        with open(SON_HATA_YOLU, "w", encoding="utf-8") as f:
            f.write(_sadelestir(metin)[:3000])
    except Exception as e:
        log.warning("Ham hata kaydedilemedi: %s", e)
