// tests/worker_guvenlik.test.mjs — Worker'ın güvenlik davranışı
//
// Çalıştırma:  node --test tests/*.test.mjs
//
// Kaynak metni aramıyor; Worker'ı gerçekten çağırıyor. fetch sahte: Telegram'a
// giden mesajlar ve GitHub'a giden dispatch'ler kaydediliyor, test hangi
// dispatch'in tetiklendiğine (ya da tetiklenmediğine) bakıyor.
//
// Buradaki her senaryo gerçek bir açıktan doğdu (2026-09-23 denetimi):
//   · "Silivri 220 m2" mesajı #220'yi silme komutu sayılıyordu
//   · bota özelden yazan herkes /finans, /sil tetikleyebiliyordu
//   · bot mesajına verilen her yanıt manşeti eziyordu
//   · hata anında 500 dönülüyor, Telegram aynı güncellemeyi yeniden yolluyordu

import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { copyFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

// Worker dosyası package.json'sız bir dizinde; .mjs kopyası ESM olarak yüklenir.
const kok = join(dirname(fileURLToPath(import.meta.url)), "..");
const gecici = join(mkdtempSync(join(tmpdir(), "edm-worker-")), "index.mjs");
copyFileSync(join(kok, "worker/index.js"), gecici);
const worker = (await import(pathToFileURL(gecici).href)).default;

const GRUP = "-1001234567890";
const YABANCI = "555000111";
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
let githubCevabi = 204;

beforeEach(() => {
  dispatchler = [];
  telegramlar = [];
  githubCevabi = 204;
  globalThis.fetch = async (url, secenek = {}) => {
    const govde = secenek.body ? JSON.parse(secenek.body) : {};
    if (String(url).includes("api.github.com") && String(url).endsWith("/dispatches")) {
      dispatchler.push(govde);
      return new Response(null, { status: githubCevabi });
    }
    telegramlar.push({ yontem: String(url).split("/").pop(), govde });
    return new Response(JSON.stringify({ ok: true, result: {} }), { status: 200 });
  };
});

function istek(update, gizli = GIZLI) {
  return new Request("https://worker.test/", {
    method: "POST",
    headers: { "X-Telegram-Bot-Api-Secret-Token": gizli, "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
}

const mesaj = (text, sohbet = GRUP, ek = {}) => ({
  message: { message_id: 10, text, chat: { id: Number(sohbet) }, from: { id: 1, first_name: "Test" }, ...ek },
});

const buton = (data, sohbet = GRUP, metin = "İçerik #220") => ({
  callback_query: {
    id: "cb1",
    data,
    message: { message_id: 20, text: metin, chat: { id: Number(sohbet) }, reply_markup: { inline_keyboard: [] } },
  },
});

const gonderilenMetinler = () => telegramlar.map((t) => t.govde.text || "").join("\n");

// ---------------------------------------------------------------------------

test("secret_token yanlışsa 401 ve hiçbir işlem yok", async () => {
  const c = await worker.fetch(istek(mesaj("/finans"), "yanlis"), ENV);
  assert.equal(c.status, 401);
  assert.equal(dispatchler.length, 0);
});

test("izinsiz sohbetten gelen komut hiçbir dispatch tetiklemez", async () => {
  for (const komut of ["/sil 65", "/gonderi", "/ozel herhangi bir konu", "/kurtar 12", "/temizle"]) {
    const c = await worker.fetch(istek(mesaj(komut, YABANCI)), ENV);
    assert.equal(c.status, 200, komut);
  }
  assert.equal(dispatchler.length, 0);
});

test("izinsiz sohbetten gelen buton hiçbir dispatch tetiklemez", async () => {
  await worker.fetch(istek(buton("kaldir_onay:haber:220", YABANCI)), ENV);
  await worker.fetch(istek(buton("yayinla", YABANCI)), ENV);
  await worker.fetch(istek(buton("kurtar:220", YABANCI)), ENV);
  assert.equal(dispatchler.length, 0);
});

test("IZINLI_SOHBETLER tanımsızsa her şey reddedilir (fail-closed)", async () => {
  const env = { ...ENV, IZINLI_SOHBETLER: "" };
  await worker.fetch(istek(mesaj("/gonderi")), env);
  await worker.fetch(istek(buton("kaldir_onay:haber:220")), env);
  assert.equal(dispatchler.length, 0);
});

test('"Silivri 220 m2 arsa var" silme komutu DEĞİLDİR', async () => {
  for (const metin of ["Silivri 220 m2 arsa var", "silivri 5 dönüm tarla", "Sil 65", "silah 12", "kaldir 65", "kaldırım 3"]) {
    await worker.fetch(istek(mesaj(metin)), ENV);
  }
  assert.equal(dispatchler.length, 0);
});

test("/sil doğrudan silmez, onay mesajı gönderir", async () => {
  await worker.fetch(istek(mesaj("/sil 220")), ENV);
  assert.equal(dispatchler.length, 0);
  const onay = telegramlar.find((t) => t.yontem === "sendMessage");
  assert.ok(onay, "onay mesajı gönderilmeli");
  const butonlar = onay.govde.reply_markup.inline_keyboard.flat().map((b) => b.callback_data);
  assert.deepEqual(butonlar, ["kaldir_onay:haber:220", "kaldir_vazgec"]);
});

test("/sil@botadi 220 de onay ister; argümansız veya çok argümanlı /sil hiçbir şey yapmaz", async () => {
  await worker.fetch(istek(mesaj("/sil@edm_bot 220")), ENV);
  assert.ok(gonderilenMetinler().includes("#220 yayından kaldırılsın mı"));
  await worker.fetch(istek(mesaj("/sil")), ENV);
  await worker.fetch(istek(mesaj("/sil 220 221")), ENV);
  assert.equal(dispatchler.length, 0);
});

test("rapordaki Kaldır butonu da doğrudan silmez, onay ister", async () => {
  await worker.fetch(istek(buton("kaldir:haber:220")), ENV);
  assert.equal(dispatchler.length, 0);
  assert.ok(gonderilenMetinler().includes("#220 yayından kaldırılsın mı"));
});

test("yalnızca onay butonu kaldırmayı tetikler", async () => {
  await worker.fetch(istek(buton("kaldir_onay:haber:220")), ENV);
  assert.equal(dispatchler.length, 1);
  assert.equal(dispatchler[0].event_type, "yayinla");
  assert.deepEqual(
    { tur: dispatchler[0].client_payload.tur, id: dispatchler[0].client_payload.id, hedef: dispatchler[0].client_payload.hedef },
    { tur: "haber", id: "220", hedef: "kaldir" },
  );
});

test("sahte kaldır onayı (geçersiz tür/ID) reddedilir", async () => {
  await worker.fetch(istek(buton("kaldir_onay:haber:220;rm")), ENV);
  await worker.fetch(istek(buton("kaldir_onay:x:220")), ENV);
  assert.equal(dispatchler.length, 0);
});

test("vazgeç butonu hiçbir şey silmez", async () => {
  await worker.fetch(istek(buton("kaldir_vazgec")), ENV);
  assert.equal(dispatchler.length, 0);
});

test("bot mesajına serbest yanıt manşeti değiştirmez", async () => {
  const botaYanit = { reply_to_message: { message_id: 99, from: { id: 7, is_bot: true } } };
  for (const metin of ["güzel olmuş", "bunu yarın paylaşalım", "3. slayt çok iyi"]) {
    await worker.fetch(istek(mesaj(metin, GRUP, botaYanit)), ENV);
  }
  assert.equal(dispatchler.length, 0);
});

test("açık sözdizimli yanıt metin düzenlemeyi tetikler", async () => {
  const botaYanit = { reply_to_message: { message_id: 99, from: { id: 7, is_bot: true } } };
  for (const metin of ["2: Yeni başlık", "başlık: Yeni manşet", "Yeni manşet | Yeni açıklama"]) {
    await worker.fetch(istek(mesaj(metin, GRUP, botaYanit)), ENV);
  }
  assert.equal(dispatchler.length, 3);
  assert.ok(dispatchler.every((d) => d.event_type === "metin_duzenle"));
});

test("insana verilen yanıt, sözdizimi doğru olsa da düzenleme sayılmaz", async () => {
  const insanaYanit = { reply_to_message: { message_id: 99, from: { id: 8, is_bot: false } } };
  await worker.fetch(istek(mesaj("2: Yeni başlık", GRUP, insanaYanit)), ENV);
  assert.equal(dispatchler.length, 0);
});

test("/temizle yalnızca eğik çizgiyle çalışır", async () => {
  await worker.fetch(istek(mesaj("temizle")), ENV);
  assert.equal(dispatchler.length, 0);
  await worker.fetch(istek(mesaj("/temizle")), ENV);
  assert.equal(dispatchler.length, 1);
});

test("/ozel metni satır sonlarıyla birlikte olduğu gibi iletilir", async () => {
  await worker.fetch(istek(mesaj("/ozel Hisseli tapu\nşufa hakkı")), ENV);
  assert.equal(dispatchler[0].client_payload.metin, "Hisseli tapu\nşufa hakkı");
});

test("dispatch başarısızsa gruba uyarı gider", async () => {
  githubCevabi = 401;
  await worker.fetch(istek(mesaj("/gonderi")), ENV);
  assert.ok(gonderilenMetinler().includes("İşlem başlatılamadı"));
});

test("işleyicide hata olursa 200 döner (Telegram yeniden yollamasın)", async () => {
  const bozuk = new Request("https://worker.test/", {
    method: "POST",
    headers: { "X-Telegram-Bot-Api-Secret-Token": GIZLI },
    body: "{bozuk json",
  });
  const c = await worker.fetch(bozuk, ENV);
  assert.equal(c.status, 200);
});

test("/durum sabit '%100 sağlıklı' iddiası taşımaz", async () => {
  await worker.fetch(istek(mesaj("/durum")), ENV);
  await worker.fetch(istek(mesaj("/saglik")), ENV);
  await worker.fetch(istek(mesaj("/havuz")), ENV);
  const metin = gonderilenMetinler();
  assert.ok(!metin.includes("%100"));
  assert.ok(!metin.includes("30+ Konu"));
  assert.ok(dispatchler.some((d) => d.event_type === "rapor"));
  assert.ok(dispatchler.some((d) => d.client_payload.eylem === "havuz"));
});

test("TikTok geri dönüş sayfası parametreyi kaçışlı basar", async () => {
  const c = await worker.fetch(
    new Request("https://worker.test/tiktok-callback?error=%3Cscript%3Ealert(1)%3C%2Fscript%3E"),
    ENV,
  );
  const html = await c.text();
  assert.ok(!html.includes("<script>alert(1)</script>"));
  assert.ok(html.includes("&lt;script&gt;"));
});

test("sahte kuyruk ucu artık yok", async () => {
  const c = await worker.fetch(new Request("https://worker.test/api/postedm/kuyruk"), ENV);
  assert.notEqual(c.status, 204);
});

// --- Haber önerisi (2026-09-24): haber içerik üretmez, öneri düşer ---

test("/haber içerik üretmez, haber önerisi iş akışını tetikler", async () => {
  await worker.fetch(istek(mesaj("/haber")), ENV);
  assert.equal(dispatchler.length, 1);
  assert.equal(dispatchler[0].event_type, "haber_oneri");
});

test("İçeriğe çevir yalnızca sayısal kimlikle ve haber_uret olarak tetiklenir", async () => {
  await worker.fetch(istek(buton("haber_uret:245")), ENV);
  assert.equal(dispatchler.length, 1);
  assert.equal(dispatchler[0].event_type, "haber_uret");
  assert.equal(dispatchler[0].client_payload.haber_id, "245");
  assert.ok(telegramlar.some((t) => t.yontem === "editMessageReplyMarkup"), "düğmeler kilitlenmedi");

  dispatchler = [];
  await worker.fetch(istek(buton("haber_uret:245;rm")), ENV);
  assert.equal(dispatchler.length, 0);
});

test("Geç düğmesi Actions koşusu harcamaz, yalnızca düğmeleri kaldırır", async () => {
  await worker.fetch(istek(buton("haber_gec:245")), ENV);
  assert.equal(dispatchler.length, 0);
  assert.ok(telegramlar.some((t) => t.yontem === "editMessageReplyMarkup"));
});

test("izinsiz sohbetten İçeriğe çevir tetiklenmez", async () => {
  await worker.fetch(istek(buton("haber_uret:245", YABANCI)), ENV);
  assert.equal(dispatchler.length, 0);
});
