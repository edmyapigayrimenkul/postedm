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
from .. import ayarlar, istemci
from . import havuz, onay, reels, sozluk

log = logging.getLogger(__name__)


def _yeni_haber_kaydet(
    kaynak: str,
    baslik: str,
    orijinal_url: str,
    ozet: str,
    onem_puani: int,
    kategori: str,
    manset: str,
    veri: Dict[str, Any],
) -> int:
    simdi = datetime.now(timezone.utc).isoformat()
    with db._baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet,
                                     eklenme_tarihi, onem_puani, kategori, manset, detay_metni,
                                     ig_caption, threads_metin, durum)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'yeni')""",
            (
                kaynak,
                baslik,
                orijinal_url,
                ozet,
                simdi,
                onem_puani,
                kategori,
                manset,
                json.dumps(veri, ensure_ascii=False),
                veri.get("caption_instagram", ""),
                veri.get("caption_threads", ""),
            ),
        )
        haber_id = int(cur.lastrowid)
        conn.commit()
    return haber_id


def haberden_icerik_hazirla(haber: Dict[str, Any], brief: Dict[str, Any]) -> bool:
    """Triyajdan geçmiş haberi, konu bankası akışıyla AYNI yoldan içeriğe çevirir."""
    istemci.mesaj_gonder(
        f"📰 <b>Haber içeriği</b> · {brief['sutun']} · {brief['bicim']} · puan {brief['_guven']}\n"
        f"<i>{haber.get('orijinal_baslik', '')[:120]}</i>\n\nİçerik hazırlanıyor..."
    )

    if not brief.get("_dayanak"):
        brief["_dayanak"] = haber.get("orijinal_ozet") or haber.get("orijinal_baslik") or ""
    brief["bicim"] = "B5"
    from ... import fetch_article
    makale = fetch_article.kuyrugu_kes(haber.get("makale_metni"))
    if len(makale) < fetch_article.ASGARI_UZUNLUK and str(haber.get("orijinal_url") or "").startswith("http"):
        makale = fetch_article.kuyrugu_kes(fetch_article.makale_metni_cek(haber["orijinal_url"], haber.get("orijinal_baslik", "")))
    if len(makale) >= fetch_article.ASGARI_UZUNLUK:
        brief["_makale"] = makale[:fetch_article.AZAMI_UZUNLUK]
    if haber.get("orijinal_baslik"):
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


def konu_bankasindan_hazirla(gun: Optional[int] = None, oto_yayin: bool = False) -> bool:
    """Günün takvimine uygun konuyu bankadan alıp içerik üretir ve onaya sunar (veya otomatik yayınlar)."""
    havuzdan = havuz.havuzdan_sun("b1", oto_yayin=True) if oto_yayin else havuz.havuzdan_sun("b1")
    if havuzdan is not None:
        return havuzdan

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
        istemci.mesaj_gonder("❌ İçerik üretilemedi. Gemini API yanıt vermedi. Konu bankadaki yerini koruyor.")
        return False

    haber_id = _yeni_haber_kaydet(
        kaynak=f"EDM Konu Bankası // {konu['kod']}",
        baslik=konu["baslik"],
        orijinal_url=f"edm://konu/{konu['kod']}/{int(time.time())}",
        ozet=veri.get("spot", ""),
        onem_puani=veri.get("onem_puani", 8),
        kategori=veri.get("kategori_kodu", "TAPU_VE_HUKUK"),
        manset=generate_text.manset_birlestir(veri),
        veri=veri,
    )
    konu_bankasi.kullanildi_isaretle(konu["kod"], haber_id=haber_id, format_turu="b1")
    return onay.haber_onayina_sun(haber_id, oto_yayin=True) if oto_yayin else onay.haber_onayina_sun(haber_id)


def _sozluk_slotu(oto_yayin: Optional[bool] = None) -> bool:
    """Sözlük: önce hazır kart; kart kalmadıysa modelle üretilip HER ZAMAN onaya sunulur."""
    zamanli_tur = oto_yayin is True
    if zamanli_tur and not sozluk.sozluk_zamanli_gunu_mu():
        log.info("Zamanlanmış sözlük bugün atlanıyor: iki günde bir çıkar.")
        return True
    sonuc = sozluk.sozluk_karti_hazirla_ve_sun() if oto_yayin is None else sozluk.sozluk_karti_hazirla_ve_sun(oto_yayin=oto_yayin)
    if sonuc is None:
        istemci.mesaj_gonder("ℹ️ Yayınlanabilir hazır sözlük kartı kalmadı; konu bankasından üretilip onayınıza sunuluyor.")
        sonuc = hizli_icerik_uret(format_turu="sozluk")
    if zamanli_tur and sonuc:
        sozluk.sozluk_zamanli_isaretle()
    return sonuc


def slot_icerigi_hazirla_ve_sun(slot: str = "bilgilendirici", oto_yayin: Optional[bool] = None, offset: int = 0) -> bool:
    """Günün içeriği ve elle/zamanlı tetiklenen slotlar ('bilgilendirici', 'sozluk', 'reels', 'haber')."""
    slot = (slot or "bilgilendirici").lower()

    if slot == "sozluk":
        log.info("Sözlük içeriği hazırlanıyor (Otomatik yayın: %s)...", oto_yayin)
        return _sozluk_slotu(oto_yayin=oto_yayin)

    if slot == "reels":
        return reels.reels_slotu_hazirla_ve_sun(oto_yayin=oto_yayin)

    if slot == "haber":
        from ... import haber_oneri
        haber_oneri.onerileri_gonder(tara=True, bos_ise_bildir=True, offset=offset)
        return True

    aktif_oto = bool(oto_yayin)
    if aktif_oto and not ayarlar.oto_yayin_modu_acik_mi():
        istemci.mesaj_gonder("ℹ️ Yarı otomatik (onaylı) mod aktif: günün içeriği onayınıza sunuluyor.")
        aktif_oto = False

    secilen_format = konu_bankasi.siradaki_bilgilendirici_format()
    log.info("Günün içeriği — döngüdeki format: %s (Otomatik yayın: %s)", secilen_format, aktif_oto)
    if secilen_format == "b1":
        basarili = konu_bankasindan_hazirla(oto_yayin=True) if aktif_oto else konu_bankasindan_hazirla()
    elif secilen_format == "sozluk":
        basarili = _sozluk_slotu(oto_yayin=oto_yayin)
    elif aktif_oto:
        basarili = _format_hazirla(format_turu=secilen_format, oto_yayin=True)
    else:
        basarili = hizli_icerik_uret(format_turu=secilen_format)

    if basarili:
        konu_bankasi.bilgilendirici_format_kaydet(secilen_format)
    return basarili


def _format_hazirla(format_turu: Optional[str] = None, oto_yayin: bool = False) -> bool:
    """Özel format (sozluk, nedir_dogrusu, vaka, net_cevap) üretir; oto_yayin yalnızca zamanlı otorite döngüsünde True olur."""
    etiketler = {
        "sozluk": "📖 EDM Gayrimenkul Sözlüğü",
        "nedir_dogrusu": "⚖️ Nedir Doğrusu?",
        "vaka": "📂 Örnek Olay",
        "net_cevap": "❓ Net Cevap Rehberi",
    }
    format_etiketi = etiketler.get(format_turu or "", "Otorite İçeriği")
    havuzdan = havuz.havuzdan_sun(format_turu or "", oto_yayin=True) if oto_yayin else havuz.havuzdan_sun(format_turu or "")
    if havuzdan is not None:
        return havuzdan
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

    haber_id = _yeni_haber_kaydet(
        kaynak=f"EDM Konu Bankası // {konu['kod']}",
        baslik=konu["baslik"],
        orijinal_url=f"edm://konu/{konu['kod']}/{int(time.time())}",
        ozet=konu.get("aci", ""),
        onem_puani=konu.get("onem_puani", 8),
        kategori=konu.get("sutun", "S1"),
        manset=generate_text.manset_birlestir(veri) or konu["baslik"],
        veri=veri,
    )
    konu_bankasi.kullanildi_isaretle(konu["kod"], haber_id=haber_id, format_turu=format_turu)
    return onay.haber_onayina_sun(haber_id, oto_yayin=True) if oto_yayin else onay.haber_onayina_sun(haber_id)


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
    return _format_hazirla(format_turu=format_turu, oto_yayin=False)
