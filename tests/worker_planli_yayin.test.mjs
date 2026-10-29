// tests/worker_planli_yayin.test.mjs — "30 dk / 1-4 saat sonra yayınla" gerçekten planlanır
//
// Çalıştırma:  node --test tests/*.test.mjs
//
// NİYE VAR (2026-09-26): gecikme GitHub'a hiç iletilmiyordu; mesaj "30 dakika sonra
// yayına alınacak" deyip yayını HEMEN yapıyordu. Artık plan KV'ye yazılır, GitHub
// uyandırılmaz; 10 dakikalık cron (scheduled) vakti geleni "yayinla" olarak yollar.

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
const DK = 60000;

function sahteKV() {
  const m = new Map();
  return {
    m,
    async get(k) { return m.has(k) ? m.get(k) : null; },
    async put(k, v, secenek) { m.set(k, v); this.sonSecenek = secenek; },
    async delete(k) { m.delete(k); },
    async list({ prefix = "" } = {}) {
      return { keys: [...m.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name })) };
    },
  };
}

let ENV;
let dispatchler = [];
let telegramlar = [];
let githubCevabi = 204;

beforeEach(() => {
  ENV = {
    WEBHOOK_SECRET: GIZLI, TELEGRAM_BOT_TOKEN: "bot-token", GITHUB_TOKEN: "gh-token",
    GITHUB_REPOSITORY: "edmyapigayrimenkul/postedm", IZINLI_SOHBETLER: GRUP, PLANLAR: sahteKV(),
  };
  dispatchler = [];
  telegramlar = [];
  githubCevabi = 204;
  globalThis.fetch = async (url, secenek = {}) => {
    const govde = secenek.body ? JSON.parse(secenek.body) : {};
    if (String(url).endsWith("/dispatches")) {
      dispatchler.push(govde);
      return new Response(null, { status: githubCevabi });
    }
    telegramlar.push({ yontem: String(url).split("/").pop(), govde });
    return new Response(JSON.stringify({ ok: true, result: {} }), { status: 200 });
  };
});

const kanallar = (acik) => [
  ["ig", "reels", "story", "threads"].map((k) => ({ text: `${acik.includes(k) ? "✅" : "⬜"} ${k}`, callback_data: `kanal:${k}` })),
  ["facebook", "youtube", "tiktok"].map((k) => ({ text: `${acik.includes(k) ? "✅" : "⬜"} ${k}`, callback_data: `kanal:${k}` })),
  [{ text: "← Geri", callback_data: "yayin_geri:4" }],
];

const tikla = (data, klavye = kanallar(["ig", "youtube"]), metin = "İçerik #220 <b>Manşet</b>") => worker.fetch(
  new Request("https://worker.test/", {
    method: "POST",
    headers: { "X-Telegram-Bot-Api-Secret-Token": GIZLI, "Content-Type": "application/json" },
    body: JSON.stringify({ callback_query: {
      id: "cb1", data, from: { id: 1 },
      message: { message_id: 77, text: metin, chat: { id: Number(GRUP) }, reply_markup: { inline_keyboard: klavye } },
    } }),
  }), ENV);

// "planla"/"plan_iptal" yalnızca içeriğe zaman işareti yazar (hatırlatıcı için); YAYIN değildir
const yayinlar = () => dispatchler.filter((d) => !["planla", "plan_iptal"].includes(d.client_payload.hedef));
const isaretler = () => dispatchler.filter((d) => ["planla", "plan_iptal"].includes(d.client_payload.hedef))
  .map((d) => d.client_payload.hedef);

const cron = (ifade = "*/10 * * * *") => worker.scheduled({ cron: ifade, scheduledTime: Date.now() }, ENV, {});
const sonMetin = () => telegramlar.filter((t) => t.yontem === "editMessageText").pop()?.govde;
const planKoy = (an, payload = { tur: "haber", hedef: "youtube", id: "220", mesaj_id: 77 }) =>
  ENV.PLANLAR.m.set("plan:77", JSON.stringify({ an: new Date(an).toISOString(), sohbet: Number(GRUP), adet: 4,
                                                  secili: ["youtube"], metin: "İçerik #220", payload }));

test("30 dk seçilince GitHub uyandırılmaz, plan KV'ye yazılır, mesaj TR saatini söyler", async () => {
  const once = Date.now();
  await tikla("yayinla_sonra:30");
  assert.equal(yayinlar().length, 0, "planlı yayın hemen tetiklenmemeli");
  const plan = JSON.parse(ENV.PLANLAR.m.get("plan:77"));
  assert.deepEqual(dispatchler.map((d) => d.client_payload),
    [{ tur: "haber", id: "220", hedef: "planla", an: plan.an }]);
  const fark = Date.parse(plan.an) - once;
  assert.ok(fark >= 30 * DK - 1000 && fark <= 30 * DK + 5000, `plan zamanı ${fark} ms sonra`);
  assert.deepEqual(plan.payload, { tur: "haber", hedef: "ig,youtube", id: "220", mesaj_id: 77 });
  assert.equal(plan.adet, 4);
  const tr = new Date(Date.parse(plan.an) + 3 * 3600000).toISOString().slice(11, 16);
  assert.match(sonMetin().text, new RegExp(`Planlandı — TR ${tr}`));
  assert.deepEqual(sonMetin().reply_markup.inline_keyboard, [[{ text: "⏹ Planı iptal et", callback_data: "plan_iptal" }]]);
  assert.ok(ENV.PLANLAR.sonSecenek.expirationTtl > 30 * 60, "anahtar plandan önce silinmemeli");
});

test("sesli planlı yayın kipi plana taşır", async () => {
  await tikla("yayinla_ses_sonra:muziksiz:120");
  const plan = JSON.parse(ENV.PLANLAR.m.get("plan:77"));
  assert.equal(plan.payload.hedef, "ig,youtube,ses_muziksiz");
  assert.match(sonMetin().text, /2 saat sonra/);
  assert.match(sonMetin().text, /fon müziksiz/);
  assert.equal(yayinlar().length, 0);
});

test("menüde olmayan süre ve bozuk girdi planlanmaz", async () => {
  for (const data of ["yayinla_sonra:45", "yayinla_sonra:-30", "yayinla_sonra:abc", "yayinla_sonra:99999999999",
                      "yayinla_ses_sonra:muzikli:15", "yayinla_sonra:30:30"]) {
    await tikla(data);
  }
  assert.equal(ENV.PLANLAR.m.size, 0);
  assert.equal(dispatchler.length, 0);
});

test("KV yoksa planlama yapılmaz ve 'hemen' yayına da düşülmez", async () => {
  delete ENV.PLANLAR;
  await tikla("yayinla_sonra:60");
  assert.equal(dispatchler.length, 0);
  assert.match(telegramlar.find((t) => t.yontem === "answerCallbackQuery").govde.text, /Planlama şu an kullanılamıyor/);
});

test("Şimdi eskisi gibi hemen yayınlar", async () => {
  await tikla("yayinla");
  assert.equal(dispatchler.length, 1);
  assert.equal(ENV.PLANLAR.m.size, 0);
});

test("planı iptal et: plan silinir, onay menüsü seçili kanallarla geri gelir, metin kaçırılır", async () => {
  await tikla("yayinla_sonra:60", kanallar(["threads", "youtube"]), "İçerik #220 <script>");
  await tikla("plan_iptal", [[{ text: "⏹ Planı iptal et", callback_data: "plan_iptal" }]], "⏰ Planlandı");
  assert.equal(ENV.PLANLAR.m.size, 0);
  const m = sonMetin();
  assert.match(m.text, /Yayın planı iptal edildi/);
  assert.match(m.text, /&lt;script&gt;/);
  const cb = m.reply_markup.inline_keyboard.flat();
  assert.ok(cb.some((b) => b.callback_data === "yayin_menu:4"));
  assert.ok(cb.some((b) => b.callback_data === "kanal:threads" && b.text.startsWith("✅")));
  assert.ok(cb.some((b) => b.callback_data === "kanal:ig" && b.text.startsWith("⬜")));
  assert.equal(yayinlar().length, 0);
  assert.deepEqual(isaretler(), ["planla", "plan_iptal"]);

  telegramlar = [];
  await tikla("plan_iptal", [], "⏰ Planlandı");  // ikinci basış: çökmez
  assert.match(telegramlar.find((t) => t.yontem === "answerCallbackQuery").govde.text, /Bekleyen plan yok/);
});

test("cron: vakti gelen plan 'yayinla' olarak gider ve silinir; gelmeyen bekler", async () => {
  planKoy(Date.now() + 20 * DK);
  await cron();
  assert.equal(dispatchler.length, 0);
  assert.equal(ENV.PLANLAR.m.size, 1);

  planKoy(Date.now() - 2 * DK, { tur: "haber", hedef: "youtube,ses_muzikli", id: "220", mesaj_id: 77 });
  await cron();
  assert.equal(dispatchler.length, 1);
  assert.equal(dispatchler[0].event_type, "yayinla");
  assert.deepEqual(dispatchler[0].client_payload,
    { tur: "haber", hedef: "youtube,ses_muzikli", id: "220", mesaj_id: 77, planli: "1" });
  assert.equal(ENV.PLANLAR.m.size, 0);

  await cron();  // bir daha gönderilmez
  assert.equal(dispatchler.length, 1);
});

test("cron: GitHub hata verirse plan kaybolmaz, sonraki turda yeniden denenir", async () => {
  planKoy(Date.now() - DK);
  githubCevabi = 500;
  await cron();
  assert.equal(ENV.PLANLAR.m.size, 1);
  githubCevabi = 204;
  await cron();
  assert.equal(ENV.PLANLAR.m.size, 0);
  assert.equal(dispatchler.length, 2);
});

test("cron: 3 saatten geç kalan plan yayınlanmaz, gruba yazılır", async () => {
  planKoy(Date.now() - 4 * 3600000);
  await cron();
  assert.equal(yayinlar().length, 0);
  assert.deepEqual(isaretler(), ["plan_iptal"]);
  assert.equal(ENV.PLANLAR.m.size, 0);
  const bildirim = telegramlar.find((t) => t.yontem === "sendMessage");
  assert.match(bildirim.govde.text, /4 saat gecikti ve yapılmadı/);
  assert.equal(String(bildirim.govde.chat_id), GRUP);
});

test("cron: bozuk kayıt temizlenir; başka cron ifadesi hiçbir şey yapmaz (günlük tur tetiklenmez)", async () => {
  ENV.PLANLAR.m.set("plan:1", "{bozuk");
  ENV.PLANLAR.m.set("plan:2", JSON.stringify({ an: "dün", payload: {} }));
  await cron();
  assert.equal(ENV.PLANLAR.m.size, 0);

  planKoy(Date.now() - DK);
  await cron("0 7 * * 1-5");
  assert.equal(dispatchler.length, 0, "eski günlük tur cron'u hiçbir şey göndermemeli");
});

test("/planlar komutu ve planlar butonu bekleyen planları listeler", async () => {
  // Plan yokken
  const respBos = await worker.fetch(
    new Request("https://worker.test/", {
      method: "POST",
      headers: { "X-Telegram-Bot-Api-Secret-Token": GIZLI, "Content-Type": "application/json" },
      body: JSON.stringify({ message: { message_id: 10, text: "/planlar", chat: { id: Number(GRUP) } } }),
    }), ENV);
  assert.equal(respBos.status, 200);
  const mBos = telegramlar.find((t) => t.yontem === "sendMessage");
  assert.match(mBos.govde.text, /herhangi bir planlı yayın bulunmuyor/);

  // Plan varken
  ENV.PLANLAR.m.set("plan:88", JSON.stringify({
    an: new Date(Date.now() + 25 * DK).toISOString(), sohbet: Number(GRUP), adet: 4,
    secili: ["youtube"], metin: "İçerik #555", payload: { tur: "haber", hedef: "ig,youtube", id: "555", mesaj_id: 88 }
  }));
  await tikla("planlar");
  const mDolu = sonMetin();
  assert.match(mDolu.text, /BEKLEYEN PLANLI YAYINLAR/);
  assert.match(mDolu.text, /İçerik #555/);
  const butonlar = mDolu.reply_markup.inline_keyboard.flat();
  assert.ok(butonlar.some((b) => b.callback_data === "plan_hemen:88"));
  assert.ok(butonlar.some((b) => b.callback_data === "plan_iptal:88"));
});

test("plan_hemen: butonu planı bekletmeden yayına alır ve KV'den siler", async () => {
  ENV.PLANLAR.m.set("plan:88", JSON.stringify({
    an: new Date(Date.now() + 40 * DK).toISOString(), sohbet: Number(GRUP), adet: 4,
    secili: ["youtube"], metin: "İçerik #555", payload: { tur: "haber", hedef: "ig,youtube", id: "555", mesaj_id: 88 }
  }));
  assert.equal(ENV.PLANLAR.m.size, 1);
  await tikla("plan_hemen:88");
  assert.equal(ENV.PLANLAR.m.size, 0);
  assert.equal(dispatchler.length, 1);
  assert.equal(dispatchler[0].event_type, "yayinla");
  assert.equal(dispatchler[0].client_payload.id, "555");
  assert.equal(dispatchler[0].client_payload.planli, "1");
});

test("/komutlar komutu setMyCommands çağırır ve gruba bildirir", async () => {
  const resp = await worker.fetch(
    new Request("https://worker.test/", {
      method: "POST",
      headers: { "X-Telegram-Bot-Api-Secret-Token": GIZLI, "Content-Type": "application/json" },
      body: JSON.stringify({ message: { message_id: 11, text: "/komutlar", chat: { id: Number(GRUP) } } }),
    }), ENV);
  assert.equal(resp.status, 200);
  const setCmd = telegramlar.find((t) => t.yontem === "setMyCommands");
  assert.ok(setCmd, "setMyCommands çağrılmalı");
  assert.ok(Array.isArray(setCmd.govde.commands));
  assert.ok(setCmd.govde.commands.length >= 10);
  const m = telegramlar.find((t) => t.yontem === "sendMessage" && t.govde.text.includes("Komut Menüsü"));
  assert.ok(m, "başarı mesajı dönmeli");
});

test("metin_sablon butonu kopyalanabilir rehber mesajı yollar", async () => {
  await tikla("metin_sablon");
  const m = telegramlar.find((t) => t.yontem === "sendMessage" && t.govde.text.includes("ELLE METİN & BAŞLIK DÜZENLEME REHBERİ"));
  assert.ok(m, "şablon rehberi yollanmalı");
  assert.match(m.govde.text, /başlık: Yeni Çarpıcı Manşet/);
});
