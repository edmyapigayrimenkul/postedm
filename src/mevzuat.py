"""
src/mevzuat.py — Kanun maddelerinin GÜNCEL metni (mevzuat.gov.tr).

NİYE VAR (2026-09-24 içerik denetimi): Canlıdaki 20 içeriğin 9'unun ana iddiası
yanlıştı. Çoğu, modelin eski hukuku bilmesinden:
  · TMK 733–734, 24/12/2025 tarihli 7571 sayılı Kanunla değişti — önalımda üst süre
    2 yıldan 1 yıla indi, bedel tapudaki değil hâkimin belirlediği rayiç değer oldu;
  · 6306 md. 6'da karar yeter sayısı 2019'dan (7181) beri salt çoğunluk, üçte iki değil;
  · 6217 geçici md. 2'deki tacir kiracı istisnası 1/7/2020'de bitti.
Bir kısmı da konu bankasındaki yanlış madde kaydından (konut kredisine tüketici
kredisinin cayma maddesi yazılmıştı). Model eğitim bilgisiyle değil, maddenin
bugünkü metniyle yazmalı; doğrulama da o metne karşı yapılmalı.

Kullanım:
    ozet = brief_mevzuati("Türk Medeni Kanunu md. 732-733")
    ozet["metin"]          # modele verilecek güncel madde metinleri
    ozet["son_degisiklik"] # maddelerdeki en yeni "Değişik/Ek" tarihi
    ozet["cozulemeyen"]    # yönetmelik/tebliğ gibi otomatik çekilemeyenler
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import tempfile
import threading
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Iterable

import certifi
import requests

from . import config

log = logging.getLogger(__name__)

TABAN = "https://www.mevzuat.gov.tr/anasayfa/MevzuatFihristDetayIframe"
ONBELLEK = config.yol_al("data/mevzuat_onbellek")
ONBELLEK_OMRU_SN = 7 * 24 * 3600

# mevzuat.gov.tr ara sertifikayı (GeoTrust TLS RSA CA G1) göndermiyor; tarayıcılar ve
# macOS curl zinciri kendisi tamamlıyor ama Python/Actions tamamlayamıyor. Doğrulamayı
# kapatmak yerine ara sertifika pakete eklenir. Sertifika 2 Kasım 2027'de sona erer.
ARA_SERTIFIKA = config.yol_al("assets/sertifika/geotrust_tls_rsa_ca_g1.pem")

# Kanun numarası → (tertip adayları, kısa ad). Tertip sitenin iç sınıflandırması;
# yanlış tertip 302 döndüğü için adaylar sırayla denenir.
KANUNLAR: Dict[int, Tuple[Tuple[int, ...], str]] = {
    4721: ((5,), "Türk Medeni Kanunu"),
    6098: ((5,), "Türk Borçlar Kanunu"),
    3194: ((5,), "İmar Kanunu"),
    634: ((5, 4), "Kat Mülkiyeti Kanunu"),
    2644: ((3, 4, 5), "Tapu Kanunu"),
    492: ((5, 4), "Harçlar Kanunu"),
    213: ((4, 5), "Vergi Usul Kanunu"),
    1319: ((5, 4), "Emlak Vergisi Kanunu"),
    5403: ((5,), "Toprak Koruma ve Arazi Kullanımı Kanunu"),
    6306: ((5,), "Afet Riski Altındaki Alanların Dönüştürülmesi Hakkında Kanun"),
    6502: ((5,), "Tüketicinin Korunması Hakkında Kanun"),
    2004: ((3, 4, 5), "İcra ve İflas Kanunu"),
    3402: ((5,), "Kadastro Kanunu"),
    6305: ((5,), "Afet Sigortaları Kanunu"),
    6217: ((5,), "Yargı Hizmetlerinin Hızlandırılması Amacıyla Bazı Kanunlarda Değişiklik Yapılmasına Dair Kanun"),
    7464: ((5,), "Konutların Turizm Amaçlı Kiralanması Hakkında Kanun"),
    2863: ((5,), "Kültür ve Tabiat Varlıklarını Koruma Kanunu"),
    7338: ((3, 4, 5), "Veraset ve İntikal Vergisi Kanunu"),
    # --- 2026-10-12: sözlük kart üretimi (SOZLUK-KART-URETIMI.md) için eklendi.
    # ⚠️ Tertip adayları DOĞRULANMADI: bu ortamda mevzuat.gov.tr ağ politikasıyla kapalıydı. Yanlış tertip
    # sitede 302 döndüğü için adaylar sırayla denenir; ilk canlı koşuda `scripts/kanun_oku.py kanunlar --dene`
    # ile her biri sınanmalı, tutmayan tertip buradan düzeltilmeli.
    2942: ((5,), "Kamulaştırma Kanunu"),
    3621: ((5,), "Kıyı Kanunu"),
    4342: ((5,), "Mera Kanunu"),
    6831: ((3, 4, 5), "Orman Kanunu"),
    4708: ((5,), "Yapı Denetimi Hakkında Kanun"),
    488: ((5, 4, 3), "Damga Vergisi Kanunu"),
    193: ((5, 4, 3), "Gelir Vergisi Kanunu"),
    3065: ((5,), "Katma Değer Vergisi Kanunu"),
    6100: ((5,), "Hukuk Muhakemeleri Kanunu"),
    6325: ((5,), "Hukuk Uyuşmazlıklarında Arabuluculuk Kanunu"),
    2985: ((5,), "Toplu Konut Kanunu"),
    1163: ((5, 4, 3), "Kooperatifler Kanunu"),
    2886: ((5,), "Devlet İhale Kanunu"),
    5393: ((5,), "Belediye Kanunu"),
}

# Adla anılan kanunlar (brief'ler çoğunlukla numara yerine ad kullanıyor)
_ADLAR: List[Tuple[str, int]] = [
    (r"t[üu]rk\s+medeni\s+kanunu|\btmk\b|medeni\s+kanun", 4721),
    (r"t[üu]rk\s+bor[çc]lar\s+kanunu|\btbk\b|bor[çc]lar\s+kanunu", 6098),
    (r"kat\s+m[üu]lkiyeti\s+kanunu|\bkmk\b", 634),
    (r"(?<!plansız alanlar )imar\s+kanunu", 3194),
    (r"tapu\s+kanunu", 2644),
    (r"har[çc]lar\s+kanunu", 492),
    (r"vergi\s+usul\s+kanunu|\bvuk\b", 213),
    (r"emlak\s+vergisi\s+kanunu", 1319),
    (r"toprak\s+koruma", 5403),
    (r"t[üu]keticinin\s+korunmas", 6502),
    (r"icra\s+ve\s+iflas\s+kanunu|\bi̇ik\b|\biik\b", 2004),
    (r"kadastro\s+kanunu", 3402),
    (r"k[üu]lt[üu]r\s+ve\s+tabiat\s+varl[ıi]klar[ıi]n[ıi]\s+koruma", 2863),
    (r"veraset\s+ve\s+intikal\s+vergisi\s+kanunu", 7338),
    (r"kamula[şs]t[ıi]rma\s+kanunu", 2942),
    (r"k[ıi]y[ıi]\s+kanunu", 3621),
    (r"mera\s+kanunu", 4342),
    (r"orman\s+kanunu", 6831),
    (r"yap[ıi]\s+denetimi\s+(?:hakk[ıi]nda\s+)?kanun", 4708),
    (r"damga\s+vergisi\s+kanunu", 488),
    (r"gelir\s+vergisi\s+kanunu|\bgvk\b", 193),
    (r"katma\s+de[ğg]er\s+vergisi\s+kanunu|\bkdvk\b", 3065),
    (r"hukuk\s+muhakemeleri\s+kanunu|\bhmk\b", 6100),
    (r"arabuluculuk\s+kanunu", 6325),
    (r"toplu\s+konut\s+kanunu", 2985),
    (r"kooperatifler\s+kanunu", 1163),
    (r"devlet\s+ihale\s+kanunu", 2886),
    (r"belediye\s+kanunu", 5393),
]


# ---------------------------------------------------------------------------
# Atıf çözümleme
# ---------------------------------------------------------------------------

def atiflari_coz(atif: Optional[str], aralik_azami: int = 3) -> Tuple[List[Tuple[int, List[str]]], List[str]]:
    """'Harçlar Kanunu md. 63 ve VUK md. 359' → [(492, ['63']), (213, ['359'])].

    Madde anahtarları metin: '63', 'geçici 16', 'ek 6'. Aralıklar (794-822) varsayılan olarak en fazla 4
    maddeye açılır (`aralik_azami`=3: ilk madde + 3; geniş aralık sonuna kadar uzayıp modele yığın metin
    vermesin). `scripts/kanun_oku.py` aralığı tam okumak için büyük değer geçer.
    Çözülemeyen atıflar (yönetmelik, tebliğ, kurul kararı) ayrı döner.
    """
    metin = str(atif or "")
    if not metin.strip():
        return [], []
    kucuk = metin.replace("İ", "i").replace("I", "ı").lower()

    bulunan: List[Tuple[int, int, int]] = []  # (konum, bitiş, kanun no)
    for m in re.finditer(r"\b(\d{3,4})\s*sayılı", kucuk):
        no = int(m.group(1))
        if no in KANUNLAR:
            bulunan.append((m.start(), m.end(), no))
    for kalip, no in _ADLAR:
        for m in re.finditer(kalip, kucuk):
            if not any(b[0] <= m.start() < b[1] + 80 and b[2] == no for b in bulunan):
                bulunan.append((m.start(), m.end(), no))
    bulunan.sort()

    sonuc: List[Tuple[int, List[str]]] = []
    for i, (bas, bit, no) in enumerate(bulunan):
        son = bulunan[i + 1][0] if i + 1 < len(bulunan) else len(kucuk)
        parca = kucuk[bit:son]
        maddeler: List[str] = []
        for m in re.finditer(r"((?:ge[çc]ici|ek)\s+)?(?:md\.?|madde|m\.)\s*(\d+)(?:\s*[-–]\s*(\d+))?((?:\s*(?:ve|,)\s*\d+)*)", parca):
            gecici = ("ek " if m.group(1).strip() == "ek" else "geçici ") if m.group(1) else ""
            ilk = int(m.group(2))
            if m.group(3):
                son_no = int(m.group(3))
                for n in range(ilk, min(son_no, ilk + aralik_azami) + 1):
                    maddeler.append(f"{gecici}{n}")
                if son_no > ilk + aralik_azami:
                    maddeler.append(f"{gecici}{son_no}")
            else:
                maddeler.append(f"{gecici}{ilk}")
            for ek in re.findall(r"\d+", m.group(4) or ""):
                maddeler.append(f"{gecici}{ek}")
        if maddeler:
            sonuc.append((no, list(dict.fromkeys(maddeler))))

    cozulemeyen = []
    if re.search(r"yönetmeli|tebli[ğg]|karar|genelge", kucuk):
        cozulemeyen.append(metin)
    elif not sonuc:
        cozulemeyen.append(metin)
    return sonuc, cozulemeyen


# ---------------------------------------------------------------------------
# Getirme ve önbellek
# ---------------------------------------------------------------------------

def atif_satiri(metin: Optional[str], azami_kanun: int = 4) -> Optional[str]:
    """Serbest metindeki kanun atıflarını brief'in `mevzuat` alanına uygun satıra çevirir.

    /arastir, /ozel ve /dosya içerikleri modelin hafızasından yazılıyordu ve hiçbir
    kanun metnine bağlanmıyordu: süre/oran denetiminin ölçütü yoktu. Bu satır
    brief'e girince güncel madde metni de girer ve denetim onunla yapılır.
    """
    cozulen, _ = atiflari_coz(metin)
    if not cozulen:
        return None
    return "; ".join(f"{no} sayılı Kanun md. {', '.join(maddeler)}" for no, maddeler in cozulen[:azami_kanun])


def _ca_paketi() -> str:
    paket = Path(tempfile.gettempdir()) / "edm_mevzuat_ca.pem"
    if not paket.exists() and ARA_SERTIFIKA.exists():
        paket.write_text(Path(certifi.where()).read_text() + "\n" + ARA_SERTIFIKA.read_text())
    return str(paket) if paket.exists() else certifi.where()


def _html_metne(ham: str) -> str:
    from bs4 import BeautifulSoup
    t = BeautifulSoup(ham, "html.parser").get_text("\n")
    t = html.unescape(re.sub(r"[ \t\xa0]+", " ", t))
    return re.sub(r"\s*\n\s*", " ", t)


def _atomik_yaz(dosya: Path, metin: str) -> None:
    """Önbelleğe atomik yazım: geçici dosya + os.replace. Paralel ajanlar (sözlük kartı üretimi) aynı kanun
    dosyasını aynı anda yazarken bir okuyucu YARIM metin görmesin; yarım metin "madde bulunamadı" demek olur."""
    gecici = dosya.with_name(f".{dosya.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        gecici.write_text(metin, encoding="utf-8")
        os.replace(gecici, dosya)
    finally:
        gecici.unlink(missing_ok=True)


def kanun_metni(no: int) -> Optional[str]:
    """Kanunun tam metni (düz yazı). 7 gün önbellekte tutulur."""
    ONBELLEK.mkdir(parents=True, exist_ok=True)
    dosya = ONBELLEK / f"{no}.txt"
    if dosya.exists() and time.time() - dosya.stat().st_mtime < ONBELLEK_OMRU_SN:
        return dosya.read_text(encoding="utf-8")

    tertipler = KANUNLAR.get(no, ((5,), ""))[0]
    for tertip in tertipler:
        try:
            r = requests.get(
                TABAN, params={"MevzuatTur": 1, "MevzuatNo": no, "MevzuatTertip": tertip},
                headers={"User-Agent": "Mozilla/5.0 (EDM postedm mevzuat denetimi)"},
                timeout=40, verify=_ca_paketi(), allow_redirects=False,
            )
        except requests.RequestException as e:
            log.warning("mevzuat.gov.tr erişilemedi (%s): %s", no, e)
            return dosya.read_text(encoding="utf-8") if dosya.exists() else None
        if r.status_code == 200 and len(r.content) > 5000:
            metin = _html_metne(r.text)
            if re.search(r"(MADDE|Madde)\s*1\s*[-–]", metin):
                _atomik_yaz(dosya, metin)
                return metin
    log.warning("Kanun metni bulunamadı: %s (tertipler %s)", no, tertipler)
    return dosya.read_text(encoding="utf-8") if dosya.exists() else None


def tertip_kesfet(no: int, aday_araligi: Iterable[int] = range(1, 9)) -> Optional[int]:
    """Kanunun sitedeki tertip numarasını arar (`KANUNLAR`taki adaylar tutmadığında). Metin döndüren ilk tertip.

    Yalnız bakım aracıdır (`kanun_oku.py kanunlar --dene`): yanlış tertip 302 döndüğü için 1-8 sırayla denenir ve
    bulunan numara `KANUNLAR`a elle yazılır. Önbelleğe yazmaz."""
    for tertip in aday_araligi:
        try:
            r = requests.get(
                TABAN, params={"MevzuatTur": 1, "MevzuatNo": no, "MevzuatTertip": tertip},
                headers={"User-Agent": "Mozilla/5.0 (EDM postedm mevzuat denetimi)"},
                timeout=40, verify=_ca_paketi(), allow_redirects=False,
            )
        except requests.RequestException as e:
            log.warning("mevzuat.gov.tr erişilemedi (%s, tertip %s): %s", no, tertip, e)
            return None
        if r.status_code == 200 and len(r.content) > 5000 and re.search(r"(MADDE|Madde)\s*1\s*[-–]", _html_metne(r.text)):
            return tertip
    return None


def madde_metni(no: int, madde: str, azami: int = 12000) -> Optional[str]:
    """Tek bir maddenin güncel metni. madde: '733', 'geçici 2' ya da 'ek 6'."""
    metin = kanun_metni(no)
    if not metin:
        return None
    gecici = madde.startswith("geçici")
    ek = madde.startswith("ek")
    n = madde.split()[-1]
    if gecici:
        bas = re.search(rf"GE[ÇC][İI]C[İI]\s+MADDE\s*{n}\s*[-–]", metin, re.I)
    elif ek:
        bas = re.search(rf"(?<![A-Za-zÇĞİÖŞÜçğıöşü])EK\s+MADDE\s*{n}\s*[-–]", metin, re.I)
    else:
        bas = re.search(rf"(?<![A-Za-zÇĞİÖŞÜçğıöşü])(?<!GEÇİCİ )(?<!Geçici )(?<!EK )(?<!Ek )(?:MADDE|Madde)\s*{n}\s*[-–]", metin)
    if not bas:
        return None
    sonraki = re.search(r"(?:GE[ÇC][İI]C[İI]\s+|EK\s+|Ek\s+)?(?:MADDE|Madde)\s*\d+\s*[-–]", metin[bas.end():])
    bitis = bas.end() + (sonraki.start() if sonraki else azami)
    return metin[bas.start():min(bitis, bas.start() + azami)].strip()


_TARIH = re.compile(r"(?:Değişik|Ek|Mülga|İptal)[^:()]{0,60}:\s*(\d{1,2})/(\d{1,2})/(\d{4})")


def degisiklik_tarihleri(metin: str) -> List[date]:
    tarihler = []
    for g, a, y in _TARIH.findall(metin or ""):
        try:
            tarihler.append(date(int(y), int(a), int(g)))
        except ValueError:
            continue
    return sorted(tarihler)


def brief_mevzuati(atif: Optional[str], azami_toplam: int = 15000) -> Dict[str, Any]:
    """Brief'in mevzuat alanındaki atıfların güncel metni ve değişiklik bilgisi."""
    atiflar, cozulemeyen = atiflari_coz(atif)
    parcalar: List[str] = []
    bulunamayan: List[str] = []
    son: Optional[date] = None
    for no, maddeler in atiflar:
        ad = KANUNLAR.get(no, ((), str(no)))[1]
        for madde in maddeler:
            m = madde_metni(no, madde)
            if not m:
                bulunamayan.append(f"{no} sayılı {ad} md. {madde}")
                continue
            parcalar.append(f"[{no} sayılı {ad}] {m}")
            tarihler = degisiklik_tarihleri(m)
            if tarihler and (son is None or tarihler[-1] > son):
                son = tarihler[-1]
    metin = "\n\n".join(parcalar)
    if len(metin) > azami_toplam:
        metin = metin[:azami_toplam] + " …"
    return {
        "metin": metin,
        "son_degisiklik": son.isoformat() if son else None,
        "cozulemeyen": cozulemeyen + bulunamayan,
        "cekildi": date.today().isoformat(),
    }


# ---------------------------------------------------------------------------
# Dayanak alıntısı — konunun "kanun şöyle diyor" iddiasının kanıtı
# ---------------------------------------------------------------------------
#
# Konu bankasına (2026-10-07) `dayanak_alintisi` alanı geldi: atıf yapılan maddenin GÜNCEL
# metninden birebir bir cümle. Alıntı kanıt olduğu için haftalık denetim (mevzuat_denetim.py)
# onun hâlâ metinde durduğunu doğrular; kanun değişirse konu kırmızıya düşer ve brief yeniden
# okunur. Ayrıca konunun `aci` alanındaki süre, oran ve çoğunluk ifadelerinin metinde geçmesi
# şart: model eğitim bilgisiyle değil, bu metinle yazar.

_DIPNOT = re.compile(r"\[\d+\]")


def cogunluk_katla(metin: str) -> str:
    """Çoğunluk ifadelerini çekim eklerinden bağımsız karşılaştırmak için: "çoğunluğu" → "çoğunluk".

    Kanun metni "salt çoğunluğu / çoğunluğuyla" yazar (k→ğ yumuşaması); içerik ise "salt çoğunluk"
    der. Düz alt dize araması doğru içeriği yanlışlıkla ⛔ yapıyordu (2026-10-07, KMK md. 30)."""
    return metin.replace("çoğunluğ", "çoğunluk")


def _alinti_normal(metin: str) -> str:
    from . import filtre
    metin = _DIPNOT.sub(" ", metin or "")
    metin = re.sub(r"\s+", " ", metin).strip().rstrip(".")
    return filtre.kucult(metin)


def alinti_metinde_mi(alinti: str, metin: str) -> bool:
    """Alıntı, kanun metninde (dipnot işaretleri ve boşluk farkı hariç) birebir geçiyor mu."""
    a = _alinti_normal(alinti)
    return len(a) >= 20 and a in _alinti_normal(metin)


def konu_dayanagi_sorunlari(konu: Dict[str, Any]) -> List[str]:
    """`dayanak_alintisi` taşıyan konunun güncel metne karşı sorunları (boş liste = temiz)."""
    alinti = str(konu.get("dayanak_alintisi") or "").strip()
    if not alinti:
        return []
    if not konu.get("mevzuat"):
        return ["dayanak_alintisi var ama mevzuat atfı yok"]
    ozet = brief_mevzuati(konu["mevzuat"], azami_toplam=200000)
    metin = ozet["metin"]
    if not metin:
        return ["dayanak_alintisi var ama atıf yapılan maddenin metni alınamadı: " + "; ".join(ozet["cozulemeyen"])[:120]]
    sorunlar: List[str] = []
    if not alinti_metinde_mi(alinti, metin):
        sorunlar.append("dayanak_alintisi güncel metinde birebir bulunamadı (madde değişmiş olabilir)")
    aci = str(konu.get("aci") or "")
    kacak_sure = sorted(sure_ifadeleri(aci) - sure_ifadeleri(metin))
    if kacak_sure:
        sorunlar.append("aci'deki süre güncel metinde yok: " + ", ".join(f"{n} {b}" for n, b in kacak_sure))
    kacak_oran = sorted(oran_ifadeleri(aci) - oran_ifadeleri(metin))
    if kacak_oran:
        sorunlar.append("aci'deki oran güncel metinde yok: " + ", ".join(f"%{o}" for o in kacak_oran))
    metin_k = cogunluk_katla(metin.replace("İ", "i").replace("I", "ı").lower())
    aci_k = cogunluk_katla(aci.replace("İ", "i").replace("I", "ı").lower())
    for c in CUNLUK_IFADELERI:
        if c in aci_k and c not in metin_k:
            sorunlar.append(f"aci'deki çoğunluk güncel metinde yok: {c}")
    return sorunlar


# ---------------------------------------------------------------------------
# Süre ve çoğunluk ifadeleri — dogrula.py bunları kanun metnine karşı denetler
# ---------------------------------------------------------------------------

_BIRLER = {"bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5, "altı": 6, "yedi": 7, "sekiz": 8, "dokuz": 9}
_ONLAR = {"on": 10, "yirmi": 20, "otuz": 30, "kırk": 40, "elli": 50, "altmış": 60, "yetmiş": 70, "seksen": 80, "doksan": 90}
# Kanun metinleri birleşik yazımı da kullanıyor ("oniki aylık", "onbeş gün").
# "yüz" da var: 7464 sayılı Kanun "yüz gün", "yüz bin" yazar; yalnız 99'a kadar tanınınca "100 gün" yazan
# doğru içerik "kanunda yok" sayılıyordu (S2-026, 2026-10-07). "yüzde" ile karışmaz: sonrasında boşluk şart.
_SAYI_SOZ = r"(?:yüz(?:\s*(?:on|yirmi|otuz|kırk|elli|altmış|yetmiş|seksen|doksan))?(?:\s*(?:bir|iki|üç|dört|beş|altı|yedi|sekiz|dokuz))?|(?:on|yirmi|otuz|kırk|elli|altmış|yetmiş|seksen|doksan)(?:\s*(?:bir|iki|üç|dört|beş|altı|yedi|sekiz|dokuz))?|bir|iki|üç|dört|beş|altı|yedi|sekiz|dokuz)"
# Yazıyla sayıda birimle arasında boşluk zorunlu: aksi hâlde "noter onaylı" → "on ay".
# Ondalık sayının kuyruğu süre değildir: "%1,8 aylık enflasyon" içindeki "8 ay" iki hafta
# önce ⛔ SÜRE KAYNAKTA YOK verdirdi (vurgu rakamı + etiket birleşince). (?<![\d.,]) bunu eler.
# Birimden sonra sözcük sınırı YOK (aylık, yıllık, günlük, aya, yıldır süre sayılır) ama bu birimlerle başlayan başka sözcükler
# süre sayılmaz: "md. 319 ayıp" → "319 ay", "bir ayrı madde" → "bir ay" ⛔ SÜRE KAYNAKTA YOK veriyordu (2026-10-13, sözlük
# dalgası: kira/satış AYIP kartları hiç geçemiyordu).
_SURE = re.compile(
    rf"(?:(?<![\d.,])\b(\d+)\s*|\b({_SAYI_SOZ})\s+)(iş\s+günü|gün(?!ey|dem|ah|ce)|hafta|ay(?!ıp|rı|nı|kı)|yıl(?!dız|an))", re.I)
# "beşte dör": kanun metni "beşte dördünün" yazar (dört → dördü, t→d ünsüz yumuşaması); "beşte dört"
# diye aramak doğru içeriği yanlışlıkla ⛔ yapıyordu (KMK md. 28, 2026-10-07).
CUNLUK_IFADELERI = ("üçte iki", "salt çoğunluk", "oybirliği", "dörtte üç", "beşte dör")


def _sayiya(soz: str) -> Optional[int]:
    soz = re.sub(r"\s+", "", soz.strip().lower())
    if soz.isdigit():
        return int(soz)
    toplam = 0
    if soz.startswith("yüz"):
        toplam, soz = 100, soz[3:]
        if not soz:
            return 100
    for onlar, deger in sorted(_ONLAR.items(), key=lambda x: -len(x[0])):
        if soz.startswith(onlar) and (soz == onlar or soz[len(onlar):] in _BIRLER):
            toplam, soz = toplam + deger, soz[len(onlar):]
            break
    if soz:
        if soz not in _BIRLER:
            return None
        toplam += _BIRLER[soz]
    return toplam or None


_ORAN = re.compile(rf"(?:%\s*(\d+(?:[.,]\d+)?)|\byüzde\s*(\d+(?:[.,]\d+)?|{_SAYI_SOZ}))", re.I)


def oran_ifadeleri(metin: str) -> set:
    """'%45', 'yüzde 45', 'yüzde kırkbeş' → {'45'}. Kanun metni oranı yazıyla verir."""
    kucuk = (metin or "").replace("İ", "i").replace("I", "ı").lower()
    sonuc = set()
    for rakam, sonra in _ORAN.findall(kucuk):
        ham = (rakam or sonra).replace(",", ".")
        if re.fullmatch(r"\d+(?:\.\d+)?", ham):
            sonuc.add(ham.rstrip("0").rstrip(".") if "." in ham else ham)
        else:
            n = _sayiya(ham)
            if n is not None:
                sonuc.add(str(n))
    return sonuc


def sure_ifadeleri(metin: str) -> set:
    """'iki yıl', '2 yıl', 'on dört gün' → {('2','yıl'), ('14','gün')}"""
    kucuk = (metin or "").replace("İ", "i").replace("I", "ı").lower()
    sonuc = set()
    for rakam, soz, birim in _SURE.findall(kucuk):
        n = _sayiya(rakam or soz)
        # "2018 yılında" bir takvim yılıdır, süre değil. Haber denetiminde kaynak
        # "2018'de" derken içerik "2018 yılında" yazınca ⛔ SÜRE KAYNAKTA YOK
        # veriyordu (#452 yeniden üretimi, 2026-10-07).
        if n is not None and birim == "yıl" and 1900 <= n <= 2100:
            continue
        if n is not None:
            sonuc.add((str(n), re.sub(r"\s+", " ", birim)))
    return sonuc
