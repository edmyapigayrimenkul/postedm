// tests/worker_hata_ayrinti.test.mjs — "🔍 Ham Hata Göster" düğmesi (2026-10-12)
//
// Eski Worker bu düğmede repodaki data/son_hata.txt dosyasını GitHub'dan okuyordu; dosya .gitignore'da olduğu için hiç
// bulunamıyordu. Artık düğme bot_yonetim/hata_ayrinti dispatch'i yollar; metni Actions DB'den (hata_kayitlari) okuyup gönderir.

import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { copyFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const kok = join(dirname(fileURLToPath(import.meta.url)), "..");
const gecici = join(mkdtempSync(join(tmpdir(), "edm-worker-hata-")), "index.mjs");
copyFileSync(join(kok, "worker/index.js"), gecici);
const worker = (await import(pathToFileURL(gecici).href)).default;

const GRUP = "-1001234567890";
const GIZLI = "test-gizli";
const ENV = { WEBHOOK_SECRET: GIZLI, TELEGRAM_BOT_TOKEN: "bot-token", GITHUB_TOKEN: "gh-token",
  GITHUB_REPOSITORY: "edmyapigayrimenkul/postedm", IZINLI_SOHBETLER: GRUP };

let dispatchler = [];
let githubOkumalari = [];

beforeEach(() => {
  dispatchler = [];
  githubOkumalari = [];
  globalThis.fetch = async (url, secenek = {}) => {
    const govde = secenek.body ? JSON.parse(secenek.body) : {};
    if (String(url).includes("api.github.com")) {
      if (String(url).endsWith("/dispatches")) { dispatchler.push(govde); return new Response(null, { status: 204 }); }
      githubOkumalari.push(String(url));
      return new Response("{}", { status: 404 });
    }
    return new Response(JSON.stringify({ ok: true, result: {} }), { status: 200 });
  };
});

const istek = (update) => new Request("https://worker.test/", {
  method: "POST",
  headers: { "X-Telegram-Bot-Api-Secret-Token": GIZLI, "Content-Type": "application/json" },
  body: JSON.stringify(update),
});
const buton = (data, sohbet = GRUP) => ({
  callback_query: { id: "cb1", data, message: { message_id: 20, text: "Hata kartı", chat: { id: Number(sohbet) } } },
});

test("Ham Hata düğmesi bot_yonetim/hata_ayrinti dispatch'i yollar, repodan dosya okumaz", async () => {
  for (const veri of ["hata_ayrinti", "hata:ayrinti"]) {
    dispatchler = [];
    const c = await worker.fetch(istek(buton(veri)), ENV);
    assert.equal(c.status, 200);
    assert.equal(dispatchler.length, 1, veri);
    assert.equal(dispatchler[0].event_type, "bot_yonetim");
    assert.equal(dispatchler[0].client_payload.eylem, "hata_ayrinti");
  }
  assert.deepEqual(githubOkumalari, [], "Worker GitHub contents API'sini çağırmamalı");
});

test("izinsiz sohbetteki Ham Hata düğmesi hiçbir şey tetiklemez", async () => {
  await worker.fetch(istek(buton("hata_ayrinti", "555000111")), ENV);
  assert.equal(dispatchler.length, 0);
});
