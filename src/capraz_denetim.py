"""
capraz_denetim.py — Anlam kayması denetimi: ikinci bir model içeriği kaynakla karşılaştırır.

`dogrula.py` sayı, süre, oran, çoğunluk, madde numarası ve özel isimleri düzenli ifadeyle denetler.
Aynı kelimeleri taşıyıp anlamı değiştiren hatayı yakalayamaz: "açılabilir" → "açıldı", "dilerse" →
"zorunlu", iki ayrı kuralın tek cümlede birleşmesi (S3-024), "kiracı" ile "ev sahibi"nin yer
değiştirmesi. Bunlar için kaynak ile içeriği birlikte okuyan bir hakem gerekiyor.

KARAR: bulgu yalnızca ⚠️ uyarıdır, yayını durdurmaz.
- Hakem de model; yanlış alarm verirse doğru içeriği kapatması, yakaladığı hatadan pahalıdır.
- Onaylayan kişi uyarıyı Telegram önizlemesinin başında görür; otomatik yayında (finans) herhangi bir
  uyarı yayını durdurup onaya düşürür (`telegram_bot.finans_icerigi_hazirla_ve_yayinla`).
- Hakem çalışamazsa (kota, ağ, bozuk yanıt) denetim sessizce atlanır: ⛔ kapısı zaten ayrı çalışıyor.

YANLIŞ ALARMI AZALTMAK İÇİN iki süzgeç kodda (prompta güvenilmiyor):
1. Model her bulguda içerikten VE (desteksiz hariç) kaynaktan birebir alıntı vermek zorunda; alıntılardan
   biri metinde bulunamazsa bulgu atılır (modelin uydurduğu çelişki).
2. En çok `AZAMI_BULGU` bulgu gösterilir; üretici modelden (gemini-3.7-flash) farklı model önce denenir.

Test modunda ağ yok: `denetle(..., cagri=sahte)` ile mantık sınanır, `cagri` verilmezse [] döner.
"""

from __future__ import annotations

import hashlib
import html
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import config

log = logging.getLogger(__name__)

# Üretici zincirin başı gemini-3.7-flash; hakemin aynı modelle kendi yazdığını onaylamaması için
# farklı modelle başlar. Yedekler üretici zincirin sağlam üyeleri.
#
# Zincirde LITE MODEL YOK: 2026-10-07 denemesinde gemini-3.5-flash-lite, ana modelin yakaladığı S3-024
# birleştirmesini ve #470'teki 25 yaş istisnasını kaçırdı (0,7 sn'de boş liste döndü). Zayıf hakem
# "temiz" demekten beter: kimseyi uyarmadan güven veriyor. Hakem çalışamazsa denetim atlanır.
# Zincir kısa: çağrı başına en kötü bekleme model sayısı × 35 sn, kapı her onayda çalışıyor.
DENETCI_MODELLER = ["gemini-3.5-flash", "gemini-3.7-flash"]

AZAMI_KAYNAK = 12000       # karakter; haber metni ya da madde metni bunun ötesinde kuyruk sayılır
AZAMI_ICERIK = 6000
AZAMI_SATIR = 60
AZAMI_BULGU = 3
EN_AZ_KAYNAK = 200         # bundan kısa kaynakla karşılaştırılacak bir şey yok
EN_AZ_ALINTI = 12          # normalleştirilmiş karakter; daha kısa alıntı kanıt sayılmaz

# İçerikte anlam taşımayan teknik alanlar
_ATLANAN_ANAHTARLAR = {
    "bicim", "format_turu", "kategori_kodu", "konu_kodu", "ulke_kodu", "gorsel_url", "foto_url",
    "kaynak_url", "onem_puani", "hashtags", "ikon", "emoji",
}

# Yazarın çıkarımı olan alanlar: kaynaktan fazlasını söylemesi doğal ("sana etkisi" okuyucuya yorumdur).
# Burada yalnız kaynakla ÇELİŞKİ aranır, "kaynakta yok" denmez (gerçek denemede #509 buna takıldı).
_YORUM_ALANLARI = {"neden_onemli", "sana_etkisi", "sirada_ne_var", "uzman_notu"}

# Sistemin captionlara eklediği kapanış çağrıları ("Tapu randevusundan önce açıp bakmak için kaydedin.")
# içerik iddiası değildir; gerçek denemede #470'te "kaynakta dayanağı yok" diye işaretlendi.
_CAGRI_KOKLERI = ("kaydedin", "kaydet", "gönderin", "paylaşın", "arayın", "takip edin", "yorumlayın")

_TURLER = {
    "celiski": "kaynakla çelişiyor",
    "kip": "kip ya da koşul değişmiş",
    "birlestirme": "ayrı hükümler birleştirilmiş",
    "ozne": "özne ya da yön değişmiş",
    "desteksiz": "kaynakta dayanağı yok",
}

_SISTEM = (
    "Sen titiz bir hukuk ve haber doğrulama editörüsün. Bir içeriğin, dayandığı KAYNAK metinle "
    "aynı anlamı taşıyıp taşımadığını denetlersin. Yalnızca JSON döndürürsün."
)

_ISTEM = """KAYNAK METİN (tek doğru bu):
\"\"\"
{kaynak}
\"\"\"

İÇERİK (numaralı satırlar; sosyal medya paylaşımı olarak yayınlanacak). "(yorum)" işaretli satırlar yazarın çıkarımıdır:
{icerik}

GÖREV: İçerikte, kaynağın söylediğinden FARKLI ANLAM üreten yerleri bul. Yalnızca şu beş türü bildir:
- "celiski": içerik kaynakla çelişiyor (kaynak "olabilir" diyorken içerik "oldu" demek, evet↔hayır, var↔yok).
- "kip": kip ya da koşul değişmiş (isteğe bağlı → zorunlu, "ancak/yalnızca" şartı düşmüş, koşullu hüküm koşulsuz yazılmış, "en az" ↔ "en çok").
- "birlestirme": kaynakta ayrı olan kural, koşul, süre, kişi ya da durum tek hükümmüş gibi birleştirilmiş.
- "ozne": kim kime ne yapar karışmış (kiracı↔ev sahibi, alıcı↔satıcı, kurum↔vatandaş, hak↔yükümlülük).
- "desteksiz": kaynakta hiç geçmeyen SOMUT bir hak, yükümlülük, yaptırım, koşul ya da olgu eklenmiş.

KURALLAR:
- "(yorum)" satırlarında yalnızca kaynakla ÇELİŞKİ bildir; kaynakta olmayan çıkarım ya da genel değerlendirme için "desteksiz" bildirme.
- Yalnızca okuyucuyu yanlış bilgiye, yanlış karara ya da yanlış davranışa götürebilecek farkları bildir (hak, yükümlülük, süre, koşul, istisna, kim-kime). Sözcük düzeyinde pedantik farkları HİÇ yazma ("ciddiyet": "dusuk").
- Üslup, sadeleştirme, kısaltma, özetleme, günlük dile çevirme SORUN DEĞİLDİR. Kaynakta yazan şeyin başka sözcüklerle anlatılması sorun değildir.
- Genel çerçeveleme ("bu konuda dikkatli olun", "uzmana danışın") ve CTA/hashtag satırları sorun değildir.
- Emin değilsen bildirme. Kaynak ile içerik uyumluysa "sorunlar" boş liste olsun.
- En fazla {en_cok} bulgu; en ciddi olanlar.
- "icerik_alintisi": içerikten BİREBİR, kısa (en çok 25 kelime) alıntı. "kaynak_alintisi": kaynaktan BİREBİR, kısa alıntı ("desteksiz" için boş bırak).
- "aciklama": tek cümle, ne fark var. "ciddiyet": "yuksek" ya da "dusuk".

YALNIZCA bu JSON'u döndür:
{{"sorunlar": [{{"tur": "celiski|kip|birlestirme|ozne|desteksiz", "satir": 1, "icerik_alintisi": "...", "kaynak_alintisi": "...", "aciklama": "...", "ciddiyet": "yuksek|dusuk"}}]}}"""

# Aynı (kaynak, içerik) çifti için model bir kez sorulur; aynı süreçte kapı birden çok kez çalışabiliyor
_ONBELLEK: Dict[str, List[str]] = {}
_ONBELLEK_SINIRI = 64


def _kalin_sil(metin: str) -> str:
    return metin.replace("**", "")


def _cagri_satiri_mi(satir: str) -> bool:
    kucuk = satir.lower()
    return len(satir) <= 90 and any(k in kucuk for k in _CAGRI_KOKLERI)


def _satirlari_topla(veri: Dict[str, Any]) -> List[Tuple[str, bool]]:
    """(metin, yorum_mu) çiftleri. Yorum: yazarın çıkarımı olan alanlar (`_YORUM_ALANLARI`)."""
    from . import dogrula

    satirlar: List[Tuple[str, bool]] = []

    def topla(d: Any, yorum: bool = False) -> None:
        if isinstance(d, dict):
            for k, v in d.items():
                if k in _ATLANAN_ANAHTARLAR or k.startswith("_"):
                    continue
                if k.startswith("caption"):
                    # Açıklama metni de aynı iddiayı taşır; hashtag, iletişim ve kapanış çağrısı denetim dışı
                    for s in dogrula._caption_govdesi(v if isinstance(v, str) else "").splitlines():
                        s = s.strip()
                        if s and not _cagri_satiri_mi(s):
                            satirlar.append((re.sub(r"\s+", " ", _kalin_sil(s)), False))
                    continue
                topla(v, yorum or k in _YORUM_ALANLARI)
        elif isinstance(d, list):
            for v in d:
                topla(v, yorum)
        elif isinstance(d, str):
            metin = re.sub(r"\s+", " ", _kalin_sil(d)).strip()
            # Tek kelimelik kod/etiket ve adresler anlam taşımaz
            if len(metin) >= 12 and " " in metin and not metin.startswith(("http://", "https://")):
                satirlar.append((metin, yorum))

    topla(veri)
    # Aynı metin birden çok alanda geçebilir (manşet ve slayt başlığı); tekrarı at
    gorulen: set = set()
    tekil: List[Tuple[str, bool]] = []
    for s, y in satirlar:
        if s not in gorulen:
            gorulen.add(s)
            tekil.append((s, y))
    return tekil[:AZAMI_SATIR]


def icerik_satirlari(veri: Dict[str, Any]) -> List[str]:
    """İçeriğin okuyucuya giden cümle ve ifadeleri; teknik alanlar, kodlar, adresler ve kapanış çağrısı hariç."""
    return [s for s, _ in _satirlari_topla(veri)]


def _normal(metin: str, dipnot_sil: bool = False) -> str:
    from . import dogrula, mevzuat
    if dipnot_sil:
        metin = mevzuat._DIPNOT.sub(" ", metin or "")
    return " ".join(dogrula._sadelestir(_kalin_sil(metin or "")).split())


_UC_NOKTA = re.compile(r"\s*(?:\.{3}|…)\s*")


def _bulunur(alinti: str, metin_normal: str) -> bool:
    """Alıntı metinde geçiyor mu. Model uzun cümleyi "..." ile kısaltabiliyor: parçalar SIRAYLA aranır.
    (2026-10-08: bu yüzden gerçek bir bulgu — S2-006'daki güvence iadesi — kanıtsız sanılıp atılmıştı.)
    En az bir parça `EN_AZ_ALINTI` uzunluğunda olmalı; çok kısa parçalar tek başına kanıt sayılmaz."""
    parcalar = [_normal(p) for p in _UC_NOKTA.split(str(alinti or ""))]
    parcalar = [p for p in parcalar if p]
    if not parcalar or max(len(p) for p in parcalar) < EN_AZ_ALINTI:
        return False
    konum = 0
    for parca in parcalar:
        bulunan = metin_normal.find(parca, konum)
        if bulunan < 0:
            return False
        konum = bulunan + len(parca)
    return True


def _istem(kaynak: str, satirlar: List[Tuple[str, bool]]) -> str:
    icerik = ""
    for i, (s, yorum) in enumerate(satirlar, 1):
        parca = f"[{i}] {'(yorum) ' if yorum else ''}{s}\n"
        if len(icerik) + len(parca) > AZAMI_ICERIK:
            break
        icerik += parca
    return _ISTEM.format(kaynak=kaynak[:AZAMI_KAYNAK], icerik=icerik.strip(), en_cok=AZAMI_BULGU)


def _kes(metin: str, sinir: int) -> str:
    """Sınırı aşan metni son tam kelimede keser (kelime ortasında kesilmiş alıntı okunmuyor)."""
    if len(metin) <= sinir:
        return metin
    return metin[:sinir].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def _bulgulari_suz(sonuc: Any, icerik_normal: str, kaynak_normal: str, yorum_normal: str = "") -> List[str]:
    """Modelin bulgularını kanıt şartıyla süzer ve onay mesajına konacak uyarılara çevirir."""
    if isinstance(sonuc, list):
        sonuc = {"sorunlar": sonuc}
    if not isinstance(sonuc, dict):
        return []
    sorunlar = sonuc.get("sorunlar")
    if not isinstance(sorunlar, list):
        return []
    uyarilar: List[str] = []
    islenen: set = set()
    for s in sorunlar:
        if not isinstance(s, dict):
            continue
        tur = str(s.get("tur") or "").strip().lower()
        if tur not in _TURLER:
            continue
        icerik_a = str(s.get("icerik_alintisi") or "").strip()
        kaynak_a = str(s.get("kaynak_alintisi") or "").strip()
        aciklama = re.sub(r"\s+", " ", str(s.get("aciklama") or "")).strip()
        if str(s.get("ciddiyet") or "yuksek").strip().lower() == "dusuk":
            continue
        if not aciklama or not _bulunur(icerik_a, icerik_normal):
            log.info("Çapraz denetim bulgusu atıldı (içerik alıntısı bulunamadı): %s", icerik_a[:60])
            continue
        if tur != "desteksiz" and not _bulunur(kaynak_a, kaynak_normal):
            log.info("Çapraz denetim bulgusu atıldı (kaynak alıntısı bulunamadı): %s", kaynak_a[:60])
            continue
        if tur == "desteksiz" and yorum_normal and _bulunur(icerik_a, yorum_normal):
            continue  # yazarın çıkarımı kaynaktan fazlasını söyleyebilir; yalnız çelişki aranır
        anahtar = _normal(icerik_a)
        if anahtar in islenen:
            continue  # model aynı cümleyi birkaç türle işaretleyebiliyor; kişiye tek uyarı yeter
        islenen.add(anahtar)
        metin = f"⚠️ ANLAM KAYMASI ({_TURLER[tur]}): “{_kes(icerik_a, 140)}”"
        if tur != "desteksiz":
            metin += f" ↔ kaynakta: “{_kes(kaynak_a, 140)}”"
        metin += f". {_kes(aciklama, 240)}"
        uyarilar.append(html.escape(metin, quote=False))
        if len(uyarilar) >= AZAMI_BULGU:
            break
    return uyarilar


def _varsayilan_cagri() -> Optional[Callable[..., Optional[str]]]:
    if config.test_modu():
        return None
    from . import generate_text

    def cagri(istem: str, sistem: str) -> Optional[str]:
        return generate_text._gemini_cagri(istem, sistem, sicaklik=0.1, modeller=DENETCI_MODELLER)

    return cagri


def denetle(veri: Dict[str, Any], kaynak: str,
            cagri: Optional[Callable[[str, str], Optional[str]]] = None) -> List[str]:
    """İçeriği kaynakla karşılaştırır; anlam kayması bulgularını ⚠️ olarak döner.

    Hakem çalışamadıysa [] döner (fail-open): insan onaylı akışta hakem yüzünden içerik durmaz. Hakemin
    GERÇEKTEN çalışıp çalışmadığı önemliyse (otomatik yayın) `denetle_ayrintili` kullanılır."""
    return denetle_ayrintili(veri, kaynak, cagri)[0]


def denetle_ayrintili(veri: Dict[str, Any], kaynak: str,
                      cagri: Optional[Callable[[str, str], Optional[str]]] = None) -> Tuple[List[str], bool]:
    """(uyarılar, hakem_calisti). `hakem_calisti` yalnızca model ayrıştırılabilir bir yanıt verdiyse True.

    Neden ayrı: "bulgu yok" ile "hakem hiç çalışmadı" ikisi de [] dönüyordu. 2026-10-07'de ücretsiz katman
    kotası dolduğunda on iki sözlüğün hepsi sessizce "temiz" göründü; denetlenmemiş içeriği otomatik
    yayına almak buna dayanamaz. Kaynak yoksa ya da çok kısaysa da karşılaştıracak bir şey yoktur: False.
    `kaynak`: haberde kaynak haber metni, konuda maddenin güncel metni.
    `cagri(istem, sistem)`: ham yanıt metni ya da None; testlerde sahte verilir."""
    kaynak = (kaynak or "").strip()
    if len(kaynak) < EN_AZ_KAYNAK:
        return [], False
    satirlar = _satirlari_topla(veri)
    if not satirlar:
        return [], False
    if cagri is None:
        cagri = _varsayilan_cagri()
        if cagri is None:
            return [], False

    anahtar = hashlib.sha1((kaynak + "\n\x00\n" + "\n".join(f"{int(y)}{s}" for s, y in satirlar)).encode("utf-8")).hexdigest()
    if anahtar in _ONBELLEK:
        return list(_ONBELLEK[anahtar]), True

    try:
        ham = cagri(_istem(kaynak, satirlar), _SISTEM)
    except Exception as e:  # noqa: BLE001 — hakem yüzünden yayın akışı kırılmaz
        log.warning("Çapraz denetim çalışmadı: %s", e)
        return [], False
    if not ham:
        return [], False
    from . import generate_text
    sonuc = generate_text._json_coz(ham) if isinstance(ham, str) else ham
    if sonuc is None:
        log.warning("Çapraz denetim yanıtı çözülemedi: %s", str(ham)[:120])
        return [], False

    icerik_normal = _normal(" ".join(s for s, _ in satirlar))
    yorum_normal = _normal(" ".join(s for s, y in satirlar if y))
    kaynak_normal = _normal(kaynak, dipnot_sil=True)
    uyarilar = _bulgulari_suz(sonuc, icerik_normal, kaynak_normal, yorum_normal)
    if len(_ONBELLEK) >= _ONBELLEK_SINIRI:
        _ONBELLEK.clear()
    _ONBELLEK[anahtar] = list(uyarilar)
    if uyarilar:
        log.warning("Çapraz denetim %d anlam kayması buldu: %s", len(uyarilar), " | ".join(uyarilar))
    return uyarilar, True
