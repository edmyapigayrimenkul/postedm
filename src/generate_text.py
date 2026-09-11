"""
generate_text.py — EDM İçerik Üretici (Biçim Duyarlı)

Konu bankasından gelen brief'i, ICERIK-SISTEMI.md'de tanımlı beş biçimden birine
göre slayt metinlerine ve caption'lara çevirir.

Tasarımın iki kuralı:

1. **Biçim konuya göre seçilir, konu biçime zorlanmaz.** Eskiden tek bir kalıp
   (kapak → iki kart → üç adım → CTA) her konuya uygulanıyordu; karşılaştırılacak
   iki tarafı olmayan konularda model karşıtlık uyduruyordu.

2. **Bütçeler çizicinin gerçek kapasitesinden gelir.** ICERIK-SISTEMI.md §5
   tablosu `scripts/metin_butcesi.py` ile ölçüldü. Prompt daha uzun metin isterse
   make_image sessizce kırpar — üretimdeki "cümle ortasında biten kart" hatası
   tam olarak buydu.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from . import config, db

log = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Model zincirleri 2026-09-11'de canlı olarak ölçüldü. Eski zincir
# ["gemini-3.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"] idi ve
# iki ucu da bozuktu: ana model kotayı doldurup 429 veriyor, son yedek 404
# ("no longer available"). Canlı turda tek içerik üretimi bu yüzden ~100 saniye
# sürdü ve üç modeli birden dolaştı.
#
# Modelin listelenmesi kullanılabilir olduğu anlamına GELMİYOR: 2.5-flash-lite
# /models listesinde görünüyor ama çağrılınca 404 dönüyor. Zincir değiştirilecekse
# gerçek generateContent çağrısıyla test edilmeli.

# İçerik üretimi: kanca ve metin kalitesi önemli, yavaşlığa katlanılır.
#
# Zincirin SONUNDA lite modeller var ve bu bilinçli. İlk kurulumda zincirin
# dördü de aynı "3.x-flash" katmanındandı; o katman topluca 503 verdiğinde
# (Google tarafında yoğunluk) zincir 246 saniye deneyip BOŞ döndü. Aynı anda
# lite modeller 0,6 saniyede yanıt veriyordu.
#
# Ders: her üyesi aynı katmandan olan zincir yedek zinciri değildir.
# Gözetimsiz cron için biraz daha sade içerik, hiç içerik olmamasından iyidir.
MODELLER = [
    "gemini-3.7-flash",          # ölçüm: 18,7 sn
    "gemini-3.6-flash",          # ölçüm: 21,5 sn
    "gemini-flash-latest",       # ölçüm: 26,1 sn
    "gemini-3.8-flash",
    # Son çare: yoğunluk fırtınasında ayakta kalan katman.
    # Sabitlenmiş sürüm önce: "-latest" takma adı en yeni (dolayısıyla en yoğun)
    # modeli işaret ettiği için süresi oynak ölçüldü (0,6 sn ve 29,5 sn),
    # sabitlenmiş sürüm tutarlı (0,9 ve 0,7 sn).
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
]

# Triyaj gibi yapılandırılmış çıkarım işleri: yaratıcılık gerekmiyor, hız gerekiyor.
# Tur başına 6 kez çağrılıyor; 20 sn'lik modelle çalıştırmak hem yavaş hem kota israfı.
MODELLER_HIZLI = [
    "gemini-3.5-flash-lite",     # ölçüm: 0,9 sn ve 0,7 sn — tutarlı
    "gemini-flash-lite-latest",  # ölçüm: 0,6 sn ama bir kez 29,5 sn — oynak
    "gemini-3.7-flash",
]

# ---------------------------------------------------------------------------
# Metin bütçeleri — ICERIK-SISTEMI.md §5
# Değer, çizicinin sığdırdığı miktarın %80'i. Türkçe kelime uzunluğu değişken
# olduğu için tam sınıra yazılan metin ilk uzun kelimede taşıyor.
# ---------------------------------------------------------------------------
BUTCE: Dict[str, int] = {
    "manset_satir": 18,      # Fraunces 78px, satır başına
    "spot": 150,             # kapak spot metni
    "kart_baslik": 42,       # slayt 2 kart başlığı
    "kart_aciklama": 210,    # slayt 2 kart gövdesi (4 satır)
    "adim_baslik": 44,       # slayt 3 adım başlığı
    "adim_aciklama": 155,    # slayt 3 adım gövdesi (3 satır)
    "rozet": 44,             # üst rozet şeridi
    "yasal_dayanak": 42,     # kapak üstündeki mevzuat şeridi (sağdaki etiketle paylaşır)
    "threads": 480,          # platform sınırı 500
}


ORTAK_KURALLAR = """Sen "EDM Yapı & Gayrimenkul"ün içerik editörüsün. Silivri merkezli, Trakya'da
toprağı bilen, tapuya kadar müşterisinin yanında duran bir emlak ofisi.
Slogan: "Yatırım Ortağınız".

MARKA SESİ — SAKİN OTORİTE:
Bilen ama bağırmayan bir uzman gibi yaz. Otorite yüksek sesle değil, kesinlikle kurulur.

MUTLAK KURALLAR:
1. ÜNLEM İŞARETİ KULLANMA. Hiçbir alanda, hiçbir gerekçeyle.
2. "ŞOK", "KAÇIRMAYIN", "İNANILMAZ", "SAKIN", "DİKKAT!", "ACİL" gibi tıklama tuzağı
   kelimeleri ve emoji kullanma. Bunlar markayı ucuzlatır.
3. KANUN MADDESİ UYDURMA. Brief'te "DOĞRULANMIŞ MEVZUAT" verildiyse yalnızca onu,
   aynen yaz. Verilmediyse madde numarası YAZMA — "ilgili mevzuat", "yürürlükteki
   düzenleme" gibi ifade kullan. Uydurulmuş bir madde numarası gerçek bir emlak
   ofisinin hesabında ciddi bir sorumluluktur.
4. RAKAM UYDURMA. Oran veya tutar veriyorsan dayanağını belirt ("TÜFE on iki aylık
   ortalaması" gibi). Dayanağı yoksa rakam verme, niteliksel yaz.
5. Görsel metinlerinde ortalama cümle uzunluğu 12 kelimeyi geçmesin. Uzun cümle
   1080 piksellik karede okunmuyor.
6. Brief'teki "AÇI" içeriğin merkezidir. Konuyu genel geçer anlatma; o açıyı işle.

MANŞET YAPISI (üç parça):
  manset_parca_1  → beyaz görünecek açılış. Durumu kurar
  manset_vurgu    → KIRMIZI görünecek kanca, BÜYÜK HARF. Okuyanın durduğu yer
  manset_parca_2  → beyaz görünecek kapanış. SONUCU söyler

ÜÇ PARÇA BİRLEŞTİĞİNDE TAM VE BİTMİŞ BİR CÜMLE OLMALIDIR.
En sık yapılan hata, cümleyi şartla bırakıp sonucu yazmamaktır:
  YANLIŞ: "Ev kiralarken" + "BU İMZAYI" + "unutursanız"     → sonuç yok, cümle askıda
  DOĞRU : "Ev kiralarken" + "BU İMZAYI" + "atarsanız evden çıkarsınız"
  DOĞRU : "Hisseli tapuda" + "ŞUFA TUZAĞI" + "iki yıl peşinizi bırakmaz"
Okuyan üçüncü satırı bitirdiğinde riskin ne olduğunu anlamış olmalı.

Her parça tek satırdır ve %(manset_satir)d KARAKTERİ AŞAMAZ. Aşarsa görselde taşar.
Kanca kalıbı brief'te verilir. Kalıplar KOPYALANACAK İFADE DEĞİL, cümlenin
biçimidir. Aşağıdaki örnek ifadeleri olduğu gibi yazma; konuya ait kendi
kelimelerinle aynı biçimi kur.

  eksik_imza    → şart + eksik olan şeyin ADI + sonuç
                  ör. "Hisseli tapuda" + "FERAGATNAME YOKSA" + "payınız gider"
  sure          → sürenin kendisi vurgudur + o sürede ne olacağı
                  ör. "Satıştan sonra" + "İKİ YIL BOYUNCA" + "dava açılabilir"
  yaygin_yanlis → yaygın inanış + DOĞRUSUNUN KENDİSİ + sonucu
                  ör. "Tarlaya tiny house" + "RUHSATA TABİDİR" + "yoksa yıkılır"
                  (vurgu kısmına "ASLINDA TAM TERSİ" gibi kalıp cümle YAZMA;
                   oraya doğru bilginin kendisi gelir)
  rakam         → rakamın kendisi vurgudur + hangi şartla geçerli
                  ör. "Arsa konuttan" + "%%65 DAHA UCUZ" + "ama imar şartıyla"
  kim_hakli     → taraf sorusu + KİMİN HAKLI OLDUĞU + kısa gerekçe
                  ör. "Depozitoyu kim çeker?" + "TEK BAŞINA ÇEKEMEZ" + "rıza şart"
  belge         → belgenin adı + engellenen işlem + sonucu
                  ör. "İmar durumu belgesi" + "OLMADAN" + "arsa değeri bilinmez"

manset_vurgu her zaman BİLGİ taşır — kalıp söz değil.

CAPTION KURALLARI:
- Instagram: ilk satır kancayı tekrar etmez, genişletir. 3-5 kısa paragraf.
  Sonunda tek bir soru sor (yorum motoru). Hashtag'leri sistem ekler, sen ekleme.
- Threads: %(threads)d karakterin altında, tek nefeslik, daha konuşkan.
- Facebook: Instagram metninin biraz daha açıklayıcı hâli.
- Hiçbir caption'da "link bio'da" yazma; hesapta henüz yönlendirme yok.
""" % BUTCE


# ---------------------------------------------------------------------------
# Biçim şemaları
# ---------------------------------------------------------------------------

_SEMA_B1 = """BİÇİM: B1 — RİSK DOSYASI (4 slayt)
Bir tuzak ve ondan korunma yolu. Kaydettirmeyi hedefler.

Slayt 2 iki taraflı analizdir: Ev Sahibi vs Kiracı, Doğru vs Yanlış, ya da
Riskin Sebebi vs Riskin Sonucu. İki taraf gerçekten varsa kullan; yoksa
kart_1'i "risk nasıl doğuyor", kart_2'yi "hangi durumda doğmuyor" olarak kur.
ASLA yapay karşıtlık uydurma.

Slayt 3 üç somut, uygulanabilir korunma adımıdır. Her adım okuyanın yarın
yapabileceği bir şey olmalı; "dikkatli olun" gibi soyut tavsiye değil.

JSON:
{
  "bicim": "B1",
  "kategori_kodu": "TAPU_VE_HUKUK | EV_SAHIBI_VE_KIRACI | YATIRIM_VE_PIYASA | ARSA_IMAR_VE_TINY_HOUSE | SEKTOREL_HABER_VE_ANALIZ",
  "rozet_metni": "En fazla %(rozet)d karakter (örn: HUKUK REHBERİ // TAPU MEVZUATI)",
  "yasal_dayanak": "En fazla %(yasal_dayanak)d karakter. Brief'te mevzuat yoksa konu tanımı yaz",
  "manset_parca_1": "≤%(manset_satir)d karakter",
  "manset_vurgu": "≤%(manset_satir)d karakter, BÜYÜK HARF",
  "manset_parca_2": "≤%(manset_satir)d karakter",
  "spot": "≤%(spot)d karakter. Riski tek nefeste anlatan 2 cümle",
  "slayt_2_detay": {
    "baslik_satir_1": "≤%(manset_satir)d karakter",
    "baslik_vurgu": "≤%(manset_satir)d karakter, BÜYÜK HARF",
    "kart_1": {
      "etiket": "≤%(rozet)d karakter (örn: RİSKİN KAYNAĞI // YASAL ÇERÇEVE)",
      "renk": "kirmizi",
      "baslik": "≤%(kart_baslik)d karakter",
      "aciklama": "≤%(kart_aciklama)d karakter. Tam cümlelerle bitir"
    },
    "kart_2": {
      "etiket": "≤%(rozet)d karakter",
      "renk": "yesil",
      "baslik": "≤%(kart_baslik)d karakter",
      "aciklama": "≤%(kart_aciklama)d karakter. Tam cümlelerle bitir"
    }
  },
  "slayt_3_cozum": {
    "tip": "adim_adim_rehber",
    "baslik_ust": "≤%(manset_satir)d karakter",
    "baslik_vurgu": "≤%(manset_satir)d karakter",
    "maddeler": [
      {"no": "01", "baslik": "≤%(adim_baslik)d karakter", "aciklama": "≤%(adim_aciklama)d karakter"},
      {"no": "02", "baslik": "≤%(adim_baslik)d karakter", "aciklama": "≤%(adim_aciklama)d karakter"},
      {"no": "03", "baslik": "≤%(adim_baslik)d karakter", "aciklama": "≤%(adim_aciklama)d karakter"}
    ]
  },
  "slayt_4_cta": {
    "slogan_parca_1": "≤%(manset_satir)d karakter",
    "slogan_vurgu": "≤%(manset_satir)d karakter",
    "aciklama": "≤%(spot)d karakter",
    "kaydet_metni": "Kaydetme çağrısı, tek cümle"
  },
  "onem_puani": 9,
  "caption_instagram": "...",
  "caption_facebook": "...",
  "caption_threads": "≤%(threads)d karakter"
}""" % BUTCE

_SEMA_B2 = """BİÇİM: B2 — KARŞILAŞTIRMA (3 slayt)
A mı B mi, rakamla. İki gerçek seçenek varsa kullanılır.

Beş satır aynı başlıklarla iki kolonda karşılaştırılır — kolonlar hizalı olmalı,
yani sol_kolon_veriler ve sag_kolon_veriler aynı sırada aynı ölçütü anlatır.
Stratejist notu taraf tutar: "duruma göre değişir" diye bitirme, bir öneri ver
ve hangi şartta geçerli olduğunu söyle.

JSON:
{
  "bicim": "B2",
  "kategori_kodu": "YATIRIM_VE_PIYASA",
  "rozet_metni": "≤%(rozet)d karakter",
  "yasal_dayanak": "≤%(yasal_dayanak)d karakter",
  "manset_parca_1": "≤%(manset_satir)d karakter",
  "manset_vurgu": "≤%(manset_satir)d karakter",
  "manset_parca_2": "≤%(manset_satir)d karakter",
  "spot": "≤%(spot)d karakter",
  "slayt_3_cozum": {
    "tip": "finansal_tablo",
    "baslik_ust": "≤%(manset_satir)d karakter",
    "baslik_vurgu": "≤%(manset_satir)d karakter",
    "alt_baslik": "≤70 karakter. Tabloyu tanıtan tek cümle. Sahip olmadığın veri iddia etme",
    "sol_kolon_baslik": "[1] SEÇENEK A ADI (≤26 karakter, BÜYÜK HARF)",
    "sag_kolon_baslik": "[2] SEÇENEK B ADI (≤26 karakter, BÜYÜK HARF)",
    "sol_kolon_veriler": [["Ölçüt:", "Değer"], ["Ölçüt:", "Değer"], ["Ölçüt:", "Değer"], ["Ölçüt:", "Değer"], ["Ölçüt:", "Değer"]],
    "sag_kolon_veriler": [["Ölçüt:", "Değer"], ["Ölçüt:", "Değer"], ["Ölçüt:", "Değer"], ["Ölçüt:", "Değer"], ["Ölçüt:", "Değer"]],
    "stratejist_notu": "≤%(spot)d karakter. Net bir öneri ve geçerlilik şartı"
  },
  "slayt_4_cta": {
    "slogan_parca_1": "≤%(manset_satir)d karakter",
    "slogan_vurgu": "≤%(manset_satir)d karakter",
    "aciklama": "≤%(spot)d karakter",
    "kaydet_metni": "Kaydetme çağrısı"
  },
  "onem_puani": 8,
  "caption_instagram": "...",
  "caption_facebook": "...",
  "caption_threads": "≤%(threads)d karakter"
}
Ölçüt başlıkları ≤24, değerler ≤26 karakter olsun; kolona sığması gerekiyor.

VERİ KAYNAĞI VERİLMEMİŞSE: kolon değerleri SAYISAL OLMAZ. "%%40-55", "18.000 TL",
"14-16 yıl" gibi uydurulmuş rakamlar yerine niteliksel karşılaştırma yaz:
"Düzenli aylık gelir", "Doğrudan gelir yok", "Sabit gideri yüksek", "Gideri
yok denecek kadar az", "Hızlı nakde çevrilir", "Alıcı bulması zaman alır".
Manşetteki vurgu da rakam içermez; farkın YÖNÜNÜ söyler.""" % BUTCE

_SEMA_B3 = """BİÇİM: B3 — TEK KARE CEVAP (1 slayt)
Yaygın bir soru ve net cevabı. Kaydırma yok, tamamlanma oranı %%100.

Cevap ilk kelimeden belli olsun: "Hayır.", "Evet, ama...", "En fazla üç aylık kira."
Kaçamak cevap bu biçimi öldürür. Gerekçe tek paragraf, kaynağı belirtilmiş.

JSON:
{
  "bicim": "B3",
  "kategori_kodu": "...",
  "rozet_metni": "≤%(rozet)d karakter",
  "yasal_dayanak": "≤%(yasal_dayanak)d karakter",
  "soru": "≤%(kart_baslik)d karakter. Okuyanın kendi kafasındaki cümle",
  "manset_parca_1": "≤%(manset_satir)d karakter",
  "manset_vurgu": "≤%(manset_satir)d karakter. Cevabın kendisi",
  "manset_parca_2": "≤%(manset_satir)d karakter",
  "spot": "≤%(spot)d karakter. Gerekçe",
  "slayt_2_detay": {
    "baslik_satir_1": "≤%(manset_satir)d karakter",
    "baslik_vurgu": "≤%(manset_satir)d karakter",
    "kart_1": {"etiket": "≤%(rozet)d karakter", "renk": "kirmizi", "baslik": "≤%(kart_baslik)d karakter", "aciklama": "≤%(kart_aciklama)d karakter"},
    "kart_2": {"etiket": "≤%(rozet)d karakter", "renk": "yesil", "baslik": "≤%(kart_baslik)d karakter", "aciklama": "≤%(kart_aciklama)d karakter"}
  },
  "onem_puani": 7,
  "caption_instagram": "...",
  "caption_facebook": "...",
  "caption_threads": "≤%(threads)d karakter"
}
slayt_2_detay tek kare paylaşımda kullanılmaz ama arşiv için doldurulur:
kart_1 sık yapılan yanlışı, kart_2 doğrusunu anlatır.""" % BUTCE

_SEMA_B5 = """BİÇİM: B5 — HABER YORUMU (2 slayt)
Ne oldu ve bu Silivri/Trakya'da ne anlama geliyor.

İkinci kısım asıl değerdir: haberi tekrar etme, yerel sonucunu söyle.
Haberin gerçekten sektörü ilgilendirdiğinden emin ol; ilgilendirmiyorsa
"onem_puani" değerini 4'ün altında ver, sistem o içeriği yayınlamaz.

JSON: B1 ile aynı şema, ancak
  slayt_2_detay.kart_1 → "NE OLDU" (renk: kirmizi)
  slayt_2_detay.kart_2 → "SİLİVRİ VE TRAKYA İÇİN ANLAMI" (renk: yesil)
  slayt_3_cozum.maddeler → haberden çıkan 3 somut sonuç
""" + _SEMA_B1.split("JSON:", 1)[1]


SEMALAR: Dict[str, str] = {"B1": _SEMA_B1, "B2": _SEMA_B2, "B3": _SEMA_B3, "B4": _SEMA_B2, "B5": _SEMA_B5}


SİSTEM_TALİMATI_ILAN = """Sen Silivri ve Trakya gayrimenkul pazarında köklü uzmanlığa sahip "EDM Yapı & Gayrimenkul"ün Kıdemli Pazarlama ve İletişim Danışmanısın.
Sloganımız: "Yatırım Ortağınız".

HEDEF:
Verilen gayrimenkul portföy ilanını analiz ederek; abartısız, sakin, net ve güven veren kurumsal bir dille sosyal medya metinleri ve vurgular üretmektir.

MARKANIN SES TONU & İLKELERİ:
1. SAKİN VE ŞEFFAF: Asla "KAÇIRMAYIN", "KELEPİR", "ŞOK FİYAT" gibi ucuz pazarlama jargonu ve ünlem işareti kullanma.
2. NET VE BİLGİLENDİRİCİ: Konum, metrekare, imar durumu, getiri potansiyeli gibi somut verilere odaklan.
3. EİDS VE MEVZUATA UYUMLU: Doğrulanabilir, dürüst ve yasal çerçevede tanıtım yap.

Çıktıyı YALNIZCA geçerli bir JSON olarak ver:
{
  "manset": "Kısa ve prestijli manşet (örn: Silivri Selimpaşa'da Müstakil Parsel)",
  "spot": "1-2 cümlelik sakin özet (25-35 kelime)",
  "one_cikan_ozellikler": ["Öne çıkan 1. özellik", "Öne çıkan 2. özellik", "Öne çıkan 3. özellik"],
  "ig_caption": "Instagram için profesyonel gönderi açıklaması",
  "fb_caption": "Facebook için detaylı portföy açıklaması",
  "threads_metin": "Threads için 500 karakter altı net ve samimi tanıtım"
}
"""


# ---------------------------------------------------------------------------
# Gemini çağrısı
# ---------------------------------------------------------------------------

def _gemini_cagri(
    prompt: str,
    sistem_talimati: str,
    sicaklik: float = 0.7,
    modeller: Optional[List[str]] = None,
) -> Optional[str]:
    """Model zincirini sırayla dener. Sıcaklık 0.7: kanca yazımı 0.3'te fazla
    kalıplaşıyordu, brief zaten olguları sabitlediği için yaratıcılık payı güvenli."""
    api_key = config.env_al("GEMINI_API_KEY")
    if not api_key:
        log.warning("GEMINI_API_KEY tanımlanmamış")
        return None

    payload = {
        "system_instruction": {"parts": [{"text": sistem_talimati}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": sicaklik, "responseMimeType": "application/json"},
    }
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}

    for model in (modeller or MODELLER):
        url = GEMINI_API_URL.format(model=model)
        for _ in range(2):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=35)
                if resp.status_code == 200:
                    log.info("Yanıt veren model: %s", model)
                    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                if resp.status_code in (429, 500, 503):
                    # 503 "yoğunluk" ve 429 "kota" aynı modelde 2 saniyede
                    # düzelmiyor. Beklemek yerine sıradaki modele geçmek hem
                    # daha hızlı hem daha çok işe yarıyor: 246 saniyelik
                    # başarısız tur bu döngüde geçmişti.
                    log.warning("%s kullanılamıyor [%d], sıradaki modele geçiliyor", model, resp.status_code)
                    break
                else:
                    log.warning("%s hata [%d]: %s", model, resp.status_code, resp.text[:120])
                    break
            except Exception as e:
                log.warning("%s istek istisnası: %s", model, e)
                time.sleep(1)
    return None


# ---------------------------------------------------------------------------
# Temizlik ve bütçe denetimi
# ---------------------------------------------------------------------------

def _json_coz(ham: str) -> Optional[Dict[str, Any]]:
    """Model çıktısını sözlüğe çevirir; küçük biçim bozukluklarını kurtarır.

    `responseMimeType: application/json` çoğu zaman temiz JSON verir ama arada
    markdown çiti sarıyor veya son nesneyi kapatmadan kesiyor. Cron gözetimsiz
    çalıştığı için tek bozuk yanıt o günün paylaşımını sessizce düşürüyordu.
    """
    if not ham:
        return None
    try:
        return json.loads(ham)
    except Exception:
        pass

    metin = ham.strip()
    # ```json ... ``` çitini ayıkla
    cit = re.search(r"```(?:json)?\s*(.+?)\s*```", metin, re.DOTALL)
    if cit:
        metin = cit.group(1).strip()
        try:
            return json.loads(metin)
        except Exception:
            pass

    # İlk { ile son } arasını dene
    bas, son = metin.find("{"), metin.rfind("}")
    if bas != -1 and son > bas:
        try:
            return json.loads(metin[bas:son + 1])
        except Exception:
            pass

    # Yanıt kesilmişse: açık kalan parantezleri kapatarak son bir deneme
    if bas != -1:
        parca = metin[bas:]
        parca = re.sub(r",\s*$", "", parca.rstrip())
        acik_suslu = parca.count("{") - parca.count("}")
        acik_kose = parca.count("[") - parca.count("]")
        if acik_suslu > 0 or acik_kose > 0:
            try:
                return json.loads(parca + ("]" * max(0, acik_kose)) + ("}" * max(0, acik_suslu)))
            except Exception:
                pass

    log.error("JSON kurtarılamadı. Yanıtın başı: %s", ham[:180])
    return None


def _markdown_temizle(metin: Any) -> Any:
    if not isinstance(metin, str):
        return metin
    return metin.replace("**", "").replace("__", "").replace("\\n", "\n").strip()


def _unlemleri_kaldir(metin: str) -> str:
    """Model kurala rağmen ünlem koyarsa nokta ile değiştirir. Marka sesi
    pazarlık konusu değil; tek bir ünlem tüm sakin tonu bozuyor."""
    return re.sub(r"!+", ".", metin)


# (yol, bütçe anahtarı) — sözlükte nokta notasyonuyla gezilir
DENETLENECEK: List[Tuple[str, str]] = [
    ("rozet_metni", "rozet"),
    ("yasal_dayanak", "yasal_dayanak"),
    ("manset_parca_1", "manset_satir"),
    ("manset_vurgu", "manset_satir"),
    ("manset_parca_2", "manset_satir"),
    ("spot", "spot"),
    ("soru", "kart_baslik"),
    ("slayt_2_detay.baslik_satir_1", "manset_satir"),
    ("slayt_2_detay.baslik_vurgu", "manset_satir"),
    ("slayt_2_detay.kart_1.etiket", "rozet"),
    ("slayt_2_detay.kart_1.baslik", "kart_baslik"),
    ("slayt_2_detay.kart_1.aciklama", "kart_aciklama"),
    ("slayt_2_detay.kart_2.etiket", "rozet"),
    ("slayt_2_detay.kart_2.baslik", "kart_baslik"),
    ("slayt_2_detay.kart_2.aciklama", "kart_aciklama"),
    ("slayt_3_cozum.baslik_ust", "manset_satir"),
    ("slayt_3_cozum.baslik_vurgu", "manset_satir"),
    ("slayt_3_cozum.stratejist_notu", "spot"),
    ("slayt_4_cta.slogan_parca_1", "manset_satir"),
    ("slayt_4_cta.slogan_vurgu", "manset_satir"),
    ("slayt_4_cta.aciklama", "spot"),
    ("caption_threads", "threads"),
]


def _yoldan_al(veri: Dict[str, Any], yol: str) -> Optional[str]:
    mevcut: Any = veri
    for p in yol.split("."):
        if not isinstance(mevcut, dict) or p not in mevcut:
            return None
        mevcut = mevcut[p]
    return mevcut if isinstance(mevcut, str) else None


def butce_ihlalleri(veri: Dict[str, Any]) -> List[str]:
    """Bütçeyi aşan alanları "yol: kaç/kaç karakter" biçiminde döner.
    Boş liste = görselde hiçbir metin kırpılmayacak."""
    ihlaller: List[str] = []
    for yol, anahtar in DENETLENECEK:
        deger = _yoldan_al(veri, yol)
        if deger and len(deger) > BUTCE[anahtar]:
            ihlaller.append(f"{yol}: {len(deger)}/{BUTCE[anahtar]} karakter")

    for i, m in enumerate(_yoldan_al_liste(veri, "slayt_3_cozum.maddeler")):
        for alan, anahtar in (("baslik", "adim_baslik"), ("aciklama", "adim_aciklama")):
            d = m.get(alan)
            if isinstance(d, str) and len(d) > BUTCE[anahtar]:
                ihlaller.append(f"slayt_3_cozum.maddeler[{i}].{alan}: {len(d)}/{BUTCE[anahtar]} karakter")
    return ihlaller


def _yoldan_al_liste(veri: Dict[str, Any], yol: str) -> List[Dict[str, Any]]:
    mevcut: Any = veri
    for p in yol.split("."):
        if not isinstance(mevcut, dict) or p not in mevcut:
            return []
        mevcut = mevcut[p]
    return mevcut if isinstance(mevcut, list) else []


def _temizle(veri: Dict[str, Any]) -> Dict[str, Any]:
    """Sözlükte özyinelemeli gezip markdown ve ünlemleri temizler."""
    if isinstance(veri, dict):
        return {k: _temizle(v) for k, v in veri.items()}
    if isinstance(veri, list):
        return [_temizle(v) for v in veri]
    if isinstance(veri, str):
        return _unlemleri_kaldir(_markdown_temizle(veri))
    return veri


# ---------------------------------------------------------------------------
# Üretim
# ---------------------------------------------------------------------------

def _uret(girdi: str, bicim: str, sicaklik: float = 0.7) -> Optional[Dict[str, Any]]:
    """Tek üretim turu + gerekirse tek onarım turu.

    Onarım turu, kırpılmayı üretim anında çözmek için var: metni kesmek yerine
    modele "şu alanlar taştı, aynı bilgiyi daha kısa yaz" deniyor. Kesme yapılırsa
    cümle ortasında biten kart sorunu geri gelir.
    """
    sema = SEMALAR.get(bicim, _SEMA_B1)
    sistem = f"{ORTAK_KURALLAR}\n\n{sema}\n\nÇıktıyı YALNIZCA geçerli JSON olarak ver."

    ham = _gemini_cagri(girdi, sistem, sicaklik)
    ayrisik = _json_coz(ham) if ham else None
    if ayrisik is None:
        # Kurtarılamadıysa bir kez daha dene: sıcaklığı düşürmek çıktıyı
        # şemaya daha sadık ve daha kısa tutuyor, kesilme ihtimali azalıyor
        log.info("JSON kurtarılamadı, düşük sıcaklıkla yeniden deneniyor")
        ham = _gemini_cagri(girdi, sistem, sicaklik=0.3)
        ayrisik = _json_coz(ham) if ham else None
    if ayrisik is None:
        return None
    veri = _temizle(ayrisik)

    ihlaller = butce_ihlalleri(veri)
    if not ihlaller:
        return veri

    log.info("Bütçe aşıldı, onarım turu: %s", "; ".join(ihlaller))
    onarim = (
        girdi
        + "\n\nÖNCEKİ DENEMEN ŞU ALANLARDA KARAKTER SINIRINI AŞTI:\n"
        + "\n".join(f"- {i}" for i in ihlaller)
        + "\n\nAynı bilgiyi koruyarak bu alanları sınırın ALTINA indir. "
        "Cümleyi yarıda kesme, yeniden yaz. Diğer alanları aynen bırak.\n\n"
        "Önceki çıktın:\n" + json.dumps(veri, ensure_ascii=False)
    )
    ham2 = _gemini_cagri(onarim, sistem, sicaklik=0.4)
    ayrisik2 = _json_coz(ham2) if ham2 else None
    if ayrisik2 is None:
        log.warning("Onarım turu başarısız, taşan metinle devam ediliyor")
        return veri
    veri2 = _temizle(ayrisik2)

    kalan = butce_ihlalleri(veri2)
    if kalan:
        log.warning("Onarım sonrası hâlâ taşan alan var: %s", "; ".join(kalan))
    return veri2


def manset_birlestir(veri: Dict[str, Any]) -> str:
    """Üç parçalı manşeti tek metne çevirir (veritabanı ve Telegram önizlemesi için)."""
    if veri.get("manset"):
        return veri["manset"]
    return " ".join(
        p.strip() for p in (
            veri.get("manset_parca_1"), veri.get("manset_vurgu"), veri.get("manset_parca_2")
        ) if p
    ).strip()


def konudan_uret(konu: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Konu bankası kaydından slayt içeriği üretir. Faz 1'in ana giriş noktası."""
    from . import konu_bankasi

    bicim = konu.get("bicim", "B1")
    girdi = (
        konu_bankasi.brief_metni(konu)
        + "\n\nBu brief'i yukarıdaki biçim şemasına göre işle. "
        "AÇI alanındaki bakış açısı içeriğin merkezi olsun."
    )
    veri = _uret(girdi, bicim)
    if veri:
        veri.setdefault("bicim", bicim)
        veri["konu_kodu"] = konu["kod"]
        # Brief'i sakla: dogrula.py metindeki mevzuat ve yerel bağ iddialarını
        # bununla karşılaştırıyor. Onay önizlemesinde uyarı olarak görünüyor.
        veri["_brief"] = {
            "mevzuat": konu.get("mevzuat"),
            "yerel": konu.get("yerel"),
            "veri_kaynagi": konu.get("veri_kaynagi"),
        }
    return veri


def otorite_icerigi_uret(
    konu_veya_haber: Any,
    kategori_kodu: Optional[str] = None,
    bicim: str = "B1",
) -> Optional[Dict[str, Any]]:
    """Serbest konu veya RSS haber kaydından içerik üretir.

    Konu bankası tercih edilir; bu fonksiyon elle tetiklenen konular ve
    B5 haber yorumu için kalıyor.
    """
    if isinstance(konu_veya_haber, dict):
        kaynak = konu_veya_haber.get("kaynak", "EDM")
        baslik = konu_veya_haber.get("orijinal_baslik") or konu_veya_haber.get("baslik", "")
        ozet = (
            konu_veya_haber.get("makale_metni")
            or konu_veya_haber.get("orijinal_ozet")
            or konu_veya_haber.get("ozet", "")
        )
        girdi = f"KAYNAK: {kaynak}\nHAM BAŞLIK: {baslik}\nHAM İÇERİK: {ozet}\n"
        bicim = "B5"
    else:
        girdi = f"İŞLENECEK KONU: {konu_veya_haber}\n"

    if kategori_kodu:
        girdi += f"HEDEF KATEGORİ: {kategori_kodu}\n"
    girdi += (
        "\nDOĞRULANMIŞ MEVZUAT: yok. Kanun maddesi numarası YAZMA.\n"
        "Bu içeriği yukarıdaki biçim şemasına göre işle."
    )

    veri = _uret(girdi, bicim)
    if not veri:
        return None
    veri.setdefault("bicim", bicim)

    if isinstance(konu_veya_haber, dict) and konu_veya_haber.get("id"):
        db.haber_guncelle(
            konu_veya_haber["id"],
            kategori=veri.get("kategori_kodu"),
            manset=manset_birlestir(veri),
            detay_metni=json.dumps(veri, ensure_ascii=False),
            ig_caption=veri.get("caption_instagram"),
            threads_metin=veri.get("caption_threads"),
            onem_puani=veri.get("onem_puani", 8),
        )
    return veri


def haber_metinleri_uret(haber: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Geriye dönük uyumlu haber girişi — B5 biçimine yönlendirir."""
    return otorite_icerigi_uret(haber, bicim="B5")


def ilan_metinleri_uret(ilan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Portföy ilanından slayt metinleri ve caption üretir (Faz 2/3)."""
    prompt = (
        f"İLAN BAŞLIĞI: {ilan.get('baslik')}\n"
        f"İŞLEM: {ilan.get('islem')}\n"
        f"TİP: {ilan.get('tip')}\n"
        f"LOKASYON: {ilan.get('ilce')} / {ilan.get('mahalle')}\n"
        f"FİYAT: {ilan.get('fiyat')} {ilan.get('paraBirimi', 'TRY')}\n"
        f"M²: {ilan.get('m2')}\n"
        f"ODA: {ilan.get('oda')}\n"
        f"DANIŞMAN: {ilan.get('danisman')}\n"
    )
    ham = _gemini_cagri(prompt, SİSTEM_TALİMATI_ILAN, sicaklik=0.5)
    if not ham:
        return None
    try:
        return _temizle(json.loads(ham))
    except Exception as e:
        log.error("İlan JSON ayrıştırma hatası: %s", e)
        return None
