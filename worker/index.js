/**
 * worker/index.js — EDM Telegram Webhook & GitHub Dispatcher
 * Cloudflare Worker üzerinde çalışır.
 * Telegram buton tıklamalarını yakalar ve GitHub Actions'ı tetikler.
 */

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("EDM Telegram Webhook Aktif", { status: 200 });
    }

    // ---------------------------------------------------------------
    // GÜVENLİK: secret_token doğrulaması
    //
    // Bu Worker GitHub Actions tetikliyor; tetiklenen iş Instagram'a
    // paylaşım yapıyor. Doğrulama olmadan adresi bilen HERKES sahte
    // bir callback gönderip yayın başlatabilir.
    //
    // Depo PUBLIC: saldırgan bu dosyayı okuyup hangi payload'ı
    // göndereceğini tam olarak bilir. Tek savunmamız "adresi
    // bilmiyorlar" olamaz.
    //
    // Telegram her webhook isteğinde bu başlığı gönderiyor
    // (setWebhook'a secret_token parametresiyle kurulur).
    //
    // FAIL-CLOSED: WEBHOOK_SECRET tanımlı değilse istek REDDEDİLİR.
    // "Tanımlı değilse kabul et" davranışı, secret'ı kurmayı unutmayı
    // sessiz bir güvenlik açığına çevirirdi.
    // ---------------------------------------------------------------
    const gelenGizli = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
    if (!env.WEBHOOK_SECRET || gelenGizli !== env.WEBHOOK_SECRET) {
      return new Response("Yetkisiz", { status: 401 });
    }

    try {
      const update = await request.json();

      // 1. Buton Tıklaması (Callback Query)
      if (update.callback_query) {
        const cb = update.callback_query;
        const data = cb.data || "";
        const chatId = cb.message?.chat?.id;
        const callbackId = cb.id;

        // Telegram'a bekleme simgesini kaldırması için hızlı yanıt ver
        await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ callback_query_id: callbackId, text: "İşlem alınıyor..." }),
        });

        // A. İlan Seçimi: "ilan_sec:19802542"
        if (data.startsWith("ilan_sec:")) {
          const ilanId = data.split(":")[1];
          await tetikleGitHub(env, "hazirla_ilan", { ilan_id: ilanId });
          return new Response("OK");
        }

        // B. İlan Menüsü Yenile: "ilan_menu_yenile"
        if (data === "ilan_menu_yenile") {
          await tetikleGitHub(env, "ilan_menusu", {});
          return new Response("OK");
        }

        // C. Onay: "onayla:haber:hepsi:12" veya "onayla:ilan:ig:19802542"
        if (data.startsWith("onayla:")) {
          const [, tur, hedef, id] = data.split(":");
          await tetikleGitHub(env, "yayinla", { tur, hedef, id });
          return new Response("OK");
        }

        // D. Reddet: "reddet:haber:12"
        if (data.startsWith("reddet:")) {
          const [, tur, id] = data.split(":");
          await tetikleGitHub(env, "yayinla", { tur, hedef: "reddet", id });
          await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ chat_id: chatId, text: `❌ ${tur.toUpperCase()} #${id} reddedildi ve arşive kaldırılıyor...` }),
          });
          return new Response("OK");
        }

        // E. Yenile: "yenile:haber:12"
        if (data.startsWith("yenile:")) {
          const [, tur, id] = data.split(":");
          await tetikleGitHub(env, "yayinla", { tur, hedef: "yenile", id });
          await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ chat_id: chatId, text: `🔄 ${tur.toUpperCase()} #${id} için metin ve görseller yeniden hazırlanıyor...` }),
          });
          return new Response("OK");
        }
      }

      // 2. Normal Komutlar
      if (update.message?.text) {
        const text = update.message.text.trim();
        const chatId = update.message.chat?.id;

        if (text === "/ilanlar" || text === "/ilan") {
          await tetikleGitHub(env, "ilan_menusu", {});
          await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ chat_id: chatId, text: "🔄 Portföy ilanları getiriliyor, lütfen bekleyin..." }),
          });
          return new Response("OK");
        }

        if (text === "/haber" || text === "/hazirla" || text === "/tara") {
          await tetikleGitHub(env, "sabah_hazirla", { kaynak: "telegram_komut" });
          await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ chat_id: chatId, text: "📰 Güncel gayrimenkul haberleri taranıyor ve onayınıza hazırlanıyor..." }),
          });
          return new Response("OK");
        }

        if (text === "/start" || text === "/yardim" || text === "/menu" || text === "/durum") {
          const yardim = (
            "🏢 <b>EDM Yapı & Gayrimenkul Sosyal Medya Botu</b>\n\n" +
            "Kullanabileceğiniz komutlar:\n" +
            "• <b>/ilanlar</b> — Güncel ilan listesini getirir ve tek tıkla paylaşım hazırlatır.\n" +
            "• <b>/haber</b> — Silivri ve emlak haberlerini tarar, 3 slaytlık post üretir.\n" +
            "• <b>/durum</b> — Bot ve API entegrasyonlarının sağlığını gösterir."
          );
          await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ chat_id: chatId, text: yardim, parse_mode: "HTML" }),
          });
          return new Response("OK");
        }
      }

      return new Response("OK");
    } catch (err) {
      return new Response(`Hata: ${err.message}`, { status: 500 });
    }
  },

  // 3. Saniyesi Şaşmayan Zamanlanmış Cron (Sabah 09:00 TR)
  async scheduled(event, env, ctx) {
    console.log("Cloudflare Cron tetiklendi, GitHub Actions uyarılıyor...");
    await tetikleGitHub(env, "sabah_hazirla", { kaynak: "cloudflare_cron" });
  },
};

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
