# 🧠 POSTEDM — PROJE HAFIZA VE REFERANS BELGESİ (MEMORY)

Bu belge, **EDM Yapı & Gayrimenkul** için geliştirilen otonom sosyal medya paylaşım sisteminin kalıcı hafıza ve mimari kayıt dosyasıdır. Tüm hesaplar, yetkiler, tasarım kararları ve stratejik yönelimler burada saklanır.

---

## 1. TEMEL FELSEFE VE STRATEJİ

* **Marka:** EDM Yapı & Gayrimenkul (`edmyapigayrimenkul.com`)
* **Slogan:** "Yatırım Ortağınız"
* **Bölge & Odak:** Silivri, Trakya ve Türkiye Geneli Gayrimenkul & Yatırım Dünyası
* **Stratejik Karar (Önemli):**
  * Türkiye'deki **EİDS (Elektronik İlan Doğrulama Sistemi)** ve Ticaret Bakanlığı mevzuatları sebebiyle doğrudan portföy ilan paylaşımları şimdilik donduruldu.
  * Sayfa **"Gayrimenkul Sektörü Otorite & Bilgi Platformu"** olarak konumlandırıldı.
  * Amaç: Hukuk & tapu tuzakları, ev sahibi & kiracı rehberleri, kredi/faiz analizleri ve arsa/imar hap bilgileriyle kaydetme (save) ve paylaşma (share) odaklı viral organik büyüme sağlamak.

---

## 2. BAĞLI SOSYAL MEDYA PLATFORMLARI & DURUMLARI

Tüm entegrasyonlar **%100 EDM Yapı & Gayrimenkul adına sıfırdan ve müstakil** olarak kurulmuştur.

| Platform | Hesap / Sayfa | ID / Bilgi | Durum & Token Türü |
| :--- | :--- | :--- | :--- |
| **Instagram** | `@edmyapigayrimenkul` | Business ID: `17841445511135602` | ✅ Aktif (Kalıcı Süresiz Sayfa Tokeni) |
| **Facebook** | `Edm Yapi & Gayrimenkul` | Sayfa ID: `145361567360773` | ✅ Aktif (Kalıcı Süresiz Sayfa Tokeni) |
| **Threads** | `@edmyapigayrimenkul` | User ID: `28138648412457225` | ✅ Aktif (Meta Long-Lived Token - 60 Günlük) |
| **YouTube Shorts** | `@edmyapigayrimenkul` | Kanal: Metin Özdoğan | ✅ Aktif (Google Cloud EDM Projesi `refresh_token`) |
| **TikTok** | `@edmyapigayrimenkul` | Creator Content API | ✅ Aktif (`TIKTOK_ACCESS_TOKEN`) |
| **LinkedIn** | `EDM Yapı&Gayrimenkul` | Org ID: `67226326` | ✅ Aktif (Community Management API - 60 Günlük OAuth) |
| **Telegram Botu** | `@PostEdmBot` | Grup: `EDM Social Media` (`-1003984339543`) | ✅ Aktif (Onay & Önizleme Merkezi) |
| **AI Motoru** | Gemini 3.5 Flash | Kurumsal Ton Promptu | ✅ Aktif (`GEMINI_API_KEY`) |
| **Görsel Barındırma** | ImgBB & Catbox | 4:5 Slayt Yükleyici | ✅ Aktif (`IMGBB_API_KEY`) |

---

## 3. TASARIM DİLİ & MARKA PAFTASI (KURUMSAL KİMLİK)

> Ayrıntılı editoryal sistem: **`ICERIK-SISTEMI.md`**. Burası yalnızca özet.

* **Oran:** 4:5 Dikey Format (`1080 x 1350 px`)
* **Slayt sayısı:** İçerik yoğunluğuna göre **4 ile 7 arası** (karma mimari).
  Karar `make_image._slayt_plani()` içinde, metnin gerçek uzunluğundan verilir.
* **Dizgi kuralları (2026-09 revizyonu):**
  * **Çerçeveli kutu yok.** Gruplama sol vurgu çizgisi ve tipografik hiyerarşiyle.
  * **Gövde 34-40px** (eski sürüm 28-29px idi ve akışta okunmuyordu).
  * **Bir karede tek fikir.** Yalnızca metin kısaysa iki fikir birleştirilir.
  * **"Kaydet" çağrısı sadece kapanış slaytında.** Her slayta konunca yer yiyordu.
  * **Ortak taban çizgisi** (`TEK_FIKIR_TABAN = 1120`): kapak, tek fikir ve adım
    slaytları aynı hizada biter; kaydırırken metin bloğu yerinde durur.
* **Zemin varyantları (anlam taşır, dekorasyon değil):**
  * `murekkep` `#121316` — nötr: adımlar ve açıklamalar. Beyaz metin
  * `kagit` `#F4F4F3` — "doğrusu / çözüm": koyu akıştan sonra nefes. Mürekkep metin
  * `kirmizi` `#C4030F` — yalnızca kritik uyarı. **Carousel başına en fazla bir kez**
    (marka oranı %70 nötr / %25 mürekkep / %5 kırmızı; tam sayfa kırmızı oranı bozar)
  * Kağıt zeminde kırmızı gövde metninde kullanılmaz — kontrast 4,4:1, yalnızca
    18px üstü metinde veya dolgu olarak.
* **Kapak:** fotoğraf + iki aşamalı karartma perdesi. Perde, yasal dayanak şeridine
  geldiğinde okunabilir koyuluğa ulaşmış olmalı (`PANEL_ALFA = 170`) — tek üslü
  rampada mevzuat satırı aydınlık fotoğrafta okunmuyordu.
* **4 Ana Otorite Kategorisi:** Tapu & Hukuk · Kiracı & Ev Sahibi · Arsa, İmar &
  Toprak · Rakam & Bölge (`ICERIK-SISTEMI.md §3`)
* **Renk Paleti:**
  * Mürekkep Siyahı: `#121316` & `#1a1c21`
  * Sıcak Pafta Kağıdı: `#f4f4f3`
  * EDM Kırmızısı: `#f0000d` · Derin: `#c4030f` · Koyu zeminde canlı: `#ff3b30`
  * Kurşun Gri: `#8a8b8f` & `#dadee6`
* **Tipografi (Orijinal Türkçe TTF Destekli):**
  * Başlıklar & Manşetler: `Fraunces` (prestijli mimari serif)
  * Gövde & Açıklamalar: `Plus Jakarta Sans` (net, modern kurumsal)
  * Teknik Metrikler & Rozetler: `IBM Plex Mono` (daktilo / kadastro karakteri)
* **Metin bütçeleri ölçülür, tahmin edilmez.** `scripts/metin_butcesi.py`
  çizicinin gerçek kapasitesini ölçer ve `generate_text.BUTCE` ile karşılaştırır.
  Font veya kutu genişliği değişince çalıştırılmalı.
* **Temiz Arka Planlar:** `assets/backgrounds/` (yalnızca kapakta kullanılır)

## 4. TEKNİK MİMARİ & ÇALIŞMA AKIŞI

1. **İçerik Hazırlığı & Cron (günde BİR içerik, 10:00 TR — bkz. §8.5):**
   * **Günlük turun ASIL tetikleyicisi Cloudflare cron'udur (2026-10-12, bkz. §10 madde 13):** Worker `scheduled()` 07:00 UTC'de
     `slot_hazirla {slot: bilgilendirici, zamanli: true}`, 09:30 UTC'de `{slot: sozluk}` yollar (`worker/wrangler.toml` `[triggers]`).
     `.github/workflows/hazirla.yml`'deki aynı saatli GitHub cron'ları GECİKMELİ YEDEKTİR (6-10 saat gecikiyorlar); `hazirla.py`
     zamanlanmış bir slotu aynı Türkiye gününde ikinci kez üretmez. Eskiden ikisi birden açıkken günde iki tur çalışırdı (bkz. §9.5).
   * **Güncel tam zamanlayıcı listesi §12.2'de** (rapor, haber önerisi ×2, içerik, iki günde bir sözlük, sessiz kuyruk bakımı ×2: hepsi Cloudflare cron'u; bkz. §10 madde 18, 20, 23).
   * RSS taranır, Gemini kanca başlıklı 3 slaytlık analiz üretir ve görseller `src/make_image.py` ile çizilir.
   * Telegram grubuna `@PostEdmBot` üzerinden önizleme ve onay butonları (`✅ Yayına Al (IG + FB + Threads)`) iletilir.
2. **Onay ve Yayınlama:**
   * Grupta butona tıklandığında Cloudflare Worker sinyali yakalar ve GitHub Actions `.github/workflows/yayinla.yml`'ı tetikler.
   * `scripts/yayinla.py` (ince giriş) → `src/yayin/` paketi devreye girer (okumaya `src/yayin/akis.py`tan başla, bkz. §10 madde 14):
     * Instagram Carousel basılır.
     * Facebook albüm gönderisi basılır.
     * Threads gönderisi basılır.
     * YouTube Shorts için dikey video renderlanıp yüklenir.
   * Başarı raporu anında Telegram grubuna yazılır.

---

## 5. GÜVENLİK VE GİT YÖNETİMİ

* `.env` dosyası kesinlikle `.gitignore` içerisindedir ve commit edilmez.
* Origin adresi temiz: `https://github.com/edmyapigayrimenkul/postedm.git` — URL'ye token GÖMÜLMEZ.
  (2026-09-23'e kadar süresiz, admin yetkili bir PAT gömülüydü; iptal ediliyor.)
* **Push yolu: düz `git push`.** Bu Mac'te github.com kimliğini `gh auth git-credential` verir;
  gh'deki `ozdogangringo-sketch` hesabı postedm'de yazma yetkili ortak çalışandır.
  `.env`'deki token'la push YAPILMAZ; `~/.git-credentials` (düz metin) kullanılmaz.
* Token'lar amaca göre ayrı ve süreli (edmyapigayrimenkul hesabı, yalnız postedm):
  `edm-dispatch` (Contents: yazma) → iki Worker'ın tetikleme secret'ı;
  `edm-secret-yazici` (Secrets: yazma) → Actions `SECRET_YAZMA_PAT`, jeton yenilemenin secret'lara yazması için.

---

## 6. INSTABOT (DAILY BRIEF) SAHA DERSLERİ & SİSTEM KURALLARI

1. **Google Cloud OAuth 7 Gün Jeton İptali Tuzağı:**
   * Google Cloud Console -> APIs & Services -> OAuth consent screen sayfasında durum **"Testing"** ise, Google refresh token'ı **TAM 7 GÜN SONRA** sessizce iptal eder.
   * **Kalıcı Çözüm:** Ekran **"Publish App"** butonuna basılarak **"In production"** durumuna alınmalıdır. Gizlilik politikası ve şartlar linki verilmelidir (logo yüklenmemelidir, logo yüklenirse haftalarca süren marka incelemesi tetiklenir).
2. **Instagram Akış (Feed Carousel) 4:5 Kesin Formatı:**
   * Instagram Graph API, 4:5 sınırını aşan (özellikle 9:16 story/video) görselleri en-boy hatasıyla reddeder.
   * `src/instagram.py:gorselleri_4_5_yap` fonksiyonu yayın öncesi tüm slaytları kontrol eder; 9:16 olanları kayıpsız merkezi 1080x1350 olarak kırpıp CDN'e yükler. 4:5 görsellere dokunmaz.
3. **Dikey Video Sessiz Parça (Audio Track) Zorunluluğu:**
   * YouTube Shorts, Instagram Reels ve TikTok, ses kanalı olmayan MP4 videolarını "işleme bekliyor" diyerek transcode kuyruğuna atar veya geciktirir.
   * `src/video.py`, videoya FFmpeg üzerinden sessiz 44.1 kHz stereo AAC ses kanalı (`anullsrc`) gömer.
4. **⚠️ VERİTABANININ SAHİBİ GITHUB'DIR, YEREL DEĞİL.**
   * Her koşu sonunda `data/edm.db` repoya commit ediliyor. Yerelde
     `hazirla.py` çalıştırırsan yerel veritabanı ilerler, GitHub'daki geride
     kalır ve **iki taraf ayrışır.**
   * 11 Eylül 2026'da yaşandı: yerelde 4 haber `onay_bekliyor`, depoda 1.
     Telegram butonu depodaki veritabanına baktığı için yereldeki kayıtların
     butonları "haber bulunamadı" verir.
   * **Kural:** yerelde gerçek tur çalıştırma. Denemek gerekiyorsa çıktıyı
     Telegram'a göndermeyen yollarla dene (`--durum`, doğrudan
     `konudan_uret` çağrısı, `scripts/stres_testi.py`).
   * Gerçek tur yerelde çalıştırıldıysa bitince veritabanı hemen commit+push
     edilmeli. Ayrışma olduysa **depodaki sürüm doğrudur** — yerel üstüne
     yazılır (yedek alarak).

5. **Veritabanı Çakışması — satır düzeyinde birleştirme (2026-09-23):**
   * `data/edm.db` ikili SQLite dosyasıdır. Eskiden çakışmada dosya bütünüyle `--theirs` ile
     seçiliyordu: bir tarafın TÜM değişiklikleri siliniyordu (143 DB commit'inin 6'sında
     kayıt geri gitti; 19fc02f'de 28 haber silindi).
   * Artık `src/db_birlestir.py` üç yönlü satır birleştirmesi yapar; `db_senkron` çakışmada
     bunu kullanır, birleşemezse push ETMEZ. 'yayinlandi' ve dolu yayın kimliği hiçbir
     birleştirmede kaybolmaz.
   * `data/edm.db`'ye yazan her GitHub Actions workflow'unda `permissions: contents: write` bulunmalıdır.
6. **Yazı Tipi & Eksik Glif Güvenliği:**
   * Inter ve Fraunces fontlarında bulunmayan ok ve emojiler (`➔`, `👉`, `📌`, `📈`, `🎯`) ekranda içi boş kare kutu (`.notdef`) olarak çıkar.
   * `src/make_image.py:_temizle_tipografi` bu glifleri daima güvenli unicode sembollerine (`→`, `◆`, `▲`, `▼`, `★`) dönüştürür.
7. **Token Sağlık Kontrolü:** (canlı durum için Telegram'da `/saglik` — jetonları gerçekten dener)
   * Düzenli olarak `python scripts/token_kontrol.py` çalıştırılarak tüm API'ler ve Threads 60 günlük token durumu tek komutla denetlenir.


---

## 7. 2026-09-23 DENETİMİ — BÜTÜN AJANLAR İÇİN KURALLAR

Bu kuralların her biri üretimde yaşanmış bir hatadan doğdu. Kod yazan her oturum
(Claude, Codex, Gemini) uymalı; çoğu test ya da kancayla da zorlanıyor.

1. **Kod commit'ine `data/edm.db` girmez.** Veritabanını yalnızca `db_senkron` commit'ler.
   Yeni klonda bir kez: `python3 scripts/git_kancalari_kur.py` (pre-commit kancası +
   birleştirme sürücüsü). `git add -A` / `commit -a` kullanma — başka oturumun
   yarım kalmış değişikliklerini de süpürür (23 Eylül'de oldu).
2. **Git kimliğini kalıcı değiştirme.** Bot kimliği yalnızca `db_senkron`'un kendi
   süreç ortamında verilir; yerel kod commit'leri kullanıcının kimliğiyle atılır.
3. **Testler üretim verisine dokunmaz.** Test modunda (`POSTEDM_TEST_MODU=1`) `.env`
   yüklenmez, DB ve `.env` geçici kopyadır (`config.db_yolu`). Yeni test dosyası
   ilk satırlarda test modunu açmalı. CI, testlerden sonra `data/edm.db` değişmişse kırmızı.
4. **Gizli anahtar DB'ye yazılmaz, DB'den okunmaz** — DB git'e gidiyor. (TikTok
   jetonları 57 commit boyunca depo geçmişine girdi.)
5. **İçerik durumu `src/durum_kurali.py`'den geçer.** Kapalı içerik yayınlanmaz, yayındaki
   içerik atla/çöpe at/yenile ile ezilmez, bir kanala iki kez gönderilmez.
6. **Worker:** komut verebilecek sohbetler `IZINLI_SOHBETLER` secret'ında (boşsa her şey
   reddedilir). Komutlar tam kelimeyle eşleşir (`startsWith("sil")` "Silivri 220"
   mesajını silme komutu sayıyordu). Geri alınamaz işlemler onay mesajı ister.
7. **Actions'ta dış girdi yalnızca `env:` ile geçer**, `run:` bloğuna `${{ }}` ile
   gömülmez (kabuk enjeksiyonu). `tests/test_is_akisi_guvenligi.py` zorlar.
8. **Ölçülemeyen değer uydurulmaz.** Rapor ve durum mesajları "ölçülmüyor/alınamadı"
   yazar; 0 ya da sabit "✓ Aktif" basmaz. (Metrikler 12 gün boyunca sahte 0'dı.)
9. **Site kuyruğu sözleşmesi:** boşken 204, iş varken JSON nesnesi, yetkisizse 401.
   Bunun dışındaki her yanıt ARIZADIR ve hata yükseltmelidir — "boş kuyruk" sayılmaz.
10. **Otomatik yayın yalnızca `dogrula` denetiminden temiz çıkan içerikte.** En ufak
    uyarıda içerik onaya düşer.

## 8. 2026-09-24 KARARLARI — YALAN BİLGİYE SIFIR TOLERANS

1. **Kritik denetim bulgusu olan içerik onaya bile sunulmaz** (`telegram_bot.yayin_kapisi`,
   yayın anında `scripts/yayinla.py` de çalıştırır). Kapı kapalı başarısız olur: denetim
   çalışmazsa içerik çıkmaz. Kapıyı gevşetmek yerine brief'i ya da konu bankasını düzelt.
2. **Boş alan koddaki genel cümleyle doldurulmaz.** Eksik alan `yeni_formatlar.EksikIcerik`
   fırlatır. (#157'de ekspertiz konusuna sabit "Yargıtay yerleşik içtihatları…" basıldı;
   sabit adım listesi 7571 sayılı Kanunla yanlış hâle gelmişti.)
3. **Promptta örnek süre/oran yazılmaz** — model kopyalıyor (#142 "İKİ YIL BOYUNCA").
   Süre ve oran yalnızca brief'teki güncel madde metninden gelir.
4. **Konu bankasında atıf, mevzuat.gov.tr'deki güncel metin okunarak eklenir**; veri kaynağı
   olmadan rakam isteyen konu `engel` alır. Eski kuralı anlatan içerik eski rakamı yazmaz
   ("kısaldı" der) — denetim kanunda olmayan rakamı durdurur.
5. **İçerik günde BİR** (hazirla.yml 10:00 TR). Haberler bağımsız: haber-oneri.yml tarihli
   öneri düşer, "İçeriğe çevir" insan kararıdır. Haber slotu içerik üretmez.
6. **Caption soruyla bitmez**: kaydet/gönder çağrısı + site/telefon + konuya özel etiket.
7. **Marka paleti**: amber/turkuaz/yeşil yok; kırmızı yalnızca vurgu, zemin çoğunlukla kağıt.

## 9. 2026-09-25/26 — TASARIM DENETİMİ, SESLENDİRME, ÖNERİ, PLANLI YAYIN

Claude oturumu. Kararların çoğu kullanıcının örnekleri dinleyip/görüp verdiği
kararlardır; yeniden sorulmaz. Her maddenin testi var, testin adı yanında.

### 9.1 Görsel denetim ve tasarım
1. **`scripts/gorsel_denetim.py` CI adımıdır (164 vaka: 8 biçim × 2 ölçü × stres/sabotaj).**
   Çizim çağrılarını dinler, pikselle değil. Denetimler: TUVAL DIŞI, KENAR, ÇAKIŞMA,
   KUTU KESİŞİMİ, ÖRTÜLDÜ (#243 sözlükte tanım kutunun altında kalmıştı), PUNTO,
   KIRPILDI, **GLİF YOK** (fontta olmayan karakter kutu basar), **YÜZEN İŞARET**.
   Yeni biçim/alan eklerken `FORMATLAR`/`fikstur` güncellenir.
2. **Sığmayan metin kırpılmaz.** Çizici en küçük okunur puntoda da sığmazsa
   `make_image.TasmaHatasi(EksikIcerik)` fırlatır; üretim durur. Bütçe:
   `generate_text.BUTCE` (terim 26, tanım 260, puf_madde 95 …; `AZAMI_PUF_MADDE = 3`).
3. **Gövde fontu IBM Plex Sans (statik örnekler).** `-Variable.ttf`, `Fraunces-Variable.ttf`
   ve `IBMPlexMono-Regular.ttf` Latin alt kümesidir: ğ ş İ ₺ YOK — kullanma.
4. **Çizim girişleri metnin süzülmüş KOPYASIYLA çalışır** (`make_image._gorsel_girdisi`,
   `gorsel_metni`): emoji, U+200B/U+202E, sahipsiz birleştirici işaret ve kart fontlarının
   ortak glif kümesinde olmayan her karakter ayıklanır; caption'daki emoji yerinde kalır.
5. **Kanca (`hook_motoru`) cümle kesmez**: ilk 8 kelimede kesilen cümle kaynağın
   söylemediği bir iddia olabiliyordu. Sığmayan kanca "…" ile kırpılmaz, basılmaz.
   Kategori etiketi kapağın üst rozetinde zaten yazdığı için kancada yok; "●" çizilir.
6. **Kapak fotoğrafı konuya göre** (`make_image.KONU_HAVUZLARI`, Pexels 15 aday, son 40
   Pexels kimliği hariç). Uydurma etiket/rakam yedekleri kaldırıldı (`SEKTÖREL BÜLTEN`,
   `18.000 TL`, `%80-%130` …).
7. **Fon müziği** (`assets/audio/1_emlak_haber_fonu.mp3`, Instabot'taki `haber_fon.mp3` ile
   aynı dosya): kaynağı ve lisansı kayıtlı değil. Kullanıcı 2026-09-26'da **müziğin kalmasına
   karar verdi** (risk anlatıldı ve kabul edildi) — yeniden sorma, değiştirme.

### 9.2 Test izolasyonu (CI "Testler data/edm.db'yi değiştirmedi" adımı)
1. Her `tests/test_*.py` VE `testler.yml`'deki her `python scripts/X.py`, `src`/`scripts`
   importundan ÖNCE `os.environ.setdefault("POSTEDM_TEST_MODU", "1")` yapmalı
   (`tests/test_test_izolasyonu.py` AST ile zorlar). Dört test dosyası ve
   `metin_butcesi.py` gerçek DB'ye yazıyordu; yeni bir DB sütunu eklenince test modu
   dışındaki HER açılış gerçek DB'ye göç yazar ve CI kırmızı olur.

### 9.3 Seslendirme (ElevenLabs) — kullanıcı kararları
1. > ✅ **KARAR (kullanıcı, 2026-10-12): seslendirme sesi ALEX'tir.** Güncel ayar `config.yaml › seslendirme`: Alex (`KediIz7pebzt5TaDHiiZ`, Instabot ana sesi),
   > yedek Adam, hız 1.15, stability 0.55, style 0.0, **-14 LUFS**. Aşağıdaki Sıla Özalp / 1.05 / -12 LUFS değerleri 2026-09-26'nın TARİHSEL kararıdır, geçersiz.
   > Sıla'ya dönülmek istenirse yalnız `config.yaml` değişir (`ELEVENLABS_VOICE_ID` ortam değişkeni okunmaz).

   **Ses ve ayarlar tek kaynak: `config.yaml › seslendirme`.** (ESKİ karar, geçersiz:) Sıla Özalp
   (`r3deco0KTo6o0Kb5inro`, haber sunucusu), yedek Adam; hız 1.05, stability 0.40,
   style 0.30; -12 LUFS. `ELEVENLABS_VOICE_ID` ortam değişkeni OKUNMAZ (yereldeki eski
   değer seçimi sessizce geri çeviriyordu). Anahtar: `ELEVENLABS_API_KEY` (GitHub
   secret'ı kullanıcı ekledi; yerelde `.env`).
2. **Yalnızca KAPAK okunur** (üç versiyon dinlendi: yalnız kapak / slayt başına cümle /
   bütün metin → yalnız kapak). Madde/bölüm başlıkları ASLA okunmaz. Nedir Doğrusu'nda
   yanlış inanış okunmaz (etiketsiz doğru bilgi gibi duyulur). `ses.kapak_seslendirme_metni`.
3. **Son slaytta kapanış çağrısı**, önce gerekçe: "…kaçırmak istemiyorsanız takipte
   kalın" (`config.yaml › seslendirme.kapanis_cagrisi`). "Beğenin" bilerek yok.
4. **Seslendirme İSTEĞE BAĞLI.** "✅ Yayınla" eskisi gibi seslendirmesiz (YT/FB fon
   müzikli, TikTok karusel, Reels elle paylaşım için müziksiz). "🎙️ Sesli Yayınla" →
   "🎵 Fon müzikli" / "🔇 Fon müziksiz" → aynı zaman menüsü. Worker hedefe
   `ses_muzikli`/`ses_muziksiz` ekler; `yayinla.py` seslendirmeyi yalnızca video
   kanallarına uygular ve TikTok'u video kipine alır. Onay anında seslendirme YOK.
5. **Seslendirilmiş video `_sesli` adlıdır ve bir daha karıştırılmaz**
   (`ses.sesli_video_hazirla`): Facebook yolu anlatımı silip yerine yalnız müzik koyardı.
6. **Başarı/hata rapor metninden anlaşılmaz** (2026-10-13'te kural değişti): eskiden `yayinla.py` rapor satırında "✓"/"✗" arıyordu, bu yüzden
   o işaretler yasaktı (seslendirme satırı başarılı yayını "başarısız" gösteriyordu). Artık her satır kendi durumunu taşır
   (`src/yayin/sonuc.py` › `Satir.durum`: YAYINDA / HATA / BILGI); metin yalnız gösterimdir.
7. **`src/okunus.py` sese giden metni Türkçe okunuşa çevirir** ("Hz." hezt değil Hazreti,
   "1/5000" beş binde bir, "18.000 TL/m²'den" metrekaresi on sekiz bin liradan, "14.00'e"
   on dörde). **Kısaltma ve tek harf olduğu gibi kalır** — ölçüldü: harf harf yazmak
   "beblokta", "da yüz", "kadeveliği" diye okunuyordu. Emin olunmayan çevrilmez
   (etiketsiz "142/85" kesir sayılmaz). Instabot'la BİREBİR AYNI dosya: birinde
   düzelteni ötekine taşı. `tests/test_okunus.py`: 100+ satır tablo, 3000 rastgele sayı,
   3000 rastgele karışık girdi, ikinci kez çevirmede kararlılık.
8. **Tek harf sese TIRNAKLA gider** (`okunus.tek_harfleri_belirginlestir`, okunuştan SONRA):
   kullanıcı "A Milli Takım derken A çok hızlı söyleniyor" dedi. Kelime zaman damgasıyla
   ölçüldü: düz "A" 0,02-0,04 sn ve 6'da 4 duyuldu, tırnaklı "A" 6'da 6. Harf-tire-sayı da:
   düz "F-16" → "F-36"/"fon a…", "D-100" → "Kazadei 100"; '"F"-16' ve '"D"-100' doğru.
   **`<break>` etiketi YASAK**: ses cümle başına uydurma kelime ekledi ("Ayrıca", "Hatta",
   "Tacan") — sıfır tolerans ihlali. Virgül de "Uluslararası" okuttu.

### 9.4 Haber önerisi — Instabot'un öneri taslağı
1. Günde iki tur (09:17, 18:17 TR, `haber-oneri.yml`); tek mesajda en fazla beş numaralı
   başlık (bağlantılı, 💬 tek cümle, kaynak · sütun · 🗓 tarih · `/incele_ID`).
2. `sec:ID` seçimi Worker'da (GitHub'a gitmez), `hazirla_secilenler` tek dispatch →
   `haber_uret` `"272,273"` → sırayla içeriğe çevrilir. `oneri_gec` düğmeleri kaldırır.
3. 🔍 `incele:ID` ve `/incele_ID` MEVCUT `bot_yonetim incele` yolundan gider;
   `telegram_bot.icerik_incele_karti` ham haberde haber ayrıntısı + "📝 İçeriğe çevir" döner
   (içerik kartı ham habere "Şimdi Yayınla" sunuyordu).

### 9.5 Planlı yayın ("30 dk / 1-4 saat sonra")
1. Eskiden gecikme GitHub'a hiç iletilmiyordu: mesaj "planlandı" deyip hemen yayınlıyordu.
2. Worker planı KV'ye yazar (`EDM_PLANLAR`, binding `PLANLAR`, Instabot'unkinden ayrı);
   `wrangler.toml` cron `*/10` → `scheduled()` vakti geleni `yayinla` (`planli=1`) yollar.
   GitHub yalnızca iş varken uyanır. 3 saatten geç plan yapılmaz, gruba yazılır.
   "⏹ Planı iptal et" menüyü geri getirir. Süreler 30/60/120/180/240, tam kalıpla doğrulanır.
3. `haberler.planlanan_yayin`: hatırlatıcı plan bekleyen içeriğe kart atmaz (eski mesajı ve
   iptal düğmesini silerdi). `hedef=planla/plan_iptal` yalnızca bu işareti yazar.
4. Hesap Workers Paid planında; yine de dağıtımdan sonra çıktıda `schedule: */10 * * * *`
   satırını doğrula (sınıra takılan dağıtım cron'u sessizce yazmıyordu — Instabot).

### 9.6 Worker ve dağıtım
1. `worker/index.js` menüleri `src/telegram/menuler*.py` menüleriyle BİREBİR aynı kalmalı (`tests/test_sozlesme.py` karşılaştırır).
   Worker değişince: `cd worker && npx --yes wrangler deploy`. Son sürümler:
   `830fb293` (öneri + sesli yayın), `a21121a4` (planlı yayın).
2. Worker testleri gerçek çağrıyla: `node --test tests/*.test.mjs` (52 test).

Commit'ler: `6243ae6` `fc6217f` (tasarım) · `a321e32` (test izolasyonu) · `0a8d51e`
`8346378` (glif) · `51071a4` (seslendirme) · `74e1b84` (öneri + sesli yayın) ·
`75427e4` (planlı yayın) · `7bcda6c` (okunuş ölçümü).

## 10. 2026-10-12 DENETİMİ — KURALLAR VE DÜZELTMELER

Tüm maddelerin testi var (`tests/test_onay_kuyrugu_ve_iade.py`, `test_hata_gunlugu.py`, `test_zamanlanmis_duraklatma.py`, `test_otomatik_yayin_kapisi.py`).

1. **[GÜNCEL 2026-10-13: süre 5 gün → 1 gün, hazır içerik havuza alınır, hatırlatma kapalı — madde 23]** **Onay zaman aşımı TÜM kuyruğa uygulanır** (`hatirlat.py`). Eskiden `LIMIT 5` yüzünden altıncı ve eski içerikler 5 güne hiç girmiyordu (14 içerik, en eskisi
   27 Eylül'den beri bekliyordu). Hatırlatma yine yalnız en yeni 5'e gider; aynı turda düşenler tek özet mesajdır.
2. **Duraklatma zamanlanmış koşuları da durdurur.** `hazirla.yml` zamanlanmış koşuyu `ZAMANLANMIS=true` ile işaretler; `--slot`/`--format` bayrağı artık
   duraklatmayı aşmaz (cron'lar bu bayraklarla çalışıyor). Elle tetiklenenler (Telegram, `workflow_dispatch`) aşar.
3. **Konu yalnız yayınlanırsa tüketilir.** Atla / çöpe at / zaman aşımı → `konu_bankasi.konuyu_havuza_iade_et`: kayıt silinmez, `sonuc='hata'` yapılır (3 gün
   sonra yeniden sıraya girer; birleştirme sürücüsü satır güncellemesini güvenle taşır). Yeni içerik yalnız `EDM Konu Bankası` ve Reels'te üretilir;
   sözlük kartı ya da haber önerisi reddi karusel doğurmaz. `konu_gecmisi.sonuc='cope_at'` kalıcı engel olarak ayrılmış kalır (kimse yazmıyor).
4. **Hata günlüğü DB'dedir** (`hata_kayitlari`, 30 gün). `data/hata_kayitlari.jsonl` ve `son_hata.txt` .gitignore'da ve Actions makinesiyle silinir; yalnız aynı iş
   içindeki sonraki adımlar içindir. **Hata metni kaydedilmeden önce `src/gizlilik.maskele` ile maskelenir** (requests istisnası URL'deki `access_token`'ı taşır;
   DB git'e gider). Yeni hata kayıt noktası eklenirse `hata_bildir.hata_kaydet` üzerinden geçmeli. `yayinla.yml`'de "Hata bildir" adımı "Veritabanını Kaydet"ten
   ÖNCE olmalı (kayıt makineyle gitmesin). "🔍 Ham Hata Göster" düğmesi artık `bot_yonetim/hata_ayrinti` ile Actions'a gider ve metni DB'den okur (`hata_bildir.son_hatayi_gonder`); eski Worker
   dosyayı repodan okumaya çalışıp hiç bulamıyordu. **Worker değişti: `cd worker && npx --yes wrangler deploy` ile dağıtılmalı** (dağıtılana dek düğme eskisi gibi "bulunamadı" der).
5. **Onaysız yayında anlam hakemi gerçekten çalışmış olmalı** (`dogrula.otomatik_yayina_uygun_mu`, ICERIK-SISTEMI §5.5.2). Şu an yalnız finans bülteni modelle üretilip
   onaysız yayına gidebilen yol.
6. **Ölçülemeyen değer rapora "0 hata ✓" diye girmez.** Günlük kota raporunda "HATA GUNLUGU": uygulamanın kaydı + GitHub'ın bildirdiği başarısız koşu sayısı
   (`rapor_uretici.basarisiz_is_akislari`; jeton/API yoksa "ölçülemedi").
7. **Site kuyruğu 401 (açık sorun):** `site-kuyrugu.yml` saatlik güvenlik ağı, 11 Ekim 2026 00:55 UTC'den beri `https://edmyapigayrimenkul.com/api/postedm/kuyruk`
   adresinden **401 Unauthorized** alıyor (kod 9 Ekim'den beri değişmedi). Workflow `EDM_SITE_API_ANAHTARI` geçirmiyor, OIDC'ye düşüyor: site tarafındaki anahtar/OIDC
   doğrulaması kontrol edilmeli. Sözleşme gereği (§7.9) 401 arızadır; her saat Telegram'a "BAŞARISIZ" düşer.
   **2026-10-12 kullanıcı kararı: saatlik yoklama (`schedule`) geçici olarak kapatıldı** (`site-kuyrugu.yml`; site düzelince yorum işaretlerini kaldırın).
   Anlık tetikleme (`repository_dispatch`) ve elle çalıştırma açık; site düzelene dek panelden paylaşım 401 ile düşer.
8. **Piyasa verisi (Emlakjet/Endeksa) KAPALI — kullanıcı kararı.** postedm'de bu tür gönderi istenmiyor (rakamlı fiyat analizi web sitesi içindi; özellik 9 Ekim'de
   başka bir oturumda, talep atfı olmadan eklenmişti). S4-001/004/013 `engel` altında, aylık cron yorum satırı; kod, testler ve toplanan 111 satır durur.
   Yeniden açma: ICERIK-SISTEMI §5.5.3 başındaki not.
9. **Silinen ölü modüller:** `fetch_photo`, `haftalik_bulten`, `makro_kart`, `otomatik_onay`, `sparkline` (hiçbir yerden çağrılmıyordu, testleri yoktu). Git geçmişinde duruyor.
10. **Sözlük kart üretim araçları yazıldı** (`kanun_oku.py`, `sozluk_kart_dogrula.py`, `sozluk_kart_birlestir.py`; SOZLUK-KART-URETIMI.md). Sahte kanun metniyle
    testli; **canlı kanunla denenmedi** (mevzuat.gov.tr geliştirme ortamında kapalıydı). 14 yeni kanunun tertipleri tahmin: ilk açık ağda `kanun_oku.py kanunlar --dene`.
    Araçlar `src.db` göçünden `data/edm.db`'yi korumak için test modunda başlar (`--hakem` hariç).
11. **Testler `data/` klasörüne dosya sızdırmaz:** hata günlüğü ve yayın raporu işareti `config.veri_yolu()` ile test modunda geçici dizine gider.
12. **Telegram teslimi (albüm + düğmeli onay kartı) — 2026-10-12.** Günlük içeriğin albümü 60 sn okuma zaman aşımına uğradı (Actions logu: "Yerel medya grubu
    istisnası … Read timed out"); eski yedek yol **yerel dosya yolunu Telegram'a "URL" diye gönderip** sessizce 400 aldı → albüm hiç gelmedi, hata günlüğüne de yazılmadı.
    Ayrıca başarısız çağrıdan sonra `son_medya_grubu_mesaj_idleri()` ÖNCEKİ içeriğin kimliklerini veriyordu (yanlış mesajlar bu içeriğe bağlanıp sonra silinirdi).
    Düzeltme (`telegram_bot.py`, testler `tests/test_telegram_medya_teslimi.py`): `medya_grubu_gonder` sırayla yerel albüm → URL albümü (`yedek_urller=` ImgBB) →
    indirip yükleme → TEK TEK `sendPhoto` dener; her istek (10 sn bağlanma, 40 sn okuma) 429'da `retry_after`, 5xx/ağ hatasında bekleyip yeniden denenir, başlık HTML hatasında
    düz metne düşer; hiçbiri tutmazsa `hata_kayitlari`'na `telegram.medya` yazılır. Onay kartı albüm gelmese de gider ve başına uyarı + ImgBB bağlantıları konur;
    kart gitmezse kısa kartla (aynı düğmelerle) tekrar denenir (`_onay_kartini_gonder`); manşet/kategori/dayanak HTML'e kaçırılır. **Zaman aşımı belirsizdir** (Telegram isteği
    işleyip cevabı geciktirmiş olabilir): nadiren aynı albüm iki kez düşebilir — albümün kaybolmasından iyidir.
    GitHub `schedule` koşularının 6–10 saat geciktiği görüldü (07:00 UTC içeriği 16:37'de, 09:30 sözlüğü 19:13'te çalıştı) → madde 13.
13. **Günlük tur Cloudflare cron'una taşındı — 2026-10-12.** Worker `scheduled()`: `0 7 * * *` → `slot_hazirla {slot: bilgilendirici, zamanli: true}`, `30 9 * * *` →
    `{slot: sozluk, zamanli: true}`; GitHub'a ulaşamazsa 3 kez dener, olmazsa gruba "Günlük içerik tetiklenemedi" yazar. `hazirla.yml` cron'ları SİLİNMEDİ, gecikmeli yedek:
    `ZAMANLANMIS` artık dispatch'te de `client_payload.zamanli` ile true (duraklatma ve günlük koruma uygulanır) ve `hazirla.py` bir slotu zamanlanmış koşuda
    **o Türkiye gününde bir kez** çalıştırır (`ayarlar › zamanli_slot_son_gun:<slot>`, yalnız başarılı turda yazılır; elle tetiklenenler korumaya takılmaz, işaret de bırakmaz).
    Neden yedek bırakıldı: Worker dağıtılmadan GitHub cron'u kaldırılırsa HİÇ içerik çıkmaz; ikisi korumasız açık kalırsa günde iki içerik çıkar. Koruma ikisini güvenle birlikte açık tutar;
    `tests/test_sozlesme.py › test_tek_tetikleyici_kurali` bunu zorunlu kılar. **Dağıtım gerekir:** GitHub → Actions → **Worker Dağıt** → Run workflow (dal: main; `.github/workflows/worker-dagit.yml`; GitHub sırları `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID`; iş Worker testlerini koşar, `wrangler deploy` eder, Cloudflare API'sinden üç cron'un yazıldığını doğrular ve Telegram'a sonucu yazar). Elle: `cd worker && npx --yes wrangler deploy`. Sonra Cloudflare panelinde
    Workers › Cron Triggers'ta ÜÇ satır (`*/10 * * * *`, `0 7 * * *`, `30 9 * * *`) görünmeli (sınıra takılan dağıtım cron'u sessizce yazmıyordu — Instabot). Cloudflare cron'u
    bir hafta sorunsuz çalışırsa GitHub cron'ları `hazirla.yml`'den kaldırılabilir (o zaman test kuralı ve `test_cron_takvimle_uyumlu` birlikte güncellenir). Worker'ın durum menüsündeki
    eski takvim (13:30 / 18:30) de düzeltildi.
14. **`scripts/yayinla.py` bölündü — 2026-10-13.** 1571 satırlık dosya (tek `main()` 1339 satır; 9 kanal işçisi `nonlocal` ile ortak değişken değiştiriyordu) →
    `src/yayin/` paketi (`akis` ana sıra · `hedef` kanal seçimi · `icerik` yükleme/görsel onarımı · `videolar` · `kanallar/` kanal başına işçi · `dagitim` paralel motor ·
    `kayit` DB · `rapor` Telegram · `koruma` durum koruması+kapı · `aksiyonlar/` reddet/yenile/foto/metin/…). `scripts/yayinla.py` yalnız komut satırı girişi (<80 satır;
    `tests/test_yayin_paketi.py` büyümesini engeller). **Güvence:** `tests/test_yayinla_altin.py` — 70 senaryo, eski kodun dış dünyaya yaptığı her şeyi (kanal API çağrıları,
    Telegram metin/düğmeleri, DB, stdout, hata) kaydetti; bölmeden sonra 69'u BİREBİR aynı, tek fark bilinçli düzeltme (aşağıda). Yeniden kayıt YALNIZ davranış bilerek
    değişince: `YAYIN_ALTIN_KAYDET=1 YAYIN_ALTIN_SENARYO=ad python -m unittest tests.test_yayinla_altin`.
    **Bölmede bulunanlar:**
    * **Hata düzeltildi:** "Başka Fotoğraf Bul → 3 aday" (`foto_adaylar`) canlıda hiç çalışmıyordu: `main()` içinde sonradan yapılan `from src import make_image` adı fonksiyon boyunca
      yerel yapıyor, aday dalı atanmadan erişince `UnboundLocalError`. Bölünce kendiliğinden düzeldi.
    * **Davranış iyileşti:** bir kanal işçisi yakalanmamış hata atarsa eskiden future sessizce yutuluyor, kanal raporda hiç görünmüyordu; şimdi "Hata (...) ✗" satırı olur.
      Rapor satırları eskiden tamamlanma sırasıyla (rastgele), şimdi kanal sırasıyla.
    * **Korundu ama sorulmalı:** (a) X (Twitter) işçisi var ama hiçbir hedef onu SEÇMEZ (`hedef.kanal_listesi`; eskiden de öyleydi). (b) `gorsel_sec:N` hedefi taslak işlemi sayılmıyor,
      bu yüzden yayın kapısından (denetim) geçiyor. (c) "zaten yayında" olarak atlanan kanal için de "Tekrar dene" düğmesi çıkabiliyor (tıklanınca "zaten yayında" der, zararsız).
15. **`telegram_bot.py` altın çıktı testi + "Yayından Kaldır" hatası — 2026-10-13.** Faz 2 (bölme) öncesi `tests/test_telegram_altin.py`: ~219 senaryo, Telegram'a giden HER istek
    (`sendMessage`/`sendPhoto`/`sendMediaGroup`/`editMessageText`/…: metin, düğmeler, zaman aşımı, deneme sayısı), yan etkiler (üretim/denetim/yükleme çağrıları, DB satırları) ve
    dönüş/hata kaydı `tests/altin/telegram.json`'da. Yeniden kayıt YALNIZ davranış bilerek değişince: `TELEGRAM_ALTIN_KAYDET=1 [TELEGRAM_ALTIN_SENARYO=ad1,ad2] python -m unittest tests.test_telegram_altin`.
    * **Hata düzeltildi:** `yayindan_kaldir("haber", …)` (✕ Yayından Kaldır düğmesi) 2026-10-07'den beri **çöküyordu**: `haberler` tablosunda olmayan `atlanma_zamani` sütununu yazıyordu
      (`OperationalError: no such column`). Facebook/Threads gönderisi silindikten SONRA çöktüğü için gönderi gidiyor, kayıt "yayında" kalıyor, Telegram'a rapor gelmiyordu.
      İlan yolu (`ilan_kaldirildi_isaretle`) etkilenmiyordu. Zaman damgası kaldırıldı; `aday.py` "atlanma_zamani" sütununu zaten yoksa tolere ediyor.
    * **Faz 2 tamamlandı (aynı gün):** `telegram_bot.py` 2919 → 168 satır (kod yok, canlı takma ad cephesi). `src/telegram/` paketi: `istemci` (tek HTTP kapısı `_istek`), `medya_istek`, `album`, `temizlik`, `ayarlar`,
      `menuler`, `menuler_panel`, `durum_metni`, `sonuc_mesaji`, `kaldir`, `kartlar`, `paneller`, `akislar/` (`kapi`, `onay`, `onay_slayt`, `onay_karti`, `otomatik`, `sozluk`, `uretim`, `reels`, `otorite`, `ilan`, `finans`, `zamanli`).
      Davranış 219 senaryoda birebir aynı (`tests/test_telegram_altin.py`); kurallar `tests/test_telegram_paketi.py`'de (≤250 satır, `telegram_bot`'a yukarı bağımlılık yok, kardeşler modül üzerinden, cephe tablosu paketle aynı).
      **Test yazarken:** Telegram'ı sessizleştirmek için GERÇEK EVİ yamala — `patch("src.telegram.istemci.mesaj_gonder")`, ağ kapısı için `src.telegram.istemci._istek` / `_bot_bilgileri`; `patch("src.telegram_bot.X")` yalnız
      cepheden çağıranları (scripts/, src/yayin/) sessizleştirir. Kaynak metni okuyan testler `tests/telegram_kaynak.py::telegram_kaynagi()` kullanır.
    * **Bölmede bulunan gizli hatalar (düzeltilmedi, karar sizin):** (a) `src/threads.py:241` `json` içe aktarılmamış; `metinleri_slaytlara_dagit` içindeki `try/except Exception` NameError'u yutuyor, yani `detay_metni` HİÇ ayrıştırılmıyor
      ve Threads zinciri satır alanlarından kuruluyor. Düzeltmek (import eklemek) içeriği değiştirir (yeni biçimlerde `manset` anahtarı olmayabilir) — gözlemlenmeden dokunulmadı. (b) `scripts/piyasa_otomatik.py` ve `src/piyasa_tablo.py`
      kapalı piyasa özelliğinde tanımsız ad / olmayan `src.caption` modülü içeriyor (özellik kapalı, çalıştırılmıyor). (c) `src/haber_oneri.py` `Path` içe aktarmamıştı: yerel dosya yollu aday görseli NameError ile günlük öneriyi çökertirdi — düzeltildi.
16. **Sözlük pilotu A07 Kadastro (3402) — 2026-10-13.** Mevzuat Önbelleği workflow'u çalıştı: 32 kanunun tamamı çekildi (14 yeni kanunun tertip tahmini tuttu). 8 kart yazıldı, bağımsız (opus) inceleme sonunda **4'ü arşive girdi (SZ-035…038)**:
    doğrulayıcı yeşili doğruluk değildir; kapsam/istisna zinciri olan maddeler (md. 14, 16–18, 20) kartlaştırılamadı (iki turda dört ret). Başlık yerleşim tabanı (≥114 pt) doğrulayıcıda denetlenmiyordu, iki kart tam testte düştü: `baslik_sigma_sorunu` eklendi.
    Ayrıntı, kart tablosu, yazar/inceleme kuralları 8–11: SOZLUK-KART-URETIMI.md "Pilot sonucu". Araç eksiği aynı gün giderildi: ek maddeler ("Ek Madde 6") artık ayrı tür (`ek md. 6` atfı, `ek 6` anahtarı); eskiden "md. 6" diye etiketleniyor, normal maddesi olmayan numaralar sessizce Ek Madde'ye çözülüyordu.
17. **Sözlük dalga 1 — 2026-10-13.** Arşiv 38 → 66 kart: 45 taslaktan 28'i girdi (SZ-039…066: TBK kira genel/konut-işyeri, KMK md. 1–19), 17 ret (%62 kabul; kabul edilenlerin çoğunu inceleyici yeniden yazdı). Yazarlar oturum kullanım sınırına takılıp yarıda kesildi;
    kural: bir dalgada en çok 4 ajan, limit sıfırlanınca yeni dalga. Süre denetimi (`mevzuat._SURE`) "md. 319 ayıp" → "319 ay" sayıp ayıp kartlarını engelliyordu: düzeltildi. Ayrıntı ve dersler: SOZLUK-KART-URETIMI.md "Dalga 1 sonucu".
    Açık: SZ-007 md. 353 istisnasını söylemiyor; md. 339/2 (altı ay ve kısa geçici kiralar) hiçbir kartta yok; A12 yazılmadı.

18. **Faz 5 — hatırlatma, haber önerisi ve günlük rapor Cloudflare cron'una taşındı — 2026-10-13.** Madde 13'ün aynısı üç iş daha için: Worker `scheduled()` artık yedi zamanlanmış işi tetikler
    (`worker/index.js › ZAMANLI_ISLER`: `40 5` rapor, `17 6` ve `17 15` haber önerisi, `0 7` içerik, `30 9` sözlük, `30 10` ve `30 18` hatırlatma; hepsi UTC, TR = +3) ve `wrangler.toml` crons **sekiz** satır
    (+ `*/10 * * * *` plan çaları). Her iş kendi `repository_dispatch` olayını `{slot, zamanli: true, kaynak: "cloudflare_cron", cron}` yüküyle yollar (`rapor`, `haber_oneri`, `hatirlat`, `slot_hazirla`);
    3 denemede olmazsa gruba "<iş adı> tetiklenemedi" yazar. Workflow'lardaki aynı saatli GitHub cron'ları **gecikmeli YEDEK olarak duruyor** (`haber-oneri.yml` cron'u slot ayırt edilsin diye ikiye bölündü: `17 6` ve `17 15`).
    **Çift çalışmayı önleyen:** `scripts/zamanli_koruma.py kontrol|isaretle` — üç workflow'da "Zamanlı koruma (günde bir kez)" adımı (`kontrol`, `atla=true` ise sonraki adımlar atlanır) ve iş başarılıysa
    "Zamanlı işi işaretle" (`isaretle`); işaret hazirla.py ile aynı: `ayarlar › zamanli_slot_son_gun:<slot>` (TR günü). Slotlar: `hatirlat_ogle`, `hatirlat_aksam`, `haber_oneri_sabah`, `haber_oneri_aksam`, `rapor`
    (`ZAMANLI_GUNLUK_SLOTLAR`'a eklendi). Başarısız tur işaretlenmez (yedek yeniden dener); **elle istek korumaya takılmaz ve onu tüketmez** (Telegram "Onayları Hatırlat", `/hatirlat`, `/haber`, `/rapor`, `/kota`,
    `workflow_dispatch`: `ZAMANLANMIS` yalnız schedule ya da `client_payload.zamanli == true`). `haber-oneri.yml`: Worker'ın zamanlı yükü `--haber-oneri` yoluna gider (eskiden schedule dışı her olay `--slot haber`e giderdi);
    Telegram'ın `haber_oneri` dispatch'i `zamanli` taşımadığı için eskisi gibi `--slot haber`. Bilinen ödünler: (a) bot duraklatılmışken zamanlı haber önerisi atlanır ama o slot "yapıldı" işaretlenir
    (gün içinde duraklatma kalkarsa o sabahın önerisi yedek tetikle de gelmez; akşam turu etkilenmez); (b) iş sessizce yutulan bir hatayla "başarılı" bitiyorsa (çıkış kodu 0) slot işaretlenir;
    (c) GitHub aynı `concurrency` grubunda (`edm-veritabani`) en çok BİR bekleyen koşu tutar, yeni bekleyen eskisini iptal eder: yedek koşular hızlı atladığı için risk düşük ama sıfır değil (yeni değil, tüm DB'ye yazan işlerde var).
    **DAĞITILDI (2026-10-13 21:26 UTC, Worker Dağıt koşusu #2, `main`@724de95, yeşil; sekiz cron Cloudflare API'sinden doğrulandı).** Eski not: main'e birleşince Actions → **Worker Dağıt** → Run workflow; Cron Triggers'ta SEKİZ satır görünmeli (iş bunu Cloudflare API'sinden doğrular, eksikse kırmızı biter).
    Dağıtılana dek her şey eskisi gibi GitHub cron'uyla çalışır (koruma bunu bozmaz: ilk koşu çalışır ve işaretlenir). **GitHub yedek cron'larını bir hafta sorunsuz Cloudflare çalışmasından sonra silin**
    (4 workflow'da `schedule` bloğu; `test_tek_tetikleyici_kurali`, `test_cron_takvimle_uyumlu`, `test_zamanli_isler.py` birlikte güncellenir). Testler: `tests/test_zamanli_isler.py` (Worker tablosu ↔ toml ↔ workflow ↔ dağıtım doğrulaması,
    koruma betiği), `tests/worker_gunluk_tur.test.mjs` (her cron'un olayı, yükü, hata bildirimi).

19. **Elle tetiklenen sözlük artık onay kartıyla düşer — 2026-10-13.** Kullanıcı isteği: günde bir sözlük kesin (12:30, zamanlanmış, onaysız yayın; değişmedi), günün diğer içeriği (10:00 döngüsü: b1 · nedir_dogrusu · net_cevap · b1)
    ve elle tetiklenen HER içerik "albüm + ayrı düğmeli kart" (✅ Yayınla, kanal seçimi, sesli yayın, ertele, atla, çöpe at) olarak gruba düşer; günde iki haber önerisi (09:17, 18:17) ayrı. Bulunan tutarsızlık: `hazirla.yml` elle
    `/sozluk` (`format_turu: sozluk`) ve `workflow_dispatch › slot_sozluk` için de `--oto-yayin` veriyordu, yani elle istenen sözlük **düğmesiz, doğrudan yayına** çıkıyordu. Şimdi `--oto-yayin` yalnız `ZAMANLANMIS=true` iken eklenir
    (Cloudflare 12:30 / GitHub yedek cron'u); `SOZLUK_OTO_YAYIN=0` acil freni aynen geçerli (o zaman günlük sözlük de düğmeli kart olur). **Finans bülteni dışarıda tutuldu** (elle de `--oto-yayin`; ayrı karar bekliyor).
    Test: `tests/test_hazirla_yml_elle_tetik.py` workflow'un kabuk betiğini sahte `python` ile gerçekten çalıştırır (eski workflow'a karşı 3 test kırmızı olur).
    **Ölçüm (data/edm.db, 2026-10-13):** onay kartları 29 Eylül'den beri `-1003984339543` sohbetine gidiyor (168 kayıt, 15 gün). 10:00 içeriği 2–9 Ekim arası GitHub cron'uyla ≈10:20'de, 10–12 Ekim arası GitHub gecikmesiyle 13:30–16:38'de,
    13 Ekim'de ilk kez Cloudflare ile 10:01'de geldi. Çok sayıda kart onaylanmadan 5 günlük zaman aşımına düştü (4–6 Ekim); 13 Ekim akşamı #594 ve #600 hâlâ onay bekliyor.

20. **Zamanlanmış sözlük iki günde bir — 2026-10-13 (kullanıcı kararı).** 12:30 sözlüğü onaysız otomatik yayınlanmaya DEVAM eder ama sıklığı günde bir → iki günde bir oldu. Kural: son TESLİM edilen zamanlanmış turdan
    (`ayarlar › sozluk_zamanli_son_gun`; kart yayınlandı ya da onaya düştü) beri `sozluk_arsivi.YAYIN_ARALIK_GUN` (=2) gün geçmediyse tur sessizce atlanır: kart tüketilmez, model çalışmaz, Telegram'a mesaj düşmez, atlanan gün "başarılı"
    sayılır (yedek GitHub cron'u da tekrar denemez). **Sabit tek/çift gün DEĞİL**: başarısız tur işaretlenmez, ertesi gün yeniden denenir. Elle `/sozluk` bu aralığa girmez ve işaret yazmaz (madde 19). Kod: `telegram/akislar/sozluk.py ›
    sozluk_zamanli_gunu_mu / sozluk_zamanli_isaretle`, çağıran `uretim._sozluk_slotu` (`oto_yayin is True` = zamanlanmış tur). **Sonuçlar:** (a) 66 kartlık arşiv ≈132 gün yeter (eskiden 66); (b) `HEDEF_KART` 730 → **365**
    (`BEKLEME_GUN // YAYIN_ARALIK_GUN`: iki günde bir kartla 2 yıl tekrarsız; tekrar bekleme süresi 730 gün aynen) — Gemini'nin yazacağı kart hedefi yarıya indi; (c) stok uyarısı "2 günde bir kartla ≈N gün" der.
    Sıklığı değiştirmek tek satır (`YAYIN_ARALIK_GUN`). Testler: `tests/test_sozluk_iki_gunde_bir.py` (6 günlük simülasyon dahil). Test yazarken: paylaşılan test DB'sinde bu işaret kalır, zamanlanmış sözlük turunu çağıran
    testler `sozluk_zamanli_gunu_mu`/`sozluk_zamanli_isaretle`'yi yamalamalı (bkz. `test_sozluk_oto_yayin_guvenceleri.py`).
21. **Finans bülteni (durum, 2026-10-13):** kullanıcı onaysız yayına itiraz etmedi ("oto yayınlanabilir") ama tasarımı henüz görmediği için önce bakılması istendi. Bülten ayrı bir tasarım DEĞİL: konu bankasının S5 (kredi/banka/tüketici hakları)
    konusundan `konudan_uret` ile modelle yazılır ve diğer rehber içerikle AYNI otorite carousel'iyle (`make_image.otorite_gonderi_slaytlari_uret`, 6 slayt 4:5) çizilir; YouTube için ayrıca Shorts videosu. Tek fark rozet/konu. Son iki yayın: #72 (17 Eylül,
    14 gün cayma) ve #103 (18 Eylül, DASK). Elle tetiklenince de hâlâ `--oto-yayin` (madde 19'da bilerek dışarıda). Faiz/oran tablosu, rakam grafiği gibi finansa özgü görsel YOK. Karar bekliyor: finans için ayrı tasarım gerekir mi, elle de düğmeli kart mı.

22. **Telegram buton sözleşmesi testi + 4 ölü buton — 2026-10-13.** Buton adları (`callback_data`) iki yerde ayrı yazılıyor: Python mesajı kurar (`src/telegram/*`, `src/yayin/`, `src/kota_uretici.py`, `src/hata_bildir.py`…), `worker/index.js`
    callback bloğu tıklamayı işler. **Worker tanımadığı adı SESSİZCE yok sayar** (cevap yok, bekleme simgesi döner, hata günlüğüne düşmez) ve hiçbir test iki tarafı karşılaştırmıyordu. Yeni `tests/test_buton_sozlesmesi.py`: (1) Python'ın ürettiği her ad Worker'da işleniyor,
    (2) Worker'ın kendi menüleri de, (3) Worker'ın yolladığı her `repository_dispatch` olayını bir workflow dinliyor, (4) statik adlar 64 bayt sınırında; ayrıştırıcı çürürse "yeterince şey bulundu" denetimleri kırılır (iki yönde bozma denemesiyle doğrulandı).
    **Bulduğu ve düzelttiği ölü butonlar (hepsi Python tarafında düzeltildi, Worker dağıtımı gerekmez):** (a) içerik inceleme kartındaki **▶️ Şimdi Yayınla** `yayinla:<id>` yolluyordu → artık `onayla:haber:hepsi:<id>` (hata kurtarma düğmesiyle aynı Worker yolu; kanal seçimi sorulmadan
    hepsine yayınlar, yayın kapısı yine uygulanır); (b) kapak adayları mesajındaki **🔄 Başka adaylar** `foto_degistir:<id>` → `foto_adaylar:<id>`; (c) kota raporundaki **🎛 Kontrol Paneli** `yonetim_panel` → `panel` (iki yerde). Bu üç düğme eskiden basılınca hiçbir şey yapmıyordu;
    iki eski test de ölü adı doğru diye sabitlemişti (`test_kota_uretici`, `test_telegram_instabot_seviyesi`; güncellendi). Altın çıktılar yalnız bu düğme adları için yeniden kaydedildi (telegram: 6 `incele_*`/`kart_incele_*` senaryosu, yayinla: `foto_adaylar`).
    **Bilinçli istisna** (`BILINEN_OLU`): `piyasa_yayinla` (piyasa özelliği kapalı, madde 8). Yeni buton eklerken: Python'da üret → Worker'da `data === "ad"` / `data.startsWith("ad:")` işleyicisi yaz → test yeşil. Test, listeyi çürümekten korur (artık ölü olmayan ya da hiç üretilmeyen istisna kırılır).

23. **Hatırlatma kapalı, onay süresi 1 gün, onaylanmayan içerik havuza döner ve YENİDEN ÜRETİLMEZ — 2026-10-13 (kullanıcı kararı).** Kullanıcının sözü: "hatırlatma gelmesin, istemiyorum; bir içeriği 1 gün yayınlamadıysam havuza dönsün,
    daha önce hazırlandığı için tekrar oluşturulmasın, başka bir gün tekrar önerilir."
    * **Hatırlatma:** `scripts/hatirlat.py` zamanlanmış koşuda (Cloudflare 13:30 / 21:30 + GitHub yedeği) artık YALNIZ sessiz kuyruk bakımı yapar; mesaj atmaz (eski "İÇERİK ZAMAN AŞIMINA UĞRADI" özeti de kalktı). Hatırlatma yalnız KULLANICI isterse:
      `--zorla` (Telegram "⏰ Onayları Hatırlat" düğmesi, `/hatirlat`). Cron'lar ve `hatirlat` olayı/slot adları (`hatirlat_ogle/aksam`) DEĞİŞMEDİ (yeniden Worker dağıtımı gerekmedi); workflow görünen adı "Onay Kuyruğu Bakımı (EDM)".
    * **1 gün:** `ZAMAN_ASIMI_DAKIKA = 24*60` (eskiden 5 gün). Bakım günde iki koşu olduğu için fiilen 24–36 saat. Süresi dolanın eski albümü ve kartı gruptan SİLİNİR (ölü düğme kalmasın; Telegram 48 saat sınırı içinde kalır).
      Planlı yayını bekleyen içerik (planlanan_yayin) süresi dolsa da dokunulmaz.
    * **Havuz:** modelle yazılmış, konu bankasından gelen hazır içerik (`konu_bankasi.HAVUZ_FORMATLARI` = b1, nedir_dogrusu, net_cevap, vaka; `havuza_alinabilir_mi`) SİLİNMEZ: `haberler.durum='havuzda'` (`db.durum_havuza_al`). Konusu havuza İADE EDİLMEZ
      (hazır içerik havuzun kendisi; yoksa konu yeniden seçilip model ikinci kez çağrılırdı). **Yeniden sunum:** aynı formatın bir sonraki turu (10:00 döngüsü ya da elle /dogrusu /vaka /soru; `uretim.konu_bankasindan_hazirla` ve `hizli_icerik_uret`)
      ÖNCE havuza bakar (`telegram/akislar/havuz.py › havuzdan_sun`, en eski önce): içerik MODEL ÇAĞRILMADAN, AYNI numarayla (#id) yeniden onaya sunulur (slaytlar saklı `detay_metni`'nden yeniden çizilir; yayın kapısı yine çalışır). Kapıdan geçemezse arşive alınır,
      konusu iade edilir ve o turda taze içerik üretilir (gün boş geçmez). Havuz kayıtları `eski_kayitlari_temizle` ile 14 günde silinir (havuz sınırsız büyümez); kullanıcı "Çöpe At / Bu turu atla" derse içerik havuza girmez.
    * **Havuza girmeyenler (eskisi gibi arşiv + konu iadesi):** haber kaynaklı içerik (bayatlar), sözlük kartı (yeniden kurmak ucuz), finans, reels, metni/manşeti eksik olanlar.
    * **Bilinen artıklar (kaldırılmadı, Gemini'ye bırakıldı):** "⏰ 1 saat ertele" düğmesi (Worker `anaMenu`, `yonetim.ertele`) ve ayar menüsündeki "Onay Hatırlatıcı AÇIK/KAPALI" düğmesi (`src/ayar.py › hatirlatici`) artık anlamsız — kaldırmak Worker + altın çıktı + testleri değiştirir.
    * Testler: `tests/test_havuz_yeniden_sunum.py` (14: sorgular, yeniden sunum modelsiz, kapıdan geçmeyen, format karışmaz, uçtan uca), `test_onay_kuyrugu_ve_iade.py`, `test_sozlesme.py`, `test_planli_yayin.py` yeni kurallara uyarlandı;
      altın çıktı yalnız `ertele_haber/ertele_ilan` mesaj metni için yeniden kaydedildi.
24. **Depo PUBLIC (doğrulandı 2026-10-13, GitHub API `private:false`).** AKSIYON-PLANI.md §0.1 "PRIVATE" diyor (11 Eylül) ama eskimiş. Sonuç: depoya sır, kişisel veri, jeton, müşteri bilgisi YAZILMAZ (DB ve .md dosyaları herkese açık);
    `data/edm.db`'de onaylanmamış taslaklar ve Telegram grup kimliği görünür (ARCHITECTURE.md §5). Sırlar yalnız GitHub Secrets / Cloudflare secret'larında durur; sohbette istenmez.
25. **Havuzdan sunulan içeriklerin kuyruk bakımında erken silinmesi hatası düzeltildi — 2026-10-15 (Gemini).** 14 Ekim 10:01'de günün içeriği olarak havuzdan sunulan #594 numaralı içerik, henüz 3.5 saat geçmişken 13:30 sessiz kuyruk bakımında silinip tekrar havuza çekilmişti ("günün içeriği çalışmadı" şikayeti).
    * **Kök neden:** `scripts/hatirlat.py:bekleme_suresi_dakika`, bekleme süresini içeriğin ilk üretim tarihi olan `haberler.eklenme_tarihi`'ne göre hesaplıyordu (11 Ekim'de üretilmiş içerik 14 Ekim'de sunulduğunda 4.117 dk yaşlı görünüp anında 24 saat kuralına takılıyordu).
    * **Çözüm:** `db.onay_bekleyen_haberleri_getir` artık bekleyen aktif onay isteğinin zaman damgasını (`onay_istekleri.olusturma_tarihi`) subquery ile `onay_istegi_tarihi` olarak döner; `db.son_onay_istegi_tarihi` eklendi; `idx_onay_istekleri_ref` indeksi eklendi. `bekleme_suresi_dakika` önce bu aktif istek tarihini, yoksa geriye dönük uyumluluk için `eklenme_tarihi`'ni kullanır.
    * **Testler:** `tests/test_havuz_yeniden_sunum.py::test_havuzdan_yeniden_sunulan_icerik_hemen_havuza_donmez_24_saat_bekler` eklendi. Ayrıca test paketindeki iki lokal pürüz düzeltildi (`tests/test_telegram_altin.py`'de `<KOK>` öncesi `sys.executable` normalizasyonu ve `tests/test_sozluk_oto_yayin_guvenceleri.py`'de `sozluk_zamanli_gunu_mu` mock'u). Tam test paketi 1203/1203 yeşil.

26. **Sözlük Dalga 2 — A12 Sözleşme Kurulması ve Kira Tamamlama — 2026-10-15 (Gemini).** Claude devrindeki sözlük eksiklerinin tamamı giderildi:
    * **A12 (TBK md. 1–40 Sözleşmenin kurulması, şekil, gabin, irade sakatlıkları, temsil):** 15 yeni kart (`SZ-067`..`SZ-081`).
    * **Kira tamamlama (A16_revize):** md. 339/2 geçici kiralar (`SZ-082 GEÇİCİ KONUT KİRASI`), md. 346 kiracı aleyhine düzenleme yasağı (`SZ-083 EK ÖDEME YASAĞI`), md. 353 dava süresinin uzaması (`SZ-084 DAVA SÜRESİ UZAMASI`).
    * **SZ-007 İHTİYAÇTAN TAHLİYE revizyonu:** `data/sozluk_kartlari.yaml`'daki SZ-007'ye md. 353 yazılı bildirimle dava süresinin bir yıl uzaması istisnası eklendi; mevzuat atfı `Türk Borçlar Kanunu md. 350, 353 ve 355` olarak güncellendi.
    * **Bağımsız Hukuki İnceleme & Kalite:** 18 taslak bağımsız alt ajanla kanun metnine karşı iddia iddia incelendi; 12 doğrudan onay, 6 düzeltildi, 0 ret. `sozluk_kart_dogrula.py` 18/18 temiz, `sozluk_kart_birlestir.py` ile arşive eklendi. `gorsel_denetim.py` (226 vaka) sıfır hata. Arşiv **66 → 84 karta çıktı (77'si hiç yayınlanmadı; iki günde bir yayınla ≈154 günlük stok)**.
    * **Testler:** 1204/1204 Python testi OK, 73/73 JS testi OK.

27. **Küçük Temizlikler: Threads `json` içe aktarımı ve anlamsız arayüz düğmelerinin kaldırılması — 2026-10-16 (Gemini).**
    * **`src/threads.py` json hatası:** `metinleri_slaytlara_dagit` fonksiyonunda `import json` eksikti ve `detay_metni` ayrıştırılırken `NameError` yutularak sessizce üst seviye alanlara düşülüyordu. `import json` eklendi; ayrıştırılan model detayları (`slayt_2_detay`, `slayt_3_cozum`, `slayt_4_cta`) ile üst seviye haber alanları (`manset`, `spot`) güvenle birleştirildi (`{**haber_veya_detay, **ayristirilmis}`). Testler: `tests/test_dagitim_ve_zincir.py`'ye JSON ayrıştırma ve bozuk JSON fallback testleri eklendi (8 test OK); `test_yayinla_altin.py` OK.
    * **Arayüz artıkları temizlendi:** 13 Ekim'de hatırlatma kapatılıp 24 saat sessiz havuz kuralına geçildiği için anlamsız kalan **"⏰ 1 saat ertele"** düğmesi onay kartı menüsünden (`src/telegram/menuler.py` ve `worker/index.js › anaMenu`), **"⏰ Onay Hatırlatıcı"** ayarı ise ayar menüsünden (`src/ayar.py` ve `worker/index.js › ayarMenusu`) kaldırıldı. Geriye dönük uyumluluk için Worker ve Python `ertele` işleyicileri korundu (eski mesajlardan tıklanırsa çökmez).
    * **Testler & Altın Çıktı:** `tests/test_buton_sozlesmesi.py` 9/9 yeşil; `tests/test_slot_ve_menu_paritesi.py` ve `tests/test_gorsel_ve_onay_paritesi.py` yeni menü yapısına güncellendi. `tests/altin/telegram.json` menülerden ertele/hatırlatıcı satırlarının kalkması için güncellendi (yalnızca beklenen fark). JS testleri 73/73 yeşil. Worker dağıtımı (`worker-dagit.yml`) gerekecektir.

28. **Sözlük Dalga 3 — A01 & A02 TMK Taşınmaz Mülkiyeti ve Komşuluk Hukuku — 2026-10-18 (Gemini).**
    * **A01 (TMK md. 683–712 Mülkiyet hakkı, bütünleyici parça, doğal ürünler, yararlanma anlaşması, paylaşma istemi, taşınmaz mülkiyeti, tescil ilkesi, resmî şekil, heyelan, olağan zamanaşımı):** 10 yeni kart (`SZ-085`..`SZ-094`).
    * **A02 (TMK md. 718–761 Dikey kapsam, haksız yapı, arazi devri istemi, taşkın yapı, taşınır yapı, komşu hakkı, taşan dal ve kökler, mecra hakkı, zorunlu su hakkı):** 9 yeni kart (`SZ-095`..`SZ-103`).
    * **Bağımsız Hukuki İnceleme Turu:** SOZLUK-KART-URETIMI.md kuralı gereği yazardan bağımsız alt ajan çalıştırıldı; 19 kart kanun metniyle iddia iddia karşılaştırıldı. 19 kartın tamamı yerinde düzeltilerek onaylandı, 0 ret. Karakter sınırları, tipografi yerleşim tabanları (≥112 pt) sağlandı. `MECRA GEÇİRME HAKKI` başlık tabanını aştığı için `MECRA HAKKI` olarak kısaltıldı; `AĞAÇ VE DAL SINIRI` yerine kanun lafzı `TAŞAN DAL VE KÖKLER` getirildi.
    * **Birleştirme & Arşiv Büyüklüğü:** `scripts/sozluk_kart_birlestir.py` ile arşive eklendi. Arşiv **84'ten 103 karta çıktı (94'ü hiç yayınlanmamış; iki günde bir yayınla ≈188 günlük stok!)**. 100 kart barajı aşıldı.
    * **Testler & Doğrulamalar:** `sozluk_kart_dogrula.py` 19/19 temiz. `gorsel_denetim.py` 226 vaka 0 hata. JS testleri 73/73 OK. Sözlük unit testleri 106/106 OK.

29. **Sözlük Dalga 4 — A03 & A04 TMK İrtifak Hakları, Taşınmaz Yükü ve Rehin/İpotek — 2026-10-18 (Gemini).**
    * **A03 (TMK md. 779–849 İrtifak hakları ve taşınmaz yükü):** 9 yeni kart (`SZ-104`..`SZ-112`) — *İrtifak Hakkı, İrtifakın Tescili, İrtifakın Sona Ermesi, İntifada Bakım, Oturma Hakkı, Oturma Kapsamı, Üst Hakkı, Üst Hakkı Süresi, Taşınmaz Yükü*.
    * **A04 (TMK md. 850–903 Taşınmaz rehni ve ipotek):** 9 yeni kart (`SZ-113`..`SZ-121`) — *Taşınmaz Rehni, Rehinde Üst Sınır, Rehnin Resmî Şekli, İpotek, İpotekli Yerin Devri, Rehin Derecesi, Boş Derece Kuralı, İpotekli Borç Senedi, Kaynak Hakkı*.
    * **Bağımsız Hukuki İnceleme & Mükerrer Tespiti:** 19 taslak bağımsız inceleme ajanınca incelendi. İNTİFA SÜRESİ taslağı, arşivdeki SZ-020 (İntifa Hakkı) ile aynı hükümleri (gerçek kişilerde ölümle sona erme, tüzel kişilerde 100 yıl) mükerrer kıldığı gerekçesiyle **REDDEDİLDİ** (1 ret, 1 onay, 17 düzeltildi). Diğer kartlarda kanun metnine dayalı kritik eklemeler yapıldı (md. 784 mülkiyet birleşmesi, md. 785 terkin istemi, md. 836 üst hakkı uzatımında ön taahhüt yasağı, md. 871 boş dereceye geçiş sözleşmesinin tapuya şerhi, md. 883 borç bitince terkin hakkı, md. 899 resmi değer takdiri).
    * **Birleştirme & Arşiv Büyüklüğü:** `scripts/sozluk_kart_birlestir.py` ile 18 kart arşive eklendi (`SZ-104`..`SZ-121`). Arşiv **103'ten 121 karta çıktı (112'si hiç yayınlanmamış; iki günde bir yayınla ≈224 günlük / 7.5 aylık stok!)**.
    * **Testler & Doğrulamalar:** `sozluk_kart_dogrula.py` 19/19 temiz. `gorsel_denetim.py` 226 vaka 0 hata. JS testleri 73/73 OK. Sözlük unit testleri 178/178 OK.

30. **Sözlük Dalga 5 — A05 TMK Tapu Sicili ve A06 Tapu Kanunu 2644 — 2026-10-18 (Gemini).**
    * **A05 (TMK md. 998–1025 Tapu sicili, tescil, şerh, aleniyet, güven ilkesi, yolsuz tescil):** 10 yeni kart (`SZ-122`..`SZ-131`) — *Kütüğe Kayıt, Zarardan Sorumluluk, Kişisel Hak Şerhi, Tasarruf Kısıtlaması, Geçici Tescil Şerhi, Beyanlar Sütunu, Tescil İstemi, Tapunun Aleniyeti, Tapuya Güven İlkesi, Yolsuz Tescil*.
    * **A06 (Tapu Kanunu 2644 md. 26 ve 35 resmî senet, şerh süresi, yabancı edinim):** 8 yeni kart (`SZ-132`..`SZ-139`) — *Resmî Senet, Farklı Yerde İmza, Evde İmza İmkânı, Satış Vaadi Terkini, Kredi İpoteği, Yabancının Edinimi, Yabancıda Proje Şartı, Yabancıda Tasfiye*.
    * **Bağımsız Hukuki İnceleme Turu:** SOZLUK-KART-URETIMI.md kuralı gereği yazardan bağımsız alt ajan çalıştırıldı; 18 kart kanun metinleriyle iddia iddia karşılaştırıldı. 18 kartın tamamı yerinde düzeltilerek onaylandı, 0 ret. Kanuni koruyucu kurallar (md. 1007 yetkili mahkeme kuralı, md. 1024/3 yolsuz tescili kötüniyetliye doğrudan ileri sürebilme, Tapu Kanunu md. 26 evde imzaya gelen memura haciz tebliği şartı, md. 35 yabancıda Cumhurbaşkanının 2 katına çıkarma yetkisi) kartlara işlendi.
    * **Birleştirme & Arşiv Büyüklüğü:** `scripts/sozluk_kart_birlestir.py` ile 18 kart arşive eklendi (`SZ-122`..`SZ-139`). Arşiv **121'den 139 karta çıktı (130'u hiç yayınlanmamış; iki günde bir yayınla ≈260 günlük / 8.5+ aylık stok!)**.
    * **Testler & Doğrulamalar:** `sozluk_kart_dogrula.py` 18/18 temiz. `gorsel_denetim.py` 226 vaka 0 hata. JS testleri 73/73 OK. Sözlük unit testleri 178/178 OK.

31. **ElevenLabs v4 ve Fish Audio S2.1 Fallback TTS Motoru Entegrasyonu (Instabot Paritesi) — 2026-10-20 (Gemini).**
    * **Ne yapıldı:** `instabot` projesindeki ElevenLabs v4 Audio Tag / `atempo` hızlandırma ve Fish Audio S2.1 (`api.fish.audio/v1/tts`) fallback motoru altyapısı `postedm`'e uyarlandı.
    * **`src/okunus.py`:** `ses_icin_kesme_kaynat` fonksiyonu eklendi; ElevenLabs'in kesme işaretlerini duraksama veya ayrı kelime algılayıp ekleri kopuk okuması önlendi ("Aksoy'un" -> "Aksoyun", "Silivri'de" -> "Silivride"). Kısaltmalar ("TBMM'de") korundu.
    * **`src/ses.py`:** `fish_audio_seslendir`, `_hizlandir_atempo`, `ses_etiketi_sec`, `son_kullanilan_motor()` eklendi. `metin_seslendir` ElevenLabs'te 401/402 kota veya yetki hatası aldığında döngüde beklemeden ve gereksiz diğer ElevenLabs seslerini denemeden anında Fish Audio S2.1 motoruna fallback yapıyor; anahtar yoksa da doğrudan Fish Audio deneniyor. Üretilen seste son kullanılan motor takip ediliyor.
    * **`config.yaml`:** Kullanıcı talimatıyla Instabot ses ayarları birebir kopyalandı (`ses_id: "KAGDtM2gzDrjWlUp2KNe"` Ana haber spikeri, `yedek_ses_id: "KediIz7pebzt5TaDHiiZ"` Alex, `fish_voice_id: "a6d624c6b8de45d2b89eb0da9a691872"` Mazlum Kiper, `model: "eleven_v4"`, `speed: 1.22`).
    * **Testler & Doğrulamalar:** `tests/test_ses_elevenlabs.py` (13 test OK), `tests/test_seslendirme.py` (22 test OK), `tests/test_okunus.py` (10 test OK), `tests/test_sesli_yayin.py` (17 test OK), `tests/test_instabot_yeni_moduller.py` ve güvenlik sözleşmesi testleri OK, JS worker testleri 73/73 OK.

32. **Yedek GitHub Cron'larının Silinmesi — 2026-10-21 (Gemini).**
    * **Ne yapıldı:** Cloudflare Worker cron'ları 13 Ekim'den bu yana sorunsuz çalıştığı için ARCHITECTURE.md §4'teki 20 Ekim sonrası planı devreye alındı. 4 adet workflow dosyasındaki (`hazirla.yml`, `gunluk-rapor.yml`, `haber-oneri.yml`, `hatirlat.yml`) gecikmeli yedek `schedule` blokları silindi.
    * **Sözleşme & Testler:** `tests/test_zamanli_isler.py`, `tests/test_zamanli_gunluk_koruma.py` ve `tests/test_sozlesme.py` içindeki schedule/cron kontrolleri güncellendi; tek tetikleyici kuralı pekiştirildi.

33. **Çift Albüm Teslimat Güvencesi & Telegram Idempotensi — 2026-10-21 (Gemini).**
    * **Ne yapıldı:** `src/telegram/album.py` ve `src/telegram/medya_istek.py` içerisinde `sendMediaGroup` zaman aşımı artırıldı (azami 120 sn), HTTP ağ kopması/zaman aşımı durumunda Telegram'ın albümü grupta fiilen oluşturup oluşturmadığı teyit edilerek aynı onay kartı için mükerrer albüm basılması (çift albüm sorunu) engellendi.
    * **Testler:** `tests/test_telegram_medya_teslimi.py` yeşil.

34. **Faz 3: Görsel Motoru Modülerleştirmesi (`src/cizim/` paketi) — 2026-10-21 (Gemini).**
    * **Ne yapıldı:** 4107 satırlık devasa `src/make_image.py` dosyası parçalanarak `src/cizim/` paketi altına 25 adet bağımsız, tek sorumluluklu modüle ayrıldı.
    * **250 Satır Kuralı:** Paketteki 25 dosyanın her biri ve geriye dönük uyumluluk cephesi olan `src/make_image.py` (163 satır) istisnasız $\le 250$ satır sınırına uymaktadır (`tests/test_cizim_paketi.py` ile zorlanır).
    * **Dinamik Tuval Boyutu Desteği:** Hikaye (`story` 9:16) ve besleme (`besleme` 4:5) geçişlerinde `tuval` bağlam yöneticisi modüller arasındaki boyut senkronizasyonunu dinamik olarak yönetir.
    * **Mock / Test Uyumluluğu:** Testlerin `make_image._foto_indir_veya_ac` ve `make_image._haber_gorseli_alternatifi` yamaları şeffaf bir köprüyle `cizim` modüllerine yansıtıldı.
    * **Doğrulama:** `scripts/gorsel_denetim.py` (226 görsel vakanın tümü) 0 HATA ile tamamlandı. 73 JS testi OK. 1213 Python testinin tamamı OK.

35. **LinkedIn Kurumsal Şirket Sayfası Entegrasyonu Devreye Alındı — 2026-10-29 (Gemini).**
    * **Onay Süreci:** LinkedIn Developer portalında `Community Management API` (Development Tier) başvurusu onaylandı.
    * **Hesap & Yetki Doğrulaması:** `EDM Yapı&Gayrimenkul` şirket sayfası (`67226326` / `urn:li:organization:67226326`) bağlandı; `w_organization_social`, `r_organization_social`, `rw_organization_admin` yetkileri içeren 60 günlük aktif OAuth token alındı ve canlı API sorgusuyla (`/rest/organizations/67226326`) HTTP 200 ile doğrulandı.
    * **Canlı Yapılandırma:** Yerel `.env` ve GitHub Actions secret'ları (`LINKEDIN_ACCESS_TOKEN` ve `LINKEDIN_ORGANIZATION_URN`) güncellendi.
    * **Yayın Hattı:** `src/yayin/hedef.py` artık `hepsi` hedefi seçildiğinde LinkedIn'i de otomatik olarak yayın kuyruğuna dahil eder (`hepsi: ['tiktok', 'story', 'threads', 'facebook', 'youtube', 'linkedin']`). Onay kartındaki tekil `💼 LI` butonu da aktiftir.

36. **Platforma Özel Kanca & Metin Mimarisi ve Kapsamlı Sabotaj/Stres Testleri — 2026-10-29 (Gemini).**
    * **Platform Ayrışımı:**
      * **LinkedIn:** B2B mevzuat analizi (`⚖️ MEVZUAT VE YASAL DAYANAK`), kurumsal yatırımcı dili, noter/fiili taksim risk değerlendirmeleri, Silivri/Çatalca bölgesel piyasa analizi. Soru kalıpları ("Yorumlarda buluşalım" vb.) kesinlikle yok; doğrudan profesyonel kaydetme/paylaşma çağrısı.
      * **Threads:** 1/N zincir köprüsü (`👇 Detaylar ve yasal haklar zincirde 🧵`), her slayt görseli için $\le 480$ karakterlik sıralı dağıtım, soru yerine hak koruma amaçlı "Kaydet" çağrısı ve son slaytta kurumsal EDM CTA kilidi.
      * **TikTok:** 150 karakterlik merak kancası ve manşeti kesmeyen başlık kurucu (`baslik_kur`), 4000 karakterlik carousel açıklaması (`aciklama_kur`).
      * **Instagram & Facebook:** İlk 125 karakterde feed kancası, taranabilir maddeler ve kurumsal kapanış.
    * **Son 1 Ayın Hata Teşhisi:**
      * LinkedIn `HTTP 400`: Community Management API token'ı ile çözüldü.
      * TikTok `HTTP 403` (`unaudited_client`): Inbox Draft taslak modunun `BILGI` seviyesinde çalıştığı, akışı çökertmediği doğrulandı.
      * Dağıtım İzolasyonu: Bir kanal aksasa dahi diğer kanalların başarıyla yayına girdiği, DB'ye yazıldığı ve mükerrer paylaşımın önlendiği teyit edildi.
    * **Sabotaj ve Stres Güvencesi:** `tests/test_platform_metinleri_ve_sabotaj.py` (12/12 yeşil) — Null/bozuk veri enjeksiyonu, 10.000 karakterlik dev payload stresi, XSS/SQLi sabotajı, ağır emoji/ZWJ unicode dayanıklılığı, 15 parçalık Threads zinciri ve kanal hata toleransı tam koruma altına alındı.

37. **Telegram Denetimi ve Etkileşim İyileştirmeleri — 2026-10-29 (Gemini).**
    * **Canlı Gönderi Linkleri (`src/yayin/rapor.py`):** Yayın sonuç raporuna Instagram permalink'i (`instagram.post_baglantisi`), Threads, Facebook, LinkedIn (`https://www.linkedin.com/feed/update/{urn}/`) ve YouTube doğrudan tıklanabilir butonları eklendi.
    * **Metin Önizleme (`📝 Metinleri Gör`):** Onay kartına `metin_onizle` aksiyonu eklendi (`src/telegram/menuler.py`, `src/yayin/aksiyonlar/yonetim.py`, `worker/index.js`). Onay öncesinde LinkedIn B2B analiz metni, Threads kancası ve Instagram açıklaması Telegram'da `<pre><code>` bloklarıyla tek tıkla önizlenebiliyor.
    * **Worker & Ayarlar:** `worker/index.js` `ayarMenusu`'ne `kanal_linkedin` butonu eklendi; `anaMenu` Python ile eşitlendi; `/yardim` menüsü güncellendi.
    * **Test Güvencesi:** `tests/test_buton_sozlesmesi.py`, `tests/test_telegram_altin.py`, `tests/test_yayinla_altin.py` ve tüm testler (1229 test) eksiksiz doğrulandı.

38. **YouTube Shorts Daimi Seslendirme ve Facebook Reels Çift-Miks Düzeltmesi — 2026-10-29 (Gemini).**
    * **Kök Neden Çözümü:** `src/ses.py` içindeki `anlatimli_video_uret` çıktısı `video_{pid}_sesli.mp4` olarak adlandırıldı. `src/yayin/videolar.py` ve `src/facebook.py` içinde seslendirilmiş videonun Ffmpeg ile ikinci kez mikslenip Alex/TTS sesinin ezilmesi (`-map 0:v -map 1:a`) engellendi.
    * **YouTube Shorts Daimi Sesli Video:** YouTube hedefte olduğu her durumda (`b.hedef_mi("yt")`) video doğrudan seslendirmeli (`anlatimli_video_uret`) üretilir; Shorts daima seslendirmeli çıkar.
    * **Facebook:** Instagram ile birebir eşitlendi: Instagram'a gönderi gittiğinde Facebook'a da standart gönderi (görsel albümü), Instagram Reels paylaşıldığında Facebook Reels (seslendirmeli video) gider.
    * **Testler:** `test_yayinla_altin.py`, `test_telegram_altin.py`, `test_buton_sozlesmesi.py` yeşil.

39. **Telegram Komut Menüsü Otomasyonu, Bekleyen Planlar Yönetimi ve Metin Düzenleme Rehberi — 2026-10-29 (Gemini).**
    * **Komut Menüsü Otomasyonu (`setMyCommands`):** `scripts/telegram_komutlari_kaydet.py` eklendi. Bot token üzerinden 17 adet güncel komutu Telegram API'ye iletir; `--kuru` modu ağa çıkmadan listeler. Worker'a `/komutlar`, `/komut_guncelle` komutları ve `komut_guncelle` callback'i eklendi (tek tıkla menüyü senkronize eder). Kontrol merkezine `[📋 Komut Menüsü]` butonu bağlandı.
    * **Bekleyen Planlı Yayınlar (`/planlar`):** Cloudflare KV'de (`PLANLAR`) zamanlanmış olarak bekleyen gönderilerin anlık durumunu listeler. Her plan için `[▶️ Hemen Yayınla]` (`plan_hemen:<id>`) ve `[⏹ İptal Et]` (`plan_iptal:<id>`) butonları sunar; kullanıcı GitHub Actions uyanmasını beklemeden yayını anında tetikleyebilir veya iptal edebilir.
    * **Metin Düzenleme Şablon Rehberi (`metin_sablon`):** Onay kartındaki metin menüsüne `[✍️ Düzenleme Şablonu]` butonu eklendi. Tıklandığında kullanıcıya yanıt vererek (Reply) manşet, başlık ve slayt metinlerini nasıl düzenleyebileceğini gösteren doğrudan kopyalanabilir markdown kod blokları gönderir.
    * **Testler & Doğrulamalar:** `tests/worker_planli_yayin.test.mjs` (4 yeni test ile 77/77 test yeşil), `tests/test_buton_sozlesmesi.py` (9/9 yeşil), `tests/test_telegram_paketi.py` (16/16 yeşil), `tests/altin/telegram.json` (güncellendi, 4/4 senaryo yeşil), 1229 Python testinin tamamı OK.

## 11. İŞ BÖLÜMÜ VE DEVİR — CLAUDE İLE ÇALIŞMA 2026-10-13'TE BİTTİ, DEVAM GEMİNİ İLE

Kullanıcı kararları: (1) önce "Claude: paylaşım + Telegram altyapısı; Gemini: sözlük kartları ve geri kalanı" diye bölündü; (2) oturum sonunda **"çalışmayı burada bitiriyoruz, Gemini'ye geçiyorum"**: bundan sonra HER iş (paylaşım, Telegram, sözlük, içerik) Gemini ile sürer.
Yeni oturum/ajan bu bölümü ve GEMINI.md'yi okuyup ona göre davranır.

| Alan | Kod / belge |
|---|---|
| **Paylaşım altyapısı** — kanallara dağıtım, yayın kapısı, zamanlama/tetikleme, yeniden deneme, raporlama, Worker | `src/yayin/`, kanal modülleri (`src/instagram.py`, `facebook.py`, `threads.py`, `tiktok.py`, `youtube.py`, `linkedin.py`, `twitter.py`), `scripts/yayinla.py`, `scripts/hazirla.py`, `worker/`, `.github/workflows/` |
| **Telegram altyapısı** — onay/yönetim yüzü, menüler, kartlar, albüm teslimi, düğme akışları | `src/telegram/` (cephe: `src/telegram_bot.py`), `worker/index.js`, `tests/test_telegram_altin.py`, `tests/test_buton_sozlesmesi.py` |
| **Sözlük kartı üretimi** (A12 ve sonrası dalgalar, reddedilen konuların yeniden yazımı, SZ-007, md. 339/2) ve diğer içerik işleri | SOZLUK-KART-URETIMI.md (devir notu en üstte), `data/sozluk_kartlari.yaml`, `data/sozluk_taslak/` |

Kurallar (modelden bağımsız):
1. Sözlük kartı hattı: yazar → doğrulayıcı → **ayrı** inceleme turu (yazan model kendi kartını incelemez) → birleştirici → tam test + `gorsel_denetim.py`. Doğrulayıcı yeşili doğruluk değildir (dalga 1: %62 kabul).
2. Paylaşım ve Telegram değişiklikleri **altın çıktı güvencesi altında** yapılır (`tests/test_yayinla_altin.py` 70 senaryo, `tests/test_telegram_altin.py` 219 senaryo) ve ARCHITECTURE.md §2'deki katman/yama kurallarına uyar
   (kardeş modüller modül üzerinden çağrılır, dosya ≤250 satır, testler gerçek evi yamalar). Davranış bilerek değişiyorsa altın dosya YALNIZ ilgili senaryolar için yeniden kaydedilir ve fark bu belgeye yazılır.
3. Yeni Telegram butonu: Python'da üret → Worker callback bloğunda `data === "ad"` / `data.startsWith("ad:")` işleyicisi yaz → `tests/test_buton_sozlesmesi.py` yeşil olmalı (madde 22).
4. Öncelik sırasını kullanıcı belirler; ARCHITECTURE.md §4 "Açık işler ve devir" aday havuzudur.

## 12. 2026-10-13 OTURUM ÖZETİ VE GEMİNİ'YE DEVİR

§10 maddeleri ayrıntıdır; burası tek bakışta özet. Çalışma düzeni, komutlar ve tuzaklar: **GEMINI.md**.

### 12.1 Bu oturumda yapılanlar
Madde 1–8 `main`'de ve canlıda (PR #1–#5 birleşti; #4'ü kullanıcının "birleştir" talimatıyla Claude birleştirdi, Worker'ı kullanıcı dağıttı). **Madde 8 (hatırlatma/havuz) ve belgeler dalda (`claude/dreamy-wozniak-jsngzw`), PR birleşince canlı olur.**
1. `scripts/yayinla.py` (1571 satır) → `src/yayin/` paketi, altın çıktı güvencesiyle; "Başka Fotoğraf Bul" çökmesi kendiliğinden düzeldi (madde 14).
2. `src/telegram_bot.py` (2919 satır) → `src/telegram/` (25 modül + canlı takma ad cephesi); `yayindan_kaldir` üretim hatası düzeltildi (madde 15). Faz 2 tamam.
3. Mevzuat önbelleği + sözlük pilotu (Kadastro 3402) + dalga 1 (TBK kira, KMK): arşiv 34 → 66 kart; araç hataları giderildi: süre denetimi ("md. 319 ayıp" → "319 ay"), ek maddeler, başlık yerleşim tabanı (madde 16, 17).
4. Zamanlayıcılar Cloudflare cron'una: günlük içerik ve sözlük (madde 13), rapor / haber önerisi / hatırlatma (madde 18, **Worker dağıtıldı**). GitHub cron'ları gecikmeli yedek; çift çalışmayı `scripts/zamanli_koruma.py` önler.
5. Elle tetiklenen sözlük onaysız yayına çıkmaz, onay kartıyla düşer (madde 19). Zamanlanmış sözlük iki günde bir (madde 20; hedef kart sayısı 365).
6. Finans bülteni incelendi: ayrı tasarımı yok, standart carousel; kullanıcı "şimdilik tamam" dedi (madde 21).
7. Buton sözleşmesi testi + 4 ölü buton düzeltildi (madde 22). Altın çıktıdaki "bugünün tarihi" gizli hatası düzeltildi (`<BUGUN>` normalleştirmesi).
8. Hatırlatma kapatıldı, onay süresi 1 gün, hazır içerik havuza alınıp modelsiz yeniden sunulur (madde 23).
9. Belgeler: bu bölüm, ARCHITECTURE.md §4, ICERIK-SISTEMI.md §5.9, README.md, SOZLUK-KART-URETIMI.md, GEMINI.md (yeni).

### 12.2 Canlıda şu an ne çalışıyor (saatler TR)
| Saat | İş | Nasıl çalışır |
|---|---|---|
| 08:40 | Günlük rapor | Cloudflare → `rapor` → `gunluk-rapor.yml` |
| 09:17 ve 18:17 | Haber önerisi (en çok 5 başlık/mesaj; seçim insanda) | Cloudflare → `haber_oneri` → `hazirla.py --haber-oneri` |
| 10:00 | Günün içeriği (döngü: b1 · nedir_dogrusu · net_cevap · b1); önce havuzdaki hazır içerik, yoksa yeni; **onaya düşer** (albüm + düğmeli kart) | Cloudflare → `slot_hazirla` {bilgilendirici} |
| 12:30 | Sözlük kartı, **iki günde bir**, kapıdan temiz geçerse **onaysız otomatik yayın**; acil fren: GitHub değişkeni `SOZLUK_OTO_YAYIN=0` | Cloudflare → `slot_hazirla` {sozluk} |
| 13:30 ve 21:30 | Sessiz kuyruk bakımı (**hatırlatma YOK**): 1 günü dolduran içerik havuza/arşive | Cloudflare → `hatirlat` |
| 10 dk'da bir | "30 dk / 1-4 saat sonra yayınla" çalar saati | Worker `PLANLAR` KV |
Elle: `/sozluk` `/dogrusu` `/vaka` `/soru` `/reels` `/haber` `/rapor` `/hatirlat` `/panel` ve paneldeki düğmeler; hepsi (finans hariç) albüm + düğmeli onay kartı olarak düşer. Her zamanlanmış işin GitHub `schedule` yedeği duruyor (6–10 saat gecikmeli; aynı gün ikinci kez çalışmaz).

### 12.3 Değişmeyen kullanıcı kararları
Sözlük otomatik yayın kalır (iki günde bir); finans elle de onaysız yayın (şimdilik); X (Twitter) kanalı seçilmez (kalsın); piyasa verisi KAPALI; saatlik site kuyruğu yoklaması KAPALI (site 401); EİDS nedeniyle doğrudan ilan paylaşımı donduruldu;
kullanıcı PR'ları kendisi birleştirir (Claude/ajan "birleştir" denmedikçe birleştirmez); Worker'ı kullanıcı dağıtır (Actions → Worker Dağıt, dal main); sır istenmez; web sitesi (edmyapigayrimenkul.com) bu işin dışında.

### 12.4 Açık işler
ARCHITECTURE.md §4 "Açık işler ve devir" tablosu. En önemlileri: yedek GitHub cron'larını silmek (20 Ekim'den sonra, sorunsuzsa), `worker/index.js`'i bölmek, sözlükte sonraki dalgalar (hedef 365 kart; Dalga 5 tamamlandı, 139 kart var; 260 gün stok).

