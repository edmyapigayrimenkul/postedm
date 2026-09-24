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

from . import config, db, filtre

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

ÖNEMLİ KİMLİK KURALI:
Biz bir HUKUK BÜROSU veya AVUKATLIK OFİSİ DEĞİLİZ; Silivri ve Trakya'da uzman bir EMLAK OFİSİYİZ.
Asla "Hukuk Bürosu", "Hukuki Danışmanlık", "Hukuk Bülteni", "Hukuki Vaka" gibi avukatlık algısı yaratacak unvan ve ifadeler kullanma.
Otoritemiz gayrimenkul danışmanlığı, arsa/konut uzmanlığı ve tapu/imar tecrübesinden gelir.

MARKA SESİ — SAKİN OTORİTE & HALK DİLİNDE DERİN UZMANLIK:
Bilen ama bağırmayan, tapudan yeni çıkmış tecrübeli bir emlak danışmanı gibi yaz. Otorite ağır bürokrasi veya hukuk jargonuyla değil; herkesin tek okuyuşta anladığı kristal netlikteki cümlelerle kurulur.

MUTLAK KURALLAR:
1. ÜNLEM İŞARETİ KULLANMA. Hiçbir alanda, hiçbir gerekçeyle.
2. "ŞOK", "KAÇIRMAYIN", "İNANILMAZ", "SAKIN", "DİKKAT!", "ACİL" gibi tıklama tuzağı
   kelimeleri ve emoji kullanma. Bunlar markayı ucuzlatır.
3. TEK OKUYUŞTA ANLAŞILIR DİL (HERKES ANLAMALI):
   - Cümleleri kısa tut (ortalama 6-10 kelime). Asla Yargıtay kararı, mahkeme ilamı veya kanun metni gibi dolambaçlı yan cümleler kurma.
   - Ağır hukuk ve tapu terimlerini halk dilindeki karşılığıyla açıkla:
     * "Şufa / Yasal önalım hakkı" → "Ön alım hakkı (ortağın hisseyi önceden alma hakkı)"
     * "Hak düşürücü süre" → "Son dava açma süresi"
     * "Noter onaylı feragatname" → "Noterden 'hisse istemiyorum' yazısı (feragatname)"
     * "Fiili taksim" → "Arazide kimin nereyi kullandığı krokisi"
     * "Düşük rayiç bedel tuzağı" → "Tapuda gerçek ödenen parayı yazdırmamak"
   - Pasif bürokrasi dili ("yapılmalıdır", "özen gösterilmelidir") KESİNLİKLE YASAKTIR. Doğrudan okuyucuya hitap et: "İsteyin", "Yazdırın", "Kontrol edin", "Haber vermezseniz hisseniz gider".
   - Okuyan kişi 3 saniyede "Bunu yapmazsam ne olur?" ve "Nasıl korunurum?" sorularının cevabını tek nefeste anlamalıdır.
4. BOŞ TAVSİYE VE GENEL GEÇER NASİHAT VERME:
   "Uzmana danışın", "avukatınıza başvurun", "dikkatli olun", "araştırma yapın",
   "ihmal etmeyin", "önem taşır", "göz ardı etmeyin", "tedbirli olun", "yetkililere sorun"
   gibi içi boş genel geçer ifadeler KESİNLİKLE YASAKTIR. Okuyucu bizden kuru nasihat değil;
   içeriden bir gayrimenkul uzmanının bildiği somut mekanizmayı, usulü ve testi bekler.
5. SOMUT MEKANİZMA, BELGE VE SÜRE VER:
   Kuru tavsiye yerine DOĞRUDAN eylemi yaz:
   - Resmi merci: Belediye İmar İşleri Müdürlüğü, Tapu ve Kadastro Müdürlüğü, Noter, Sulh Hukuk Mahkemesi.
   - Belge adı: 1/1000 Uygulama İmar Planı, TAKBİS tapu kaydı (şerhler ve beyanlar hanesi), Aplikasyon krokisi, Yapı Kullanma İzin Belgesi (İskân), Zemin etüt raporu.
   - Yasal süre ve oran: 2 yıllık hak düşürücü süre, 90 günlük dava açma hakkı, en fazla %%45 DOP kesintisi (İmar K. md. 18), 10 yıllık tahliye süresi.
   - Test adımı: "Tapu kütüğünde kamulaştırma veya şufa şerhi sorgulayın", "Belediyeden parselin terk veya ifraz şartını teyit edin", "Noter kanalıyla ihtarname gönderin".
6. KANUN MADDESİ UYDURMA. Brief'te "DOĞRULANMIŞ MEVZUAT" verildiyse yalnızca onu,
   aynen yaz. Verilmediyse madde numarası YAZMA — "ilgili mevzuat", "yürürlükteki
   düzenleme" gibi ifade kullan. Uydurulmuş bir madde numarası gerçek bir emlak
   ofisinin hesabında ciddi bir sorumluluktur.
7. RAKAM UYDURMA. Oran veya tutar veriyorsan dayanağını belirt ("TÜFE on iki aylık
   ortalaması" gibi). Dayanağı yoksa rakam verme, niteliksel yaz.
8. DİNAMİK DETAY SAYFALARI:
   Konuyu yapay olarak kalıplara sokma.
   - Detay analizi (`slayt_2_detay`): Konu tek bir tuzaktan ibaretse 1 kart; iki taraf/seçenek varsa 2 kart; 3 veya 4 aşamalı bir durum varsa `kartlar` dizisinde 3-4 kart yaz. Yapay karşıtlık üretme.
   - Korunma adımları (`slayt_3_cozum`): 2 ile 5 arasında somut, doğrudan uygulanabilir adım (`maddeler`) yaz. Dolgu madde ekleme.
9. Görsel metinlerinde ortalama cümle uzunluğu 12 kelimeyi geçmesin. Uzun cümle
   1080 piksellik karede okunmuyor.
10. Brief'teki "AÇI" içeriğin merkezidir. Konuyu genel geçer anlatma; o açıyı işle.

MANŞET YAPISI (üç parça):
  manset_parca_1  → beyaz görünecek açılış. DOĞRUDAN AKSİYON ve DURUMU kurar (Title Case, örn: "Arsa Alırken", "Tapuyu İmzalamadan", "Kira Kontratında", "Hisseli Tapuda"). ASLA "Muhtelif", "Genel olarak", "Birtakım" gibi bürokratik, pasif veya kuru kelimelerle başlama.
  manset_vurgu    → KIRMIZI görünecek kanca, BÜYÜK HARF. Okuyanın durduğu yer (BÜYÜK HARF, örn: "İMAR DURUMU YOKSA", "BU İMZAYI ATARSANIZ", "FERAGATNAME YOKSA").
  manset_parca_2  → beyaz görünecek kapanış. SONUCU ve RİSKİ söyler (İlk harfi büyük / Title Case, örn: "Paranız Çöp Olur", "Tüm Birikiminiz Gider", "Evden Çıkartılırsınız").

ÜÇ PARÇA BİRLEŞTİĞİNDE TAM VE BİTMİŞ BİR CÜMLE OLMALIDIR.
En sık yapılan hata, cümleyi şartla bırakıp sonucu yazmamaktır:
  YANLIŞ: "Ev kiralarken" + "BU İMZAYI" + "unutursanız"     → sonuç yok, cümle askıda
  DOĞRU : "Ev kiralarken" + "BU İMZAYI" + "atarsanız evden çıkarsınız"
  DOĞRU : "Arsa alırken"  + "İMAR DURUMU YOKSA" + "paranız çöp olur"
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

CAPTION KURALLARI (HER PLATFORM İÇİN ZORUNLU 4 BLOK):
1. İLK SATIR - HOOK (KANCA METNİ):
   - Açıklamanın ilk satırı akışta kaydırmayı anında durduran, merak veya farkındalık uyandıran güçlü bir kanca cümlesiyle başlar.
   - Örn: "Tapuda bu tek bir imzayı atlarsanız, satın aldığınız mülk iki yıl sonra elinizden gidebilir." veya "Tarla veya arsa bakarken imar durumunda çoğu kişinin atladığı büyük bir risk var."
   - Asla "DİKKAT!", "ŞOK!", "ÖNEMLİ DUYURU" gibi ucuz ve tıklama tuzağı ifadeler kullanma. Sakin otoriteyle doğrudan gerçeği söyle.
2. GÖVDE:
   - Konuyu halk dilinde, akıcı, kısa ve net cümlelerle (6-10 kelime) 2-3 kısa paragrafta açıkla.
3. KAPANIS CÜMLESİ - ETKİLEŞİM SORUSU (?):
   - Metnin son cümlesi mutlaka okuyucuya doğrudan hitap eden, yoruma ve kendi deneyimini paylaşmaya teşvik eden samimi bir soru olmalıdır.
   - Örn: "Siz daha önce mülk alımında veya hisseli tapuda benzer bir durumla karşılaştınız mı? Yorumlarda buluşalım." veya "Sizce bölgenizde arsa yatırımı mı yoksa konut mu daha avantajlı? Fikirlerinizi paylaşın."
4. HASHTAG BLOĞU (EN FAZLA 5 ADET):
   - Çoğu sosyal medya platformu en fazla 5 etiketi kabul eder veya verimli görür. Bu yüzden ASLA 5'ten fazla hashtag yazma (en fazla 3-5 adet).
   - Sorunun ardından 1 satır boşluk bırakılarak eklenir.
   - Örn: #EDMYapıGayrimenkul #Silivri #Gayrimenkul #Arsa #Yatırım
- Threads: Karakter sınırı katıdır (%(threads)d karakter altı). Hook + kısa özet + etkileşim sorusu + 3-4 hashtag şeklinde tek nefeslik yaz.
- Facebook: Instagram metninin biraz daha detaylı ve açıklayıcı hali (en fazla 5 hashtag).
- Hiçbir caption'da "link bio'da" yazma; hesapta henüz yönlendirme yok.
""" % BUTCE


# ---------------------------------------------------------------------------
# Biçim şemaları
# ---------------------------------------------------------------------------

_SEMA_B1 = """BİÇİM: B1 — RİSK DOSYASI (Dinamik 4-8 Slayt)
Bir tuzak ve ondan somut korunma mekanizması.

Slayt 2 detay analizi: Konunun gereksinimine göre 1 ile 4 arasında kart (`kartlar`) içerebilir.
- Tek bir risk/tuzak varsa: 1 kart yeterlidir.
- Karşılaştırma veya iki durum varsa: 2 kart (`kart_1` ve `kart_2`).
- Çok yönlü bir risk varsa: 3 veya 4 kart.
ASLA yapay karşıtlık veya dolgu madde uydurma.

Slayt 3 çözüm adımları: 2 ile 5 arasında somut, uygulanabilir adımdır (`maddeler`).
Her adım okuyanın yarın tapuda, belediyede veya noter kanalıyla yapabileceği bir işlem olmalı;
"dikkatli olun" gibi soyut nasihat değil.

JSON:
{
  "bicim": "B1",
  "kategori_kodu": "TAPU_VE_HUKUK | EV_SAHIBI_VE_KIRACI | YATIRIM_VE_PIYASA | ARSA_IMAR_VE_TINY_HOUSE | SEKTOREL_HABER_VE_ANALIZ",
  "rozet_metni": "En fazla %(rozet)d karakter (örn: TAPU REHBERİ // İMAR MEVZUATI)",
  "yasal_dayanak": "En fazla %(yasal_dayanak)d karakter. Brief'te mevzuat yoksa konu tanımı yaz",
  "manset_parca_1": "≤%(manset_satir)d karakter",
  "manset_vurgu": "≤%(manset_satir)d karakter, BÜYÜK HARF",
  "manset_parca_2": "≤%(manset_satir)d karakter",
  "spot": "≤%(spot)d karakter. Riski tek nefeste anlatan 2 cümle",
  "slayt_2_detay": {
    "baslik_satir_1": "≤%(manset_satir)d karakter",
    "baslik_vurgu": "≤%(manset_satir)d karakter, BÜYÜK HARF",
    "kartlar": [
      {
        "etiket": "≤%(rozet)d karakter (örn: RİSKİN SEBEBİ // YASAL ÇERÇEVE)",
        "renk": "kirmizi | yesil | gri",
        "baslik": "≤%(kart_baslik)d karakter",
        "aciklama": "≤%(kart_aciklama)d karakter. Somut mekanizma ve tam cümle"
      }
    ],
    "kart_1": {
      "etiket": "≤%(rozet)d karakter",
      "renk": "kirmizi",
      "baslik": "≤%(kart_baslik)d karakter",
      "aciklama": "≤%(kart_aciklama)d karakter"
    },
    "kart_2": {
      "etiket": "≤%(rozet)d karakter",
      "renk": "yesil",
      "baslik": "≤%(kart_baslik)d karakter",
      "aciklama": "≤%(kart_aciklama)d karakter"
    }
  },
  "slayt_3_cozum": {
    "tip": "adim_adim_rehber",
    "baslik_ust": "≤%(manset_satir)d karakter",
    "baslik_vurgu": "≤%(manset_satir)d karakter",
    "maddeler": [
      {"no": "01", "baslik": "≤%(adim_baslik)d karakter", "aciklama": "≤%(adim_aciklama)d karakter"},
      {"no": "02", "baslik": "≤%(adim_baslik)d karakter", "aciklama": "≤%(adim_aciklama)d karakter"}
    ]
  },
  "slayt_4_cta": {
    "slogan_parca_1": "≤%(manset_satir)d karakter",
    "slogan_vurgu": "≤%(manset_satir)d karakter",
    "aciklama": "≤%(spot)d karakter",
    "kaydet_metni": "Kaydetme çağrısı, tek cümle"
  },
  "onem_puani": 9,
  "caption_instagram": "Hook ile başla, 2-3 kısa paragraf çözüm anlat, etkileşim sorusu (?) ile bitir ve en fazla 5 hashtag ekle (#EDMYapıGayrimenkul #Silivri #Gayrimenkul #Arsa #Yatırım).",
  "caption_facebook": "Instagram metninin biraz daha detaylı hali. Hook + gövde + soru (?) + en fazla 5 hashtag.",
  "caption_threads": "≤%(threads)d karakter. Hook + kısa gövde + soru (?) + 3-4 hashtag."
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
  "caption_instagram": "Hook ile başla, 2-3 kısa paragraf karşılaştırmayı ve stratejiyi anlat, soru (?) ile bitir ve en fazla 5 hashtag ekle (#EDMYapıGayrimenkul #Silivri #Gayrimenkul #Arsa #Yatırım).",
  "caption_facebook": "Instagram metninin biraz daha detaylı hali. Hook + gövde + soru (?) + en fazla 5 hashtag.",
  "caption_threads": "≤%(threads)d karakter. Hook + kısa karşılaştırma + soru (?) + 3-4 hashtag."
}
Ölçüt başlıkları ≤24, değerler ≤26 karakter olsun; kolona sığması gerekiyor.

VERİ KAYNAĞI VERİLMEMİŞSE: kolon değerleri SAYISAL OLMAZ. "%%40-55", "18.000 TL",
"14-16 yıl" gibi uydurulmuş rakamlar yerine niteliksel karşılaştırma yaz:
"Düzenli aylık gelir", "Doğrudan gelir yok", "Sabit gideri yüksek", "Gideri
yok denecek kadar az", "Hızlı nakde çevrilir", "Alıcı bulması zaman alır".
Manşetteki vurgu da rakam içermez; farkın YÖNÜNÜ söyler.""" % BUTCE

_SEMA_B3 = """BİÇİM: B3 — NET CEVAP VE ÇÖZÜM REHBERİ (4-5 slayt carousel)
Yaygın bir soru, net cevabı, analiz kartları ve çözüm adımları.

Cevap ilk kelimeden belli olsun: "Hayır.", "Evet, ama...", "En fazla üç aylık kira."
Kaçamak cevap bu biçimi öldürür. Gerekçe net, kaynağı belirtilmiş.

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
  "slayt_3_cozum": {
    "tip": "adim_adim_rehber",
    "baslik_ust": "≤%(manset_satir)d karakter",
    "baslik_vurgu": "≤%(manset_satir)d karakter",
    "maddeler": [
      {"no": "01", "baslik": "≤%(adim_baslik)d karakter", "aciklama": "≤%(adim_aciklama)d karakter"},
      {"no": "02", "baslik": "≤%(adim_baslik)d karakter", "aciklama": "≤%(adim_aciklama)d karakter"}
    ]
  },
  "slayt_4_cta": {
    "slogan_parca_1": "≤%(manset_satir)d karakter",
    "slogan_vurgu": "≤%(manset_satir)d karakter",
    "aciklama": "≤%(spot)d karakter",
    "kaydet_metni": "Kaydetme çağrısı, tek cümle"
  },
  "onem_puani": 7,
  "caption_instagram": "Hook ile başla, net cevabı ve yasal çerçeveyi 2-3 kısa paragrafta açıkla, soru (?) ile bitir ve en fazla 5 hashtag ekle (#EDMYapıGayrimenkul #Silivri #Gayrimenkul #Arsa #Yatırım).",
  "caption_facebook": "Instagram metninin biraz daha detaylı hali. Hook + net cevap ve çözüm + soru (?) + en fazla 5 hashtag.",
  "caption_threads": "≤%(threads)d karakter. Hook + net cevap + soru (?) + 3-4 hashtag."
}
kart_1 sık yapılan yanlışı, kart_2 doğru yasal çerçeveyi anlatır.
slayt_3_cozum maddeleri atılması gereken somut adımları listeler.""" % BUTCE

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

_TUKENMIS: set[tuple[str, str]] = set()


def _anahtarlari_al() -> List[Tuple[str, str]]:
    """Denenecek API anahtarlarını döner."""
    anahtarlar = []
    ana = config.env_al("GEMINI_API_KEY")
    if ana:
        anahtarlar.append(("birincil", ana))
    yedek = config.env_al("GEMINI_API_KEY_2") or config.env_al("GEMINI_IMAGE_API_KEY")
    if yedek and yedek != ana:
        anahtarlar.append(("yedek", yedek))
    return anahtarlar


def _gunluk_kota_hatasi(cevap: Any) -> bool:
    if isinstance(cevap, dict):
        mesaj = str(cevap.get("error", {}).get("message", ""))
    else:
        mesaj = str(cevap)
    return "PerDay" in mesaj or "per day" in mesaj.lower()


def _gemini_cagri(
    prompt: str,
    sistem_talimati: str,
    sicaklik: float = 0.7,
    modeller: Optional[List[str]] = None,
) -> Optional[str]:
    """Model zincirini ve yedek anahtarları sırayla dener."""
    anahtarlar = _anahtarlari_al()
    if not anahtarlar:
        log.warning("Hiçbir GEMINI_API_KEY tanımlanmamış")
        return None

    payload = {
        "system_instruction": {"parts": [{"text": sistem_talimati}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": sicaklik, "responseMimeType": "application/json"},
    }

    for anahtar_adi, api_key in anahtarlar:
        headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
        for model in (modeller or MODELLER):
            if (model, anahtar_adi) in _TUKENMIS:
                log.debug("%s/%s günlük kotası tükenmiş, atlanıyor", model, anahtar_adi)
                continue

            url = GEMINI_API_URL.format(model=model)
            for _ in range(2):
                try:
                    resp = requests.post(url, headers=headers, json=payload, timeout=35)
                    if resp.status_code == 200:
                        veri = resp.json()
                        candidates = veri.get("candidates", [])
                        if candidates:
                            c = candidates[0]
                            sebep = c.get("finishReason", "STOP")
                            if sebep in ("SAFETY", "RECITATION", "BLOCKLIST"):
                                log.warning(
                                    "%s güvenlik filtresine takıldı (finishReason=%s), sıradaki modele geçiliyor",
                                    model,
                                    sebep,
                                )
                                break
                            parts = c.get("content", {}).get("parts", [])
                            if parts and "text" in parts[0]:
                                log.info("Yanıt veren model: %s (%s)", model, anahtar_adi)
                                return parts[0]["text"]
                        log.warning("%s adayı boş döndü, sıradaki model", model)
                        break

                    if resp.status_code == 429:
                        try:
                            if _gunluk_kota_hatasi(resp.json()):
                                _TUKENMIS.add((model, anahtar_adi))
                                log.warning(
                                    "%s/%s günlük kotası doldu, bu çalıştırmada tekrar denenmeyecek",
                                    model,
                                    anahtar_adi,
                                )
                        except Exception:
                            pass
                        log.warning("%s hız/kota sınırında [%d], sıradaki modele geçiliyor", model, resp.status_code)
                        break

                    if resp.status_code in (500, 503):
                        log.warning("%s sunucu yoğun [%d], sıradaki modele geçiliyor", model, resp.status_code)
                        break

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

    for i, k in enumerate(_yoldan_al_liste(veri, "slayt_2_detay.kartlar")):
        for alan, anahtar in (("etiket", "rozet"), ("baslik", "kart_baslik"), ("aciklama", "kart_aciklama")):
            d = k.get(alan)
            if isinstance(d, str) and len(d) > BUTCE[anahtar]:
                ihlaller.append(f"slayt_2_detay.kartlar[{i}].{alan}: {len(d)}/{BUTCE[anahtar]} karakter")

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
        return _unlemleri_kaldir(filtre.markdown_temizle(veri))
def manset_birlestir(veri: Dict[str, Any]) -> str:
    """Üç parçalı manşeti tek metne çevirir (veritabanı ve Telegram önizlemesi için)."""
    if not isinstance(veri, dict):
        return ""
    if veri.get("manset"):
        return str(veri["manset"]).strip()
    return " ".join(
        p.strip() for p in (
            veri.get("manset_parca_1"), veri.get("manset_vurgu"), veri.get("manset_parca_2")
        ) if p
    ).strip()


def caption_zenginlestir(
    caption: str,
    kategori_kodu: Optional[str] = None,
    konu_kodu: Optional[str] = None,
    platform: str = "instagram",
    manset: Optional[str] = None,
) -> str:
    """
    Açıklama metnini (caption) kurumsal EDM 4 bloklu standart mimarisine dönüştürür:
    1. Blok: Hook (Kaydırmayı anında durduran kanca)
    2. Blok: Gövde (Halk dilinde, akıcı kısa paragraflar)
    3. Blok: Etkileşim Sorusu (Yorum ve tartışmayı teşvik eden samimi soru (?))
    4. Blok: Hashtag Bloğu (Marka, bölge ve konuya özel temiz etiketler)

    İdempotenttir: Zaten zenginleştirilmiş bir metne tekrar uygulandığında soru veya hashtag tekrarlamaz.
    """
    ham = filtre.markdown_temizle(caption or "").strip()
    ham = _unlemleri_kaldir(ham).strip()
    if not ham and manset:
        ham = _unlemleri_kaldir(filtre.markdown_temizle(manset)).strip()
    if not ham:
        return ""

    # 1. Mevcut hashtag'leri ayıkla ve metnin sonundaki hashtag bloğunu gövdeden ayır
    mevcut_etiketler = re.findall(r"#[A-Za-z0-9ÇĞİÖŞÜçğıöşü_]+", ham)
    govde = re.sub(r"(?:[\s\n]*#[A-Za-z0-9ÇĞİÖŞÜçğıöşü_]+)+$", "", ham).strip()
    govde = re.sub(r"^(?:Açıklama|Instagram|Facebook|Threads|Caption|Metin|Post)\s*:\s*", "", govde, flags=re.IGNORECASE).strip()

    if not govde:
        govde = manset or ham

    # 2. Hook Kontrolü: Eğer ilk satır çok kısaysa (<25 karakter) ve manşet varsa manşetle zenginleştir
    satirlar = [s.strip() for s in govde.split("\n") if s.strip()]
    if satirlar and len(satirlar[0]) < 25 and manset and manset.strip() not in satirlar[0]:
        govde = f"{manset.strip()}\n\n{govde}"

    # 3. Kapanış Sorusu (?) Kontrolü
    soru = ""
    son_kisim = govde[-250:] if len(govde) > 250 else govde
    if "?" not in son_kisim:
        kategori_ust = (kategori_kodu or "").upper()
        govde_kucuk = filtre.kucult(govde)

        if any(w in govde_kucuk for w in ["şufa", "hisseli", "hisse", "tapu", "miras", "paydaş", "intikal", "ferağ"]):
            soru = "Siz tapu işlemlerinizde veya hisseli mülk alımında benzer bir durumla karşılaştınız mı? Yorumlarda buluşalım."
        elif any(w in govde_kucuk for w in ["kira", "kiracı", "ev sahibi", "tahliye", "kontrat", "depozito"]):
            soru = "Sizce kira ve tahliye süreçlerinde en çok nelere dikkat edilmeli? Deneyimlerinizi yorumlarda paylaşın."
        elif any(w in govde_kucuk for w in ["arsa", "tarla", "imar", "ifraz", "parsel", "tiny house", "ruhsat"]):
            soru = "Silivri veya Trakya genelinde arsa bakarken imar durumunda en çok neye dikkat ediyorsunuz? Fikirlerinizi yazın."
        elif any(w in govde_kucuk for w in ["kredi", "faiz", "banka", "mevduat", "bddk", "enflasyon", "ekspertiz"]):
            soru = "Sizce şu anki piyasa şartlarında arsa yatırımı mı yoksa mevduat veya konut mu daha avantajlı? Ne düşünüyorsunuz?"
        elif "ILAN" in kategori_ust or any(w in govde_kucuk for w in ["satılık", "kiralık", "portföy", "m²"]):
            soru = "Bu portföyümüz hakkında detaylı bilgi ve yerinde inceleme için bize hemen ulaşabilirsiniz. Ne düşünüyorsunuz?"
        elif "ARSA" in kategori_ust:
            soru = "Silivri ve Trakya'da arsa alırken en çok hangi bölgeyi tercih ediyorsunuz? Yorumlarda paylaşın."
        elif "EV_SAHIBI" in kategori_ust:
            soru = "Sizce kiracı ve ev sahibi ilişkilerinde en sağlıklı çözüm nedir? Yorumlarda buluşalım."
        elif "FINANS" in kategori_ust:
            soru = "Siz birikiminizi değerlendirirken gayrimenkulü hangi sırada tutuyorsunuz? Yorumlarda buluşalım."
        else:
            soru = "Siz bu konuda ne düşünüyorsunuz? Görüş ve tecrübelerinizi yorumlarda bekliyoruz."

        govde = f"{govde}\n\n{soru}"
    else:
        for p in reversed(govde.split("\n")):
            p_strip = p.strip()
            if "?" in p_strip:
                soru = p_strip
                break

    # 4. Hashtag Bloğunu Hazırla
    platform_key = platform.lower()
    sabitler_ayar = config.ayar_al(f"sosyal.sabit_hashtagler.{platform_key}") or config.ayar_al("sosyal.sabit_hashtagler.instagram")
    varsayilan_sabitler = [
        "#EDMYapıGayrimenkul",
        "#Silivri",
        "#Gayrimenkul",
        "#Arsa",
        "#Yatırım",
    ]
    sabit_liste = sabitler_ayar if (sabitler_ayar and isinstance(sabitler_ayar, list)) else varsayilan_sabitler

    konu_etiketleri: List[str] = []
    kategori_ust = (kategori_kodu or "").upper()
    govde_kucuk = filtre.kucult(ham or govde)
    if soru and filtre.kucult(soru) in govde_kucuk:
        govde_kucuk = govde_kucuk.replace(filtre.kucult(soru), "")

    if "FINANS" in kategori_ust or any(w in govde_kucuk for w in ["kredi", "faiz", "banka", "finans", "bddk"]):
        konu_etiketleri.extend(["#KonutKredisi", "#EmlakYatırımı"])
    if "TAPU" in kategori_ust or any(w in govde_kucuk for w in ["tapu", "şufa", "hisseli", "miras", "hisse", "paydaş"]):
        konu_etiketleri.extend(["#TapuRehberi", "#HisseliTapu"])
    if "EV_SAHIBI" in kategori_ust or "KIRA" in kategori_ust or any(w in govde_kucuk for w in ["kira", "kiracı", "tahliye", "ev sahibi"]):
        konu_etiketleri.extend(["#KiraSözleşmesi", "#EvSahibiKiracı"])
    if "ARSA" in kategori_ust or "IMAR" in kategori_ust or any(w in govde_kucuk for w in ["arsa", "tarla", "parsel", "imar", "tiny house"]):
        konu_etiketleri.extend(["#SilivriArsa", "#TrakyaArsa", "#İmar"])

    # Marka ve bölgeyi her zaman önceliklendir (sabit listenin ilk 2'si), ardından konu ve mevcut etiketler, sonra kalan sabitler
    oncelikli_sabitler = sabit_liste[:2] if len(sabit_liste) >= 2 else sabit_liste
    kalan_sabitler = sabit_liste[2:] if len(sabit_liste) >= 2 else []
    tum_adaylar = oncelikli_sabitler + mevcut_etiketler + konu_etiketleri + kalan_sabitler

    gorulen = set()
    nihai_etiketler: List[str] = []
    for tag in tum_adaylar:
        t = tag.strip()
        if not t.startswith("#"):
            t = f"#{t}"
        k = filtre.kucult(t)
        if k not in gorulen and len(t) > 2:
            gorulen.add(k)
            nihai_etiketler.append(t)

    # 5. Platform Uyarlaması
    if platform_key == "tiktok":
        from . import tiktok
        kanca_baslik = satirlar[0] if satirlar else (manset or govde)
        return tiktok.baslik_kur(kanca_baslik, nihai_etiketler)

    if platform_key == "threads":
        th_etiketler = nihai_etiketler[:4]
        tag_str = " ".join(th_etiketler)

        if len(govde) + len(tag_str) + 2 <= 480:
            return f"{govde}\n\n{tag_str}".strip()

        th_etiketler = nihai_etiketler[:2]
        tag_str = " ".join(th_etiketler)
        if len(govde) + len(tag_str) + 2 <= 480:
            return f"{govde}\n\n{tag_str}".strip()

        # Metin çok uzunsa: soruyu ve etiketleri koruyarak ana gövdeyi kısalt
        if soru and soru in govde:
            ana_metin = govde.rsplit(soru, 1)[0].strip()
            kalan_yer = 480 - len(soru) - len(tag_str) - 8
            if kalan_yer > 40:
                kirpilmis = ana_metin[:kalan_yer]
                son_bosluk = kirpilmis.rfind(" ")
                if son_bosluk > 30:
                    kirpilmis = kirpilmis[:son_bosluk]
                govde = f"{kirpilmis.strip()}...\n\n{soru}"
                return f"{govde}\n\n{tag_str}".strip()

        kalan_yer = 480 - len(tag_str) - 6
        if kalan_yer > 80:
            kirpilmis = govde[:kalan_yer]
            son_bosluk = kirpilmis.rfind(" ")
            if son_bosluk > 60:
                kirpilmis = kirpilmis[:son_bosluk]
            govde = kirpilmis.strip() + "..."
            return f"{govde}\n\n{tag_str}".strip()
        else:
            return f"{govde[:475].strip()}..."

    secilen_etiketler = nihai_etiketler[:5]
    tag_str = " ".join(secilen_etiketler)
    return f"{govde}\n\n{tag_str}".strip()


def _captionlari_zenginlestir(veri: Dict[str, Any]) -> Dict[str, Any]:
    """Sözlükteki caption alanlarını hook, soru ve hashtag ile zenginleştirir."""
    if not isinstance(veri, dict):
        return veri
    kat = veri.get("kategori_kodu")
    man = manset_birlestir(veri)

    if veri.get("caption_instagram"):
        veri["caption_instagram"] = caption_zenginlestir(
            veri["caption_instagram"], kategori_kodu=kat, platform="instagram", manset=man
        )

    if veri.get("caption_facebook"):
        veri["caption_facebook"] = caption_zenginlestir(
            veri["caption_facebook"], kategori_kodu=kat, platform="facebook", manset=man
        )
    elif veri.get("caption_instagram"):
        veri["caption_facebook"] = caption_zenginlestir(
            veri["caption_instagram"], kategori_kodu=kat, platform="facebook", manset=man
        )

    if veri.get("caption_threads"):
        veri["caption_threads"] = caption_zenginlestir(
            veri["caption_threads"], kategori_kodu=kat, platform="threads", manset=man
        )
    elif veri.get("caption_instagram"):
        veri["caption_threads"] = caption_zenginlestir(
            veri["caption_instagram"], kategori_kodu=kat, platform="threads", manset=man
        )
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
    _captionlari_zenginlestir(veri)

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
    _captionlari_zenginlestir(veri2)

    kalan = butce_ihlalleri(veri2)
    if kalan:
        log.warning("Onarım sonrası hâlâ taşan alan var: %s", "; ".join(kalan))
    return veri2


def konudan_uret(konu: Dict[str, Any], format_turu: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Konu bankası kaydından slayt içeriği üretir. Faz 1'in ana giriş noktası."""
    from . import konu_bankasi

    bicim = konu.get("bicim", "B1")
    girdi = (
        konu_bankasi.brief_metni(konu)
        + "\n\nBu brief'i yukarıdaki biçim şemasına göre işle. "
        "AÇI alanındaki bakış açısı içeriğin merkezi olsun."
    )
    if format_turu in ("nedir_dogrusu", "dogrusu"):
        girdi += (
            "\n\nÖNEMLİ FORMAT TALEBİ: Bu içeriği 'NEDİR DOĞRUSU? (DOĞRU BİLİNEN YANLIŞLAR)' formatında üret. "
            "JSON nesnesinde 'format_turu': 'nedir_dogrusu', "
            "'yanlis_metin': (Vatandaşın veya kiracının/yatırımcının inandığı yaygın yanlış / şehir efsanesi - tek ve vurucu cümle), "
            "'dogru_metin': (Kanunen ve hukuken işin esası ve yasal dayanak maddesi - 2-3 cümle. "
            "Yargıtay kararı numarası veya tarihi YAZMA: brief'te içtihat yok, uydurulmuş karar "
            "numarası gerçek bir ofisin hesabında ağır sorumluluktur), "
            "'altin_kural': (EDM Altın Kuralı: Kısa ve net uzman tavsiyesi) alanlarını MUTLAKA doldur."
        )
    elif format_turu in ("sozluk", "sozluk_uret"):
        girdi += (
            "\n\nÖNEMLİ FORMAT TALEBİ: Bu içeriği 'EDM GAYRİMENKUL SÖZLÜĞÜ' formatında üret. "
            "JSON nesnesinde 'format_turu': 'sozluk', "
            "'terim': (Konunun odaklandığı gayrimenkul/imar/tapu hukuku terimi - örn: ŞUFA, İFRAZ, vb.), "
            "'tanim_metni': (Terimin sadece sözlük karşılığını değil; gayrimenkul ve tapu pratiğinde ne anlama geldiğini, yasal dayanak maddesini ve taraflara etkisini 2-3 akıcı ve doyurucu cümleyle izah eden zengin hukuki açıklama), "
            "'puf_maddeleri': [(Yatırımcının bilmesi gereken 2-3 kritik kural ve risk)] alanlarını MUTLAKA doldur."
        )
    elif format_turu in ("vaka", "emsal_karar"):
        girdi += (
            "\n\nÖNEMLİ FORMAT TALEBİ: Bu içeriği 'HUKUKİ VAKA ANALİZİ' formatında üret. "
            "JSON nesnesinde 'format_turu': 'vaka', 'vaka_kodu': '01 / ÖRNEK OLAY', "
            "'yargitay_kaynak': (Yalnızca brief'teki mevzuat maddesi; Yargıtay esas/karar numarası UYDURMA), "
            "'manset': (Çarpıcı başlık), 'olay_detay': (Tipik bir olay örneği — gerçek bir dava gibi sunma), "
            "'yargitay_hukmu': (Kanun maddesine göre sonuç; belirli bir mahkeme kararına atıf yapma), "
            "'cikarilacak_ders': (Yatırımcının çıkarması gereken ders) alanlarını MUTLAKA doldur."
        )
    elif format_turu in ("net_cevap", "soru", "kim_hakli"):
        girdi += (
            "\n\nÖNEMLİ FORMAT TALEBİ: Bu içeriği 'NET CEVAP REHBERİ' formatında üret. "
            "JSON nesnesinde 'format_turu': 'net_cevap', 'soru': (Net soru?), 'net_cevap': 'CEVAP: ...', "
            "'aciklama': (Gerekçe ve hukuki açıklama), 'tavsiye_metin': (Resmi adım ve tavsiye) alanlarını MUTLAKA doldur."
        )

    veri = _uret(girdi, bicim)
    if veri:
        veri.setdefault("bicim", bicim)
        if format_turu:
            veri["format_turu"] = format_turu
        veri["konu_kodu"] = konu["kod"]
        # Brief'i sakla: dogrula.py metindeki mevzuat ve yerel bağ iddialarını
        # bununla karşılaştırıyor. Onay önizlemesinde uyarı olarak görünüyor.
        veri["_brief"] = {
            "mevzuat": konu.get("mevzuat"),
            "yerel": konu.get("yerel"),
            "veri_kaynagi": konu.get("veri_kaynagi"),
        }
        # Güncel madde metni DB'ye yazılmaz (git'e gidiyor, şişer); dogrula.py
        # denetim anında "mevzuat" atfından önbellekli olarak çeker.
    return veri


def otorite_icerigi_uret(
    konu_veya_haber: Any,
    kategori_kodu: Optional[str] = None,
    bicim: str = "B1",
    ek_talimat: Optional[str] = None,
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
        if len((ozet or "").strip()) < 200:
            girdi += (
                "\n⚠️ DİKKAT: Kaynakta bu haber hakkında çok az bilgi var. "
                "Bilgiyi genişletme, olmayan detay/olay/sebep UYDURMA, yalnızca verilen "
                "somut olguları yaz. Bilgi yetersizse genel geçer cümlelerle doldurma, "
                "kısa ve net bırak.\n"
            )
        bicim = "B5"
    else:
        girdi = f"İŞLENECEK KONU: {konu_veya_haber}\n"

    if kategori_kodu:
        girdi += f"HEDEF KATEGORİ: {kategori_kodu}\n"
    if ek_talimat:
        girdi += f"\nEK EDİTORYAL TALİMAT: {ek_talimat}\n"
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


def haber_metinleri_uret(haber: Dict[str, Any], ek_talimat: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Geriye dönük uyumlu haber girişi — B5 biçimine yönlendirir."""
    return otorite_icerigi_uret(haber, bicim="B5", ek_talimat=ek_talimat)


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
        sonuc = _temizle(json.loads(ham))
        baslik = ilan.get("baslik")
        if "ig_caption" in sonuc and sonuc["ig_caption"]:
            sonuc["ig_caption"] = caption_zenginlestir(sonuc["ig_caption"], kategori_kodu="ILAN", platform="instagram", manset=baslik)
        if "fb_caption" in sonuc and sonuc["fb_caption"]:
            sonuc["fb_caption"] = caption_zenginlestir(sonuc["fb_caption"], kategori_kodu="ILAN", platform="facebook", manset=baslik)
        if "threads_metin" in sonuc and sonuc["threads_metin"]:
            sonuc["threads_metin"] = caption_zenginlestir(sonuc["threads_metin"], kategori_kodu="ILAN", platform="threads", manset=baslik)
        return sonuc
    except Exception as e:
        log.error("İlan JSON ayrıştırma hatası: %s", e)
        return None
