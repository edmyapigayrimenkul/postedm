# EDM Yapı & Gayrimenkul — Sosyal Medya Botu (`postedm`)

EDM Yapı & Gayrimenkul (`edmyapigayrimenkul.com`) markasının kurumsal kimliğine, diline ve portföyüne tam uyumlu; **Instagram**, **Threads**, **YouTube Shorts** ve **TikTok** platformlarında paylaşım yapan otomatik ve Telegram onaylı sosyal medya botudur.

---

## 🏗 Mimari ve Çalışma Mantığı

```
[RSS Emlak Haberleri]      [site/data/listings.json (46 İlan)]
          │                                  │
          ▼                                  ▼
   [fetch_news.py]                  [fetch_listings.py]
          │                                  │
          ├──────────────────────────────────┤
          ▼
   [generate_text.py]  (Google Gemini — EDM Ses Tonu: Net, Sakin, Yerel)
          ▼
   [make_image.py]     (Pillow — 1080x1350 4:5 Rölöve/İmar Paftası Kartları)
   [video.py]          (imageio — 1080x1920 9:16 Dikey Video / Shorts)
          ▼
   [telegram_bot.py]   (Telegram Grubuna Önizleme ve Onay Butonları)
          │
          ├── [✅ Tümüne Yayınla]
          ├── [📸 Sadece Instagram]
          ├── [🧵 Sadece Threads]
          └── [❌ Pas Geç]
          ▼
   [Cloudflare Worker] ──► [GitHub Actions (yayinla.yml)]
          ▼
   [Instagram Graph API] + [Threads API] + [YouTube API] + [TikTok API]
```

---

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

### Emlak Haberlerini Tara ve Onaya Gönder:
```bash
python scripts/hazirla.py --haber-tara
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
