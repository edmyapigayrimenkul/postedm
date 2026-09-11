"""
haber_triyaj.py — Haberi Brief'e Çeviren Değerlendirme Katmanı

Anahtar fikir: **haber de konu bankası girdisiyle aynı şekle dönüşür.**

Konu bankası iyi çalışıyor çünkü modele hazır bir brief veriyor: konu, açı,
kanca kalıbı, doğrulanmış mevzuat. Haber tarafında böyle bir şey yoktu —
ham RSS metni doğrudan "bunu otorite içeriğine çevir" diye veriliyordu ve model
açıyı kendisi uydurmak zorunda kalıyordu.

Bu modül aradaki boşluğu dolduruyor. İki aşamalı:

  1. `haber_puanlama.degerlendir()` — ucuz, kural tabanlı ön eleme.
     Reklamı ve konu dışını atar, sütuna oturtur, puanlar.
  2. `triyaj_et()` — yalnızca eşiği geçenlere uygulanan LLM değerlendirmesi.
     "Burada gerçek bir EDM açısı var mı?" sorusunu yanıtlar ve varsa açıyı
     yazar. Yoksa haberi reddeder — bu red yetkisi kritik: modele "bir şey
     üret" demek yerine "üretmeye değer mi" diye sormak, uydurmayı önlüyor.

Çıktı `konu_bankasi.brief_metni()` ile aynı alanları taşır, böylece içerik
üretimi tek yoldan ilerler.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Tuple

from . import haber_puanlama

log = logging.getLogger(__name__)


# Triyaj prompt'u iki kez yazıldı. İlk sürüm modele doğrudan "bu haberden iyi
# içerik çıkar mı, 1-10 güven ver" diye soruyordu. Gerçek beslemede sonuç:
# 5 adayın 5'i kabul, hepsine güven=8, ve kaynakta geçmeyen Silivri bağları
# uyduruldu ("Silivri gibi çeper ilçelerde ezilen kiracılar").
#
# Ders: modele kendi çıktısını değerlendirmesini söylemek işe yaramıyor; kibarca
# "evet" diyor. Bu sürüm karar sormuyor, DOĞRULANABİLİR OLGULAR soruyor ve
# kararı kod veriyor. "Metinde süre geçiyor mu, alıntıla" sorusuna model
# güvenilir yanıt verir; "bu paylaşmaya değer mi" sorusuna vermez.
TRIYAJ_TALIMATI = """Sen "EDM Yapı & Gayrimenkul"ün içerik editörüsün. Silivri merkezli, Trakya'da
toprağı bilen bir emlak ofisi. Takipçi kitlesi: bölgedeki ev sahipleri, kiracılar,
arsa yatırımcıları ve ilk kez mülk alacaklar.

Sana bir haber verilecek. GÖREVİN KARAR VERMEK DEĞİL, HABERİ İNCELEMEK.
Aşağıdaki soruları yalnızca METİNDE YAZANA bakarak yanıtla. Kararı sistem verecek.

MUTLAK KURAL — UYDURMA YASAĞI:
Her olgusal iddia için haber metninden BİREBİR ALINTI vermelisin. Alıntı
veremiyorsan o alanın yanıtı "hayır" veya null'dur. Metinde geçmeyen bir şehir,
rakam, süre veya kanun maddesi yazma. Özellikle: haberde Silivri/Trakya
geçmiyorsa yerel bağ UYDURMA — "Silivri gibi ilçelerde de olabilir" türü
çıkarımlar yasak.

SORULAR:

1. somut_kural — Haberde DEĞİŞEN ya da yanlış bilinen somut bir kural, oran,
   süre, şart veya yükümlülük var mı? Genel eğilim ("fiyatlar arttı") sayılmaz.
2. okuyucu_eylemi — Bunu okuyan biri BUGÜN ne yapmalı? Somut bir eylem yoksa null.
   "Takip etmeli", "bilgi sahibi olmalı" gibi ifadeler eylem DEĞİLDİR, null yaz.
3. dayanak_alintisi — 1 ve 2'yi destekleyen, metinden birebir alınmış cümle.
4. yerel_gecis — Haber metninde Silivri, Trakya, Çatalca, Çorlu, Tekirdağ veya
   Edirne AÇIKÇA geçiyor mu? Geçmiyorsa "hayir". İstanbul geçiyorsa "istanbul".
5. mevzuat_alintisi — Metinde açıkça geçen kanun/madde numarası. Yoksa null.
   TAHMİN ETME.
6. kalicilik — Bu bilgi üç ay sonra da geçerli mi ("kalici"), yoksa yalnızca
   şimdi mi anlamlı ("guncel"), yoksa çoktan eskidi mi ("eskimis")?
7. zaten_biliniyor — Bu, hedef kitlenin zaten bildiği bir genelleme mi? (evet/hayir)
8. tekil_segment — Haber yalnızca dar bir kesimi mi ilgilendiriyor (örn. yalnızca
   GYO yatırımcıları, yalnızca müteahhitler)? (evet/hayir)

Sonra, YALNIZCA yukarıdaki yanıtlara dayanarak içerik brief'i doldur:
  baslik      — iç kullanım için konu başlığı (manşet değil)
  aci         — takipçimiz açısından NEDEN önemli, 1-2 cümle.
                Haberi özetleme; sonucunu söyle. Uydurma bağ kurma.
  sutun       — S1 Tapu&Hukuk | S2 Kiracı&EvSahibi | S3 Arsa&İmar | S4 Rakam&Bölge
  bicim       — B1 (somut risk + korunma adımları) | B3 (tek cümlelik net cevap)
                | B5 (ne oldu / bizde ne anlama geliyor)
  kanca_kalip — eksik_imza | sure | yaygin_yanlis | rakam | kim_hakli | belge

Çıktıyı YALNIZCA geçerli JSON olarak ver:
{
  "somut_kural": "evet" veya "hayir",
  "okuyucu_eylemi": "somut eylem" veya null,
  "dayanak_alintisi": "metinden birebir cümle" veya null,
  "yerel_gecis": "yakin" | "istanbul" | "hayir",
  "mevzuat_alintisi": "metinde geçen madde" veya null,
  "kalicilik": "kalici" | "guncel" | "eskimis",
  "zaten_biliniyor": "evet" veya "hayir",
  "tekil_segment": "evet" veya "hayir",
  "baslik": "...",
  "aci": "...",
  "sutun": "S1|S2|S3|S4",
  "bicim": "B1|B3|B5",
  "kanca_kalip": "..."
}
"""


def _karar_ver(y: Dict[str, Any]) -> Tuple[bool, str, int]:
    """Triyaj yanıtından kararı KOD verir, model değil.

    Modelin kendi verdiği güven puanı ayırt edici çıkmadı (gerçek beslemede beş
    farklı habere de 8 verdi). Bunun yerine doğrulanabilir alt yanıtlardan
    puan hesaplanıyor.

    Döner: (kabul, gerekçe, puan)
    """
    def evet(alan: str) -> bool:
        return str(y.get(alan, "")).strip().lower() == "evet"

    # --- Elemeler ---
    # Red sebebi yalnızca elemek için değil YÖNLENDİRMEK için kullanılıyor:
    # "kural değişikliği yok ama bilgi kalıcı" = haber değil, konu adayı.
    # Gerçek beslemede "Bu maddeyi kontrol etmeden tahliye davası açmayın"
    # başlığı böyle: haber olarak reddedilmeli ama konu bankasına aday.
    if not evet("somut_kural"):
        if str(y.get("kalicilik", "")).lower() == "kalici":
            return False, "konu-adayi:kalıcı bilgi, haber değil", 0
        return False, "somut bir kural/süre/oran değişimi yok", 0
    if not y.get("dayanak_alintisi"):
        return False, "metinden dayanak alıntısı verilemedi", 0
    if not y.get("okuyucu_eylemi"):
        return False, "okuyucunun yapacağı somut bir şey yok", 0
    if evet("zaten_biliniyor"):
        return False, "kitlenin zaten bildiği genelleme", 0
    if evet("tekil_segment"):
        return False, "yalnızca dar bir kesimi ilgilendiriyor", 0
    if str(y.get("kalicilik", "")).lower() == "eskimis":
        return False, "bilgi eskimiş", 0

    # --- Puan ---
    # Taban 5: beş elemeyi birden geçen haber zaten kayda değer. Taban 4 iken
    # kontrol testinde "Tapu harcında beyan yükümlülüğü değişti" haberi 6 puanla
    # elenmişti — gerçek bir kural değişikliği, somut sonucu olan, kalıcı bir
    # haber. Madde numarası anılmadığı için mevzuat puanı alamamıştı.
    puan = 5
    if y.get("mevzuat_alintisi"):
        puan += 3                               # doğrulanmış mevzuat en güçlü sinyal
    yerel = str(y.get("yerel_gecis", "")).lower()
    if yerel == "yakin":
        puan += 3
    elif yerel == "istanbul":
        puan += 1
    if str(y.get("kalicilik", "")).lower() == "kalici":
        puan += 2                               # kalıcı bilgi kaydedilir

    return True, "uygun", puan


KONU_ONERI_TALIMATI = """Sen "EDM Yapı & Gayrimenkul"ün içerik editörüsün (Silivri, Trakya, emlak).

Sana bir rehber/açıklayıcı makale başlığı verilecek ("Temellük nedir?",
"Arsa alırken nelere dikkat edilmeli?" gibi). Bu tür başlıklar HABER DEĞİL —
insanların gerçekten ne aradığının göstergesi.

GÖREV: Bunu bizim konu bankamıza eklenecek bir KONU BRIEF'ine çevir.

Brief'in kalitesi çıktının kalitesini belirler. `aci` alanı konuyu genel geçer
anlatmaz; o konuyu paylaşmaya DEĞER kılan şeyi söyler. Karşılaştır:
  zayıf: "Temellük, mülkiyetin devralınmasıdır."
  güçlü: "Temellük tapuda sık görülen ama anlamı bilinmeyen bir terim; miras
         yoluyla gelen hisseyi devralanlar sonradan vergi ve harç sürprizi
         yaşıyor."

Emin olmadığın kanun maddesi numarası YAZMA; `mevzuat: null` bırak.

Çıktıyı YALNIZCA geçerli JSON olarak ver:
{
  "uygun": true veya false,
  "red_sebebi": "uygun false ise gerekçe, değilse null",
  "baslik": "Konu başlığı",
  "aci": "Bu konuyu paylaşmaya değer kılan şey — 1-2 cümle",
  "sutun": "S1 | S2 | S3 | S4",
  "bicim": "B1 | B3",
  "kanca_kalip": "eksik_imza | sure | yaygin_yanlis | rakam | kim_hakli | belge",
  "mevzuat": null veya doğrulanmış madde,
  "yerel": "Silivri/Trakya bağı veya null"
}
"""


def _haber_metni(haber: Dict[str, Any], azami: int = 2200) -> str:
    baslik = haber.get("orijinal_baslik") or haber.get("baslik", "")
    ozet = haber.get("orijinal_ozet") or haber.get("ozet", "")
    govde = haber.get("makale_metni") or ""
    parcalar = [f"BAŞLIK: {baslik}"]
    if ozet:
        parcalar.append(f"ÖZET: {ozet}")
    if govde:
        parcalar.append(f"METİN: {govde[:azami]}")
    parcalar.append(f"KAYNAK: {haber.get('kaynak', 'bilinmiyor')}")
    return "\n".join(parcalar)


def triyaj_et(haber: Dict[str, Any], asgari_guven: int = 6) -> Optional[Dict[str, Any]]:
    """Haberi brief'e çevirir; değmiyorsa None döner.

    `asgari_guven`: modelin kendi verdiği değerlilik puanı bunun altındaysa
    haber elenir. Modelin "uygun" demesi yetmiyor — ne kadar emin olduğunu da
    soruyoruz, çünkü zorlandığında kibarca "evet" deme eğiliminde.
    """
    from . import generate_text  # döngüsel içe aktarmayı önlemek için burada

    # Triyaj olgu çıkarımı; hızlı zincir yeterli ve tur başına 6 kez çağrılıyor
    ham = generate_text._gemini_cagri(
        _haber_metni(haber), TRIYAJ_TALIMATI, sicaklik=0.3,
        modeller=generate_text.MODELLER_HIZLI,
    )
    sonuc = generate_text._json_coz(ham) if ham else None
    if not sonuc:
        log.warning("Triyaj yanıtı çözülemedi: %s", str(haber.get("orijinal_baslik"))[:60])
        return None

    kabul, gerekce, guven = _karar_ver(sonuc)
    if not kabul:
        log.info("Triyaj reddetti (%s): %s", gerekce, str(haber.get("orijinal_baslik"))[:60])
        if gerekce.startswith("konu-adayi:"):
            haber["_konu_adayi"] = True   # çağıran konu bankası yoluna yönlendirsin
        return None
    if guven < asgari_guven:
        log.info("Triyaj puanı düşük (%d < %d): %s", guven, asgari_guven,
                 str(haber.get("orijinal_baslik"))[:60])
        return None

    # Yerel bağ uydurulmasın: model metinde yoksa "hayir" demişti
    yerel_bag = None
    if str(sonuc.get("yerel_gecis", "")).lower() == "yakin":
        yerel_bag = "Haberde bölge açıkça geçiyor"

    # Konu bankası kaydıyla aynı şekil — içerik üretimi tek yoldan ilerlesin
    return {
        "kod": f"HABER-{haber.get('id', '?')}",
        "sutun": sonuc.get("sutun") or "S4",
        "bicim": sonuc.get("bicim") or "B5",
        "baslik": sonuc.get("baslik") or haber.get("orijinal_baslik", ""),
        "aci": sonuc.get("aci", ""),
        "kanca_kalip": sonuc.get("kanca_kalip") or "yaygin_yanlis",
        "mevzuat": sonuc.get("mevzuat_alintisi"),
        "yerel": yerel_bag,
        "_guven": guven,
        "_dayanak": sonuc.get("dayanak_alintisi"),
        "_eylem": sonuc.get("okuyucu_eylemi"),
        "_haber_id": haber.get("id"),
        "_kaynak_url": haber.get("orijinal_url"),
    }


def konu_adayi_mi(haber: Dict[str, Any]) -> bool:
    """`triyaj_et` bu haberi konu bankası adayına yönlendirdi mi."""
    return bool(haber.get("_konu_adayi"))


def konu_onerisi_uret(haber: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Rehber/açıklayıcı makaleyi konu bankası adayına çevirir.

    Bu, beslemenin asıl değeri: "Temellük nedir?" gibi başlıklar insanların
    gerçekten ne aradığını gösteriyor ve bankamızda karşılığı yok.
    """
    from . import generate_text

    ham = generate_text._gemini_cagri(
        _haber_metni(haber, azami=1200), KONU_ONERI_TALIMATI, sicaklik=0.4,
        modeller=generate_text.MODELLER_HIZLI,
    )
    sonuc = generate_text._json_coz(ham) if ham else None
    if not sonuc or not sonuc.get("uygun"):
        return None

    return {
        "sutun": sonuc.get("sutun") or "S1",
        "bicim": sonuc.get("bicim") or "B3",
        "baslik": sonuc.get("baslik", ""),
        "aci": sonuc.get("aci", ""),
        "kanca_kalip": sonuc.get("kanca_kalip") or "yaygin_yanlis",
        "mevzuat": sonuc.get("mevzuat"),
        "yerel": sonuc.get("yerel"),
        "_kaynak_url": haber.get("orijinal_url"),
    }
