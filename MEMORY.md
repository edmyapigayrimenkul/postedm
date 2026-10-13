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
1. `worker/index.js` menüleri `telegram_bot.py` menüleriyle BİREBİR aynı kalmalı.
   Worker değişince: `cd worker && npx --yes wrangler deploy`. Son sürümler:
   `830fb293` (öneri + sesli yayın), `a21121a4` (planlı yayın).
2. Worker testleri gerçek çağrıyla: `node --test tests/*.test.mjs` (52 test).

Commit'ler: `6243ae6` `fc6217f` (tasarım) · `a321e32` (test izolasyonu) · `0a8d51e`
`8346378` (glif) · `51071a4` (seslendirme) · `74e1b84` (öneri + sesli yayın) ·
`75427e4` (planlı yayın) · `7bcda6c` (okunuş ölçümü).

## 10. 2026-10-12 DENETİMİ — KURALLAR VE DÜZELTMELER

Tüm maddelerin testi var (`tests/test_onay_kuyrugu_ve_iade.py`, `test_hata_gunlugu.py`, `test_zamanlanmis_duraklatma.py`, `test_otomatik_yayin_kapisi.py`).

1. **Onay zaman aşımı TÜM kuyruğa uygulanır** (`hatirlat.py`). Eskiden `LIMIT 5` yüzünden altıncı ve eski içerikler 5 güne hiç girmiyordu (14 içerik, en eskisi
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
    * **Faz 2 aşama 1–3 (aynı gün):** `telegram_bot.py` 2919 → 1219 satır. `src/telegram/` paketi: `istemci` (tek HTTP kapısı `_istek`), `medya_istek` (foto/video + yeniden deneme), `album`, `temizlik`, `ayarlar` (duraklatma/kanal),
      `menuler` + `menuler_panel` (düğme setleri), `durum_metni` + `sonuc_mesaji` + `kaldir`, `kartlar`, `paneller`. Davranış 219 senaryoda birebir aynı; kuralları `tests/test_telegram_paketi.py` zorlar
      (≤250 satır, `telegram_bot`'a yukarı bağımlılık yok, kardeş işlevler modül üzerinden). **Yeni bir testte Telegram yamalarken:** ağ kapısı `src.telegram.istemci._istek` / `_bot_bilgileri`;
      `telegram_bot.mesaj_gonder` yaması yalnız hâlâ `telegram_bot.py`'de duran akışları sessizleştirir, `sonucu_yaz`/`canli_yayin_durumu_guncelle`/`panel_gonder` gibi taşınmış işlevleri sessizleştirmez.
