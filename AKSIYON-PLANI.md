# postedm — Sağlamlaştırma Aksiyon Planı

instabot'ta iki yılda öğrenilenlerin postedm'e uyarlanması.
Kaynak: `~/Dogukan/instabot/CLAUDE.md` (2029 satır saha dersi) + 11 workflow + 14 test.

**Uyarlama ilkesi:** instabot son dakika haberciliği yapıyor, biz emlak otoritesi
kuruyoruz. Altyapı dersleri ortak, içerik kararları değil. Her madde "bize ne
uyarlanacak" diye süzüldü.

---

## Mevcut fark tablosu

| Alan | instabot | postedm | Sonuç |
|---|---|---|---|
| Depo görünürlüğü | **private** | **PUBLIC** | strateji ve iç yapı açıkta |
| Workflow sayısı | 11 | 2 | — |
| CI testi (her push) | `testler.yml`, 2 katman | **yok** | lxml hatası 3 gün görülmedi |
| Bütünlük testi | `test_0_butunluk.py` | **yok** | çağrı/imza hataları canlıda çıkıyor |
| Sözleşme testi | 46 denetim, CI'da | 323 satır var, **CI'da değil** | çalıştırılmıyorsa yok sayılır |
| Worker güvenliği | `secret_token` doğrulaması | **yok** | webhook'u herkes tetikleyebilir |
| Jeton yenileme | `jeton-yenile.yml` haftalık | **yok** | Threads 60 günde sessizce ölecek |
| Kaynak erişim testi | `test-kaynak-erisim.yml` | **yok** | RSS kaynağı ölse fark edilmez |
| Hata bildirimi | her job → Telegram | kısmi | sessiz başarısızlık |
| Günlük rapor | `gunluk-rapor.yml` | **yok** | "dün ne oldu" bilinmiyor |
| Sessiz başarısızlık tarayıcı | `sessiz_basarisizlik_tara.py` | **yok** | — |
| Kota takibi | ölçülmüş (%65) | **yok** | sınır bilinmiyor |

---

# P0 — Kanayan yaralar

## 0.1 Depo görünürlüğü — PRIVATE ✅ (11 Eyl 2026, karar değişti)

Önce public kalmasına karar verilmişti; aynı gün Actions kotası hesaplanınca
private'a çevrildi. Ölçülen aylık yük ~190 dakika, private ücretsiz kota
2000 dk/ay → **%10 kullanım**, rahat sığıyor.

| İş | Aylık | Süre |
|---|---|---|
| Günlük içerik (hafta içi) | 22 × ~4 dk | 88 dk |
| Onay → yayın | ~22 × 3 dk | 66 dk |
| Cumartesi konu madenciliği | 4 × 3 dk | 12 dk |
| Jeton yenileme | 4 × 1 dk | 4 dk |
| CI testleri | ~20 push × 1 dk | 20 dk |

**Private olmanın sonuçları:**

1. **`MEMORY.md` artık depoda durabilir** — hesap ID'leri ve iç notlar
   dışarı açık değil.
2. **Worker güvenliği yine de gerekli.** Kod artık gizli ama Worker adresi
   herkese açık bir uç nokta; güvenlik "kimse kodu görmüyor" varsayımına
   dayanamaz. §0.4 zaten yapıldı.
3. ⚠️ **Otomasyonun Actions okuma erişimi kayboldu.** Depo private olunca
   `GITHUB_TOKEN` (ince taneli PAT) `/actions/runs` ve `/actions/workflows`
   uçlarına 403 veriyor; public'ken "metadata" yetkisi yetiyordu.

   Sonuç: CI sonuçları ve iş akışı logları artık otomatik okunamıyor.
   Bugün üç `main` kırığı bu loglar sayesinde bulunmuştu.

   **Çözüm:** GitHub → Settings → Developer settings → Personal access
   tokens → ilgili token → Repository permissions → **Actions: Read**
   (yenileme işini sürdürmek için **Read and write**).

**Kota izleme:** aylık kullanım Settings → Billing → Actions'tan görülebilir.
%50'yi geçerse ilk kısılacak yer CI'nın `pull_request` tetikleyicisi.

## 0.2 Workflow yazma yetkisi ✅ VERİLDİ (11 Eyl 2026)

Son 7 zamanlanmış koşunun 7'si başarısız. Logda `GITHUB_TOKEN Permissions:
Contents: read`. Veritabanı hiç kaydedilemiyor → her koşu sıfırdan başlıyor →
konu rotasyonu ve mükerrer engeli çalışmıyor.

**Yapılacak:** Settings → Actions → General → Workflow permissions →
"Read and write permissions". *(Benim token'ım bu ayarı değiştiremiyor.)*

**Tahmini:** 1 dakika (senin elinle)

## 0.3 CI testleri — her push'ta ✅ YAPILDI (11 Eyl 2026)

instabot'un dersi birebir bizim başımıza geldi: `lxml` eksikti, yerelde çalıştı,
üretimde 3 gün boyunca her RSS kaynağı sessizce düştü.

**Yapılacak:**
- `testler.yml` — `src/`, `scripts/`, `tests/`, `worker/`, `config.yaml`,
  `requirements.txt` değişince tetiklenir
- İçinde: bütünlük testi + sözleşme testi + **bağımlılık testi**
- Ağa çıkmaz, DB'ye dokunmaz, saniyeler sürer

**Bize özel ek — bağımlılık denetimi:** import edilen her üçüncü parti paket
`requirements.txt`'te mi? lxml olayı tam olarak buydu.

**Tahmini:** 1 saat

## 0.4 Worker güvenliği ✅ YAPILDI (11 Eyl 2026)

instabot Worker'ı Telegram'ın `secret_token` başlığını doğruluyor. Bizimki
doğrulamıyor — URL'yi bilen herkes sahte onay gönderip **yayın tetikleyebilir**.

**Yapılacak:** `WEBHOOK_SECRET` secret'ı + `X-Telegram-Bot-Api-Secret-Token`
doğrulaması + webhook'u `secret_token` parametresiyle yeniden kur.

**Tahmini:** 45 dakika

---

# 11 Eylül 2026 oturumunda yapılanlar ve çıkan sürprizler

## Beklenmeyen keşif: onay akışı hiç var olmamış

`§0.4` "güvenlik ekle" sanılıyordu. Ölçünce çıkan:

- Cloudflare'de `edm-telegram-dispatcher` diye bir worker **yoktu**
- Telegram webhook'u **boştu** (`getWebhookInfo` → url: "")
- Yani gruptaki onay butonlarına basınca **hiçbir şey olmuyordu**

Benzer isimli `haber-bot-onay` instabot'a ait (50 KB, "daily" içeriyor) —
üstüne yazılmadı.

Dolayısıyla onay → yayın zinciri postedm için bugün ilk kez var oldu.

## Testin ilk çalıştırmada bulduğu ikinci vaka

Bağımlılık denetimi yazılırken `numpy` de `requirements.txt`'te bulunamadı —
lxml ile tam olarak aynı sınıf hata. `video.py` onu import ediyor; Reels/Shorts
üretimi runner'da patlardı. Yerelde kurulu olduğu için görünmüyordu.

**Bu, test yazmanın karşılığını ilk dakikada verdiği bir örnek.**

## CI ilk koşusunda main'in kırık olduğunu buldu

`testler.yml` ilk kez çalıştığında kırmızı döndü:

```
src/fetch_news.py:188 db.haber_kaydet() → 'makale_metni' diye bir parametre yok
```

Sebep bu oturumdaki kendi kararım. `fetch_news.py`'yi commit'lerken
"oturum öncesi işi kendi mesajıma gömme" ilkesiyle `db.py`'ye dokunmadım.
İlke doğruydu ama **main'i tutarsız bıraktı**: commit'li `fetch_news`,
commit'li `db.py`'de olmayan bir parametre çağırıyordu. Her haber kaydı
`TypeError` atardı.

Yerelde görünmüyordu çünkü yerel `db.py` o değişikliği taşıyor — lxml ve
numpy ile tam olarak aynı sınıf: **"bende çalışıyor" ile "orada çalışıyor"
farkı.**

Ders: bağımlılığı olan bir dosyayı commit'lerken bağımlılıklarının da
commit'li olduğunu doğrula. `test_butunluk.py` artık bunu otomatik yapıyor.

## Önlenen tuzak: çift tetikleyici

Worker'ın `scheduled()` işleyicisi `sabah_hazirla` gönderiyor ve `hazirla.yml`
bunu dinliyor; `hazirla.yml`'nin kendi cron'u da var. İkisi birden açık olsaydı
aynı gün **iki tur** çalışırdı: iki önizleme, iki konu tüketimi, iki paylaşım.
Cloudflare cron'u bilerek kapalı dağıtıldı, kural sözleşme testine bağlandı.

---

# P1 — Sessizce ölecek şeyler

## 1.1 Jeton yenileme ✅ YAPILDI (11 Eyl 2026)

`MEMORY.md`: Threads = "Meta Long-Lived Token - 60 Günlük". 60 gün dolduğunda
bot bir sabah sessizce durur — instabot'ta birebir yaşanmış.

**Düzeltme (11 Eyl 2026):** `src/refresh_token.py` zaten yazılmış ve içinde
işin zor kısmı duruyor:
- `threads_token_durumu()` / `threads_token_yenile()`
- `meta_token_durumu()` (Instagram + Facebook sayfa jetonu)
- `github_secret_guncelle()` — yenilenen jetonu GitHub Secret'a yazıyor

`scripts/token_kontrol.py` de elle çalıştırılabilir sağlık raporu veriyor.
**Eksik olan tek şey: bunu çağıran bir workflow.**

instabot'un iki dersi korunacak:
- **Ölmüş jeton yenilenemiyor** → 10 günden az kalınca yenile, dolmasını bekleme
- Gündüz çalıştır (Pazartesi 12:07 TR) → uyarı ayaktayken görülsün

**Ayrıca kontrol edilecek:** YouTube `refresh_token` — OAuth ekranı "Testing"
modundaysa Google 7 günde sessizce iptal ediyor (`MEMORY.md §6.1`).

**Küçük hijyen:** `refresh_token.py:105` hata durumunda `res.text`'i
logluyor; Meta'nın hata cevabı jetonu yankılayabilir. Maskelenmeli.

**Tahmini:** ~~2 saat~~ **40 dakika** (altyapı hazır)

## 1.2 Kaynak erişim testi ✅ YAPILDI (11 Eyl 2026)

Emlakkulisi bizim tek gerçek kaynağımız — 50 haberin 16'sı ondan. Beslemesi
ölse veya yapısı değişse fark etmeyiz; sistem sessizce konu bankasına düşer
ve "haber yok" sanırız.

**Yapılacak:** `kaynak-erisim.yml` (günlük) — her kaynağa bak, kaç `<item>`
döndü, kaçı süzgeci geçti. Bir kaynak arka arkaya 2 gün sıfır dönerse Telegram'a
uyarı.

**Bize özel:** Hürriyet'in "emlak" beslemesi 100 haberde 0 alakalı döndürüyordu
ve bunu ancak elle ölçünce gördük. Bu test onu otomatik yakalar.

**Tahmini:** 1 saat

## 1.3 Hata bildirimi ✅ YAPILDI (11 Eyl 2026)

instabot: "Herhangi bir job patlarsa Telegram'a hata mesajı."
Bizde sadece `hazirla.py`'nin kendi `try/except`'i var. Workflow adımı patlarsa
(lxml olayı gibi) kimse bilmiyor — 3 gün boyunca bilmedik.

**Yapılacak:** her workflow'a `if: failure()` adımı → Telegram'a job adı, adım,
log bağlantısı.

**Tahmini:** 30 dakika

---

# P2 — Kalite ağları

## 2.1 Bütünlük testi ✅ YAPILDI (11 Eyl 2026) (`test_0_butunluk.py` eşdeğeri)

Scriptleri çalıştırmadan ayrıştırıp her `modul.fonksiyon()` çağrısının var
olduğunu ve imzaya uyduğunu denetler.

instabot'ta üç kez aynı hata: `fetch_news.hepsini_cek` (yok),
`metinleri_uret(con, ...)` (yanlış imza). Üçü de sözdizimsel geçerliydi,
ilk gerçek çalıştırmada patladı.

**Bizde risk yüksek:** bu oturumda `telegram_bot.haberden_icerik_hazirla` ve
`konu_bankasi.aday_kaydet` gibi yeni fonksiyonlar ekledim; `hazirla.py`
bunları çağırıyor. Biri yeniden adlandırılırsa cron'da patlar.

**Tahmini:** 1,5 saat

## 2.2 Sözleşme testini genişlet ✅ YAPILDI (11 Eyl 2026) + CI'a bağla

`tests/test_sozlesme.py` zaten 323 satır ve iyi denetimler içeriyor ama
**hiçbir yerde çalıştırılmıyor.**

**Eklenecek denetimler (bu oturumda öğrendiklerimizden):**

| Denetim | Hangi olaydan doğdu |
|---|---|
| import edilen her paket requirements'ta | lxml — 3 gün sessiz RSS ölümü |
| `MODELLER` zincirinde en az iki farklı katman | dört model aynı katmandandı, 246 sn boş döndü |
| metin bütçeleri çizici kapasitesinin altında | prompt 45 kelime istiyordu, kutu 30 alıyordu |
| `_slayt_plani` sayfa sayacıyla tutarlı | 3 slaytta "01 / 04" yazıyordu |
| kanca kalıpları literal kopyalanmıyor | "ASLINDA TAM TERSİ" aynen basılıyordu |
| veri kaynağı yoksa B2/B4'te rakam yok | "ARSA %300 DAHA hızlı kazandırır" |
| workflow cron'ları takvimle uyumlu | haftada 14 tetikleme vs 5 paylaşım |
| `--haber-tara` cron'da kullanılmıyor | cron hiçbir şey paylaşmıyordu |

**Tahmini:** 2 saat

## 2.3 Sessiz başarısızlık tarayıcı ✅ YAPILDI (11 Eyl 2026)

instabot'un en sık hata sınıfı: "kod 0 döndü ama iş yapılmadı ve kimseye
söylenmedi." Testler bunu göremiyor — kod çalışıyor, yanlış şeyi yapıyor.

**Bize özel örnek:** `konudan_uret` `None` dönerse `konu_bankasindan_hazirla`
Telegram'a "❌ üretilemedi" yazıyor (iyi). Ama `_konu_adaylarini_madenle`
sessizce 0 döndürebiliyor.

**Yapılacak:** `scripts/sessiz_basarisizlik_tara.py` — iş yapmadan `return`
eden ve bildirim göndermeyen dalları listeler. Yanlış pozitif verir, çıktısı
"incelenecek adaylar".

**Tahmini:** 1,5 saat

## 2.4 Günlük rapor ✅ YAPILDI (11 Eyl 2026)

instabot `gunluk-rapor.yml` ile her sabah dün ne olduğunu yazıyor.

**Bize uyarlama:** her sabah Telegram'a — dün kaç haber tarandı, kaçı ön elemeyi
geçti, kaçı triyajı geçti, ne paylaşıldı, konu bankasında kaç hafta kaldı,
kaç konu adayı onay bekliyor, jetonların kalan ömrü.

Bu aynı zamanda **ölçüm altyapısının başlangıcı** — §9'daki kaydetme/paylaşım
oranları buraya eklenecek.

**Tahmini:** 1,5 saat

---

# P3 — Olgunlaşma

## 3.1 Doğrulama katmanı ✅ YAPILDI (11 Eyl 2026) (`dogrula.py` uyarlaması)

instabot onay mesajından ÖNCE çalışıp uyarıları mesajın başına koyuyor:
kaynakta doğrulanamayan sayı/isim, içi boş başlık kalıpları, suçlama dili.

**Bize uyarlama — emlak sürümü:**
- **Uydurma mevzuat denetimi:** metinde geçen her "md. NN" / "NNNN sayılı"
  brief'teki doğrulanmış mevzuatla eşleşiyor mu? Eşleşmiyorsa kırmızı uyarı.
  *Bu bizim en büyük sorumluluk riskimiz.*
- **Dayanaksız rakam denetimi:** yüzde/tutar var ama `veri_kaynagi` yok →
  uyarı
- **İçi boş manşet kalıpları:** "…hakkında bilmeniz gerekenler",
  "…ne anlama geliyor" gibi konuyu duyurup sonucu saklayan kalıplar
- **Zorlama yerel bağ:** metinde Silivri/Trakya geçiyor ama brief'te
  `yerel: null` → model uydurmuş olabilir (triyajda birebir yaşandı)

⚠️ **Türkçe `İ` tuzağı:** `"İlişkin".lower()` noktalı i üretiyor, düz
karşılaştırma tutmuyor. instabot'ta bu tarama sessizce hiçbir şey yakalamadı.

**Tahmini:** 3 saat

## 3.2 Supergroup tuzağı

Telegram bir grubu supergroup'a yükseltince chat ID **değişir** ve bot
sessizce mesaj atamaz olur. Cevapta `parameters.migrate_to_chat_id` geliyor.

Bizim grup şu an `supergroup` (kontrol ettim) — yani bu geçiş olmuş.
Yine de yakalama kodu konmalı; başka bir gruba taşınırsa aynı sorun.

**Tahmini:** 30 dakika

## 3.3 Kota takibi ✅ ÖLÇÜLDÜ (11 Eyl 2026)

instabot ölçtü: ~1290/2000 dakika (%65). Bizde hiç ölçülmedi.

**GÜNCELLEME:** depo public kalıyor (§0.1) → GitHub Actions dakikası
**sınırsız**. Bu madde büyük ölçüde düştü.

Geriye kalan tek darboğaz **Gemini kotası**: `gemini-3.5-flash` zaten 429
veriyor ve 11 Eylül'de dört model birden 503 verdi.

Ayrıca **Gemini kotası** bizde asıl darboğaz: `gemini-3.5-flash` zaten 429
veriyor. Günlük çağrı sayısını raporda takip etmeliyiz.

**Tahmini:** 1 saat

---

# 11 Eylül akşamı — ilk paylaşım yayında 🎉

```
https://www.instagram.com/p/DdJzdlCoDka/
CAROUSEL_ALBUM · 19:08 TR · Threads'e de basıldı
```

Zincirin tamamı ilk kez uçtan uca döndü:
**RSS → puanlama → triyaj → brief → slayt → Telegram → Worker → Actions →
Instagram + Threads.**

## Günlük zaman çizelgesi (TR)

| Saat | İş |
|---|---|
| 08:40 | Günlük rapor — dün ne oldu |
| 09:30 | Kaynak sağlığı — beslemeler ayakta mı |
| 10:00 | İçerik turu (Pzt-Cum) |
| her saat :07 | Site ilan kuyruğu güvenlik ağı |
| Pzt 12:07 | Jeton yenileme |
| Cmt 08:00 | Konu madenciliği |

**Kota:** ~780 zamanlanmış koşu/ay ≈ %39 (2000 dk private sınırı).

## Kalan işler

| Madde | Durum |
|---|---|
| §3.2 Supergroup tuzağı | yapılmadı — grup zaten supergroup, düşük risk |
| Ölçüm (§9 kaydetme/paylaşım oranları) | ilk 10 paylaşım verisi bekleniyor |
| Site deposu push | postedm tarafı canlı, site commit'i push edilmedi |

---

# Sıralama önerisi

**Bu oturum (yaklaşık 3 saat):**
1. §0.1 depo görünürlüğü — *senin kararın*
2. §0.2 workflow yetkisi — *senin elinle*
3. §0.3 CI testleri + bağımlılık denetimi
4. §0.4 Worker güvenliği

**Sonraki oturum (~4 saat):**
5. §1.1 jeton yenileme
6. §1.2 kaynak erişim testi
7. §1.3 hata bildirimi
8. §2.2 sözleşme testini genişlet

**Ondan sonra:**
9. §2.1 bütünlük testi
10. §2.4 günlük rapor
11. §3.1 doğrulama katmanı

**Neden bu sıra:** P0'lar olmadan sistem ya güvensiz ya da sessizce bozuk.
Jeton yenileme (P1) takvimsel bir bomba — 60 gün sonra patlıyor, ama şu an
acil değil. Kalite ağları (P2) ise hata *bulmak* için değil, bulunanı bir daha
görmemek için.

---

# Uyarlamayacaklarımız — ve nedeni

| instabot'ta var | Bizde olmayacak | Neden |
|---|---|---|
| `son-dakika.yml` saat başı | — | Emlakta son dakika yok; haber triyajımız zaten günde bir |
| `piyasa-bulteni.yml` | — | Borsa/döviz bülteni bizim sütunlarımızda yok |
| `hatirlat.yml` 7 kez/gün | **sadeleştirilmiş** | Onay beklemede tek hatırlatma yeter; 7 bildirim grubu yorar |
| `haftalik-ozet.yml` | **ertelendi** | Ölçüm verisi birikmeden özetlenecek şey yok |
| Carousel 10 slayt | — | Bizde 4-7, karma mimari zaten karar verilmiş |
