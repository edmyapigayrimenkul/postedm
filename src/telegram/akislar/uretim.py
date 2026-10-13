"""
src/telegram/akislar/uretim.py — Haber / konu bankası / slot / hızlı üretim: içeriği hazırlayıp onay akışına verir.

Katman 4 (akış). `hizli_icerik_uret` ⇄ `slot_icerigi_hazirla_ve_sun` ⇄ `_sozluk_slotu` birbirini çağırır; bu yüzden aynı modülde durur.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ... import db, generate_text, konu_bankasi
from .. import istemci
from . import onay, reels, sozluk

log = logging.getLogger(__name__)


def haberden_icerik_hazirla(haber: Dict[str, Any], brief: Dict[str, Any]) -> bool:
    """Triyajdan geçmiş haberi, konu bankası akışıyla AYNI yoldan içeriğe çevirir.

    Haber ham metin olarak değil, triyajın ürettiği brief olarak işleniyor —
    konu bankası girdisiyle aynı şekilde. Model artık açıyı kendisi uydurmuyor,
    hazır bir brief işliyor; kaliteyi yükselten şey bu.
    """
    istemci.mesaj_gonder(
        f"📰 <b>Haber içeriği</b> · {brief['sutun']} · {brief['bicim']} · puan {brief['_guven']}\n"
        f"<i>{haber.get('orijinal_baslik', '')[:120]}</i>\n\nİçerik hazırlanıyor..."
    )

    if not brief.get("_dayanak"):
        brief["_dayanak"] = haber.get("orijinal_ozet") or haber.get("orijinal_baslik") or ""
    # Model haberin tam metniyle çalışır (bkz. konu_bankasi.brief_metni). Eski
    # kayıtlarda gövdenin sonunda çerez/KVKK şablonu var; kuyruk burada da kesilir.
    from ... import fetch_article
    makale = fetch_article.kuyrugu_kes(haber.get("makale_metni"))
    if len(makale) >= fetch_article.ASGARI_UZUNLUK:
        brief["_makale"] = makale[:fetch_article.AZAMI_UZUNLUK]
    if haber.get("orijinal_baslik") and not brief.get("baslik"):
        brief["baslik"] = haber["orijinal_baslik"]
    if haber.get("kaynak"):
        brief["kaynak"] = haber["kaynak"]

    veri = generate_text.konudan_uret(brief, format_turu="dailybrief")
    if not veri:
        istemci.mesaj_gonder("❌ Haber içeriği üretilemedi.")
        return False
    veri["format_turu"] = "dailybrief"
    if haber.get("gorsel_url"):
        veri["gorsel_url"] = haber["gorsel_url"]
        veri["gorsel_yolu"] = haber["gorsel_url"]
        veri["foto_yolu"] = haber["gorsel_url"]
    if haber.get("orijinal_url"):
        veri["orijinal_url"] = haber["orijinal_url"]
    if haber.get("kaynak"):
        veri["kaynak"] = haber["kaynak"]

    db.haber_guncelle(
        haber["id"],
        kategori=veri.get("kategori_kodu"),
        manset=generate_text.manset_birlestir(veri),
        detay_metni=json.dumps(veri, ensure_ascii=False),
        ig_caption=veri.get("caption_instagram"),
        threads_metin=veri.get("caption_threads"),
    )
    return onay.haber_onayina_sun(haber["id"])


def konu_bankasindan_hazirla(gun: Optional[int] = None) -> bool:
    """Günün takvimine uygun konuyu bankadan alıp içerik üretir ve onaya sunar.

    Faz 1'in ana giriş noktası (ICERIK-SISTEMI.md §2). RSS'e bağımlı değildir:
    yüksek etkileşimli emlak içeriğinin çoğu haber değil evergreen bilgidir ve
    her gün üretilebilir olması takvimin aksamamasını sağlar.
    """
    konu = konu_bankasi.sonraki_konu(gun=gun, format_turu="b1")
    if not konu:
        istemci.mesaj_gonder(
            "⚠️ Konu bankasında uygun konu kalmadı. "
            "<code>data/konu_bankasi.yaml</code> dosyasına yeni konu eklenmeli."
        )
        return False

    istemci.mesaj_gonder(
        f"⏳ <b>{konu['kod']}</b> · {konu['sutun']} · {konu['bicim']}\n"
        f"<i>{konu['baslik']}</i>\n\nİçerik hazırlanıyor..."
    )

    veri = generate_text.konudan_uret(konu)
    if not veri:
        # Geçici API hatasında konuyu 3 gün kilitlemek yerine bakir tut
        istemci.mesaj_gonder("❌ İçerik üretilemedi. Gemini API yanıt vermedi. Konu bankadaki yerini koruyor.")
        return False

    orijinal_url = f"edm://konu/{konu['kod']}/{int(time.time())}"
    simdi = datetime.now(timezone.utc).isoformat()
    with db._baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet,
                                     eklenme_tarihi, onem_puani, kategori, manset, detay_metni,
                                     ig_caption, threads_metin, durum)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'yeni')""",
            (
                f"EDM Konu Bankası // {konu['kod']}",
                konu["baslik"],
                orijinal_url,
                veri.get("spot", ""),
                simdi,
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

    konu_bankasi.kullanildi_isaretle(konu["kod"], haber_id=haber_id, format_turu="b1")
    return onay.haber_onayina_sun(haber_id)


def _sozluk_slotu(oto_yayin: Optional[bool] = None) -> bool:
    """Günün sözlüğü: önce hazır kart; kart kalmadıysa modelle üretilip HER ZAMAN onaya sunulur."""
    if oto_yayin is None:
        sonuc = sozluk.sozluk_karti_hazirla_ve_sun()
    else:
        sonuc = sozluk.sozluk_karti_hazirla_ve_sun(oto_yayin=oto_yayin)
    if sonuc is None:
        istemci.mesaj_gonder("ℹ️ Yayınlanabilir hazır sözlük kartı kalmadı; konu bankasından üretilip onayınıza sunuluyor.")
        return hizli_icerik_uret(format_turu="sozluk")
    return sonuc


def slot_icerigi_hazirla_ve_sun(slot: str = "bilgilendirici", oto_yayin: Optional[bool] = None) -> bool:
    """Günün içeriği ve elle tetiklenen slotlar.

    - 'bilgilendirici': 10:00 TR'nin içeriği. Format dört günlük döngüde döner: b1, nedir_dogrusu,
      net_cevap, b1 (konu_bankasi.BILGILENDIRICI_FORMATLAR). Sözlük bu döngüde DEĞİL: her gün 12:30'da
      'sozluk' slotuyla ayrıca yayınlanır.
    - 'sozluk': sözlük içeriği (oto_yayin aktifse doğrudan yayınlanır).
    - 'haber': içerik ÜRETMEZ; taze haberleri tarihleriyle öneri olarak düşürür
      (haber_oneri). Hangisinin içeriğe çevrileceğine insan karar verir.
    """
    slot = (slot or "bilgilendirici").lower()

    if slot == "sozluk":
        log.info("Sözlük içeriği hazırlanıyor (Otomatik yayın: %s)...", oto_yayin)
        return _sozluk_slotu(oto_yayin=oto_yayin)

    if slot == "haber":
        from ... import haber_oneri
        haber_oneri.onerileri_gonder(tara=True, bos_ise_bildir=True)
        return True

    secilen_format = konu_bankasi.siradaki_bilgilendirici_format()
    log.info("Günün içeriği — döngüdeki format: %s", secilen_format)
    if secilen_format == "b1":
        basarili = konu_bankasindan_hazirla()
    elif secilen_format == "sozluk":
        basarili = _sozluk_slotu(oto_yayin=oto_yayin)
    else:
        basarili = hizli_icerik_uret(format_turu=secilen_format)

    if basarili:
        konu_bankasi.bilgilendirici_format_kaydet(secilen_format)
    return basarili


def hizli_icerik_uret(format_turu: Optional[str] = None) -> bool:
    """Belirtilen formata (sozluk, nedir_dogrusu, vaka, net_cevap, b1, reels, rotasyon, haber) göre konuyu üretir ve onaya sunar."""
    if format_turu == "reels":
        return reels.reels_hazirla_ve_sun()
    if format_turu == "rotasyon":
        return slot_icerigi_hazirla_ve_sun(slot="bilgilendirici")
    if format_turu == "haber":
        return slot_icerigi_hazirla_ve_sun(slot="haber")
    if format_turu == "b1":
        return konu_bankasindan_hazirla()

    etiketler = {
        "sozluk": "📖 EDM Gayrimenkul Sözlüğü",
        "nedir_dogrusu": "⚖️ Nedir Doğrusu?",
        "vaka": "📂 Örnek Olay",
        "net_cevap": "❓ Net Cevap Rehberi",
    }
    format_etiketi = etiketler.get(format_turu or "", "Otorite İçeriği")
    istemci.mesaj_gonder(f"⏳ <b>{format_etiketi}</b> için sıradaki konu hazırlanıyor...")

    konu = konu_bankasi.sonraki_konu(format_turu=format_turu)
    if not konu:
        istemci.mesaj_gonder("⚠️ Konu bankasında bakir konu kalmadı.")
        return False

    veri = generate_text.konudan_uret(konu, format_turu=format_turu)
    if not veri:
        istemci.mesaj_gonder("❌ İçerik üretilemedi. Gemini API yanıt vermedi.")
        return False

    if format_turu:
        veri["format_turu"] = format_turu

    orijinal_url = f"edm://konu/{konu['kod']}/{int(time.time())}"
    simdi = datetime.now(timezone.utc).isoformat()
    with db._baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet,
                                     eklenme_tarihi, onem_puani, kategori, manset, detay_metni,
                                     ig_caption, threads_metin, durum)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'yeni')""",
            (
                f"EDM Konu Bankası // {konu['kod']}",
                konu["baslik"],
                orijinal_url,
                konu.get("aci", ""),
                simdi,
                konu.get("onem_puani", 8),
                konu.get("sutun", "S1"),
                generate_text.manset_birlestir(veri) or konu["baslik"],
                json.dumps(veri, ensure_ascii=False),
                veri.get("caption_instagram", ""),
                veri.get("caption_threads", ""),
            ),
        )
        haber_id = cur.lastrowid
        conn.commit()

    konu_bankasi.kullanildi_isaretle(konu["kod"], haber_id=haber_id, format_turu=format_turu)
    return onay.haber_onayina_sun(haber_id)
