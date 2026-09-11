# EDM Sosyal Medya — İçerik Sistemi

Bu belge, `postedm` botunun **ne paylaşacağına** karar veren katmandır. Kod nasıl
paylaşacağını bilir; burası neyin paylaşmaya değer olduğunu tanımlar.

Yapay zekâ bu belgeyi okumaz — bu belge **prompt'ları, konu bankasını ve slayt
bütçelerini** üreten kaynaktır. Biri değişirse diğerleri de değişmelidir.

---

## 1. Neden bu belge var

Sistem teknik olarak çalışıyordu ama ortaya iyi içerik çıkmıyordu. Sebep modelin
zayıflığı değil, zincirdeki dört kırıktı:

**a) Konu kaynağı tek başına RSS'ti, RSS de çöp getiriyordu.**
`_emlak_alakali_mi()` VEYA mantığıyla çalışıyor: anahtar kelimelerden biri tutarsa
haber geçiyor. Veritabanındaki gerçek kayıtlar:

| Başlık | Neden geçti | Önem puanı |
|---|---|---|
| "Selçuk Mızraklı bugün tahliye oluyor" | `tahliye` eşleşti | 8 |
| "Euro Bölgesi'nde Sentix hareketi" | `faiz` eşleşti | 8 |

Sonra bu haber Gemini'ye "EDM standartlarında 4 slaytlık otorite içeriğine
dönüştür" diye veriliyordu. Model de alakasız haberden otorite içeriği
uyduruyordu. **Çöp girdi, çöp çıktı — modelin suçu değil.**

**b) Tek kalıp her konuya zorlanıyordu.**
`SİSTEM_TALİMATI_OTORITE` her şeyi aynı iskelete sokuyor: kapak → kart_1 vs kart_2
→ 3 adım → CTA. Şufa davası için mükemmel; "TCMB faiz kararı" için anlamsız.
Karşılaştırılacak iki taraf olmayan konularda model karşıtlık **uyduruyor**.

**c) Prompt ile çizici birbirini tanımıyordu — metin sessizce kesiliyordu.**
Prompt slayt 2 kartları için "35-45 kelime" istiyor. `make_image.py` ise
`[:4]` ile dört satırda kırpıyor. Ölçtük: o kutuya ~40 kelime *tam sınırda*
sığıyor. Sonuç `revize_v4_perfect_02_detay.jpg`'de görünüyor — kart cümlenin
ortasında, "…belgeyi geçersiz" diye bitiyor. Uyarı yok, hata yok.

**d) Sabit yükseklikli kartlar alt tarafı boş bırakıyordu.**
`k_h = 305` sabit. Metin kısaysa kart yarı boş; uzunsa kesiliyor. Slayt 3'te
`kart_h = min(250, …)` tavanı yüzünden üç kartın altında ~300px ölü alan kalıyor —
1350px'lik karenin dörtte biri.

**Kısaca:** model iyi bir brief almıyordu ve çizemeyeceğimiz uzunlukta metin
istiyorduk.

---

## 2. Faz planı

Hedef sıralaması net: **önce kitle, sonra ilan.** Ama "yeteri kadar kitle" ölçülebilir
olmazsa faz hiç değişmez. Eşikler:

| Faz | Takipçi | İçerik karışımı | Amaç |
|---|---|---|---|
| **1 — Otorite** | 0 → 1.500 | %100 bilgi | Erişim ve kaydetme. Sayfa "emlakçı" değil "bilen adam" olarak tanınsın |
| **2 — Karma** | 1.500 → 4.000 | %75 bilgi / %25 portföy | Portföy **vaka olarak** girer: "bu arsa neden 2 yılda değerlendi" |
| **3 — Dönüşüm** | 4.000+ | %60 bilgi / %40 portföy | İlan paylaşımı normalleşir, bilgi içeriği erişimi taşımaya devam eder |

Faz atlama şartı takipçi sayısı **değil**, sağlıklı takipçi sayısıdır. Üç ay üst üste:

- kayıt oranı (save/reach) **> %3**
- takipçi olmayan erişim payı **> %55**

Bu ikisi tutmadan takipçi 1.500'ü geçse bile faz 1'de kalınır. Aksi hâlde ilan
paylaşımı erişimi düşürür ve toparlaması aylar alır.

> **EİDS notu:** Doğrudan portföy ilanı paylaşımı mevzuat gerekçesiyle donduruldu
> (bkz. `MEMORY.md §1`). Faz 2 ve 3'teki "portföy" içeriği ilan değil **vaka
> analizidir**: fiyat/iletişim çağrısı yerine bölge, imar durumu ve değerlenme
> gerekçesi anlatılır. Mevzuat çözülene kadar bu ayrım korunur.

---

## 3. İçerik sütunları

Dört sütun. Her paylaşım tam olarak birine ait; ikisine birden ait olan içerik
odaksızdır ve bölünür.

### S1 — Tapu & Hukuk *(kaydettirir)*
Şufa, hisseli tapu, şerhler, kaparo, vekâletle satış, miras taksimi.
**Neden işler:** okuyan kişi bunu ileride lazım olacak diye kaydeder. Kaydetme,
Instagram'ın en ağır sinyalidir.

### S2 — Kiracı & Ev Sahibi *(paylaştırır)*
Kira artışı, tahliye taahhüdü, depozito, tadilat sorumluluğu, ihtarname.
**Neden işler:** Türkiye'de herkes bu masanın bir tarafında. İçerik bir tartışmayı
bitirdiği için WhatsApp'a atılır. En yüksek paylaşım oranı bu sütunda.

### S3 — Arsa, İmar & Toprak *(EDM'yi ayrıştırır)*
TAKS/KAKS, tarla vasfı, yola cephe, ifraz/tevhid, kadastro, tiny house.
**Neden işler:** portföyün yarısı arsa/tarla ve marka kimliği konut değil **toprak**
üzerine kurulu (bkz. site `CLAUDE.md`). Rakiplerin çoğu bu konuyu bilmiyor.

### S4 — Rakam & Bölge *(yerelleştirir)*
Silivri mahalle m² fiyatları, kira çarpanı, TÜFE kira tavanı, konut vs arsa getirisi.
**Neden işler:** yerel takipçi getirir — yani gerçekten müşteri olabilecek takipçi.
Yorum motoru: insanlar kendi mahallesini sorar.

**Sütun dağılımı (haftalık 5 paylaşım):** S1 ×1 · S2 ×2 · S3 ×1 · S4 ×1
S2 iki kez çünkü kitlesi en geniş; S4 bölgesel bağı canlı tutar.

---

## 4. Paylaşım biçimleri

Tek biçim yerine beş. Biçim konuya göre seçilir, konu biçime zorlanmaz.

### B1 — RİSK DOSYASI · 4-7 slayt (karma)
`kapak → analiz → korunma adımları → kapanış`
Bir tuzak ve ondan korunma yolu. Slayt sayısı **içeriğin uzunluğuna göre** değişir
(bkz. §5.5). Kısa içerikte 4, uzun içerikte 7 slayt.
**Ne zaman:** somut bir yanlış yapma riski varsa. **Sütun:** S1, S3.

### B2 — KARŞILAŞTIRMA · 3 slayt
`kapak → iki kolon tablo → stratejist notu`
A mı B mi, rakamla. Konut/arsa, kirala/satın al, tarla/imarlı.
**Ne zaman:** iki gerçek seçenek varsa. **Sütun:** S4.

### B3 — TEK KARE CEVAP · 1 slayt
`soru + net cevap + tek cümle gerekçe`
En ucuz, en sık üretilebilen biçim. Kaydırma gerektirmediği için tamamlanma oranı
%100 — algoritma için değerli.
**Ne zaman:** cevabı tek cümle olan yaygın bir soru. **Sütun:** hepsi.

### B4 — RAKAM KARNESİ · 3 slayt
`başlık → rakam ızgarası → yorum`
Ayın verisi. Tekrarlayan format takipçide alışkanlık yaratır.
**Ne zaman:** ayda bir, veri tazeyken. **Sütun:** S4.

### B5 — HABER YORUMU · 2 slayt
`ne oldu → bu Silivri'de ne demek`
**Ne zaman:** yalnızca gerçekten sektörü ilgilendiren bir gelişme olduğunda.
Varsayılan biçim **değildir** — sistemin eski hatası buydu.

---

## 5. Metin bütçeleri (ölçülmüş, tahmin değil)

Bu tablo `make_image.py`'ın gerçek çizim kapasitesinden ölçüldü. **Prompt'lardaki
kelime sınırları buradan gelir.** Font veya kutu genişliği değişirse
`scripts/metin_butcesi.py` yeniden çalıştırılıp bu tablo güncellenmelidir.

| Alan | Font | Sığan | Prompt bütçesi |
|---|---|---|---|
| Manşet satırı (kapak) | Fraunces 78px | 23 karakter | **≤ 18 karakter/satır, 3 satır** |
| Spot (kapak) | Jakarta 32px ×3 | 189 karakter | **≤ 150 karakter** |
| Kart başlığı (slayt 2) | Jakarta Bold 34px | 53 karakter | **≤ 42 karakter** |
| Kart açıklaması (slayt 2) | Jakarta 29px ×4 | 263 karakter | **≤ 210 karakter (~30 kelime)** |
| Adım başlığı (slayt 3) | Jakarta Bold 33px | 55 karakter | **≤ 44 karakter** |
| Adım açıklaması (slayt 3) | Jakarta 28px ×3 | 196 karakter | **≤ 155 karakter (~23 kelime)** |
| Rozet şeridi | Mono Bold 19px | 56 karakter | **≤ 44 karakter** |
| Yasal dayanak şeridi | Mono Bold 21px | 53 karakter | **≤ 42 karakter** |

Bütçeler sığan miktarın **%80'i** olarak belirlendi. Türkçe kelime uzunluğu
değişkendir ve tam sınıra yazılan metin ilk uzun kelimede taşar.

Bütçe aşılırsa `generate_text._uret()` metni kesmez; modele hangi alanın kaç
karakter taştığını söyleyip **tek onarım turu** çalıştırır. Kesme yapılsaydı
cümle ortasında biten kart sorunu geri gelirdi.

İki güvenlik ağı daha var: `_govde_sigdir()` sığmayan metni kırpmak yerine
puntoyu küçültür, `_dikey_dagit()` ve `_ek_dolgu_hesapla()` kartları ölçüp
kareye dağıtır. Yani prompt yanılsa bile görsel bozulmaz.

---

## 5.5 Slayt mimarisi ve görsel dil

İlk sürümde iç slaytlar bir karede iki dolu kart, üç adım kartı ve bir "kaydet"
şeridi taşıyordu: çerçeveli kutular, 28px gövde, ~60 kelime. Telefonda akışta
kimse okumuyordu. Kurallar değişti.

### Kutu yok, tipografi var

Gruplama çerçeveli kutuyla değil **sol vurgu çizgisi** ve tipografik hiyerarşiyle
yapılır. Kutu, kalabalık hissinin ana kaynağıydı.

| | Önce | Sonra |
|---|---|---|
| Gövde puntosu | 28-29px | **34-40px** |
| Kare başına fikir | 2-3 | **1** (kısa içerikte 2) |
| Çerçeveli kutu | var | **yok** |
| Kaydet şeridi | her slaytta | **hiçbir slaytta — çağrı caption'da** |

### Karma mimari: yoğunluk slayt sayısını belirler

Karar konudan değil **metnin gerçek uzunluğundan** verilir (`make_image._slayt_plani`):

| Bölüm | Eşik | Altındaysa | Üstündeyse |
|---|---|---|---|
| Analiz | iki açıklama toplamı ≤ 290 karakter | tek karede iki fikir | fikir başına bir slayt |
| Adımlar | tüm açıklamalar ≤ 330 karakter | tek karede üç adım | adım başına bir slayt |

Sonuç 4 ile 7 slayt arasında değişir. Kısa içeriği yaymak, uzun içeriği tıkmak
kadar kötüdür.

### Zemin varyantları — dekorasyon değil, anlam

Üç zemin var ve her biri bir şey söyler:

| Zemin | Renk | Kullanım | Metin |
|---|---|---|---|
| `murekkep` | `#121316` | Nötr: adımlar, açıklamalar | Beyaz |
| `kagit` | `#F4F4F3` | "Doğrusu / çözüm" — koyu akıştan sonra nefes | Mürekkep |
| `kirmizi` | `#C4030F` | Yalnızca kritik uyarı | Beyaz |

**Kırmızı zemin carousel başına en fazla bir kez** kullanılır. Marka oranı
%70 nötr / %25 mürekkep / %5 kırmızı; tam sayfa kırmızı bu oranı hızla bozar.
Planlayıcı bu sınırı kendisi uygular.

Kağıt zeminde kırmızı **gövde metninde kullanılmaz** — kontrast 4,4:1, yalnızca
18px üstü metinde veya dolgu olarak geçerli (site `CLAUDE.md` ile aynı kural).

### Kapanış

Kapanış da aynı dile tabidir. Eskiden on öğe taşıyordu (rozet, manşet, spot,
telefon kutusu, adres bloğu, ofis daveti, web/e-posta/sosyal bloğu, kaydet
kutusu, sorumluluk notu, alt bar). Akışta kimse Instagram'dan adres okumuyor.
Kalan dört şey: **ne yaptığımız · tek bir numara · hesap adı · sorumluluk notu.**

Sorumluluk notu `TAPU_VE_HUKUK`, `EV_SAHIBI_VE_KIRACI` ve
`ARSA_IMAR_VE_TINY_HOUSE` kategorilerinde otomatik eklenir (§7.4).

### İki tuval ölçüsü

Aynı içerik iki formatta üretilir. Yerleşim sabit sayılardan değil tuval
boyutundan türetilir (`make_image._yerlesim()`), böylece tek çizim kodu ikisini
de besler.

| Ölçü | Piksel | Nerede | Üst kronik | İçerik alanı |
|---|---|---|---|---|
| `besleme` | 1080×1350 (4:5) | Instagram/Facebook carousel | y=62 | 212 → 1215 |
| `story` | 1080×1920 (9:16) | Reels, Shorts, TikTok, Story | y=180 | 380 → 1580 |

Story'de güvenli alan dar: üstte profil başlığı, altta yanıt çubuğu ve eylem
butonları kareyi kapatıyor. Rozet ve logo da aşağı iner — 4:5'teki y=62'de
kalsalardı platform arayüzünün altında görünmez olurlardı.

```python
otorite_gonderi_slaytlari_uret(veri, cikti_onek="gonderi", olcu="story")
```

### Girdi normalleştirme

Çizim katmanı modelden gelen JSON'un şekline güvenmez. `veriyi_normalize_et()`
tek kapıda tipleri garanti eder: metin beklenen yerde sayı gelirse metne çevrilir,
liste birleştirilir, sözlük düşürülür, `maddeler` liste değilse boşaltılır.

Bu katman sabotaj testinin bulduğu dört çökme sınıfından sonra eklendi. Cron
gözetimsiz çalıştığı için tek bozuk alan o günün paylaşımını düşürmemeli.

### Ortak taban çizgisi

Kapak manşeti alta yaslıdır. Tek fikirli slaytlar ve adım slaytları da aynı taban
çizgisine (`TEK_FIKIR_TABAN = 1120`) oturur. Kaydırırken metin bloğu yerinde
durur, yalnızca zemin ve içerik değişir — carousel'e ritim veren şey budur.

---

## 5.6 Stres ve sabotaj testi

`scripts/stres_testi.py` — 33 vaka × 2 ölçü = **66 koşu**.

**Stres (13 vaka):** geçerli ama uç hacimli içerik — tüm alanlar boş, tek kelime,
bütçenin 2 katı, 10 katı, sarılamayan tek kelime, 10 adım, tek adım, hiç adım,
yoğun Türkçe glif yükü, B2 finansal tablo, B3 tek kare.

**Sabotaj (20 vaka):** bozuk ve düşmanca girdi — boş sözlük, tüm alanlar `None`,
metin yerine sayı/liste/sözlük, `kart_1` sözlük değil, `maddeler` liste değil,
kontrol karakterleri, fontta olmayan glifler, RTL yön değiştirici, şablon
enjeksiyonu, 1 MB'lık tek alan, geçersiz renk ve madde numaraları, erişilemeyen
görsel URL'si.

**Beş denetim:** çökme yok · ölçü doğru · metin güvenli alan dışına piksel
taşırmıyor · slayt boş kalmıyor · süre makul.

Testin bulduğu ve düzeltilen hatalar:

| Hata | Sebep | Düzeltme |
|---|---|---|
| Adım numarası kareyi taşırıyor | `no` hiç sınırlanmıyor; model "Adım 1" yazarsa 150 puntoyla basılıyor | `_adim_numarasi()` iki haneye indirger |
| Uzun kelime sağdan taşıyor | `_metin_sar` boşluksuz kelimeyi bölemiyor | `_kelimeyi_bol()` ikili aramayla böler |
| Kapanış manşeti alttan taşıyor | Satır sınırı yok | `_govde_sigdir` ile iki satıra kilitlendi |
| Rozet kelime ortasından kesiliyor | Ham `[:44]` dilimi | `_rozet_kirp()` kelime sınırında keser |
| Dört ayrı çökme sınıfı | Çizim katmanı JSON tipine güveniyor | `veriyi_normalize_et()` tek kapıda garanti eder |
| Gövde alt bara giriyor | Blok yüksekliği alana kilitli değil | `_blogu_sigdir()` kırpar, son satıra "…" koyar |

Son iki tanesi gözle bakmasa fark edilmezdi; bu yüzden `scripts/kontakt_foy.py`
çıktıları tek föyde toplar. Piksel denetimi taşmayı yakalar, "çirkin mi"
sorusunu yanıtlamaz.

---

## 5.7 Haber bulma algoritması

Haber akışının eski hâli çalışmıyordu ve ölçtüğümüzde sebebi netleşti.

### Ölçüm (2026-09-11)

| Kaynak | Haber | Alakalı | Not |
|---|---|---|---|
| Emlakkulisi | 50 | 16 haber + 4 konu adayı | **Asıl kaynak** |
| AA Ekonomi | 30 | 1 | |
| Ekonomim | 25 | 2 | |
| Bloomberg HT | 20 | 1 | ABD konut fiyatları — kitlemize uzak |
| Hürriyet "Emlak Haberleri" | 100 | **0** | Besleme emlak taşımıyor: "Proforma Fatura Nedir", "Şirket Nasıl Kapatılır" — **çıkarıldı** |

### Düzeltilen üç kusur

**1. Kaynak ağırlığı içeriği eziyordu.** Formül `onem = agirlik + sinyal` idi;
ağırlık 7-10, sinyal 0-10. Sonuç: aynı Yargıtay kararı AA'dan geçiyor,
Hürriyet'ten eleniyordu. *"Silivri imar planı askıya çıktı"* — EDM için
olabilecek en değerli haber — eleniyor, genel bir faiz haberi geçiyordu.
Kaynağın prestiji O HABERİN değerli olduğunu söylemez. Ağırlık artık puana
eklenmiyor, yalnızca eşitlik bozucu.

**2. Türkçe ek yapısı göz ardı ediliyordu.** `\bev sahibi\b` deseni
"ev **sahipleri**"ni tutmuyordu. Emlakkulisi'nde *"Ev sahipleri dikkat! Bu
maddeyi kontrol etmeden tahliye davası açmayın"* bu yüzden eleniyordu — oysa
aradığımız içeriğin tarifi bu. Artık ek-toleranslı eşleşme var
(`haber_puanlama.terim_gecer`), bilinen yanlış eşleşmeler için blokliste ile
("kira" → "Kiraztepe").

**3. Reklam gürültüsü süzülmüyordu.** Emlak kaynaklarının yarısı proje
tanıtımı: *"X projesinde 6 milyon TL'den başlayan fiyatlarla satışta"*. İçinde
"konut" geçtiği için geçiyorlardı. Artık fiyat + reklam kalıbı birlikteyse ilan
sayılıp eleniyor — 50 haberin 14'ü bu kuralla düştü.

### İki kapılı mimari

```
RSS → [1] kural tabanlı puanlama → [2] LLM triyajı → brief → içerik
                     ↓ red                  ↓ "kalıcı bilgi"
                  atılır              konu bankası adayı
```

**1. kapı — `haber_puanlama.degerlendir()`** (ucuz, açıklanabilir)
Tek sayı yerine adlandırılmış bileşenler: `mevzuat`, `eylem`, `yerel`, `kitle`,
`somut`, `taze` ve olumsuzlar `reklam`, `pr`, `uzak`. Haber bir içerik sütununa
(S1-S4) oturmuyorsa bizim işimiz değildir, elenir. Eşik 9.

**2. kapı — `haber_triyaj.triyaj_et()`** (pahalı, sadece eşiği geçene)

> Bu prompt iki kez yazıldı. İlk sürüm modele doğrudan *"bu haberden iyi içerik
> çıkar mı, 1-10 güven ver"* diye soruyordu. Gerçek beslemede sonuç: **5 adayın
> 5'i kabul**, hepsine güven=8, ve kaynakta geçmeyen Silivri bağları uyduruldu
> ("Silivri gibi çeper ilçelerde ezilen kiracılar").
>
> **Ders: modele kendi çıktısını değerlendirmesini söylemek işe yaramıyor.**
> Kibarca "evet" diyor. İkinci sürüm karar sormuyor, doğrulanabilir olgular
> soruyor ve kararı kod veriyor. *"Metinde süre geçiyor mu, alıntıla"* sorusuna
> model güvenilir yanıt verir; *"bu paylaşmaya değer mi"* sorusuna vermez.

Model sekiz olgusal soruyu yanıtlar (her iddia için **metinden birebir alıntı**
zorunlu — uydurmayı kesen şey bu), `_karar_ver()` kararı verir:

| Eleme | Sebep |
|---|---|
| `somut_kural = hayir` | Değişen bir kural/oran/süre yok |
| `dayanak_alintisi = null` | İddia metinde dayanaksız |
| `okuyucu_eylemi = null` | Okuyanın yapacağı bir şey yok |
| `zaten_biliniyor = evet` | Kitlenin bildiği genelleme |
| `tekil_segment = evet` | Yalnızca dar bir kesime hitap ediyor |

Puan: taban 5 · doğrulanmış mevzuat +3 · yakın bölge +3 (İstanbul +1) ·
kalıcı bilgi +2. **Eşik 7.** Merdiven:

| Haber | Puan | |
|---|---|---|
| Mevzuat + yerel + kalıcı | 13 | geçer |
| Yerel + kalıcı | 10 | geçer |
| Ulusal kural değişikliği, kalıcı | 7 | geçer |
| İstanbul, yalnızca güncel | 6 | elenir |
| Ulusal, yalnızca güncel | 5 | elenir |

Taban 4 iken kontrol testinde *"Tapu harcında beyan yükümlülüğü değişti"* 6 puanla
eleniyordu — gerçek bir kural değişikliği, somut sonucu olan, kalıcı bir haber.
Kontrol testi bunun içindir: **her şeye hayır diyen filtre, her şeye evet diyen
kadar işe yaramaz.**

### Beslemenin asıl değeri: konu madenciliği

Gerçek ölçümde 6 adayın 6'sı reddedildi ve bu doğru sonuçtu. Ama red sebebi
yalnızca elemek için değil **yönlendirmek** için kullanılıyor: *"kural
değişikliği yok ama bilgi kalıcı"* = haber değil, **konu adayı**.

*"Temellük nedir?"*, *"Kimler tapu randevusu alabilir?"* gibi başlıklar
insanların gerçekten ne aradığını gösteriyor ve 61 konuluk bankamızda
karşılığı yok. Bunlar `konu_adaylari` tablosuna düşer, `--durum` ile listelenir
ve `aday_yaml_blogu()` ile bankaya yapıştırılabilir blok üretir.

**Otomatik eklenmezler.** Bankaya giren her konu insan gözünden geçmeli;
brief'in kalitesi çıktının kalitesini belirliyor (§5.5).

```bash
python scripts/hazirla.py --konu-madenle   # beslemeden konu adayı çıkar
python scripts/hazirla.py --durum          # bankanın ve adayların durumu
```

---

## 5.8 Model zincirleri

İki ayrı zincir var ve ikisi de canlı ölçümle kuruldu (2026-09-11):

| İş | Zincir | Neden |
|---|---|---|
| **İçerik üretimi** | `3.7-flash` → `3.6-flash` → `flash-latest` → `3.8-flash` → **`flash-lite-latest` → `3.5-flash-lite`** | Kanca kalitesi önemli; ama sonda lite yedekler şart (aşağıya bak) |
| **Triyaj / çıkarım** | `flash-lite-latest` → `3.5-flash-lite` → `3.7-flash` | Yaratıcılık gerekmiyor, hız gerekiyor. Tur başına 6 çağrı |

Ayrım gerçek bir kazanç: triyaj **20-30 sn'den 1,5 sn'ye** indi.

### Her üyesi aynı katmandan olan zincir, yedek zinciri değildir

İlk kurulumda içerik zincirinin dördü de "3.x-flash" katmanındandı. Google
tarafında o katman topluca 503 verdiğinde zincir **246 saniye deneyip boş
döndü** — tek bir içerik bile üretilemedi. Aynı dakikalarda lite modeller
0,6 saniyede yanıt veriyordu.

Bu yüzden zincirin sonunda lite modeller var. Gözetimsiz cron için biraz daha
sade içerik, hiç içerik olmamasından iyidir.

Ayrıca aynı modeli yoğunluk hatasında ikinci kez denemek bırakıldı: 503 ve 429
iki saniyede düzelmiyor, sıradaki modele geçmek hem hızlı hem etkili.

### Kesinti konu bankasını tüketmemeli

Başarısız üretim konuyu `konu_gecmisi`'ne yazıyordu ve orada kalan her kayıt
konuyu KALICI olarak kullanılmış sayıyordu. Yani bir API kesintisi 61 konuluk
bankayı sessizce eritebilirdi. Artık `sonuc='hata'` kayıtları yalnızca
`HATA_BEKLEME_GUNU` (3 gün) boyunca sayılıyor: bozuk bir brief ertesi gün
tekrar denenmez, ama kesinti konuyu yakmaz. **Kesinti, konunun kalitesi
hakkında bir şey söylemez.**

**Modelin listelenmesi kullanılabilir olduğu anlamına gelmiyor.** İlk canlı turda
zincir `["gemini-3.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"]` idi
ve iki ucu da bozuktu: ana model kotayı doldurup 429, son yedek 404
("no longer available"). `/models` listesinde ikisi de görünüyordu. Tek bir içerik
üretimi ~100 saniye sürdü ve üç modeli birden dolaştı.

Zincir değiştirilecekse **gerçek `generateContent` çağrısıyla test edilmeli**,
liste çıktısına güvenilmemeli.

---

## 6. Kanca kütüphanesi

Manşet üç parçadır: `parça_1` (beyaz) + `vurgu` (kırmızı) + `parça_2` (beyaz).
Kırmızı parça **kancadır** — okuyanın durduğu yer orasıdır.

Çalışan altı kalıp:

| Kalıp | İskelet | Örnek |
|---|---|---|
| **Eksik imza** | X alırken **BU İMZAYI UNUTURSANIZ** sonuç | Hisseli tapuda feragatname |
| **Süre** | **2 YIL BOYUNCA** riskin sürer | Şufa hak düşürücü süre |
| **Yaygın yanlış** | Herkesin bildiği yanlış: **ASLINDA TAM TERSİ** | "Tarlaya ev yapılmaz" |
| **Rakam** | **%65 DAHA UCUZ** ama tek şartla | Arsa vs konut girişi |
| **Kim haklı** | Ev sahibi mi kiracı mı? **YARGITAY NE DİYOR** | Depozito iadesi |
| **Belge** | Bu belge olmadan **TAPU DEVRİ YAPILMAZ** | Zorunlu evrak listesi |

**Kancada yasaklar:** ünlem işareti, "ŞOK", "KAÇIRMAYIN", "İNANILMAZ", "SAKIN",
emoji. Marka sesi sakin otorite; bağıran içerik ucuzlatır ve kurumsal kimlikle
çelişir.

---

## 7. Yazım kuralları (prompt'lara birebir geçer)

1. **Ünlem işareti yok.** Hiçbir alanda.
2. **Emin olmadığın kanun maddesi numarası yazma.** Konu bankasında `mevzuat`
   alanı doluysa onu kullan, boşsa madde numarası verme, "ilgili mevzuat" de.
   *Uydurulmuş bir madde numarası gerçek bir emlak ofisinin hesabında ciddi bir
   sorumluluktur — bu kural pazarlık konusu değildir.*
3. **Rakam verirsen kaynağını ver.** "TÜFE 12 aylık ortalaması" gibi. Uydurma oran
   yok.
4. **Hukuki bilgi tavsiye değildir.** Risk dosyalarının kapanışında "bağlayıcı
   hukuki görüş için avukatınıza danışın" satırı bulunur.
5. **Yerel bağ.** Her içerikte Silivri/Trakya bağlantısı kurulabiliyorsa kurulur;
   zorlama olacaksa kurulmaz.
6. **Karşılaştırma uydurma.** İki taraf yoksa B1 biçimi seçilmez, biçim değiştirilir.
7. **Cümle uzunluğu.** Görsel metinlerinde ortalama 12 kelimeyi geçmez. Uzun cümle
   1080px'te okunmuyor.

---

## 8. Haftalık takvim

| Gün | Sütun | Biçim | Not |
|---|---|---|---|
| Pazartesi | S2 Kiracı & Ev Sahibi | B1 Risk Dosyası | Haftanın en geniş kitleli günü |
| Salı | S4 Rakam & Bölge | B3 Tek Kare | Yerel bağ, düşük maliyet |
| Çarşamba | S1 Tapu & Hukuk | B1 Risk Dosyası | Kaydetme günü |
| Perşembe | S3 Arsa & İmar | B3 Tek Kare | EDM'yi ayrıştıran sütun |
| Cuma | S2 veya S4 | B2 Karşılaştırma | Hafta sonu okuması, uzun içerik |

Ayda bir cuma B2 yerine **B4 Rakam Karnesi** girer.
B5 Haber Yorumu takvimin dışındadır; gerçekten haber olduğunda araya girer.

---

## 9. Ölçüm

Takipçi sayısı gecikmeli ve yanıltıcı bir metriktir. Haftalık bakılacaklar:

| Metrik | Neyi söyler | Hedef |
|---|---|---|
| **Kayıt / erişim** | İçerik referans değeri taşıyor mu | > %3 |
| **Paylaşım / erişim** | Tartışma bitiriyor mu | > %1,5 |
| **Takipçi olmayan erişim** | Keşfete düşüyor mu | > %55 |
| **Slayt 1→2 geçişi** | Kanca tutuyor mu | > %65 |
| **Profil ziyareti / erişim** | Otorite merak uyandırıyor mu | > %2 |

**Slayt 1→2 geçişi %65'in altındaysa sorun kancadadır, konuda değil.**
Aynı konu farklı kancayla yeniden denenir — konu bankasında `kanca_kalip`
alanı bunun için var.

---

## 10. Sistemin parçaları

| Dosya | Sorumluluk |
|---|---|
| `ICERIK-SISTEMI.md` | Bu belge. Kararların kaynağı |
| `data/konu_bankasi.yaml` | Evergreen konu havuzu — brief'ler burada |
| `src/konu_bankasi.py` | Sıradaki konuyu seçer, tekrarı önler |
| `src/generate_text.py` | Biçime özel prompt'lar, bütçeler §5'ten |
| `src/fetch_news.py` | Yalnızca B5 için haber süzer — artık varsayılan değil |
| `src/make_image.py` | Dizgi katmanı, zemin varyantları, karma slayt planlayıcı |
| `scripts/metin_butcesi.py` | §5 tablosunu yeniden ölçer |
| `scripts/stres_testi.py` | İki ölçüde stres + sabotaj testi |
| `scripts/kontakt_foy.py` | Test çıktılarını gözle taramak için tek föy |
