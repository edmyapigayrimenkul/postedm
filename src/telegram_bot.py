"""
telegram_bot.py — EDM Telegram Onay ve Yönetim Botu
Haber ve İlan önizlemelerini Telegram grubuna iletir, inline butonlarla onay alır.
Tek tıkla portföyden ilan seçip post üretme özelliğini yönetir.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from . import config, db, fetch_listings, generate_text, konu_bankasi, make_image, upload_image

log = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"


def _bot_bilgileri() -> tuple[str, str]:
    token = config.env_al("TELEGRAM_BOT_TOKEN")
    chat_id = config.env_al("TELEGRAM_CHAT_ID")
    return token, chat_id


def mesaj_gonder(metin: str, reply_markup: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    token, chat_id = _bot_bilgileri()
    if not token or not chat_id:
        log.warning("Telegram token veya chat_id eksik.")
        return None

    url = TELEGRAM_API_URL.format(token=token, method="sendMessage")
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": metin,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            return r.json().get("result")
        log.error("Telegram mesaj hatası [%d]: %s", r.status_code, r.text)
    except Exception as e:
        log.error("Telegram istek hatası: %s", e)
    return None


def fotograf_gonder(
    foto_yolu_veya_url: Path | str,
    caption: str = "",
    reply_markup: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    token, chat_id = _bot_bilgileri()
    if not token or not chat_id:
        return None

    url = TELEGRAM_API_URL.format(token=token, method="sendPhoto")
    data: Dict[str, Any] = {
        "chat_id": chat_id,
        "caption": caption[:1024],
        "parse_mode": "HTML",
    }
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)

    p = Path(str(foto_yolu_veya_url))
    try:
        if p.exists() and p.is_file():
            with open(p, "rb") as f:
                r = requests.post(url, data=data, files={"photo": f}, timeout=30)
        else:
            data["photo"] = str(foto_yolu_veya_url)
            r = requests.post(url, data=data, timeout=30)

        if r.status_code == 200:
            return r.json().get("result")
        log.error("Telegram fotoğraf hatası [%d]: %s", r.status_code, r.text)
    except Exception as e:
        log.error("Telegram fotoğraf gönderme hatası: %s", e)
    return None


def medya_grubu_gonder(foto_yollari: List[Path | str], caption: str = "") -> bool:
    """Carousel önizlemesi için albüm (medya grubu) gönderir."""
    token, chat_id = _bot_bilgileri()
    if not token or not chat_id or not foto_yollari:
        return False

    url = TELEGRAM_API_URL.format(token=token, method="sendMediaGroup")
    media = []
    files = {}

    for idx, f_yol in enumerate(foto_yollari[:10]):
        attach_name = f"photo_{idx}"
        m_item: Dict[str, Any] = {"type": "photo", "media": f"attach://{attach_name}"}
        if idx == 0 and caption:
            m_item["caption"] = caption[:1024]
            m_item["parse_mode"] = "HTML"
        media.append(m_item)

        p = Path(str(f_yol))
        if p.exists():
            files[attach_name] = open(p, "rb")

    try:
        r = requests.post(url, data={"chat_id": chat_id, "media": json.dumps(media)}, files=files, timeout=45)
        for fp in files.values():
            fp.close()
        return r.status_code == 200
    except Exception as e:
        log.error("Telegram medya grubu hatası: %s", e)
        for fp in files.values():
            fp.close()
    return False


# =========================================================================
# ONAY AKIŞLARI (HABER VE İLAN)
# =========================================================================


def haber_onayina_sun(haber_id: int) -> bool:
    """Haberin görselini ve metnini hazırlayıp Telegram onayına sunar."""
    haber = db.haber_getir(haber_id)
    if not haber:
        return False

    # 1. Metin yoksa üret
    if not haber.get("manset"):
        metin_sonuc = generate_text.haber_metinleri_uret(haber)
        if not metin_sonuc:
            log.error("Haber metni üretilemedi (#%d)", haber_id)
            return False
        haber = db.haber_getir(haber_id)

    # 2. Slayt görsellerini al veya üret
    slayt_yollari = []
    if haber.get("slayt_yollari"):
        try:
            mevcut = json.loads(haber["slayt_yollari"])
            if isinstance(mevcut, list) and len(mevcut) > 0 and all(Path(p).exists() for p in mevcut):
                slayt_yollari = [str(p) for p in mevcut]
        except Exception:
            slayt_yollari = []

    otorite_verisi = None
    if haber.get("detay_metni"):
        try:
            otorite_verisi = json.loads(haber["detay_metni"])
        except Exception:
            otorite_verisi = None

    if not slayt_yollari:
        if (
            otorite_verisi
            and isinstance(otorite_verisi, dict)
            and isinstance(otorite_verisi.get("slayt_2_detay"), dict)
        ):
            slayt_listesi = make_image.otorite_gonderi_slaytlari_uret(otorite_verisi, cikti_onek=f"haber_{haber_id}")
            slayt_yollari = [str(p) for p in slayt_listesi]
        else:
            # Klasik 3'lü Haber Paftası (Fallback)
            k1 = make_image.haber_slayti_1_ciz(
                manset=haber["manset"],
                spot=haber.get("slayt_1_spot") or haber.get("detay_metni", "")[:120],
                kaynak=haber.get("kaynak", "EDM"),
                tarih=haber.get("yayin_tarihi", ""),
                foto_url=haber.get("gorsel_url"),
            )
            maddeler = [haber.get("slayt_2_detay", "")] if haber.get("slayt_2_detay") else [haber.get("detay_metni", "")]
            k2 = make_image.haber_slayti_2_ciz(
                manset=haber["manset"],
                maddeler=maddeler,
            )
            k3 = make_image.haber_kapanis_slayti_ciz()
            slayt_yollari = [str(k1), str(k2), str(k3)]

    rozet = "HUKUK & YATIRIM REHBERİ"
    dayanak = haber.get("kaynak", "EDM Yapı & Gayrimenkul")
    if otorite_verisi and isinstance(otorite_verisi, dict):
        rozet = otorite_verisi.get("rozet_metni", rozet)
        dayanak = otorite_verisi.get("yasal_dayanak", dayanak)

    # 2.5 Slaytları Public CDN'e yükle (Runner bağımsızlığı ve API'ler için)
    slayt_urlleri = []
    try:
        slayt_urlleri = upload_image.coklu_gorsel_yukle(slayt_yollari)
    except Exception as e:
        log.warning("Görseller CDN'e yüklenemedi: %s", e)

    db.haber_guncelle(
        haber_id,
        slayt_yollari=json.dumps(slayt_yollari),
        slayt_urlleri=json.dumps(slayt_urlleri) if slayt_urlleri else None,
        durum="onay_bekliyor"
    )

    # 3. Medya albümü gönder
    caption_ozeti = (haber.get("ig_caption") or "")[:350]

    # Yayın öncesi denetim. Otomatik eleme yapmıyor; onaylayan kişiye
    # "şuna bir daha bak" diyor. En kritik denetim uydurma kanun maddesi:
    # gerçek bir emlak ofisinin hesabında bu ciddi bir sorumluluk.
    denetim_basligi = ""
    if otorite_verisi and isinstance(otorite_verisi, dict):
        try:
            from . import dogrula
            uyarilar = dogrula.denetle(otorite_verisi, otorite_verisi.get("_brief"))
            denetim_basligi = dogrula.uyari_basligi(uyarilar)
            if uyarilar:
                log.info("Denetim uyarıları (#%d): %s", haber_id, "; ".join(uyarilar))
        except Exception as e:
            log.warning("Denetim çalıştırılamadı: %s", e)

    onizleme_metni = (
        denetim_basligi
        + f"🏛 <b>YENİ OTORİTE İÇERİĞİ ONAY BEKLİYOR</b>\n\n"
        f"<b>Kategori:</b> {rozet}\n"
        f"<b>Dayanak:</b> {dayanak}\n"
        f"<b>Manşet:</b> {haber['manset']}\n"
        f"<b>Önem Puanı:</b> {haber.get('onem_puani', 8)}/10\n\n"
        f"<b>Açıklama (Instagram/Facebook):</b>\n{caption_ozeti}..."
    )

    medya_grubu_gonder(slayt_yollari, caption=onizleme_metni)

    # 4. Onay Butonları
    butonlar = {
        "inline_keyboard": [
            [
                {"text": "✅ Yayına Al (Tüm Kanallar)", "callback_data": f"onayla:haber:hepsi:{haber_id}"},
            ],
            [
                {"text": "📸 Instagram", "callback_data": f"onayla:haber:ig:{haber_id}"},
                {"text": "📘 Facebook", "callback_data": f"onayla:haber:fb:{haber_id}"},
                {"text": "🧵 Threads", "callback_data": f"onayla:haber:threads:{haber_id}"},
            ],
            [
                {"text": "🎬 Sadece Video (Reels/Shorts/TikTok)", "callback_data": f"onayla:haber:video:{haber_id}"},
            ],
            [
                {"text": "🔄 Metinleri Yenile", "callback_data": f"yenile:haber:{haber_id}"},
                {"text": "❌ Reddet", "callback_data": f"reddet:haber:{haber_id}"},
            ],
        ]
    }
    mesaj_gonder("Bu içeriği sosyal medya hesaplarımızda paylaşalım mı?", reply_markup=butonlar)
    return True


def haberden_icerik_hazirla(haber: Dict[str, Any], brief: Dict[str, Any]) -> bool:
    """Triyajdan geçmiş haberi, konu bankası akışıyla AYNI yoldan içeriğe çevirir.

    Haber ham metin olarak değil, triyajın ürettiği brief olarak işleniyor —
    konu bankası girdisiyle aynı şekilde. Model artık açıyı kendisi uydurmuyor,
    hazır bir brief işliyor; kaliteyi yükselten şey bu.
    """
    mesaj_gonder(
        f"📰 <b>Haber içeriği</b> · {brief['sutun']} · {brief['bicim']} · puan {brief['_guven']}\n"
        f"<i>{haber.get('orijinal_baslik', '')[:120]}</i>\n\nİçerik hazırlanıyor..."
    )

    veri = generate_text.konudan_uret(brief)
    if not veri:
        mesaj_gonder("❌ Haber içeriği üretilemedi.")
        return False

    db.haber_guncelle(
        haber["id"],
        kategori=veri.get("kategori_kodu"),
        manset=generate_text.manset_birlestir(veri),
        detay_metni=json.dumps(veri, ensure_ascii=False),
        ig_caption=veri.get("caption_instagram"),
        threads_metin=veri.get("caption_threads"),
    )
    return haber_onayina_sun(haber["id"])


def konu_bankasindan_hazirla(gun: Optional[int] = None) -> bool:
    """Günün takvimine uygun konuyu bankadan alıp içerik üretir ve onaya sunar.

    Faz 1'in ana giriş noktası (ICERIK-SISTEMI.md §2). RSS'e bağımlı değildir:
    yüksek etkileşimli emlak içeriğinin çoğu haber değil evergreen bilgidir ve
    her gün üretilebilir olması takvimin aksamamasını sağlar.
    """
    konu = konu_bankasi.sonraki_konu(gun=gun)
    if not konu:
        mesaj_gonder(
            "⚠️ Konu bankasında uygun konu kalmadı. "
            "<code>data/konu_bankasi.yaml</code> dosyasına yeni konu eklenmeli."
        )
        return False

    mesaj_gonder(
        f"⏳ <b>{konu['kod']}</b> · {konu['sutun']} · {konu['bicim']}\n"
        f"<i>{konu['baslik']}</i>\n\nİçerik hazırlanıyor..."
    )

    veri = generate_text.konudan_uret(konu)
    if not veri:
        konu_bankasi.kullanildi_isaretle(konu["kod"], sonuc="hata")
        mesaj_gonder("❌ İçerik üretilemedi. Gemini API yanıt vermedi.")
        return False

    orijinal_url = f"edm://konu/{konu['kod']}/{int(time.time())}"
    with db._baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet,
                                     eklenme_tarihi, onem_puani, kategori, manset, detay_metni,
                                     ig_caption, threads_metin, durum)
               VALUES (?, ?, ?, ?, datetime('now'), ?, ?, ?, ?, ?, ?, 'yeni')""",
            (
                f"EDM Konu Bankası // {konu['kod']}",
                konu["baslik"],
                orijinal_url,
                veri.get("spot", ""),
                veri.get("onem_puani", 8),
                veri.get("kategori_kodu", "TAPU_VE_HUKUK"),
                generate_text.manset_birlestir(veri),
                json.dumps(veri, ensure_ascii=False),
                veri.get("caption_instagram", ""),
                veri.get("caption_threads", ""),
            ),
        )
        haber_id = cur.lastrowid
        conn.commit()

    konu_bankasi.kullanildi_isaretle(konu["kod"], haber_id=haber_id)
    return haber_onayina_sun(haber_id)


def otorite_postu_hazirla_ve_sor(konu: str, kategori_kodu: Optional[str] = None) -> bool:
    """Belirtilen hukuki, finansal veya sektörel bir konudan 4 slaytlık otorite postu üretip Telegram'a sunar."""
    mesaj_gonder(f"⏳ <b>'{konu[:60]}...'</b> konusu için EDM Otorite Carousel içeriği hazırlanıyor...")

    # 1. Gemini ile 4 slaytlık otorite içeriği üret
    veri = generate_text.otorite_icerigi_uret(konu, kategori_kodu=kategori_kodu)
    if not veri:
        mesaj_gonder("❌ Otorite içeriği üretilemedi. Gemini API yanıt vermedi.")
        return False

    # 2. Veritabanına kaydet
    orijinal_url = f"edm://otorite/{int(time.time())}"
    with db._baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet, eklenme_tarihi, onem_puani, kategori, manset, detay_metni, ig_caption, threads_metin, durum)
               VALUES (?, ?, ?, ?, datetime('now'), ?, ?, ?, ?, ?, ?, 'yeni')""",
            (
                "EDM Otorite Masası",
                konu,
                orijinal_url,
                veri.get("spot", ""),
                veri.get("onem_puani", 9),
                veri.get("kategori_kodu", "TAPU_VE_HUKUK"),
                generate_text.manset_birlestir(veri) or konu,
                json.dumps(veri, ensure_ascii=False),
                veri.get("caption_instagram", ""),
                veri.get("caption_threads", ""),
            ),
        )
        haber_id = cur.lastrowid
        conn.commit()

    # 3. Onaya sun
    return haber_onayina_sun(haber_id)


def tek_tikla_ilan_menusu_gonder() -> bool:
    """Portföydeki aktif ilanları buton listesi olarak Telegram'a gönderir."""
    ilanlar = fetch_listings.aktif_ilanlar(limit=6)
    if not ilanlar:
        mesaj_gonder("Portföyde paylaşılacak aktif ilan bulunamadı.")
        return False

    satirlar = []
    for i in ilanlar:
        fiyat_str = fetch_listings.ilan_fiyat_bicimlendir(float(i.get("fiyat", 0)), i.get("paraBirimi", "TRY"))
        kisa_baslik = i.get("baslik", "")[:35]
        buton_metni = f"🏡 {i.get('ilce')} {i.get('tip')} ({fiyat_str}) — {kisa_baslik}"
        satirlar.append([{"text": buton_metni, "callback_data": f"ilan_sec:{i.get('id')}"}])

    satirlar.append([{"text": "🔄 İlan Listesini Yenile", "callback_data": "ilan_menu_yenile"}])

    reply_markup = {"inline_keyboard": satirlar}
    mesaj_gonder(
        "<b>EDM PORTFÖYÜ — TEK TIKLA İLAN PAYLAŞ</b>\n\n"
        "Aşağıdaki aktif ilanlarımızdan birini seçin, anında 4:5 kartları ve metni üretilip onayınıza sunulsun:",
        reply_markup=reply_markup,
    )
    return True


def ilan_postunu_hazirla_ve_sor(ilan_id: str) -> bool:
    """Seçilen ilanın slaytlarını ve metnini üretip onay butonlarıyla gruba gönderir."""
    ilan = db.ilan_getir(ilan_id)
    if not ilan:
        return False

    mesaj_gonder(f"⏳ <b>#{ilan_id}</b> nolu ilan için görseller ve açıklama hazırlanıyor...")

    # 1. Metin üret
    metinler = generate_text.ilan_metinleri_uret(ilan)

    # 2. Slayt görsellerini üret (3'lü Prestij Carousel)
    k1 = make_image.ilan_kapak_slayti_ciz(ilan)
    k2 = make_image.ilan_detay_slayti_ciz(ilan)
    k3 = make_image.ilan_kapanis_slayti_ciz(ilan)

    slayt_yollari = [str(k1), str(k2), str(k3)]

    caption = (metinler.get("ig_caption") if metinler else "") or (
        f"{ilan.get('baslik')}\n\n"
        f"📍 Konum: {ilan.get('ilce')} / {ilan.get('mahalle')}\n"
        f"💰 Fiyat: {fetch_listings.ilan_fiyat_bicimlendir(float(ilan.get('fiyat', 0)))}\n\n"
        f"EDM Yapı & Gayrimenkul · 0536 343 41 97\nedmyapigayrimenkul.com"
    )

    onizleme_metni = (
        f"🏡 <b>İLAN PAYLAŞIM ÖNİZLEMESİ</b>\n\n"
        f"<b>Başlık:</b> {ilan.get('baslik')}\n"
        f"<b>Fiyat:</b> {fetch_listings.ilan_fiyat_bicimlendir(float(ilan.get('fiyat', 0)))}\n"
        f"<b>Lokasyon:</b> {ilan.get('ilce')} / {ilan.get('mahalle')}\n\n"
        f"<b>Açıklama:</b>\n{caption[:350]}..."
    )

    medya_grubu_gonder(slayt_yollari, caption=onizleme_metni)

    butonlar = {
        "inline_keyboard": [
            [
                {"text": "✅ İlanı Yayınla (Tüm Kanallar)", "callback_data": f"onayla:ilan:hepsi:{ilan_id}"},
            ],
            [
                {"text": "📸 Instagram", "callback_data": f"onayla:ilan:ig:{ilan_id}"},
                {"text": "📘 Facebook", "callback_data": f"onayla:ilan:fb:{ilan_id}"},
                {"text": "🧵 Threads", "callback_data": f"onayla:ilan:threads:{ilan_id}"},
            ],
            [
                {"text": "🎬 Sadece Video (Reels/Shorts/TikTok)", "callback_data": f"onayla:ilan:video:{ilan_id}"},
            ],
            [
                {"text": "🔄 Yeniden Hazırla", "callback_data": f"yenile:ilan:{ilan_id}"},
                {"text": "❌ İptal Et", "callback_data": f"reddet:ilan:{ilan_id}"},
            ],
        ]
    }
    mesaj_gonder("Bu portföy ilanını sosyal medyada yayınlayalım mı?", reply_markup=butonlar)
    return True
