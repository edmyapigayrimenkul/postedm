# EDM Yapı & Gayrimenkul — Sosyal Medya Botu (`postedm`)

EDM Yapı & Gayrimenkul (`edmyapigayrimenkul.com`) markasının kurumsal kimliğine, diline ve portföyüne tam uyumlu; **Instagram**, **Threads**, **YouTube Shorts** ve **TikTok** platformlarında paylaşım yapan otomatik ve Telegram onaylı sosyal medya botudur.

---

## 🏗 Mimari ve Çalışma Mantığı

**İçerik kararlarının kaynağı [`ICERIK-SISTEMI.md`](ICERIK-SISTEMI.md).**
Kod nasıl paylaşacağını bilir; o belge neyin paylaşmaya değer olduğunu tanımlar.

```
   [data/konu_bankasi.yaml]          [RSS]              [site/data/listings.json]
    61 evergreen konu brief'i      haber akışı              portföy (Faz 2/3)
            │                          │                          │
            ▼                          ▼                          ▼
    [konu_bankasi.py]           [fetch_news.py]           [fetch_listings.py]
    takvime göre seçer          çekirdek terim              (EİDS nedeniyle
    tekrarı önler                süzgeci                     şimdilik donuk)
            │                          │
            └───────────┬──────────────┘
                        ▼
              [generate_text.py]   biçime özel prompt (B1-B5)
                                   ölçülmüş karakter bütçeleri
                                   bütçe aşılırsa onarım turu
                        ▼
               [make_image.py]     karma planlayıcı: 4 ↔ 7 slayt
                                   kutusuz dizgi, 3 zemin varyantı
                        ▼
              [telegram_bot.py]    @PostEdmBot önizleme + onay
                        │
                        ├── [✅ Yayına Al]   └── [❌ Pas Geç]
                        ▼
              [Cloudflare Worker] ──► [GitHub Actions: yayinla.yml]
                        ▼
        Instagram · Facebook · Threads · YouTube Shorts
```

### Neden konu bankası var

Sistem eskiden yalnızca RSS'e bakıyordu ve süzgeç gevşekti: "Selçuk Mızraklı
bugün tahliye oluyor" gibi haberler 8 puanla veritabanına girip modele "bunu
otorite içeriğine çevir" diye veriliyordu. Model de alakasız haberden içerik
uyduruyordu — çöp girdi, çöp çıktı.

Artık varsayılan yol hazırlanmış konu brief'leridir. Haber ancak gerçekten
değerliyse (`HABER_ONCELIK_ESIGI = 12`) takvimin önüne geçer. Yüksek etkileşimli
emlak içeriğinin çoğu zaten haber değil evergreen bilgidir.

## 🚀 Hızlı Başlangıç

### 1. Kurulum
```bash
cd postedm
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Çevre Değişkenleri (.env)
`.env.example` dosyasını `.env` olarak kopyalayıp anahtarlarınızı doldurun:
```ini
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHAT_ID=-1001234567890
GEMINI_API_KEY=AIzaSy...
IMGBB_API_KEY=...
INSTAGRAM_ACCESS_TOKEN=...
INSTAGRAM_ACCOUNT_ID=...
```

---

## 🛠 Kullanım Komutları

### Günlük İçerik (varsayılan: konu bankası, güçlü haber varsa haber):
```bash
python scripts/hazirla.py
```

### Yalnızca Konu Bankasından Üret:
```bash
python scripts/hazirla.py --konu
```

### Konu Bankası Doluluk Durumu:
```bash
python scripts/hazirla.py --durum
```

### Yalnızca RSS Tara:
```bash
python scripts/hazirla.py --haber-tara
```

### Metin Bütçelerini Yeniden Ölç (font/kutu değişince ZORUNLU):
```bash
python scripts/metin_butcesi.py
```

### Portföyden Tek Tıkla İlan Paylaşma Menüsünü Gönder:
```bash
python scripts/hazirla.py --ilan-menu
```

### Doğrudan Bir İlanın Kartlarını Üret:
```bash
python -c "from src.telegram_bot import ilan_postunu_hazirla_ve_sor; ilan_postunu_hazirla_ve_sor('19802542')"
```

---

## 📱 Telegram Bot & Onay Akışı Kurulumu

1. **BotFather**'a gidin, `/newbot` komutuyla bot oluşturun ve `TELEGRAM_BOT_TOKEN`'ı alın.
2. Botu ve onay verecek kişileri bir gruba ekleyin.
3. Botu grupta yönetici yapın.
4. `https://api.telegram.org/bot<TOKEN>/getUpdates` adresine giderek grubun `chat_id`'sini (örn: `-100...`) bulun ve `.env`'ye yazın.

---

## ⚡ Cloudflare Worker Kurulumu (Anında Onay İçin)

Worker, Telegram buton tıklamalarını alıp GitHub Actions'a iletir:
```bash
cd worker
npm install -g wrangler
wrangler secret put TELEGRAM_BOT_TOKEN
wrangler secret put GITHUB_TOKEN
wrangler deploy
```
Ardından Telegram webhook'unu bağlayın:
```bash
curl -F "url=https://<worker-adiniz>.workers.dev" https://api.telegram.org/bot<TOKEN>/setWebhook
```
