"""
src/telegram/akislar/onay.py — Haber/otorite/sözlük içeriğini Telegram onayına sunma akışının ana sırası.

Katman 4 (akış). Sıra: metin → mevcut slayt/otorite verisi → YAYIN KAPISI → (gerekirse) çizim → CDN → DB → [otomatik yayın] →
eski mesajları sil → albüm → onay kartı. Her adım kendi modülünde (`kapi`, `onay_slayt`, `onay_karti`, `otomatik`);
bu dosya yalnız sıralamayı tutar. Davranış `tests/test_telegram_altin.py` (onay_* senaryoları) ile donduruldu.
"""

from __future__ import annotations

import html
import json
import logging

from ... import db, generate_text
from .. import album, istemci, temizlik
from . import kapi, onay_karti, onay_slayt, otomatik

log = logging.getLogger(__name__)


def haber_onayina_sun(haber_id: int, yeniden_ciz: bool = True, oto_yayin: bool = False) -> bool:
    """Haberin görselini ve metnini hazırlayıp Telegram onayına sunar.

    `oto_yayin=True`: kapıdan uyarısız geçerse onay beklenmeden yayınlanır; yayın ya da koşullardan biri
    tutmazsa içerik her zamanki gibi onaya düşer (otomatik yol hiçbir zaman içeriği kaybettirmez)."""
    from ... import yeni_formatlar
    try:
        return _haber_onayina_sun(haber_id, yeniden_ciz=yeniden_ciz, oto_yayin=oto_yayin)
    except yeni_formatlar.EksikIcerik as e:
        log.warning("İçerik #%s eksik alan yüzünden durdu: %s", haber_id, e)
        kapi._eksik_icerik_bildir(haber_id, e)
        return False


def _haber_onayina_sun(haber_id: int, yeniden_ciz: bool = True, oto_yayin: bool = False) -> bool:
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


    # 2. Slayt görsellerini al veya üret (yeniden_ciz=True ise bayat dosyaları kullanma)
    slayt_yollari = onay_slayt.mevcut_slaytlar(haber, yeniden_ciz)
    otorite_verisi, format_turu = onay_slayt.otorite_verisini_oku(haber)

    # YAYIN KAPISI — slayt ve video üretiminden ÖNCE: durdurulacak içerik için
    # görsel üretmek boşa dakika.
    # Hazır arşiv kartı kanun metniyle ve hakemle BİR KEZ doğrulandı (sozluk_arsivi); her yayında yeniden
    # model çağırmak kota harcar ve hakem gürültüsü kartı boşuna durdurur. Kanunun hâlâ aynı olduğu
    # kart seçilirken sınanır.
    kart_mi = bool(isinstance(otorite_verisi, dict) and (otorite_verisi.get("_brief") or {}).get("kart"))
    gecti, uyarilar = kapi.yayin_kapisi(haber_id, haber, kapi._denetim_verisi(haber, otorite_verisi), anlam_denetimi=not kart_mi)
    if not gecti:
        return False
    if oto_yayin and uyarilar:
        # Finanstaki kural: otomatik yayın insan onayını atlıyor, bu yüzden EN UFAK uyarıda durur
        log.warning("İçerik #%s otomatik yayını durduruldu: %s", haber_id, "; ".join(uyarilar))
        istemci.mesaj_gonder(
            f"🛑 <b>Otomatik yayın durduruldu (#{haber_id})</b> — {len(uyarilar)} denetim uyarısı.\n"
            "<i>İçerik onayınıza sunuluyor; uyarıları kontrol edip elle yayınlayın.</i>"
        )
        oto_yayin = False

    if not slayt_yollari:
        slayt_yollari = onay_slayt.slaytlari_ciz(haber_id, haber, otorite_verisi, format_turu)

    # 2.5 Slaytları Public CDN'e yükle (Runner bağımsızlığı ve API'ler için)
    slayt_urlleri = onay_slayt.cdn_yukle(slayt_yollari)

    # 2.6 Veritabanına kaydet (Video onaya sunulmaz; kullanıcı 'Yayınla' dediğinde derlenir - Instabot standardı)
    is_reels = (format_turu == "reels") or (haber.get("kategori") == "REELS")
    is_haber = (format_turu in ("dailybrief", "haber", "haber_dailybrief")) or (otorite_verisi and otorite_verisi.get("bicim") in ("haber", "B5")) or (not otorite_verisi and not is_reels)

    db.haber_guncelle(
        haber_id,
        slayt_yollari=json.dumps(slayt_yollari),
        slayt_urlleri=json.dumps(slayt_urlleri) if slayt_urlleri else None,
        video_yolu=None,
        durum="onay_bekliyor"
    )

    if oto_yayin:
        if otomatik._oto_yayinla(haber_id, slayt_yollari, haber, slayt_urlleri):
            return True
        istemci.mesaj_gonder(f"⚠️ #{haber_id} otomatik yayınlanamadı; içerik onayınıza sunuluyor.")

    # 2.7 Önceki tüm mesajları (eski onay kartı ve albüm slaytları) temizle
    temizlik.icerik_onceki_mesajlarini_temizle("haber_album", haber_id)
    temizlik.icerik_onceki_mesajlarini_temizle("haber", haber_id)

    # 3. Format bazlı başlık ve rozet belirleme (Haberle Birebir Aynı Standart)
    manset_h = html.escape(str(haber.get("manset") or ""), quote=False)
    rozet, dayanak, album_caption, kart_baslik = onay_karti.kart_basliklari(
        haber_id, haber, otorite_verisi, format_turu, is_reels, is_haber, manset_h)

    # 3.1 Slayt görsellerini albüm (veya tek görsel) olarak gönder
    album_res = album.medya_grubu_gonder(slayt_yollari, caption=album_caption, yedek_urller=slayt_urlleri)
    _, chat_id = istemci._bot_bilgileri()
    cid = int(str(chat_id).strip()) if str(chat_id).lstrip("-").isdigit() else None
    # Başarısız çağrıda "son albümün" kimliklerine bakılmaz: önceki içeriğin mesajları bu içeriğe yazılıp
    # sonraki temizlikte yanlışlıkla silinirdi.
    album_mids = album_res if isinstance(album_res, list) else []
    gorsel_notu = onay_karti._album_teslim_notu(album_res, min(len(slayt_yollari), 10), slayt_urlleri)
    for mid in album_mids:
        try:
            db.onay_istegi_kaydet("haber_album", str(haber_id), mid, cid)
        except Exception as e:
            log.warning("Albüm mesaj ID kaydedilemedi: %s", e)

    mesaj_metni = onay_karti.kart_metni(haber_id, haber, uyarilar, gorsel_notu, kart_baslik, rozet, dayanak, manset_h)
    butonlar = onay_karti.onay_butonlari(slayt_yollari, is_reels, is_haber)
    res = onay_karti._onay_kartini_gonder(haber_id, mesaj_metni, butonlar, manset_h, "haber")
    if res and isinstance(res, dict) and "message_id" in res:
        try:
            db.onay_istegi_kaydet("haber", str(haber_id), res["message_id"], cid)
        except Exception as e:
            log.warning("Onay isteği kaydedilemedi: %s", e)

    # Instabot tecrübesi (1c): Kullanıcı Telegram'da butona saniyeler içinde basabilir.
    # Onay mesajı gittiği an veritabanını GitHub'a güvenle kaydet (arka planda commit+push).
    try:
        from ... import db_senkron
        db_senkron.hemen_kaydet(f"db: haber #{haber_id} onaya sunuldu")
    except Exception as e:
        log.warning("Hemen kaydetme adımı atlandı: %s", e)

    return True
