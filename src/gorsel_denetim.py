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
from typing import Any, Dict, List, Optional

import requests
from PIL import Image

log = logging.getLogger(__name__)

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
    """Denenecek Gemini anahtarları."""
    anahtarlar = []
    for ad in ("GEMINI_API_KEY", "GEMINI_IMAGE_API_KEY", "GOOGLE_API_KEY"):
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
    model = g.get("model", "gemini-2.5-flash")
    zaman_asimi = g.get("zaman_asimi", 60)

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

    for anahtar in anahtarlar:
        try:
            cevap = requests.post(
                UC_NOKTA.format(model=model),
                headers={"x-goog-api-key": anahtar},
                json=govde,
                timeout=zaman_asimi,
            )
        except requests.RequestException as e:
            log.warning("görsel denetimi ağ hatası: %s", e)
            continue
        if cevap.status_code == 200:
            try:
                ham = cevap.json()["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(ham)
            except Exception as e:
                log.warning("görsel denetim cevabı çözülemedi: %s", e)
                return None
        if cevap.status_code == 429:
            log.info("görsel denetimi kota doldu, sonraki anahtar deneniyor")
            continue
        log.warning("görsel denetimi HTTP %s: %s", cevap.status_code, cevap.text[:160])
        return None
    return None
