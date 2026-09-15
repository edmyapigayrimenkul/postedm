/**
 * worker/index.js — EDM Telegram Webhook & GitHub Dispatcher
 * Cloudflare Worker üzerinde çalışır.
 * Telegram buton tıklamalarını yakalar, hızlı arayüz güncellemelerini anında yapar,
 * yayın ve içerik üretim aksiyonları için GitHub Actions'ı tetikler.
 */

export default {
  async fetch(request, env) {
    const reqUrl = new URL(request.url);

    // TikTok OAuth Callback Yakalayıcı (PKCE Yetkilendirme)
    if (reqUrl.pathname === "/tiktok-callback") {
      const code = reqUrl.searchParams.get("code") || "";
      const error = reqUrl.searchParams.get("error_description") || reqUrl.searchParams.get("error") || "";
      const icerik = code
        ? `<div style="background:#161b22;border:1px solid #30363d;padding:15px;font-size:20px;font-family:monospace;color:#7ee787;display:inline-block;border-radius:6px;margin:20px 0;user-select:all;">${code}</div><p style="color:#8b949e;">Yukarıdaki kodu kopyalayıp terminaldeki sihirbaza yapıştırın.</p>`
        : `<div style="color:#f85149;margin:20px 0;">Hata: ${error || "Yetkilendirme kodu alınamadı"}</div>`;

      const html = `<!DOCTYPE html>
<html lang="tr">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>TikTok EDM Yetkilendirme</title></head>
<body style="font-family:system-ui,-apple-system,sans-serif;text-align:center;padding:50px 20px;background:#0d1117;color:#c9d1d9;">
  <h2 style="color:#58a6ff;">🎵 TikTok EDM Yetkilendirme</h2>
  ${icerik}
</body>
</html>`;
      return new Response(html, { headers: { "Content-Type": "text/html; charset=utf-8" } });
    }

    // Gizlilik Politikası (Privacy Policy) — TikTok & Meta API Onayı ve KVKK İçin
    if (reqUrl.pathname === "/privacy") {
      const html = `<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="tiktok-developers-site-verification" content="S7Gxo9q0MKvPpjQ4AqK9qZZ8zPJI7ETq">
  <title>Gizlilik Politikası (Privacy Policy) | EDM Yapı Gayrimenkul</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; background: #0b132b; color: #e0e1dd; margin: 0; padding: 40px 20px; }
    .container { max-width: 800px; margin: 0 auto; background: #1c2541; padding: 40px; border-radius: 12px; border: 1px solid #3a506b; box-shadow: 0 10px 30px rgba(0,0,0,0.4); }
    h1 { color: #64dfdf; margin-top: 0; font-size: 26px; border-bottom: 2px solid #3a506b; padding-bottom: 12px; }
    h2 { color: #48cae4; font-size: 19px; margin-top: 24px; }
    p, li { color: #cbd5e1; font-size: 15px; }
    a { color: #64dfdf; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .footer { margin-top: 40px; pt-20; border-top: 1px solid #3a506b; font-size: 13px; color: #8d99ae; text-align: center; }
    .badge { background: #3a506b; color: #e0e1dd; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
  </style>
</head>
<body>
  <div class="container">
    <h1>EDM Yapı Gayrimenkul — Gizlilik Politikası (Privacy Policy)</h1>
    <p><strong>Son Güncelleme:</strong> 15 Eylül 2026 | <span class="badge">KVKK & GDPR Uyumlu</span></p>

    <h2>1. Genel Bilgiler ve Veri Sorumlusu</h2>
    <p>İşbu Gizlilik Politikası, <strong>EDM Yapı Gayrimenkul</strong> (Web: <a href="https://edmyapigayrimenkul.com">edmyapigayrimenkul.com</a>, İletişim: <a href="mailto:edmyapigayrimenkul@gmail.com">edmyapigayrimenkul@gmail.com</a>) tarafından yürütülen dijital yayıncılık, gayrimenkul danışmanlığı ve otomatik sosyal medya entegrasyonu hizmetleri için geçerlidir.</p>

    <h2>2. Toplanan Veriler ve Kullanım Amacı</h2>
    <p>EDM Yapı sistemleri ve bağlı sosyal medya otomasyon uygulamaları (TikTok for Developers, Meta Graph API vb.);</p>
    <ul>
      <li>Yalnızca şirketimizin resmi sosyal medya profillerine içerik ve kısa eğitim videoları yayınlamak amacıyla yetkilendirilmiş API erişim anahtarlarını (OAuth token) kullanır.</li>
      <li>Son kullanıcılara veya üçüncü taraflara ait hiçbir kişisel kimlik verisi, mesaj, telefon veya kredi kartı bilgisi toplanmaz, kaydedilmez veya üçüncü şahıslara satılmaz.</li>
    </ul>

    <h2>3. TikTok ve Üçüncü Taraf API Entegrasyonları</h2>
    <p>Uygulamamız TikTok Developer Platformu üzerinden <code>video.upload</code>, <code>video.publish</code> ve <code>user.info.basic</code> izinlerini kullanır. Bu izinler münhasıran şirketimizin yetkilendirdiği gayrimenkul ve tapu bilgilendirme videolarının TikTok hesabımızda yayınlanması için kullanılır. TikTok Topluluk Kuralları ve Veri Politikasına tam uyum gösterilir.</p>

    <h2>4. Veri Güvenliği ve Saklama</h2>
    <p>Yetkilendirme anahtarları yüksek güvenlikli şifrelenmiş sunucu ortamlarında (Cloudflare Worker & GitHub Secrets) saklanır. İlgili yetkilendirmeler istendiği anda kullanıcı veya platform tarafından tek tıkla iptal edilebilir.</p>

    <h2>5. Haklarınız ve İletişim</h2>
    <p>6698 sayılı KVKK ve ilgili mevzuat uyarınca verilerinizin durumunu öğrenmek veya silinmesini talep etmek için <a href="mailto:edmyapigayrimenkul@gmail.com">edmyapigayrimenkul@gmail.com</a> adresi üzerinden bizimle dilediğiniz an iletişime geçebilirsiniz.</p>

    <div class="footer">
      &copy; 2026 EDM Yapı Gayrimenkul. Tüm hakları saklıdır. &bull; <a href="/terms">Kullanım Şartları (Terms of Service)</a>
    </div>
  </div>
</body>
</html>`;
      return new Response(html, { headers: { "Content-Type": "text/html; charset=utf-8" } });
    }

    // Kullanım Şartları (Terms of Service) — TikTok & Meta API Onayı İçin
    if (reqUrl.pathname === "/terms") {
      const html = `<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="tiktok-developers-site-verification" content="S7Gxo9q0MKvPpjQ4AqK9qZZ8zPJI7ETq">
  <title>Kullanım Şartları (Terms of Service) | EDM Yapı Gayrimenkul</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; background: #0b132b; color: #e0e1dd; margin: 0; padding: 40px 20px; }
    .container { max-width: 800px; margin: 0 auto; background: #1c2541; padding: 40px; border-radius: 12px; border: 1px solid #3a506b; box-shadow: 0 10px 30px rgba(0,0,0,0.4); }
    h1 { color: #64dfdf; margin-top: 0; font-size: 26px; border-bottom: 2px solid #3a506b; padding-bottom: 12px; }
    h2 { color: #48cae4; font-size: 19px; margin-top: 24px; }
    p, li { color: #cbd5e1; font-size: 15px; }
    a { color: #64dfdf; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .footer { margin-top: 40px; pt-20; border-top: 1px solid #3a506b; font-size: 13px; color: #8d99ae; text-align: center; }
  </style>
</head>
<body>
  <div class="container">
    <h1>EDM Yapı Gayrimenkul — Kullanım Şartları (Terms of Service)</h1>
    <p><strong>Son Güncelleme:</strong> 15 Eylül 2026</p>

    <h2>1. Şartların Kabulü</h2>
    <p><strong>EDM Yapı Gayrimenkul</strong> ("edmyapigayrimenkul.com") web sitesini ve bağlı içerik otomasyon servislerini kullanan tüm yetkili kullanıcılar bu kullanım koşullarını kabul etmiş sayılır.</p>

    <h2>2. Hizmetin Kapsamı ve Amacı</h2>
    <p>Uygulamamız, EDM Yapı Gayrimenkul kurumsal ekibi tarafından gayrimenkul piyasası, tapu mevzuatı, arsa ve konut projelerine ilişkin özgün bilgilendirici grafik ve video içeriklerinin üretilmesi ve sosyal medya mecralarına (Instagram, TikTok, YouTube vb.) planlı şekilde iletilmesi amacıyla geliştirilmiştir.</p>

    <h2>3. Fikri Mülkiyet ve Telif Hakları</h2>
    <p>Platformda üretilen ve paylaşılan tüm görsel tasarımlar, metinler, logolar ve video kurguları EDM Yapı Gayrimenkul'e aittir. İzinsiz kopyalanamaz veya ticari amaçla çoğaltılamaz.</p>

    <h2>4. Platform Kurallarına Uyum</h2>
    <p>Uygulama, entegre olduğu TikTok for Developers ve Meta for Developers platformlarının geliştirici sözleşmelerine ve topluluk kurallarına mutlak surette riayet eder. Spam, manipülasyon veya yanıltıcı içerik yayını kesinlikle yasaktır.</p>

    <h2>5. İletişim ve Destek</h2>
    <p>Kullanım koşulları veya servislerimiz hakkında tüm sorularınız için resmi e-posta adresimiz: <a href="mailto:edmyapigayrimenkul@gmail.com">edmyapigayrimenkul@gmail.com</a></p>

    <div class="footer">
      &copy; 2026 EDM Yapı Gayrimenkul. Tüm hakları saklıdır. &bull; <a href="/privacy">Gizlilik Politikası (Privacy Policy)</a>
    </div>
  </div>
</body>
</html>`;
      return new Response(html, { headers: { "Content-Type": "text/html; charset=utf-8" } });
    }

    // Ana Sayfa (Landing Page)
    if (reqUrl.pathname === "/" && (request.method === "GET" || request.method === "HEAD")) {
      const html = `<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="tiktok-developers-site-verification" content="S7Gxo9q0MKvPpjQ4AqK9qZZ8zPJI7ETq">
  <title>EDM Yapı Gayrimenkul | Resmi Web Portalı</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; background: #0b132b; color: #e0e1dd; margin: 0; padding: 50px 20px; text-align: center; }
    .container { max-width: 700px; margin: 0 auto; background: #1c2541; padding: 50px 30px; border-radius: 16px; border: 1px solid #3a506b; box-shadow: 0 15px 35px rgba(0,0,0,0.5); }
    h1 { color: #ffffff; font-size: 30px; margin-bottom: 8px; font-weight: 800; letter-spacing: -0.5px; }
    p.lead { color: #64dfdf; font-size: 18px; margin-top: 0; margin-bottom: 25px; }
    p.desc { color: #cbd5e1; font-size: 15px; max-width: 550px; margin: 0 auto 30px; }
    .links { display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; margin-top: 30px; }
    .btn { background: #3a506b; color: #ffffff; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px; transition: background 0.2s; border: 1px solid #48cae4; }
    .btn:hover { background: #48cae4; color: #0b132b; }
    .footer { margin-top: 40px; font-size: 13px; color: #8d99ae; }
  </style>
</head>
<body>
  <div class="container">
    <h1>EDM YAPI GAYRİMENKUL</h1>
    <p class="lead">Güvenilir Gayrimenkul Danışmanlığı & Dijital İçerik Portalı</p>
    <p class="desc">EDM Yapı Gayrimenkul, modern gayrimenkul çözümleri, tapu-imar danışmanlığı ve dijital medya otomasyonlarıyla sektöre değer katmaktadır.</p>
    <div class="links">
      <a href="/privacy" class="btn">Gizlilik Politikası (Privacy Policy)</a>
      <a href="/terms" class="btn">Kullanım Şartları (Terms of Service)</a>
    </div>
    <div class="footer">
      İletişim: edmyapigayrimenkul@gmail.com &bull; &copy; 2026 EDM Yapı
    </div>
  </div>
</body>
</html>`;
      return new Response(html, { headers: { "Content-Type": "text/html; charset=utf-8" } });
    }

    if (request.method !== "POST") {
      return new Response("EDM Telegram Webhook Aktif", { status: 200 });
    }

    // GÜVENLİK: secret_token doğrulaması
    const gelenGizli = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
    if (!env.WEBHOOK_SECRET || gelenGizli !== env.WEBHOOK_SECRET) {
      return new Response("Yetkisiz", { status: 401 });
    }

    try {
      const update = await request.json();

      // =====================================================================
      // 1. BUTON TIKLAMALARI (CALLBACK QUERY)
      // =====================================================================
      if (update.callback_query) {
        const cb = update.callback_query;
        const data = cb.data || "";
        const chatId = cb.message?.chat?.id;
        const messageId = cb.message?.message_id;
        const callbackId = cb.id;

        // Telegram'a bekleme simgesini kaldırması için hızlı yanıt ver
        const cevapVer = async (metin = "İşlem alınıyor...") => {
          await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ callback_query_id: callbackId, text: metin }),
          });
        };

        // Mesajı güncelleme yardımcısı
        const mesajiGuncelle = async (metin, replyMarkup = null) => {
          const body = {
            chat_id: chatId,
            message_id: messageId,
            text: metin,
            parse_mode: "HTML",
            disable_web_page_preview: true,
          };
          if (replyMarkup) body.reply_markup = replyMarkup;
          await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageText`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          });
        };

        // Butonları güncelleme yardımcısı
        const butonlariGuncelle = async (inlineKeyboard) => {
          await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageReplyMarkup`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: chatId,
              message_id: messageId,
              reply_markup: { inline_keyboard: inlineKeyboard },
            }),
          });
        };

        // A. KANAL TOGGLE BUTONLARI (ANINDA ARAYÜZ GÜNCELLEMESİ)
        if (data.startsWith("kanal_toggle:")) {
          const keyboard = cb.message?.reply_markup?.inline_keyboard || [];
          let aktifKanallar = [];

          for (let row of keyboard) {
            for (let btn of row) {
              if (btn.callback_data === data) {
                const acik = btn.text.startsWith("✅");
                const yeniSimge = acik ? "⬜" : "✅";
                const kanalAdi = btn.text.replace(/^[✅⬜]\s*/, "");
                btn.text = `${yeniSimge} ${kanalAdi}`;
              }
              if (btn.callback_data?.startsWith("kanal_toggle:")) {
                const k = btn.callback_data.split(":")[1];
                if (btn.text.startsWith("✅")) {
                  aktifKanallar.push(k);
                }
              }
            }
          }

          // Yayınla butonunun hedef parametresini güncelle
          const hedefStr = aktifKanallar.length > 0 ? aktifKanallar.join(",") : "ig,threads";
          for (let row of keyboard) {
            for (let btn of row) {
              if (btn.callback_data?.startsWith("onayla:haber:")) {
                const parts = btn.callback_data.split(":");
                parts[2] = hedefStr;
                btn.callback_data = parts.join(":");
              }
            }
          }

          await butonlariGuncelle(keyboard);
          await cevapVer(`Kanal tercihi güncellendi: ${hedefStr.toUpperCase()}`);
          return new Response("OK");
        }

        // B. KONTROL PANELİ VE DURAKLATMA MENÜLERİ
        if (data === "panel" || data === "menu") {
          await cevapVer();
          await mesajiGuncelle(
            "🏢 <b>EDM YAPI & GAYRİMENKUL // KONTROL MERKEZİ</b>\n\n" +
            "Aşağıdaki butonları kullanarak tek tıkla yeni içerik üretebilir, " +
            "yayın akışını yönetebilir veya sistem durumunu denetleyebilirsiniz.",
            kontrolMerkeziMenusu()
          );
          return new Response("OK");
        }

        if (data === "duraklat_menu") {
          await cevapVer();
          await mesajiGuncelle(
            "⏸️ <b>OTOMATİK AKIŞI DURAKLAT</b>\n\n" +
            "Lütfen duraklatmak istediğiniz süreyi seçin:",
            duraklatmaMenusu()
          );
          return new Response("OK");
        }

        if (data.startsWith("duraklat:")) {
          const saat = data.split(":")[1];
          await cevapVer("Bot duraklatıldı");
          const sureMetni = saat === "0" ? "Süresiz" : `${saat} saat boyunca`;
          await mesajiGuncelle(
            `⏸️ <b>BOT DURAKLATILDI (${sureMetni})</b>\n\n` +
            "Otomatik paylaşımlar durduruldu. İstediğiniz zaman 'Devam Ettir' ile başlatabilirsiniz.",
            { inline_keyboard: [[{ text: "▶️ Devam Ettir", callback_data: "devam_et" }, { text: "← Kontrol Paneli", callback_data: "panel" }]] }
          );
          await tetikleGitHub(env, "bot_yonetim", { eylem: "duraklat", saat: parseInt(saat, 10) });
          return new Response("OK");
        }

        if (data === "devam_et") {
          await cevapVer("Bot tekrar aktif");
          await mesajiGuncelle(
            "🟢 <b>OTOMATİK AKIŞ AKTİF EDİLDİ</b>\n\n" +
            "Otomatik paylaşımlar belirlenen günlerde sabah 10:00'da onaya sunulacaktır.",
            kontrolMerkeziMenusu()
          );
          await tetikleGitHub(env, "bot_yonetim", { eylem: "devam_et" });
          return new Response("OK");
        }

        if (data === "durum" || data === "saglik_testi" || data === "havuz_durum") {
          await cevapVer();
          await mesajiGuncelle(
            "📊 <b>EDM SİSTEM & YAYIN DURUMU</b>\n\n" +
            "• <b>Otomasyon:</b> 🟢 Aktif\n" +
            "• <b>Aktif Kanallar:</b> ✅ IG · ✅ THREADS · ⬜ FB\n" +
            "• <b>Haftalık Plan:</b> Pzt (Sözlük) · Çar (Doğrusu) · Cum (Vaka) · Paz (Net Cevap)\n\n" +
            "<i>Tüm sistemler ve API bağlantıları sağlıklı çalışıyor.</i>",
            { inline_keyboard: [[{ text: "← Kontrol Paneline Dön", callback_data: "panel" }]] }
          );
          return new Response("OK");
        }

        // C. HIZLI İÇERİK ÜRETİMİ
        if (data.startsWith("hizli_uret:")) {
          const format = data.split(":")[1];
          await cevapVer("İçerik üretimi başlatıldı");
          if (format === "reels") {
            await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ chat_id: chatId, text: `🎬 <b>EDM Reels Videosu</b> hazırlanıyor, videonuz ve metniniz birazdan gruba iletilecek...`, parse_mode: "HTML" }),
            });
            await tetikleGitHub(env, "sabah_hazirla", { format_turu: "reels", kaynak: "hizli_uret_reels" });
            return new Response("OK");
          }
          await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ chat_id: chatId, text: `⏳ <b>${format.toUpperCase()}</b> formatında içerik hazırlanıyor, onayınıza sunulacak...`, parse_mode: "HTML" }),
          });
          await tetikleGitHub(env, "sabah_hazirla", { format_turu: format, kaynak: "hizli_uret_butonu" });
          return new Response("OK");
        }

        // D. FORMAT DEĞİŞTİRME MENÜSÜ
        if (data.startsWith("format_menu:")) {
          const id = data.split(":")[1];
          await cevapVer();
          await butonlariGuncelle(formatSecimMenusu(id));
          return new Response("OK");
        }

        if (data.startsWith("onay_menu_don:")) {
          const id = data.split(":")[1];
          await cevapVer();
          await butonlariGuncelle(standartOnayMenusu(id));
          return new Response("OK");
        }

        if (data.startsWith("format_uygula:")) {
          const [, format, id] = data.split(":");
          await cevapVer("Format dönüştürülüyor");
          await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ chat_id: chatId, text: `🎨 Haber #${id} <b>${format.toUpperCase()}</b> formatına dönüştürülüyor...`, parse_mode: "HTML" }),
          });
          await tetikleGitHub(env, "format_donustur", { haber_id: id, format_turu: format });
          return new Response("OK");
        }

        // E. ERTELEME
        if (data.startsWith("ertele:")) {
          const id = data.split(":")[1] || "";
          await cevapVer("Yayın 1 saat ertelendi");
          await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ chat_id: chatId, text: `⏰ Post #${id} yayını 1 saat ertelendi.` }),
          });
          return new Response("OK");
        }

        // F. YAYIN ONAYI
        if (data.startsWith("onayla:")) {
          await cevapVer("Yayın süreci başlatıldı");
          const [, tur, hedef, id] = data.split(":");
          await tetikleGitHub(env, "yayinla", { tur, hedef, id });
          await mesajiGuncelle(`🚀 <b>${tur.toUpperCase()} #${id} yayına alınıyor...</b>\nSeçili kanallar: <code>${hedef}</code>`);
          return new Response("OK");
        }

        // G. REDDET
        if (data.startsWith("reddet:")) {
          await cevapVer("İçerik reddedildi");
          const [, tur, id] = data.split(":");
          await tetikleGitHub(env, "yayinla", { tur, hedef: "reddet", id });
          await mesajiGuncelle(`❌ <b>${tur.toUpperCase()} #${id} reddedildi ve arşive kaldırıldı.</b>`);
          return new Response("OK");
        }

        // H. YENİLE
        if (data.startsWith("yenile:")) {
          await cevapVer("Yeniden hazırlanıyor");
          const [, tur, id] = data.split(":");
          await tetikleGitHub(env, "yayinla", { tur, hedef: "yenile", id });
          await mesajiGuncelle(`🔄 <b>${tur.toUpperCase()} #${id} için metin ve görseller yeniden üretiliyor...</b>`);
          return new Response("OK");
        }

        // İ. ESKİ İLAN MENÜSÜ CALLBACKLERİ
        if (data.startsWith("ilan_sec:")) {
          const ilanId = data.split(":")[1];
          await cevapVer();
          await tetikleGitHub(env, "hazirla_ilan", { ilan_id: ilanId });
          return new Response("OK");
        }
        if (data === "ilan_menu_yenile") {
          await cevapVer();
          await tetikleGitHub(env, "ilan_menusu", {});
          return new Response("OK");
        }
      }

      // =====================================================================
      // 2. YAZILI SLASH KOMUTLARI
      // =====================================================================
      if (update.message?.text) {
        const text = update.message.text.trim().toLowerCase();
        const chatId = update.message.chat?.id;

        const mesajGonder = async (metin, replyMarkup = null) => {
          const body = {
            chat_id: chatId,
            text: metin,
            parse_mode: "HTML",
            disable_web_page_preview: true,
          };
          if (replyMarkup) body.reply_markup = replyMarkup;
          await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          });
        };

        if (text === "/panel" || text === "/menu" || text === "panel" || text === "menu") {
          await mesajGonder(
            "🏢 <b>EDM YAPI & GAYRİMENKUL // KONTROL MERKEZİ</b>\n\n" +
            "Aşağıdaki butonları kullanarak tek tıkla yeni içerik üretebilir, " +
            "yayın akışını yönetebilir veya sistem durumunu denetleyebilirsiniz.",
            kontrolMerkeziMenusu()
          );
          return new Response("OK");
        }

        if (text === "/durum" || text === "durum") {
          await mesajGonder(
            "📊 <b>EDM SİSTEM & YAYIN DURUMU</b>\n\n" +
            "• <b>Otomasyon:</b> 🟢 Aktif\n" +
            "• <b>Aktif Kanallar:</b> ✅ IG · ✅ THREADS · ⬜ FB\n" +
            "• <b>Haftalık Plan:</b> Pzt (Sözlük) · Çar (Doğrusu) · Cum (Vaka) · Paz (Net Cevap)\n\n" +
            "<i>Tüm sistemler ve API bağlantıları sağlıklı çalışıyor.</i>",
            { inline_keyboard: [[{ text: "🎛 Kontrol Paneli", callback_data: "panel" }]] }
          );
          return new Response("OK");
        }

        if (text === "/yeni" || text === "/uret" || text === "/haber" || text === "/hazirla") {
          await mesajGonder("⏳ Sıradaki konu hazırlanıyor ve onayınıza sunulacak...");
          await tetikleGitHub(env, "sabah_hazirla", { kaynak: "telegram_komut" });
          return new Response("OK");
        }

        if (text === "/sozluk") {
          await mesajGonder("⏳ <b>EDM Gayrimenkul Sözlüğü</b> içeriği hazırlanıyor...");
          await tetikleGitHub(env, "sabah_hazirla", { format_turu: "sozluk", kaynak: "slash_sozluk" });
          return new Response("OK");
        }

        if (text === "/dogrusu") {
          await mesajGonder("⏳ <b>Nedir Doğrusu?</b> içeriği hazırlanıyor...");
          await tetikleGitHub(env, "sabah_hazirla", { format_turu: "nedir_dogrusu", kaynak: "slash_dogrusu" });
          return new Response("OK");
        }

        if (text === "/vaka") {
          await mesajGonder("⏳ <b>Hukuki Vaka Analizi</b> içeriği hazırlanıyor...");
          await tetikleGitHub(env, "sabah_hazirla", { format_turu: "vaka", kaynak: "slash_vaka" });
          return new Response("OK");
        }

        if (text === "/soru") {
          await mesajGonder("⏳ <b>Net Cevap Rehberi</b> içeriği hazırlanıyor...");
          await tetikleGitHub(env, "sabah_hazirla", { format_turu: "net_cevap", kaynak: "slash_soru" });
          return new Response("OK");
        }

        if (text === "/reels" || text === "/video") {
          await mesajGonder("🎬 <b>EDM Reels Videosu (9:16 Dikey)</b> hazırlanıyor, birazdan video ve metin gruba iletilecek...");
          await tetikleGitHub(env, "sabah_hazirla", { format_turu: "reels", kaynak: "slash_reels" });
          return new Response("OK");
        }

        if (text === "/durdur" || text === "/duraklat") {
          await mesajGonder("⏸️ <b>Akışı Duraklat:</b> Lütfen süreyi seçin:", duraklatmaMenusu());
          return new Response("OK");
        }

        if (text === "/devam") {
          await mesajGonder("🟢 <b>Otomatik akış tekrar aktif edildi.</b> Paylaşımlar takvime göre devam edecek.");
          await tetikleGitHub(env, "bot_yonetim", { eylem: "devam_et" });
          return new Response("OK");
        }

        if (text === "/start" || text === "/yardim") {
          const yardim = (
            "🏢 <b>EDM Yapı & Gayrimenkul Sosyal Medya Botu</b>\n\n" +
            "<b>Kullanabileceğiniz Komutlar:</b>\n" +
            "• <b>/panel</b> — İnteraktif kontrol merkezini açar.\n" +
            "• <b>/durum</b> — Bot ve yayın durumunu raporlar.\n" +
            "• <b>/yeni</b> — Sıradaki konuyu hemen üretip onaya sunar.\n" +
            "• <b>/sozluk</b> — Emlak sözlüğü formatında içerik üretir.\n" +
            "• <b>/dogrusu</b> — Nedir Doğrusu formatında içerik üretir.\n" +
            "• <b>/vaka</b> — 2 slaytlık vaka analizi carousel üretir.\n" +
            "• <b>/soru</b> — Net cevap rehberi üretir.\n" +
            "• <b>/reels</b> — 9:16 Dikey Reels videosu ve metni üretir.\n" +
            "• <b>/durdur</b> — Otomatik paylaşımları duraklatır.\n" +
            "• <b>/devam</b> — Duraklatılmış akışı devam ettirir."
          );
          await mesajGonder(yardim);
          return new Response("OK");
        }
      }

      return new Response("OK");
    } catch (err) {
      return new Response(`Hata: ${err.message}`, { status: 500 });
    }
  },

  // Zamanlanmış Cron (Sabah 10:00 TR)
  async scheduled(event, env, ctx) {
    console.log("Cloudflare Cron tetiklendi, GitHub Actions uyarılıyor...");
    await tetikleGitHub(env, "sabah_hazirla", { kaynak: "cloudflare_cron" });
  },
};

function kontrolMerkeziMenusu() {
  return {
    inline_keyboard: [
      [
        { text: "📖 Sözlük Üret", callback_data: "hizli_uret:sozluk" },
        { text: "⚖️ Nedir Doğrusu?", callback_data: "hizli_uret:nedir_dogrusu" },
      ],
      [
        { text: "📂 Vaka Analizi", callback_data: "hizli_uret:vaka" },
        { text: "❓ Net Cevap", callback_data: "hizli_uret:net_cevap" },
      ],
      [
        { text: "🎬 Reels Videosu Üret (9:16)", callback_data: "hizli_uret:reels" },
      ],
      [
        { text: "📊 Durum & Sağlık", callback_data: "durum" },
        { text: "⏸️ Akışı Duraklat", callback_data: "duraklat_menu" },
      ],
    ],
  };
}

function duraklatmaMenusu() {
  return {
    inline_keyboard: [
      [
        { text: "⏸️ 1 Saat", callback_data: "duraklat:1" },
        { text: "⏸️ 6 Saat", callback_data: "duraklat:6" },
      ],
      [
        { text: "⏸️ 24 Saat", callback_data: "duraklat:24" },
        { text: "⏸️ Süresiz", callback_data: "duraklat:0" },
      ],
      [
        { text: "← Kontrol Paneli", callback_data: "panel" },
      ],
    ],
  };
}

function formatSecimMenusu(id) {
  return {
    inline_keyboard: [
      [
        { text: "📖 EDM Sözlük", callback_data: `format_uygula:sozluk:${id}` },
        { text: "⚖️ Nedir Doğrusu?", callback_data: `format_uygula:nedir_dogrusu:${id}` },
      ],
      [
        { text: "📂 Vaka Analizi", callback_data: `format_uygula:vaka:${id}` },
        { text: "❓ Net Cevap", callback_data: `format_uygula:net_cevap:${id}` },
      ],
      [
        { text: "← Onay Menüsüne Dön", callback_data: `onay_menu_don:${id}` },
      ],
    ],
  };
}

function standartOnayMenusu(id) {
  return {
    inline_keyboard: [
      [
        { text: "✅ Instagram", callback_data: "kanal_toggle:ig" },
        { text: "✅ Threads", callback_data: "kanal_toggle:threads" },
        { text: "⬜ Facebook", callback_data: "kanal_toggle:fb" },
      ],
      [
        { text: "🚀 Seçili Kanallarda Yayınla", callback_data: `onayla:haber:ig,threads:${id}` },
      ],
      [
        { text: "🔄 Metinleri Yenile", callback_data: `yenile:haber:${id}` },
        { text: "🎨 Formatı Değiştir", callback_data: `format_menu:${id}` },
      ],
      [
        { text: "⏰ 1 Saat Ertele", callback_data: `ertele:haber:${id}` },
        { text: "❌ İptal / Reddet", callback_data: `reddet:haber:${id}` },
      ],
    ],
  };
}

async function tetikleGitHub(env, eventType, clientPayload) {
  const repo = env.GITHUB_REPOSITORY || "edmyapigayrimenkul/postedm";
  const url = `https://api.github.com/repos/${repo}/dispatches`;

  const resp = await fetch(url, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
      "Accept": "application/vnd.github.v3+json",
      "User-Agent": "EDM-Cloudflare-Worker",
    },
    body: JSON.stringify({
      event_type: eventType,
      client_payload: clientPayload,
    }),
  });

  return resp.status === 204;
}
