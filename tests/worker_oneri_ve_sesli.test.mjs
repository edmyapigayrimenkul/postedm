// tests/worker_oneri_ve_sesli.test.mjs — Instabot biçimli haber önerisi ve "🎙️ Sesli Yayınla"
//
// Çalıştırma:  node --test tests/*.test.mjs
//
// Kullanıcı kararları (2026-09-26):
//   · Öneri tek mesaj; numaralarla çoklu seçim Worker'da (GitHub'a gitmez),
//     "▶️ Hazırla (n)" seçilenleri TEK dispatch ile yollar.
//   · Düz "✅ Yayınla" eskisi gibi; "🎙️ Sesli Yayınla" → fon müzikli / müziksiz →
//     aynı zaman menüsü. Seslendirme yalnızca video kanallarına uygulanır.

import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { copyFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const kok = join(dirname(fileURLToPath(import.meta.url)), "..");
const gecici = join(mkdtempSync(join(tmpdir(), "edm-worker-")), "index.mjs");
copyFileSync(join(kok, "worker/index.js"), gecici);
const worker = (await import(pathToFileURL(gecici).href)).default;

const GRUP = "-1001234567890";
const GIZLI = "test-gizli";
const ENV = {
  WEBHOOK_SECRET: GIZLI,
  TELEGRAM_BOT_TOKEN: "bot-token",
  GITHUB_TOKEN: "gh-token",
  GITHUB_REPOSITORY: "edmyapigayrimenkul/postedm",
  IZINLI_SOHBETLER: GRUP,
};

let dispatchler = [];
let telegramlar = [];

beforeEach(() => {
  dispatchler = [];
  telegramlar = [];
  globalThis.fetch = async (url, secenek = {}) => {
    const govde = secenek.body ? JSON.parse(secenek.body) : {};
    if (String(url).endsWith("/dispatches")) {
      dispatchler.push(govde);
      return new Response(null, { status: 204 });
    }
    telegramlar.push({ yontem: String(url).split("/").pop(), govde });
    return new Response(JSON.stringify({ ok: true, result: {} }), { status: 200 });
  };
});

const istek = (update) => new Request("https://worker.test/", {
  method: "POST",
  headers: { "X-Telegram-Bot-Api-Secret-Token": GIZLI, "Content-Type": "application/json" },
  body: JSON.stringify(update),
});

const tikla = (data, klavye, metin = "İçerik #220") => worker.fetch(istek({
  callback_query: {
    id: "cb1", data, from: { id: 1, first_name: "Test" },
    message: { message_id: 20, text: metin, chat: { id: Number(GRUP) }, reply_markup: { inline_keyboard: klavye } },
  },
}), ENV);

const yaz = (text) => worker.fetch(istek({
  message: { message_id: 10, text, chat: { id: Number(GRUP) }, from: { id: 1, first_name: "Test" } },
}), ENV);

const sonKlavye = () => {
  const d = telegramlar.filter((t) => t.yontem === "editMessageReplyMarkup").pop();
  return d ? d.govde.reply_markup.inline_keyboard : null;
};
const cbler = (klavye) => klavye.flat().map((b) => b.callback_data);
const yanitlar = () => telegramlar.filter((t) => t.yontem === "answerCallbackQuery").map((t) => t.govde.text).join(" | ");

const oneriKlavyesi = (secili = []) => [
  [272, 273, 274].map((id, i) => ({ text: (secili.includes(id) ? "✅" : "") + ["1️⃣", "2️⃣", "3️⃣"][i], callback_data: `sec:${id}` })),
  [272, 273, 274].map((id, i) => ({ text: `🔍 ${i + 1}`, callback_data: `incele:${id}` })),
  [{ text: `▶️ Hazırla (${secili.length})`, callback_data: "hazirla_secilenler" }],
  [{ text: "❌ Hiçbiri", callback_data: "oneri_gec" }],
];

const kanallar = (acik) => [
  ["ig", "reels", "story", "threads"].map((k) => ({ text: `${acik.includes(k) ? "✅" : "⬜"} ${k}`, callback_data: `kanal:${k}` })),
  ["facebook", "youtube", "tiktok"].map((k) => ({ text: `${acik.includes(k) ? "✅" : "⬜"} ${k}`, callback_data: `kanal:${k}` })),
];

// --- Haber önerisi -----------------------------------------------------------

test("numara seçimi Worker'da işaretlenir, sayaç güncellenir, GitHub'a gitmez", async () => {
  await tikla("sec:273", oneriKlavyesi([272]));
  const k = sonKlavye();
  assert.deepEqual(k[0].map((b) => b.text), ["✅1️⃣", "✅2️⃣", "3️⃣"]);
  assert.equal(k[2][0].text, "▶️ Hazırla (2)");
  assert.equal(dispatchler.length, 0);

  await tikla("sec:272", oneriKlavyesi([272]));  // ikinci basış işareti kaldırır
  assert.equal(sonKlavye()[0][0].text, "1️⃣");
  assert.equal(sonKlavye()[2][0].text, "▶️ Hazırla (0)");
});

test("Hazırla seçilenleri TEK dispatch ile yollar; seçim yoksa hiçbir şey olmaz", async () => {
  await tikla("hazirla_secilenler", oneriKlavyesi());
  assert.equal(dispatchler.length, 0);
  assert.match(yanitlar(), /en az bir haber/);

  await tikla("hazirla_secilenler", oneriKlavyesi([272, 274]));
  assert.equal(dispatchler.length, 1);
  assert.equal(dispatchler[0].event_type, "haber_uret");
  assert.equal(dispatchler[0].client_payload.haber_id, "272,274");
});

test("sahte ✅ taşıyan yabancı düğme seçime karışmaz", async () => {
  const klavye = oneriKlavyesi([272]);
  klavye.push([{ text: "✅ sahte", callback_data: "sec:1;rm -rf" }, { text: "✅ başka", callback_data: "yayinla" }]);
  await tikla("hazirla_secilenler", klavye);
  assert.equal(dispatchler[0].client_payload.haber_id, "272");
});

test("🔍 ve dokunulabilir /incele_272 mevcut inceleme yoluna gider; bozuk kimlik reddedilir", async () => {
  await tikla("incele:273", oneriKlavyesi());
  await yaz("/incele_274");
  await yaz("/incele 275");
  await yaz("/incele abc");
  await yaz("/incele_27;4");
  assert.deepEqual(dispatchler.map((d) => [d.event_type, d.client_payload.eylem, d.client_payload.id]),
    [["bot_yonetim", "incele", "273"], ["bot_yonetim", "incele", "274"], ["bot_yonetim", "incele", "275"]]);
});

test("Hiçbiri düğmeleri kaldırır, Actions harcamaz", async () => {
  await tikla("oneri_gec", oneriKlavyesi());
  assert.equal(dispatchler.length, 0);
  assert.deepEqual(cbler(sonKlavye()), ["noop"]);
});

// --- Sesli yayın ---------------------------------------------------------------

test("ana menüde Sesli Yayınla, Yayınla'nın yanında", async () => {
  await tikla("yayin_geri:3", kanallar(["ig", "youtube"]));
  const satir = sonKlavye().find((s) => s.some((b) => b.callback_data === "yayin_menu:3"));
  assert.deepEqual(satir.map((b) => b.callback_data), ["yayin_menu:3", "ses_menu:3"]);
});

test("Sesli Yayınla → fon müzikli / müziksiz → aynı zaman menüsü; kanal seçimi korunur", async () => {
  await tikla("ses_menu:3", kanallar(["youtube"]));
  let k = sonKlavye();
  assert.ok(cbler(k).includes("ses_zaman:muzikli:3") && cbler(k).includes("ses_zaman:muziksiz:3"));
  assert.ok(k.flat().some((b) => b.callback_data === "kanal:youtube" && b.text.startsWith("✅")));

  await tikla("ses_zaman:muziksiz:3", kanallar(["youtube"]));
  k = sonKlavye();
  for (const cb of ["yayinla_ses:muziksiz", "yayinla_ses_sonra:muziksiz:30", "yayinla_ses_sonra:muziksiz:240", "ses_menu:3"]) {
    assert.ok(cbler(k).includes(cb), cb);
  }
  assert.equal(dispatchler.length, 0);
});

test("sesli yayın hedefe ses kipini ekler; düz yayın eklemez", async () => {
  await tikla("yayinla_ses:muzikli", kanallar(["ig", "youtube", "tiktok"]));
  await tikla("yayinla", kanallar(["ig", "youtube", "tiktok"]));
  await tikla("yayinla_ses:muziksiz", kanallar(["reels"]));
  assert.deepEqual(dispatchler.map((d) => d.client_payload.hedef),
    ["ig,youtube,tiktok,ses_muzikli", "ig,youtube,tiktok", "reels,ses_muziksiz"]);
  const metinler = telegramlar.filter((t) => t.yontem === "editMessageText").map((t) => t.govde.text);
  assert.match(metinler[0], /Seslendirme:<\/b> fon müzikli/);
  assert.doesNotMatch(metinler[1], /Seslendirme/);
  assert.doesNotMatch(metinler[0], /SES_/);  // ses işareti kanal listesinde görünmez
});

test("video kanalı yoksa sesli yayın başlamaz", async () => {
  await tikla("yayinla_ses:muzikli", kanallar(["ig", "story", "threads"]));
  assert.equal(dispatchler.length, 0);
  assert.match(yanitlar(), /video kanalı/);
});

test("uydurma ses kipi reddedilir", async () => {
  for (const data of ["yayinla_ses:hack", "yayinla_ses:", "yayinla_ses_sonra:x:30"]) {
    await tikla(data, kanallar(["youtube"]));
  }
  assert.equal(dispatchler.length, 0);
});

// Planlı (sesli) yayın: tests/worker_planli_yayin.test.mjs
