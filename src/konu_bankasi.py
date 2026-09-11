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

# ICERIK-SISTEMI.md §8 — haftalık takvim.
# Pazartesi=0 ... Pazar=6. Hafta sonu paylaşım yok; kitle sektörel içeriğe
# hafta içi bakıyor, cumartesi/pazar erişimi düşürüyor.
TAKVIM: Dict[int, Dict[str, Any]] = {
    0: {"sutun": "S2", "bicim": "B1"},
    1: {"sutun": "S4", "bicim": "B3"},
    2: {"sutun": "S1", "bicim": "B1"},
    3: {"sutun": "S3", "bicim": "B3"},
    4: {"sutun": ("S2", "S4"), "bicim": "B2"},
}

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


def sonraki_konu(
    gun: Optional[int] = None,
    sutun: Optional[str] = None,
    bicim: Optional[str] = None,
    bekleme_gun: int = 120,
) -> Optional[Dict[str, Any]]:
    """Takvime uygun, yakın zamanda kullanılmamış bir konu seçer.

    Seçim sırası:
      1. Takvimin istediği sütun+biçim, hiç kullanılmamış
      2. Aynı sütun, biçim serbest, hiç kullanılmamış
      3. Herhangi bir sütun, hiç kullanılmamış
      4. `bekleme_gun`den eski, en uzun süredir dokunulmamış konu

    Havuz tükendiğinde durmak yerine en eskiye dönmek bilinçli: bir konu dört ay
    sonra farklı kancayla yeniden işlenebilir ve takipçi kitlesi bu sürede değişir.
    """
    tabloyu_kur()
    havuz = havuzu_yukle()
    if not havuz:
        return None

    if gun is None:
        gun = date.today().weekday()

    plan = TAKVIM.get(gun)
    if sutun is None and plan:
        p_sutun = plan["sutun"]
        sutun = random.choice(p_sutun) if isinstance(p_sutun, tuple) else p_sutun
    if bicim is None and plan:
        bicim = plan["bicim"]

    gecmis = _kullanim_gecmisi()
    bakir = [k for k in havuz if k["kod"] not in gecmis]

    for aday_kume in (
        [k for k in bakir if k["sutun"] == sutun and k["bicim"] == bicim],
        [k for k in bakir if k["sutun"] == sutun],
        bakir,
    ):
        if aday_kume:
            secim = random.choice(aday_kume)
            log.info("Konu seçildi: %s — %s", secim["kod"], secim["baslik"])
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
    return {
        "toplam": len(havuz),
        "kullanilmis": len(gecmis),
        "bakir": len(bakir),
        "bakir_sutun_dagilimi": dict(sorted(sutun_dagilim.items())),
        "kalan_hafta": round(len(bakir) / 5, 1),
    }
