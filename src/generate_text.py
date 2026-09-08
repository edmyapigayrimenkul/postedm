"""
generate_text.py — EDM Ses Tonuna Uygun Gemini İçerik Üretici
Haber ve İlan içeriklerini EDM Marka Paftası kurallarına göre (Net, Sakin, Yerel, Kalıcı) işler.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Dict, Optional

import requests

from . import config, db

log = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SİSTEM_TALİMATI_HABER = """Sen Silivri ve Trakya merkezli köklü bir emlak ofisi olan "EDM Yapı & Gayrimenkul"ün kurumsal içerik uzmanısın.
Sloganımız: "Yatırım Ortağınız".

MARKANIN SES TONU KURALLARI:
1. SAKİN VE NET: Kesinlikle "KAÇIRILMAYACAK FIRSAT!!!", "ŞOK GELİŞME!", "ACİL!", ünlem işaretleri veya abartılı sıfatlar kullanma.
2. YEREL VE BİLGİLİ: Rakamları, kanun/mevzuat maddelerini, imar ve piyasa etkilerini açık ve anlaşılır şekilde aktar.
3. BAŞLIK: Fraunces serif fontuna yakışacak, saygın bir gazete manşeti gibi olmalı (maksimum 8-10 kelime).
4. İÇERİK SLAYTLARI: 
   - Slayt 1 (Spot): Olayı ve piyasaya doğrudan etkisini özetleyen 2-3 sakin cümle (30-40 kelime).
   - Slayt 2 (Detay): Rakamlar, oranlar veya mevzuat detayını içeren açıklayıcı paragraf (40-60 kelime).
   - vurgu_sayi: Haberde geçen en çarpıcı veri/rakam/oran (örn: "%25", "1.2 mn", "4. kez", yoksa boş bırak).
   - vurgu_etiket: Vurgu sayısının kısa açıklaması (örn: "Yıllık kira artış tavanı", yoksa boş bırak).
5. CAPTION (Instagram & Threads):
   - Temiz paragraflar. Sonda "EDM Yapı & Gayrimenkul · Yatırım Ortağınız\n0536 343 41 97 · edmyapigayrimenkul.com" imzası.

Çıktıyı YALNIZCA JSON formatında ver:
{
  "manset": "...",
  "slayt_1_spot": "...",
  "slayt_2_detay": "...",
  "vurgu_sayi": "...",
  "vurgu_etiket": "...",
  "onem_puani": 8,
  "ig_caption": "...",
  "threads_metin": "..."
}
"""

SİSTEM_TALİMATI_ILAN = """Sen "EDM Yapı & Gayrimenkul"ün ilan editörüsün.
Portföydeki gayrimenkulü EDM kurumsal kimliğine uygun olarak tanıtacaksın.

KURALLAR:
1. "Fiyat için DM", "Arayınız" ASLA YAZILMAZ. Fiyat, metrekare, oda sayısı ve lokasyon en başta net şekilde belirtilir.
2. Şişirme, abartı ve bağırma dili yasaktır.
3. 4-5 maddelik temiz teknik özet çıkar (İmar durumu, tapu durumu, ulaşım, altyapı).
4. Sonda danışman adı, telefon (0536 343 41 97) ve edmyapigayrimenkul.com yer alır.

Çıktıyı YALNIZCA JSON formatında ver:
{
  "manset": "Silivri Akören'de 1.924 m² İmarlı Arsa & Müstakil Ev",
  "lokasyon_etiketi": "Silivri · Akören Mahallesi",
  "fiyat_etiketi": "25 mn ₺",
  "metrikler": ["1.924 m²", "2+1", "Kat Mülkiyeti"],
  "maddeler": [
    "1.924 m² konut imarlı arsa içerisinde müstakil ev",
    "Yola cepheli, elektrik ve su altyapısı hazır",
    "Kuzey Marmara Otoyolu bağlantısına kolay erişim",
    "Krediye uygun, tapusu devire hazır"
  ],
  "ig_caption": "...",
  "threads_metin": "..."
}
"""


MODELLER = ["gemini-3.5-flash", "gemini-flash-latest"]

def _gemini_cagri(prompt: str, sistem_talimati: str) -> Optional[str]:
    api_key = config.env_al("GEMINI_API_KEY")
    if not api_key:
        log.warning("GEMINI_API_KEY tanımlanmamış!")
        return None

    payload = {
        "system_instruction": {"parts": [{"text": sistem_talimati}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json",
        },
    }

    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}

    for model in MODELLER:
        url = GEMINI_API_URL.format(model=model)
        for deneme in range(2):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=30)
                if resp.status_code == 200:
                    veri = resp.json()
                    return veri["candidates"][0]["content"]["parts"][0]["text"]
                elif resp.status_code in (429, 500, 503):
                    log.warning("%s yoğun/hata [%d], bekleniyor...", model, resp.status_code)
                    time.sleep(2)
                else:
                    log.warning("%s hata [%d]: %s", model, resp.status_code, resp.text[:120])
                    break
            except Exception as e:
                log.warning("%s istek istisnası: %s", model, e)
                time.sleep(1)

    return None


def haber_metinleri_uret(haber: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Bir haber kaydından EDM üslubunda başlık, slayt metinleri ve caption üretir."""
    prompt = (
        f"KAYNAK: {haber.get('kaynak')}\n"
        f"BAŞLIK: {haber.get('orijinal_baslik')}\n"
        f"ÖZET/İÇERİK: {haber.get('orijinal_ozet')}\n\n"
        "Lütfen bu haberi EDM Yapı & Gayrimenkul standartlarında kurumsal bir sosyal medya içeriğine dönüştür."
    )

    ham_json = _gemini_cagri(prompt, SİSTEM_TALİMATI_HABER)
    if not ham_json:
        return None

    try:
        sonuc = json.loads(ham_json)
        # Veritabanını güncelle
        db.haber_guncelle(
            haber["id"],
            manset=sonuc.get("manset"),
            detay_metni=sonuc.get("slayt_2_detay"),
            ig_caption=sonuc.get("ig_caption"),
            threads_metin=sonuc.get("threads_metin"),
            onem_puani=sonuc.get("onem_puani", haber.get("onem_puani", 7)),
        )
        return sonuc
    except Exception as e:
        log.error("Gemini JSON ayrıştırma hatası: %s", e)
        return None


def ilan_metinleri_uret(ilan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Bir gayrimenkul ilanından EDM standartlarında slayt metinleri ve caption üretir."""
    prompt = (
        f"İLAN BAŞLIĞI: {ilan.get('baslik')}\n"
        f"İŞLEM: {ilan.get('islem')}\n"
        f"TİP: {ilan.get('tip')}\n"
        f"LOKASYON: {ilan.get('ilce')} / {ilan.get('mahalle')}\n"
        f"FİYAT: {ilan.get('fiyat')} {ilan.get('paraBirimi', 'TRY')}\n"
        f"M²: {ilan.get('m2')}\n"
        f"ODA: {ilan.get('oda')}\n"
        f"DANIŞMAN: {ilan.get('danisman')}\n"
    )

    ham_json = _gemini_cagri(prompt, SİSTEM_TALİMATI_ILAN)
    if not ham_json:
        return None

    try:
        return json.loads(ham_json)
    except Exception as e:
        log.error("İlan JSON ayrıştırma hatası: %s", e)
        return None
