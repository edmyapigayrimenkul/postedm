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
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config, gizlilik, telegram_bot

log = logging.getLogger(__name__)

# Yerel/oturum içi kopyalar (Actions makinesi iş bitince silinir). KALICI kayıt DB'dedir
# (`db.hata_kayitlari`); dosyalar yalnız aynı iş içindeki sonraki adımlar (yayinla.yml "Hata bildir") içindir.
# Test modunda geçici dizine gider (config.veri_yolu).
HATA_LOG_YOLU = config.veri_yolu("hata_kayitlari.jsonl")
SON_HATA_YOLU = config.veri_yolu("son_hata.txt")
RAPOR_ISARET_YOLU = config.veri_yolu("son_rapor_gonderildi.txt")

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
        "ne_oldu": "Meta (Instagram / Threads) görselleri indirirken geçici zaman aşımına uğradı.",
        "neden": "Meta sunucuları görsel barındırma adresinden (ImgBB) görseli çekerken anlık gecikme yaşadı.",
        "ne_yapilir": "Görseller sağlamdır. Sonuç kartındaki '🔄 Tekrar Gönder' butonuyla yalnızca geciken kanalı yeniden deneyebilirsiniz.",
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
        "desen": r"Content-Range|byte\(s\) in the request body|There should have been.*byte",
        "ne_oldu": "YouTube Shorts video yüklemesinde dosya boyutu (bayt) uyuşmazlığı oluştu.",
        "neden": "Video aktarılırken Google sunucusuna bildirilen dosya boyutu ile giden bayt sayısı eşleşmedi.",
        "ne_yapilir": "'🔄 ▶️ Shorts'a Tekrar Yükle' butonuna basarak videoyu anında tekrar yükleyebilirsiniz.",
        "eylem": "yeniden_yayinla",
    },
    {
        "desen": r"error_subcode[\"']?\s*:\s*459|checkpoint_url|log in to www\.facebook\.com and follow the instructions",
        "ne_oldu": "Meta (Facebook/Instagram) hesabı güvenlik kontrolüne (checkpoint) takıldı.",
        "neden": "Meta güvenlik politikası gereği tarayıcıdan www.facebook.com adresine giriş yaparak hesabınızı doğrulamanızı veya ekrandaki güvenlik uyarısını onaylamanızı istiyor.",
        "ne_yapilir": "Tarayıcıdan www.facebook.com adresine giriş yapın ve çıkan güvenlik/doğrulama adımını onaylayın. Ardından paylaşıma devam edebilirsiniz.",
        "eylem": "yeniden_yayinla",
    },
    {
        "desen": r"Error validating access token|Session has expired|OAuthException",
        "ne_oldu": "Sosyal medya erişim yetkisinin (Token) süresi dolmuş veya geçersiz.",
        "neden": "Meta veya Threads güvenlik politikaları gereği jeton yenilemesi gerekiyor.",
        "ne_yapilir": "GitHub Secrets veya .env üzerinden ilgili platform jetonunu yenileyin.",
        "eylem": "durum",
    },
    {
        "desen": r"threads.*(hata|timeout|gecikme|fail|✗)|graph\.threads\.net|THREADS_ACCESS_TOKEN",
        "ne_oldu": "Threads paylaşımı geçici olarak başarısız oldu.",
        "neden": "Threads API jetonunun süresi dolmuş veya Meta görseli çekerken geçici ağ zaman aşımı oluşmuş.",
        "ne_yapilir": "Diğer kanallar (YouTube Shorts, Instagram, Facebook) etkilenmez. Sonuç mesajındaki '🔄 🧵 Threads'i Tekrar Gönder' butonuna basabilirsiniz.",
        "eylem": "yeniden_yayinla",
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
        "desen": r"spam_risk_too_many_pending_share",
        "ne_oldu": "TikTok gelen kutunuzda 5 adet bekleyen (paylaşılmamış) taslak biriktiği için güvenlik kotasına takıldı.",
        "neden": "TikTok API, bir hesaba 24 saat içinde en fazla 5 adet bekleyen gelen kutusu taslağı gönderilmesine izin verir. Önceki taslaklar onaylanmadığı veya silinmediği için sınır doldu.",
        "ne_yapilir": "Telefonunuzdan TikTok uygulamasını açın: Gelen Kutusu (Inbox) / Taslaklar bölümüne girip bekleyen taslakları silin veya onaylayıp paylaşın. Kutuyu temizledikten sonra '🔄 Tekrar Yayınla' ile işlemi tamamlayabilirsiniz.",
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
        "desen": r"youtube.*(invalid_grant|token.*(expired|revoked))|invalid_grant.*(google|oauth2)",
        "ne_oldu": "YouTube erişim yetkisi (Refresh Token) geçersiz veya süresi dolmuş.",
        "neden": "Google Cloud OAuth consent screen 'Testing' modundaysa refresh_token tam 7 gün sonra iptal edilir (7 gün tuzağı).",
        "ne_yapilir": "Google Cloud Console > OAuth Consent Screen ekranında 'Publish App' ile uygulamayı 'In production' moduna alın ve jetonu yenileyin.",
        "eylem": "durum",
    },
    {
        "desen": r"youtube.*(quota|uploadLimitExceeded|quotaExceeded)|uploadLimitExceeded",
        "ne_oldu": "YouTube API günlük yükleme veya işlem kotası aşıldı.",
        "neden": "YouTube Data API v3 günlük 10.000 birim kota verir; video yükleme işlemi 1.600 birim harcar (günde azami ~6 video).",
        "ne_yapilir": "Kota her gece Pasifik Saatiyle (PST) sıfırlanır. Reels ve TikTok paylaşımları etkilenmez.",
        "eylem": "durum",
    },
]


def _sadelestir(metin: str) -> str:
    """Fazla boşlukları ve satır sonlarını temizler."""
    return re.sub(r"\s+", " ", (metin or "")).strip()


def hata_kaydet(nerede: str, baslik: str, ham_hata: str, teshis: Dict[str, Any]) -> None:
    """Hatayı KALICI olarak DB'ye (`hata_kayitlari`), aynı iş içindeki adımlar için de yerel dosyalara yazar.

    Gizli değerler (access_token, Bearer, bot adresi, API anahtarı) kayıttan önce maskelenir: DB git'e gidiyor."""
    ham_hata = gizlilik.maskele(ham_hata)
    try:
        from . import db
        db.hata_kaydi_ekle(nerede, baslik, teshis.get("ne_oldu", ""), teshis.get("neden", ""),
                           teshis.get("eylem", ""), bool(teshis.get("tanindi", False)), ham_hata)
    except Exception as e:  # noqa: BLE001 — hata kaydı hata bildirimini düşürmesin
        log.warning("Hata DB'ye yazılamadı: %s", e)
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


def son_hatalari_ozetle(saat: int = 24) -> List[Dict[str, Any]]:
    """Son belirtilen saat içindeki hata kayıtlarını döner (kaynak: DB).

    Önceki sürüm yalnız yerel jsonl'yi okuyordu ve kayıt anahtarını `tarih_iso` diye arıyordu; yazıcı `tarih`
    yazdığı için dosya var olsa bile hiçbir kayıt eşleşmiyordu."""
    try:
        from . import db
        return db.son_hata_kayitlari(saat=saat)
    except Exception as e:  # noqa: BLE001
        log.warning("Hata kayıtları DB'den okunamadı: %s", e)
        return []


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


def _butonlar(
    eylem: str,
    nerede: str = "",
    mesaj_id: Optional[str] = None,
    tur: str = "",
    ref_id: str = "",
    hedef: str = "",
    run_url: str = "",
) -> Optional[Dict[str, Any]]:
    """Hataya uygun tek tıkla kurtarma inline butonları üretir."""
    inline_keyboard: List[List[Dict[str, str]]] = []
    m_id = str(mesaj_id or "")

    # 1. Tekrar Yayınla / Yeniden Hazırla Butonu
    if tur and ref_id:
        h_param = hedef or "hepsi"
        yayinla_cb = f"onayla:{tur}:{h_param}:{ref_id}"
        iptal_cb = f"reddet:{tur}:{ref_id}"
    elif m_id:
        yayinla_cb = f"onayla:{m_id}"
        iptal_cb = "iptal"
    else:
        yayinla_cb = "yayinla"
        iptal_cb = "iptal"

    satir_1 = [{"text": "🔄 Tekrar Yayınla", "callback_data": yayinla_cb}]
    if eylem == "tur_tekrar":
        satir_1 = [{"text": "🔄 Yeniden Hazırla", "callback_data": f"yenile:{ref_id}" if ref_id else "ilan_menu_yenile"}]
    satir_1.append({"text": "❌ Bu Turu Atla", "callback_data": iptal_cb})
    inline_keyboard.append(satir_1)

    # 2. Hata İnceleme ve Durum Butonları
    inline_keyboard.append([
        {"text": "🔍 Ham Hata Göster", "callback_data": "hata_ayrinti"},
        {"text": "📊 Sistem Durumu", "callback_data": "durum"},
    ])

    # 3. GitHub Log Linki
    if run_url and run_url.startswith("http"):
        inline_keyboard.append([{"text": "🌐 GitHub Logunu Aç", "url": run_url}])

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
    tur: str = "",
    ref_id: str = "",
    hedef: str = "",
    run_url: str = "",
) -> bool:
    """Hatayı analiz eder, kalıcı loga yazar ve Telegram grubuna interaktif kart gönderir."""
    # Hata metni boşsa son_hata.txt dosyasından oku
    if not istisna and not ek_bilgi and SON_HATA_YOLU.exists():
        try:
            with open(SON_HATA_YOLU, "r", encoding="utf-8") as f:
                kayitli = f.read().strip()
                if kayitli:
                    ek_bilgi = kayitli
        except Exception:
            pass

    # Referans ID boşsa veritabanındaki son içerikten otomatik tamamla
    if not ref_id:
        try:
            from . import db
            bekleyenler = db.onay_bekleyen_haberleri_getir(limit=1)
            if bekleyenler:
                ref_id = str(bekleyenler[0].get("id", ""))
        except Exception:
            pass

    hata_str = str(istisna) if istisna else ek_bilgi
    tb_str = traceback.format_exc() if istisna else ""
    tum_hata = f"{hata_str}\n{tb_str}" if tb_str and "NoneType: None" not in tb_str else hata_str

    teshis = hatayi_analiz_et(tum_hata)
    hata_kaydet(islem_adi, islem_adi, tum_hata, teshis)
    son_ham_hata_kaydet(tum_hata)

    mesaj = mesaji_kur(islem_adi, teshis, islem_adi)
    reply_markup = _butonlar(
        teshis["eylem"],
        islem_adi,
        mesaj_id=mesaj_id,
        tur=tur,
        ref_id=ref_id,
        hedef=hedef,
        run_url=run_url,
    )

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
            f.write(gizlilik.maskele(_sadelestir(metin))[:3000])
    except Exception as e:
        log.warning("Ham hata kaydedilemedi: %s", e)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="EDM Telegram Akıllı Hata Bildirimi")
    parser.add_argument("--islem", default="Yayınla", help="İşlem veya workflow adı")
    parser.add_argument("--hata", default="", help="Hata metni veya istisna özeti")
    parser.add_argument("--tur", default="", help="İçerik türü (haber/reels/ilan)")
    parser.add_argument("--id", default="", help="İçerik referans ID")
    parser.add_argument("--hedef", default="hepsi", help="Hedef platformlar")
    parser.add_argument("--mesaj-id", default="", help="Telegram mesaj ID")
    parser.add_argument("--run-url", default="", help="GitHub Actions run URL")
    args = parser.parse_args()

    hata_metni = args.hata
    if not hata_metni and SON_HATA_YOLU.exists():
        try:
            with open(SON_HATA_YOLU, "r", encoding="utf-8") as f:
                icerik = f.read().strip()
                if icerik:
                    hata_metni = icerik
        except Exception:
            pass

    ref_id = args.id
    if not ref_id:
        try:
            from . import db
            bekleyenler = db.onay_bekleyen_haberleri_getir(limit=1)
            if bekleyenler:
                ref_id = str(bekleyenler[0].get("id", ""))
        except Exception:
            pass

    # Eğer bu içerik için zaten Telegram'a özet sonuç raporu ve telafi butonları ("🔄 Threads'i Tekrar Gönder" vb.)
    # iletildiyse, gruba ikinci bir mükerrer teknik hata kartı atıp grubu kirletme ve kullanıcıyı yanıltma.
    rapor_sentinel = RAPOR_ISARET_YOLU
    if args.islem == "Yayınla" and rapor_sentinel.exists():
        try:
            kayitli_ref = rapor_sentinel.read_text(encoding="utf-8").strip()
            if not ref_id or kayitli_ref == str(ref_id):
                log.info("Özet sonuç raporu ve telafi butonları zaten iletildi; mükerrer hata kartı atlanıyor.")
                sys.exit(0)
        except Exception as se:
            log.debug("Sentinel kontrolü atlandı: %s", se)

    telegrama_hata_bildir(
        islem_adi=args.islem,
        ek_bilgi=hata_metni or "İşlem sırasında beklenmeyen bir hata meydana geldi.",
        tur=args.tur or "haber",
        ref_id=ref_id,
        hedef=args.hedef,
        mesaj_id=args.mesaj_id,
        run_url=args.run_url,
    )
