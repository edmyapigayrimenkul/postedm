# postedm — Mimari (2026-10-13)

Bu belge sistemin **bugünkü** yapısını, hedef yapıyı ve oraya nasıl güvenle gidileceğini anlatır. "En baştan düzgün kurmak" burada
**sıfırdan yeniden yazmak değil**, çalışan sistemi davranışını bozmadan katman katman düzene sokmaktır: sistem canlıda her gün
Instagram, Facebook, Threads, YouTube ve TikTok'a yayın yapıyor, yanlış bir satır herkese görünür.

## 1. Sistem tek bakışta

```
 GitHub Actions cron (yedek)  ─┐
 Cloudflare cron (asıl) ───────┼─► hazirla.yml ─► scripts/hazirla.py ─► telegram_bot.slot_icerigi_hazirla_ve_sun
                               │       (konu seç → metin üret → görsel çiz → denetle → onaya sun)
                               │                                   │
 Telegram buton ─► Cloudflare Worker ─► repository_dispatch ─► yayinla.yml ─► scripts/yayinla.py ─► src/yayin/
                               (worker/index.js)                              (kanallara dağıt → DB → Telegram raporu)

 Durum:  data/edm.db (SQLite) git'te ─ her iş sonunda db_kaydet.py ile commit+push (satır bazlı 3'lü birleştirme: src/db_birlestir.py)
```

Üç yürütme ortamı vardır ve birbirini yalnızca **GitHub dispatch + Telegram mesajı + DB dosyası** ile tanır:

| Ortam | Dil | Ne yapar | Kod |
|---|---|---|---|
| Cloudflare Worker | JS | Telegram'dan gelen butonu yakalar, zamanlayıcıdır (10 dk plan, 10:00 ve 12:30 günlük tur) | `worker/` |
| GitHub Actions | Python | İçerik üretir, yayınlar, hatırlatır, raporlar | `.github/workflows/`, `scripts/`, `src/` |
| Telegram | — | İnsanın onay/yönetim yüzü | `src/telegram_bot.py` |

## 2. Katmanlar ve bağımlılık yönü

Hedef: **bağımlılık yalnız aşağı doğru** akar. Alttaki katman üsttekini bilmez.

```
 5  giriş       scripts/*.py                      (komut satırı; iş mantığı yok)
 4  akışlar     src/yayin/ · src/telegram_bot (akışlar) · hazirla
 3  etki        src/instagram.py facebook threads tiktok youtube linkedin twitter · telegram API · upload_image · ses · video
 2  üretim      generate_text · yeni_formatlar · make_image · haber_tasarim · konu_bankasi · sozluk_arsivi · okunus
 1  kural       dogrula · durum_kurali · capraz_denetim · filtre · mevzuat   (saf işlevler: ağa/diske çıkmaz ya da çıkışı enjekte edilir)
 0  durum       db · config · gizlilik · db_birlestir · db_senkron
```

Kurallar (yeni kod bunlara uyar, eski kod buna doğru taşınır):
1. **Kural katmanı (1) hiçbir şeye bağımlı olmaz** — yalnız 0. Böylece "bu içerik yayınlanabilir mi?" sorusu ağsız test edilir (bugün de öyle: `dogrula`, `durum_kurali`).
2. **Dış dünyaya (3) yalnız akışlar (4) çıkar.** Kanal modülü Telegram'a yazmaz; sonucu döndürür, raporlamayı akış yapar. (`src/yayin/kanallar/*` bunu yapıyor, bir istisna: `reels.py` Telegram'a video gönderir çünkü Instagram Reels API ile yüklenemez.)
3. **Başarı/hata metinde aranmaz**, tipli sonuçla taşınır (`src/yayin/sonuc.py`). 2026-10-12'ye kadar "✓" karakteri durum makinesinin girdisiydi.
4. **Dış modüller `modul.islev()` biçiminde çağrılır**, `from modul import islev` değil. Testler modül nesnesini yamalar; kod nereye taşınırsa taşınsın aynı yama geçerli kalır. Bu, bölmeyi güvenli yapan tek kuraldır.
5. **Bir dosya 250 satırı geçmez** (yeni paketlerde `tests/test_yayin_paketi.py` zorlar). Eski büyük dosyalar aşağıdaki planla küçülür.

## 3. Bugünkü durum — neresi düzgün, neresi değil

Düzgün: `db_birlestir` (satır bazlı birleştirme, testli), `dogrula`/`durum_kurali` (saf kurallar), `gizlilik`, `config.veri_yolu` (test izolasyonu), `src/yayin/` (bu belgeyle birlikte bölündü).

Düzensiz (boyut = satır, 2026-10-13):

| Dosya | Satır | Sorun |
|---|---|---|
| `src/make_image.py` | 4107 | 15 görsel biçimi + yardımcılar + tuval yönetimi tek dosyada; `yeni_formatlar.py` (1993) ve `haber_tasarim.py` (2009) ile çizim mantığı üçe bölünmüş, sınırları belirsiz |
| `src/telegram_bot.py` | 2919 | Beş ayrı iş: (a) Telegram API istemcisi, (b) menü/düğme üretimi, (c) durum kartları, (d) içerik akışları (haber, sözlük, finans, reels, ilan, slot), (e) duraklatma/kanal ayarı. 22 kaynak dosyası (src + scripts) ve 31 test dosyası ona bağlı |
| `src/generate_text.py` | 1515 | Model zinciri, istem metinleri, caption süsleme, bütçe |
| `src/db.py` | 777 | Tablolar + tüm sorgular tek yerde; `konu_bankasi`/`sozluk_arsivi` kendi tablolarını ayrıca kuruyor (`tabloyu_kur`) |

## 4. Yol haritası (her faz: önce davranışı dondur, sonra taşı)

Her fazın değişmez sırası: **(1) altın çıktı testi yaz ve ESKİ kodla kaydet → (2) böl → (3) altın çıktı aynı mı bak → (4) fark varsa tek tek karar ver.** Yayın fazında bu 113 senaryoyla yapıldı; 111'i birebir aynı çıktı, 2 fark bilinçli bir hata düzeltmesiydi (bkz. MEMORY.md §10 madde 14).

| Faz | İş | Durum |
|---|---|---|
| 1 | `scripts/yayinla.py` → `src/yayin/` | **Yapıldı** (bu PR) |
| 2 | `src/telegram_bot.py` → `src/telegram/` (`api`, `menuler`, `kartlar`, `akislar/`) | Sıradaki. Önce onay akışı için altın çıktı testi (`haber_onayina_sun`, `sozluk_karti_hazirla_ve_sun`, `slot_icerigi_hazirla_ve_sun`, ilan, reels) |
| 3 | Çizim: `make_image` / `yeni_formatlar` / `haber_tasarim` ortak çizim çekirdeği + biçim başına dosya | Piksel karşılaştırmalı altın görseller (`scripts/gorsel_denetim.py` zaten 164 vaka ölçüyor) |
| 4 | `db.py` → depo başına modül (haber, ilan, onay, ayar, hata) | Küçük; şema değişmez |
| 5 | Zamanlayıcıların tamamı Cloudflare'e (hatırlatma, haber önerisi, günlük rapor) | GitHub cron'u 6–10 saat gecikiyor; yalnız günlük tur taşındı |

**Faz 2'nin tuzağı:** testler `src.telegram_bot.mesaj_gonder` gibi adları yamalıyor (31 dosya). Fonksiyonlar yeni modüllere taşınırsa, eski adı yeniden dışa aktaran bir "kabuk" yetmez: kod yeni modüldeki işlevi çağırır, yama kabuktaki adı değiştirir, yama etkisiz kalır. Doğru yol: taşınan kodun **diğer modüllerdeki işlevleri `telegram_bot.mesaj_gonder()` gibi modül öznitelik erişimiyle çağırması** ya da testleri yeni konuma taşımak. Bu yüzden Faz 2 ayrı, dikkatli bir PR'dır.

## 5. Veritabanı kararı: git'te KALIYOR

`data/edm.db` (SQLite) depoda duruyor. "Neden taşıyoruz?" sorusunun dürüst cevabı: **şimdilik taşımıyoruz.** Önerdiğim gerekçeler ve karşı gerekçeler:

| | Bugünkü ölçüm |
|---|---|
| Boyut | DB 1,7 MB; `.git` 30 MB; 78 commit'in 54'ü DB değişikliği (günde ~4) |
| Büyüme | Her DB commit'i yaklaşık 0,5 MB ekler (30 MB / 54) → bu hızla yılda yüzlerce MB. Actions `checkout` yalnız son commit'i çeker (derinlik 1), yani yavaşlamaz; yalnız `git clone` yavaşlar |
| Gizlilik | **Depo herkese açık.** DB'de onaylanmamış taslaklar, takipçi/etkileşim geçmişi, Telegram grup kimliği (`onay_istekleri.telegram_chat_id`), ilan kaydı var. Bot jetonu/sır **yok** (kural: DB'ye sır yazılmaz; `gizlilik.maskele`). Grup kimliği tek başına sır değildir ama görünür |
| Birleştirme | `db_birlestir` satır bazlı çözüyor; eşzamanlı yazma `concurrency: edm-veritabani` ile sıralı. Çalışıyor, testli, ama bu **ikili dosyayı git'te tutmanın bedeli**: karmaşıklık |

Seçenekler:

| Seçenek | Çözdüğü | Maliyeti | Öneri |
|---|---|---|---|
| A. Olduğu gibi | — | Gizlilik görünür; büyüme yavaş | **Şimdilik bu** |
| B. DB'yi **özel (private) ikinci depoya** taşı | Gizlilik, `.git` büyümesi (kod deposu ayrılır) | `db_senkron`/`db_kaydet` ikinci depoya push eder; Actions'a bir erişim jetonu sırrı; yeni bir hata kaynağı | Gizlilik önemliyse **ilk tercih** |
| C. Depoyu özel yap | Her şey kapanır | Özel depoda Actions dakikası kotalı (ücretsiz planda ayda 2000); bugünkü kullanım ölçülmeli | Kotaya sığıyorsa en basiti |
| D. Cloudflare D1 (SQL) | Worker'ın doğrudan DB okuması (buton anında yanıt), git'ten kurtulma | `db.py` HTTP üzerinden yeniden yazılır, tüm testler ve birleştirme sürücüsü değişir; Actions'tan her sorgu ağ turu | Yalnız Worker'ın **anlık durum okuması** gerçek bir ihtiyaç olursa |

**Taşıma kararını tetikleyecek eşikler:** (1) gizlilik talebi kesinleşirse → B ya da C; (2) `.git` 200 MB'ı geçerse → B; (3) Worker'ın butonda içerik durumunu anında bilmesi gerekirse → D. Hiçbiri bugün yok. Önce Faz 2–4 (kod düzeni), sonra bu karar yeniden bakılır.

## 6. Bu belge nasıl güncel kalır
- Faz bitince tabloda durum güncellenir ve MEMORY.md §10'a bulgu notu düşülür.
- Yeni modül açılırken önce §2'deki katman kuralı sorulur: "bu kod hangi katmanda, aşağıya mı bağımlı?"
- Büyük bölmeden önce altın çıktı testi şart; "testler geçiyor" tek başına yetmez (yayin bölmesinde mevcut testlerin hiçbiri `foto_adaylar` çökmesini yakalamamıştı).
