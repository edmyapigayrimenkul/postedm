"""
sozluk_dogrulama.py — Sözlük kartı TASLAKLARINI arşive girmeden önce denetleyen ve arşive ekleyen kitaplık.
(CLI: scripts/sozluk_kart_dogrula.py, scripts/sozluk_kart_birlestir.py; süreç: SOZLUK-KART-URETIMI.md)

Neden ayrı kitaplık: yazar ajan kendi taslağını, inceleme ajanı yeniden, birleştirici bir kez daha aynı denetimi
çalıştırır; üçü de AYNI kuralı görmeli. Arşivin kendi yükleyicisi (`sozluk_arsivi.kartlari_yukle`) kusurlu kartı
yalnız günlüğe yazıp ATLAR; taslak aşamasında sessiz atlama olmaz, her sorun kartın yanında açıkça yazılır.

Denetim katmanları (hepsi "sorun" = arşive girmez; "ipucu" = bilgi):
  1. yapı        alanlar, karakter bütçeleri, yasaklı işaretler     (`sozluk_arsivi.kart_yapisal_sorunlari`)
  2. tekrar      terim arşivde / başka taslakta / aynı dosyada var   (aksan, büyük-küçük harf, boşluk gözetmeden)
  3. kanun       atıftaki her madde okunabilmeli; dayanak alıntısı güncel metinde BİREBİR olmalı; kartta geçen
                 her süre, oran, çoğunluk maddede bulunmalı        (`sozluk_arsivi.kart_kanun_durumu`)
  4. kapı        yayın kapısı (`dogrula.denetle`) UYARISIZ olmalı
  5. çizim       iki ölçüde (besleme, story) TasmaHatasi vermeden çizilmeli
  6. hakem       (yalnız istenirse) ikinci model anlam kaymasını arar; orkestratör kullanır, yazar ajanlar kullanmaz
  İpucu          cümle başına sözcük kökü örtüşmesi: kanun metninde karşılığı zayıf cümleleri işaretler (hüküm değil)
"""

from __future__ import annotations

import copy
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

import yaml

from . import filtre, mevzuat, sozluk_arsivi

GECICI_KOD = "SZ-999"            # taslakta kod yoktur (birleştirmede atanır); yapı denetimi için yer tutucu
ALAN_SIRASI = ("kod", "terim", "kategori_kodu", "tanim", "puf", "mevzuat", "dayanak_alintisi", "kontrol", "pasif")
KABUL_EDILEN_INCELEME = ("onay", "duzeltildi")   # inceleme ajanı kartı olduğu gibi (onay) ya da düzelterek (duzeltildi) kabul etti
ORTUSME_ESIGI = 0.5              # cümledeki anlamlı sözcüklerin bu orandan azı kanun metninde köklenirse ipucu çıkar
KOK_UZUNLUK = 5


@dataclass
class KartRaporu:
    terim: str
    kod: Optional[str] = None
    sorunlar: List[str] = field(default_factory=list)
    ipuclari: List[str] = field(default_factory=list)
    inceleme: Optional[str] = None

    @property
    def temiz(self) -> bool:
        return not self.sorunlar

    def sozluk(self) -> Dict[str, Any]:
        return {"terim": self.terim, "kod": self.kod, "temiz": self.temiz, "sorunlar": self.sorunlar,
                "ipuclari": self.ipuclari, "inceleme": self.inceleme}


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

_ASCII = str.maketrans({"ı": "i", "ğ": "g", "ü": "u", "ş": "s", "ö": "o", "ç": "c", "â": "a", "î": "i", "û": "u"})


def normal_terim(terim: Any) -> str:
    """Tekrar karşılaştırması için terim: Türkçe küçük harf, aksansız, tek boşluk, noktalama yok."""
    metin = filtre.kucult(str(terim or "")).translate(_ASCII)
    metin = unicodedata.normalize("NFKD", metin)
    metin = "".join(c for c in metin if not unicodedata.combining(c))
    metin = re.sub(r"[^a-z0-9 ]+", " ", metin)
    return re.sub(r"\s+", " ", metin).strip()


def taslagi_yukle(yol: Path | str) -> List[Dict[str, Any]]:
    """Taslak dosyasının `kartlar` listesi. Biçim bozuksa ValueError (sessiz boş liste DÖNMEZ)."""
    yol = Path(yol)
    try:
        ham = yaml.safe_load(yol.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise ValueError(f"{yol}: okunamadı/ayrıştırılamadı: {e}") from e
    if isinstance(ham, list):          # düz liste de kabul: yazar ajan `kartlar:` anahtarını unutabilir
        kartlar = ham
    elif isinstance(ham, dict) and isinstance(ham.get("kartlar"), list):
        kartlar = ham["kartlar"]
    else:
        raise ValueError(f"{yol}: 'kartlar:' listesi yok")
    for i, k in enumerate(kartlar):
        if not isinstance(k, dict):
            raise ValueError(f"{yol}: kartlar[{i}] bir sözlük değil")
    return kartlar


def arsiv_ham_kartlari(arsiv_yolu: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    """Arşivdeki TÜM kartlar (kusurlu olanlar dahil): tekrar ve kod denetimi yükleyicinin atladıklarını da bilmeli.
    `arsiv_yolu` None ise çağrı anındaki `sozluk_arsivi.ARSIV_YOLU` (varsayılan değer tanım anında bağlanmaz)."""
    yol = Path(arsiv_yolu or sozluk_arsivi.ARSIV_YOLU)
    if not yol.exists():
        return []
    ham = yaml.safe_load(yol.read_text(encoding="utf-8")) or {}
    return [k for k in (ham.get("kartlar") or []) if isinstance(k, dict)]


def arsiv_terimleri(arsiv_yolu: Optional[Path | str] = None) -> Dict[str, str]:
    """normal terim → arşivdeki kod."""
    return {normal_terim(k.get("terim")): str(k.get("kod")) for k in arsiv_ham_kartlari(arsiv_yolu)}


def _cumleler(metin: str) -> List[str]:
    return [c.strip() for c in re.split(r"(?<=[.;:])\s+", metin or "") if c.strip()]


def _kok(sozcuk: str) -> str:
    return normal_terim(sozcuk).replace(" ", "")[:KOK_UZUNLUK]


def ortusme_ipuclari(kart: Dict[str, Any], kanun_metni: str, esik: float = ORTUSME_ESIGI) -> List[str]:
    """Her cümlenin anlamlı sözcüklerinin (5+ harf) kaçı kök olarak kanun metninde geçiyor. Düşük örtüşme = cümle
    maddeden değil yazarın hafızasından gelmiş olabilir. HÜKÜM DEĞİL İPUCU: eş anlamlı yeniden ifade doğru olabilir."""
    kanun_kokleri = {_kok(s) for s in re.findall(r"[^\W\d_]{%d,}" % KOK_UZUNLUK, filtre.kucult(kanun_metni))}
    ipuclari: List[str] = []
    parcalar = [("tanim", str(kart.get("tanim") or ""))] + [(f"puf[{i}]", str(m)) for i, m in enumerate(kart.get("puf") or [])]
    for ad, metin in parcalar:
        for cumle in _cumleler(metin):
            sozcukler = re.findall(r"[^\W\d_]{%d,}" % KOK_UZUNLUK, filtre.kucult(cumle))
            if len(sozcukler) < 3:
                continue
            oran = sum(1 for s in sozcukler if _kok(s) in kanun_kokleri) / len(sozcukler)
            if oran < esik:
                ipuclari.append(f"{ad}: kanun metniyle örtüşme %{round(oran * 100)}: “{cumle[:70]}”")
    return ipuclari


# ---------------------------------------------------------------------------
# Tek kartın denetimi
# ---------------------------------------------------------------------------

def karti_denetle(
    kart: Dict[str, Any],
    mevcut_terimler: Optional[Dict[str, str]] = None,
    *,
    kanun: bool = True,
    ciz: bool = True,
    hakem: bool = False,
    hakem_cagri: Optional[Callable[..., Optional[str]]] = None,
) -> KartRaporu:
    """Kartı bütün katmanlardan geçirir. `mevcut_terimler`: normal terim → nerede olduğu (arşiv kodu / taslak adı);
    kart temizse çağıran bunu kendi sözlüğüne ekler (bkz. `taslaklari_denetle`)."""
    rapor = KartRaporu(terim=str(kart.get("terim") or "?"), kod=kart.get("kod"), inceleme=kart.get("inceleme"))
    tam = dict(kart)
    tam.setdefault("kod", GECICI_KOD)
    if not tam.get("kod"):
        tam["kod"] = GECICI_KOD

    # 1. yapı — eksikse diğer katmanlar anlamsız
    yapi = sozluk_arsivi.kart_yapisal_sorunlari(tam)
    if yapi:
        rapor.sorunlar.extend(f"yapı: {s}" for s in yapi)
        return rapor

    # 2. tekrar
    if mevcut_terimler is not None:
        nerede = mevcut_terimler.get(normal_terim(tam["terim"]))
        if nerede:
            rapor.sorunlar.append(f"tekrar: “{tam['terim']}” zaten var ({nerede})")

    # 3-4. kanun ve kapı
    metin = ""
    if kanun:
        ozet = mevzuat.brief_mevzuati(tam["mevzuat"], azami_toplam=200000)
        metin = ozet.get("metin") or ""
        if ozet.get("cozulemeyen"):
            rapor.sorunlar.append("kanun: atıf tam çözülemedi/okunamadı: " + "; ".join(ozet["cozulemeyen"])[:200])
        if not metin:
            rapor.sorunlar.append("kanun: atıf yapılan maddelerin metni alınamadı (doğrulanamayan kart arşive girmez)")
        else:
            taze, kanun_sorunlari = sozluk_arsivi.kart_kanun_durumu(tam)
            if taze is not True:
                rapor.sorunlar.extend(f"kanun: {s}" for s in (kanun_sorunlari or ["doğrulanamadı"]))
            brief = {"mevzuat": tam["mevzuat"], "mevzuat_metni": metin, "veri_kaynagi": "kanun", "yerel": None}
            from . import dogrula
            veri = sozluk_arsivi.karttan_veri(tam)
            for uyari in dogrula.denetle(veri, brief):
                rapor.sorunlar.append(f"kapı: {uyari}")
            rapor.ipuclari.extend(ortusme_ipuclari(tam, metin))
    else:
        rapor.ipuclari.append("kanun denetimi ATLANDI (--kanunsuz): bu sonuç birleştirme için GEÇERSİZ")

    # 5. çizim
    if ciz:
        rapor.sorunlar.extend(cizim_sorunlari(tam))

    # 6. hakem (yalnız orkestratör)
    if hakem and kanun and metin:
        from . import capraz_denetim
        bulgular, calisti = capraz_denetim.denetle_ayrintili(sozluk_arsivi.karttan_veri(tam), metin, hakem_cagri)
        rapor.sorunlar.extend(f"hakem: {b}" for b in bulgular)
        if not calisti:
            rapor.ipuclari.append("hakem ÇALIŞMADI (kota/ağ/kaynak yok): anlam kayması denetlenmedi")
    return rapor


def cizim_sorunlari(kart: Dict[str, Any]) -> List[str]:
    """Kartı iki ölçüde çizer; taşma/örtülme/eksik içerik hatası (TasmaHatasi, EksikIcerik) sorun sayılır."""
    from . import yeni_formatlar
    sorunlar: List[str] = []
    veri = sozluk_arsivi.karttan_veri(kart)
    with tempfile.TemporaryDirectory() as tmp:
        for olcu in ("besleme", "story"):
            try:
                yollar = yeni_formatlar.slaytlari_uret(
                    copy.deepcopy(veri), format_turu="sozluk", cikti_dizini=Path(tmp),
                    cikti_onek=f"dogrula_{olcu}", olcu=olcu)
                if len(yollar) != 1:
                    sorunlar.append(f"çizim ({olcu}): 1 yerine {len(yollar)} görsel")
            except Exception as e:  # noqa: BLE001 — her çizim hatası kartı eler
                sorunlar.append(f"çizim ({olcu}): {type(e).__name__}: {str(e)[:160]}")
    return sorunlar


# ---------------------------------------------------------------------------
# Taslakların denetimi (dosya içi + dosyalar arası + arşiv tekrarı)
# ---------------------------------------------------------------------------

def taslaklari_denetle(
    yollar: Iterable[Path | str],
    *,
    arsiv_yolu: Optional[Path | str] = None,
    kanun: bool = True,
    ciz: bool = True,
    hakem: bool = False,
    hakem_cagri: Optional[Callable[..., Optional[str]]] = None,
) -> List[Tuple[Path, List[Tuple[Dict[str, Any], KartRaporu]]]]:
    """Her dosya için [(kart, rapor)]. Tekrar denetimi arşivi, ÖNCEKİ taslakları ve aynı dosyada önceki kartları
    görür: aynı terimi iki ajan yazdıysa ilk geleni kalır, ikincisi 'tekrar' alır."""
    terimler = dict(arsiv_terimleri(arsiv_yolu))
    sonuc = []
    for yol in map(Path, yollar):
        kartlar = taslagi_yukle(yol)
        satirlar = []
        for i, kart in enumerate(kartlar):
            rapor = karti_denetle(kart, terimler, kanun=kanun, ciz=ciz, hakem=hakem, hakem_cagri=hakem_cagri)
            # Yalnız temiz ve reddedilmemiş kart terimi "alır": kusurlu ya da inceleme ajanının reddettiği kart, aynı terimi
            # doğru yazan başka bir taslağı tekrar diye engellemesin.
            if rapor.temiz and kart.get("inceleme") != "red" and normal_terim(kart.get("terim")) not in terimler:
                terimler[normal_terim(kart.get("terim"))] = f"{yol.name} kart {i + 1}"
            satirlar.append((kart, rapor))
        sonuc.append((yol, satirlar))
    return sonuc


# ---------------------------------------------------------------------------
# Birleştirme
# ---------------------------------------------------------------------------

@dataclass
class BirlestirmeRaporu:
    eklenen: List[Dict[str, Any]] = field(default_factory=list)       # arşive girecek (kod atanmış) kartlar
    atlanan: List[Tuple[str, str]] = field(default_factory=list)      # (terim, neden)
    yazildi: bool = False
    hata: Optional[str] = None


def sonraki_kod_numarasi(arsiv_kartlari: List[Dict[str, Any]]) -> int:
    """Arşivdeki en büyük SZ-NNN'den sonraki numara. Kodlar kalıcı kimliktir (yayın geçmişi buna bakar): silinen/pasif
    kartın kodu da yeniden kullanılmaz, bu yüzden TÜM kartlara (pasif dahil) bakılır."""
    sayilar = [int(m.group(1)) for k in arsiv_kartlari if (m := re.fullmatch(r"SZ-(\d{3,})", str(k.get("kod") or "")))]
    return (max(sayilar) + 1) if sayilar else 1


def _arsive_girecek_alanlar(kart: Dict[str, Any], kod: str) -> Dict[str, Any]:
    """Taslağa özgü alanlar (inceleme, inceleme_notu, kod) düşer; sıra sabit."""
    tam = dict(kart, kod=kod)
    return {a: tam[a] for a in ALAN_SIRASI if a in tam and tam[a] not in (None, "")}


def kartlari_yaml_metnine(kartlar: List[Dict[str, Any]]) -> str:
    """Arşivin mevcut biçemiyle aynı (kök seviyede '- kod: ...'), başlık yorumlarına dokunmadan EKLENECEK metin."""
    return yaml.safe_dump(kartlar, allow_unicode=True, sort_keys=False, default_flow_style=False, width=10_000)


def birlestir(
    yollar: Iterable[Path | str],
    *,
    arsiv_yolu: Optional[Path | str] = None,
    kuru: bool = False,
    denetle: Callable[..., List[Tuple[Path, List[Tuple[Dict[str, Any], KartRaporu]]]]] = taslaklari_denetle,
) -> BirlestirmeRaporu:
    """Onaylı (inceleme: onay | duzeltildi) ve denetimden TEMİZ çıkan taslak kartları arşivin sonuna ekler.

    Arşive yazılmadan önce taslaklar yeniden denetlenir (kanun + kapı + çizim dahil): birleştirici kimsenin
    "geçti" sözüne güvenmez. `kuru=True`: yazmaz, ne ekleyeceğini söyler. Yazım atomiktir ve ardından arşiv
    yeniden yüklenip hiçbir kartın yapısal denetimden kalmadığı doğrulanır; kalırsa dosya eski haline döner."""
    arsiv_yolu = Path(arsiv_yolu or sozluk_arsivi.ARSIV_YOLU)
    rapor = BirlestirmeRaporu()
    ham = arsiv_ham_kartlari(arsiv_yolu)
    numara = sonraki_kod_numarasi(ham)
    for _yol, satirlar in denetle(yollar, arsiv_yolu=arsiv_yolu):
        for kart, r in satirlar:
            terim = str(kart.get("terim") or "?")
            if kart.get("inceleme") not in KABUL_EDILEN_INCELEME:
                rapor.atlanan.append((terim, f"inceleme '{kart.get('inceleme') or 'yok'}' (onay/duzeltildi gerekir)"))
            elif not r.temiz:
                rapor.atlanan.append((terim, "denetim: " + "; ".join(r.sorunlar)[:300]))
            else:
                rapor.eklenen.append(_arsive_girecek_alanlar(kart, f"SZ-{numara:03d}"))
                numara += 1
    if kuru or not rapor.eklenen:
        return rapor

    eski = arsiv_yolu.read_text(encoding="utf-8") if arsiv_yolu.exists() else "kartlar:\n"
    yeni = eski.rstrip("\n") + "\n" + kartlari_yaml_metnine(rapor.eklenen)
    gecici = arsiv_yolu.with_name(f".{arsiv_yolu.name}.{os.getpid()}.tmp")
    try:
        gecici.write_text(yeni, encoding="utf-8")
        os.replace(gecici, arsiv_yolu)
    finally:
        gecici.unlink(missing_ok=True)

    # Doğrulama: yazılan arşiv okunabilir ve hiçbir kart yükleyiciden atlanmıyor mu
    beklenen = len(ham) + len(rapor.eklenen)
    try:
        yuklenen = yaml.safe_load(arsiv_yolu.read_text(encoding="utf-8"))["kartlar"]
        sorun = None if len(yuklenen) == beklenen else f"arşivde {len(yuklenen)} kart var, {beklenen} bekleniyordu"
        if sorun is None:
            eksik = [k["kod"] for k in yuklenen if sozluk_arsivi.kart_yapisal_sorunlari(k)]
            sorun = f"yapısal denetimden kalan kart: {eksik[:5]}" if eksik else None
    except Exception as e:  # noqa: BLE001
        sorun = f"yazılan arşiv okunamadı: {e}"
    if sorun:
        arsiv_yolu.write_text(eski, encoding="utf-8")
        rapor.hata = f"{sorun}; arşiv eski haline döndürüldü"
        return rapor
    rapor.yazildi = True
    return rapor
