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
      // Parametreler kullanıcı kontrolünde: kaçışsız basılırsa yansıtmalı XSS olur.
      const code = htmlKacis(reqUrl.searchParams.get("code") || "");
      const error = htmlKacis(reqUrl.searchParams.get("error_description") || reqUrl.searchParams.get("error") || "");
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

    // Site Paylaşım Kuyruğu API'si (/api/postedm/kuyruk)
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

      // GÜVENLİK: yalnızca izinli sohbetler komut verebilir.
      // secret_token isteğin Telegram'dan geldiğini kanıtlar, KİMİN yazdığını değil.
      // Bu kontrol yokken bota özelden yazan herhangi biri /finans ile onaysız
      // yayın, /sil ile geri alınamaz silme tetikleyebiliyordu.
      // Liste boşsa hiçbir komut çalışmaz (fail-closed).
      const gelenSohbet = update.callback_query?.message?.chat?.id ?? update.message?.chat?.id;
      if (!sohbetIzinliMi(env, gelenSohbet)) {
        if (update.callback_query) await callbackYanitla(env, update.callback_query.id, "Yetkisiz");
        // 200 dönülür: 4xx/5xx'te Telegram aynı güncellemeyi tekrar tekrar yollar.
        return new Response("OK");
      }

      // Mesaj silme yardımcısı (Telegram deleteMessage)
      const mesajiSil = async (cId, mId) => {
        try {
          await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/deleteMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ chat_id: cId, message_id: mId }),
          });
        } catch (e) {
          // sessizce yoksay
        }
      };

      // =====================================================================
      // 1. BUTON TIKLAMALARI (CALLBACK QUERY)
      // =====================================================================
      if (update.callback_query) {
        const cb = update.callback_query;

        const data = cb.data || "";
        const chatId = cb.message?.chat?.id;
        const messageId = cb.message?.message_id;
        const callbackId = cb.id;

        // Mesaj metni veya fotoğraf/video caption'ından içerik ID'sini (#123) çıkaran yardımcı
        const icerikIdBul = () => {
          const metin = cb.message?.text || cb.message?.caption || "";
          const m = metin.match(/#(\d+)/);
          return m ? m[1] : "";
        };

        // Telegram'a bekleme simgesini kaldırması için hızlı yanıt ver
        const cevapVer = async (metin = "İşlem alınıyor...") => {
          await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ callback_query_id: callbackId, text: metin }),
          });
        };

        // Mesajı güncelleme yardımcısı (Telegram parse hatalarına karşı dayanıklı)
        const mesajiGuncelle = async (metin, replyMarkup = null) => {
          const body = {
            chat_id: chatId,
            message_id: messageId,
            text: metin,
            parse_mode: "HTML",
            disable_web_page_preview: true,
          };
          if (replyMarkup) body.reply_markup = replyMarkup;
          try {
            const r = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageText`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(body),
            });
            if (!r.ok) {
              // Parse hatası veya Telegram entity hatası olursa düz metne dönüştürerek kurtar
              delete body.parse_mode;
              body.text = metin.replace(/<[^>]+>/g, "");
              await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageText`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
              });
            }
          } catch (_) {}
        };

        // Butonları güncelleme yardımcısı
        const butonlariGuncelle = async (inlineKeyboard) => {
          const markup = Array.isArray(inlineKeyboard)
            ? { inline_keyboard: inlineKeyboard }
            : (inlineKeyboard && inlineKeyboard.inline_keyboard ? inlineKeyboard : { inline_keyboard: inlineKeyboard });
          try {
            await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageReplyMarkup`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                chat_id: chatId,
                message_id: messageId,
                reply_markup: markup,
              }),
            });
          } catch (_) {}
        };

        // A. KANAL TOGGLE BUTONLARI (ANINDA ARAYÜZ GÜNCELLEMESİ)
        if (data.startsWith("kanal:") || data.startsWith("kanal_toggle:")) {
          const hedefKanal = data.replace(/^(kanal:|kanal_toggle:)/, "");
          const keyboard = cb.message?.reply_markup?.inline_keyboard || [];
          let hedefSuAnSecili = false;
          for (let row of keyboard) {
            for (let btn of row) {
              if (btn.callback_data === `kanal:${hedefKanal}` || btn.callback_data === `kanal_toggle:${hedefKanal}`) {
                hedefSuAnSecili = btn.text.startsWith("✅");
              }
            }
          }
          const hedefYeniSecili = !hedefSuAnSecili;

          for (let row of keyboard) {
            for (let btn of row) {
              const buKanal = (btn.callback_data || "").replace(/^(kanal:|kanal_toggle:)/, "");
              if (btn.callback_data?.startsWith("kanal:") || btn.callback_data?.startsWith("kanal_toggle:")) {
                if (buKanal === hedefKanal) {
                  const label = btn.text.replace(/^[✅⬜]\s*/, "");
                  btn.text = `${hedefYeniSecili ? "✅" : "⬜"} ${label}`;
                } else if (hedefYeniSecili && hedefKanal === "reels" && buKanal === "ig") {
                  // Kural: Ya gönderi ya da Reels. Reels seçilince IG gönderi deaktif edilir.
                  const label = btn.text.replace(/^[✅⬜]\s*/, "");
                  btn.text = `⬜ ${label}`;
                } else if (hedefYeniSecili && hedefKanal === "ig" && buKanal === "reels") {
                  // Kural: IG gönderi seçilince Reels deaktif edilir.
                  const label = btn.text.replace(/^[✅⬜]\s*/, "");
                  btn.text = `⬜ ${label}`;
                }
              }
            }
          }

          // Güncel seçili kanallara göre klavyedeki diğer navigasyon butonlarının callback_data'sını senkronize et
          const guncelKanallar = seciliKanallariCikar(keyboard);
          const guncelKStr = kanallariKodla(guncelKanallar);

          for (const satir of keyboard) {
            for (const btn of satir) {
              const cd = btn.callback_data || "";
              if (cd.startsWith("kanal:") || cd.startsWith("kanal_toggle:")) continue;

              const szMatch = /^ses_zaman:(muzikli|muziksiz):(\d{1,2})(?::[a-z0-9_,]*)?$/.exec(cd);
              if (szMatch) {
                btn.callback_data = guncelKStr
                  ? `ses_zaman:${szMatch[1]}:${szMatch[2]}:${guncelKStr}`
                  : `ses_zaman:${szMatch[1]}:${szMatch[2]}`;
                continue;
              }

              const slMatch = /^slayt:([1-9]|10):(\d{1,2})(?::[a-z0-9_,]*)?$/.exec(cd);
              if (slMatch) {
                btn.callback_data = guncelKStr
                  ? `slayt:${slMatch[1]}:${slMatch[2]}:${guncelKStr}`
                  : `slayt:${slMatch[1]}:${slMatch[2]}`;
                continue;
              }

              const mMatch = /^(slayt_menu|yayin_menu|ses_menu|foto_menu|metin_menu|geri|yayin_geri|foto_geri|metin_geri):(\d{1,2})(?::[a-z0-9_,]*)?$/.exec(cd);
              if (mMatch) {
                btn.callback_data = guncelKStr
                  ? `${mMatch[1]}:${mMatch[2]}:${guncelKStr}`
                  : `${mMatch[1]}:${mMatch[2]}`;
                continue;
              }
            }
          }

          await butonlariGuncelle(keyboard);
          const kanalAdi = hedefKanalEtiketleri(hedefKanal);
          await cevapVer(hedefYeniSecili ? `✅ ${kanalAdi} seçildi` : `⬜ ${kanalAdi} kaldırıldı`);
          return new Response("OK");
        }

        // B. KONTROL PANELİ VE DURAKLATMA MENÜLERİ
        if (data === "panel" || data === "menu") {
          await cevapVer("🎛 Kontrol Paneli");
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
          await tetikle(env, chatId, "bot_yonetim", { eylem: "duraklat", saat: parseInt(saat, 10) });
          return new Response("OK");
        }

        if (data === "devam_et") {
          await cevapVer("Bot tekrar aktif");
          await mesajiGuncelle(
            "🟢 <b>OTOMATİK AKIŞ AKTİF EDİLDİ</b>\n\n" +
            "Otomatik paylaşımlar belirlenen günlerde sabah 10:00'da onaya sunulacaktır.",
            kontrolMerkeziMenusu()
          );
          await tetikle(env, chatId, "bot_yonetim", { eylem: "devam_et" });
          return new Response("OK");
        }

        if (data === "hatirlat_tetikle") {
          await cevapVer("Onaylar taranıyor");
          await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ chat_id: chatId, text: "⏰ Bekleyen onaylar taranıyor, onay bekleyen varsa hatırlatılacak..." }),
          });
          await tetikle(env, chatId, "hatirlat", { zorla: true });
          return new Response("OK");
        }

        // Önceki sürüm burada sabit "%100 sağlıklı çalışıyor" metni basıyordu —
        // metrikler sıfır yazarken ve CI kırmızıyken bile. Durum mesajı takvimi
        // anlatır; sağlık ve havuz gerçek veriden, Actions üzerinden gelir.
        if (data === "durum") {
          await cevapVer();
          await mesajiGuncelle(durumMetni(), {
            inline_keyboard: [[
              { text: "🩺 Canlı Sağlık Raporu", callback_data: "saglik_testi" },
              { text: "← Kontrol Paneli", callback_data: "panel" },
            ]],
          });
          return new Response("OK");
        }

        if (data === "saglik_testi") {
          await cevapVer("Rapor hazırlanıyor");
          await sohbeteGonder(env, chatId, SAGLIK_BEKLEME_METNI);
          await tetikle(env, chatId, "rapor", { kategori: "menu" });
          return new Response("OK");
        }

        if (data === "havuz_durum") {
          await cevapVer("Havuz sayılıyor");
          await tetikle(env, chatId, "bot_yonetim", { eylem: "havuz" });
          return new Response("OK");
        }

        if (data === "ayar" || data === "ayar_menu") {
          await cevapVer();
          await mesajiGuncelle(
            "⚙️ <b>EDM ÇALIŞMA VE YAYIN AYARLARI</b>\n\n" +
            "Aşağıdaki ayarları tek tıkla canlı olarak açıp kapatabilirsiniz:",
            ayarMenusu()
          );
          return new Response("OK");
        }

        if (data.startsWith("ayarsec:")) {
          const [_, key, val] = data.split(":");
          await cevapVer("Ayar güncellendi");
          const keyboard = cb.message?.reply_markup?.inline_keyboard || [];
          for (let row of keyboard) {
            for (let btn of row) {
              if (btn.callback_data?.startsWith(`ayarsec:${key}:`)) {
                const suAnAcik = btn.text.includes("✅");
                const yeniAcik = !suAnAcik;
                btn.text = btn.text.replace(/^[✅⬜]/, yeniAcik ? "✅" : "⬜");
                btn.callback_data = `ayarsec:${key}:${!yeniAcik}`;
              }
            }
          }
          await butonlariGuncelle(keyboard);
          await tetikle(env, chatId, "bot_yonetim", { eylem: "ayar_degistir", anahtar: key, deger: val });
          return new Response("OK");
        }

        if (data === "sonpostlar") {
          await cevapVer("Son postlar getiriliyor...");
          await tetikle(env, chatId, "bot_yonetim", { eylem: "sonpostlar", mesaj_id: messageId });
          return new Response("OK");
        }

        if (data.startsWith("incele:")) {
          const refId = data.split(":")[1];
          await cevapVer("İçerik inceleniyor...");
          await tetikle(env, chatId, "bot_yonetim", { eylem: "incele", id: refId, mesaj_id: messageId });
          return new Response("OK");
        }

        if (data.startsWith("yayin_kontrol:")) {
          const refId = data.split(":")[1];
          await cevapVer("Yayın kontrol ediliyor...");
          await tetikle(env, chatId, "bot_yonetim", { eylem: "yayin_kontrol", id: refId, mesaj_id: messageId });
          return new Response("OK");
        }

        if (data.startsWith("kurtar:")) {
          const refId = data.split(":")[1];
          await cevapVer("Tüm kanallar için kurtarılıyor...");
          await mesajiGuncelle(`🚀 <b>İçerik #${refId}</b> tüm kanallar için kurtarılıyor ve yayınlanıyor...`);
          await tetikle(env, chatId, "yayinla", { hedef: "hepsi", id: refId, mesaj_id: messageId });
          return new Response("OK");
        }

        if (data.startsWith("retry_kanal:")) {
          const [_, kanal, refId] = data.split(":");
          await cevapVer(`${kanal.toUpperCase()} için tekrar deneniyor...`);
          await mesajiGuncelle(`🔄 <b>İçerik #${refId}</b> için <b>${kanal.toUpperCase()}</b> yayını tekrarlanıyor...`);
          await tetikle(env, chatId, "yayinla", { hedef: kanal, id: refId, mesaj_id: messageId });
          return new Response("OK");
        }

        // Ham hata metni artık repodaki dosyadan değil DB'den (hata_kayitlari) okunur: eski yol data/son_hata.txt'yi
        // GitHub'dan çekiyordu, dosya .gitignore'da olduğu için HİÇ bulunamıyordu (2026-10-12). DB'ye Actions erişir,
        // Worker erişmez; bu yüzden diğer yönetim düğmeleri gibi bot_yonetim üzerinden gider (birkaç sn gecikir).
        if (data === "hata_ayrinti" || data === "hata:ayrinti") {
          await cevapVer("Hata detayı getiriliyor...");
          await tetikle(env, chatId, "bot_yonetim", { eylem: "hata_ayrinti" });
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
            await tetikle(env, chatId, "sabah_hazirla", { format_turu: "reels", kaynak: "hizli_uret_reels" });
            return new Response("OK");
          }
          if (format === "rotasyon") {
            await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ chat_id: chatId, text: `⏳ <b>Günün Gönderisi (Bilgilendirici Rotasyon)</b> hazırlanıyor, onayınıza sunulacak...`, parse_mode: "HTML" }),
            });
            await tetikle(env, chatId, "sabah_hazirla", { slot: "bilgilendirici", kaynak: "hizli_uret_rotasyon" });
            return new Response("OK");
          }
          if (format === "haber") {
            // Haber artık içerik üretmez, ÖNERİ düşürür (2026-09-24): içerik günde bir,
            // haber ondan bağımsız; hangisinin içeriğe çevrileceğine insan karar verir.
            await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ chat_id: chatId, text: `🌐 <b>Taze emlak haberleri</b> taranıyor; öneriler tarihleriyle birazdan düşecek...`, parse_mode: "HTML" }),
            });
            await tetikle(env, chatId, "haber_oneri", { kaynak: "hizli_uret_haber" });
            return new Response("OK");
          }
          await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ chat_id: chatId, text: `⏳ <b>${format.toUpperCase()}</b> formatında içerik hazırlanıyor, onayınıza sunulacak...`, parse_mode: "HTML" }),
          });
          await tetikle(env, chatId, "sabah_hazirla", { format_turu: format, kaynak: "hizli_uret_butonu" });
          return new Response("OK");
        }

        // C2. HABER ÖNERİSİ DÜĞMELERİ
        if (data === "noop") {
          await cevapVer("");
          return new Response("OK");
        }
        if (data.startsWith("haber_uret:")) {
          const haberId = data.split(":")[1];
          if (!/^\d+$/.test(haberId)) {
            await cevapVer("Geçersiz haber");
            return new Response("OK");
          }
          await cevapVer("İçerik hazırlanıyor");
          await butonlariGuncelle([[{ text: "⏳ İçeriğe çevriliyor…", callback_data: "noop" }]]);
          await tetikle(env, chatId, "haber_uret", { haber_id: haberId });
          return new Response("OK");
        }
        if (data.startsWith("haber_gec:")) {
          // Yalnızca düğmeler kalkar: kayıt zaten 'onerildi', bir daha önerilmez.
          // Bunun için bir Actions koşusu harcamaya gerek yok.
          await cevapVer("Geçildi");
          await butonlariGuncelle([[{ text: "✖ Geçildi", callback_data: "noop" }]]);
          return new Response("OK");
        }

        // C3. ÇOKLU HABER ÖNERİSİ — Instabot'un öneri taslağı (2026-09-26)
        // "sec:ID" bir başlığı işaretler/işareti kaldırır: GitHub'a GİTMEZ, Worker
        // düğmeleri doğrudan düzenler. Her seçimde Actions uyandırmak dakikalar sürerdi.
        // "hazirla_secilenler" işaretlilerin hepsini TEK dispatch ile gönderir; id'ler
        // düğmelerin callback_data'sından okunur, metinden değil.
        if (/^sec:\d{1,8}$/.test(data)) {
          const klavye = cb.message?.reply_markup?.inline_keyboard || [];
          let secili = 0;
          const yeni = klavye.map((satir) => satir.map((btn) => {
            const kopya = { ...btn };
            if (kopya.callback_data === data) {
              kopya.text = kopya.text.startsWith("✅") ? kopya.text.slice(1) : "✅" + kopya.text;
            }
            if (/^sec:\d{1,8}$/.test(String(kopya.callback_data || "")) && String(kopya.text || "").startsWith("✅")) {
              secili += 1;
            }
            return kopya;
          }));
          for (const satir of yeni) {
            for (const btn of satir) {
              if (btn.callback_data === "hazirla_secilenler") btn.text = `▶️ Hazırla (${secili})`;
            }
          }
          await butonlariGuncelle(yeni);
          await cevapVer("");
          return new Response("OK");
        }
        if (data === "hazirla_secilenler") {
          const klavye = cb.message?.reply_markup?.inline_keyboard || [];
          const idler = klavye.flat()
            .filter((b) => /^sec:\d{1,8}$/.test(String(b.callback_data || "")) && String(b.text || "").startsWith("✅"))
            .map((b) => b.callback_data.slice(4));
          if (idler.length === 0) {
            await cevapVer("Önce en az bir haber seç");
            return new Response("OK");
          }
          await cevapVer(`${idler.length} haber içeriğe çevriliyor`);
          await butonlariGuncelle([[{ text: `⏳ ${idler.length} haber sırayla içeriğe çevriliyor…`, callback_data: "noop" }]]);
          await tetikle(env, chatId, "haber_uret", { haber_id: idler.join(",") });
          return new Response("OK");
        }
        if (data === "oneri_gec") {
          // Kayıtlar zaten 'onerildi': bir daha önerilmez, Actions koşusu gerekmez
          await cevapVer("Geçildi");
          await butonlariGuncelle([[{ text: "✖ Bu turda haber seçilmedi", callback_data: "noop" }]]);
          return new Response("OK");
        }

        // D. MENÜ GEZİNMELERİ (ANINDA WORKER TARAFINDAN YÖNETİLİR)
        if (
          data.startsWith("yayin_menu:") || data.startsWith("yayin_geri:") ||
          data.startsWith("foto_menu:") || data.startsWith("foto_geri:") ||
          data.startsWith("metin_menu:") || data.startsWith("metin_geri:") ||
          data.startsWith("slayt_menu:") || data.startsWith("geri:") ||
          data.startsWith("format_menu:") || data.startsWith("onay_menu_don:") ||
          data.startsWith("slayt:") || data.startsWith("ses_menu:") || data.startsWith("ses_zaman:")
        ) {
          const parts = data.split(":");
          const kok = parts[0];
          const adet = parseInt(parts[parts.length - 1] || "2", 10) || 2;
          const klavye = cb.message?.reply_markup?.inline_keyboard || [];
          const seciliKanallar = seciliKanallariCikar(klavye);

          let yeniMenu;
          if (kok === "slayt") {
            const sira = parseInt(parts[1] || "1", 10) || 1;
            yeniMenu = slaytIslemMenusu(sira, adet, seciliKanallar);
          } else if (kok === "yayin_menu") {
            yeniMenu = yayinZamaniMenusu(adet, seciliKanallar);
          } else if (kok === "ses_menu") {
            yeniMenu = sesMenusu(adet, seciliKanallar);
          } else if (kok === "ses_zaman") {
            yeniMenu = sesliYayinZamaniMenusu(parts[1] === "muziksiz" ? "muziksiz" : "muzikli", adet, seciliKanallar);
          } else if (kok === "foto_menu") {
            yeniMenu = fotoMenusu(adet, seciliKanallar);
          } else if (kok === "metin_menu") {
            yeniMenu = metinMenusu(adet, seciliKanallar);
          } else if (kok === "slayt_menu" || kok === "format_menu") {
            yeniMenu = slaytSecimMenusu(adet, seciliKanallar);
          } else {
            yeniMenu = anaMenu(adet, seciliKanallar);
          }
          await butonlariGuncelle(yeniMenu);
          await cevapVer();
          return new Response("OK");
        }

        // E. YAYINLA AKSİYONU
        if (data === "yayinla" || data.startsWith("yayinla_sonra:") || data.startsWith("onayla:") ||
            data.startsWith("yayinla_ses:") || data.startsWith("yayinla_ses_sonra:")) {
          const klavye = cb.message?.reply_markup?.inline_keyboard || [];
          const secili = seciliKanallariCikar(klavye);
          const sesli = data.startsWith("yayinla_ses");
          const sesModu = sesli ? data.split(":")[1] : null;

          // Sıfır kanal seçimi koruması
          if (secili && secili.length === 0 && !data.startsWith("onayla:")) {
            await cevapVer("⚠️ En az bir yayın kanalı seçmelisin!");
            return new Response("OK");
          }
          if (sesli && !["muzikli", "muziksiz"].includes(sesModu)) {
            await cevapVer("Geçersiz seçim");
            return new Response("OK");
          }
          // Seslendirme yalnızca videoya uygulanır: video kanalı yoksa sesli yayın anlamsız
          if (sesli && !secili.some((k) => ["reels", "facebook", "youtube", "tiktok"].includes(k))) {
            await cevapVer("🎙️ Sesli yayın için en az bir video kanalı seç (Reels, FB, YT, TT)");
            return new Response("OK");
          }

          const msgMetin = cb.message?.text || cb.message?.caption || "";
          const isIlan = /PORTFÖY|İLAN/i.test(msgMetin);
          let isReels = secili.includes("reels");
          let tur = isIlan ? "ilan" : (isReels ? "reels" : "haber");
          let hedef = secili.join(",") + (sesli ? `,ses_${sesModu}` : "");
          let icerikId = "";

          if (data.startsWith("onayla:")) {
            // Örn: onayla:ilan:hepsi:123 veya onayla:123
            const parts = data.split(":");
            if (parts.length >= 4) {
              tur = parts[1];
              hedef = parts[2] === "hepsi" ? "hepsi" : parts[2];
              icerikId = parts[3];
            } else if (parts.length === 2 && parts[1]) {
              icerikId = parts[1];
            }
          }

          if (!icerikId) {
            icerikId = icerikIdBul();
          }

          const gecikme = data.startsWith("yayinla_sonra:") ? data.split(":")[1]
            : (data.startsWith("yayinla_ses_sonra:") ? data.split(":")[2] : null);

          const baslikEtiketi = tur === "reels" ? "Reels Videosu" : (tur === "ilan" ? "İlan Postu" : "İçerik");
          const kanallarStr = hedefKanalEtiketleri(hedef);
          const sesSatiri = sesli
            ? `\n\n🎙️ <b>Seslendirme:</b> ${sesModu === "muzikli" ? "fon müzikli" : "fon müziksiz"} (video kanallarında)`
            : "";

          // PLANLI YAYIN (2026-09-26). Eskiden gecikme GitHub'a HİÇ iletilmiyordu: mesaj
          // "30 dakika sonra" deyip yayını hemen yapıyordu. GitHub'da "N dakika sonra çalış"
          // yok; plan KV'ye yazılır ve 10 dakikalık Cloudflare cron'u (scheduled) vakti
          // gelince yayını tetikler. GitHub şimdi uyandırılmaz. Instabot'un deseni.
          if (gecikme) {
            const dakika = parseInt(gecikme, 10);
            // Tam kalıp: "yayinla_sonra:30:30" gibi bozuk girdi ikinci parçası yok sayılarak planlanmasın
            const kalip = sesli ? /^yayinla_ses_sonra:(?:muzikli|muziksiz):\d{1,3}$/ : /^yayinla_sonra:\d{1,3}$/;
            if (!kalip.test(data) || !PLAN_SURELERI.includes(dakika)) {
              await cevapVer("Geçersiz süre");
              return new Response("OK");
            }
            if (!env.PLANLAR) {
              await cevapVer("⚠️ Planlama şu an kullanılamıyor; '▶️ Şimdi' ile yayınlayın");
              return new Response("OK");
            }
            const an = new Date(Date.now() + dakika * 60000);
            const plan = {
              an: an.toISOString(),
              sohbet: chatId,
              adet: menuAdedi(klavye),
              secili,
              metin: cb.message?.text || "",
              payload: { tur, hedef, id: icerikId, mesaj_id: messageId },
            };
            try {
              await env.PLANLAR.put(`plan:${messageId}`, JSON.stringify(plan),
                { expirationTtl: dakika * 60 + PLAN_AZAMI_GECIKME_SN + 3600 });
            } catch (e) {
              await cevapVer("⚠️ Plan kaydedilemedi; '▶️ Şimdi' ile yayınlayın");
              return new Response("OK");
            }
            // Zaman içeriğe de yazılır: hatırlatıcı plan bekleyene "onay bekliyor" kartı atıp
            // bu mesajı (ve "Planı iptal et" düğmesini) silmesin. Yayını bu dispatch YAPMAZ.
            await tetikle(env, chatId, "yayinla", { tur, id: icerikId, hedef: "planla", an: an.toISOString() });
            await cevapVer(`⏰ TR ${trSaati(an)} için planlandı`);
            await mesajiGuncelle(
              `⏰ <b>${baslikEtiketi} Planlandı — TR ${trSaati(an)}</b>\n\n` +
              `İçerik <b>${dakika < 60 ? `${dakika} dakika` : `${dakika / 60} saat`} sonra</b> yayına alınacak ` +
              `(kontrol 10 dakikada bir: en geç TR ${trSaati(new Date(an.getTime() + 10 * 60000))}).\n\n` +
              `📡 <b>Hedef Kanallar:</b>\n${kanallarStr}${sesSatiri}`,
              { inline_keyboard: [[{ text: "⏹ Planı iptal et", callback_data: "plan_iptal" }]] },
            );
            return new Response("OK");
          }

          await cevapVer("Yayın süreci başlatıldı");
          await mesajiGuncelle(`🚀 <b>${baslikEtiketi} Yayına Alınıyor...</b>\n\nİçerik dağıtım motoru çalıştırıldı, yayın durumu birazdan güncellenecek.\n\n📡 <b>Hedef Kanallar:</b>\n${kanallarStr}${sesSatiri}`);
          await tetikle(env, chatId, "yayinla", {
            tur,
            hedef,
            id: icerikId,
            mesaj_id: messageId,
          });
          return new Response("OK");
        }

        // E2. PLANI İPTAL ET — plan KV'den silinir, onay menüsü seçilen kanallarla geri gelir
        if (data === "plan_iptal") {
          const ham = env.PLANLAR ? await env.PLANLAR.get(`plan:${messageId}`) : null;
          if (!ham) {
            await cevapVer("Bekleyen plan yok — yayınlanmış ya da iptal edilmiş olabilir");
            await butonlariGuncelle([]);
            return new Response("OK");
          }
          await env.PLANLAR.delete(`plan:${messageId}`);
          let plan = {};
          try { plan = JSON.parse(ham); } catch (_) {}
          await cevapVer("Plan iptal edildi");
          if (plan.payload?.id) {
            await tetikle(env, chatId, "yayinla", { tur: plan.payload.tur, id: plan.payload.id, hedef: "plan_iptal" });
          }
          await mesajiGuncelle(
            `⏹ <b>Yayın planı iptal edildi</b> — içerik onay bekliyor.\n\n${htmlKacis(plan.metin || "")}`.trim(),
            anaMenu(plan.adet || 2, Array.isArray(plan.secili) ? plan.secili : undefined),
          );
          return new Response("OK");
        }

        // F. MANUEL PAYLAŞIM PAKETİ
        if (data === "manuel_paket" || data.startsWith("manuel_paket:")) {
          const mId = (data.includes(":") ? data.split(":")[1] : "") || icerikIdBul();
          const msgMetin = cb.message?.text || cb.message?.caption || "";
          const isIlan = /PORTFÖY|İLAN/i.test(msgMetin);
          const tur = isIlan ? "ilan" : "haber";
          await cevapVer("Manuel paket hazırlanıyor...");
          await mesajiGuncelle(`📲 <b>Manuel Paylaşım Paketi Hazırlanıyor...</b>\n\nAçıklama metni, etiketler ve yönlendirme paneli birazdan gruba sunulacak.`);
          await tetikle(env, chatId, "yayinla", { tur: tur, id: mId, hedef: "manuel_paket", mesaj_id: messageId });
          return new Response("OK");
        }

        // --- "İşleniyor" butonuna basılırsa kullanıcıyı bilgilendir ---
        if (data === "isleniyor") {
          await cevapVer("⏳ İşlem devam ediyor, lütfen bekleyin…");
          return new Response("OK");
        }

        // --- Kurtar: Worker onay menüsünü ve butonları anında geri yükler ---
        if (data.startsWith("kurtar_menu:") || data.startsWith("menu_kurtar:")) {
          const parts = data.split(":");
          const adet = parseInt(parts[1] || "2", 10) || 2;
          const klavye = cb.message?.reply_markup?.inline_keyboard || [];
          const secili = seciliKanallariCikar(klavye);
          let temizMetin = (cb.message?.text || cb.message?.caption || "").replace(/^⏳[^\n]*\n\n/, "");
          await mesajiGuncelle(temizMetin || "EDM Günlük Onay Menüsü", anaMenu(adet, secili));
          await cevapVer("✅ Menü geri yüklendi");
          return new Response("OK");
        }

        // G. METİN DÜZENLEME EYLEMLERİ
        if (data === "metin_ozetle" || data === "metin_detaylandir" || data === "metin_yenile" || data.startsWith("metin_eylem:") || data.startsWith("yenile:")) {
          const eylem = data.startsWith("metin_eylem:") ? data.split(":")[1] : (data.startsWith("yenile:") ? "yenile" : data);
          const mId = (data.startsWith("yenile:") && data.split(":").length > 2 ? data.split(":")[2] : "") || icerikIdBul();
          const msgMetin = cb.message?.text || cb.message?.caption || "";
          const isIlan = /PORTFÖY|İLAN/i.test(msgMetin);
          const tur = isIlan ? "ilan" : "haber";
          const etiket = eylemEtiketi(eylem);
          await cevapVer(`${etiket} hazırlanıyor...`);
          await mesajiGuncelle(
            `✍️ <b>Metin Düzenleniyor: ${etiket}</b>\n\nYapay zeka metni yeniden işliyor, lütfen bekleyin...`,
            {
              inline_keyboard: [
                [{ text: `⏳ ${etiket} İşleniyor…`, callback_data: "isleniyor" }],
                [{ text: "↩️ Menüyü Geri Getir", callback_data: "kurtar_menu:2" }],
              ],
            }
          );
          await tetikle(env, chatId, "yayinla", { tur: tur, hedef: eylem, id: mId, mesaj_id: messageId });
          return new Response("OK");
        }

        // H. FOTOĞRAF EYLEMLERİ
        if (data.startsWith("gorsel_sec:")) {
          const parts = data.split(":");
          const adayNo = parts[1];
          const fId = parts.length > 3 ? parts[3] : (parts.length > 2 ? parts[2] : icerikIdBul());
          await cevapVer(`${adayNo}. aday uygulanıyor...`);
          await mesajiGuncelle(
            `🎨 <b>${adayNo}. Görsel Adayı Seçildi</b>\n\nİçeriğe uygulanıyor ve slaytlar yeniden çiziliyor...`,
            {
              inline_keyboard: [
                [{ text: `⏳ Görsel Uygulanıyor…`, callback_data: "isleniyor" }],
                [{ text: "↩️ Menüyü Geri Getir", callback_data: "kurtar_menu:2" }],
              ],
            }
          );
          await tetikle(env, chatId, "yayinla", { hedef: `gorsel_sec:${adayNo}`, id: fId, mesaj_id: messageId });
          return new Response("OK");
        }

        if (data === "foto_adaylar" || data.startsWith("foto_adaylar:")) {
          const fId = (data.includes(":") ? data.split(":")[1] : "") || icerikIdBul();
          await cevapVer("3 aday hazırlanıyor...");
          await mesajiGuncelle(
            `✨ <b>3 Alternatif Görsel Adayı Hazırlanıyor...</b>\n\nBirazdan albüm olarak sunulacak, dilediğinizi tek tıkla seçebileceksiniz.`,
            {
              inline_keyboard: [
                [{ text: `⏳ Adaylar Hazırlanıyor…`, callback_data: "isleniyor" }],
                [{ text: "↩️ Menüyü Geri Getir", callback_data: "kurtar_menu:2" }],
              ],
            }
          );
          await tetikle(env, chatId, "yayinla", { hedef: "foto_adaylar", id: fId, mesaj_id: messageId });
          return new Response("OK");
        }

        if (data === "foto_gercek" || data === "foto_stok" || data === "foto_ai" || data === "foto_editoryal" || data === "foto_ilk" || data.startsWith("foto_eylem:")) {
          const eylem = data.startsWith("foto_eylem:") ? data.split(":")[1] : data;
          const fId = icerikIdBul();
          const etiket = eylemEtiketi(eylem);
          await cevapVer(`${etiket} uygulanıyor...`);
          await mesajiGuncelle(
            `🖼️ <b>Görsel Güncelleniyor: ${etiket}</b>\n\nSeçilen görsel stiline göre slaytlar yeniden çiziliyor...`,
            {
              inline_keyboard: [
                [{ text: `⏳ Görsel Hazırlanıyor…`, callback_data: "isleniyor" }],
                [{ text: "↩️ Menüyü Geri Getir", callback_data: "kurtar_menu:2" }],
              ],
            }
          );
          await tetikle(env, chatId, "yayinla", { hedef: eylem, id: fId, mesaj_id: messageId });
          return new Response("OK");
        }

        // I. FORMAT DÖNÜŞTÜRME
        if (data.startsWith("format_uygula:")) {
          const parts = data.split(":");
          const format = parts[1];
          const fmtId = (parts.length > 2 ? parts[2] : "") || icerikIdBul();
          const fEtiket = formatEtiketi(format);
          await cevapVer(`${fEtiket} formatına dönüştürülüyor...`);
          await mesajiGuncelle(
            `🎨 <b>Format Dönüştürülüyor: ${fEtiket}</b>\n\nİçerik yeni şablon ve tasarım kurallarına göre yeniden derleniyor...`,
            {
              inline_keyboard: [
                [{ text: `⏳ Format Çiziliyor…`, callback_data: "isleniyor" }],
                [{ text: "↩️ Menüyü Geri Getir", callback_data: "kurtar_menu:2" }],
              ],
            }
          );
          await tetikle(env, chatId, "format_donustur", { format_turu: format, id: fmtId, haber_id: fmtId, mesaj_id: messageId });
          return new Response("OK");
        }

        // J. ERTELEME
        if (data === "ertele" || data.startsWith("ertele:")) {
          const ertId = icerikIdBul();
          const msgMetin = cb.message?.text || cb.message?.caption || "";
          const isIlan = /PORTFÖY|İLAN/i.test(msgMetin);
          const tur = isIlan ? "ilan" : "haber";
          await cevapVer("Yayın 1 saat ertelendi");
          await mesajiGuncelle(
            `⏰ <b>Yayın 1 Saat Ertelendi</b>\n\n` +
            `İçerik onay kuyruğunda korunmaktadır. Hatırlatıcılar 1 saat boyunca sessize alındı.`,
            {
              inline_keyboard: [
                [{ text: "🚀 Şimdi Yayına Al", callback_data: "yayinla" }],
                [{ text: "↩️ Menüyü Göster", callback_data: "kurtar_menu:2" }],
              ],
            }
          );
          await tetikle(env, chatId, "yayinla", { tur: tur, hedef: "ertele", id: ertId, mesaj_id: messageId });
          return new Response("OK");
        }

        // K. İPTAL / ATLA (HAVUZA DÖNER)
        if (data === "iptal" || data.startsWith("reddet:")) {
          await cevapVer("İçerik atlandı, konu havuza iade edildi");
          await mesajiGuncelle(`❌ <b>Bu İçerik Atlandı</b>\n\n<i>Konu havuza iade edildi. Sıradaki içerik rotasyonu hazırlanıyor...</i>`);
          let tur = "haber";
          let refId = "";
          if (data.startsWith("reddet:")) {
            const parts = data.split(":");
            if (parts.length >= 3) {
              tur = parts[1];
              refId = parts[2];
            } else if (parts.length === 2) {
              refId = parts[1];
            }
          }
          if (!refId) refId = icerikIdBul();
          const msgMetin = cb.message?.text || cb.message?.caption || "";
          if (/PORTFÖY|İLAN/i.test(msgMetin)) tur = "ilan";
          await tetikle(env, chatId, "yayinla", { tur, id: refId, hedef: "iptal", mesaj_id: messageId });
          return new Response("OK");
        }

        // L. ÇÖPE AT (TASLAK ÇÖPE ATILIR, KULLANICI İSTEĞİYLE KONU KİLİTLENMEZ)
        if (data === "cope_at" || data.startsWith("cope_at:")) {
          const copId = (data.includes(":") ? data.split(":")[1] : "") || icerikIdBul();
          const msgMetin = cb.message?.text || cb.message?.caption || "";
          const isIlan = /PORTFÖY|İLAN/i.test(msgMetin);
          const tur = isIlan ? "ilan" : "haber";
          await cevapVer("Taslak çöpe atıldı");
          await mesajiGuncelle(
            `🗑️ <b>Taslak Çöpe Atıldı</b>\n\n<i>İçerik silindi, konu havuza iade edildi.</i>`,
            { inline_keyboard: [[{ text: "🎛 Kontrol Paneli", callback_data: "panel" }]] }
          );
          await tetikle(env, chatId, "yayinla", { tur: tur, hedef: "cope_at", id: copId, mesaj_id: messageId });
          return new Response("OK");
        }

        // L1. MESAJI SİL (TELEGRAM KARTINI VE ALBÜM SLAYTLARINI ANINDA TEMİZLE)
        if (data === "mesaji_sil" || data.startsWith("mesaji_sil:")) {
          await cevapVer("🗑️ Mesaj siliniyor...");
          await mesajiSil(chatId, messageId);
          for (let delta = 1; delta <= 6; delta++) {
            await mesajiSil(chatId, messageId - delta);
          }
          await tetikle(env, chatId, "bot_yonetim", { eylem: "mesaj_sil", mesaj_id: messageId });
          return new Response("OK");
        }

        // L2. YAYINDAN KALDIR (SOSYAL MEDYA YAYINLARINI GERİ ALMA)

        if (data === "kaldir" || data.startsWith("kaldir:")) {
          let tur = "haber";
          let refId = "";
          const parts = data.split(":");
          if (parts.length === 3) {
            tur = parts[1];
            refId = parts[2];
          } else if (parts.length === 2) {
            if (/^\d+$/.test(parts[1])) {
              refId = parts[1];
            } else {
              tur = parts[1];
            }
          }
          if (!refId) refId = icerikIdBul();
          if (!/^\d+$/.test(refId)) {
            await cevapVer("İçerik numarası bulunamadı");
            return new Response("OK");
          }
          // Geri alınamaz işlem: tek dokunuşla değil, ayrı bir onay mesajıyla yürür.
          // Orijinal rapor mesajı ve butonları olduğu gibi kalır.
          await cevapVer("Onay gerekiyor");
          await sohbeteGonder(env, chatId, kaldirmaOnayMetni(refId), kaldirmaOnayMenusu(tur, refId));
          return new Response("OK");
        }

        // L3. KALDIRMA ONAYI — yalnızca onay mesajındaki "Evet" butonu siler
        if (data.startsWith("kaldir_onay:")) {
          const [, tur, refId] = data.split(":");
          if (!/^(haber|reels|ilan)$/.test(tur || "") || !/^\d+$/.test(refId || "")) {
            await cevapVer("Geçersiz istek");
            return new Response("OK");
          }
          await cevapVer("Yayından kaldırma başlatıldı");
          await mesajiGuncelle(`🗑️ <b>İçerik #${refId} yayından kaldırılıyor...</b>\n<i>Facebook ve Threads'ten siliniyor; Instagram için ayrı talimat gelecek.</i>`);
          await tetikle(env, chatId, "yayinla", { tur, id: refId, hedef: "kaldir", mesaj_id: messageId });
          return new Response("OK");
        }

        if (data === "kaldir_vazgec") {
          await cevapVer("Vazgeçildi");
          await mesajiGuncelle("↩️ <b>Kaldırma iptal edildi.</b> İçerik yayında kalmaya devam ediyor.");
          return new Response("OK");
        }

        // M. İLAN İŞLEMLERİ
        if (data.startsWith("ilan_sec:")) {
          const ilanId = data.split(":")[1];
          await cevapVer("İlan içeriği hazırlanıyor...");
          await mesajiGuncelle(`🏡 <b>İlan #${ilanId} Seçildi</b>\n\nÖzel carousel ve açıklama metni derleniyor, birazdan sunulacak...`);
          await tetikle(env, chatId, "hazirla_ilan", { ilan_id: ilanId });
          return new Response("OK");
        }
        if (data === "ilan_menu_yenile") {
          await cevapVer("İlan listesi güncelleniyor...");
          await tetikle(env, chatId, "ilan_menusu", {});
          return new Response("OK");
        }

        // N. SLAYT DETAY VE SIRALAMA EYLEMLERİ
        if (
          data.startsWith("slayt_basa:") || data.startsWith("slayt_yukari:") ||
          data.startsWith("slayt_asagi:") || data.startsWith("slayt_sil:") ||
          data.startsWith("slayt_carpici:") || data.startsWith("slayt_uzat:") ||
          data.startsWith("slayt_kisalt:")
        ) {
          const [eylem, sira] = data.split(":");
          const etiket = eylemEtiketi(eylem);
          await cevapVer(`${sira}. Slayt: ${etiket}`);
          await mesajiGuncelle(`⏳ <b>${sira}. Slayt Güncelleniyor: ${etiket}</b>\n\nLütfen bekleyin, slayt parametreleri işleniyor...`);
          await tetikle(env, chatId, "slayt_islem", {
            eylem,
            sira: parseInt(sira, 10),
            mesaj_id: messageId,
          });
          return new Response("OK");
        }

        if (data.startsWith("slayt_elle:")) {
          const sira = data.split(":")[1];
          await cevapVer();
          await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: chatId,
              text: `✍️ <b>${sira}. slaytın başlığını düzenlemek için</b> bu mesaja yanıt (reply) vererek yeni başlığı yazın:\n\n<code>${sira}: Yeni Başlık Metni</code>\n\n<i>Başlık ve açıklamayı birlikte girmek için:</i>\n<code>${sira}: Yeni Başlık | Yeni Açıklama</code>`,
              parse_mode: "HTML",
            }),
          });
          return new Response("OK");
        }

        // O. YÖNETİM AKSİYONLARI (TEMİZLEME VE KOTA)
        if (data === "tur_temizle") {
          await cevapVer("Onaylar temizleniyor...");
          await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ chat_id: chatId, text: "🧹 Askıda bekleyen onaylar taranıp temizleniyor...", parse_mode: "HTML" }),
          });
          await tetikle(env, chatId, "bot_yonetim", { eylem: "tur_temizle" });
          return new Response("OK");
        }

        if (
          data === "kota_raporu" || data === "kota_goster" || data === "kota_tazele" ||
          data === "rapor_goster" || data === "rapor_tazele" || data === "kota_menu" ||
          data.startsWith("kota_kat:")
        ) {
          let kategori = "menu";
          if (data.startsWith("kota_kat:")) {
            kategori = data.split(":")[1];
          }
          await cevapVer("Kota bilgisi hazırlanıyor...");
          if (messageId) {
            await mesajiGuncelle("🔄 <b>Kota güncelleniyor...</b>\n<i>Bulut, yapay zeka ve sosyal medya kotaları taranıyor...</i>");
          }
          await tetikle(env, chatId, "rapor", { mesaj_id: messageId, kategori: kategori });
          return new Response("OK");
        }
      }

      // =====================================================================
      // 2. YAZILI SLASH KOMUTLARI
      // =====================================================================
      if (update.message?.text) {
        const rawText = update.message.text.trim();
        // Komut = ilk kelime ("@botadi" eki atılmış). Eşleşme HER ZAMAN tam kelimeyle:
        // eski startsWith("sil") kontrolü "Silivri 220 m2 arsa var" mesajını
        // #220'yi silme komutu sayıyordu.
        const kelimeler = rawText.split(/\s+/);
        const komut = (kelimeler[0] || "").split("@")[0].toLowerCase();
        const arguman = kelimeler.slice(1);
        const argumanMetni = rawText.replace(/^\S+\s*/, "");  // satır sonlarını korur
        const text = [komut, ...arguman.map((a) => a.toLowerCase())].join(" ");
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

        // --- Yanıtlanan Mesajlar (Reply) ---
        if (update.message.reply_to_message) {
          const replyId = update.message.reply_to_message.message_id;
          const userMsgId = update.message.message_id;
          const replyText = rawText.toLowerCase().trim();

          // Reply ile mesaj / onay silme
          if (replyText === "sil" || replyText === "/sil" || replyText === "iptal" || replyText === "/iptal") {
            await mesajiSil(chatId, userMsgId);
            await mesajiSil(chatId, replyId);
            for (let delta = 1; delta <= 6; delta++) {
              await mesajiSil(chatId, replyId - delta);
            }
            await tetikle(env, chatId, "bot_yonetim", { eylem: "mesaj_sil", mesaj_id: replyId });
            return new Response("OK");
          }

          // Reply ile sıfırdan yeniden üretme
          if (replyText === "yenile" || replyText === "/yenile" || replyText === "tekrar" || replyText === "/tekrar") {
            await mesajiSil(chatId, userMsgId);
            await mesajGonder("🔄 İçerik sıfırdan yeniden hazırlanıyor, lütfen bekleyin...");
            await tetikle(env, chatId, "yayinla", { hedef: "yenile", mesaj_id: replyId });
            return new Response("OK");
          }

          // Reply ile başlık/metin düzenleme
          if (update.message.reply_to_message?.from?.is_bot && duzenlemeSozdizimiMi(rawText)) {
            const replyMetin = rawText;
            const gonderen = update.message.from ? `${update.message.from.first_name || ""} ${update.message.from.username ? "@" + update.message.from.username : ""}`.trim() : "";

            await mesajGonder("✍️ Yeni metin işleniyor, slaytlar yeniden çiziliyor...");
            await tetikle(env, chatId, "metin_duzenle", {
              mesaj_id: replyId,
              metin: replyMetin,
              gonderen: gonderen,
            });
            return new Response("OK");
          }
        }


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
          await mesajGonder(durumMetni(), {
            inline_keyboard: [[
              { text: "🩺 Canlı Sağlık Raporu", callback_data: "saglik_testi" },
              { text: "🎛 Kontrol Paneli", callback_data: "panel" },
            ]],
          });
          return new Response("OK");
        }

        if (text === "/hatirlat" || text === "hatirlat") {
          await mesajGonder("⏰ Bekleyen onaylar taranıyor, onay bekleyen varsa hatırlatılacak...");
          await tetikle(env, chatId, "hatirlat", { zorla: true });
          return new Response("OK");
        }

        // /link <URL> — Web linkinden otorite postu üretir
        if (komut === "/link") {
          const url = argumanMetni.trim();
          if (!url.startsWith("http")) {
            await mesajGonder("⚠️ Lütfen geçerli bir web linki girin:\n<code>/link https://...</code>");
            return new Response("OK");
          }
          await mesajGonder(`🌐 <b>Link taranıyor ve özel içerik hazırlanıyor...</b>\n<code>${url.slice(0, 70)}...</code>`);
          await tetikle(env, chatId, "ozel_uret", { tur: "link", url });
          return new Response("OK");
        }

        // /ozel <metin> veya /konu <metin> — Serbest konudan içerik üretir
        if (komut === "/ozel" || komut === "/konu") {
          const metin = argumanMetni.trim();
          if (metin.length < 5) {
            await mesajGonder("⚠️ Lütfen üretmek istediğiniz konuyu yazın:\n<code>/ozel Hisseli tapuda şufa hakkı...</code>");
            return new Response("OK");
          }
          await mesajGonder(`✍️ <b>Özel konu için içerik hazırlanıyor...</b>\n<i>"${metin.slice(0, 100)}..."</i>`);
          await tetikle(env, chatId, "ozel_uret", { tur: "ozel", metin });
          return new Response("OK");
        }

        // /temizle — Askıda bekleyen onayları temizler
        if (text === "/temizle") {
          await mesajGonder("🧹 Askıda bekleyen onaylar temizleniyor...");
          await tetikle(env, chatId, "bot_yonetim", { eylem: "tur_temizle" });
          return new Response("OK");
        }

        // /mesaj_sil [sayi] — Son Telegram onay kartını ve albüm slaytlarını siler
        if (komut === "/mesaj_sil" || komut === "/sil_mesaj") {
          const userMsgId = update.message.message_id;
          await mesajiSil(chatId, userMsgId);
          const sayi = /^\d+$/.test(arguman[0]) ? parseInt(arguman[0], 10) : 5;
          const adet = Math.min(Math.max(sayi, 1), 15);
          for (let i = 1; i <= adet; i++) {
            await mesajiSil(chatId, userMsgId - i);
          }
          await tetikle(env, chatId, "bot_yonetim", { eylem: "son_mesaji_sil", adet: adet });
          return new Response("OK");
        }

        // /yenile, /tekrar — Son onay bekleyen içeriği sıfırdan yeniden üretir
        if (komut === "/yenile" || komut === "yenile" || komut === "/tekrar" || komut === "tekrar") {
          await mesajGonder("🔄 Son içerik sıfırdan yeniden hazırlanıyor, lütfen bekleyin...");
          await tetikle(env, chatId, "yayinla", { hedef: "yenile" });
          return new Response("OK");
        }

        // /kaldir ve /sil — Yayındaki içeriği sosyal medyadan geri alır (yalnızca / ile ve tek ID ile)
        if (komut === "/kaldir" || komut === "/sil") {
          const refId = arguman.length === 1 ? arguman[0] : "";
          if (/^\d+$/.test(refId)) {
            await mesajGonder(kaldirmaOnayMetni(refId), kaldirmaOnayMenusu("haber", refId));
          }
          return new Response("OK");
        }


        // /rapor, /kullanim, /kota — Detaylı sistem, GitHub Actions ve yapay zeka kota tablosu
        if (["/rapor", "rapor", "/kullanim", "kullanim", "/kota", "kota"].includes(komut)) {
          const parcalar = text.split(/\s+/);
          let kategori = "menu";
          if (parcalar.length > 1) {
            const p = parcalar[1];
            if (p === "1" || p === "bulut" || p === "api") kategori = "1";
            else if (p === "2" || p === "sosyal" || p === "yayin") kategori = "2";
          }
          await mesajGonder("📈 <b>Kota ve Sistem Durumu taranıyor...</b>\nBulut altyapısı, yapay zeka tokenları ve yayın limitleri alınıyor...");
          await tetikle(env, chatId, "rapor", { kategori: kategori });
          return new Response("OK");
        }

        if (text === "/gonderi" || text === "/yeni" || text === "/uret" || text === "/hazirla") {
          await mesajGonder("⏳ Günün konusu hazırlanıyor ve onayınıza sunulacak...");
          await tetikle(env, chatId, "sabah_hazirla", { slot: "bilgilendirici", kaynak: "telegram_komut" });
          return new Response("OK");
        }

        const haberUretMatch = text.match(/^\/(?:haber|haber_uret|haberden)(?:\s+|_)#?(\d+)$/i);
        if (haberUretMatch) {
          const haberId = haberUretMatch[1];
          await mesajGonder(`⏳ <b>Haber #${haberId}</b> içeriğe çevriliyor, onay kartı birazdan hazırlanacak...`);
          await tetikle(env, chatId, "haber_uret", { haber_id: haberId });
          return new Response("OK");
        }

        if (text === "/haber" || text === "/sondakika") {
          await mesajGonder("🌐 Taze emlak haberleri taranıyor; öneriler tarihleriyle birazdan düşecek...");
          await tetikle(env, chatId, "haber_oneri", { kaynak: "telegram_komut" });
          return new Response("OK");
        }

        if (text === "/sozluk") {
          await mesajGonder("⏳ <b>EDM Gayrimenkul Sözlüğü</b> içeriği hazırlanıyor...");
          await tetikle(env, chatId, "sabah_hazirla", { format_turu: "sozluk", kaynak: "slash_sozluk" });
          return new Response("OK");
        }

        if (text === "/dogrusu") {
          await mesajGonder("⏳ <b>Nedir Doğrusu?</b> içeriği hazırlanıyor...");
          await tetikle(env, chatId, "sabah_hazirla", { format_turu: "nedir_dogrusu", kaynak: "slash_dogrusu" });
          return new Response("OK");
        }

        if (text === "/vaka") {
          await mesajGonder("⏳ <b>Hukuki Vaka Analizi</b> içeriği hazırlanıyor...");
          await tetikle(env, chatId, "sabah_hazirla", { format_turu: "vaka", kaynak: "slash_vaka" });
          return new Response("OK");
        }

        if (text === "/soru") {
          await mesajGonder("⏳ <b>Net Cevap Rehberi</b> içeriği hazırlanıyor...");
          await tetikle(env, chatId, "sabah_hazirla", { format_turu: "net_cevap", kaynak: "slash_soru" });
          return new Response("OK");
        }

        if (text === "/reels" || text === "/video") {
          await mesajGonder("🎬 <b>EDM Reels Videosu (9:16 Dikey)</b> hazırlanıyor, birazdan video ve metin gruba iletilecek...");
          await tetikle(env, chatId, "sabah_hazirla", { format_turu: "reels", kaynak: "slash_reels" });
          return new Response("OK");
        }

        if (text === "/ilanlar" || text === "/ilan" || text === "ilanlar" || text === "ilan") {
          await mesajGonder("🏡 <b>Portföy İlan Menüsü</b> hazırlanıyor, birazdan gruba sunulacak...");
          await tetikle(env, chatId, "ilan_menusu", {});
          return new Response("OK");
        }

        if (text === "/saglik" || text === "/saglik_testi" || text === "saglik") {
          await mesajGonder(SAGLIK_BEKLEME_METNI);
          await tetikle(env, chatId, "rapor", { kategori: "menu" });
          return new Response("OK");
        }

        if (text === "/havuz" || text === "/havuz_durum" || text === "havuz") {
          await mesajGonder("📚 <b>Konu havuzu sayılıyor...</b>");
          await tetikle(env, chatId, "bot_yonetim", { eylem: "havuz" });
          return new Response("OK");
        }

        if (text === "/durdur" || text === "/duraklat") {
          await mesajGonder("⏸️ <b>Akışı Duraklat:</b> Lütfen süreyi seçin:", duraklatmaMenusu());
          return new Response("OK");
        }

        if (text === "/devam") {
          await mesajGonder("🟢 <b>Otomatik akış tekrar aktif edildi.</b> Paylaşımlar takvime göre devam edecek.");
          await tetikle(env, chatId, "bot_yonetim", { eylem: "devam_et" });
          return new Response("OK");
        }

        if (komut === "/arastir") {
          const metin = argumanMetni.trim();
          if (metin.length < 3) {
            await mesajGonder("⚠️ Lütfen araştırmak istediğiniz konuyu yazın:\n<code>/arastir 2026 tapu harcı muafiyeti şartları</code>");
            return new Response("OK");
          }
          await mesajGonder(`🔍 <b>Derin araştırma başlatıldı...</b>\n<i>"${metin.slice(0, 100)}..."</i>`);
          await tetikle(env, chatId, "ozel_uret", { tur: "arastir", metin });
          return new Response("OK");
        }

        if (komut === "/dosya" || komut === "/kronoloji") {
          const metin = argumanMetni.trim();
          if (metin.length < 3) {
            await mesajGonder("⚠️ Lütfen dosya konusunu yazın:\n<code>/dosya Kentsel Dönüşüm Hukuki Süreci</code>");
            return new Response("OK");
          }
          await mesajGonder(`📂 <b>Özel dosya ve süreç analizi hazırlanıyor...</b>\n<i>"${metin.slice(0, 100)}..."</i>`);
          await tetikle(env, chatId, "ozel_uret", { tur: "dosya", metin });
          return new Response("OK");
        }

        if (komut === "/incele" || komut === "incele" || komut.startsWith("/incele_")) {
          // Öneri listesindeki "/incele_272" dokunulabilir komut; haber önerisi mi içerik mi
          // ayrımını Python yapar (telegram_bot.icerik_incele_karti)
          const parcalar = komut.startsWith("/incele_") ? ["/incele", komut.slice("/incele_".length)] : text.split(/\s+/);
          if (parcalar.length > 1 && /^\d{1,8}$/.test(parcalar[1])) {
            await mesajGonder(`🔎 <b>#${parcalar[1]}</b> inceleniyor...`);
            await tetikle(env, chatId, "bot_yonetim", { eylem: "incele", id: parcalar[1] });
            return new Response("OK");
          }
          await mesajGonder("⚠️ Lütfen incelenecek ID'yi belirtin: <code>/incele 104</code>");
          return new Response("OK");
        }

        if (text === "/sonpostlar" || text === "/son_postlar" || text === "sonpostlar") {
          await mesajGonder("📰 <b>Son yayınlanan postlar</b> taranıyor...");
          await tetikle(env, chatId, "bot_yonetim", { eylem: "sonpostlar" });
          return new Response("OK");
        }

        if (komut === "/kurtar") {
          const parcalar = text.split(/\s+/);
          if (parcalar.length > 1 && /^\d+$/.test(parcalar[1])) {
            await mesajGonder(`🚀 <b>İçerik #${parcalar[1]}</b> tüm kanallar için kurtarılıyor ve yayınlanıyor...`);
            await tetikle(env, chatId, "yayinla", { hedef: "hepsi", id: parcalar[1] });
            return new Response("OK");
          }
          await mesajGonder("⚠️ Lütfen kurtarılacak ID'yi belirtin: <code>/kurtar 104</code>");
          return new Response("OK");
        }

        if (komut === "/yayin_kontrol") {
          const parcalar = text.split(/\s+/);
          if (parcalar.length > 1 && /^\d+$/.test(parcalar[1])) {
            await mesajGonder(`📡 <b>İçerik #${parcalar[1]}</b> için yayın durumu kontrol ediliyor...`);
            await tetikle(env, chatId, "bot_yonetim", { eylem: "yayin_kontrol", id: parcalar[1] });
            return new Response("OK");
          }
          await mesajGonder("⚠️ Lütfen kontrol edilecek ID'yi belirtin: <code>/yayin_kontrol 104</code>");
          return new Response("OK");
        }

        if (text === "/ayar" || text === "/ayarlar" || text === "ayar") {
          await mesajGonder(
            "⚙️ <b>EDM ÇALIŞMA VE YAYIN AYARLARI</b>\n\n" +
            "Aşağıdaki ayarları tek tıkla canlı olarak açıp kapatabilirsiniz:",
            ayarMenusu()
          );
          return new Response("OK");
        }

        if (text === "/start" || text === "/yardim") {
          const yardim = (
            "🏢 <b>EDM Yapı & Gayrimenkul Sosyal Medya Botu</b>\n\n" +
            "<b>✍️ İÇERİK ÜRET & ARAŞTIR:</b>\n" +
            "• <b>/gonderi</b> — Günün konusundan onaylı post üretir (Rotasyon).\n" +
            "• <b>/reels</b> — 9:16 Dikey Reels videosu ve metni üretir.\n" +
            "• <b>/arastir &lt;konu&gt;</b> — Derin mevzuat araştırması ve post üretir.\n" +
            "• <b>/dosya &lt;konu&gt;</b> — Kronolojik dosya ve süreç analizi üretir.\n" +
            "• <b>/link &lt;url&gt;</b> — Web linkinden otorite postu üretir.\n" +
            "• <b>/ozel &lt;metin&gt;</b> — Serbest duyuru/konudan post üretir.\n" +
            "• <b>/haber</b> — Taze sektörel haber tara ve post üret.\n" +
            "• <b>/sozluk</b> — Emlak sözlüğü formatında içerik üretir.\n" +
            "• <b>/dogrusu</b> — Nedir Doğrusu formatında içerik üretir.\n" +
            "• <b>/vaka</b> — 2 slaytlık vaka analizi carousel üretir.\n" +
            "• <b>/soru</b> — Net cevap rehberi üretir.\n" +
            "• <b>/ilanlar</b> — Portföyden ilan seçip yayınlama menüsünü açar.\n\n" +
            "<b>📊 AKIŞ, İNCELEME & RAPOR:</b>\n" +
            "• <b>/sonpostlar</b> — Son paylaşılan 5 postu listeler.\n" +
            "• <b>/incele &lt;id&gt;</b> — Post detaylarını ve slayt metinlerini inceler.\n" +
            "• <b>/kurtar &lt;id&gt;</b> — Aksayan yayını tüm kanallara kurtarır.\n" +
            "• <b>/durum</b> — Bot ve yayın durumunu raporlar.\n" +
            "• <b>/rapor</b> — GitHub Actions, yapay zeka ve sistem kota tablosu.\n" +
            "• <b>/havuz</b> — Konu bankası havuz durumunu gösterir.\n\n" +
            "<b>🎛 YÖNETİM & AYARLAR:</b>\n" +
            "• <b>/panel</b> — İnteraktif kontrol merkezini açar.\n" +
            "• <b>/ayar</b> — Çalışma ayarlarını canlı düzenler.\n" +
            "• <b>/hatirlat</b> — Onay bekleyen paylaşımları anında tarar.\n" +
            "• <b>/temizle</b> — Askıda bekleyen onayları temizler.\n" +
            "• <b>/saglik</b> — API ve sistem bağlantı sağlık testi.\n" +
            "• <b>/durdur</b> — Otomatik paylaşımları duraklatır.\n" +
            "• <b>/devam</b> — Duraklatılmış akışı devam ettirir."
          );
          await mesajGonder(yardim);
          return new Response("OK");
        }
      }

      return new Response("OK");
    } catch (err) {
      // 200 dönülür: 5xx'te Telegram güncellemeyi yeniden yollar ve aynı
      // dispatch (ör. yayınla) ikinci kez tetiklenir. Hata log'a ve gruba gider.
      console.error("Webhook hatası:", err?.stack || err);
      await bildirimGonder(env, `⚠️ <b>Worker hatası:</b> <code>${htmlKacis(String(err?.message || err)).slice(0, 300)}</code>`);
      return new Response("OK");
    }
  },

  // Zamanlanmış cron'lar (wrangler.toml › triggers):
  //  • */10 * * * *   planlı yayın çalar saati
  //  • 0 7 * * *      10:00 TR günlük bilgilendirici içerik   → slot_hazirla {slot: bilgilendirici}
  //  • 30 9 * * *     12:30 TR günlük sözlük kartı            → slot_hazirla {slot: sozluk}
  // Günlük tur ASIL olarak buradan tetiklenir (2026-10-12): GitHub `schedule` koşuları 6-10 saat gecikiyordu.
  // hazirla.yml'deki aynı saatli cron'lar gecikmeli YEDEKTİR; `zamanli: true` yükü hazirla.py'ye "zamanlanmış koşu"
  // der (duraklatma uyulur) ve aynı slot aynı günde ikinci kez üretilmez (bkz. test_tek_tetikleyici_kurali).
  async scheduled(event, env, ctx) {
    if (event.cron === PLAN_CRON) {
      if (env.PLANLAR) await planlariIsle(env);
      return;
    }
    const slot = GUNLUK_TURLAR[event.cron];
    if (slot) await gunlukTuruTetikle(env, slot, event.cron);
  },
};

function ayarMenusu(ayarlar = {}) {
  const v = (k, d = true) => (ayarlar[k] !== undefined ? ayarlar[k] : d);
  return {
    inline_keyboard: [
      [{ text: `${v('oto_yayin', true) ? '✅ AÇIK' : '⬜ KAPALI'} 🌙 Otomatik Yayın`, callback_data: `ayarsec:oto_yayin:${!v('oto_yayin', true)}` }],
      [{ text: `${v('hatirlatici', true) ? '✅ AÇIK' : '⬜ KAPALI'} ⏰ Onay Hatırlatıcı`, callback_data: `ayarsec:hatirlatici:${!v('hatirlatici', true)}` }],
      [{ text: `${v('reels_varsayilan', false) ? '✅ AÇIK' : '⬜ KAPALI'} 🎬 Varsayılan Reels Modu`, callback_data: `ayarsec:reels_varsayilan:${!v('reels_varsayilan', false)}` }],
      [{ text: `${v('kanal_threads', true) ? '✅ AÇIK' : '⬜ KAPALI'} 🧵 Threads Paylaşımı`, callback_data: `ayarsec:kanal_threads:${!v('kanal_threads', true)}` }],
      [{ text: `${v('kanal_fb', true) ? '✅ AÇIK' : '⬜ KAPALI'} 📘 Facebook Paylaşımı`, callback_data: `ayarsec:kanal_fb:${!v('kanal_fb', true)}` }],
      [{ text: `${v('kanal_tiktok', true) ? '✅ AÇIK' : '⬜ KAPALI'} 🎵 TikTok Paylaşımı`, callback_data: `ayarsec:kanal_tiktok:${!v('kanal_tiktok', true)}` }],
      [{ text: `${v('kanal_youtube', true) ? '✅ AÇIK' : '⬜ KAPALI'} ▶️ YouTube Shorts`, callback_data: `ayarsec:kanal_youtube:${!v('kanal_youtube', true)}` }],
      [{ text: "← Kontrol Paneli", callback_data: "panel" }],
    ],
  };
}

function kontrolMerkeziMenusu() {
  return {
    inline_keyboard: [
      [
        { text: "📰 Günün Gönderisi (Rotasyon)", callback_data: "hizli_uret:rotasyon" },
        { text: "🎬 Reels Videosu (9:16)", callback_data: "hizli_uret:reels" },
      ],
      [
        { text: "📖 Sözlük Üret", callback_data: "hizli_uret:sozluk" },
        { text: "⚖️ Nedir Doğrusu?", callback_data: "hizli_uret:nedir_dogrusu" },
      ],
      [
        { text: "📂 Vaka Analizi", callback_data: "hizli_uret:vaka" },
        { text: "❓ Net Cevap", callback_data: "hizli_uret:net_cevap" },
      ],
      [
        { text: "🌐 Taze Haber Tara & Post Yap", callback_data: "hizli_uret:haber" },
        { text: "🏛️ Klasik Otorite (B1)", callback_data: "hizli_uret:b1" },
      ],
      [
        { text: "📊 Sıradaki Post & Durum", callback_data: "durum" },
        { text: "📰 Son Postlar", callback_data: "sonpostlar" },
      ],
      [
        { text: "📈 Detaylı Kota Raporu", callback_data: "kota_goster" },
        { text: "⚙️ Çalışma Ayarları", callback_data: "ayar" },
      ],
      [
        { text: "🩺 Sistem Sağlık Testi", callback_data: "saglik_testi" },
        { text: "⏸️ Akışı Duraklat", callback_data: "duraklat_menu" },
      ],
      [
        { text: "🔄 Konu Havuzu", callback_data: "havuz_durum" },
        { text: "⏰ Onayları Hatırlat", callback_data: "hatirlat_tetikle" },
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

const KANAL_KODLARI = {
  ig: "i",
  reels: "r",
  story: "s",
  threads: "t",
  facebook: "f",
  youtube: "y",
  tiktok: "k",
  twitter: "x",
  linkedin: "l",
};
const KOD_TO_KANAL = {
  i: "ig",
  r: "reels",
  s: "story",
  t: "threads",
  f: "facebook",
  y: "youtube",
  k: "tiktok",
  x: "twitter",
  l: "linkedin",
};

function kanallariKodla(kanallar) {
  if (!kanallar) return "";
  const arr = Array.isArray(kanallar) ? kanallar : (typeof kanallar === "string" ? kanallar.split(",") : []);
  return arr.map((k) => KANAL_KODLARI[k.trim().toLowerCase()] || k.trim()).join(",");
}

function kanallariCoz(str) {
  if (!str) return [];
  return str.split(",").map((s) => KOD_TO_KANAL[s.trim().toLowerCase()] || s.trim().toLowerCase()).filter(Boolean);
}

function seciliKanallariCikar(klavye) {
  if (!klavye || !klavye.length) return ["ig", "story", "threads", "facebook", "youtube", "tiktok", "linkedin"];
  const kanalButonlari = klavye.flat().filter(b => String(b.callback_data || "").startsWith("kanal:"));
  if (kanalButonlari.length === 0) return ["ig", "story", "threads", "facebook", "youtube", "tiktok", "linkedin"];
  return kanalButonlari
    .filter(b => String(b.text || "").startsWith("✅"))
    .map(b => b.callback_data.replace(/^kanal:/, ""));
}

function kanalButonlariSatirlari(secili = ["ig", "story", "threads", "facebook", "youtube", "tiktok", "linkedin"]) {
  const varMi = (k) => Array.isArray(secili) ? secili.includes(k) : Boolean(secili && secili[k]);
  return [
    [
      { text: `${varMi('ig') ? '✅' : '⬜'} IG`, callback_data: "kanal:ig" },
      { text: `${varMi('reels') ? '✅' : '⬜'} Reels`, callback_data: "kanal:reels" },
      { text: `${varMi('story') ? '✅' : '⬜'} Story`, callback_data: "kanal:story" },
      { text: `${varMi('threads') ? '✅' : '⬜'} Threads`, callback_data: "kanal:threads" },
    ],
    [
      { text: `${varMi('facebook') ? '✅' : '⬜'} FB`, callback_data: "kanal:facebook" },
      { text: `${varMi('youtube') ? '✅' : '⬜'} YT`, callback_data: "kanal:youtube" },
      { text: `${varMi('tiktok') ? '✅' : '⬜'} TT`, callback_data: "kanal:tiktok" },
      { text: `${varMi('linkedin') ? '✅' : '⬜'} LI`, callback_data: "kanal:linkedin" },
    ],
  ];
}

function anaMenu(adet = 2, seciliKanallar = ["ig", "story", "threads", "facebook", "youtube", "tiktok", "linkedin"]) {
  return {
    inline_keyboard: [
      ...kanalButonlariSatirlari(seciliKanallar),
      [
        { text: "✅ Yayınla", callback_data: `yayin_menu:${adet}` },
        { text: "🎙️ Sesli Yayınla", callback_data: `ses_menu:${adet}` },
      ],
      [
        { text: "📲 Manuel Paylaşım Paketi", callback_data: "manuel_paket" },
      ],
      [
        { text: "🔄 Başka Fotoğraf Bul", callback_data: `foto_menu:${adet}` },
        { text: "✍️ Metinleri Yenile", callback_data: `metin_menu:${adet}` },
      ],
      [
        { text: `🎨 Slayt düzenle (${adet} slayt)`, callback_data: `slayt_menu:${adet}` },
      ],
      [
        { text: "⏰ 1 saat ertele", callback_data: "ertele" },
      ],
      [
        { text: "❌ Bu turu atla (Havuza döner)", callback_data: "iptal" },
        { text: "🗑️ Çöpe At", callback_data: "cope_at" },
      ],
    ],
  };
}

function yayinZamaniMenusu(adet = 2, seciliKanallar = ["ig", "story", "threads", "facebook"]) {
  return {
    inline_keyboard: [
      ...kanalButonlariSatirlari(seciliKanallar),
      [
        { text: "▶️ Şimdi", callback_data: "yayinla" },
        { text: "30 dk", callback_data: "yayinla_sonra:30" },
      ],
      [
        { text: "1 saat", callback_data: "yayinla_sonra:60" },
        { text: "2 saat", callback_data: "yayinla_sonra:120" },
      ],
      [
        { text: "3 saat", callback_data: "yayinla_sonra:180" },
        { text: "4 saat", callback_data: "yayinla_sonra:240" },
      ],
      [
        { text: "← Geri", callback_data: `yayin_geri:${adet}` },
      ],
    ],
  };
}

// Sesli yayın: "Yayınla" ile aynı yol, önce fon müziği sorulur. Seslendirme yalnızca
// video kanallarına (Reels, FB, YT, TT) uygulanır; düz "Yayınla" eskisi gibi seslendirmesiz.
function sesMenusu(adet = 2, seciliKanallar = ["ig", "story", "threads", "facebook"]) {
  return {
    inline_keyboard: [
      ...kanalButonlariSatirlari(seciliKanallar),
      [
        { text: "🎵 Fon müzikli", callback_data: `ses_zaman:muzikli:${adet}` },
        { text: "🔇 Fon müziksiz", callback_data: `ses_zaman:muziksiz:${adet}` },
      ],
      [
        { text: "← Geri", callback_data: `yayin_geri:${adet}` },
      ],
    ],
  };
}

function sesliYayinZamaniMenusu(mod = "muzikli", adet = 2, seciliKanallar = ["ig", "story", "threads", "facebook"]) {
  const etiket = mod === "muziksiz" ? "🔇" : "🎵";
  return {
    inline_keyboard: [
      ...kanalButonlariSatirlari(seciliKanallar),
      [
        { text: `▶️ Şimdi ${etiket}`, callback_data: `yayinla_ses:${mod}` },
        { text: "30 dk", callback_data: `yayinla_ses_sonra:${mod}:30` },
      ],
      [
        { text: "1 saat", callback_data: `yayinla_ses_sonra:${mod}:60` },
        { text: "2 saat", callback_data: `yayinla_ses_sonra:${mod}:120` },
      ],
      [
        { text: "3 saat", callback_data: `yayinla_ses_sonra:${mod}:180` },
        { text: "4 saat", callback_data: `yayinla_ses_sonra:${mod}:240` },
      ],
      [
        { text: "← Geri", callback_data: `ses_menu:${adet}` },
      ],
    ],
  };
}

function fotoMenusu(adet = 2, seciliKanallar = ["ig", "story", "threads", "facebook"]) {
  return {
    inline_keyboard: [
      ...kanalButonlariSatirlari(seciliKanallar),
      [
        { text: "✨ 3 Farklı Aday Göster", callback_data: "foto_adaylar" },
      ],
      [
        { text: "📸 Gerçek Fotoğraf Ara", callback_data: "foto_gercek" },
        { text: "🖼️ Stok Fotoğraf (Pexels)", callback_data: "foto_stok" },
      ],
      [
        { text: "🎨 Yapay Zeka ile Üret", callback_data: "foto_ai" },
        { text: "🏛️ Saf Editoryal Zemin", callback_data: "foto_editoryal" },
      ],
      [
        { text: "← Ana Menü", callback_data: `foto_geri:${adet}` },
      ],
    ],
  };
}

function metinMenusu(adet = 2, seciliKanallar = ["ig", "story", "threads", "facebook"]) {
  return {
    inline_keyboard: [
      ...kanalButonlariSatirlari(seciliKanallar),
      [
        { text: "✂️ Haberi Daha da Özetle", callback_data: "metin_ozetle" },
        { text: "📖 Hukuki Detay Ekle", callback_data: "metin_detaylandir" },
      ],
      [
        { text: "🔄 Standart Yeniden Yaz", callback_data: "metin_yenile" },
      ],
      [
        { text: "← Ana Menü", callback_data: `metin_geri:${adet}` },
      ],
    ],
  };
}

function slaytSecimMenusu(adet = 2, seciliKanallar = ["ig", "story", "threads", "facebook"]) {
  const tuslar = [];
  if (adet > 1) {
    const satir = [];
    for (let i = 1; i <= Math.min(adet, 5); i++) {
      satir.push({ text: String(i), callback_data: `slayt:${i}:${adet}` });
    }
    tuslar.push(satir);
  }
  tuslar.push([
    { text: "📰 DailyBrief Haber", callback_data: "format_uygula:dailybrief" },
    { text: "📖 Sözlük Formatı", callback_data: "format_uygula:sozluk" },
  ]);
  tuslar.push([
    { text: "⚖️ Nedir Doğrusu?", callback_data: "format_uygula:nedir_dogrusu" },
    { text: "📂 Vaka Analizi", callback_data: "format_uygula:vaka" },
  ]);
  tuslar.push([
    { text: "❓ Net Cevap", callback_data: "format_uygula:net_cevap" },
    { text: "🎬 9:16 Dikey Reels", callback_data: "format_uygula:reels" },
  ]);
  tuslar.push([
    { text: "🏛️ Klasik Otorite (B1)", callback_data: "format_uygula:b1" },
    { text: "← Geri", callback_data: `geri:${adet}` },
  ]);
  return { inline_keyboard: tuslar };
}

function slaytIslemMenusu(sira, adet, seciliKanallar = ["ig", "story", "threads", "facebook"]) {
  const tuslar = [];
  if (adet > 1) {
    if (sira > 1) {
      tuslar.push([{ text: `🔝 ${sira}. Slaytı EN BAŞA Al (Manşet)`, callback_data: `slayt_basa:${sira}` }]);
    }
    const siraSatiri = [];
    if (sira > 1) {
      siraSatiri.push({ text: "⬆️ 1 Yukarı Taşı", callback_data: `slayt_yukari:${sira}` });
    }
    if (sira < adet) {
      siraSatiri.push({ text: "⬇️ 1 Aşağı Taşı", callback_data: `slayt_asagi:${sira}` });
    }
    if (siraSatiri.length) {
      tuslar.push(siraSatiri);
    }
  }

  tuslar.push(
    [{ text: `🔥 ${sira}. Slayt: Başlığı Daha Çarpıcı Yap`, callback_data: `slayt_carpici:${sira}` }],
    [{ text: `✍️ ${sira}. Slayt: Başlığı Elle Düzenle (Reply)`, callback_data: `slayt_elle:${sira}` }],
    [
      { text: `➕ ${sira}. Slayt: Metni Uzat`, callback_data: `slayt_uzat:${sira}` },
      { text: `➖ ${sira}. Slayt: Metni Kısalt`, callback_data: `slayt_kisalt:${sira}` },
    ]
  );
  if (adet > 2) {
    tuslar.push([{ text: `🗑 ${sira}. Slaytı Çıkar`, callback_data: `slayt_sil:${sira}` }]);
  }
  tuslar.push([{ text: "← Slayt Seçimine Dön", callback_data: `slayt_menu:${adet}` }]);
  return { inline_keyboard: tuslar };
}

// Geriye dönük uyumluluk takma adları
const standartOnayMenusu = (id, kanallar) => anaMenu(2, ["ig", "story", "threads", "facebook"]);
const reelsOnayMenusu = (id, kanallar) => anaMenu(2, ["reels", "story", "threads", "facebook", "youtube", "tiktok"]);
const formatSecimMenusu = (id) => slaytSecimMenusu(2);
const metinSecimMenusu = (id, tur) => metinMenusu(2);
const fotoSecimMenusu = (id, tur) => fotoMenusu(2);

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

// =====================================================================
// GÜVENLİK VE BİLDİRİM YARDIMCILARI
// =====================================================================

function htmlKacis(metin) {
  return String(metin ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// IZINLI_SOHBETLER: virgülle ayrılmış sohbet kimlikleri (grup kimliği eksi işaretli).
// İlk kimlik bildirim sohbetidir. Boşsa hiçbir sohbet izinli değildir.
function izinliSohbetler(env) {
  return String(env.IZINLI_SOHBETLER || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function sohbetIzinliMi(env, sohbetId) {
  if (sohbetId === undefined || sohbetId === null) return false;
  return izinliSohbetler(env).includes(String(sohbetId));
}

async function callbackYanitla(env, callbackId, metin) {
  await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ callback_query_id: callbackId, text: metin }),
  });
}

async function sohbeteGonder(env, sohbetId, metin, replyMarkup = null) {
  if (!sohbetId) return;
  const body = { chat_id: sohbetId, text: metin, parse_mode: "HTML", disable_web_page_preview: true };
  if (replyMarkup) body.reply_markup = replyMarkup;
  try {
    const r = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      delete body.parse_mode;
      body.text = metin.replace(/<[^>]+>/g, "");
      await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    }
  } catch (_) {}
}

// Günlük tur cron'ları (worker/wrangler.toml › triggers). Anahtar cron ifadesidir, UTC.
const GUNLUK_TURLAR = {
  "0 7 * * *": "bilgilendirici",   // 10:00 TR
  "30 9 * * *": "sozluk",          // 12:30 TR (hazirla.py --slot sozluk --oto-yayin)
};
const GUNLUK_TETIK_DENEME = 3;

// Günlük turu GitHub'a yollar. GitHub 5xx/ağ hatası verirse kısa beklemelerle yeniden dener (Cloudflare cron'u
// başarısız çalıştırmayı kendisi yeniden denemez); yine olmazsa gruba haber verir: sessizce gün kaybolmasın.
// GitHub cron'u zaten gecikmeli yedek olarak açık olduğundan içerik geç de olsa çıkar.
async function gunlukTuruTetikle(env, slot, cron) {
  const bekleme = Number(env.TETIK_BEKLEME_MS ?? 3000);
  for (let deneme = 1; deneme <= GUNLUK_TETIK_DENEME; deneme++) {
    try {
      if (await tetikleGitHub(env, "slot_hazirla", { slot, zamanli: true, kaynak: "cloudflare_cron", cron })) return true;
    } catch (e) {
      console.error(`Günlük tur (${slot}) tetiklenemedi (deneme ${deneme}):`, e);
    }
    if (deneme < GUNLUK_TETIK_DENEME && bekleme > 0) await new Promise((r) => setTimeout(r, bekleme * deneme));
  }
  await bildirimGonder(
    env,
    `⚠️ <b>Günlük içerik tetiklenemedi</b> (<code>${htmlKacis(slot)}</code>, Cloudflare cron).\n` +
      "<i>GitHub Actions'a ulaşılamadı — Worker'daki GITHUB_TOKEN süresi dolmuş veya yetkisi eksik olabilir. " +
      "GitHub'ın kendi cron'u yedek olarak içeriği geç de olsa üretir; kalıcı çözüm için token'ı yenileyin.</i>"
  );
  return false;
}

// Planlı yayın (worker/wrangler.toml › triggers ve PLANLAR KV'si)
const PLAN_CRON = "*/10 * * * *";
const PLAN_SURELERI = [30, 60, 120, 180, 240];
// Cron uzun süre çalışmazsa (Cloudflare kesintisi) saatler sonra "planlı" diye
// yayın çıkmasın: 3 saatten geç kalan plan yapılmaz, gruba yazılır. Instabot'taki gibi.
const PLAN_AZAMI_GECIKME_SN = 3 * 3600;

function trSaati(an) {
  // Türkiye yaz saati uygulamıyor: UTC+3 sabit
  return new Date(an.getTime() + 3 * 3600000).toISOString().slice(11, 16);
}

function menuAdedi(klavye) {
  for (const b of klavye.flat()) {
    const m = /^(?:yayin_geri|ses_menu):(\d{1,2})$/.exec(String(b.callback_data || ""));
    if (m) return parseInt(m[1], 10);
  }
  return 2;
}

// Vakti gelen planları yayınlar. GitHub yalnızca gerçek iş varken uyandırılır.
// Dispatch başarısızsa plan kalır, sonraki turda yeniden denenir. Aynı plan iki kez
// gönderilse bile yayinla.py'nin durum koruması yayınlanmış içeriği bir daha çıkarmaz.
async function planlariIsle(env, simdi = Date.now()) {
  let liste;
  try {
    liste = await env.PLANLAR.list({ prefix: "plan:" });
  } catch (e) {
    console.error("Plan listesi okunamadı:", e);
    return 0;
  }
  let gonderilen = 0;
  for (const anahtar of liste.keys) {
    let plan = null;
    try { plan = JSON.parse((await env.PLANLAR.get(anahtar.name)) || "null"); } catch (_) {}
    if (!plan || !plan.payload || !Date.parse(plan.an)) {
      await env.PLANLAR.delete(anahtar.name);
      continue;
    }
    const an = Date.parse(plan.an);
    if (an > simdi) continue;
    if (simdi - an > PLAN_AZAMI_GECIKME_SN * 1000) {
      await env.PLANLAR.delete(anahtar.name);
      try {
        await tetikleGitHub(env, "yayinla", { tur: plan.payload.tur, id: plan.payload.id, hedef: "plan_iptal" });
      } catch (_) { /* işaret 3 saat sonra zaten geçersiz sayılır */ }
      await sohbeteGonder(env, plan.sohbet || izinliSohbetler(env)[0],
        `⌛ <b>Planlanan yayın ${Math.floor((simdi - an) / 3600000)} saat gecikti ve yapılmadı.</b>\n` +
        `İçerik #${htmlKacis(String(plan.payload.id || "?"))} onay bekliyor; yeniden yayınlayabilirsiniz.`);
      continue;
    }
    let tamam = false;
    try {
      tamam = await tetikleGitHub(env, "yayinla", { ...plan.payload, planli: "1" });
    } catch (e) {
      console.error("Planlı yayın tetiklenemedi:", e);
    }
    if (tamam) {
      await env.PLANLAR.delete(anahtar.name);
      gonderilen += 1;
    }
  }
  return gonderilen;
}

function hedefKanalEtiketleri(hedef) {
  const harita = {
    ig: "📸 Instagram (4:5)",
    reels: "🎬 Reels (9:16)",
    story: "📱 Instagram Story",
    threads: "🧵 Threads",
    facebook: "📘 Facebook",
    fb: "📘 Facebook",
    youtube: "▶️ YouTube Shorts",
    shorts: "▶️ YouTube Shorts",
    tiktok: "🎵 TikTok",
    tt: "🎵 TikTok",
    linkedin: "💼 LinkedIn",
    li: "💼 LinkedIn",
  };
  const parcalar = String(hedef || "hepsi").toLowerCase().split(",").filter((p) => !p.trim().startsWith("ses_"));
  if (parcalar.includes("hepsi") || parcalar.length === 0) {
    return "Tüm Kanallar (Instagram, Threads, Facebook, YouTube, TikTok, LinkedIn)";
  }
  return parcalar.map((p) => harita[p.trim()] || p.trim().toUpperCase()).join(", ");
}

function eylemEtiketi(eylem) {
  const harita = {
    metin_ozetle: "Daha Öz & Kısa Metin",
    metin_detaylandir: "Hukuki & Detaylı Analiz",
    metin_yenile: "Yeniden Metin Yazımı",
    yenile: "Yeniden Metin & Slayt Üretimi",
    foto_gercek: "Mimari / Portföy Fotoğrafı",
    foto_stok: "Pexels Yüksek Çözünürlüklü Stok Görsel",
    foto_ai: "Yapay Zeka Mimari Tasarım",
    foto_editoryal: "Mevzuat & Editoryal Zemin",
    foto_ilk: "İlk Orijinal Görsel",
    slayt_basa: "1. Sıraya Taşıma (Manşet)",
    slayt_yukari: "Yukarı Taşıma",
    slayt_asagi: "Aşağı Taşıma",
    slayt_sil: "Slaytı Çıkarma",
    slayt_carpici: "Manşeti Çarpıcı Hale Getirme",
    slayt_uzat: "Metin Detaylandırma",
    slayt_kisalt: "Metin Sadeleştirme",
  };
  return harita[eylem] || eylem;
}

function formatEtiketi(format) {
  const harita = {
    dailybrief: "📰 Haber Bülteni (DailyBrief)",
    haber: "📰 Haber Bülteni (DailyBrief)",
    sozluk: "📖 EDM Gayrimenkul Sözlüğü",
    nedir_dogrusu: "⚖️ Nedir / Doğrusu Ne?",
    vaka: "🔍 Emlak & Hukuk Vakası",
    net_cevap: "💡 Net Cevap Rehberi",
    reels: "🎬 9:16 Dikey Reels Videosu",
    b1: "🏛️ Klasik Otorite (B1)",
  };
  return harita[format] || (format ? String(format).toUpperCase() : "Özel Format");
}

async function bildirimGonder(env, metin) {
  try {
    await sohbeteGonder(env, izinliSohbetler(env)[0], metin);
  } catch (e) {
    console.error("Bildirim gönderilemedi:", e);
  }
}

// tetikleGitHub'ın sonucu önceden hiçbir yerde okunmuyordu: dispatch başarısız
// olunca kullanıcı "yayına alınıyor..." görüp hiçbir şey olmadığını bilmiyordu.
async function tetikle(env, sohbetId, eventType, clientPayload) {
  let tamam = false;
  try {
    tamam = await tetikleGitHub(env, eventType, clientPayload);
  } catch (e) {
    console.error("Dispatch hatası:", e);
  }
  if (!tamam) {
    await sohbeteGonder(
      env,
      sohbetId || izinliSohbetler(env)[0],
      `⚠️ <b>İşlem başlatılamadı</b> (<code>${htmlKacis(eventType)}</code>).\n` +
        "<i>GitHub Actions tetiklenemedi — Worker'daki GITHUB_TOKEN süresi dolmuş veya yetkisi eksik olabilir. Butona tekrar basmadan önce kontrol et.</i>"
    );
  }
  return tamam;
}

// Açık düzenleme sözdizimi: "3: Başlık" · "başlık: Başlık" · "Başlık | Açıklama"
function duzenlemeSozdizimiMi(metin) {
  const m = String(metin || "").trim();
  if (!m || m.startsWith("/")) return false;
  return /^(?:[1-9]|10)\s*:/.test(m) || /^ba[sş]l[ıi]k\s*:/i.test(m) || m.includes("|");
}

function kaldirmaOnayMetni(refId) {
  return (
    `⚠️ <b>İçerik #${htmlKacis(refId)} yayından kaldırılsın mı?</b>\n\n` +
    "• Facebook ve Threads'ten <b>kalıcı olarak silinir</b>, geri alınamaz.\n" +
    "• Instagram API silmeye izin vermiyor; bağlantısı gönderilir, uygulamadan elle silersin."
  );
}

function kaldirmaOnayMenusu(tur, refId) {
  return {
    inline_keyboard: [[
      { text: `🗑️ Evet, #${refId} kaldır`, callback_data: `kaldir_onay:${tur}:${refId}` },
      { text: "↩️ Vazgeç", callback_data: "kaldir_vazgec" },
    ]],
  };
}

function durumMetni() {
  return (
    "📊 <b>EDM YAYIN TAKVİMİ</b>\n\n" +
    "• <b>10:00</b> — Bilgilendirici (rotasyon: B1 · Nedir Doğrusu · Net Cevap · B1) — önce bu gruba <b>onaya</b> gelir\n" +
    "• <b>12:30</b> — Emlak Sözlüğü kartı — hazır arşivden, denetimden temiz geçerse <b>onaysız otomatik yayınlanır</b> (butonlu kart gelmez)\n\n" +
    "Haber önerileri ayrıca düşer; hangisinin içeriğe çevrileceğine siz karar verirsiniz.\n\n" +
    "<i>Bu mesaj takvimi gösterir, sistemin sağlığını değil. Gerçek durum için " +
    "“Canlı Sağlık Raporu”na bas — kanallar, jetonlar ve son çalışmalar gerçekten denetlenir.</i>"
  );
}

const SAGLIK_BEKLEME_METNI =
  "🩺 <b>Canlı sağlık raporu hazırlanıyor...</b>\n" +
  "<i>Kanallar, jetonlar ve son çalışmalar denetleniyor; sonuç birkaç dakika içinde gelir.</i>";
