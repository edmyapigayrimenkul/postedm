"""
src/ozel_icerik.py — Telegram Üzerinden Dış Kaynaklı Özel İçerik Üretimi
2 Modu Destekler:
  1. /link <URL>     — Web sitesi, haber veya Resmi Gazete linkinden tam otorite postu üretir.
  2. /ozel <METİN>   — Kullanıcının yazdığı serbest konu/sorudan EDM formatında post üretir.
"""

from __future__ import annotations

import html
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from . import config, db, db_senkron, fetch_article, generate_text, mevzuat, telegram_bot

log = logging.getLogger("ozel_icerik")


def _url_bilgisi_al(url: str) -> Tuple[str, str, Optional[str], str]:
    """URL'den başlık, tam gövde metni, og:image görseli ve kaynak domainini çeker."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
    }
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()

    soup = BeautifulSoup(r.content, "html.parser")

    # 1. Başlık bul
    baslik = ""
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        baslik = og_title["content"].strip()
    elif soup.title and soup.title.string:
        baslik = soup.title.string.strip()

    # 2. Makale metni çek
    govde = fetch_article.makale_metni_cek(url) or ""
    if not govde:
        paragraflar = [p.get_text(" ", strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 40]
        govde = " ".join(paragraflar)[:3500]

    # 3. Görsel çek
    gorsel = fetch_article.og_gorseli_cek(url)

    domain = urlparse(url).netloc.replace("www.", "").split(".")[0].capitalize()
    return baslik or "Özel Gayrimenkul Rehberi", govde, gorsel, domain or "EDM Yapı & Gayrimenkul"


def linkten_icerik_uret(url: str) -> Optional[int]:
    """Verilen URL'den makaleyi çeker, EDM otorite formatına dönüştürür ve onay kartını gönderir."""
    log.info("Linkten içerik üretimi başladı: %s", url)
    telegram_bot.mesaj_gonder(f"🌐 <b>Link taranıyor:</b>\n<code>{url[:70]}...</code>\n<i>Metin çekiliyor ve analiz ediliyor...</i>")

    try:
        baslik, govde, gorsel_url, kaynak = _url_bilgisi_al(url)
    except Exception as e:
        log.error("URL kazıma hatası: %s", e)
        telegram_bot.mesaj_gonder(f"⚠️ Link içeriği okunamadı: {e}")
        return None

    if len(govde) < 100:
        govde = baslik

    simdi = datetime.now(timezone.utc).isoformat()
    konu_kodu = f"LINK_{int(time.time())}"

    konu_dict = {
        "kod": konu_kodu,
        "sutun": "S1",
        "kategori": "TAPU_VE_HUKUK",
        "baslik": baslik[:90],
        "aci": govde[:3000],
        "bicim": "B1",
        "onem_puani": 9,
        "kaynak": kaynak,
    }

    telegram_bot.mesaj_gonder("🤖 <b>Gemini içerik üretiyor...</b>\n<i>Otorite slaytları ve açıklama metni hazırlanıyor...</i>")
    veri = generate_text.konudan_uret(konu_dict)
    if not veri:
        telegram_bot.mesaj_gonder("❌ Gemini içerik üretemedi.")
        return None

    # Veritabanına kaydet (Varsa güncelle, yoksa ekle)
    manset = generate_text.manset_birlestir(veri) or baslik
    with db._baglanti_al() as conn:
        var = conn.execute("SELECT id FROM haberler WHERE orijinal_url = ?", (url,)).fetchone()
        if var:
            haber_id = var["id"]
            conn.execute(
                """UPDATE haberler SET kaynak = ?, orijinal_baslik = ?, orijinal_ozet = ?,
                                      eklenme_tarihi = ?, onem_puani = ?, kategori = ?,
                                      manset = ?, detay_metni = ?, ig_caption = ?,
                                      threads_metin = ?, durum = 'onay_bekliyor', gorsel_url = ?,
                                      slayt_yollari = NULL, slayt_urlleri = NULL
                   WHERE id = ?""",
                (
                    kaynak,
                    baslik,
                    govde[:400],
                    simdi,
                    9,
                    "TAPU_VE_HUKUK",
                    manset,
                    json.dumps(veri, ensure_ascii=False),
                    veri.get("caption_instagram", ""),
                    veri.get("caption_threads", ""),
                    gorsel_url,
                    haber_id,
                ),
            )
        else:
            cur = conn.execute(
                """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet,
                                         eklenme_tarihi, onem_puani, kategori, manset, detay_metni,
                                         ig_caption, threads_metin, durum, gorsel_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'onay_bekliyor', ?)""",
                (
                    kaynak,
                    baslik,
                    url,
                    govde[:400],
                    simdi,
                    9,
                    "TAPU_VE_HUKUK",
                    manset,
                    json.dumps(veri, ensure_ascii=False),
                    veri.get("caption_instagram", ""),
                    veri.get("caption_threads", ""),
                    gorsel_url,
                ),
            )
            haber_id = cur.lastrowid
        conn.commit()

    db_senkron.hemen_kaydet(f"db: linkten haber #{haber_id} olusturuldu")
    telegram_bot.haber_onayina_sun(haber_id)
    return haber_id


def konudan_ozel_icerik_uret(konu_metni: str) -> Optional[int]:
    """Kullanıcının girdiği serbest konudan / sorudan EDM otorite içeriği üretir."""
    log.info("Özel konudan içerik üretimi başladı: %s", konu_metni[:50])
    telegram_bot.mesaj_gonder(f"✍️ <b>Özel konu işleniyor:</b>\n<i>\"{html.escape(konu_metni[:120])}\"</i>\n\nİçerik ve slaytlar hazırlanıyor...")

    simdi = datetime.now(timezone.utc).isoformat()
    konu_kodu = f"OZEL_{int(time.time())}"
    orijinal_url = f"edm://ozel/{konu_kodu}"

    # Başlık ve açıyı ayır
    baslik = konu_metni.split("\n")[0][:80]

    konu_dict = {
        "kod": konu_kodu,
        "sutun": "S1",
        "kategori": "TAPU_VE_HUKUK",
        "baslik": baslik,
        "aci": konu_metni[:2500],
        "bicim": "B1",
        "onem_puani": 9,
        "kaynak": "EDM Gayrimenkul Uzmanı",
        # Metinde kanun atfı varsa güncel madde metni brief'e girer, denetim onunla yapılır
        "mevzuat": mevzuat.atif_satiri(konu_metni),
    }

    veri = generate_text.konudan_uret(konu_dict)
    if not veri:
        telegram_bot.mesaj_gonder("❌ Gemini içerik üretemedi.")
        return None

    manset = generate_text.manset_birlestir(veri) or baslik
    with db._baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet,
                                     eklenme_tarihi, onem_puani, kategori, manset, detay_metni,
                                     ig_caption, threads_metin, durum)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'onay_bekliyor')""",
            (
                "EDM Özel Talep",
                baslik,
                orijinal_url,
                konu_metni[:400],
                simdi,
                9,
                "TAPU_VE_HUKUK",
                manset,
                json.dumps(veri, ensure_ascii=False),
                veri.get("caption_instagram", ""),
                veri.get("caption_threads", ""),
            ),
        )
        haber_id = cur.lastrowid
        conn.commit()

    db_senkron.hemen_kaydet(f"db: ozel haber #{haber_id} olusturuldu")
    telegram_bot.haber_onayina_sun(haber_id)
    return haber_id


def arastir_icerik_uret(konu: str) -> Optional[int]:
    """
    Kullanıcının ilettiği konuyu (örn: /arastir 2026 tapu harcı muafiyeti şartları)
    Gemini ile derinlemesine araştırıp mevzuat maddeleri, kriterler ve uzman tavsiyesi
    içeren otorite karuseli üretir.
    """
    log.info("Konu araştırma süreci başlatıldı: %s", konu[:50])
    telegram_bot.mesaj_gonder(
        f"🔍 <b>Derin Gayrimenkul Araştırması Başlatıldı:</b>\n"
        f"<i>\"{html.escape(konu[:120])}\"</i>\n\n"
        f"⏳ İlgili mevzuat hükümleri taranıyor, uzman analizi ve slaytlar hazırlanıyor..."
    )

    arastirma_promptu = (
        f"Sen Türkiye'nin en saygın gayrimenkul hukuku ve tapu danışmanlığı şirketi EDM Yapı'nın "
        f"kıdemli hukuk ve değerleme uzmanısın. Kullanıcı şu konuda derin araştırma ve bilgilendirme istedi:\n"
        f"\"{konu}\"\n\n"
        f"Bu konuyu Tapu Kanunu, Medeni Kanun, Kat Mülkiyeti Kanunu veya ilgili güncel mevzuat hükümleriyle "
        f"somut, net ve vatandaşın hemen anlayabileceği pratik tavsiyelerle analiz et. "
        f"Temel sorun, kanuni hüküm ve yapılması gereken adımları özetle. "
        f"Dayandığın her hükmü '<kanun numarası> sayılı Kanun md. <madde>' biçiminde yaz "
        f"(ör. '4721 sayılı Kanun md. 733'); emin olmadığın madde numarasını YAZMA. "
        f"Bu atıflar kanunun güncel metniyle karşılaştırılacak."
    )
    sistem = "Sen EDM Yapı & Gayrimenkul Baş Danışmanısın. Cevabın net, otoriter ve hukuken sağlam olmalıdır."

    arastirma_ozeti = ""
    try:
        yanit = generate_text._gemini_cagri(arastirma_promptu, sistem_talimati=sistem, sicaklik=0.5)
        if yanit:
            arastirma_ozeti = yanit.strip()
    except Exception as e:
        log.warning("Araştırma analizi çağrısı başarısız: %s", e)

    if not arastirma_ozeti:
        arastirma_ozeti = konu

    simdi = datetime.now(timezone.utc).isoformat()
    konu_kodu = f"ARASTIR_{int(time.time())}"
    orijinal_url = f"edm://arastir/{konu_kodu}"
    baslik = konu.split("\n")[0][:80]

    konu_dict = {
        "kod": konu_kodu,
        "sutun": "S1",
        "kategori": "TAPU_VE_HUKUK",
        "baslik": baslik,
        "aci": f"{konu}\n\nDetaylı Analiz & Hukuki Çerçeve:\n{arastirma_ozeti}"[:3000],
        "bicim": "B1",
        "onem_puani": 10,
        "kaynak": "EDM Hukuk & Araştırma Masası",
        # Araştırma modelin hafızasından yazılıyor; atıfları güncel metne bağlanmazsa
        # eski hukuk denetimsiz geçer (önalım "2 yıl", kentsel dönüşüm "üçte iki").
        "mevzuat": mevzuat.atif_satiri(arastirma_ozeti),
    }

    veri = generate_text.konudan_uret(konu_dict)
    if not veri:
        telegram_bot.mesaj_gonder("❌ Araştırma sonucundan içerik üretilemedi.")
        return None

    manset = generate_text.manset_birlestir(veri) or baslik
    with db._baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet,
                                     eklenme_tarihi, onem_puani, kategori, manset, detay_metni,
                                     ig_caption, threads_metin, durum)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'onay_bekliyor')""",
            (
                "EDM Araştırma Masası",
                baslik,
                orijinal_url,
                arastirma_ozeti[:400],
                simdi,
                10,
                "TAPU_VE_HUKUK",
                manset,
                json.dumps(veri, ensure_ascii=False),
                veri.get("caption_instagram", ""),
                veri.get("caption_threads", ""),
            ),
        )
        haber_id = cur.lastrowid
        conn.commit()

    db_senkron.hemen_kaydet(f"db: arastirma haberi #{haber_id} olusturuldu")
    telegram_bot.haber_onayina_sun(haber_id)
    return haber_id


def dosya_icerik_uret(konu: str) -> Optional[int]:
    """
    Kullanıcının talep ettiği konuyu (örn: /dosya İmar Barışı ve Yapı Kayıt Belgesi)
    adım adım süreç, kritik dönüm noktaları ve risk tablosu içeren prestij dosya haberine dönüştürür.
    """
    log.info("Dosya haberi üretimi başlatıldı: %s", konu[:50])
    telegram_bot.mesaj_gonder(
        f"📂 <b>Özel Dosya / Süreç Analizi Başlatıldı:</b>\n"
        f"<i>\"{html.escape(konu[:120])}\"</i>\n\n"
        f"⏳ Kronolojik aşamalar, riskler ve çözüm adımları derleniyor..."
    )

    dosya_promptu = (
        f"Sen EDM Yapı & Gayrimenkul Baş Danışmanısın. Aşağıdaki konu hakkında adım adım süreç analizi yap:\n"
        f"\"{konu}\"\n\n"
        f"Bu süreci: 1. Başlangıç & Kritik Sorun, 2. Yasal / İdari Süreç Aşamaları, 3. Vatandaşın Korunması & Çözüm Yolu "
        f"başlıklarıyla net ve kapsamlı biçimde açıkla. "
        f"Dayandığın her hükmü '<kanun numarası> sayılı Kanun md. <madde>' biçiminde yaz; "
        f"emin olmadığın madde numarasını YAZMA."
    )
    sistem = "Sen EDM Yapı & Gayrimenkul Baş Danışmanısın. Detaylı, net ve rehber niteliğinde yaz."

    analiz = ""
    try:
        yanit = generate_text._gemini_cagri(dosya_promptu, sistem_talimati=sistem, sicaklik=0.5)
        if yanit:
            analiz = yanit.strip()
    except Exception as e:
        log.warning("Dosya analizi çağrısı başarısız: %s", e)

    if not analiz:
        analiz = konu

    simdi = datetime.now(timezone.utc).isoformat()
    konu_kodu = f"DOSYA_{int(time.time())}"
    orijinal_url = f"edm://dosya/{konu_kodu}"
    baslik = f"DOSYA: {konu.split(chr(10))[0][:70]}"

    konu_dict = {
        "kod": konu_kodu,
        "sutun": "S2",
        "kategori": "IMAR_VE_MEVZUAT",
        "baslik": baslik,
        "aci": f"{konu}\n\nSüreç ve Dosya Detayları:\n{analiz}"[:3000],
        "bicim": "B1",
        "onem_puani": 10,
        "kaynak": "EDM Dosya Masası",
        "mevzuat": mevzuat.atif_satiri(analiz),
    }

    veri = generate_text.konudan_uret(konu_dict)
    if not veri:
        telegram_bot.mesaj_gonder("❌ Dosya analizi içeriği üretilemedi.")
        return None

    manset = generate_text.manset_birlestir(veri) or baslik
    with db._baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet,
                                     eklenme_tarihi, onem_puani, kategori, manset, detay_metni,
                                     ig_caption, threads_metin, durum)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'onay_bekliyor')""",
            (
                "EDM Dosya Masası",
                baslik,
                orijinal_url,
                analiz[:400],
                simdi,
                10,
                "IMAR_VE_MEVZUAT",
                manset,
                json.dumps(veri, ensure_ascii=False),
                veri.get("caption_instagram", ""),
                veri.get("caption_threads", ""),
            ),
        )
        haber_id = cur.lastrowid
        conn.commit()

    db_senkron.hemen_kaydet(f"db: dosya haberi #{haber_id} olusturuldu")
    telegram_bot.haber_onayina_sun(haber_id)
    return haber_id
