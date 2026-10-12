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

### S5 — Finans & Kredi *(2026-09 sonrası eklendi)*
Konut kredisi, cayma hakkı, ekspertiz, DASK, faiz/BDDK. Kodda `sutun.SUTUN_ADLARI` ve konu bankasında 15 konu var. Model yazdığı için
onaysız yayın yolu en sıkı kapıya bağlıdır (§5.5.2 sonu: `dogrula.otomatik_yayina_uygun_mu`).

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
| Adımlar | — | **her zaman adım başına bir slayt** | (aşağıya bakın) |

Sonuç 4 ile 7 slayt arasında değişir. Kısa içeriği yaymak, uzun içeriği tıkmak
kadar kötüdür.

**Adımlar neden birleşmiyor (2026-10-07).** Bu tabloda adımların ≤ 330 karakterde tek karede
toplandığı yazıyordu; kod bunu `0a416a0`'dan beri yapmıyor (Instabot paritesi: her adım kendi
ekranında; `slayt_adimlar_toplu` yalnız eski planlar için duruyor). Ölçüm: format başına slayt
sayısı erişimi belirliyor (tek kare formatlar en düşük erişimdeydi), bu yüzden kısa adımları
birleştirmek yerine **aynı slayt iri dizilir**:

- Kümenin TÜM adımları kısaysa (gövde ≤ 110, başlık ≤ 34 karakter; `make_image.adim_iri_mi`)
  numara 150→190 px, başlık +14, gövde +10 punto büyür. Ölçek küme düzeyinde seçilir; tek tek
  seçilirse ardışık slaytlarda boyut zıplar. Bir cümlelik adımın sayfa doluluğu %34 → %42-50.
- Numara kümenin en uzun bloğuna göre hizalanır (`adim_blok_yuksekligi`): gövdesi tek satıra
  sığan adımın numarası iki satır tutanınkinden aşağıda durup kaydırırken zıplıyordu.
- Örnek Olay'ın 2. slaytında hüküm, rozet ile ders kutusu arasında dikey ortalanır ve sığan en
  büyük puntoda (62'ye kadar) dizilir; eskiden tepeye yapışıktı, ortası boştu.
- **Kapanış slaytı değişmedi** (kullanıcı kararı).

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
| `story` | 1080×1920 (9:16) | Reels, Shorts, TikTok, Story | y=300 | 400 → 1550 |

**9:16 kuralı (kullanıcı kuralı, Instabot'taki `STORY_GUVENLI_PAY` ile aynı):**
9:16 karede TÜM içerik (rozet, logo, başlık, metin, kaynak satırı) 4:5 merkez
kutusunun içinde kalır: y=285..1635. Kutunun dışı yalnızca fotoğraf ve düz
zemindir. İki sonucu var: kare akışta ya da profil ızgarasında 4:5'e kırpılınca
hiçbir şey kesilmez; tam ekranda (Story, Reels, Shorts, TikTok) üst profil
başlığına ve alt yazı/eylem bandına çarpmaz. Kural `scripts/gorsel_denetim.py`
içinde `4:5 KUTU DIŞI` olarak hata seviyesinde denetlenir.

Geçmiş: kural `haber_dailybrief_slayti_ciz` docstring'inde yazılıydı ama kod
260 / H-250 kullanıyordu; üstte rozet y=268'de, altta kaynak satırı y=1730'da
çiziliyordu (2026-10-07 ölçümü: 109 story vakasında 963 ihlal). B2 tablo slaytı
ayrıca 4:5 koordinatlarını (y=60, H-105) sabit yazmıştı.

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

## 5.5.1 Haber tasarımı: Instabot ile aynı (2026-10-07)

Kullanıcı kararı: **haber içeriğinde her şey Instabot'la aynıdır; yalnızca logo ve
renkler EDM'indir.** Bu yüzden haber carousel'i `src/haber_tasarim.py` içinde çizilir ve
bu dosyadaki çizim kodu Instabot'un `src/make_image.py` dosyasından AST ile **birebir**
çıkarılmıştır (yorumlarıyla). Elle yeniden yazılmadı; Instabot'ta bir düzeltme yapılınca
buraya da taşınır (iki dosya karşılaştırılarak).

| | Instabot | postedm haber |
|---|---|---|
| Çizim kodu | `make_image.py` | `haber_tasarim.py` (aynı kod) |
| Ana kare | 1080×1920, içerik 4:5 kutuda | aynı |
| Akış karesi | ortadan 1080×1350 kırpma | aynı (`beslemeye_kirp`) |
| Fotoğraf | yatay: ~1150 px'e iner, göl yansıması, yumuşak perde | aynı |
| Yazı tipi | Inter Variable | aynı dosya (md5 aynı); Türkçe kapsamı ölçüldü, eksik yok |
| Başlık / özet | iri kalın başlık, `**` vurgu, özet, kaynak satırı | aynı |
| Detay sayfaları | 46 punto giriş, vurgu rakamı, alıntı, dengeli sayfalama | aynı |
| Logo | yuvarlak DailyBrief, sol üst | EDM yatay logo, sol üst |
| Renkler | amber vurgu, turkuaz, zümrüt, kategori şeridi | kırmızı vurgu, kireç, kurşun, tek mürekkep zemin |
| Alt bilgi alan adı | dailybrief.co | edmyapigayrimenkul.com |

**EDM yamaları** (Instabot'ta olmayan, aşırı girdide çökme/taşma sabotaj testinde bulundu):
sığmayan tek kelime ve URL satıra bölünür, kaynak adı kanal ikonlarına taşmaz, özetin
"…" soneki kenara taşmaz, satır sonlu başlık çökertmez. Hepsi `# EDM YAMASI` yorumlu.

**Kanca (hook):** kırmızı METİN fotoğraf üstünde okunmuyor (Instabot'ta ölçüldü:
kontrast 2,02, eşik 3,00; sebep göz parlaklığını yeşil kanaldan okuması). Instabot amber'e
geçti; EDM markasında amber yok. Çözüm: kırmızı metin olmaktan çıkıp **dolgu** oldu.
`hook_motoru.KANCA_STILI`: `plaka` (varsayılan: ikinci satır kırmızı plakada beyaz),
`cubuk` (beyaz iki satır + kırmızı çubuk + sınırlı koyu bant), `amber` (Instabot birebir,
yalnız karşılaştırma). Kanca da Instabot'la aynı Inter 900.

**İçerik şeması da Instabot'la aynı (2026-10-07):** model artık `manset` (başlık),
`spot` (tek cümle özet), `detay_yazisi` (120-200 kelime, 4-5 paragraf, `**kalın**`
vurgulu), `kanca`, `vurgu_sayi` + `vurgu_etiket`, `alinti` + `alinti_sahibi`,
`neden_onemli`, `sana_etkisi`, `sirada_ne_var`, `ulke_kodu` + `ulke_adi` üretir.
`manset` ve `spot` anahtarları bilerek korundu (veritabanı, Telegram, LinkedIn, site ve
seslendirme bunları okuyor). Eski B5 kayıtları (`detay_maddeleri`, `uzman_notu`) onay
bekleyen kuyrukta ve geçmişte duruyor; tek okuma noktası `src/haber_alanlari.py` iki şemayı
da okur, tüketici şemayı bilmez.

Üretim sonrası `dogrula.haber_alanlarini_sadelestir` (Instabot standardı: sessizce eler,
bütün içeriği durdurmaz): kaynakta doğrulanamayan alıntı, kaynakta olmayan ya da
başlıkta/özette/kancada zaten geçen vurgu rakamı, boş övgü, içi boş kanca, başlık sonu
noktası atılır. Kaynak ince ise (<400 karakter) detay ilk iki paragrafla sınırlanır ve
çıkarım ağırlıklı alanlar (neden önemli, sana etkisi) atılır: model boşluğu genel
cümlelerle dolduruyordu (#171). Kapı (`dogrula.denetle`) yedek olarak durur ve haberde
kaynakta olmayan sayı ve yerel bağı ⛔ sayar.

Sayfaya sığmayan detay kırpılmaz, üretim durur (`TasmaHatasi`): Instabot sınırı aşan
blokları sessizce düşürüyordu. Bütçe: detay en fazla 230 kelime (`AZAMI_DETAY_KELIME`).

### Anlam kayması hakemi (2026-10-07)

Düzenli ifade sayı, süre, çoğunluk ve madde numarasını yakalar; "açılabilir"→"açıldı",
"dilerse"→"zorunlu", iki ayrı kuralın tek cümlede birleşmesi (S3-024: otuz günlük ilan
süresi ile on yıllık hak düşürücü süre) gibi anlam değişikliklerini yakalayamaz.
`src/capraz_denetim.py` ikinci bir modele (`gemini-3.5-flash`, üretici zincirin başından
farklı) içeriği kaynakla (haber metni ya da maddenin güncel metni) karşılaştırtır. Kapıda
`dogrula.icerigi_denetle` içinde, ⛔ yoksa çalışır; yayın anındaki kapıda (`anlam_denetimi=False`)
çalışmaz çünkü orada uyarılar kullanılmıyor.

- **Yalnız ⚠️.** Hakem de modeldir; doğru içeriği kapatması yakaladığı hatadan pahalı. Onaylayan
  uyarıyı Telegram önizlemesinin başında görür; finans otomatik yayınında herhangi bir uyarı
  yayını durdurup onaya düşürür.
- **Kanıt şartı.** Her bulgu içerikten ve (desteksiz hariç) kaynaktan birebir alıntı taşımak
  zorunda; alıntı metinde bulunamazsa bulgu atılır. Düşük ciddiyetli (sözcük düzeyinde pedantik)
  bulgu ve aynı cümle için ikinci bulgu atılır; en çok 3 uyarı.
- **Gürültü süzgeçleri** gerçek model denemesinden: sistemin eklediği "…için kaydedin"
  kapanış satırı içerik sayılmaz; `sana_etkisi`/`neden_onemli` gibi yazarın yorumu olan
  alanlarda "kaynakta yok" denmez, yalnız çelişki aranır.
- **Fail-open.** Kota, ağ, zaman aşımı ya da bozuk yanıtta denetim sessizce atlanır. Zincirde lite
  model yok: ölçümde ana modelin yakaladığı iki gerçek kaymayı kaçırdı; zayıf hakem "temiz" diyerek
  yanlış güven verir.
- Test modunda ağ yok; testler sahte `cagri` ile mantığı sınar.

## 5.5.2 Sözlük: hazır kart arşivi ve otomatik yayın (2026-10-08)

Sözlüğü otomatik yayına almadan önce yapılan inceleme (gerçek model, kanun alıntısıyla doğrulanmış
12 konu, her biri iki ölçüde çizildi):

| Katman | Ölçüm | Sonuç |
|---|---|---|
| Çizim | 12 içerik × besleme ve story | 12/12 sorunsuz: taşma, çakışma, kırpılma yok |
| İçerik | elle okuma | en az 4'ünde ince yanlışlık: S2-001 "teslim" yerine "sözleşme", S3-005 "Bakanlık izni olmadan ifraz yapılamaz", S3-007 "plansız alanda ifraz yapılamaz", S2-006 belirsiz iade süresi |
| Düzenli ifade kapısı | aynı 12 | gerçek yanlışı HİÇ yakalamadı (yalnız sayı ve özel isme bakar); 5/12 yanlış "yerel bağ", 1/12 yanlış ⛔ |
| Anlam hakemi | aynı 12 | gerçekten çalıştığında 9/12'de bulgu (bazıları gerçek, bazıları kullanılmayan bloklardan); kota bitince **sessizce hiç çalışmıyor** ve "temiz" görünüyor |

**Sonuç: modelin yazdığı sözlük otomatik yayına uygun değil.** İnsan onayı varken bu kusurlar kabul
edilebilir; onay kalkınca değildir. Bu yüzden iki ayrı yol var:

1. **Modelle üretilen sözlük** (eskisi gibi, HER ZAMAN onaya düşer). Ama sadeleştirildi: model B1'in bütün
   şemasını dolduruyordu, kullanılmayan `slayt_2/3/4` blokları hiçbir kanala gitmiyor ama kapıyı ve
   hakemi yanıltıyordu; artık silinir. Başlık "TERİM nedir?" olur (modelin serbest cümlesi değil), `spot`
   tanımın ilk cümlesidir. Yalnızca kanun alıntısıyla doğrulanmış konulardan üretilir. Kutu başlığı
   kitleye göre ("YATIRIMCI İÇİN ÖNEMİ" kiracı kartında yanlıştı).
2. **Hazır kart arşivi** (`data/sozluk_kartlari.yaml`, `src/sozluk_arsivi.py`): her kart bir KEZ yazılır,
   kanun metniyle ve anlam hakemiyle (üç ayrı geçiş) doğrulanır; yayın anında **modele hiç başvurulmaz**.
   İçerik değişmez, yalnız kanunun hâlâ aynı olduğu yeniden sınanır.

**Kart yazma kuralı:** tanım ve maddeler yalnızca atıf yapılan maddede yazanı aktarır. Kartta geçen her sayı,
süre ve oran o maddede bulunmalıdır; madde numarası anılıyorsa atıf listesinde olmalıdır. Hakem üç geçişte
bile yeni nüanslar buldu (kesinleşmiş karar, "aşırı ifa güçlüğü" istisnası, yüzdenin hesap tabanı): tek
geçiş yetmez. Yeni kart: YAML'a ekle → `python -m unittest tests.test_sozluk_arsivi` (biçim, kanun metni,
kapı, çizim) → hakemle kontrol.

**Ortam farkı (öğrenilen ders, 2026-10-09):** yayın GitHub'ın Linux makinesinde çiziliyor (Pillow orada HarfBuzz/raqm ile
kerning uygular), geliştirme macOS'ta (BASIC yerleşim). Metin birkaç piksel farklı ölçülür: aynı kart bir yerde 3 öbüründe 4
satır çıktı, bir terim 116 yerine 118 punto oldu ve macOS'ta kusursuz görünen tanım Linux'ta tek kelimelik son satırla bitti
(CI kırmızıydı). Bu yüzden (1) satırlar `_en_esit_kir` ile ölçüme bakarak dağıtılır, (2) testler kesin piksel/punto eşitliği
değil ÖZELLİK sınar (sığar, taşmaz, dul satır yok; genişlik kaydırılarak farklı ölçüm ortamları taklit edilir),
(3) yayınlanacak görünümü görmek için Actions → "Sözlük Önizleme" → Run workflow: 34 kartı Linux'ta çizip kontak sayfaları
olarak yükler (`scripts/sozluk_onizleme.py`; veritabanına, Telegram'a ve kanallara dokunmaz).

**Stok ve tekrar (kullanıcı şartı: EN AZ 2 YIL tekrarsız):** günde bir kartla 2 yıl için 730 kart gerekir (`sozluk_arsivi.HEDEF_KART`);
bekleme süresi bu yüzden 730 gün (`BEKLEME_GUN`, önceki 180 gün 34 kartla 6 ayda tekrara düşürüyordu). 2026-10-09'da 34 kart var:
34 gün yeter, sonra yayınlanabilir kart kalmaz ve sözlük her gün modelle üretilip onaya düşer (eksik: 696 kart). Hiç yayınlanmamış
kart 14'e inince her yayında Telegram'a "stok azalıyor" hatırlatması gider; `hazirla.py --durum` eksik kart sayısını yazar.
Yeni kartlar bu bölümdeki kuralla yazılır (kanun alıntısı birebir, her sayı atıf listesinde, üç hakem geçişi) ve ancak ondan sonra
`data/sozluk_kartlari.yaml`'a girer.

**Metin boyutu:** kısa içerikli kartlarda yazı büyür (`yeni_formatlar.SOZLUK_BUYUME_BASAMAKLARI`: tanım 46-60, madde 31-40 punto);
yoğun kart eski tavanda (44/30) kalır. Kutudaki "—" işaretinin girintisi ve başlık puntosu büyüklükle orantılı artar.

**Otomatik yayın** (`telegram_bot.sozluk_karti_hazirla_ve_sun`): her gün öğlen 12:30 TR (09:30 UTC, `hazirla.yml` cron
`30 9 * * *`) `hazirla.py --slot sozluk --oto-yayin` çalışır. `--oto-yayin` "bu çalıştırma onaysız yayına yetkili" demektir;
bayraksız çalıştırmalar (10:00 günlük döngü, elle `--slot sozluk`) açık anahtar yoksa hiçbir zaman otomatik değildir.
Modelin yazdığı sözlük bayrakla bile ASLA otomatik yayınlanmaz (kart kalmadıysa onaya düşer).

**Günde bir sözlük:** sözlük 10:00'daki günlük döngüde YOK (döngü: b1, nedir_dogrusu, net_cevap, b1); yalnız 12:30'da
yayınlanır. Döngüde kalsaydı beşinci günde aynı gün iki sözlük çıkardı (biri onayda bekler, biri otomatik yayınlanır).

**Dizgi (kart görseli):** terim büyük ve ayrım çizgisi sabit (kullanıcı kuralı, `yeni_formatlar.uret_sozluk`). Satırlar
`_dengeli_sar` ile eşitlenir: açgözlü kırma son satıra tek kelime bırakıyordu (34 tanımın 10'unda, "…depozito / denir.");
satır sayısı artmadan en dar genişlik aranır, boyut seçimi ve yükseklik değişmez. Tanım ve kutu maddelerine uygulanır
(`tests/test_sozluk_dengeli_satir.py`: 34 kartta tanım ve 90 maddenin hiçbirinin son satırı tek kelime değil).
Kart başına ortalama 44 görünür kelime (28–63): terim ~2, tanım ~15, maddeler ~27; Instagram açıklaması ortalama 68 kelime.

**Acil fren** (kod değiştirmeden, push ve dağıtım beklemeden): GitHub → Settings → Secrets and variables → Actions →
Variables → `SOZLUK_OTO_YAYIN` = `0` (ya da DB ayarı `sozluk_oto_yayin` = `0`). Kart o gün onaya düşer ve Telegram'a nedeni
yazılır; değişken tanımsız ya da boşken zamanlanmış çalıştırma yayınlar. Telegram'dan bot duraklatılırsa da durur.
Yayınlanmış bir kartı geri almak için ayrıca yayın kanallarından silmek gerekir; fren yalnız sonrakini durdurur.
Otomatik yayın YALNIZCA şu koşulların HEPSİ varsa olur, biri eksikse kart onaya düşer ve Telegram'a nedeni yazılır:

- kart hazır arşivden (model yazmadı) ve kanun metni alındı, alıntı güncel metinde birebir var, kartta geçen
  sayılar maddede mevcut (kanun değişmişse kart durur ve Telegram'a bildirilir; sıradaki kart denenir)
- bot duraklatılmamış; bugün başka bir sözlük kartı otomatik yayınlanmamış (günde en çok bir)
- denetim kapısı UYARISIZ (⛔ içerik hiç sunulmaz; herhangi bir ⚠️ otomatiği durdurur)
- yayın betiği çökerse (sonuç satırı üretmezse) kart onaya düşer; kanallar görsel karta uygun olarak
  (IG, Threads, Story, TikTok, Facebook — YouTube Shorts video gerektirdiğinden hariç tutulur)
- Önce kart görseli ve başlığı Telegram'a düşer (`📖 EDM EMLAK SÖZLÜĞÜ // OTOMATİK YAYIN`), dağıtım tamamlandığında
  canlı yayınlama raporu ve bağlantı butonları Telegram'a raporlanır.

Haftalık mevzuat denetimi kartları da denetler (`scripts/mevzuat_denetim.py`): kanun değişince kart yayından
önce kırmızıya düşer. Kart sayısı ve anahtar durumu: `python scripts/hazirla.py --durum`.

**Gemini kotası (aynı gün bulundu).** Anahtar ÜCRETSİZ katmanda; model başına günlük istek sınırı var ve
2026-10-07'de tek günlük yoğun deneme üç modelin kotasını doldurdu (yenilenme ~5 saat). GitHub'daki yedek
sırlar (`GEMINI_API_KEY_YEDEK`, `YEDEK2`) kodda hiç okunmuyordu; artık okunuyor ve `hazirla.yml`
adımlarına verildi. Her anahtar ayrı proje (ayrı kota).

**Onaysız yayında kapı (2026-10-12).** İnsan onayında hakemin sessizce atlanması kabul edilebilir (uyarıyı insan görür); onaysız yayında
değil. Model yazdığı içerik (finans bülteni) yalnız `dogrula.otomatik_yayina_uygun_mu` temiz derse çıkar: hiç ⛔/⚠️ olmamalı **ve**
anlam hakemi (`capraz_denetim.denetle_ayrintili`) gerçekten çalışıp temiz sonuç vermiş olmalı. Hakem kota ya da kaynak metin yokluğu
yüzünden çalışamadıysa "temiz" varsayılmaz: içerik reddedilmez, onaya düşer ve nedeni Telegram'a yazılır. Hazır sözlük arşivi bu kapıya
girmez (modele hiç başvurulmaz; kendi güvenceleri yukarıda).

## 5.5.3 Piyasa verisi: S4 "Rakam & Bölge" rakamları (2026-10-09)

> ⏸ **KAPALI (2026-10-12, kullanıcı kararı).** postedm'de piyasa verisi gönderisi istenmiyor; rakamlı fiyat analizi web sitesi için
> istenmişti. `veri_blogu` taşıyan üç konu (S4-001, S4-004, S4-013) `engel` altında, aylık toplama zamanlaması (`piyasa-verisi.yml` `schedule`)
> yorum satırı. Kod, testler ve 12 Ekim'de toplanan 111 satır yerinde duruyor. Yeniden açmak: konulardaki `engel` satırlarını sil,
> workflow'daki `schedule` işaretlerini kaldır. Aşağıdaki anlatım kapatılmadan önceki tasarımdır.

S4 konularının üçü rakam istiyordu ama doğrulanmış kaynak yoktu (kira çarpanı, mahalle fiyatları, arsa-daire
karşılaştırması); kaynaksız rakam yayınlanmadığı için engelliydi. Kaynak seçimi:

| Kaynak | Durum |
|---|---|
| Sahibinden, Hepsiemlak | sunucudan 403 (CLAUDE.md "kapanmış konular") |
| Endeksa'nın kendi sitesi | rakamlar JavaScript ile yükleniyor; düz istekle gelmiyor |
| **Emlakjet bölge sayfaları** | ortalama m² fiyatı, kira, mahalle kırılımı sayfada hazır; robots.txt `*` için serbest. Hesapları Endeksa yapıyor (Emlakjet "Verilerimiz ve Metodolojimiz") |

**Ne toplanıyor** (`src/piyasa_verisi.py`, `scripts/piyasa_topla.py`, aylık `piyasa-verisi.yml`): Silivri için satılık daire, arsa
ve tarla; karşılaştırma için Çatalca, Büyükçekmece ve Çorlu satılık dairesi. Bölge başına ortalama m² fiyatı, bir yıllık
değişim, ortalama fiyat, kira, ilan sayısı ve mahalle satırları. Bölge başına tek istek, 2,5 sn arayla, kendini tanıtan
User-Agent; 403/429'da zorlanmaz. Tablo: `piyasa_verisi` (günlük ölçüm; geçmiş birikir, ileride zaman serisi olur).

**Ne OLDUĞU (içerikte hep böyle anılır):** Endeksa'nın web ilanları ile danışman ve iş ortağı satış bildirimlerinden
hesapladığı TAHMİNİ bölge ortalamaları. Gerçekleşen tapu bedeli ya da resmî değerleme değil; Emlakjet'in kendi uyarısı da
"resmî değerleme raporu niteliği taşımaz, yatırım tavsiyesi değildir". Kaynak (Emlakjet/Endeksa) ve tarih içerikte yazılır.

**Güvenceler**
- Sayfa biçimi değişirse yanlış rakam yazmaktansa hiç rakam yazılmaz: JSON-LD ile kart çapraz denetlenir, her alan makul
  aralığa karşı sınanır, sayfadaki getiri/geri dönüş kendi fiyat ve kirasından yeniden hesaplanır (`olcum_sorunlari`).
- Düşük örneklem yayınlanmaz: ilçe için 15, mahalle için 10 ilan alt sınırı. Gerçek sayfada tek ilanlı mahallede m² fiyatı
  168.988 ₺ (ilçe ortalaması 62.962 ₺) ya da arsada %190 artış görüldü. Mahalle kırılımı yalnız satılık dairede; arsa ve
  tarlada yalnız ilçe düzeyi (parsel büyüklüğü ve imar dağılımı çok geniş).
- Veri 40 günden eskiyse ya da bloktaki ölçümler aynı günden değilse ona bağlı konu üretilmez (`hazirla.py --durum` yaşını yazar).
- İçerik veri bloğuna karşı denetlenir (`dogrula.veri_blogu_denetimi`): birimli her rakam (%, ₺, m², yıl, ilan…) blokta
  geçmeli ⛔; Emlakjet/Endeksa anılmalı ⛔; "ortalama/tahmini" denmeli ⚠️; "tapu bedeli", "kesin fiyat" gibi iddialar ⚠️.
  Kanun maddesi anmak uydurmadır ⛔. Yuvarlama da yasak: blokta 14,7 yıl varsa "15 yıl" yazılamaz. Anlam hakemi aynı bloğu kaynak alır.
- Konu bankasında `veri_blogu: <anahtar>` taşıyan konular yalnız b1 biçiminde ve veri varken seçilir; `konudan_uret` bloğu
  üretimden hemen önce çözer (veri yoksa model hiç çağrılmaz).

**Konular:** S4-001 (mahalle mahalle satılık daire), S4-004 (kira çarpanı; engeli kalktı), S4-013 (arsa/tarla/daire bir yıllık
değişim; eski "getiri hesabı" ve "enflasyona yenilme" iddiası veri olmadan yazılamadığı için konu daraltıldı). S4-002, S4-009 ve
S4-014 zaman serisi ya da sahil hattı verisi istediği için engelli kalır. S4-007 ("hangi tip ne kadar sürede satılıyor") de
engellendi: veri modele hiç verilmiyordu, rakamı model uyduruyordu.

**Canlı kontrol:** `python scripts/piyasa_topla.py --kuru` gerçek sayfaları okur ve yazmadan özetler; `--goster` kayıtlı
ölçümleri ve içerik bloklarını yazar. Sayfa biçimi değişirse fikstürler (`tests/fixtures/emlakjet_*.html`, gerçek sayfadan
birebir kesilmiş) yenilenir. Erişim kalıcı kapanırsa (403) S4 veri konuları 40 gün sonra kendiliğinden durur; Telegram'a haber gider.

## 5.6 Stres ve sabotaj testi

> **2026-09-25:** Asıl denetim artık `scripts/gorsel_denetim.py` (CI adımı, 164 vaka).
> Pikselle değil çizim kaydıyla bakar: taşma, çakışma, **örtülme** (#243), kırpılma,
> fontta olmayan glif, yüzen birleştirici işaret. Sığmayan metin kırpılmaz, üretim
> `TasmaHatasi` ile durur. Aşağıdaki `stres_testi.py` yalnız B biçimleri için kaldı.
> Seslendirme metninin sabotaj testleri: `tests/test_okunus.py`. Ayrıntı: `MEMORY.md` §9.

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

## 5.7.1 Öneri biçimi (2026-09-26)

Öneri artık Instabot'un öneri taslağıyla aynı: günde iki tur (09:17, 18:17 TR), tek
mesajda en fazla beş numaralı başlık; numaralarla çoklu seçim (Worker'da), "▶️ Hazırla
(n)" seçilenleri sırayla içeriğe çevirir, 🔍 ya da `/incele_ID` ayrıntıyı getirir.
Kural tabanlı eşik (`haber_oneri.ONERI_ESIGI`) ve "içeriğe çevirme insan kararıdır"
ilkesi değişmedi.

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

## 8. Haftalık takvim (ESKİ — üretimde uygulanmıyor)

> **2026-10-12 notu:** Bu tablo ilk tasarımdı. Bugün günün içeriği `konu_bankasi.BILGILENDIRICI_FORMATLAR` döngüsüyle
> (b1 → nedir_dogrusu → net_cevap → b1) 10:00'da, sözlük 12:30'da ayrı ve otomatik yayınlanır; haberler 09:17/18:17'de öneri olarak gelir
> (§5.7.1). `konu_bankasi.TAKVIM` yalnız `hazirla.py --gun` ile sütun önerisi için duruyor.

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
