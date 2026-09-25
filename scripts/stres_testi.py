#!/usr/bin/env python3
"""
scripts/stres_testi.py — Görsel Motor Stres ve Sabotaj Testi

İki tuval ölçüsünde (4:5 besleme ve 9:16 story) çizim motorunu hem HACİM UÇLARINDA
hem de BOZUK/DÜŞMANCA GİRDİYLE zorlar.

Neden var: motor modelden gelen JSON'a güveniyor. Model bazen alan atlıyor, bazen
yanlış tip gönderiyor, bazen 10 katı uzunlukta metin yazıyor. Cron gözetimsiz
çalıştığı için bunların hiçbiri çökmeyle sonuçlanmamalı; çökerse o günün paylaşımı
sessizce düşer.

Denetimler:
  1. ÇÖKME       — hiçbir girdi istisna fırlatmamalı
  2. ÖLÇÜ        — çıktı istenen tuval boyutunda olmalı
  3. TAŞMA       — metin güvenli alanın dışına piksel taşırmamalı (düz zeminlerde)
  4. BOŞLUK      — slayt tamamen boş kalmamalı (içerik kayboldu demektir)
  5. SÜRE        — tek slayt çizimi makul sürede bitmeli

    python scripts/stres_testi.py              # tam paket, iki boyut
    python scripts/stres_testi.py --olcu story # tek boyut
    python scripts/stres_testi.py --hizli      # sabotaj atlanır
"""

from __future__ import annotations

import argparse
import copy
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from PIL import Image

from src import make_image as mi

CIKTI = KOK / "data/output/stres"

# Piksel analizinde yapılamayan slaytlar: kapak ve finansal tablo fotoğraf/gradyan
# taşıdığı için "zemin rengi" tanımlı değil.
DUZ_ZEMIN_SLAYTLARI = {"tek_fikir", "ikili_fikir", "adim", "adimlar_toplu", "kapanis"}


# =========================================================================
# FİKSTÜRLER
# =========================================================================

def _temel() -> Dict[str, Any]:
    """Gerçek üretimden alınmış referans içerik."""
    return {
        "bicim": "B1",
        "kategori_kodu": "EV_SAHIBI_VE_KIRACI",
        "rozet_metni": "TAHLİYE REHBERİ // BOŞ TARİH",
        "yasal_dayanak": "Türk Borçlar Kanunu md. 352/1",
        "manset_parca_1": "Boş tarihe atılan",
        "manset_vurgu": "O İMZA SİZİ",
        "manset_parca_2": "evden çıkarabilir",
        "spot": "Boş tarihli tahliye taahhütnamesi geçerlidir. Ancak sözleşmeyle aynı gün imzalandığı ispat edilirse geçersiz sayılabilir.",
        "slayt_2_detay": {
            "baslik_satir_1": "Boş tarihin",
            "baslik_vurgu": "HUKUKİ ETKİSİ",
            "kart_1": {
                "etiket": "KİRACININ BİLMEDİĞİ RİSK", "renk": "kirmizi",
                "baslik": "Sonradan doldurulan tarih geçerlidir",
                "aciklama": "Yargıtay boş bırakılan tarihin sonradan doldurulmasını hukuka aykırı bulmaz. Kiracı imza atarak bu riski üstlenmiş sayılır.",
            },
            "kart_2": {
                "etiket": "YARGITAY'IN İSTİSNASI", "renk": "yesil",
                "baslik": "Sözleşmeyle aynı gün imza tespiti",
                "aciklama": "Sözleşmeyle aynı gün atılan imzalar ispatlanırsa geçersiz sayılır. Yargıtay bu durumu irade fesadı olarak kabul eder.",
            },
        },
        "slayt_3_cozum": {
            "tip": "adim_adim_rehber",
            "baslik_ust": "Hak kaybı yaşamamak için",
            "baslik_vurgu": "ÖNLEME REHBERİ",
            "maddeler": [
                {"no": "01", "baslik": "Tarihleri mutlaka elle doldurun", "aciklama": "Taahhütnameyi imzalarken düzenleme ve tahliye tarihlerini kendi el yazınızla yazın."},
                {"no": "02", "baslik": "Teslim tutanağı düzenleyin", "aciklama": "Sözleşme ve taahhütnamenin hangi tarihte teslim edildiğini yazılı olarak kayıt altına alın."},
                {"no": "03", "baslik": "İspat araçlarını saklayın", "aciklama": "İmza gününü kanıtlayabilecek mesajlaşma ve şahit beyanlarını saklayın."},
            ],
        },
        "slayt_4_cta": {
            "slogan_parca_1": "Doğru adımlarla",
            "slogan_vurgu": "GÜVENLİ KİRALAMA",
            "aciklama": "Silivri ve Trakya genelinde mülk yönetimi ve hukuki süreçlerde uzman kadromuzla yanınızdayız.",
            "kaydet_metni": "İhtiyaç anında başvurmak için kaydedin.",
        },
    }


def _alanlari_donustur(veri: Any, donustur) -> Any:
    """Sözlükteki tüm metin alanlarını özyinelemeli dönüştürür."""
    if isinstance(veri, dict):
        return {k: _alanlari_donustur(v, donustur) for k, v in veri.items()}
    if isinstance(veri, list):
        return [_alanlari_donustur(v, donustur) for v in veri]
    if isinstance(veri, str):
        return donustur(veri)
    return veri


UZUN_KELIME = "Muvaffakiyetsizleştiricileştiriveremeyebileceklerimizdenmişsinizcesine"


def stres_vakalari() -> List[Tuple[str, Dict[str, Any]]]:
    """Geçerli ama uç hacimli içerikler. Hepsi ÇİZİLEBİLMELİ."""
    v: List[Tuple[str, Dict[str, Any]]] = []

    v.append(("referans", _temel()))

    # Tüm metinler tek kelime
    v.append(("asgari_tek_kelime", _alanlari_donustur(_temel(), lambda s: "Kısa")))

    # Tüm metinler boş
    v.append(("tumu_bos", _alanlari_donustur(_temel(), lambda s: "")))

    # Bütçenin iki katı
    v.append(("iki_kat_uzun", _alanlari_donustur(_temel(), lambda s: (s + " " + s) if s else s)))

    # Bütçenin on katı — sığdırma mantığının sınırı
    v.append(("on_kat_uzun", _alanlari_donustur(_temel(), lambda s: " ".join([s] * 10) if s else s)))

    # Sarılamayan tek uzun kelime
    v.append(("sarilamayan_kelime", _alanlari_donustur(_temel(), lambda s: UZUN_KELIME if s else s)))

    # Aynı kelimenin tekrarıyla devasa paragraf
    d = _temel()
    d["slayt_2_detay"]["kart_1"]["aciklama"] = (UZUN_KELIME + " ") * 40
    v.append(("devasa_paragraf", d))

    # 10 adım — planlayıcı genişletilmiş yola gider
    d = _temel()
    d["slayt_3_cozum"]["maddeler"] = [
        {"no": f"{i:02d}", "baslik": f"{i}. adımın başlığı burada duruyor",
         "aciklama": f"{i}. adımın açıklaması. Uygulanabilir, somut ve tek cümlelik olması beklenir."}
        for i in range(1, 11)
    ]
    v.append(("on_adim", d))

    # Tek adım
    d = _temel()
    d["slayt_3_cozum"]["maddeler"] = [d["slayt_3_cozum"]["maddeler"][0]]
    v.append(("tek_adim", d))

    # Hiç adım yok
    d = _temel()
    d["slayt_3_cozum"]["maddeler"] = []
    v.append(("adim_yok", d))

    # Türkçe karakter yükü + büyük/küçük İ-I
    d = _temel()
    tr = "ĞÜŞİÖÇIığüşiöç ışık İstanbul IĞDIR ÖĞÜŞÇİ"
    d = _alanlari_donustur(d, lambda s: (s + " " + tr) if s else s)
    v.append(("turkce_glif_yuku", d))

    # B2 finansal tablo yolu
    d = _temel()
    d["bicim"] = "B2"
    d["slayt_3_cozum"] = {
        "tip": "finansal_tablo",
        "baslik_ust": "Beş yıllık vadede",
        "baslik_vurgu": "KONUT MU ARSA MI",
        "sol_kolon_veriler": [("Gelir Tipi:", "Düzenli kira akışı")] * 5,
        "sag_kolon_veriler": [("Gelir Tipi:", "Doğrudan gelir yok")] * 5,
        "stratejist_notu": "Kısa vadeli nakit ihtiyacınız yoksa gelişim aksındaki arsa öne geçer.",
    }
    v.append(("finansal_tablo", d))

    # B3 tek kare
    d = _temel()
    d["bicim"] = "B3"
    v.append(("b3_tek_kare", d))

    return v


def sabotaj_vakalari() -> List[Tuple[str, Dict[str, Any]]]:
    """Bozuk, eksik ve düşmanca girdiler. Hiçbiri ÇÖKMEMELİ."""
    v: List[Tuple[str, Dict[str, Any]]] = []

    # Tamamen boş sözlük
    v.append(("bos_sozluk", {}))

    # Sadece biçim bilgisi
    v.append(("yalniz_bicim", {"bicim": "B1"}))

    # Her metin alanı None
    v.append(("tum_alanlar_none", _alanlari_donustur(_temel(), lambda s: None)))

    # Metin beklenen yerde sayı
    v.append(("metin_yerine_sayi", _alanlari_donustur(_temel(), lambda s: 12345)))

    # Metin beklenen yerde liste
    v.append(("metin_yerine_liste", _alanlari_donustur(_temel(), lambda s: ["a", "b"])))

    # Metin beklenen yerde sözlük
    v.append(("metin_yerine_sozluk", _alanlari_donustur(_temel(), lambda s: {"x": 1})))

    # kart_1 sözlük değil
    d = _temel(); d["slayt_2_detay"]["kart_1"] = "ben bir kart değilim"
    v.append(("kart_metin", d))

    # slayt_2_detay tamamen yanlış tip
    d = _temel(); d["slayt_2_detay"] = ["liste", "geldi"]
    v.append(("detay_liste", d))

    # maddeler liste değil
    d = _temel(); d["slayt_3_cozum"]["maddeler"] = "01 02 03"
    v.append(("maddeler_metin", d))

    # maddeler içinde sözlük olmayan öğeler
    d = _temel(); d["slayt_3_cozum"]["maddeler"] = ["a", 5, None, {"baslik": "geçerli", "aciklama": "tek geçerli madde"}]
    v.append(("maddeler_karisik", d))

    # slayt_3_cozum None
    d = _temel(); d["slayt_3_cozum"] = None
    v.append(("cozum_none", d))

    # Kontrol karakterleri ve satır sonları
    d = _alanlari_donustur(_temel(), lambda s: "\x00satır\r\nsonu\tsekme\x1b[31mansi" if s else s)
    v.append(("kontrol_karakterleri", d))

    # Fontta olmayan glifler: emoji, Çince, Arapça, matematik sembolleri
    d = _alanlari_donustur(_temel(), lambda s: "👉📌🎯 中文测试 عربى ∑∫≠ 🏠🔑" if s else s)
    v.append(("eksik_glifler", d))

    # Unicode yön değiştirici (görsel karıştırma denemesi)
    d = _alanlari_donustur(_temel(), lambda s: "normal‮ters‬ metin" if s else s)
    v.append(("rtl_override", d))

    # Şablon / enjeksiyon benzeri dizeler
    d = _alanlari_donustur(_temel(), lambda s: "{{kotu}} <script>x</script> %s {0} ${env}" if s else s)
    v.append(("sablon_enjeksiyonu", d))

    # 1 MB'lık tek alan
    d = _temel(); d["spot"] = "A" * 1_000_000
    v.append(("bir_mb_metin", d))

    # Geçersiz renk adı ve absürt madde numaraları
    d = _temel()
    d["slayt_2_detay"]["kart_1"]["renk"] = "mor-ötesi"
    d["slayt_3_cozum"]["maddeler"][0]["no"] = -7
    d["slayt_3_cozum"]["maddeler"][1]["no"] = "ÇOKUZUNNUMARA"
    d["slayt_3_cozum"]["maddeler"][2]["no"] = None
    v.append(("gecersiz_deger", d))

    # Bilinmeyen kategori (arka plan seçimi)
    d = _temel(); d["kategori_kodu"] = "OLMAYAN_KATEGORI_XYZ"
    v.append(("bilinmeyen_kategori", d))

    # Görsel URL'si bozuk / erişilemez
    d = _temel(); d["gorsel_url"] = "https://ornek.gecersiz.alan/olmayan.jpg"
    v.append(("bozuk_gorsel_url", d))

    # Sadece boşluk karakterleri
    d = _alanlari_donustur(_temel(), lambda s: "        " if s else s)
    v.append(("yalniz_bosluk", d))

    return v


# =========================================================================
# DENETİMLER
# =========================================================================

def _zemin_rengi(img: Image.Image) -> Tuple[int, int, int]:
    """Köşelerden zemin rengini tahmin eder."""
    w, h = img.size
    koseler = [img.getpixel((2, 2)), img.getpixel((w - 3, 2)),
               img.getpixel((2, h - 3)), img.getpixel((w - 3, h - 3))]
    return max(set(koseler), key=koseler.count)


def _tasma_denetle(yol: Path, tur: str) -> Optional[str]:
    """Metnin güvenli alan dışına piksel taşırıp taşırmadığını ölçer.

    Yalnızca düz zeminli slaytlarda anlamlı; kapak ve finansal tablo fotoğraf
    veya gradyan taşıdığı için zemin rengi tanımlı değil.
    """
    if tur not in DUZ_ZEMIN_SLAYTLARI:
        return None

    img = Image.open(yol).convert("RGB")
    w, h = img.size
    zemin = _zemin_rengi(img)
    esik = 42  # JPEG sıkıştırma gürültüsü bu eşiğin altında kalır

    def kirli(x: int, y: int) -> bool:
        r, g, b = img.getpixel((x, y))
        return (abs(r - zemin[0]) + abs(g - zemin[1]) + abs(b - zemin[2])) > esik

    with mi.tuval((w, h)):
        yer = mi._yerlesim()
    kenar = yer["kenar"]

    ihlaller = []

    # Sol/sağ kenar boşluğu — logo ve rozet üst şeritte, o bölge hariç
    pay = 10
    for y in range(yer["ust"], min(h - 8, yer["alt_bar"] + 70), 3):
        for x in list(range(0, max(1, kenar - pay), 3)) + list(range(w - kenar + pay, w, 3)):
            if kirli(x, y):
                ihlaller.append(f"yan kenar (x={x}, y={y})")
                break
        if ihlaller:
            break

    # İçerik alanı ile alt bar arasındaki tampon temiz olmalı.
    # Bu bandı denetlemezsek gövde metni alt şerit yazısının üstüne biner ve
    # "alt bar + 72" kontrolünden sıyrılır — kontakt föyünde görülen kusur buydu.
    for y in range(yer["alt"] + 18, max(yer["alt"] + 19, yer["alt_bar"] - 4), 3):
        for x in range(kenar, w - kenar, 6):
            if kirli(x, y):
                ihlaller.append(f"içerik alt bara giriyor (y={y})")
                break
        if ihlaller:
            break

    # Alt bar yazısının da altı temiz olmalı
    for y in range(min(h - 1, yer["alt_bar"] + 72), h, 3):
        for x in range(kenar, w - kenar, 6):
            if kirli(x, y):
                ihlaller.append(f"alt taşma (y={y})")
                break
        if ihlaller:
            break

    return "; ".join(ihlaller[:2]) if ihlaller else None


def _bos_mu(yol: Path, tur: str) -> bool:
    """Slayt neredeyse tamamen tek renk mi (içerik kaybolmuş mu)."""
    if tur not in DUZ_ZEMIN_SLAYTLARI:
        return False
    img = Image.open(yol).convert("RGB")
    w, h = img.size
    zemin = _zemin_rengi(img)
    farkli = 0
    for y in range(0, h, 7):
        for x in range(0, w, 7):
            r, g, b = img.getpixel((x, y))
            if (abs(r - zemin[0]) + abs(g - zemin[1]) + abs(b - zemin[2])) > 42:
                farkli += 1
                if farkli > 120:
                    return False
    return True


# =========================================================================
# KOŞUCU
# =========================================================================

def vaka_calistir(ad: str, veri: Dict[str, Any], olcu: str) -> Dict[str, Any]:
    sonuc: Dict[str, Any] = {"vaka": ad, "olcu": olcu, "durum": "GEÇTİ", "notlar": []}
    beklenen = mi.TUVAL_OLCULERI[olcu]
    onek = f"stres/{olcu}_{ad}"

    t0 = time.time()
    try:
        # Motor girdiyi bozmamalı; kopya vererek yan etkiyi de denetliyoruz
        girdi = copy.deepcopy(veri)
        yollar = mi.otorite_gonderi_slaytlari_uret(girdi, cikti_onek=onek, olcu=olcu)
    except mi.EksikIcerik as e:
        # Bilinçli durma (2026-09-25): boş içerik ya da okunabilir puntoda sığmayan
        # metin yayına çıkmaz. Eskiden kapak metni tuvalden taşıyordu; bu test kapağı
        # piksel denetiminden muaf tuttuğu için göremiyordu (bkz. gorsel_denetim.py).
        sonuc["durum"] = "DURDU"
        sonuc["notlar"].append(f"{type(e).__name__}: {e}")
        sonuc["sure"] = time.time() - t0
        return sonuc
    except Exception as e:
        sonuc["durum"] = "ÇÖKTÜ"
        sonuc["notlar"].append(f"{type(e).__name__}: {e}")
        sonuc["iz"] = traceback.format_exc(limit=4)
        sonuc["sure"] = time.time() - t0
        return sonuc

    sonuc["sure"] = time.time() - t0
    sonuc["slayt"] = len(yollar)

    if not yollar:
        sonuc["durum"] = "BAŞARISIZ"
        sonuc["notlar"].append("hiç slayt üretilmedi")
        return sonuc

    for yol in yollar:
        tur = yol.stem.split("_")[-1]
        if not yol.exists() or yol.stat().st_size == 0:
            sonuc["durum"] = "BAŞARISIZ"
            sonuc["notlar"].append(f"{yol.name}: dosya yok/boş")
            continue

        img = Image.open(yol)
        if img.size != beklenen:
            sonuc["durum"] = "BAŞARISIZ"
            sonuc["notlar"].append(f"{yol.name}: ölçü {img.size} ≠ {beklenen}")

        tasma = _tasma_denetle(yol, tur)
        if tasma:
            sonuc["durum"] = "BAŞARISIZ"
            sonuc["notlar"].append(f"{yol.name}: TAŞMA — {tasma}")

        if _bos_mu(yol, tur):
            if sonuc["durum"] == "GEÇTİ":
                sonuc["durum"] = "UYARI"
            sonuc["notlar"].append(f"{yol.name}: içerik boş görünüyor")

    # Girdinin bozulmadığını doğrula (motor çağıranın verisini kirletmemeli)
    return sonuc


def main() -> int:
    ap = argparse.ArgumentParser(description="EDM görsel motoru stres ve sabotaj testi")
    ap.add_argument("--olcu", choices=sorted(mi.TUVAL_OLCULERI), default=None,
                    help="Tek ölçüde çalıştır (varsayılan: hepsi)")
    ap.add_argument("--hizli", action="store_true", help="Sabotaj vakalarını atla")
    ap.add_argument("--vaka", default=None, help="Tek bir vakayı adıyla çalıştır")
    args = ap.parse_args()

    CIKTI.mkdir(parents=True, exist_ok=True)
    olculer = [args.olcu] if args.olcu else sorted(mi.TUVAL_OLCULERI)

    paketler = [("STRES", stres_vakalari())]
    if not args.hizli:
        paketler.append(("SABOTAJ", sabotaj_vakalari()))

    tum: List[Dict[str, Any]] = []
    for paket_adi, vakalar in paketler:
        if args.vaka:
            vakalar = [(a, v) for a, v in vakalar if a == args.vaka]
            if not vakalar:
                continue
        print(f"\n{'=' * 78}\n{paket_adi}  ({len(vakalar)} vaka × {len(olculer)} ölçü)\n{'=' * 78}")
        print(f"{'VAKA':26} {'ÖLÇÜ':9} {'SLAYT':>6} {'SÜRE':>7}  DURUM")
        print("-" * 78)
        for ad, veri in vakalar:
            for olcu in olculer:
                s = vaka_calistir(ad, veri, olcu)
                s["paket"] = paket_adi
                tum.append(s)
                isaret = {"GEÇTİ": "✓", "UYARI": "!", "DURDU": "■", "BAŞARISIZ": "✗", "ÇÖKTÜ": "✗✗"}[s["durum"]]
                print(f"{ad:26} {olcu:9} {s.get('slayt', '-'):>6} {s['sure']:>6.2f}s  {isaret} {s['durum']}")
                for n in s["notlar"][:3]:
                    print(f"{'':44}   → {n}")

    print(f"\n{'=' * 78}\nÖZET\n{'=' * 78}")
    for durum in ("GEÇTİ", "UYARI", "DURDU", "BAŞARISIZ", "ÇÖKTÜ"):
        n = sum(1 for s in tum if s["durum"] == durum)
        if n:
            print(f"  {durum:11} {n:3} / {len(tum)}")

    sorunlu = [s for s in tum if s["durum"] in ("BAŞARISIZ", "ÇÖKTÜ")]
    if sorunlu:
        print(f"\n{'-' * 78}\nSORUNLAR\n{'-' * 78}")
        for s in sorunlu:
            print(f"\n[{s['paket']}] {s['vaka']} / {s['olcu']} — {s['durum']}")
            for n in s["notlar"]:
                print(f"   {n}")
            if "iz" in s:
                for satir in s["iz"].strip().splitlines()[-4:]:
                    print(f"   | {satir}")
        return 1

    en_yavas = max(tum, key=lambda s: s["sure"])
    print(f"\n  en yavaş: {en_yavas['vaka']} / {en_yavas['olcu']} — {en_yavas['sure']:.2f}s")
    print(f"  çıktılar: {CIKTI}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
