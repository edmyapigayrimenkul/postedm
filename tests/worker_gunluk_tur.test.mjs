// tests/worker_gunluk_tur.test.mjs — günlük tur Cloudflare cron'undan tetiklenir (2026-10-12)
//
// Çalıştırma:  node --test tests/*.test.mjs
//
// NİYE VAR: GitHub `schedule` koşuları 6-10 saat gecikiyordu (07:00 UTC içeriği 16:37'de, 09:30 sözlüğü 19:13'te çalıştı).
// Worker artık 07:00 ve 09:30 UTC'de `slot_hazirla` {slot, zamanli: true} yollar. GitHub'ın kendi cron'u gecikmeli yedektir;
// aynı slot aynı günde ikinci kez üretilmez (hazirla.py, tests/test_zamanli_gunluk_koruma.py).

import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { copyFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const kok = join(dirname(fileURLToPath(import.meta.url)), "..");
const gecici = join(mkdtempSync(join(tmpdir(), "edm-worker-gunluk-")), "index.mjs");
copyFileSync(join(kok, "worker/index.js"), gecici);
const worker = (await import(pathToFileURL(gecici).href)).default;

const GRUP = "-1001234567890";

function sahteKV() {
  const m = new Map();
  return {
    async get(k) { return m.has(k) ? m.get(k) : null; },
    async put(k, v) { m.set(k, v); },
    async delete(k) { m.delete(k); },
    async list({ prefix = "" } = {}) {
      return { keys: [...m.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name })) };
    },
  };
}

let ENV;
let dispatchler = [];
let telegramlar = [];
let githubDurumlari = [];

beforeEach(() => {
  ENV = {
    WEBHOOK_SECRET: "g", TELEGRAM_BOT_TOKEN: "bot-token", GITHUB_TOKEN: "gh-token",
    GITHUB_REPOSITORY: "edmyapigayrimenkul/postedm", IZINLI_SOHBETLER: GRUP, PLANLAR: sahteKV(),
    TETIK_BEKLEME_MS: "0",
  };
  dispatchler = [];
  telegramlar = [];
  githubDurumlari = [];
  globalThis.fetch = async (url, secenek = {}) => {
    const govde = secenek.body ? JSON.parse(secenek.body) : {};
    if (String(url).endsWith("/dispatches")) {
      dispatchler.push(govde);
      const durum = githubDurumlari.length ? githubDurumlari.shift() : 204;
      return new Response(null, { status: durum });
    }
    telegramlar.push({ yontem: String(url).split("/").pop(), govde });
    return new Response(JSON.stringify({ ok: true, result: {} }), { status: 200 });
  };
});

const cron = (ifade) => worker.scheduled({ cron: ifade, scheduledTime: Date.now() }, ENV, {});

test("10:00 TR (07:00 UTC) bilgilendirici turu zamanlı yükle tetiklenir", async () => {
  await cron("0 7 * * *");
  assert.equal(dispatchler.length, 1);
  assert.equal(dispatchler[0].event_type, "slot_hazirla");
  assert.equal(dispatchler[0].client_payload.slot, "bilgilendirici");
  assert.equal(dispatchler[0].client_payload.zamanli, true);
  assert.equal(dispatchler[0].client_payload.kaynak, "cloudflare_cron");
  assert.equal(telegramlar.length, 0, "başarılı tetikte gruba mesaj düşmemeli");
});

test("12:30 TR (09:30 UTC) sözlük turu tetiklenir", async () => {
  await cron("30 9 * * *");
  assert.equal(dispatchler.length, 1);
  assert.equal(dispatchler[0].client_payload.slot, "sozluk");
  assert.equal(dispatchler[0].client_payload.zamanli, true);
});

// Faz 5 (2026-10-13): hatırlatma, haber önerisi ve günlük rapor da Cloudflare cron'undan tetiklenir.
// GitHub'ın kendi cron'ları yedek; aynı slot aynı günde bir kez çalışır (scripts/zamanli_koruma.py).
const ZAMANLI = [
  ["40 5 * * *", "rapor", "rapor", "Günlük rapor"],                          // 08:40 TR
  ["17 6 * * *", "haber_oneri", "haber_oneri_sabah", "Haber önerisi"],       // 09:17 TR
  ["30 10 * * *", "hatirlat", "hatirlat_ogle", "Onay hatırlatıcı"],          // 13:30 TR
  ["17 15 * * *", "haber_oneri", "haber_oneri_aksam", "Haber önerisi"],      // 18:17 TR
  ["30 18 * * *", "hatirlat", "hatirlat_aksam", "Onay hatırlatıcı"],         // 21:30 TR
];

for (const [ifade, olay, slot] of ZAMANLI) {
  test(`${ifade} → ${olay} (${slot}) zamanlı yükle tetiklenir`, async () => {
    await cron(ifade);
    assert.equal(dispatchler.length, 1);
    assert.equal(dispatchler[0].event_type, olay);
    assert.equal(dispatchler[0].client_payload.slot, slot);
    assert.equal(dispatchler[0].client_payload.zamanli, true);
    assert.equal(dispatchler[0].client_payload.kaynak, "cloudflare_cron");
    assert.equal(dispatchler[0].client_payload.cron, ifade);
    assert.equal(dispatchler[0].client_payload.zorla, undefined, "hatırlatma zorla modunda çalışmamalı: 60 dk bekleme kuralı geçerli");
    assert.equal(telegramlar.length, 0, "başarılı tetikte gruba mesaj düşmemeli");
  });
}

for (const [ifade, , slot, ad] of ZAMANLI) {
  test(`${slot}: üç denemede tetiklenemezse gruba iş adıyla haber verir`, async () => {
    githubDurumlari = [401, 401, 401];
    await cron(ifade);
    assert.equal(dispatchler.length, 3);
    const mesajlar = telegramlar.filter((t) => t.yontem === "sendMessage");
    assert.equal(mesajlar.length, 1);
    assert.ok(mesajlar[0].govde.text.includes(`${ad} tetiklenemedi`), mesajlar[0].govde.text);
    assert.ok(mesajlar[0].govde.text.includes(slot));
  });
}

test("yedi zamanlı işin her cron'u wrangler.toml'da ve her biri yalnız KENDİ olayını yollar", async () => {
  const toml = await import("node:fs").then((fs) => fs.readFileSync(join(kok, "worker/wrangler.toml"), "utf8"));
  for (const ifade of ["40 5 * * *", "17 6 * * *", "0 7 * * *", "30 9 * * *", "30 10 * * *", "17 15 * * *", "30 18 * * *"]) {
    assert.ok(toml.includes(`"${ifade}"`), `${ifade} wrangler.toml'da yok`);
    dispatchler = [];
    await cron(ifade);
    assert.equal(dispatchler.length, 1, `${ifade} tam bir dispatch yollamalı`);
  }
});

test("10 dakikalık plan cron'u günlük tur TETİKLEMEZ", async () => {
  await cron("*/10 * * * *");
  assert.equal(dispatchler.filter((d) => d.event_type === "slot_hazirla").length, 0);
});

test("bilinmeyen cron hiçbir şey yollamaz", async () => {
  await cron("5 4 * * *");
  assert.equal(dispatchler.length, 0);
  assert.equal(telegramlar.length, 0);
});

test("GitHub geçici hata verirse yeniden dener, düzelince gruba haber vermez", async () => {
  githubDurumlari = [502, 503];
  await cron("0 7 * * *");
  assert.equal(dispatchler.length, 3);
  assert.equal(telegramlar.length, 0);
});

test("üç denemede de tetiklenemezse gruba nedeniyle haber verir (gün sessizce kaybolmaz)", async () => {
  githubDurumlari = [401, 401, 401];
  await cron("30 9 * * *");
  assert.equal(dispatchler.length, 3);
  const mesajlar = telegramlar.filter((t) => t.yontem === "sendMessage");
  assert.equal(mesajlar.length, 1);
  assert.match(mesajlar[0].govde.text, /Günlük içerik tetiklenemedi/);
  assert.match(mesajlar[0].govde.text, /sozluk/);
  assert.match(mesajlar[0].govde.text, /GITHUB_TOKEN/);
});

test("fetch istisna fırlatsa da Worker çökmez, yeniden dener ve bildirir", async () => {
  let cagri = 0;
  const eski = globalThis.fetch;
  globalThis.fetch = async (url, secenek) => {
    if (String(url).endsWith("/dispatches")) { cagri += 1; throw new Error("ağ koptu"); }
    return eski(url, secenek);
  };
  await cron("0 7 * * *");
  assert.equal(cagri, 3);
  assert.equal(telegramlar.filter((t) => t.yontem === "sendMessage").length, 1);
});

test("durum menüsü güncel takvimi gösterir (eski 13:30/18:30 İÇERİK slotları yok; 13:30 artık yalnız hatırlatma)", async () => {
  const kaynak = await import("node:fs").then((fs) => fs.readFileSync(join(kok, "worker/index.js"), "utf8"));
  assert.ok(!kaynak.includes("<b>18:30</b>"));
  assert.ok(!/<b>13:30<\/b>\s*—\s*(Bilgilendirici|Emlak|Haber)/.test(kaynak), "13:30 içerik slotu olarak geri gelmemeli");
  assert.match(kaynak, /<b>13:30<\/b> ve <b>21:30<\/b> — Sessiz kuyruk bakımı \(hatırlatma YOK\)/);
  assert.ok(kaynak.includes("<b>12:30</b>"));
  assert.ok(kaynak.includes("<b>08:40</b>"));
});
