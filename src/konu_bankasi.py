"""
konu_bankasi.py — Evergreen Konu Havuzu Seçicisi

Botun konu kaynağı. Model artık konu uydurmaz; buradaki hazır brief'i işler.

Sistem kuralları ve takvim: ICERIK-SISTEMI.md
Havuz: data/konu_bankasi.yaml
"""

from __future__ import annotations

import logging
import random
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import yaml

from . import config, db

log = logging.getLogger(__name__)

BANKA_YOLU = config.yol_al("data/konu_bankasi.yaml")

# Haftalık 7 Günlük Takvim (Pazartesi=0 ... Pazar=6).
# Her gün 1 Otorite Postu (Görsel/Carousel) + 1 Dikey Video (Reels).
TAKVIM: Dict[int, Dict[str, Any]] = {
    0: {"sutun": "S2", "bicim": "B1"},           # Pazartesi: Sözlük
    1: {"sutun": "S4", "bicim": "B3"},           # Salı: Net Cevap Rehberi
    2: {"sutun": "S1", "bicim": "B1"},           # Çarşamba: Nedir Doğrusu?
    3: {"sutun": "S3", "bicim": "B1"},           # Perşembe: Sözlük / Mevzuat
    4: {"sutun": ("S2", "S4"), "bicim": "B2"},   # Cuma: Vaka Analizi (Carousel)
    5: {"sutun": "S1", "bicim": "B3"},           # Cumartesi: Nedir Doğrusu? / Yatırım
    6: {"sutun": "S4", "bicim": "B3"},           # Pazar: Net Cevap Rehberi
}

GUN_FORMATLARI: Dict[int, str] = {
    0: "sozluk",
    1: "net_cevap",
    2: "nedir_dogrusu",
    3: "sozluk",
    4: "vaka",
    5: "nedir_dogrusu",
    6: "net_cevap",
}

# Günde TEK içerik (2026-09-24 kararı; önceden günde 3 slot vardı). Format
# altı günlük bir döngüde döner. B1 iki kez: denetimde her kanalda en yüksek
# erişim çok slaytlı B1'deydi. Sözlük tek kare kaldığı için döngüde bir kez.
BILGILENDIRICI_FORMATLAR: List[str] = [
    "b1",
    "nedir_dogrusu",
    "net_cevap",
    "b1",
    "vaka",
    "sozluk",
]


def _son_sira() -> Optional[int]:
    """Döngüde en son kullanılan sıra. Aynı format iki kez geçtiği için sıra
    numarası tutulur; eski kayıtta yalnızca format adı vardı."""
    ham = db.ayar_oku("bilgilendirici_sira")
    try:
        sira = int(str(ham))
        if 0 <= sira < len(BILGILENDIRICI_FORMATLAR):
            return sira
    except (TypeError, ValueError):
        pass
    son_format = db.ayar_oku("son_bilgilendirici_format")
    if son_format in BILGILENDIRICI_FORMATLAR:
        return BILGILENDIRICI_FORMATLAR.index(son_format)
    return None


def _siradaki_sira() -> int:
    son = _son_sira()
    return 0 if son is None else (son + 1) % len(BILGILENDIRICI_FORMATLAR)


def siradaki_bilgilendirici_format() -> str:
    """Döngüdeki sıradaki format: b1 → nedir_dogrusu → net_cevap → b1 → vaka → sozluk → b1 …"""
    return BILGILENDIRICI_FORMATLAR[_siradaki_sira()]


def bilgilendirici_format_kaydet(format_turu: str) -> None:
    """Kullanılan formatı döngüdeki sırasıyla kaydeder."""
    if format_turu not in BILGILENDIRICI_FORMATLAR:
        return
    sira = _siradaki_sira()
    if BILGILENDIRICI_FORMATLAR[sira] != format_turu:
        sira = BILGILENDIRICI_FORMATLAR.index(format_turu)
    db.ayar_yaz("bilgilendirici_sira", str(sira))
    db.ayar_yaz("son_bilgilendirici_format", format_turu)


def gun_icin_format(gun: Optional[int] = None) -> str:
    """Günün indeksine (0-6) göre aktif otorite format türünü döner."""
    if gun is None:
        # Türkiye saatine göre gün (UTC+3)
        simdi_tr = datetime.now(timezone.utc) + timedelta(hours=3)
        gun = simdi_tr.weekday()
    return GUN_FORMATLARI.get(gun, "sozluk")

_havuz_onbellek: Optional[List[Dict[str, Any]]] = None


def tabloyu_kur() -> None:
    """Konu kullanım geçmişi tablosunu oluşturur.

    Ayrı tablo tutuluyor çünkü `haberler` tablosu URL benzersizliğine dayanıyor;
    evergreen konuların URL'si yok ve aynı konu aylar sonra tekrar işlenebilmeli.
    """
    with db._baglanti_al() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS konu_gecmisi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                konu_kodu TEXT NOT NULL,
                kullanim_tarihi TEXT NOT NULL,
                haber_id INTEGER,
                sonuc TEXT DEFAULT 'uretildi'
            );
            CREATE INDEX IF NOT EXISTS idx_konu_kodu ON konu_gecmisi(konu_kodu);

            -- Beslemeden madenlenen konu adayları.
            -- Haber akışının asıl değeri haber değil, insanların NE ARADIĞI:
            -- "Temellük nedir?" gibi başlıklar bankada olmayan konuları gösteriyor.
            CREATE TABLE IF NOT EXISTS konu_adaylari (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                baslik TEXT NOT NULL,
                aci TEXT,
                sutun TEXT,
                bicim TEXT,
                kanca_kalip TEXT,
                mevzuat TEXT,
                yerel TEXT,
                kaynak_url TEXT UNIQUE,
                eklenme_tarihi TEXT NOT NULL,
                durum TEXT DEFAULT 'bekliyor'
            );
        """)


def havuzu_yukle(tazele: bool = False) -> List[Dict[str, Any]]:
    """YAML havuzunu okur ve doğrular. Bozuk kayıt havuzu tamamen düşürmez, atlanır."""
    global _havuz_onbellek
    if _havuz_onbellek is not None and not tazele:
        return _havuz_onbellek

    if not BANKA_YOLU.exists():
        log.error("Konu bankası bulunamadı: %s", BANKA_YOLU)
        _havuz_onbellek = []
        return []

    with open(BANKA_YOLU, "r", encoding="utf-8") as f:
        ham = yaml.safe_load(f) or {}

    zorunlu = ("kod", "sutun", "bicim", "baslik", "aci", "kanca_kalip")
    gecerli: List[Dict[str, Any]] = []
    kodlar = set()

    for k in ham.get("konular", []):
        eksik = [a for a in zorunlu if not k.get(a)]
        if eksik:
            log.warning("Konu atlandı (eksik alan %s): %s", eksik, k.get("kod", "?"))
            continue
        if k["kod"] in kodlar:
            log.warning("Konu atlandı (tekrar eden kod): %s", k["kod"])
            continue
        kodlar.add(k["kod"])
        gecerli.append(k)

    log.info("Konu bankası yüklendi: %d konu", len(gecerli))
    _havuz_onbellek = gecerli
    return gecerli


# Başarısız denemenin konuyu kilitleyeceği süre (gün).
# Kısa tutuluyor: amaç bozuk bir brief'i ertesi gün tekrar denememek, ama geçici
# bir API kesintisinin konuyu KALICI olarak yakmasını da önlemek.
HATA_BEKLEME_GUNU = 3


def _kullanim_gecmisi() -> Dict[str, str]:
    """Konu kodu -> en son geçerli kullanım tarihi (ISO).

    Başarısız denemeler (`sonuc='hata'`) yalnızca `HATA_BEKLEME_GUNU` boyunca
    sayılır. Öncesinde her hata kaydı konuyu kalıcı olarak tüketiyordu: Gemini
    tarafındaki bir kesinti (2026-09-11'de dört model birden 503 verdi) 61
    konuluk bankayı sessizce eritebilirdi. Kesinti konunun kalitesi hakkında
    bir şey söylemez.
    """
    try:
        esik = (datetime.now(timezone.utc) - timedelta(days=HATA_BEKLEME_GUNU)).isoformat()
        with db._baglanti_al() as conn:
            satirlar = conn.execute(
                """SELECT konu_kodu, MAX(kullanim_tarihi) AS son
                   FROM konu_gecmisi
                   WHERE sonuc != 'hata' OR kullanim_tarihi > ?
                   GROUP BY konu_kodu""",
                (esik,),
            ).fetchall()
        return {s["konu_kodu"]: s["son"] for s in satirlar}
    except sqlite3.Error as e:
        log.warning("Konu geçmişi okunamadı: %s", e)
        return {}


def _gun_farki(iso_tarih: str) -> float:
    try:
        dt = datetime.fromisoformat(iso_tarih)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0
    except Exception:
        return 9999.0


def _son_kullanilan_sutunlar(limit: int = 3) -> List[str]:
    """Son paylaşılan konuların sütunlarını döner (rotasyon dengesi için)."""
    try:
        havuz_map = {k["kod"]: k.get("sutun") for k in havuzu_yukle()}
        with db._baglanti_al() as conn:
            satirlar = conn.execute(
                "SELECT konu_kodu FROM konu_gecmisi WHERE sonuc != 'hata' ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [havuz_map[s["konu_kodu"]] for s in satirlar if s["konu_kodu"] in havuz_map]
    except Exception:
        return []


def _engellenen_konular() -> set[str]:
    """Üretime alınmayacak konular: kullanıcının 'Çöpe At' ile engelledikleri ve
    konu bankasında `engel` alanı taşıyanlar (dayanağı doğrulanamayan konular —
    2026-09-24 mevzuat denetiminde eklendi)."""
    yaml_engel = {k["kod"] for k in havuzu_yukle() if k.get("engel")}
    try:
        with db._baglanti_al() as conn:
            satirlar = conn.execute(
                "SELECT DISTINCT konu_kodu FROM konu_gecmisi WHERE sonuc IN ('cope_at', 'engellendi')"
            ).fetchall()
        return yaml_engel | {s["konu_kodu"] for s in satirlar}
    except Exception:
        return yaml_engel


def sonraki_konu(
    gun: Optional[int] = None,
    sutun: Optional[str] = None,
    bicim: Optional[str] = None,
    bekleme_gun: int = 120,
) -> Optional[Dict[str, Any]]:
    """Akıllı dinamik rotasyonla yakın zamanda kullanılmamış bir konu seçer.
    
    Haftanın gününe katı kilitlenmez; sütunlar (S1-S4) arasında dengeli rotasyon yapar
    ve arka arkaya aynı sütunun gelmesini önler.
    Çöpe atılan/engellenen konular havuza ASLA bir daha dönmez.
    """
    tabloyu_kur()
    ham_havuz = havuzu_yukle()
    if not ham_havuz:
        return None

    engelliler = _engellenen_konular()
    havuz = [k for k in ham_havuz if k["kod"] not in engelliler]
    if not havuz:
        log.warning("Havuzdaki tüm konular engellenmiş veya boş.")
        return None

    gecmis = _kullanim_gecmisi()
    bakir = [k for k in havuz if k["kod"] not in gecmis]
    son_sutunlar = _son_kullanilan_sutunlar(limit=2)

    # Eğer sütun özellikle belirtilmemişse, son kullanılan sütunları dışlayarak çeşitlilik sağla
    if sutun is None:
        tum_sutunlar = ["S1", "S2", "S3", "S4", "S5"]
        tercih_sutunlar = [s for s in tum_sutunlar if not son_sutunlar or s != son_sutunlar[0]]
        if gun is not None and gun in TAKVIM:
            p_sutun = TAKVIM[gun]["sutun"]
            oneri = random.choice(p_sutun) if isinstance(p_sutun, tuple) else p_sutun
            if oneri in tercih_sutunlar:
                sutun = oneri
        if sutun is None:
            sutun = random.choice(tercih_sutunlar if tercih_sutunlar else tum_sutunlar)

    for aday_kume in (
        [k for k in bakir if k["sutun"] == sutun and (bicim is None or k["bicim"] == bicim)],
        [k for k in bakir if k["sutun"] == sutun],
        [k for k in bakir if not son_sutunlar or k["sutun"] != son_sutunlar[0]],
        bakir,
    ):
        if aday_kume:
            secim = random.choice(aday_kume)
            log.info("Konu seçildi: %s [%s/%s] — %s", secim["kod"], secim["sutun"], secim["bicim"], secim["baslik"])
            return secim

    # Havuz tükendi: bekleme süresini doldurmuş, en uzun süredir kullanılmayan konu
    eskiler = [(k, _gun_farki(gecmis[k["kod"]])) for k in havuz if k["kod"] in gecmis]
    uygun = [(k, y) for k, y in eskiler if y >= bekleme_gun]
    if not uygun:
        log.warning(
            "Havuzdaki tüm konular son %d gün içinde kullanılmış. Konu bankasına yeni konu eklenmeli.",
            bekleme_gun,
        )
        return None

    secim = max(uygun, key=lambda t: t[1])[0]
    log.info("Konu tekrar dolaşımda: %s — %s", secim["kod"], secim["baslik"])
    return secim


def sonraki_finans_konusu(bekleme_gun: int = 120) -> Optional[Dict[str, Any]]:
    """Finans, bankacılık, faiz, konut kredisi veya yakın sektörleri ele alan konuyu seçer.
    
    Önce S5 sütunundaki bakir konulara bakar; bulamazsa havuzdaki finans/banka/kredi
    anahtar kelimeleri taşıyan diğer konuları da tarar.
    """
    konu = sonraki_konu(sutun="S5", bekleme_gun=bekleme_gun)
    if konu:
        return konu

    ham_havuz = havuzu_yukle()
    engelliler = _engellenen_konular()
    gecmis = _kullanim_gecmisi()
    finans_anahtarlar = ("kredi", "banka", "faiz", "ipotek", "enflasyon", "finans", "bddk", "tcmb", "ekspertiz")
    adaylar = [
        k for k in ham_havuz
        if k["kod"] not in engelliler
        and k["kod"] not in gecmis
        and any(a in (k.get("baslik", "") + " " + k.get("aci", "")).lower() for a in finans_anahtarlar)
    ]
    if adaylar:
        return random.choice(adaylar)
    return sonraki_konu(sutun="S5", bekleme_gun=30)



def kullanildi_isaretle(konu_kodu: str, haber_id: Optional[int] = None, sonuc: str = "uretildi") -> None:
    """Konuyu kullanıldı olarak kaydeder. Üretim başarısızsa `sonuc='hata'` geçilir;
    hatalı denemeler de geçmişe yazılır ki aynı bozuk konu ertesi gün tekrar denenmesin."""
    tabloyu_kur()
    with db._baglanti_al() as conn:
        conn.execute(
            "INSERT INTO konu_gecmisi (konu_kodu, kullanim_tarihi, haber_id, sonuc) VALUES (?, ?, ?, ?)",
            (konu_kodu, datetime.now(timezone.utc).isoformat(), haber_id, sonuc),
        )


def aday_kaydet(aday: Dict[str, Any]) -> Optional[int]:
    """Konu adayını kaydeder. Aynı kaynak URL'si ikinci kez eklenmez."""
    tabloyu_kur()
    try:
        with db._baglanti_al() as conn:
            cur = conn.execute(
                """INSERT OR IGNORE INTO konu_adaylari
                   (baslik, aci, sutun, bicim, kanca_kalip, mevzuat, yerel, kaynak_url, eklenme_tarihi)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    aday.get("baslik", ""), aday.get("aci", ""), aday.get("sutun"),
                    aday.get("bicim"), aday.get("kanca_kalip"), aday.get("mevzuat"),
                    aday.get("yerel"), aday.get("_kaynak_url"),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            return cur.lastrowid if cur.rowcount else None
    except sqlite3.Error as e:
        log.warning("Konu adayı kaydedilemedi: %s", e)
        return None


def bekleyen_adaylar(limit: int = 20) -> List[Dict[str, Any]]:
    tabloyu_kur()
    with db._baglanti_al() as conn:
        satirlar = conn.execute(
            "SELECT * FROM konu_adaylari WHERE durum='bekliyor' ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(s) for s in satirlar]


def aday_yaml_blogu(aday: Dict[str, Any], kod: str) -> str:
    """Adayı `data/konu_bankasi.yaml`'a yapıştırılabilir bloğa çevirir.

    Otomatik yazmak yerine blok üretiliyor: bankaya giren her konu insan gözünden
    geçmeli. Brief'in kalitesi çıktının kalitesini belirliyor.
    """
    def alan(ad: str, deger: Any, girinti: str = "    ") -> str:
        if deger in (None, "", "null"):
            return f"{girinti}{ad}: null"
        return f'{girinti}{ad}: "{str(deger).replace(chr(34), chr(39))}"'

    return "\n".join([
        f"  - kod: {kod}",
        alan("sutun", aday.get("sutun")),
        alan("bicim", aday.get("bicim")),
        alan("baslik", aday.get("baslik")),
        alan("aci", aday.get("aci")),
        alan("kanca_kalip", aday.get("kanca_kalip")),
        alan("mevzuat", aday.get("mevzuat")),
        alan("yerel", aday.get("yerel")),
    ])


def guncel_mevzuat(konu: Dict[str, Any]) -> Dict[str, Any]:
    """Konunun mevzuat atıflarının güncel metni. Test modunda ağa çıkılmaz."""
    if not konu.get("mevzuat") or config.test_modu():
        return {}
    try:
        from . import mevzuat
        return mevzuat.brief_mevzuati(konu["mevzuat"])
    except Exception as e:
        log.warning("Güncel mevzuat metni alınamadı (%s): %s", konu.get("kod"), e)
        return {}


def brief_metni(konu: Dict[str, Any]) -> str:
    """Konu kaydını modele verilecek brief metnine çevirir."""
    satirlar = [
        f"KONU KODU: {konu['kod']}",
        f"SÜTUN: {konu['sutun']}",
        f"BİÇİM: {konu['bicim']}",
        f"KONU: {konu['baslik']}",
        f"AÇI (içeriğin merkezi budur): {konu['aci']}",
        f"KANCA KALIBI: {konu['kanca_kalip']}",
    ]
    if konu.get("mevzuat"):
        satirlar.append(f"DOĞRULANMIŞ MEVZUAT (aynen kullan): {konu['mevzuat']}")
        guncel = guncel_mevzuat(konu)
        if guncel.get("metin"):
            # Model eski hukuku biliyor: 2026-09-24 denetiminde 9/20 içeriğin ana
            # iddiası, sonradan değişmiş maddelere dayandığı için yanlıştı.
            satirlar.append(
                f"MADDENİN GÜNCEL METNİ (mevzuat.gov.tr, {guncel['cekildi']}). "
                "Eğitim bilginle çelişirse BU METİN geçerlidir. Bu metinde geçmeyen "
                "süre, oran veya çoğunluk yazma:\n" + guncel["metin"]
            )
    else:
        satirlar.append(
            "DOĞRULANMIŞ MEVZUAT: yok. Kanun maddesi numarası YAZMA, 'ilgili mevzuat' de."
        )
    if konu.get("yerel"):
        satirlar.append(f"YEREL BAĞ: {konu['yerel']}")
    if konu.get("veri_kaynagi"):
        satirlar.append(f"VERİ KAYNAĞI: {konu['veri_kaynagi']}")
    else:
        # Rakam odaklı biçimlerde (B2 karşılaştırma, B4 rakam karnesi) veri kaynağı
        # yoksa model boşluğu uydurma oranla dolduruyor. Üretimde "ARSA %300 DAHA
        # hızlı kazandırır" çıktısı görüldü — gerçek bir emlak ofisinin hesabında
        # bu ciddi bir sorumluluk. Yasak biçime göre sertleştirilir.
        if konu.get("bicim") in ("B2", "B4"):
            satirlar.append(
                "VERİ KAYNAĞI: YOK. Bu içerikte SAYISAL ORAN, YÜZDE veya TUTAR VERME. "
                "Karşılaştırmayı niteliksel yap (\"düzenli nakit akışı sağlar\", "
                "\"gideri yok\", \"likiditesi düşüktür\" gibi). Uydurulmuş bir oran "
                "markanın güvenilirliğini doğrudan zedeler."
            )
        else:
            satirlar.append(
                "VERİ KAYNAĞI: yok. Doğrulayamadığın oran veya tutar yazma."
            )
    return "\n".join(satirlar)


def durum_ozeti() -> Dict[str, Any]:
    """Havuzun doluluk durumu — `scripts/konu_durum.py` ve panel için."""
    tabloyu_kur()
    havuz = havuzu_yukle()
    gecmis = _kullanim_gecmisi()
    bakir = [k for k in havuz if k["kod"] not in gecmis]
    sutun_dagilim: Dict[str, int] = {}
    for k in bakir:
        sutun_dagilim[k["sutun"]] = sutun_dagilim.get(k["sutun"], 0) + 1
    # Tüketim hızı varsayılmıyor, son 14 günden ölçülüyor: takvim haftada 5
    # içerikten günde 3 slota çıktığında sabit "/5" hesabı havuzu olduğundan
    # üç kat uzun gösteriyordu.
    son_14 = sum(1 for t in gecmis.values() if _gun_farki(t) <= 14)
    gunluk = son_14 / 14
    return {
        "toplam": len(havuz),
        "kullanilmis": len(gecmis),
        "bakir": len(bakir),
        "bakir_sutun_dagilimi": dict(sorted(sutun_dagilim.items())),
        "gunluk_tuketim": round(gunluk, 2),
        "kalan_gun": round(len(bakir) / gunluk) if gunluk else None,
        "kalan_hafta": round(len(bakir) / gunluk / 7, 1) if gunluk else None,
    }
