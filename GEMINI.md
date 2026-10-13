# GEMINI.md — `postedm` çalışma rehberi

Gemini CLI bu dosyayı otomatik bağlam olarak okur. Önceki ajan (Claude) 2026-10-13'te çalışmayı bitirdi ve her şeyi devretti. **Bu dosya kısa girişi verir; ayrıntı belgelerde.**
Kullanıcı Türkçe konuşur; pratik, açıklayıcı, dürüst cevap ister ("yaptım/oldu" demeden önce doğrula, başarısız olanı açıkça söyle).

## Bu proje ne?

EDM Yapı & Gayrimenkul (Silivri/Trakya) için otonom sosyal medya botu. İçerik üretir (Gemini), görsel çizer (Pillow), **Telegram grubunda onaya sunar**, onayla Instagram · Facebook · Threads · YouTube Shorts · TikTok'a yayınlar.
Üç ortam: **Cloudflare Worker** (JS; Telegram butonlarını yakalar, zamanlayıcı) · **GitHub Actions** (Python; üretir/yayınlar) · **Telegram** (insanın onay yüzü). Durum `data/edm.db` (SQLite, git'te; GitHub sahibidir, yerel değil).
**Depo PUBLIC**: sır, jeton, kişisel veri, müşteri bilgisi ASLA depoya yazılmaz; kullanıcıdan jeton/parola istenmez (sırlar GitHub Secrets / Cloudflare secret'larında).

## Okuma sırası

> İlk oturumsa kullanıcı `GEMINI-BASLANGIC-PROMPTU.md`'deki başlangıç promptunu yapıştırmış olmalı: önce yönelim ve temel çizgi (değişiklik yok), sonra onayla ilk iş.

1. `MEMORY.md` **§11–12** (iş bölümü, bu oturumun özeti, canlı düzen, değişmeyen kullanıcı kararları) ve §10 (numaralı kural/hata/karar defteri; 1–24).
2. `ARCHITECTURE.md` §2 (katman kuralları), §4 (**Açık işler ve devir** tablosu).
3. `ICERIK-SISTEMI.md` (ne paylaşılır: §5.5.2 sözlük, §5.9 onay kuyruğu/havuz) · `SOZLUK-KART-URETIMI.md` (kart üretim hattı, **Gemini devir notu en üstte**) · `README.md` (kurulum, komutlar).
4. `AKSIYON-PLANI.md` tarihsel (11 Eylül); eskiyen yerleri başındaki nottadır.

## Canlıda ne çalışıyor (saatler TR; ayrıntı MEMORY.md §12.2)

08:40 rapor · 09:17 ve 18:17 haber önerisi · **10:00 günün içeriği** (onay kartı; önce havuzdaki hazır içerik) · **12:30 sözlük** (iki günde bir, kapıdan temiz geçerse ONAYSIZ otomatik yayın) · 13:30 ve 21:30 sessiz kuyruk bakımı (hatırlatma YOK) · 10 dk'da bir planlı yayın çalar saati.
Hepsini **Cloudflare cron'u** tetikler (`worker/index.js › ZAMANLI_ISLER`); GitHub `schedule` yedeği gecikmeli durur, `scripts/zamanli_koruma.py` aynı işin günde iki kez çalışmasını önler. Elle: `/sozluk /dogrusu /vaka /soru /reels /haber /rapor /hatirlat /panel`; hepsi (finans hariç) albüm + düğmeli onay kartı olarak düşer.

## Komutlar

```bash
pip install -r requirements.txt                              # qrcode, yaml... eksikse testler içe aktarmada düşer
POSTEDM_TEST_MODU=1 python -m unittest discover tests        # ~6 dk, 1203 test (1 atlanır). Gerçek DB'ye/ağa dokunmaz
node --test tests/*.test.mjs                                 # Worker testleri, 73 test
python scripts/gorsel_denetim.py                             # çizim denetimi (kart/format değişince)
# Altın çıktı: davranışı BİLEREK değiştirdiysen YALNIZ ilgili senaryoları yeniden kaydet, farkı gözle doğrula
TELEGRAM_ALTIN_KAYDET=1 TELEGRAM_ALTIN_SENARYO=ad1,ad2 POSTEDM_TEST_MODU=1 python -m unittest tests.test_telegram_altin
YAYIN_ALTIN_KAYDET=1 YAYIN_ALTIN_SENARYO=ad POSTEDM_TEST_MODU=1 python -m unittest tests.test_yayinla_altin
```
**Yerelde gerçek tur ÇALIŞTIRMA** (`hazirla.py`, `yayinla.py`): DB'nin sahibi GitHub'dır, yerel DB ayrışır ve Telegram'a gerçek mesaj gider. Denemek için `--durum` ya da testler.

## Kurallar (testler çoğunu zorlar)

- **Küçük dosya:** `src/telegram/` ve `src/yayin/` altında dosya ≤ 250 satır (`test_telegram_paketi.py`, `test_yayin_paketi.py`). Sınırdakiler: `akislar/uretim.py` (249), `album.py` (247).
- **Dış modül `modul.islev()` ile çağrılır**, `from modul import islev` ile değil; testler modül nesnesini yamalar. Testler **gerçek evi** yamalar (`patch("src.telegram.istemci.mesaj_gonder")`); `src/telegram_bot.py` yalnız canlı takma ad cephesidir (`_EV` tablosu: yeni genel işlev eklenince tabloya da eklenir, test uyarır).
- **Telegram butonu:** Python'da `callback_data` üret → `worker/index.js` callback bloğunda `data === "ad"` / `data.startsWith("ad:")` işle. Worker bilinmeyen adı SESSİZCE yutar; `tests/test_buton_sozlesmesi.py` iki tarafı karşılaştırır (4 ölü buton böyle bulundu).
- **Zamanlanmış iş:** Worker `ZAMANLI_ISLER` ↔ `wrangler.toml` crons ↔ workflow cron/slot/olay ↔ `worker-dagit.yml` doğrulaması aynı olmalı (`tests/test_zamanli_isler.py`). Yeni slot `ZAMANLI_GUNLUK_SLOTLAR`'a da eklenir.
- **Hata/iş "başarılı" diye bildirilmeden önce** testle ya da Actions çıktısıyla doğrula. Doğrulayıcı yeşili doğruluk değildir (sözlükte yazar çıktısının %62'si geçti).
- Başarısızlık metinde aranmaz, tipli sonuçla taşınır; yayında olan içerik hiçbir başarısız denemeyle "hata"ya düşmez (`src/durum_kurali.py`).

## Süreç

- **PR'ı kullanıcı birleştirir** ("birleştir" demedikçe birleştirme). Dal: kullanıcının verdiği dal; birleşmiş PR'a commit eklenmez, yeni değişiklik güncel `main`'den başlar.
- **Worker'ı kullanıcı dağıtır:** GitHub → Actions → **Worker Dağıt** → Run workflow (Branch: main). İş testleri koşar, dağıtır, Cloudflare'de beklenen cron'ların yazıldığını API'den doğrular (eksikse kırmızı), gruba "✅ Worker dağıtıldı" yazar. Yalnız `worker/` değişince gerekir; Python değişikliği `main`'e birleşince Actions'ta kendiliğinden canlıdır.
- Her önemli değişiklikte MEMORY.md §10'a numaralı madde (ne, neden, test, bilinen ödün) ve gerekirse ARCHITECTURE.md / ICERIK-SISTEMI.md güncellenir. Bu repo'da belgeler hafızadır: sonraki ajan yalnız onları okur.

## Sözlük kartı hattı (Gemini'nin ilk işi)

Arşiv `data/sozluk_kartlari.yaml` (66 kart; hedef 365; iki günde bir yayın). Hat: **yazar → `scripts/sozluk_kart_dogrula.py` → AYRI inceleme turu (kartı yazmayan oturum, kanun metnine iddia iddia bakar) → `scripts/sozluk_kart_birlestir.py --kuru` → tam test + `gorsel_denetim.py`**.
Kanun metni: `scripts/kanun_oku.py madde|ara|kanunlar` (`mevzuat-onbellek` dalındaki önbellek; ayrıntı SOZLUK-KART-URETIMI.md). İlk işler: A12 (TBK sözleşme kurulması), reddedilen kira/fesih konuları (md. 347–349, 353, 356 birlikte), SZ-007'ye md. 353 istisnası, md. 339/2.

## Tuzaklar (acı tecrübe)

- Testler **paylaşılan geçici DB** kullanır: zamanlanmış sözlük/hatırlatma gibi DB'ye işaret yazan yolları çağıran testte `sozluk_zamanli_gunu_mu`/`sozluk_zamanli_isaretle`'yi yamala; sonsuz özyinelemeye dikkat (`hatirlat.db` ile `db` aynı modül: gerçek işlevi yamadan ÖNCE sakla).
- Altın çıktıda "bugünün tarihi" `<BUGUN>` olur (aksi halde test ertesi gün kırılır). Yeni tarihe bağlı çıktı eklersen normalleştir.
- GitHub `concurrency` grubu (`edm-veritabani`) en çok BİR bekleyen koşu tutar; yeni bekleyen eskisini iptal eder (DB'ye yazan işlerde nadir ama sıfır değil).
- Telegram 48 saatten eski mesajı silmeyi genellikle reddeder (kuyruk bakımı 24–36 saatte çalıştığı için sorun olmaz); `callback_data` ≤ 64 bayt; Worker'daki `ertele`/`Hatırlatıcı AÇIK-KAPALI` düğmeleri artık anlamsız (kaldırılabilir, bkz. ARCHITECTURE.md §4).
- Kapak fotoğrafı Pexels'ten gelir (anahtar yoksa yerel havuz): yerelde çizilen önizleme canlıdakinden farklı fotoğraf gösterebilir.

## Açık işler

ARCHITECTURE.md §4 "Açık işler ve devir" (yedek GitHub cron'larını 20 Ekim'den sonra sil · `worker/index.js`'i böl · çift albüm · `threads.py` `json` · site kuyruğu 401 · finans tasarımı · Faz 3–4 · depo public kararı). **Sırayı kullanıcı belirler.**
