#!/usr/bin/env python3
"""
scripts/gorsel_denetim.py — Tüm Görsel Formatların Taşma, Çakışma ve Kırpılma Denetimi

NİYE VAR (2026-09-25): sözlük kartında (#243) tanımın son iki satırı alttaki
kutunun ARKASINDA kaldı, kutu üç maddenin yalnızca ikisini gösterdi. Mevcut
stres testi (stres_testi.py) yalnızca B1 carousel'e ve piksel analizine
bakıyordu; sözlük, Nedir Doğrusu, Net Cevap, Örnek Olay, haber ve kapanış
slaytları hiç denetlenmiyordu.

Yöntem piksel değil ÇİZİM KAYDI: Pillow'un metin ve kutu çizim çağrıları
dinlenir, her metnin gerçek sınır kutusu tutulur. Böylece fotoğraflı ve
degrade zeminlerde de denetim yapılabilir ve "neyin neyle çakıştığı" adıyla
raporlanır.

Denetimler (her slayt):
  TUVAL DIŞI    metin tuvalin dışına taşıyor                       → hata
  KENAR         metin kenara 36 pikselden yakın                     → hata
  ÇAKIŞMA       iki opak metin üst üste biniyor                     → hata
  KUTU KESİŞİMİ metin dolu bir kutunun kenarını kesiyor             → hata
  ÖRTÜLDÜ       metin, SONRADAN çizilen dolu bir kutunun altında kaldı → hata
                (#243: tanımın son satırları alttaki kutunun arkasındaydı)
  PUNTO         uzun gövde metni telefonda okunamayacak kadar küçük → uyarı
  GLİF YOK      karakter o fontta yok, kutu (□) olarak basılır     → hata
                (IBM Plex Sans'a geçince hook etiketindeki "●" kutuya döndü;
                taşma denetimi bunu görmez çünkü kutu da yer kaplar)
  4:5 KUTU DIŞI 9:16 çizimde metin y=285..1635 dışında              → hata
                (kullanıcı kuralı: tüm içerik 4:5 merkez kutusunda kalır)
  YÜZEN İŞARET  harfe bağlanmamış birleştirici işaret (U+0307 …)     → hata
                (yön işareti silinince noktası bir boşluğun üstünde kaldı)
Denetimler (her içerik):
  KIRPILDI      girdideki kelimeler hiçbir slaytta çizilmemiş       → hata
  ÇÖKTÜ         çizici istisna fırlattı (EksikIcerik bilinçli durdurma sayılmaz)

    python scripts/gorsel_denetim.py                 # tam paket
    python scripts/gorsel_denetim.py --format sozluk # tek format
    python scripts/gorsel_denetim.py --kaydet        # slaytları data/output/denetim altına bırakır
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import time
import traceback
import unicodedata
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim DB'sine ve .env'e dokunma

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from PIL import Image, ImageDraw  # noqa: E402

from src import make_image as mi, yeni_formatlar as yf  # noqa: E402

CIKTI = KOK / "data/output/denetim"
TUVALLER = {(1080, 1350), (1080, 1920)}
KENAR_ASGARI = 36
PUNTO_ASGARI = 24

# 9:16 KURALI (kullanıcı kuralı, Instabot STORY_GUVENLI_PAY): 9:16 çizimde TÜM
# metin 4:5 merkez kutusunun (y=285..1635) içinde kalır; kutunun dışı yalnızca
# fotoğraf ve zemindir. Böylece aynı kare akışta/ızgarada 4:5'e kırpılınca hiçbir
# şey kesilmez, tam ekranda (Story, Reels, Shorts, TikTok) üst ve alt arayüze çarpmaz.
# 2026-10-07: kural docstring'de yazıyordu ama kodda uygulanmıyordu (260 / H-250).
KUTU_UST = (1920 - 1350) // 2          # 285
KUTU_ALT = KUTU_UST + 1350             # 1635

# ---------------------------------------------------------------------------
# Çizim kaydı
# ---------------------------------------------------------------------------

_OLAYLAR: List[Dict[str, Any]] = []
_SLAYTLAR: List[Dict[str, Any]] = []
_ORJ = {}


def _alfa(fill: Any) -> int:
    if isinstance(fill, tuple) and len(fill) == 4:
        return int(fill[3])
    return 255


def _boyut(draw: ImageDraw.ImageDraw) -> Tuple[int, int]:
    try:
        return tuple(draw.im.size)  # type: ignore[return-value]
    except Exception:
        return (0, 0)


def _metin(self, xy, text, fill=None, font=None, anchor=None, *args, **kwargs):
    try:
        bbox = self.textbbox(xy, text, font=font, anchor=anchor,
                             spacing=kwargs.get("spacing", 4), stroke_width=kwargs.get("stroke_width", 0))
    except Exception:
        bbox = None
    _OLAYLAR.append({
        "tur": "metin", "sira": len(_OLAYLAR), "boyut": _boyut(self), "bbox": bbox, "metin": str(text),
        "alfa": _alfa(fill), "punto": getattr(font, "size", None), "font": str(getattr(font, "path", "")),
    })
    return _ORJ["text"](self, xy, text, fill, font, anchor, *args, **kwargs)


def _kutu_kaydi(ad: str):
    def sar(self, xy, *args, **kwargs):
        fill = kwargs.get("fill", args[1] if ad == "rounded_rectangle" and len(args) > 1 else (args[0] if args else None))
        try:
            (x0, y0), (x1, y1) = xy if isinstance(xy[0], (tuple, list)) else ((xy[0], xy[1]), (xy[2], xy[3]))
            _OLAYLAR.append({"tur": "kutu", "sira": len(_OLAYLAR), "boyut": _boyut(self), "bbox": (x0, y0, x1, y1),
                             "alfa": _alfa(fill) if fill is not None else 0})
        except Exception:
            pass
        return _ORJ[ad](self, xy, *args, **kwargs)
    return sar


def _kaydet(self, fp, *args, **kwargs):
    if self.size in TUVALLER and isinstance(fp, (str, Path)):
        _SLAYTLAR.append({"yol": str(fp), "boyut": self.size, "olaylar": list(_OLAYLAR)})
        _OLAYLAR.clear()
    return _ORJ["save"](self, fp, *args, **kwargs)


def kaydi_ac() -> None:
    if _ORJ:
        return
    _ORJ["text"] = ImageDraw.ImageDraw.text
    _ORJ["rectangle"] = ImageDraw.ImageDraw.rectangle
    _ORJ["rounded_rectangle"] = ImageDraw.ImageDraw.rounded_rectangle
    _ORJ["save"] = Image.Image.save
    ImageDraw.ImageDraw.text = _metin
    ImageDraw.ImageDraw.rectangle = _kutu_kaydi("rectangle")
    ImageDraw.ImageDraw.rounded_rectangle = _kutu_kaydi("rounded_rectangle")
    Image.Image.save = _kaydet


def kaydi_kapat() -> None:
    if not _ORJ:
        return
    ImageDraw.ImageDraw.text = _ORJ.pop("text")
    ImageDraw.ImageDraw.rectangle = _ORJ.pop("rectangle")
    ImageDraw.ImageDraw.rounded_rectangle = _ORJ.pop("rounded_rectangle")
    Image.Image.save = _ORJ.pop("save")


# ---------------------------------------------------------------------------
# Slayt analizi
# ---------------------------------------------------------------------------

def _kesisim(a, b) -> float:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    return max(0, x1 - x0) * max(0, y1 - y0)


def _alan(a) -> float:
    return max(0, a[2] - a[0]) * max(0, a[3] - a[1])


def _icinde(ic, dis, pay: int = 3) -> bool:
    return ic[0] >= dis[0] - pay and ic[1] >= dis[1] - pay and ic[2] <= dis[2] + pay and ic[3] <= dis[3] + pay


_CMAP: Dict[str, set] = {}


def eksik_glifler(metin: str, font_yolu: str) -> List[str]:
    """Metinde olup fontun karakter haritasında bulunmayan karakterler."""
    if not font_yolu or not Path(font_yolu).is_file():
        return []
    if font_yolu not in _CMAP:
        from fontTools.ttLib import TTFont
        _CMAP[font_yolu] = set(TTFont(font_yolu, lazy=True).getBestCmap())
    return sorted({c for c in metin if not c.isspace() and ord(c) not in _CMAP[font_yolu]})


def slayt_denetle(slayt: Dict[str, Any]) -> List[str]:
    W, H = slayt["boyut"]
    metinler = [o for o in slayt["olaylar"] if o["tur"] == "metin" and o["boyut"] == (W, H)
                and o["bbox"] and o["metin"].strip() and o["alfa"] >= 200]
    kutular = [o for o in slayt["olaylar"] if o["tur"] == "kutu" and o["boyut"] == (W, H) and o["alfa"] >= 200
               and 0.004 * W * H < _alan(o["bbox"]) < 0.6 * W * H]
    sorunlar: List[str] = []
    for m in metinler:
        b = m["bbox"]
        kisa = m["metin"][:40]
        if b[0] < -1 or b[1] < -1 or b[2] > W + 1 or b[3] > H + 1:
            sorunlar.append(f"TUVAL DIŞI: \"{kisa}\" {tuple(int(v) for v in b)}")
        elif b[0] < KENAR_ASGARI or b[2] > W - KENAR_ASGARI:
            sorunlar.append(f"KENAR: \"{kisa}\" kenara {int(min(b[0], W - b[2]))}px")
        # Kapanıştaki hukuki not bilinçli olarak 22px (tek satıra sığsın diye)
        if (m["punto"] and m["punto"] < PUNTO_ASGARI and "Mono" not in m["font"]
                and len(m["metin"]) > 24 and not (m["punto"] >= 22 and "bilgilendirmedir" in m["metin"])):
            sorunlar.append(f"PUNTO: \"{kisa}\" {m['punto']}px")
        yuzen = [c for c in unicodedata.normalize("NFC", m["metin"]) if unicodedata.category(c) == "Mn"]
        if yuzen:
            sorunlar.append(f"YÜZEN İŞARET: \"{kisa}\" [{', '.join(f'U+{ord(c):04X}' for c in yuzen)}]")
        if (W, H) == (1080, 1920) and (b[1] < KUTU_UST or b[3] > KUTU_ALT):
            sorunlar.append(f"4:5 KUTU DIŞI: \"{kisa}\" y={int(b[1])}..{int(b[3])} (izinli {KUTU_UST}..{KUTU_ALT})")
        eksik = eksik_glifler(m["metin"], m["font"])
        if eksik:
            kodlar = ", ".join(f"U+{ord(c):04X}" for c in eksik)
            sorunlar.append(f"GLİF YOK: \"{kisa}\" [{kodlar}] {Path(m['font']).name}")
    for i, a in enumerate(metinler):
        for c in metinler[i + 1:]:
            if a["metin"] == c["metin"]:
                continue  # gölge/difüzyon kopyası
            k = _kesisim(a["bbox"], c["bbox"])
            if k and k / max(1.0, min(_alan(a["bbox"]), _alan(c["bbox"]))) > 0.15:
                sorunlar.append(f"ÇAKIŞMA: \"{a['metin'][:30]}\" × \"{c['metin'][:30]}\"")
    for m in metinler:
        for k in kutular:
            if not _kesisim(m["bbox"], k["bbox"]):
                continue
            if k["sira"] > m["sira"]:
                # Kutu metinden SONRA çizildi: metnin kesişen kısmı artık görünmüyor
                sorunlar.append(f"ÖRTÜLDÜ: \"{m['metin'][:40]}\" sonradan çizilen kutunun altında {tuple(int(v) for v in k['bbox'])}")
            elif not _icinde(m["bbox"], k["bbox"]) and not _icinde(k["bbox"], m["bbox"]):
                sorunlar.append(f"KUTU KESİŞİMİ: \"{m['metin'][:40]}\" kutu {tuple(int(v) for v in k['bbox'])}")
    return list(dict.fromkeys(sorunlar))


def _sade(metin: str) -> str:
    metin = unicodedata.normalize("NFKC", metin).replace("İ", "i").replace("I", "ı").lower()
    return re.sub(r"[^0-9a-zçğıöşü]", "", metin)


def kirpilma_denetle(girdi_alanlari: Dict[str, str], slaytlar: List[Dict[str, Any]]) -> List[str]:
    """Girdideki her alanın kelimeleri çizilen metinde geçiyor mu (tire ile bölünme tolere edilir)."""
    cizilen = _sade(" ".join(o["metin"] for s in slaytlar for o in s["olaylar"] if o["tur"] == "metin"))
    sorunlar = []
    for ad, deger in girdi_alanlari.items():
        kelimeler = [_sade(k) for k in re.split(r"\s+", str(deger or "")) if len(_sade(k)) >= 3]
        if not kelimeler:
            continue
        eksik = [k for k in kelimeler if k not in cizilen]
        if len(eksik) > max(0, len(kelimeler) * 0.05):
            sorunlar.append(f"KIRPILDI: {ad} ({len(kelimeler) - len(eksik)}/{len(kelimeler)} kelime çizildi; ör. \"{eksik[0]}\")")
    return sorunlar


# ---------------------------------------------------------------------------
# Fikstürler — gerçekçi ve DOĞRU içerik (güncel kanun metniyle uyumlu)
# ---------------------------------------------------------------------------

ADIMLAR = {"baslik_vurgu": "ATILACAK ADIMLAR", "maddeler": [
    {"no": "01", "baslik": "Satışı noterden bildirin", "aciklama": "Önalım süresi, satışın paydaşlara noter aracılığıyla bildirilmesiyle başlar."},
    {"no": "02", "baslik": "Üç ayı takvime yazın", "aciklama": "Bildirimden itibaren üç ay içinde dava açılmazsa hak düşer."},
]}


def fikstur(format_turu: str) -> Dict[str, Any]:
    if format_turu == "sozluk":
        return {"format_turu": "sozluk", "kategori_kodu": "S3", "terim": "İFRAZ",
                "tanim_metni": "Bir parselin, imar planına ve belediye onayına uygun olarak birden fazla parsele bölünmesidir. Tarım arazisinde asgari büyüklüğün altına inilemez.",
                "puf_maddeleri": ["Belediyeden imar durumu belgesi alın.", "Tarım arazisinde asgari büyüklüğü sorgulayın.", "Yola cephe şartını kontrol edin."]}
    if format_turu == "nedir_dogrusu":
        return {"format_turu": "nedir_dogrusu", "kategori_kodu": "S1",
                "yanlis_metin": "Hisseli tapuda ortak, satıştan yıllar sonra bile hisseyi geri alabilir.",
                "dogru_metin": "Önalım hakkı, satışın bildirilmesinden itibaren üç ay ve her hâlde satıştan itibaren bir yıl geçince düşer.",
                "altin_kural": "Satıştan sonra noter bildirimi yaptırın; süre bildirimle başlar.",
                "slayt_3_cozum": copy.deepcopy(ADIMLAR)}
    if format_turu == "net_cevap":
        return {"format_turu": "net_cevap", "kategori_kodu": "S2", "soru": "Kira ödenmezse ev sahibi hemen dava açabilir mi",
                "net_cevap": "Hayır. Önce en az otuz gün süre verilir.",
                "aciklama": "Konut kiralarında ev sahibi yazılı olarak en az otuz gün süre verir; bu sürede ödeme yapılmazsa sözleşmeyi feshedebilir.",
                "tavsiye_metin": "İhtarı noter aracılığıyla gönderin.", "slayt_3_cozum": copy.deepcopy(ADIMLAR)}
    if format_turu == "vaka":
        return {"format_turu": "vaka", "kategori_kodu": "S1", "manset": "Ortağına haber vermeden hissesini sattı",
                "olay_detay": "Ayşe Hanım hisseli tarladaki payını üçüncü bir kişiye sattı, diğer paydaşlara bildirmedi.",
                "yargitay_hukmu": "Diğer paydaşlar önalım hakkını kullanarak payı alıcıdan, hâkimin belirlediği rayiç değerle alabilir.",
                "cikarilacak_ders": "Hisse satışında noter bildirimi süreyi başlatır.", "yasal_dayanak": "4721 sayılı Kanun md. 732-734",
                "slayt_3_cozum": copy.deepcopy(ADIMLAR)}
    if format_turu in ("B1", "B3"):
        veri = {"bicim": format_turu, "kategori_kodu": "TAPU_VE_HUKUK", "rozet_metni": "TAPU REHBERİ // ÖNALIM",
                "yasal_dayanak": "Türk Medeni Kanunu md. 733", "manset_parca_1": "Hisseli tapuda", "manset_vurgu": "ÖNALIM SÜRESİ",
                "manset_parca_2": "bildirimle başlar", "spot": "Satış paydaşlara noterle bildirilirse önalım hakkı üç ayda, her hâlde satıştan itibaren bir yılda düşer.",
                "slayt_2_detay": {"baslik_satir_1": "Önalımda", "baslik_vurgu": "İKİ KURAL",
                                  "kart_1": {"etiket": "YAYGIN YANLIŞ", "renk": "kirmizi", "baslik": "Süre hiç bitmez sanılır", "aciklama": "Oysa bildirim yapılmasa da satıştan itibaren bir yıl geçince hak düşer."},
                                  "kart_2": {"etiket": "DOĞRUSU", "renk": "yesil", "baslik": "Bedeli hâkim belirler", "aciklama": "Payın bedeli tapudaki rakam değil, hâkimin belirlediği rayiç değerdir."}},
                "slayt_3_cozum": copy.deepcopy(ADIMLAR),
                "slayt_4_cta": {"slogan_parca_1": "Hisseli tapuda", "slogan_vurgu": "DOĞRU ADIM", "aciklama": "Silivri ve Trakya'da tapudan imara yanınızdayız.", "kaydet_metni": "Kaydedin."}}
        if format_turu == "B3":
            veri["soru"] = "Önalım süresi ne zaman başlar?"
        return veri
    if format_turu == "B2":
        return {"bicim": "B2", "kategori_kodu": "YATIRIM_VE_PIYASA", "rozet_metni": "KARŞILAŞTIRMA", "yasal_dayanak": "",
                "manset_parca_1": "Arsa mı konut mu", "manset_vurgu": "AMACA GÖRE", "manset_parca_2": "değişir",
                "spot": "Kira geliri isteyen için konut, uzun vade için imarlı arsa öne çıkar.",
                "slayt_3_cozum": {"tip": "finansal_tablo", "baslik_ust": "İki seçenek", "baslik_vurgu": "YAN YANA", "alt_baslik": "Niteliksel karşılaştırma",
                                  "sol_kolon_baslik": "KONUT", "sag_kolon_baslik": "İMARLI ARSA",
                                  "sol_kolon_veriler": [["Gelir:", "Düzenli kira"], ["Gider:", "Aidat ve bakım"], ["Nakde dönüş:", "Görece hızlı"], ["Yönetim:", "Kiracı ilişkisi"], ["Risk:", "Boş kalma"]],
                                  "sag_kolon_veriler": [["Gelir:", "Doğrudan yok"], ["Gider:", "Çok düşük"], ["Nakde dönüş:", "Alıcı bulmak zaman alır"], ["Yönetim:", "Neredeyse yok"], ["Risk:", "İmar değişikliği"]],
                                  "stratejist_notu": "Nakit akışı gerekiyorsa konut; bekleyebiliyorsanız imarlı arsa."}}
    if format_turu == "haber":
        return {"format_turu": "dailybrief", "manset": "Selimpaşa'da plan değişikliği askıya çıktı",
                "spot": "Değişiklik otuz gün askıda kalacak; itirazlar belediyeye yazılı yapılabilir.",
                "kategori": "ARSA_VE_IMAR", "kaynak": "Silivri Belediyesi",
                "gorsel_yolu": str(KOK / "assets/backgrounds" / sorted(os.listdir(KOK / "assets/backgrounds"))[0]),
                "detay_maddeleri": [{"etiket": "NE DEĞİŞTİ", "metin": "Plan notlarında emsal değeri güncellendi.", "renk": "kirmizi"},
                                    {"etiket": "SÜRE", "metin": "Askı süresi otuz gündür.", "renk": "kirec"}],
                "uzman_notu": "İtirazı askı süresi içinde yazılı yapın."}
    raise ValueError(format_turu)


# Girdi alanları (kırpılma denetimi için) — formatın okura mutlaka ulaşması gereken metinler
ONEMLI_ALANLAR = {
    "sozluk": ["terim", "tanim_metni", "puf_maddeleri"],
    "nedir_dogrusu": ["yanlis_metin", "dogru_metin", "altin_kural", "slayt_3_cozum"],
    "net_cevap": ["soru", "net_cevap", "aciklama", "slayt_3_cozum"],
    "vaka": ["manset", "olay_detay", "yargitay_hukmu", "cikarilacak_ders", "slayt_3_cozum"],
    # slayt_2_detay'ın bölüm başlığı (baslik_satir_1/vurgu) carousel'de bilerek kullanılmıyor;
    # kartlar varsa kart_1/kart_2 yok sayılır (plan böyle çalışır)
    "B1": ["manset_parca_1", "manset_vurgu", "manset_parca_2", "spot", "slayt_2_detay.kartlar|slayt_2_detay.kart_1,slayt_2_detay.kart_2", "slayt_3_cozum.maddeler"],
    "B3": ["manset_parca_1", "manset_vurgu", "manset_parca_2", "spot", "slayt_2_detay.kartlar|slayt_2_detay.kart_1,slayt_2_detay.kart_2", "slayt_3_cozum.maddeler"],
    "B2": ["manset_parca_1", "manset_vurgu", "manset_parca_2", "spot", "slayt_3_cozum.sol_kolon_veriler", "slayt_3_cozum.sag_kolon_veriler", "slayt_3_cozum.stratejist_notu"],
    "haber": ["manset", "spot", "detay_maddeleri", "uzman_notu"],
}


def _alan_metinleri(veri: Dict[str, Any], alanlar: List[str]) -> Dict[str, str]:
    sonuc = {}

    def topla(d: Any) -> List[str]:
        if isinstance(d, str):
            return [d]
        if isinstance(d, dict):
            return [s for k, v in d.items() if k not in ("renk", "no", "tip") for s in topla(v)]
        if isinstance(d, (list, tuple)):
            return [s for v in d for s in topla(v)]
        return []

    def al(yol: str) -> Any:
        d: Any = veri
        for p in yol.split("."):
            if not isinstance(d, dict) or p not in d:
                return None
            d = d[p]
        return d

    for a in alanlar:
        for secenek in a.split("|"):       # "a|b,c": a varsa a, yoksa b ve c
            degerler = [al(y) for y in secenek.split(",")]
            if any(v is not None for v in degerler):
                sonuc[secenek] = " ".join(s for v in degerler for s in topla(v))
                break
    return sonuc


# ---------------------------------------------------------------------------
# Stres ve sabotaj vakaları
# ---------------------------------------------------------------------------

UZUN_CUMLE = ("Hisseli taşınmazda paydaşlardan birinin payını üçüncü kişiye satması hâlinde diğer paydaşlar "
              "satışın kendilerine bildirilmesinden itibaren üç ay içinde önalım hakkını kullanabilir ve bu hak "
              "her hâlde satıştan itibaren bir yıl geçince düşer; bedeli hâkim belirler.")
UZUN_KELIME = "Gayrimenkulleştirilemeyeceklerindenmişsiniz https://edmyapigayrimenkul.com/rehber/hisseli-tapu-onalim 1.250.000,00₺"


# Kapak manşeti parçası başına 18 karakterlik bütçeye sahip; "her alana 100 karakter
# ekle" vakaları manşeti ayrıca "manset_uzun" vakası dener.
MANSET_ALANLARI = ("manset_parca_1", "manset_vurgu", "manset_parca_2")


def _metinleri_donustur(veri: Any, fn: Callable[[str, str], Any], yol: str = "", manset_haric: bool = False) -> Any:
    if isinstance(veri, dict):
        return {k: (v if k in ("format_turu", "bicim", "renk", "no", "tip", "kategori_kodu", "kategori", "gorsel_yolu")
                    or (manset_haric and k in MANSET_ALANLARI)
                    else _metinleri_donustur(v, fn, f"{yol}.{k}", manset_haric)) for k, v in veri.items()}
    if isinstance(veri, list):
        return [_metinleri_donustur(v, fn, yol, manset_haric) for v in veri]
    if isinstance(veri, str):
        return fn(veri, yol)
    return veri


def vakalar(format_turu: str) -> List[Tuple[str, Dict[str, Any], str]]:
    """(ad, veri, beklenti) — beklenti: 'ciz' (hatasız çizilmeli) | 'dur' (EksikIcerik ile durmalı) | 'ciz_veya_dur'."""
    temel = fikstur(format_turu)
    v: List[Tuple[str, Dict[str, Any], str]] = [("gercekci", temel, "ciz")]
    mh = format_turu in ("B1", "B2", "B3")
    # Karşılaştırma tablosu hücreleri kısa ölçüt/değer çiftleridir; hücreye 100 karakter
    # eklenince tablonun sığmayıp üretimin durması doğrudur.
    ek_beklenti = "ciz_veya_dur" if format_turu in ("B2", "net_cevap") else "ciz"

    kisa = _metinleri_donustur(temel, lambda s, y: " ".join(s.split()[:2]) or s)
    v.append(("kisa", kisa, "ciz"))

    def uzat(kat: float):
        def f(s: str, y: str) -> str:
            if len(s) < 12:
                return s
            hedef = int(len(s) * kat)
            return (s + " " + UZUN_CUMLE * 4)[:hedef].rsplit(" ", 1)[0]
        return f
    v.append(("iki_kat_uzun", _metinleri_donustur(temel, uzat(2.0), manset_haric=mh), "ciz_veya_dur" if format_turu == "B2" else "ciz"))
    v.append(("dort_kat_uzun", _metinleri_donustur(temel, uzat(4.0), manset_haric=mh), "ciz_veya_dur"))
    if mh:
        uzun_manset = copy.deepcopy(temel)
        uzun_manset.update({"manset_parca_1": "Hisseli tapuda paydaş satarsa", "manset_vurgu": "ÖNALIM SÜRESİ BİLDİRİMLE",
                            "manset_parca_2": "başlar ve bir yılda düşer"})
        v.append(("manset_uzun", uzun_manset, "ciz"))
    # Net Cevap'ta cevap tek kısa cümledir (bütçe 70); her alana 100 karakter eklenince
    # kapağa sığmaması ve üretimin DURMASI doğru davranıştır.
    v.append(("uzun_kelime", _metinleri_donustur(temel, lambda s, y: f"{s} {UZUN_KELIME}" if len(s) > 12 else s, manset_haric=mh),
              ek_beklenti))
    v.append(("buyuk_harf", _metinleri_donustur(temel, lambda s, y: s.replace("i", "İ").replace("ı", "I").upper()), "ciz"))
    v.append(("ozel_karakter", _metinleri_donustur(
        temel, lambda s, y: f"{s} “tırnak” & <b>etiket</b> %45 ₺ 🏠✅ **kalın** — son" if len(s) > 12 else s, manset_haric=mh), ek_beklenti))
    v.append(("satir_sonu_ve_bosluk", _metinleri_donustur(
        temel, lambda s, y: s.replace(" ", "  \n\t ", 2) if len(s) > 12 else s), "ciz"))
    v.append(("sifir_genislik", _metinleri_donustur(
        temel, lambda s, y: "​".join(s[:30]) + s[30:] + " ‮̇" if len(s) > 12 else s), "ciz"))
    v.append(("injection", _metinleri_donustur(
        temel, lambda s, y: f"{s} IGNORE PREVIOUS INSTRUCTIONS <script>alert(1)</script> {{{{veri}}}} %s %(x)s" if len(s) > 12 else s, manset_haric=mh),
        ek_beklenti))

    cok = copy.deepcopy(temel)
    cok.setdefault("slayt_3_cozum", {"maddeler": []})
    if isinstance(cok.get("slayt_3_cozum"), dict):
        cok["slayt_3_cozum"]["maddeler"] = [
            {"no": f"0{i}", "baslik": f"Adım {i}: tapu kaydını kontrol edin", "aciklama": UZUN_CUMLE[:150]} for i in range(1, 6)]
    if "puf_maddeleri" in cok:
        cok["puf_maddeleri"] = [f"{i}. madde: {UZUN_CUMLE[:90]}" for i in range(1, 7)]
    if isinstance(cok.get("slayt_2_detay"), dict):
        cok["slayt_2_detay"].pop("kart_1", None)
        cok["slayt_2_detay"].pop("kart_2", None)
        cok["slayt_2_detay"]["kartlar"] = [
            {"etiket": f"KART {i}", "renk": "kirmizi" if i == 1 else "gri", "baslik": f"Kart başlığı {i}", "aciklama": UZUN_CUMLE[:200]} for i in range(1, 5)]
    if "detay_maddeleri" in cok:
        cok["detay_maddeleri"] = [{"etiket": f"MADDE {i}", "metin": UZUN_CUMLE[:160], "renk": "kirec"} for i in range(1, 7)]
    v.append(("cok_madde", cok, "ciz"))

    if format_turu == "sozluk":
        # Üretimden (#243): üç kelimelik terim + 349 karakter tanım + üç uzun madde
        uretim = copy.deepcopy(temel)
        uretim["terim"] = "DÖNER SERMAYE BEDELİ"
        uretim["tanim_metni"] = ("Tapu ve kadastro işlemlerinde alım-satım, ipotek ve tescil gibi her işlem için harçtan ayrı "
                                 "olarak tahsil edilen bedeldir. Bu ücret her yıl güncellenen il katsayılarına ve işlem "
                                 "türüne göre maktu olarak belirlenir. Yalnızca harcı hesaplamak bütçe planlaması için "
                                 "yeterli değildir; iki kalem birlikte ödenmeden devir tamamlanmaz.")
        uretim["puf_maddeleri"] = ["Döner sermaye bedeli her yıl yöresel katsayılara göre yeniden hesaplanır ve harçtan ayrı ödenir.",
                                   "Büyükşehirlerdeki işlem maliyetleri, il katsayıları nedeniyle standart tariften farklılık gösterir.",
                                   "Tapu randevusundan önce bedelin yatırılmaması, devir işleminin o gün yapılamamasına yol açar."]
        v.append(("uretim_243", uretim, "ciz"))
        v.append(("uzun_terim", {**copy.deepcopy(temel), "terim": "KAZANDIRICI ZAMANAŞIMIYLA TAPU TESCİLİ"}, "ciz"))

    bos = {k: val for k, val in temel.items() if k in ("format_turu", "bicim", "kategori_kodu", "kategori")}
    v.append(("tamamen_bos", bos, "dur"))

    bozuk = _metinleri_donustur(temel, lambda s, y: 12345 if y.endswith("altin_kural") or y.endswith("cikarilacak_ders") else s)
    for alan in ("puf_maddeleri",):
        if alan in bozuk:
            bozuk[alan] = "tek bir metin, liste değil"
    if isinstance(bozuk.get("slayt_3_cozum"), dict):
        bozuk["slayt_3_cozum"]["maddeler"] = ["düz metin adım", None, 42, {"baslik": None, "aciklama": ["liste"]}]
    v.append(("bozuk_tip", bozuk, "ciz_veya_dur"))
    return v


# ---------------------------------------------------------------------------
# Çalıştırıcı
# ---------------------------------------------------------------------------

def _ciz(format_turu: str, veri: Dict[str, Any], dizin: Path, onek: str, olcu: str) -> List[Path]:
    if format_turu in ("sozluk", "nedir_dogrusu", "net_cevap", "vaka"):
        return yf.slaytlari_uret(veri, cikti_dizini=dizin, cikti_onek=onek, olcu=olcu)
    if format_turu == "haber":
        return mi.haber_dailybrief_slaytlari_uret(haber=veri, cikti_dizini=dizin, cikti_onek=onek, olcu=olcu,
                                                  foto_yolu=veri.get("gorsel_yolu"))
    return mi.otorite_gonderi_slaytlari_uret(veri, cikti_onek=f"denetim/{onek}", olcu=olcu)


FORMATLAR = {
    # Dört format da 9:16'da Reels/Story olarak yayına gidiyor; yalnız 4:5 sınanıyordu
    "sozluk": ["besleme", "story"], "nedir_dogrusu": ["besleme", "story"],
    "net_cevap": ["besleme", "story"], "vaka": ["besleme", "story"],
    "B1": ["besleme", "story"], "B2": ["besleme", "story"], "B3": ["besleme", "story"], "haber": ["besleme", "story"],
}


def denetle(format_filtre: Optional[str] = None, kaydet: bool = False, sessiz: bool = False,
            vaka_filtre: Optional[set] = None, olcu_filtre: Optional[set] = None) -> Dict[str, Any]:
    kaydi_ac()
    dizin = CIKTI
    dizin.mkdir(parents=True, exist_ok=True)
    rapor: Dict[str, Any] = {"vakalar": [], "hata": 0, "uyari": 0}
    try:
        for fmt, olculer in FORMATLAR.items():
            if format_filtre and fmt != format_filtre:
                continue
            for olcu in olculer:
                if olcu_filtre and olcu not in olcu_filtre:
                    continue
                for ad, veri, beklenti in vakalar(fmt):
                    if vaka_filtre and ad not in vaka_filtre:
                        continue
                    _OLAYLAR.clear()
                    _SLAYTLAR.clear()
                    onek = f"{fmt}_{olcu}_{ad}"
                    kayit = {"format": fmt, "olcu": olcu, "vaka": ad, "sorunlar": [], "slayt": 0, "sure": 0.0}
                    t0 = time.time()
                    tamamlandi = False
                    try:
                        yollar = _ciz(fmt, copy.deepcopy(veri), dizin, onek, olcu)
                        kayit["slayt"] = len(yollar)
                        tamamlandi = True
                        if beklenti == "dur":
                            kayit["sorunlar"].append("DURMADI: boş içerik çizildi (koddaki yedek metin olabilir)")
                    except yf.EksikIcerik as e:
                        if beklenti == "ciz":
                            kayit["sorunlar"].append(f"GEREKSİZ DURMA: {e}")
                    except Exception as e:  # çökme
                        kayit["sorunlar"].append(f"ÇÖKTÜ: {type(e).__name__}: {e}")
                        kayit["iz"] = traceback.format_exc(limit=4)
                    kayit["sure"] = round(time.time() - t0, 2)
                    for s in _SLAYTLAR:
                        for sorun in slayt_denetle(s):
                            kayit["sorunlar"].append(f"[{Path(s['yol']).name}] {sorun}")
                    if tamamlandi and _SLAYTLAR and beklenti != "dur" and ad in ("gercekci", "iki_kat_uzun", "uzun_kelime", "cok_madde", "buyuk_harf", "uretim_243", "uzun_terim", "manset_uzun"):
                        kayit["sorunlar"].extend(kirpilma_denetle(_alan_metinleri(veri, ONEMLI_ALANLAR.get(fmt, [])), _SLAYTLAR))
                    if not kaydet:
                        for s in _SLAYTLAR:
                            Path(s["yol"]).unlink(missing_ok=True)
                    hatalar = [x for x in kayit["sorunlar"] if "PUNTO:" not in x]
                    rapor["hata"] += len(hatalar)
                    rapor["uyari"] += len(kayit["sorunlar"]) - len(hatalar)
                    rapor["vakalar"].append(kayit)
                    if not sessiz:
                        durum = "✓" if not kayit["sorunlar"] else ("⚠" if not hatalar else "✗")
                        print(f"{durum} {fmt:14} {olcu:8} {ad:22} {kayit['slayt']} slayt {kayit['sure']:.1f}s"
                              + (f"  ({len(kayit['sorunlar'])} sorun)" if kayit["sorunlar"] else ""))
                        for x in kayit["sorunlar"][:6]:
                            print(f"      · {x}")
                        if len(kayit["sorunlar"]) > 6:
                            print(f"      · … {len(kayit['sorunlar']) - 6} sorun daha")
    finally:
        kaydi_kapat()
    return rapor


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", choices=sorted(FORMATLAR))
    ap.add_argument("--kaydet", action="store_true", help="Slaytları data/output/denetim altına bırak")
    ap.add_argument("--json", help="Raporu bu dosyaya yaz")
    args = ap.parse_args()
    rapor = denetle(args.format, kaydet=args.kaydet)
    print(f"\nToplam: {len(rapor['vakalar'])} vaka · {rapor['hata']} hata · {rapor['uyari']} uyarı")
    if args.json:
        Path(args.json).write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if rapor["hata"] else 0


if __name__ == "__main__":
    sys.exit(main())
