// tests/worker_stres_ve_sabotaj.test.mjs — Worker Stres, Sabotaj ve Uç Durum Güvenlik Paketi
//
// Çalıştırma: node --test tests/worker_stres_ve_sabotaj.test.mjs

import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { copyFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const kok = join(dirname(fileURLToPath(import.meta.url)), "..");
const gecici = join(mkdtempSync(join(tmpdir(), "edm-worker-stres-")), "index.mjs");
copyFileSync(join(kok, "worker/index.js"), gecici);
const worker = (await import(pathToFileURL(gecici).href)).default;

const GRUP = "-1001234567890";
const GIZLI = "test-gizli-stres";

const ENV = {
  WEBHOOK_SECRET: GIZLI,
  TELEGRAM_BOT_TOKEN: "bot-token-stres",
  GITHUB_TOKEN: "gh-token-stres",
  GITHUB_REPOSITORY: "edmyapigayrimenkul/postedm",
  IZINLI_SOHBETLER: GRUP,
};

let dispatchler = [];
let telegramlar = [];
let telegramCevapKodu = 200;

beforeEach(() => {
  dispatchler = [];
  telegramlar = [];
  telegramCevapKodu = 200;
  globalThis.fetch = async (url, secenek = {}) => {
    const govde = secenek.body ? JSON.parse(secenek.body) : {};
    if (String(url).includes("api.github.com") && String(url).endsWith("/dispatches")) {
      dispatchler.push(govde);
      return new Response(null, { status: 204 });
    }
    telegramlar.push({ yontem: String(url).split("/").pop(), govde });
    if (telegramCevapKodu !== 200) {
      return new Response(JSON.stringify({ ok: false, description: "Simulated Telegram Error" }), { status: telegramCevapKodu });
    }
    return new Response(JSON.stringify({ ok: true, result: {} }), { status: 200 });
  };
});

function cbIstek(data, ekstra = {}) {
  const update = {
    callback_query: {
      id: "cb_stres_123",
      data: data,
      message: {
        chat: { id: GRUP },
        message_id: 8888,
        text: "📰 GÜNCEL HABER BÜLTENİ (#777)",
        ...ekstra,
      },
    },
  };
  return new Request("https://worker.test/", {
    method: "POST",
    headers: {
      "X-Telegram-Bot-Api-Secret-Token": GIZLI,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(update),
  });
}

test("bozuk ve eksik callback_data kombinasyonları çökmeden 200 döner", async () => {
  const bozukDatalar = [
    "",
    "   ",
    "kanal:",
    "kanal_toggle:",
    "onayla:",
    "onayla:haber:",
    "onayla:ilan:hepsi:",
    "slayt:",
    "slayt::",
    "slayt:abc:xyz",
    "slayt:99999999999999999999:0",
    "yayinla_sonra:",
    "yayinla_sonra:gecersiz",
    "yayinla_sonra:-30",
    "retry_kanal:",
    "retry_kanal::",
    "format_uygula:",
    "format_uygula:bilinmeyen_format",
    "duraklat:abc",
    "ayarsec:",
    "ayarsec:oto_yayin",
    "gorsel_sec:",
    "slayt_basa:",
    "slayt_sil:notanumber",
    "noop",
    "isleniyor",
  ];

  for (const bData of bozukDatalar) {
    const res = await worker.fetch(cbIstek(bData), ENV);
    assert.equal(res.status, 200, `Bozuk data '${bData}' durumunda 200 dönmeliydi.`);
  }
});

test("html ve script injection sabotajı güvenle işlenir ve çökmez", async () => {
  const sabotajDatalar = [
    "format_uygula:<script>alert(1)</script>",
    "metin_eylem:<b onmouseover=alert(1)>xss</b>",
    "retry_kanal:<svg onload=alert(1)>:777",
    "gorsel_sec:<iframe src='evil.com'>:777",
  ];

  for (const sData of sabotajDatalar) {
    const res = await worker.fetch(cbIstek(sData), ENV);
    assert.equal(res.status, 200);
  }

  // Telegram mesajlarında script taglerinin kaçışlı veya temiz olduğunu doğrula
  for (const t of telegramlar) {
    if (t.govde?.text) {
      assert.ok(!t.govde.text.includes("<script>alert(1)</script>"), "Zararlı script metne doğrudan girmemeli");
    }
  }
});

test("path traversal ve injection denemeleri kaldir_onay tarafından reddedilir", async () => {
  const saldirilar = [
    "kaldir_onay:../../../etc/passwd:777",
    "kaldir_onay:haber:777' OR '1'='1",
    "kaldir_onay:system;rm -rf /:777",
    "kaldir_onay:eval(process.exit()):777",
  ];

  for (const s of saldirilar) {
    const res = await worker.fetch(cbIstek(s), ENV);
    assert.equal(res.status, 200);
  }

  // Hiçbir tehlikeli dispatch tetiklenmemeli
  assert.equal(dispatchler.length, 0, "Düşmanca silme saldırıları dispatch tetiklememeli");
});

test("aşırı uzun metinler ve devasa caption girdisi bellek tüketmeden işlenir", async () => {
  const devasaCaption = "EDM Yapı " + "A".repeat(8000) + " #999";
  const devasaUpdate = {
    callback_query: {
      id: "cb_devasa",
      data: "yayinla",
      message: {
        chat: { id: GRUP },
        message_id: 1111,
        caption: devasaCaption,
        reply_markup: {
          inline_keyboard: [[{ text: "✅ Instagram", callback_data: "kanal:ig" }]],
        },
      },
    },
  };

  const req = new Request("https://worker.test/", {
    method: "POST",
    headers: { "X-Telegram-Bot-Api-Secret-Token": GIZLI, "Content-Type": "application/json" },
    body: JSON.stringify(devasaUpdate),
  });

  const res = await worker.fetch(req, ENV);
  assert.equal(res.status, 200);
  assert.equal(dispatchler.length, 1);
  assert.equal(dispatchler[0].client_payload.id, "999");
});

test("aynı anda 50 eşzamanlı callback_query yarışı (race condition) başarıyla yönetilir", async () => {
  const istekler = Array.from({ length: 50 }, (_, i) => {
    return worker.fetch(cbIstek(`kanal:${i % 2 === 0 ? "ig" : "threads"}`), ENV);
  });

  const cevaplar = await Promise.all(istekler);
  for (const c of cevaplar) {
    assert.equal(c.status, 200);
  }
});

test("telegram api 500 veya 400 hatası döndüğünde dahi worker çökmeden 200 döner", async () => {
  telegramCevapKodu = 500;
  const res500 = await worker.fetch(cbIstek("yayinla"), ENV);
  assert.equal(res500.status, 200, "Telegram 500 verse bile Worker 200 dönerek döngüsel yeniden gönderimi engellemeli");

  telegramCevapKodu = 400;
  const res400 = await worker.fetch(cbIstek("panel"), ENV);
  assert.equal(res400.status, 200, "Telegram 400 verse bile Worker 200 dönmeli");
});

test("kurtar_menu hasarlı mesaj gövdesini güvenle temizleyip ana menüyü geri yükler", async () => {
  const hasarliText = "⏳ İşlem devam ediyor...\n\nOrijinal Metin Burada Duruyor #555";
  const req = cbIstek("kurtar_menu:4", { text: hasarliText });
  const res = await worker.fetch(req, ENV);
  assert.equal(res.status, 200);

  // Düzenleme çağrısının yapıldığını ve temiz metnin iletildiğini doğrula
  const editCagrisi = telegramlar.find((t) => t.yontem === "editMessageText");
  assert.ok(editCagrisi);
  assert.ok(editCagrisi.govde.text.includes("Orijinal Metin Burada Duruyor"));
  assert.ok(!editCagrisi.govde.text.startsWith("⏳"));
});
