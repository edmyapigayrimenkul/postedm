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
          await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ chat_id: chatId, text: `❌ ${tur.toUpperCase()} #${id} yayından kaldırıldı.` }),
          });
          return new Response("OK");
        }
      }

      // 2. Normal Komut: "/ilanlar"
      if (update.message?.text) {
        const text = update.message.text.trim();
        if (text === "/ilanlar" || text === "/ilan") {
          await tetikleGitHub(env, "ilan_menusu", {});
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
