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

1. **İçerik Hazırlığı & Cron (Sabah 09:00 TR):**
   * Cloudflare Worker (`postedm/worker/`) içindeki `[triggers] crons = ["0 6 * * *"]` tetikleyicisi saniyesi şaşmadan uyanır.
   * GitHub Actions'taki `.github/workflows/hazirla.yml` iş akışına `sabah_hazirla` sinyali yollar (böylece GitHub'ın yoğun saatlerdeki gecikmeleri aşılır).
   * RSS taranır, Gemini kanca başlıklı 3 slaytlık analiz üretir ve görseller `src/make_image.py` ile çizilir.
   * Telegram grubuna `@PostEdmBot` üzerinden önizleme ve onay butonları (`✅ Yayına Al (IG + FB + Threads)`) iletilir.
2. **Onay ve Yayınlama:**
   * Grupta butona tıklandığında Cloudflare Worker sinyali yakalar ve GitHub Actions `.github/workflows/yayinla.yml`'ı tetikler.
   * `scripts/yayinla.py` devreye girer:
     * Instagram Carousel basılır.
     * Facebook albüm gönderisi basılır.
     * Threads gönderisi basılır.
     * YouTube Shorts için dikey video renderlanıp yüklenir.
   * Başarı raporu anında Telegram grubuna yazılır.

---

## 5. GÜVENLİK VE GİT YÖNETİMİ

* `.env` dosyası kesinlikle `.gitignore` içerisindedir ve commit edilmez.
* Depo origin adresi temizdir: `https://github.com/edmyapigayrimenkul/postedm.git` (URL içine token gömülmez).
* Mac Keychain'deki eski `ozdogangringo-sketch` hesabı izole edilmiştir; push işlemleri dinamik olarak `.env` üzerinden yürütülür.

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

5. **Veritabanı İkili Çakışma & Runner İzolasyonu:**
   * `data/edm.db` ikili SQLite dosyasıdır; `git pull --rebase` çakışması repo'yu detached HEAD'de kilitler.
   * `src/db_senkron.py` çakışma durumunda otomatik `--theirs` ile en taze runner veritabanını seçer, çözülemezse `rebase --abort` ile repoyu temiz bırakır.
   * `data/edm.db`'ye yazan her GitHub Actions workflow'unda `permissions: contents: write` bulunmalıdır.
6. **Yazı Tipi & Eksik Glif Güvenliği:**
   * Inter ve Fraunces fontlarında bulunmayan ok ve emojiler (`➔`, `👉`, `📌`, `📈`, `🎯`) ekranda içi boş kare kutu (`.notdef`) olarak çıkar.
   * `src/make_image.py:_temizle_tipografi` bu glifleri daima güvenli unicode sembollerine (`→`, `◆`, `▲`, `▼`, `★`) dönüştürür.
7. **Token Sağlık Kontrolü:**
   * Düzenli olarak `python scripts/token_kontrol.py` çalıştırılarak tüm API'ler ve Threads 60 günlük token durumu tek komutla denetlenir.

