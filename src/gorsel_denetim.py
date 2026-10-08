"""
gorsel_denetim.py — Yayına çıkacak fotoğrafın İÇİNE bakar (Gemini Vision Denetimi).

Bu modül seçilen veya indirilen görselin içeriği (haber, gayrimenkul, arsa, imar,
hukuk vb.) gerçekten anlatıp anlatmadığını, konu ve bağlamla çelişip çelişmediğini
Gemini Vision çok modlu modeliyle denetler.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests
from PIL import Image

from . import config

log = logging.getLogger(__name__)

# Fotoğrafa bakan model de kota/yoğunluk yüzünden düşebiliyor (2026-10-07: gemini-3.5-flash 429,
# 3.7-flash ve flash-latest zaman aşımı). Tek modele bağlı denetim sessizce hiç çalışmıyordu; zincir
# ve toplam süre sınırı var: kapak fotoğrafı yüzünden üretim dakikalarca beklemez.
MODELLER = ["gemini-3.5-flash", "gemini-3.7-flash"]
ZAMAN_ASIMI = 25
AZAMI_TOPLAM_SURE = 45

UC_NOKTA = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/{model}:generateContent"
)

AZAMI_KENAR = 512

CEVAP_SEMASI = {
    "type": "object",
    "properties": {
        "fotografta_ne_var": {"type": "string"},
        "konuyu_gosteriyor_mu": {"type": "boolean"},
        "baglam_uyuyor_mu": {"type": "boolean"},
        "sebep": {"type": "string"},
    },
    "required": [
        "fotografta_ne_var",
        "konuyu_gosteriyor_mu",
        "baglam_uyuyor_mu",
        "sebep",
    ],
}

ISTEM = """Sen bir haber ve gayrimenkul editoryal ekibinin FOTO EDİTÖRÜSÜN. Bu fotoğrafın bu içerikte/haberde \
kullanılıp kullanılamayacağına karar vereceksin.

İÇERİK BAŞLIĞI / KONUSU: {baslik}
FOTOĞRAFTA GÖRÜNMESİ BEKLENEN: {konu}
GEREKLİ GÜNCEL BAĞLAM: {baglam}

Sırayla cevapla:

1) fotografta_ne_var: Fotoğrafta gerçekten NE gördüğünü tarif et. Mekânı, nesneleri, yapıları veya kişileri nesnel olarak yaz. Tahmin etme, GÖRDÜĞÜNÜ yaz.

2) konuyu_gosteriyor_mu: Fotoğraf "görünmesi beklenen" şeyi gösteriyor mu?
   ⚠️ Temsili fotoğraf da GEÇERLİDİR: gayrimenkul, arsa, konut, şantiye, tapu, imar, mahkeme, ekonomi veya ilgili temsili görseller true'dur. Yalnızca fotoğraf tamamen alakasız bir şeyi (ör. alakasız magazin, kedi/köpek, soyut çizim vb.) gösteriyorsa false ver.

3) baglam_uyuyor_mu: "Gerekli güncel bağlam" boşsa her zaman true ver.
   Doluysa fotoğraf o bağlama uyuyor mu? Bağlamla ÇELİŞEN bir şey görmüyorsan true ver — emin olamamak çelişki değildir.

4) sebep: Kararını tek kısa cümleyle açıkla."""


def _anahtarlar() -> List[str]:
    """Denenecek Gemini anahtarları. Test modunda ağ yok: boş döner (testler bunu yamalar)."""
    if config.test_modu():
        return []
    anahtarlar = []
    for ad in ("GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_YEDEK", "GEMINI_API_KEY_YEDEK2",
               "GEMINI_IMAGE_API_KEY", "GOOGLE_API_KEY"):
        deger = (os.getenv(ad) or "").strip()
        if deger and deger not in anahtarlar:
            anahtarlar.append(deger)
    return anahtarlar


def _kucult(foto: Image.Image) -> bytes:
    """Fotoğrafı JPEG bayta çevirir, uzun kenarı AZAMI_KENAR'a indirir."""
    kopya = foto.convert("RGB")
    if max(kopya.size) > AZAMI_KENAR:
        oran = AZAMI_KENAR / max(kopya.size)
        kopya = kopya.resize(
            (max(1, int(kopya.width * oran)), max(1, int(kopya.height * oran))),
            Image.LANCZOS,
        )
    tampon = io.BytesIO()
    kopya.save(tampon, "JPEG", quality=80)
    return tampon.getvalue()


def gorseli_denetle(
    foto: Image.Image,
    baslik: str,
    konu: str = "",
    baglam: str = "",
    ayarlar: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Fotoğrafın içeriğe uygunluğunu Gemini Vision'a sorar.

    Döner: şema sözlüğü, ya da denetim YAPILAMADIYSA None.
    ⚠️ None ile `konuyu_gosteriyor_mu=False` AYNI ŞEY DEĞİL. None 'soramadık'
    demektir (kota, ağ, anahtar yok) ve o durumda içerik akışını tıkamamak için
    fotoğraf kabul edilir.
    """
    anahtarlar = _anahtarlar()
    if not anahtarlar:
        log.warning("Gemini anahtarı yok, görsel denetimi atlanıyor")
        return None

    g = (ayarlar or {}).get("gemini", {}) or {}
    modeller = [g["model"]] if g.get("model") else list(MODELLER)
    zaman_asimi = g.get("zaman_asimi", ZAMAN_ASIMI)

    try:
        veri = base64.b64encode(_kucult(foto)).decode("ascii")
    except Exception as e:
        log.warning("görsel denetim için küçültülemedi: %s", e)
        return None

    govde = {
        "contents": [
            {
                "parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": veri}},
                    {
                        "text": ISTEM.format(
                            baslik=baslik or "(yok)",
                            konu=konu or "(belirtilmemiş)",
                            baglam=baglam or "",
                        )
                    },
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": CEVAP_SEMASI,
            "temperature": 0.1,
        },
    }

    baslangic = time.monotonic()
    for model in modeller:
        for anahtar in anahtarlar:
            if time.monotonic() - baslangic > AZAMI_TOPLAM_SURE:
                log.warning("görsel denetimi süre sınırını aştı, atlanıyor")
                return None
            try:
                cevap = requests.post(
                    UC_NOKTA.format(model=model),
                    headers={"x-goog-api-key": anahtar},
                    json=govde,
                    timeout=zaman_asimi,
                )
            except requests.RequestException as e:
                log.warning("görsel denetimi ağ hatası (%s): %s", model, e)
                continue
            if cevap.status_code == 200:
                try:
                    ham = cevap.json()["candidates"][0]["content"]["parts"][0]["text"]
                    return json.loads(ham)
                except Exception as e:
                    log.warning("görsel denetim cevabı çözülemedi (%s): %s", model, e)
                    continue  # bozuk yanıt modele özgü olabilir; sıradaki model
            # 429 kota, 5xx yoğunluk, 404 model yok, 400 modelin desteklemediği alan: sıradaki model/anahtar
            log.info("görsel denetimi %s HTTP %s: %s", model, cevap.status_code, cevap.text[:120])
    return None
