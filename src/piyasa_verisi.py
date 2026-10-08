"""
piyasa_verisi.py — Emlakjet bölge ortalamaları: S4 ("Rakam & Bölge") içeriğinin rakam kaynağı.

NİYE (2026-10-08): S4 konularının üçü (kira çarpanı, mahalle fiyatları, arsa-daire karşılaştırması) rakam
istiyordu ama doğrulanmış kaynak yoktu; kaynaksız rakam yayınlanmadığı için hepsi engelliydi. Sahibinden ve
Hepsiemlak sunucudan 403 verir (CLAUDE.md "kapanmış konular"). Emlakjet'in bölge sayfaları ise ortalama m²
fiyatı, kira, getiri ve mahalle kırılımını sayfada hazır sunuyor ve robots.txt `*` için serbest.

Rakamları Emlakjet değil Endeksa hesaplıyor (Emlakjet'in "Verilerimiz ve Metodolojimiz" sayfası: "Tüm
hesaplamalar ve analizler Endeksa tarafından yapılır"); ilan, danışmanların bildirdiği kapanış değerleri ve iş
ortaklarından alınan satış değerleri harmanlanıyor. Yani bu GERÇEKLEŞEN TAPU BEDELİ DEĞİL, tahmini bölge
ortalamasıdır; içerikte her zaman böyle anılır (bkz. `NITELIK`). Sayfanın kendi uyarısı da aynı: "Resmi
değerleme raporu niteliği taşımaz, yatırım tavsiyesi değildir."

Ayrıştırma neden bu kadar savunmacı: sayfa Next.js; veri `self.__next_f.push` akış metninde ve JSON-LD'de.
Biçim değişirse yanlış rakam yazmaktansa HİÇ rakam yazılmalı. Bu yüzden her alan makul aralığa karşı sınanır,
JSON-LD ile kart çapraz denetlenir, sayfadaki getiri/geri dönüş kendi kira ve fiyatından yeniden hesaplanır.
Doğrulanamayan sayfa kaydedilmez; veri bayatlarsa (`AZAMI_YAS_GUN`) ona bağlı konular durur.

Düşük örneklemli mahalle satırları (ör. tek ilanlı mahallede m² fiyatı 168.988 ₺ ya da arsada %190 artış)
yayına girmez: mahalle kırılımı yalnız satılık dairede ve `MAHALLE_ASGARI_ILAN` ve üzeri ilanda kullanılır.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from . import db

log = logging.getLogger(__name__)

KAYNAK = "emlakjet"
KAYNAK_ADI = "Emlakjet bölge verileri (hesaplamalar Endeksa'ya aittir)"
TABAN = "https://www.emlakjet.com"
# Kim olduğumuzu söyleriz: ayda birkaç istek, gizlenecek bir şey yok
KULLANICI_AJANI = "EDM-Yapi-PiyasaVerisi/1.0 (+https://edmyapigayrimenkul.com; aylik, bolge basina tek istek)"
ISTEK_ARASI_SN = 2.5
ZAMAN_ASIMI_SN = 25
AZAMI_YAS_GUN = 40            # aylık toplama + pay; daha eskisi içerikte kullanılmaz
MAHALLE_ASGARI_ILAN = 10      # bundan az ilanlı mahallenin ortalaması birkaç ilana bağlıdır: yayınlanmaz
ILCE_ASGARI_ILAN = 15         # ilçe ortalaması için alt sınır; altındaki sayfa kaydedilmez
TR = timezone(timedelta(hours=3))

NITELIK = (
    "Endeksa'nın web ilanları ile danışman ve iş ortağı satış bildirimlerinden hesapladığı TAHMİNİ bölge "
    "ortalamalarıdır; gerçekleşen tapu bedeli ya da resmî değerleme değildir."
)

# (tür, bölge). Önce asıl hedef Silivri, sonra karşılaştırma bölgeleri.
HEDEFLER: Tuple[Tuple[str, str], ...] = (
    ("satilik-daire", "istanbul-silivri"),
    ("satilik-arsa", "istanbul-silivri"),
    ("satilik-tarla", "istanbul-silivri"),
    ("satilik-daire", "istanbul-catalca"),
    ("satilik-daire", "istanbul-buyukcekmece"),
    ("satilik-daire", "tekirdag-corlu"),
)

# Ölçülen ortalamanın makul sınırları; bunun dışı veri değil ayrıştırma hatasıdır (birim/sütun kayması).
M2_FIYAT_ARALIGI = {
    "satilik-daire": (5_000, 400_000),
    "satilik-arsa": (200, 500_000),
    "satilik-tarla": (20, 150_000),
}
# Ortalama toplam fiyat ÷ ortalama m² fiyatı = ima edilen ortalama alan (m²)
ALAN_ARALIGI = {
    "satilik-daire": (30, 500),
    "satilik-arsa": (50, 20_000),
    "satilik-tarla": (200, 250_000),
}
M2_KIRA_ARALIGI = (30, 5_000)
DEGISIM_ARALIGI = (-0.5, 2.0)     # yıllık değişim oranı: -%50 ... +%200
GETIRI_SAPMASI = 0.3              # sayfadaki getiri ile kendi hesabımız arasındaki en çok fark (yüzde puanı)

AYLAR = ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık")


class SayfaHatasi(ValueError):
    """Sayfa alınamadı ya da beklenen veri bulunamadı/doğrulanamadı: o ölçüm kaydedilmez."""


class ErisimKapali(SayfaHatasi):
    """403/429: site bizi geri çeviriyor. Zorlanmaz; kalan sayfalar da denenmez."""


# ---------------------------------------------------------------------------
# Biçimleme (Türkçe)
# ---------------------------------------------------------------------------

def _ondalikli(deger: float, basamak: int) -> str:
    metin = f"{deger:,.{basamak}f}"
    return metin.replace(",", "§").replace(".", ",").replace("§", ".")


def tl(deger: float, basamak: int = 0) -> str:
    """51094 → '51.094'; 290.39 (basamak=2) → '290,39'."""
    return _ondalikli(deger, basamak)


def yuzde(oran: float, basamak: int = 1) -> str:
    """0.3162 → '%31,6' (oran, 1 = %100)."""
    return "%" + _ondalikli(oran * 100, basamak)


def tarih_yazisi(gun: str) -> str:
    """'2026-10-08' → '8 Ekim 2026'."""
    d = date.fromisoformat(gun)
    return f"{d.day} {AYLAR[d.month - 1]} {d.year}"


def _tr_bugun() -> str:
    return datetime.now(timezone.utc).astimezone(TR).date().isoformat()


# ---------------------------------------------------------------------------
# Ayrıştırma
# ---------------------------------------------------------------------------

_PUSH = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')
_KART = re.compile(
    r'\{"label":"(?P<etiket>Ort\.[^"]+)","amount":(?P<tutar>[\d.]+),"type":"\w+"'
    r'(?:,"annualChangeRatio":(?P<oran>-?[\d.]+))?\}'
)
_MAHALLE_ISARETI = '"className":"group listing-subregion-pill"'
_MAHALLE_YOLU = re.compile(r'"href":"(?P<yol>/[^"]+)"')
# Tutar nesnesi bir bileşen çağrısının argümanıdır (`["$","$Ld1",null,{"amount":…}]`). Önek şart: satırın href'i ile
# tutarı arasına başka bir akış satırı girebiliyor ve onun içinde başka `{"amount":…}` nesneleri geçebilir.
_MAHALLE_DEGERI = re.compile(
    r'\["\$","\$L[0-9a-f]+",null,\{"amount":(?P<tutar>[\d.]+)(?:,"annualChangeRatio":(?P<oran>-?[\d.]+))?\}'
)
_BOLGE_KAYDI = re.compile(r'\{"id":"\d+","name":"(?P<ad>[^"]+)","slug":"(?P<slug>[a-z0-9-]+)","count":(?P<adet>\d+)\}')
_MAHALLE_BASLIGI = re.compile(r'"children":"(?P<adet>\d+) bölge için ortalama m² fiyatları"')
_KART_ETIKETLERI = {
    "Ort. m² Fiyatı": "m2_fiyat",
    "Ort. Fiyat": "ort_fiyat",
    "Ort. m² Kirası": "m2_kira",
    "Ort. Kira": "ort_kira",
}


def akis_metni(html: str) -> str:
    """Sayfadaki Next.js akış parçalarını (`self.__next_f.push`) kaçışlarından arındırıp birleştirir."""
    parcalar: List[str] = []
    for m in _PUSH.finditer(html):
        try:
            parcalar.append(json.loads('"' + m.group(1) + '"'))
        except ValueError:
            continue  # bozuk bir parça diğerlerini götürmesin; eksik veri aşağıda yakalanır
    return "".join(parcalar)


def _json_ld(html: str, kimlik: str) -> Optional[Dict[str, Any]]:
    m = re.search(r'<script id="%s" type="application/ld\+json">(.*?)</script>' % re.escape(kimlik), html, re.S)
    if not m:
        return None
    try:
        veri = json.loads(m.group(1))
    except ValueError:
        return None
    return veri if isinstance(veri, dict) else None


def _sayi(metin: str) -> Optional[float]:
    try:
        return float(metin)
    except (TypeError, ValueError):
        return None


def _binlik_sayi(metin: str) -> Optional[int]:
    """'1.443' → 1443 (Türkçe binlik noktası)."""
    try:
        return int(metin.replace(".", ""))
    except ValueError:
        return None


def _kartlar(akis: str) -> Dict[str, Dict[str, Optional[float]]]:
    """etiket → {tutar, oran}. Aynı etiket farklı değerlerle iki kez geçerse belirsizdir, hata."""
    bulunan: Dict[str, Dict[str, Optional[float]]] = {}
    for m in _KART.finditer(akis):
        alan = _KART_ETIKETLERI.get(m["etiket"])
        if not alan:
            continue
        kayit = {"tutar": _sayi(m["tutar"]), "oran": _sayi(m["oran"]) if m["oran"] else None}
        if alan in bulunan and bulunan[alan] != kayit:
            raise SayfaHatasi(f"'{m['etiket']}' kartı farklı değerlerle birden çok kez geçiyor")
        bulunan[alan] = kayit
    return bulunan


def _kart_degeri(akis: str, etiket: str) -> Optional[str]:
    """'Geri dönüş süresi' / 'Getiri' kutusunun değeri ('15 yıl', '%6.82')."""
    m = re.search(
        r'"children":"%s"\}\],\["\$","span",null,\{"className":"[^"]*","children":"(?P<deger>[^"]+)"' % re.escape(etiket),
        akis,
    )
    return m["deger"] if m else None


def _getiri_yuzdesi(metin: Optional[str]) -> Optional[float]:
    if not metin:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)", metin)
    return float(m.group(1).replace(",", ".")) if m else None


def _mahalleler(akis: str, tur: str, bolge: str) -> List[Dict[str, Any]]:
    """Sayfadaki mahalle satırları: ad, ₺/m², yıllık değişim, ilan sayısı.

    Satırlar akışta bitişik durmaz ve bir satırın değeri başka bir akış satırıyla bölünebilir; bu yüzden her
    satır işaretçiden bir sonrakine kadar taranır. İlan sayısı sayfanın süzgeç kayıtlarından eşlenir; eşleşme
    yoksa ya da belirsizse (aynı mahalle farklı sayılarla) `ilan_sayisi` None kalır ve satır yayına girmez.
    """
    sayilar: Dict[str, List[Tuple[str, int]]] = {}
    for m in _BOLGE_KAYDI.finditer(akis):
        sayilar.setdefault(m["slug"], []).append((m["ad"], int(m["adet"])))

    sonuc: List[Dict[str, Any]] = []
    gorulen = set()
    for parca in akis.split(_MAHALLE_ISARETI)[1:]:
        yol = _MAHALLE_YOLU.search(parca[:4000])
        deger = _MAHALLE_DEGERI.search(parca[:60000])
        if not yol or not deger:
            continue
        parcalar = yol["yol"].strip("/").split("/")
        if len(parcalar) != 2 or parcalar[0] != tur or not parcalar[1].startswith(bolge + "-"):
            continue                       # başka tür ya da başka bölgenin satırı
        slug = parcalar[1]
        if slug in gorulen:
            continue
        gorulen.add(slug)
        tutar = _sayi(deger["tutar"])
        if not tutar or tutar <= 0:
            continue
        kayitlar = sayilar.get(slug) or []
        ad = kayitlar[0][0] if kayitlar else None
        adet = kayitlar[0][1] if len({a for _, a in kayitlar}) == 1 else None
        sonuc.append({
            "bolge": slug,
            "bolge_adi": ad,
            "m2_fiyat": tutar,
            "m2_degisim": _sayi(deger["oran"]) if deger["oran"] else None,
            "ilan_sayisi": adet,
        })
    return sonuc


def sayfa_coz(html: str, tur: str, bolge: str) -> Dict[str, Any]:
    """Bir bölge sayfasından ölçümü çıkarır. Temel veri yoksa ya da çelişiyorsa `SayfaHatasi`."""
    akis = akis_metni(html)
    yer = _json_ld(html, "listing-place") or {}
    koleksiyon = _json_ld(html, "listing-collection-schema") or {}

    ld_fiyat = None
    for ozellik in yer.get("additionalProperty") or []:
        if isinstance(ozellik, dict) and ozellik.get("name") == "averagePricePerSquareMeter":
            ld_fiyat = _sayi(str(ozellik.get("value")))
    kartlar = _kartlar(akis)
    kart_fiyat = (kartlar.get("m2_fiyat") or {}).get("tutar")

    if ld_fiyat is None and kart_fiyat is None:
        raise SayfaHatasi("ortalama m² fiyatı ne JSON-LD'de ne kartta bulundu (sayfa biçimi değişmiş olabilir)")
    if ld_fiyat is not None and kart_fiyat is not None and abs(ld_fiyat - kart_fiyat) > 0.01 * kart_fiyat:
        raise SayfaHatasi(f"JSON-LD ({ld_fiyat:g}) ile kart ({kart_fiyat:g}) m² fiyatı çelişiyor")
    m2_fiyat = kart_fiyat if kart_fiyat is not None else ld_fiyat

    ilan_sayisi = None
    m = re.search(r"(\d[\d.]*) adet", str(koleksiyon.get("description") or ""))
    if m:
        ilan_sayisi = _binlik_sayi(m.group(1))

    geri_donus = _kart_degeri(akis, "Geri dönüş süresi")
    geri_donus_yil = None
    if geri_donus:
        g = re.search(r"(\d+)", geri_donus)
        geri_donus_yil = int(g.group(1)) if g else None

    olcum: Dict[str, Any] = {
        "kaynak": KAYNAK,
        "tur": tur,
        "bolge": bolge,
        "bolge_adi": str(yer.get("name") or "").strip() or None,
        "ust_bolge": None,
        "m2_fiyat": m2_fiyat,
        "m2_degisim": (kartlar.get("m2_fiyat") or {}).get("oran"),
        "ort_fiyat": (kartlar.get("ort_fiyat") or {}).get("tutar"),
        "m2_kira": (kartlar.get("m2_kira") or {}).get("tutar"),
        "m2_kira_degisim": (kartlar.get("m2_kira") or {}).get("oran"),
        "ort_kira": (kartlar.get("ort_kira") or {}).get("tutar"),
        "getiri": _getiri_yuzdesi(_kart_degeri(akis, "Getiri")),
        "geri_donus_yil": geri_donus_yil,
        "ilan_sayisi": ilan_sayisi,
        "mahalleler": _mahalleler(akis, tur, bolge),
    }
    baslik = _MAHALLE_BASLIGI.search(akis)
    olcum["mahalle_basligi"] = int(baslik["adet"]) if baslik else None
    return olcum


def olcum_sorunlari(o: Dict[str, Any]) -> List[str]:
    """Kaydetmeden önce ölçümün makullüğü. Boş liste = kaydedilebilir."""
    sorunlar: List[str] = []
    tur = o["tur"]
    alt, ust = M2_FIYAT_ARALIGI.get(tur, (1, 10 ** 7))
    fiyat = o.get("m2_fiyat")
    if not fiyat or not alt <= fiyat <= ust:
        sorunlar.append(f"m² fiyatı makul aralığın ({alt:,}-{ust:,}) dışında: {fiyat}")
        return sorunlar
    adet = o.get("ilan_sayisi")
    if adet is None:
        sorunlar.append("ilan sayısı okunamadı")
    elif adet < ILCE_ASGARI_ILAN:
        sorunlar.append(f"ilan sayısı yetersiz ({adet} < {ILCE_ASGARI_ILAN}): ortalama güvenilmez")
    degisim = o.get("m2_degisim")
    if degisim is not None and not DEGISIM_ARALIGI[0] <= degisim <= DEGISIM_ARALIGI[1]:
        sorunlar.append(f"yıllık değişim makul aralığın dışında: {degisim}")
    ort_fiyat = o.get("ort_fiyat")
    if ort_fiyat:
        alan = ort_fiyat / fiyat
        a_alt, a_ust = ALAN_ARALIGI.get(tur, (1, 10 ** 7))
        if not a_alt <= alan <= a_ust:
            sorunlar.append(f"ortalama fiyat ÷ m² fiyatı = {alan:.0f} m²: makul alan aralığının dışında")
    kira = o.get("m2_kira")
    if kira is not None:
        if not M2_KIRA_ARALIGI[0] <= kira <= M2_KIRA_ARALIGI[1]:
            sorunlar.append(f"m² kirası makul aralığın dışında: {kira}")
        else:
            hesap = kira * 12 / fiyat * 100
            sayfa = o.get("getiri")
            if sayfa is not None and abs(hesap - sayfa) > GETIRI_SAPMASI:
                sorunlar.append(f"sayfadaki getiri %{sayfa} ile kendi hesabımız %{hesap:.2f} tutmuyor")
            yil = o.get("geri_donus_yil")
            if yil is not None and abs(100 / hesap - yil) > 1:
                sorunlar.append(f"sayfadaki geri dönüş {yil} yıl ile kendi hesabımız {100 / hesap:.1f} yıl tutmuyor")
    return sorunlar


# ---------------------------------------------------------------------------
# Ağ
# ---------------------------------------------------------------------------

BASLIKLAR = {
    "User-Agent": KULLANICI_AJANI,
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "tr-TR,tr;q=0.9",
}


def sayfayi_cek(tur: str, bolge: str, deneme: int = 2) -> str:
    """Bölge sayfasının HTML'i. 403/429'da vazgeçilir (zorlanmaz), geçici hatada bir kez daha denenir."""
    adres = f"{TABAN}/{tur}/{bolge}"
    son_hata = ""
    for i in range(1, deneme + 1):
        try:
            r = requests.get(adres, headers=BASLIKLAR, timeout=ZAMAN_ASIMI_SN)
        except requests.RequestException as e:
            son_hata = f"{type(e).__name__}"
        else:
            if r.status_code == 200:
                return r.text
            if r.status_code in (403, 429):
                raise ErisimKapali(f"{adres} → HTTP {r.status_code}: site erişimi kapattı, zorlanmıyor")
            if r.status_code == 404:
                raise SayfaHatasi(f"{adres} → 404: bölge adresi yok")
            son_hata = f"HTTP {r.status_code}"
        if i < deneme:
            time.sleep(ISTEK_ARASI_SN * 2)
    raise SayfaHatasi(f"{adres} alınamadı ({son_hata})")


def topla(
    hedefler: Tuple[Tuple[str, str], ...] = HEDEFLER,
    cek: Callable[[str, str], str] = sayfayi_cek,
    bekle: Callable[[float], None] = time.sleep,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Hedeflerin ölçümünü toplar: (geçerli ölçümler, hata iletileri). İstekler arası `ISTEK_ARASI_SN` beklenir;
    site erişimi kapatırsa (403/429) kalan hedefler denenmez."""
    olcumler: List[Dict[str, Any]] = []
    hatalar: List[str] = []
    for sira, (tur, bolge) in enumerate(hedefler):
        if sira:
            bekle(ISTEK_ARASI_SN)
        try:
            o = sayfa_coz(cek(tur, bolge), tur, bolge)
            sorunlar = olcum_sorunlari(o)
            if sorunlar:
                raise SayfaHatasi("; ".join(sorunlar))
        except ErisimKapali as e:
            hatalar.append(f"{tur}/{bolge}: {e}")
            break
        except SayfaHatasi as e:
            hatalar.append(f"{tur}/{bolge}: {e}")
            continue
        olcumler.append(o)
    return olcumler, hatalar


# ---------------------------------------------------------------------------
# Depo
# ---------------------------------------------------------------------------

def tabloyu_kur() -> None:
    """`piyasa_verisi`: bölge başına günlük bir satır; mahalle satırları `ust_bolge` ile ilçeye bağlanır.

    Bilerek UNIQUE yok: veritabanı satır düzeyinde üç yönlü birleştiriliyor (bkz. db_birlestir) ve iki yazarın
    aynı mantıksal satırı eklemesi UNIQUE çakışması yerine yinelenen satıra yol açar; okuma en yeni `id`'yi alır.
    """
    with db._baglanti_al() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS piyasa_verisi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kaynak TEXT NOT NULL,
            tur TEXT NOT NULL,
            bolge TEXT NOT NULL,
            bolge_adi TEXT,
            ust_bolge TEXT,
            tarih TEXT NOT NULL,
            m2_fiyat REAL NOT NULL,
            m2_degisim REAL,
            ort_fiyat REAL,
            m2_kira REAL,
            m2_kira_degisim REAL,
            ort_kira REAL,
            getiri REAL,
            geri_donus_yil INTEGER,
            ilan_sayisi INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_piyasa_bolge ON piyasa_verisi(tur, bolge, tarih);
        """)


_SUTUNLAR = ("kaynak", "tur", "bolge", "bolge_adi", "ust_bolge", "tarih", "m2_fiyat", "m2_degisim", "ort_fiyat",
             "m2_kira", "m2_kira_degisim", "ort_kira", "getiri", "geri_donus_yil", "ilan_sayisi")


def kaydet(olcumler: List[Dict[str, Any]], tarih: Optional[str] = None) -> int:
    """Ölçümleri (ve mahalle satırlarını) o günün kaydı olarak yazar; aynı gün tekrar çalışırsa eskisi silinir.
    Dönen: yazılan satır sayısı."""
    tabloyu_kur()
    gun = tarih or _tr_bugun()
    yazilan = 0
    with db._baglanti_al() as conn:
        for o in olcumler:
            conn.execute(
                "DELETE FROM piyasa_verisi WHERE kaynak = ? AND tur = ? AND tarih = ? AND (bolge = ? OR ust_bolge = ?)",
                (o.get("kaynak", KAYNAK), o["tur"], gun, o["bolge"], o["bolge"]),
            )
            satirlar = [{**o, "ust_bolge": None, "tarih": gun}]
            for mh in o.get("mahalleler") or []:
                satirlar.append({
                    "kaynak": o.get("kaynak", KAYNAK), "tur": o["tur"], "bolge": mh["bolge"], "bolge_adi": mh.get("bolge_adi"),
                    "ust_bolge": o["bolge"], "tarih": gun, "m2_fiyat": mh["m2_fiyat"], "m2_degisim": mh.get("m2_degisim"),
                    "ilan_sayisi": mh.get("ilan_sayisi"),
                })
            for s in satirlar:
                conn.execute(
                    f"INSERT INTO piyasa_verisi ({', '.join(_SUTUNLAR)}) VALUES ({', '.join('?' * len(_SUTUNLAR))})",
                    tuple(s.get(k) if k != "kaynak" else s.get("kaynak", KAYNAK) for k in _SUTUNLAR),
                )
                yazilan += 1
    return yazilan


def _yas_gun(tarih: str, bugun: Optional[str] = None) -> int:
    return (date.fromisoformat(bugun or _tr_bugun()) - date.fromisoformat(tarih)).days


def son_olcum(tur: str, bolge: str, bugun: Optional[str] = None, azami_yas: int = AZAMI_YAS_GUN) -> Optional[Dict[str, Any]]:
    """İlçenin en yeni ölçümü (mahalle satırlarıyla). `azami_yas` günden eskiyse ya da hiç yoksa None:
    bayat rakam içeriğe girmez."""
    tabloyu_kur()
    with db._baglanti_al() as conn:
        satir = conn.execute(
            "SELECT * FROM piyasa_verisi WHERE kaynak = ? AND tur = ? AND bolge = ? AND ust_bolge IS NULL "
            "ORDER BY tarih DESC, id DESC LIMIT 1",
            (KAYNAK, tur, bolge),
        ).fetchone()
        if not satir:
            return None
        o = dict(satir)
        if _yas_gun(o["tarih"], bugun) > azami_yas:
            return None
        ham = conn.execute(
            "SELECT * FROM piyasa_verisi WHERE kaynak = ? AND tur = ? AND ust_bolge = ? AND tarih = ? ORDER BY id",
            (KAYNAK, tur, bolge, o["tarih"]),
        ).fetchall()
    mahalleler: Dict[str, Dict[str, Any]] = {}
    for r in ham:          # yinelenen satırda en yeni id kalır
        mahalleler[r["bolge"]] = dict(r)
    o["mahalleler"] = list(mahalleler.values())
    return o


def durum_ozeti(bugun: Optional[str] = None) -> str:
    """`hazirla.py --durum` için tek satır: en yeni toplama tarihi ve yaşı."""
    tabloyu_kur()
    with db._baglanti_al() as conn:
        satir = conn.execute("SELECT MAX(tarih) AS t FROM piyasa_verisi WHERE kaynak = ?", (KAYNAK,)).fetchone()
    if not satir or not satir["t"]:
        return "Piyasa verisi: hiç toplanmadı"
    yas = _yas_gun(satir["t"], bugun)
    isaret = "bayat — S4 veri konuları duruyor" if yas > AZAMI_YAS_GUN else "güncel"
    return f"Piyasa verisi: son toplama {satir['t']} ({yas} gün önce, {isaret})"


# ---------------------------------------------------------------------------
# İçeriğe girecek veri blokları
# ---------------------------------------------------------------------------

def kira_carpani(o: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """Fiyat ÷ yıllık kira: (geri dönüş yılı, brüt getiri yüzdesi). Kira yoksa None.
    Satış ve kira ortalamaları ayrı ilan kümelerinden gelir; sonuç bir yaklaşıktır."""
    fiyat, kira = o.get("m2_fiyat"), o.get("m2_kira")
    if not fiyat or not kira:
        return None
    yillik = kira * 12
    return {"yil": fiyat / yillik, "getiri": yillik / fiyat * 100}


def _baslik(gun: str) -> str:
    return (
        f"VERİ KAYNAĞI: {KAYNAK_ADI}, {tarih_yazisi(gun)} itibarıyla.\n"
        f"NİTELİK: {NITELIK}"
    )


_KURALLAR = (
    "KURALLAR: Yalnızca yukarıdaki rakamları, yazıldığı gibi kullan; yuvarlama, toplama ya da kendi başına oran "
    "hesaplama yapma. Kaynağı (Emlakjet/Endeksa) ve tarihi içerikte belirt. Rakamlara \"ortalama\" ya da "
    "\"tahmini\" de; \"tapu bedeli\", \"kesin fiyat\" ya da \"garanti getiri\" deme. Enflasyonla ya da "
    "başka bir veriyle karşılaştırma yapma, gelecek tahmini yazma."
)


def _ilce(tur: str, bolge: str, bugun: Optional[str]) -> Optional[Dict[str, Any]]:
    return son_olcum(tur, bolge, bugun)


def _ilce_satiri(ad: str, o: Dict[str, Any]) -> str:
    degisim = f"; son bir yılda {yuzde(o['m2_degisim'])} değişim" if o.get("m2_degisim") is not None else ""
    return f"{ad}: ortalama {tl(o['m2_fiyat'])} ₺/m² ({tl(o['ilan_sayisi'])} ilan{degisim})."


def _ayni_gun(olcumler: List[Dict[str, Any]]) -> bool:
    """Bir blokta yan yana duran ölçümler aynı gün toplanmış olmalı: başlıktaki "… itibarıyla" hepsi için doğru olsun.
    Bir sayfa toplanamayıp eski ölçümü kalırsa blok kurulmaz; ertesi toplamayı bekler."""
    return len({o["tarih"] for o in olcumler}) == 1


def blok_silivri_daire_mahalle(bugun: Optional[str] = None) -> Optional[str]:
    """S4-001: Silivri'de mahalle mahalle satılık daire m² fiyatı (yalnız yeterli ilanı olan mahalleler)."""
    ilce = _ilce("satilik-daire", "istanbul-silivri", bugun)
    if not ilce:
        return None
    yeterli = [m for m in ilce["mahalleler"]
               if (m.get("ilan_sayisi") or 0) >= MAHALLE_ASGARI_ILAN and m.get("bolge_adi") and m.get("m2_fiyat")]
    if len(yeterli) < 3:
        return None
    yeterli.sort(key=lambda m: m["m2_fiyat"], reverse=True)
    satirlar = [
        _baslik(ilce["tarih"]),
        "",
        _ilce_satiri("SİLİVRİ SATILIK DAİRE (ilçe geneli)", ilce),
        f"MAHALLELER (satılık daire ortalama ₺/m²; yalnızca {MAHALLE_ASGARI_ILAN} ve üzeri ilanı olan mahalleler, "
        f"pahalıdan ucuza):",
    ]
    for m in yeterli:
        satirlar.append(f"- {m['bolge_adi']}: {tl(m['m2_fiyat'])} ₺/m² ({tl(m['ilan_sayisi'])} ilan)")
    en_yuksek, en_dusuk = yeterli[0], yeterli[-1]
    fark = (en_yuksek["m2_fiyat"] / en_dusuk["m2_fiyat"] - 1) * 100
    # Ek (-den/-dan) kullanılmaz: mahalle adlarına ek getirmek yanlış yazıma yol açıyordu
    satirlar += [
        f"HESAPLANMIŞ FARK: en pahalı mahalle ({en_yuksek['bolge_adi']}) ile en ucuz mahalle ({en_dusuk['bolge_adi']}) "
        f"arasında yüzde {tl(fark, 1)} fark var.",
        "",
        _KURALLAR,
    ]
    return "\n".join(satirlar)


def blok_silivri_kira_carpani(bugun: Optional[str] = None) -> Optional[str]:
    """S4-004: Silivri'de satılık daire fiyatı ÷ yıllık kira (kira çarpanı) ve komşu bölgelerle karşılaştırma."""
    ilce = _ilce("satilik-daire", "istanbul-silivri", bugun)
    carpan = kira_carpani(ilce) if ilce else None
    if not ilce or not carpan:
        return None
    satirlar = [
        _baslik(ilce["tarih"]),
        "",
        f"SİLİVRİ: satılık daire ortalama {tl(ilce['m2_fiyat'])} ₺/m²; kiralık daire ortalama aylık "
        f"{tl(ilce['m2_kira'], 2)} ₺/m².",
        f"SİLİVRİ KİRA ÇARPANI (hesaplanmış, satış ÷ yıllık kira): {tl(carpan['yil'], 1)} yıl; "
        f"brüt kira getirisi yıllık {yuzde(carpan['getiri'] / 100, 2)}.",
    ]
    karsilastirma = []
    for tur, bolge, ad in (("satilik-daire", "istanbul-catalca", "Çatalca"),
                           ("satilik-daire", "istanbul-buyukcekmece", "Büyükçekmece"),
                           ("satilik-daire", "tekirdag-corlu", "Çorlu")):
        o = _ilce(tur, bolge, bugun)
        c = kira_carpani(o) if o else None
        if c and _ayni_gun([ilce, o]):      # başlıktaki tarih karşılaştırma satırı için de doğru olsun
            karsilastirma.append(f"- {ad}: satılık daire {tl(o['m2_fiyat'])} ₺/m², kira {tl(o['m2_kira'], 2)} ₺/m²; "
                                 f"kira çarpanı {tl(c['yil'], 1)} yıl, brüt getiri {yuzde(c['getiri'] / 100, 2)}")
    if karsilastirma:
        satirlar += ["KOMŞU BÖLGELER (aynı yöntemle):", *karsilastirma]
    satirlar += [
        "NOT: Satış ve kira ortalamaları ayrı ilan kümelerinden gelir; çarpan bir yaklaşıktır. Vergi, aidat, boş "
        "kalma süresi ve masraflar hesaba katılmamıştır (brüt).",
        "",
        _KURALLAR,
    ]
    return "\n".join(satirlar)


def blok_silivri_arsa_tarla_daire(bugun: Optional[str] = None) -> Optional[str]:
    """S4-013: Silivri'de arsa, tarla ve daire m² fiyatları ile bir yıllık değişimleri."""
    gruplar = [("SATILIK ARSA", "satilik-arsa"), ("SATILIK TARLA", "satilik-tarla"), ("SATILIK DAİRE", "satilik-daire")]
    olcumler = [(ad, _ilce(tur, "istanbul-silivri", bugun)) for ad, tur in gruplar]
    if any(o is None or o.get("m2_degisim") is None for _, o in olcumler) or not _ayni_gun([o for _, o in olcumler]):
        return None
    satirlar = [_baslik(olcumler[0][1]["tarih"]), ""]
    for ad, o in olcumler:
        satirlar.append(_ilce_satiri(f"SİLİVRİ {ad}", o))
    satirlar += [
        "NOT: Arsa ve tarlada kira geliri yoktur; veri yalnızca ilan fiyatı ortalamasındaki değişimi gösterir, "
        "bu bir getiri hesabı değildir. Arsa ve tarla ortalamaları parsel büyüklüğü ve imar durumuna göre çok "
        "dağılır; mahalle ya da tek parsel için bağlayıcı değildir.",
        "",
        _KURALLAR,
    ]
    return "\n".join(satirlar)


BLOKLAR: Dict[str, Callable[[Optional[str]], Optional[str]]] = {
    "silivri_daire_mahalle": blok_silivri_daire_mahalle,
    "silivri_kira_carpani": blok_silivri_kira_carpani,
    "silivri_arsa_tarla_daire": blok_silivri_arsa_tarla_daire,
}


def blok(anahtar: str, bugun: Optional[str] = None) -> Optional[str]:
    """Konunun `veri_blogu` anahtarına göre içeriğe girecek veri metni. Veri yoksa/bayatsa/yetersizse None:
    o konu o gün üretilmez. Bilinmeyen anahtar hatadır (yazım yanlışı sessizce konuyu kapatmasın)."""
    if anahtar not in BLOKLAR:
        raise KeyError(f"bilinmeyen veri bloğu: {anahtar}")
    return BLOKLAR[anahtar](bugun)


def brief_olustur(metin: str) -> Dict[str, Any]:
    """Üretilen içeriğin doğrulama ölçütü veri bloğunun KENDİSİdir. `mevzuat_metni` süre/oran/tutar ifadelerini
    (dogrula 1b ve 2), `veri_blogu_metni` birimli her rakamı ve kaynak atfını (dogrula.veri_blogu_denetimi) bloğa karşı
    denetler. `mevzuat` bilerek boştur: piyasa içeriği kanun maddesi anmaz, anarsa uydurmadır (⛔).
    `veri_kaynagi` bilerek yoktur: onunla bloktaki olmayan rakam ⚠️'ya iner, oysa burada ⛔ olmalı."""
    return {
        "mevzuat": None,
        "mevzuat_metni": metin,
        "veri_blogu_metni": metin,
        "yerel": True,
    }
