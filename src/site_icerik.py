"""postEDM haberini sitenin *taslak* içerik sözleşmesine dönüştürür.

Bu modül sosyal paylaşım sonucundan bağımsızdır: siteye gelen kayıt hiçbir
zaman doğrudan görünür olmaz. Son yayın kararı EDM yönetim panelindedir.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, Iterable

import requests

OIDC_HEDEF_KITLE = "edm-postedm-site"
_OIDC_JETONU: str | None = None

KATEGORILER = {
    "TAPU_VE_HUKUK": "Tapu & Hukuk",
    "KIRA_VE_TAHLIYE": "Kira & Tahliye",
    "KENTSEL_DONUSUM": "Kentsel Dönüşüm",
    "IMAR_VE_MEVZUAT": "İmar & Arsa",
    "PIYASA_VE_YATIRIM": "Piyasa & Yatırım",
}


def _https_adres(adres: Any) -> str:
    metin = str(adres or "").strip()
    return metin if re.match(r"^https://[^\s]+$", metin, re.I) else ""


def _slug(metin: str, haber_id: int) -> str:
    turkce = str.maketrans({"ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g", "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c"})
    ascii_metin = unicodedata.normalize("NFKD", metin.translate(turkce)).encode("ascii", "ignore").decode("ascii").lower()
    temiz = re.sub(r"[^a-z0-9]+", "-", ascii_metin).strip("-")
    return f"{temiz[:110].rstrip('-') or 'gayrimenkul-bulteni'}-{haber_id}"


def _json_metinleri(deger: Any) -> Iterable[str]:
    if isinstance(deger, str):
        yield deger.strip()
    elif isinstance(deger, list):
        for oge in deger:
            yield from _json_metinleri(oge)
    elif isinstance(deger, dict):
        for oge in deger.values():
            yield from _json_metinleri(oge)


def _detay(haber: Dict[str, Any]) -> Dict[str, Any]:
    try:
        deger = json.loads(str(haber.get("detay_metni") or "{}"))
        return deger if isinstance(deger, dict) else {}
    except (TypeError, ValueError):
        return {}


def haber_site_girdisi(haber: Dict[str, Any]) -> Dict[str, Any]:
    """Bir haber kaydını worker'ın kabul ettiği JSON'a çevirir.

    Kaynak veya yeterli gövde yoksa bilinçli biçimde hata verir. Sosyal medya
    caption'ı tek başına web haberi yerine geçmez.
    """
    haber_id = int(haber.get("id") or 0)
    if haber_id <= 0:
        raise ValueError("Site içeriği için geçerli haber kimliği gerekli.")
    kaynak_url = _https_adres(haber.get("orijinal_url"))
    if not kaynak_url:
        raise ValueError("Site taslağı için doğrulanabilir HTTPS kaynak bağlantısı gerekli.")

    detay = _detay(haber)
    baslik = str(haber.get("manset") or haber.get("orijinal_baslik") or "").strip()
    spot = str(detay.get("spot") or haber.get("orijinal_ozet") or "").strip()
    govde = str(haber.get("makale_metni") or "").strip()
    if len(govde) < 160:
        adaylar = [metin for metin in _json_metinleri(detay) if len(metin) >= 40]
        govde = "\n\n".join(adaylar).strip()
    if len(govde) < 160:
        raise ValueError("Site taslağı için en az 160 karakterlik kaynaklı makale metni gerekli.")
    if len(spot) < 30:
        spot = govde[:500].rsplit(" ", 1)[0]

    sosyal_urlleri: list[str] = []
    try:
        sosyal_urlleri = [adres for adres in json.loads(str(haber.get("slayt_urlleri") or "[]")) if _https_adres(adres)][:12]
    except (TypeError, ValueError):
        pass
    kapak = _https_adres(haber.get("gorsel_url"))
    kategori_kodu = str(haber.get("kategori") or "").strip()
    return {
        "disKimlik": f"postedm:haber:{haber_id}",
        "tur": "bulten",
        "slug": _slug(baslik, haber_id),
        "baslik": baslik,
        "spot": spot,
        "govde": govde,
        "kategori": KATEGORILER.get(kategori_kodu, kategori_kodu.replace("_", " ").title() or "Gayrimenkul"),
        "kaynakAdlari": [str(haber.get("kaynak") or "Kaynak")],
        "kaynakUrlleri": [kaynak_url],
        "kapakUrl": kapak,
        "sosyalUrlleri": sosyal_urlleri,
        "orijinalYayin": haber.get("yayin_tarihi") or haber.get("yayin_zamani") or datetime.now(timezone.utc).isoformat(),
    }


def _kimlik_basliklari() -> Dict[str, str]:
    ortak_anahtar = os.environ.get("EDM_SITE_API_ANAHTARI", "").strip()
    if ortak_anahtar:
        return {"X-Postedm-Anahtari": ortak_anahtar}

    global _OIDC_JETONU
    if not _OIDC_JETONU:
        adres = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "").strip()
        istek_jetonu = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "").strip()
        if not adres or not istek_jetonu:
            raise RuntimeError("EDM_SITE_API_ANAHTARI veya GitHub Actions OIDC kimliği tanımlı değil.")
        yanit = requests.get(adres, headers={"Authorization": f"Bearer {istek_jetonu}"}, params={"audience": OIDC_HEDEF_KITLE}, timeout=30)
        yanit.raise_for_status()
        _OIDC_JETONU = str(yanit.json().get("value") or "").strip()
        if not _OIDC_JETONU:
            raise RuntimeError("GitHub Actions OIDC yanıtında jeton yok.")
    return {"Authorization": f"Bearer {_OIDC_JETONU}"}


def site_taslagi_gonder(haber: Dict[str, Any]) -> Dict[str, Any]:
    """Taslağı güvenli site ucuna gönderir; Worker'ın yayına alma hakkı yoktur."""
    adres = os.environ.get("EDM_SITE_ICERIK_URL", "https://edmyapigayrimenkul.com/api/postedm/icerik").strip()
    yanit = requests.post(
        adres,
        headers={**_kimlik_basliklari(), "Content-Type": "application/json"},
        json=haber_site_girdisi(haber),
        timeout=30,
    )
    yanit.raise_for_status()
    veri = yanit.json()
    if not isinstance(veri, dict) or not veri.get("tamam") or veri.get("durum") != "taslak":
        raise RuntimeError("Site taslak ucu geçersiz yanıt döndürdü.")
    return veri
