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

from . import config, db, db_senkron, fetch_article, generate_text, telegram_bot

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
