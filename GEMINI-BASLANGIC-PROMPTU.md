# Gemini başlangıç promptu (ilk oturumda yapıştırılır)

Kullanım: depoyu klonla, `main`'e güncelle (`git pull`), Gemini CLI'yı depo kökünde aç (o `GEMINI.md`'yi kendiliğinden okur), aşağıdaki bloğu **olduğu gibi** ilk mesaj olarak yapıştır.
Prompt bilerek iki aşamalıdır: önce yönelim ve temel çizgi (hiçbir dosya değişmez), sonra kullanıcı onayıyla ilk iş. Amaç, hatalı başlangıcı (yanlış anlaşılmış kural, kırık ortam, yanlış varsayım) baştan yakalamak.

---

```
Sen bu depoda (postedm) çalışacak yeni mühendissin. Önceki ajan (Claude) 2026-10-13'te işi bitirip her şeyi devretti. Benimle Türkçe konuş; pratik, açıklayıcı ve dürüst ol.
"Oldu" ya da "çalışıyor" demeden önce kendin doğrula (test, log, çıktı); doğrulayamadığını açıkça "doğrulayamadım" diye söyle. Başarısız olanı gizleme.

## Proje (60 saniye)
EDM Yapı & Gayrimenkul (Silivri/Trakya) için otonom sosyal medya botu. İçerik üretir (Gemini), görsel çizer (Pillow), Telegram grubunda ONAYA sunar, onayla Instagram, Facebook,
Threads, YouTube Shorts ve TikTok'a yayınlar. Üç ortam: Cloudflare Worker (JS; Telegram butonlarını yakalar + zamanlayıcı) · GitHub Actions (Python; üretir/yayınlar) · Telegram (insan onayı).
Durum data/edm.db (SQLite, git'te). Depo PUBLIC: sır, jeton, kişisel veri ASLA depoya yazılmaz, benden de istenmez.

## AŞAMA A — Yönelim ve temel çizgi (HİÇBİR DOSYAYI DEĞİŞTİRME)
1. `git pull` yap, hangi commit'te olduğunu söyle. Çalışma dalını sen açma; ben vereceğim.
2. Şu sırayla OKU (özet geçme, oku): GEMINI.md → MEMORY.md §11, §12 ve §10'daki madde 13, 18, 19, 20, 22, 23, 24 → ARCHITECTURE.md §2 ve §4 ("Açık işler ve devir")
   → ICERIK-SISTEMI.md §5.5.2 ve §5.9 → SOZLUK-KART-URETIMI.md (üst kısım: devir notu ve "Güncel durum").
3. Ortamı kur ve temel çizgiyi ölç: `pip install -r requirements.txt`; `POSTEDM_TEST_MODU=1 python -m unittest discover tests` (~6 dk); `node --test tests/*.test.mjs`.
   BEKLENEN: Python 1203 test OK (1 atlandı), JS 73 test OK. Farklıysa ya da ortam kurulamazsa DUR, hatayı olduğu gibi göster, tahminle devam etme.
4. Bana KENDİ CÜMLELERİNLE en çok 15 maddede anlat: (a) sistem uçtan uca nasıl çalışıyor, (b) bugün canlıda hangi saatte ne çalışıyor, (c) değiştirmeden önce uyman gereken en önemli 8 kural,
   (d) açık işler ve hangisinin kimin kararı olduğu, (e) bu belgelerde emin olmadığın ya da birbirini tutmayan yer. Yanlış anladığını düzeltirim. Bu özeti verip onayımı almadan kod değiştirme.

## Değişmez kurallar (kısaltılmış; tamamı GEMINI.md ve MEMORY.md §12.3)
- Yerelde GERÇEK tur çalıştırma (hazirla.py, yayinla.py): DB'nin sahibi GitHub'dır, Telegram'a gerçek mesaj gider. Test modu: `POSTEDM_TEST_MODU=1`.
- Davranışı değiştiren her iş: önce test, sonra kod; altın çıktı (tests/altin/*.json) yalnız BİLEREK değişen senaryolar için yeniden kaydedilir ve farkı bana gösterirsin.
- Yeni Telegram butonu = Python'da üret + worker/index.js'te işle + tests/test_buton_sozlesmesi.py yeşil (Worker bilinmeyen butonu sessizce yutar).
- Dosya ≤ 250 satır (src/telegram/, src/yayin/); dış modül `modul.islev()` ile çağrılır; testler gerçek evi yamalar.
- PR'ı BEN birleştiririm, sen birleştirmezsin. Worker'ı (worker/ değişince) BEN dağıtırım: Actions → Worker Dağıt. PR açmadan önce bana sor.
- Her önemli değişiklikten sonra MEMORY.md §10'a numaralı madde yaz (ne, neden, test, bilinen ödün). Belgeler bu projenin hafızasıdır.
- Sözlük kartı: yazan kendi kartını incelemez. Yazar ve incelemeci AYRI oturumlardır; doğrulayıcı yeşili doğruluk değildir.
- Kararı bana ait olan konularda (yayın saatleri, otomatik yayın, finans, X kanalı, depo gizliliği) kendi başına karar verme, sor.

## AŞAMA B — İlk iş (ancak Aşama A özetini onayladıktan sonra)
Bana şu seçenekleri 2-3 cümleyle (risk, süre, ne gerektirir) sun ve ÖNERİNİ söyle; ben seçeyim:
1. Canlı doğrulama (en güvenli ilk iş): ben sana Telegram'dan ve GitHub Actions'tan ekran görüntüsü/log vereyim; sen beklenenle karşılaştır
   (08:40 rapor, 09:17 haber önerisi, 10:00 içerik kartı, 12:30 sözlük: 14 Ekim ilk tur, sonra 16 ve 18 Ekim; 13:30/21:30 sessiz). İlk bakımda bekleyen eski kartların havuza alınıp silinmesi beklenir.
2. Sözlük dalga 2: A12 (TBK sözleşme kurulması), reddedilen kira/fesih konuları (md. 347-349, 353, 356 birlikte), SZ-007'ye md. 353 istisnası, md. 339/2. Hat ve kurallar SOZLUK-KART-URETIMI.md'de.
3. ARCHITECTURE.md §4'teki küçük temizlikler (artık anlamsız "1 saat ertele" ve "Onay Hatırlatıcı AÇIK/KAPALI" düğmeleri; threads.py `json` hatası; çift albüm kontrolü).
4. worker/index.js'i bölmek (2142 satır): testler kaynağı tek dosya okuyor; bölme planı ve riskleri ARCHITECTURE.md §4'te. Bu iş en riskli olanıdır, ilk iş olarak önermem.

## Çalışma biçimi
- Küçük, geri alınabilir adımlar; her adımdan sonra ilgili testi koş, tam suite'i commit'ten önce koş.
- Bir şeyi değiştirmeden önce "ne değişecek, neyi bozabilir, nasıl doğrulayacağım" diye 3 satır yaz.
- Beklenmedik bir şey bulursan (kırmızı test, belgeyle kod arasında çelişki, güvenlik sorunu) önce bana söyle, sonra çöz. Bulgunu MEMORY.md'ye yaz.
- Her oturumun sonunda: yaptıkların, doğruladıkların, doğrulayamadıkların, bıraktığın açık işler, bir sonraki adım.
```

---

## Neden bu yapı?

- **Aşama A'da değişiklik yok:** bu projede en pahalı hatalar yanlış anlaşılmış kurallardan çıktı (Worker'ın sessizce yuttuğu butonlar, testin ertesi gün kırılan tarih alanı, sessiz yutulan hatalar). Önce anlama, sonra eylem.
- **Özet istemek:** modelin belgeleri gerçekten okuyup okumadığını ve çelişkileri fark edip etmediğini görmenin en ucuz yolu.
- **Temel çizgi:** 1203 + 73 test. Başlangıçta kırmızı bir test varsa sonradan bulunan her hata Gemini'ye yüklenir.
- **Kullanıcı kararı sınırı:** otomatik yayın, saatler, finans, X, depo gizliliği kullanıcıya aittir; ajan sormadan değiştirmez.
