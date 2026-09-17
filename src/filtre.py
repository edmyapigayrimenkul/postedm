"""
filtre.py — EDM ve Sosyal Medya Metin & Tipografi Filtresi
Instabot / Daily Brief mimarisinden uyarlanmıştır.

Görevleri:
1. Türkçe tipografi ve sayı standartlarını otomatik temizler (bin 410 -> 1.410, yüzde 25 -> %25, TL -> ₺).
2. Düz metin platformları (Instagram caption, Threads, Telegram caption) için markdown işaretlerini (**bold**, __italic__) temizler, hashtag'leri korur.
3. Gemini'nin bazen çıktıya düz metin olarak yazdığı literal '\\n' kaçış dizilerini gerçek karakterlere dönüştürür.
4. Hassas veya shadowban riski taşıyan kelimeleri yumuşatır.
"""

from __future__ import annotations

import re
def kucult(metin: str) -> str:
    """
    Türkçe İ ve I harflerini gözeterek güvenli küçük harfe dönüştürür.
    Python'un standart metin.lower() fonksiyonu 'İ' için noktalı i (U+0069 U+0307)
    üretir ve 'kira' in 'KİRA'.lower() gibi sorgular sessizce False döner.
    Bu fonksiyon bu tuzağı engelleyerek doğru eşleşme sağlar.
    """
    if not metin or not isinstance(metin, str):
        return ""
    return metin.replace("İ", "i").replace("I", "ı").lower()


def kacislari_coz(metin: str) -> str:
    """
    Modelin veya kaydın ürettiği kaçış dizilerini gerçek karaktere çevirir.
    Gemini bazen '\\n\\n' dizisini düz metin olarak döner; bu durum slaytlarda
    harf harf '\\n\\n' basılmasına yol açar. Bu fonksiyon bunu gerçek satır sonuna çevirir.
    """
    if not metin or not isinstance(metin, str):
        return ""
    if "\\" not in metin:
        return metin
    return (
        metin.replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\n")
        .replace("\\t", " ")
    )


def tipografi_temizle(metin: str) -> str:
    """
    Türkçe tipografi ve sayı standartlarını otomatik temizler:
      * 'bin 410' -> '1.410', '2 bin 410' -> '2.410', 'bin 257' -> '1.257'
      * 'yüzde 25' / 'Yüzde 2,5' -> '%25' / '%2,5'
      * '7,76 TL' -> '7,76 ₺', '90 TL' -> '90 ₺'
      * Bozuk/eksik markdown yıldızlarını ('**95-96 *') düzeltir veya öksüz tek yıldızları temizler.
    """
    if not metin or not isinstance(metin, str):
        return ""

    # Kaçış dizilerini çöz
    metin = kacislari_coz(metin)

    # 1. 4 basamaklı sayıları rakama dönüştür: '2 bin 410' -> '2.410', 'bin 410' -> '1.410'
    metin = re.sub(r"\b(\d+)\s+bin\s+(\d{3})\b", r"\1.\2", metin)
    metin = re.sub(r"\bbin\s+(\d{3})\b", r"1.\1", metin)

    # 2. Yüzde ifadeleri: 'yüzde 25' -> '%25', 'Yüzde 2,5' -> '%2,5'
    metin = re.sub(r"\b[yY]üzde\s+(\d+(?:,\d+)?)\b", r"%\1", metin)

    # 3. Türk Lirası simgesi: '7,76 TL' -> '7,76 ₺', '90 TL'yi' -> '90 ₺'yi'
    metin = re.sub(r"(\d+(?:,\d+)?)\s*TL\b", r"\1 ₺", metin)

    # 4. Kapanmamış markdown kalıpları: '**95-96 *' -> '**95-96**'
    metin = re.sub(r"\*\*([^*]+)\s*(?<!\w)\*(?!\*)", r"**\1**", metin)

    # 5. Öksüz tek yıldızları temizle (sansür yıldızlarına dokunmadan)
    metin = re.sub(r"(?<!\*)(?<!\w)\*(?!\*)", "", metin)

    return metin


def markdown_temizle(metin: str) -> str:
    """
    Metindeki markdown kalın (**metin**) veya italik (*metin* / _metin_) işaretlerini temizler.
    Instagram, Threads, Facebook gibi düz metin alanlarında ** işaretlerinin çıplak görünmesini engeller.
    Hashtag'leri (#kelime) korur.
    """
    if not metin or not isinstance(metin, str):
        return ""
    # Önce genel tipografiyi düzelt
    metin = tipografi_temizle(metin)
    # HTML etiketlerini temizle (örn: <b>, <i>, <script>)
    metin = re.sub(r"<[^>]+>", "", metin)
    # **kalın** -> kalın
    metin = re.sub(r"\*\*(.*?)\*\*", r"\1", metin)
    # __kalın__ -> kalın
    metin = re.sub(r"__(.*?)__", r"\1", metin)
    # Markdown başlık işaretleri (örn: '### Başlık' -> 'Başlık', hashtag'leri bozmaz)
    metin = re.sub(r"^#{1,6}\s+", "", metin, flags=re.MULTILINE)
    # `kod` -> kod
    metin = re.sub(r"`(.*?)`", r"\1", metin)
    # Kalan tekil çift yıldızları temizle
    metin = metin.replace("**", "").replace("__", "")
    return metin.strip()


def _yildizla(kelime: str) -> str:
    """Kelimenin ortasına doğru ilk sesliyi yıldızla değiştirir."""
    sesliler = "aeıioöuüAEIİOÖUÜ"
    for i in range(2, len(kelime)):
        if kelime[i] in sesliler:
            return kelime[:i] + "*" + kelime[i + 1:]
    orta = len(kelime) // 2
    return kelime[:orta] + "*" + kelime[orta + 1:]


def metni_yumusat(metin: str, kelimeler: List[str]) -> str:
    """Belirtilen riskli kelimeleri metin içinde yumuşatarak yıldızlar."""
    if not metin or not kelimeler:
        return metin

    for kok in kelimeler:
        kok = kok.strip()
        if not kok:
            continue

        def degistir(eslesme: re.Match) -> str:
            bulunan = eslesme.group(0)
            govde = bulunan[: len(kok)]
            ek = bulunan[len(kok):]
            return _yildizla(govde) + ek

        metin = re.sub(
            rf"\b{re.escape(kok)}\w*",
            degistir,
            metin,
            flags=re.IGNORECASE,
        )

    return metin


def hashtaglari_ele(etiketler: List[str], yasakli: List[str]) -> List[str]:
    """Kısıtlı etiketleri listeden tamamen çıkarır."""
    yasakli_kume = {y.strip().casefold().lstrip("#") for y in yasakli if y.strip()}
    return [
        e for e in etiketler
        if e.casefold().lstrip("#") not in yasakli_kume
    ]
