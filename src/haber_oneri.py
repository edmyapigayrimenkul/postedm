"""
haber_oneri.py — Taze emlak haberlerini Telegram'a ÖNERİ olarak düşürür.

2026-09-24 kararı: içerik günde bir; emlak haberleri içerikten bağımsız, günde
birkaç kez taranıp gruba öneri olarak gelir. Hangi haberin içeriğe çevrileceğine
insan karar verir ("📝 İçeriğe çevir"), sistem değil.

Neden triyaj burada yok: eski akışta LLM triyajı haberi hem süzüyor hem içeriğe
çeviriyordu ve 14 günde 98 haberin hiçbiri geçmedi; tek "haber" diye çıkanlar
iki deneme kaydıydı (#170, #171). Öneri ucuz ve kural tabanlı; triyaj yalnızca
insan "İçeriğe çevir" dediğinde çalışır ve orada da haberde doğrulanabilir bir
kural/süre/oran yoksa içerik üretmeyi reddeder.

Tarih her öneride yazılır: haberin yaşı, içeriğe çevirip çevirmeme kararının
yarısıdır.

2026-09-26 kararı: öneri Instabot'un öneri taslağıyla aynı biçimde gelir — günde
iki tur, tek mesajda en fazla beş numaralı başlık (bağlantılı, tek cümlelik özet,
kaynak · sütun · tarih · /incele). Numaralarla çoklu seçim yapılır, "▶️ Hazırla"
seçilenleri sırayla içeriğe çevirir. Seçim Worker'da yapılır, GitHub'a gitmez.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from . import config, db, fetch_news, sutun

log = logging.getLogger(__name__)

# Kural tabanlı önem puanı (haber_puanlama). Eski içerik eşiği 9'du; öneriye
# insan baktığı için eşik daha düşük — config'deki haberler.onem_puani_esigi.
ONERI_ESIGI = config.ayar_al("haberler.onem_puani_esigi", 6)
TAZELIK_SAAT = 36
TUR_BASI_AZAMI = 5      # Instabot'taki gibi: tek mesajda beş numara (1️⃣–5️⃣)
GUNLUK_AZAMI = 10       # günde iki tur
_RAKAMLAR = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

_AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
          "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
_GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
TR = timezone(timedelta(hours=3))

_DURAK_KELIMELER: Set[str] = {
    "ve", "ile", "veya", "bir", "bu", "şu", "o", "da", "de", "ta", "te",
    "icin", "için", "gibi", "kadar", "sonra", "once", "önce", "gore", "göre",
    "cok", "çok", "daha", "en", "mi", "mı", "mu", "mü", "ne", "nasil", "nasıl",
    "neden", "kim", "her", "tum", "tüm", "olan", "olarak", "etti", "oldu", "dedi",
    "yeni", "son", "dakika",
}


def _haber_kelimeleri(baslik: str) -> Set[str]:
    """Başlıktan bağlaç ve durak kelimeleri ayıklar, anlamlı gövde kümesini döner."""
    temiz = re.sub(r"[^\w\s]", " ", (baslik or "").lower())
    return {k for k in temiz.split() if len(k) >= 3 and k not in _DURAK_KELIMELER}


def _ayni_konu_mu(k1: Set[str], k2: Set[str]) -> bool:
    """İki başlığın aynı olayı/haberi işleyip işlemediğini Jaccard ve ortak kelimeyle denetler."""
    if not k1 or not k2:
        return False
    kesisim = len(k1 & k2)
    birlesim = len(k1 | k2)
    return (kesisim / birlesim >= 0.35) or (kesisim >= 3)


def tarih_metni(iso: Optional[str], simdi: Optional[datetime] = None) -> str:
    """'2026-09-24T11:05:00+00:00' → '24 Eylül 2026 Perşembe, 14:05 · 3 saat önce' (TR saati)."""
    try:
        dt = datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return "tarih bilinmiyor"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    yerel = dt.astimezone(TR)
    simdi = simdi or datetime.now(timezone.utc)
    fark = simdi - dt
    saat = int(fark.total_seconds() // 3600)
    if fark.total_seconds() < 3600:
        yas = f"{max(1, int(fark.total_seconds() // 60))} dakika önce"
    elif saat < 48:
        yas = f"{saat} saat önce"
    else:
        yas = f"{saat // 24} gün önce"
    return (f"{yerel.day} {_AYLAR[yerel.month - 1]} {yerel.year} {_GUNLER[yerel.weekday()]}, "
            f"{yerel:%H:%M} · {yas}")


def tarih_kisa(iso: Optional[str], simdi: Optional[datetime] = None) -> str:
    """Listede tek satıra sığan tarih: '24 Eylül 14:05 · 3 saat önce' (TR saati)."""
    uzun = tarih_metni(iso, simdi)
    if uzun == "tarih bilinmiyor":
        return uzun
    gun, _, yas = uzun.partition(" · ")
    parca = gun.split(" ")  # ['24', 'Eylül', '2026', 'Perşembe,', '14:05']
    return f"{parca[0]} {parca[1]} {parca[-1]} · {yas}"


def _gunluk_sayac_anahtari(simdi: datetime) -> str:
    return simdi.astimezone(TR).date().isoformat()


def _bugun_onerilen(simdi: datetime) -> int:
    ham = str(db.ayar_oku("haber_oneri_gunluk") or "")
    gun, _, sayi = ham.partition(":")
    return int(sayi) if gun == _gunluk_sayac_anahtari(simdi) and sayi.isdigit() else 0


def _sayaci_artir(simdi: datetime, adet: int) -> None:
    db.ayar_yaz("haber_oneri_gunluk", f"{_gunluk_sayac_anahtari(simdi)}:{_bugun_onerilen(simdi) + adet}")


def adaylari_sec(limit: int, offset: int = 0) -> List[Dict[str, Any]]:
    """Önerilecek haberler: taze, rehber değil, eşiği geçen; en yüksek puan önce.

    Aynı konuyu işleyen farklı ajans haberleri kümelenir; en yüksek puanlı olan
    aday listesine girerken diğerleri 'mutabakat' (consensus) sayacını artırır.
    Böylece 5 slot aynı konunun kopyalarıyla işgal edilmez, kaç kaynağın
    bu konuyu yazdığı rozetle (🔥 n kaynak) gösterilir.
    """
    esik = config.ayar_al("haberler.onem_puani_esigi", ONERI_ESIGI)
    ham_adaylar = []
    for h in db.bekleyen_haberleri_getir(limit=60):
        if (h.get("kategori") or "") == "rehber":
            continue  # rehber makaleleri haftalık konu madenciliğine gidiyor
        if fetch_news._saat_farki_saat(h.get("yayin_tarihi") or "") > TAZELIK_SAAT:
            continue
        if int(h.get("onem_puani") or 0) < esik:
            continue
        ham_adaylar.append(h)

    ham_adaylar.sort(key=lambda h: (int(h.get("onem_puani") or 0), h.get("yayin_tarihi") or ""), reverse=True)

    # Konu kümeleme ve mutabakat hesabı
    kume_listesi: List[Tuple[Dict[str, Any], Set[str]]] = []
    for h in ham_adaylar:
        kelimeler = _haber_kelimeleri(h.get("orijinal_baslik") or "")
        eslesen_kok = None
        for kok_h, kok_kelimeler in kume_listesi:
            if _ayni_konu_mu(kelimeler, kok_kelimeler):
                eslesen_kok = kok_h
                break
        if eslesen_kok:
            eslesen_kok["mutabakat"] = eslesen_kok.get("mutabakat", 1) + 1
        else:
            h["mutabakat"] = 1
            kume_listesi.append((h, kelimeler))

    tekil_adaylar = [kok_h for kok_h, _ in kume_listesi]
    return tekil_adaylar[offset:offset + max(0, limit)]


def _tek_cumle(metin: str, azami: int = 180) -> str:
    """Özetin ilk cümlesi; Instabot'taki gibi başlığın altında tek satırlık 💬."""
    metin = " ".join((metin or "").split())
    cumle = metin.split(". ")[0].rstrip(".") + "." if metin else ""
    if len(cumle) > azami:
        cumle = cumle[:azami].rsplit(" ", 1)[0] + "…"
    return cumle


def oneri_listesi_mesaji(haberler: List[Dict[str, Any]], offset: int = 0) -> Tuple[str, Dict[str, Any]]:
    """Instabot'un öneri taslağı: tek mesaj, numaralı başlıklar, çoklu seçim düğmeleri.

    callback_data yalnızca haber id'si taşır (64 bayt sınırı); başlık düğme
    metninde bile yok, numara yeter. Seçim sayacı ("Hazırla (n)") Worker'da güncellenir.
    Telegram modern <blockquote expandable> kutusu ile spot, künye ve mutabakat rozeti taşır.
    """
    satirlar = ["📰 <b>Günün Öne Çıkan Haber Adayları</b>", ""]
    secim, incele = [], []
    gosterilecek = haberler[:len(_RAKAMLAR)]
    for i, h in enumerate(gosterilecek):
        rakam = _RAKAMLAR[i]
        puan = f"[{h['onem_puani']}] " if h.get("onem_puani") is not None else ""
        baslik = html.escape(h.get("orijinal_baslik") or "")
        url = str(h.get("orijinal_url") or "")
        if url.startswith("http"):
            satirlar.append(f"{rakam} <a href=\"{html.escape(url, quote=True)}\"><b>{puan}{baslik}</b></a>")
        else:
            satirlar.append(f"{rakam} <b>{puan}{baslik}</b>")
        ham_baslik = (h.get("orijinal_baslik") or "").lower()
        spot = _tek_cumle(h.get("orijinal_ozet") or h.get("makale_metni") or "")
        spot_str = f"💬 <i>{html.escape(spot)}</i>\n" if (spot and spot.lower().rstrip(".…") not in ham_baslik and ham_baslik not in spot.lower()) else ""
        sutun_adi = sutun.SUTUN_ADLARI.get(sutun.sutun_bul(h.get("kategori")) or "", "")
        kunye = " · ".join(html.escape(x) for x in (h.get("kaynak") or "", sutun_adi) if x)
        rozetler = []
        mut = h.get("mutabakat") or 1
        if mut >= 2:
            rozetler.append(f"🔥 {mut} kaynak")
        rozet_str = (" · " + " · ".join(rozetler)) if rozetler else ""
        tarih_str = f" · 🗓 {tarih_kisa(h.get('yayin_tarihi'))}" if h.get("yayin_tarihi") else ""
        satirlar.append(
            f"<blockquote expandable>{spot_str}"
            f"📌 <i>{kunye}</i>{rozet_str}{tarih_str} · <code>/incele_{h['id']}</code></blockquote>"
        )
        satirlar.append("")
        secim.append({"text": rakam, "callback_data": f"sec:{h['id']}"})
        incele.append({"text": f"🔍 {i + 1}", "callback_data": f"incele:{h['id']}"})
    satirlar.append("<i>Numaralara basarak haber seçebilir, 🔍 butonlarıyla veya /incele &lt;id&gt; "
                    "ile detaylarını önizleyebilirsin.</i>")

    ileri_offset = offset + len(gosterilecek)
    klavye = {"inline_keyboard": [
        secim,
        incele,
        [{"text": "▶️ Hazırla (0)", "callback_data": "hazirla_secilenler"}],
        [
            {"text": "🔄 Başka Öner", "callback_data": f"oneri_baska:{ileri_offset}"},
            {"text": "❌ Hiçbiri", "callback_data": "oneri_gec"},
        ],
    ]}
    return "\n".join(satirlar), klavye


def onerileri_gonder(tara: bool = True, bos_ise_bildir: bool = False, offset: int = 0) -> int:
    """RSS'i tarar, taze adayları gruba öneri olarak gönderir. Gönderilen adedi döner."""
    from . import telegram_bot

    if tara:
        yeni = fetch_news.rss_tara()
        log.info("RSS taraması: %d yeni kayıt", len(yeni))

    simdi = datetime.now(timezone.utc)
    if offset == 0:
        kalan = GUNLUK_AZAMI - _bugun_onerilen(simdi)
        if kalan <= 0:
            log.info("Günlük öneri sınırı (%d) doldu.", GUNLUK_AZAMI)
            return 0
        istenen = min(TUR_BASI_AZAMI, kalan)
    else:
        istenen = TUR_BASI_AZAMI

    gonderilen = 0
    adaylar = adaylari_sec(istenen, offset=offset)
    if adaylar:
        secilen_aday = None
        ilk_gorsel = None
        for a in adaylar:
            g = a.get("gorsel_url")
            if g and (str(g).startswith("http") or Path(str(g)).exists()):
                ilk_gorsel = g
                secilen_aday = a
                break
        if not secilen_aday and adaylar:
            secilen_aday = adaylar[0]
            ilk_gorsel = secilen_aday.get("gorsel_url")

        if ilk_gorsel and (str(ilk_gorsel).startswith("http") or Path(str(ilk_gorsel)).exists()):
            try:
                baslik_kisa = html.escape(secilen_aday.get("orijinal_baslik") or "")
                puan_val = min(10, int(secilen_aday.get("onem_puani") or 8))
                foto_caption = (
                    f"📰 <b>GÜNÜN 1 NUMARALI HABER ADAYI [{puan_val}/10]</b>\n"
                    f"<b>{baslik_kisa}</b>\n\n"
                    f"<i>Günün öne çıkan {len(adaylar)} haber adayı ve seçim menüsü aşağıdadır 👇</i>"
                )
                telegram_bot.fotograf_gonder(ilk_gorsel, caption=foto_caption)
            except Exception as e:
                log.warning("Öneri kapak fotoğrafı gönderilemedi: %s", e)

        metin, klavye = oneri_listesi_mesaji(adaylar, offset=offset)
        if telegram_bot.mesaj_gonder(metin, reply_markup=klavye):
            for h in adaylar:
                db.haber_guncelle(h["id"], durum="onerildi")
            gonderilen = len(adaylar)
    if gonderilen and offset == 0:
        _sayaci_artir(simdi, gonderilen)
    elif not gonderilen and bos_ise_bildir:
        esik = config.ayar_al("haberler.onem_puani_esigi", ONERI_ESIGI)
        telegram_bot.mesaj_gonder(
            f"📭 Şu an önerilecek taze haber yok (son {TAZELIK_SAAT} saat, puan ≥ {esik})."
        )
    log.info("%d haber önerisi gönderildi (offset=%d).", gonderilen, offset)
    return gonderilen


def ham_haber_mi(h: Optional[Dict[str, Any]]) -> bool:
    """Kayıt içeriğe çevrilmemiş bir haber önerisi mi (içerik kartı yerine haber ayrıntısı)?"""
    return bool(h) and not h.get("detay_metni") and h.get("durum") in ("yeni", "onerildi", "elendi")


def haber_detay_karti(h: Dict[str, Any]) -> Tuple[str, Optional[Dict[str, Any]]]:
    """🔍 / /incele: haberin ayrıntısı ve (henüz işlenmediyse) "İçeriğe çevir" düğmesi."""
    govde = " ".join((h.get("makale_metni") or h.get("orijinal_ozet") or "").split())
    if len(govde) > 900:
        govde = govde[:900].rsplit(" ", 1)[0] + "…"
    sutun_adi = sutun.SUTUN_ADLARI.get(sutun.sutun_bul(h.get("kategori")) or "", "")
    puan_fmt = min(10, int(h.get("onem_puani", 8))) if str(h.get("onem_puani", "")).isdigit() else 8
    kunye = " · ".join(x for x in (html.escape(h.get("kaynak") or ""), html.escape(sutun_adi),
                                   f"puan {puan_fmt}/10") if x)
    metin = (
        f"🔍 <b>Haber #{h['id']}</b>\n<b>{html.escape(h.get('orijinal_baslik') or '')}</b>\n\n"
        f"🗓 {tarih_metni(h.get('yayin_tarihi'))}\n🏷 {kunye}\n"
        f"📌 Durum: <code>{html.escape(str(h.get('durum')))}</code>\n"
    )
    if govde:
        metin += f"\n{html.escape(govde)}\n"
    if h.get("orijinal_url"):
        metin += f"\n🔗 <a href=\"{html.escape(h['orijinal_url'], quote=True)}\">Haberi kaynağında aç</a>"
    klavye = None
    if h.get("durum") in ("onerildi", "yeni", "elendi"):
        klavye = {"inline_keyboard": [[{"text": "📝 İçeriğe çevir", "callback_data": f"haber_uret:{h['id']}"}]]}
    return metin, klavye


def haberlerden_icerige(haber_idleri: List[int]) -> int:
    """Listeden seçilenler sırayla içeriğe çevrilir; her biri kendi onay mesajıyla gelir."""
    return sum(1 for haber_id in dict.fromkeys(haber_idleri) if haberden_icerige(haber_id))


def haberden_icerige(haber_id: int) -> bool:
    """"📝 İçeriğe çevir": triyaj haberden brief çıkarır, içerik onaya sunulur.

    Kullanıcı açıkça bu haberi seçtiği için (insan iradesi) triyaj haberi
    reddetmez (`zorla=True`), sektörel B5 formatında içerik onaya sunulur.
    """
    from . import haber_triyaj, telegram_bot

    haber = db.haber_getir(haber_id)
    if not haber:
        telegram_bot.mesaj_gonder(f"⚠️ Haber #{haber_id} bulunamadı (14 günden eskiyse havuzdan silinmiş olabilir).")
        return False
    if haber.get("durum") not in ("onerildi", "yeni", "elendi"):
        telegram_bot.mesaj_gonder(
            f"ℹ️ Haber #{haber_id} zaten işlenmiş (durum: <code>{html.escape(str(haber.get('durum')))}</code>)."
        )
        return False

    brief = haber_triyaj.triyaj_et(haber, asgari_guven=0, zorla=True)
    if not brief:
        gerekce = haber.get("_red_gerekcesi") or "triyaj yanıtı alınamadı"
        db.haber_guncelle(haber_id, durum="elendi")
        telegram_bot.mesaj_gonder(
            f"🚫 <b>Haber #{haber_id} içeriğe çevrilmedi.</b>\n"
            f"Neden: {html.escape(gerekce)}.\n"
            "<i>Haber metninden brief çıkarılamadı.</i>"
        )
        return False
    return telegram_bot.haberden_icerik_hazirla(haber, brief)
