#!/usr/bin/env node
// Egy agens dedikalt Telegram INBOUND hidja.
//
// Miert letezik: a claude telegram MCP-plugin getUpdates pollere megbizhatatlanul
// csatlakozik (2026-07-29/30-an ketszer nemult el), es minden `claude -p`
// alfolyamat sajat plugint inditott ugyanazzal a tokennel (egy tokenre EGY
// poller szabad). Ez a hid az egyetlen getUpdates-hivo.
//
// A `tmux send-keys` sikeres visszaterese NEM kezbesites. Ezert:
//   1. minden update ELOBB tartos esemeny-naploba irodik (events-*.jsonl),
//      az offset csak ezutan — es csak a HIBATLAN feldolgozas utan — lephet;
//   2. sikertelen inject -> lemezes pending-sor, periodikusan ujraprobalva;
//   3. tartos kezbesitetlenseg vagy 409 -> a hid MAGA szol a csoportnak.
// A bejovo uzenetek a kezbesitesi naploba is bekerulnek (delivery-*.jsonl,
// docs/delivery-log.md); a kimeno oldalt a send.mjs irja ugyanoda.
//
// Ez a fajl csak osszedrotoz; a felelossegek a lib/ moduljaiban elnek.
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { loadConfig } from "./lib/config.mjs";
import { MediaQueue } from "./lib/mediaqueue.mjs";
import { createTelegram } from "./lib/telegram.mjs";
import { downloadMedia } from "./lib/media.mjs";
import { createDeliverer } from "./lib/deliverer.mjs";
import { createAlbums } from "./lib/albums.mjs";
import { createHandlers } from "./lib/handlers.mjs";
import { appendEvent, createInboundLogger, pruneInbox } from "./lib/inbox.mjs";
import { initOffset, pollForever } from "./lib/poll.mjs";
import { holdTokenLockOrExit } from "./lib/token-lock-guard.mjs";
import { createWebhookWire } from "./lib/webhook-wire.mjs";
import { createReceiptWire } from "./lib/receipt-wire.mjs";

const log = (...a) => console.log(new Date().toISOString(), "[bridge]", ...a);

// Wiring: a CFG-bol felepiti a hid alkatreszeit. Kulon fuggveny, hogy a
// modul importja ne inditson semmit (tesztek, `node --check`).
// deps.webhookPost / deps.webhookCa: csak tesztnek (a webhook-POST helyettesitese, sajat CA).
export function createBridge(CFG, deps = {}) {
  const { tg, fileApi } = createTelegram(CFG.token, CFG.telegramApi);
  // A felirat CFG.agentLabel: tobb hid eseten mindegyik a sajat neveben szol.
  const alert = async (text) => {
    try {
      await tg("sendMessage", { chat_id: CFG.groupId, text: `⚠️ [${CFG.agentLabel} híd] ${text}` });
    } catch (e) {
      log("selfAlert failed:", e.message);
    }
  };
  // Serult allapotfajl: a karanten a lib dolga, a HANGOSSA TETEL a mienk.
  const onCorrupt = (p) => {
    log("ÁLLAPOTFÁJL SÉRÜLT, karanténba téve:", p);
    alert(`állapotfájl sérült, karanténba téve: ${p} — kézi visszajátszás az events-naplóból lehetséges`)
      .catch(() => {});
  };
  const receipts = createReceiptWire(CFG, { tg, alert, log, onCorrupt }); // 3.2, BRIDGE_RECEIPT=1
  const delivery = createDeliverer({
    session: CFG.session, pendingFile: CFG.pendingFile, maxPending: CFG.maxPending,
    pendingAlertMs: CFG.pendingAlertMs, healthFile: CFG.healthFile, label: CFG.agentLabel,
    alert, log, onCorrupt, ...receipts.hooks,
  });
  receipts.bind(delivery);
  const albums = createAlbums({
    file: join(dirname(CFG.mediaQueueFile), "album-buffer.json"), inboxDir: CFG.inboxDir,
    debounceMs: CFG.albumDebounceMs, maxBytes: CFG.maxFileBytes, deliver: delivery.deliver,
    download: (o) => downloadMedia({ tg, fileApi, maxBytes: CFG.maxFileBytes, ...o }),
    alert, log, onCorrupt,
  });
  // Tartos media-sor: az enqueue szinkron lemezre ir, a letoltes a hatterben, EGYESEVEL.
  const mediaQueue = new MediaQueue(CFG.mediaQueueFile,
    (item) => albums.handleMedia(item.msg, item.media, item.updateId), { onCorrupt });
  const webhook = createWebhookWire(CFG, { post: deps.webhookPost, ca: deps.webhookCa, tg, log, onCorrupt });
  const botIdentity = { username: "", id: 0 };
  const handlers = createHandlers({
    groupId: CFG.groupId, allowIds: CFG.allowIds, requireMention: CFG.requireMention,
    maxFileBytes: CFG.maxFileBytes, bot: () => botIdentity, deliver: delivery.deliver,
    enqueueMedia: (item) => {
      mediaQueue.enqueue(item);
      mediaQueue.drain().catch(() => {});
    },
    logInbound: createInboundLogger({ inboxDir: CFG.inboxDir, healthFile: CFG.healthFile, log }),
    log, onApprovalCandidate: webhook.onApprovalCandidate,
  });
  const processUpdate = (upd) => {
    appendEvent(CFG.inboxDir, CFG.healthFile, upd); // tartos naplo ELOBB; dob, ha nem sikerult
    handlers.handleMessage(upd.message, { updateId: upd.update_id });
    handlers.handleMessage(upd.edited_message, { edited: true, updateId: upd.update_id });
    handlers.handleReaction(upd.message_reaction);
  };
  return { tg, alert, onCorrupt, delivery, albums, mediaQueue, botIdentity, handlers, processUpdate, webhook, receipts };
}

async function main() {
  let CFG;
  try {
    CFG = loadConfig(process.env);
  } catch (e) {
    console.error(`[bridge] FATAL: ${e.message}`);
    process.exit(1);
  }
  // Egy tokenre EGY poller (H5) — MINDEN halozati hivas elott; foglalt: exit 75.
  holdTokenLockOrExit({ lockDir: CFG.lockDir, token: CFG.token, checkMs: CFG.lockCheckMs });
  const b = createBridge(CFG);
  log(`starting. session=${CFG.session} group=${CFG.groupId} allow=${CFG.allowIds.join(",")} inbox=${CFG.inboxDir} ${b.webhook.summary}`);
  // A getMe valaszat VALIDALJUK: enelkul requireMention=true mellett a hid
  // MINDEN csoport-uzenetet nemán eldobna. Nincs degradalt mod — a systemd visszahoz.
  const me = await b.tg("getMe", {}).catch((e) => ({ body: { ok: false, error: e.message } }));
  if (!me?.body?.ok || !me.body.result?.username || !me.body.result?.id) {
    console.error(`[bridge] FATAL: getMe érvénytelen válasz — a mention-kapu így minden üzenetet eldobna. ` +
      `Válasz: ${JSON.stringify(me?.body ?? null).slice(0, 300)}`);
    process.exit(1);
  }
  b.botIdentity.username = me.body.result.username;
  b.botIdentity.id = me.body.result.id;
  log(`bot identity: @${b.botIdentity.username} id=${b.botIdentity.id} requireMention=${CFG.requireMention}`);

  mkdirSync(CFG.inboxDir, { recursive: true });
  const prune = () => {
    const n = pruneInbox(CFG.inboxDir, CFG.retentionDays);
    if (n) log(`inbox takarítás: ${n} régi fájl törölve`);
  };
  prune();
  setInterval(prune, 6 * 60 * 60 * 1000).unref?.();
  setInterval(() => b.delivery.retryPending().catch((e) => log("retry error:", e.message)),
    CFG.pendingRetryMs).unref?.();
  // A sor elen hibara futott elemet periodikusan is meglokjuk.
  setInterval(() => b.mediaQueue.drain().catch((e) => log("media queue error:", e.message)),
    CFG.pendingRetryMs).unref?.();

  // Elobb a felbemaradt albumok, csak utana a sor ujra-feldolgozasa.
  const resumed = b.albums.resume();
  if (resumed) log(`${resumed} félbemaradt album kiküldve indulás után`);
  if (b.mediaQueue.depth()) log(`${b.mediaQueue.depth()} média-elem maradt a sorban — feldolgozás indul`);
  b.mediaQueue.drain().catch((e) => log("media queue error:", e.message));
  b.webhook.start(); // a felbemaradt webhook-sor induláskor folytatodik
  b.receipts.start(); // a fuggo nyugta-ellenorzesek is

  const offset = await initOffset({ tg: b.tg, offsetFile: CFG.offsetFile, onCorrupt: b.onCorrupt, log });
  await pollForever({
    tg: b.tg, offset, offsetFile: CFG.offsetFile, healthFile: CFG.healthFile,
    conflictAlertMs: CFG.conflictAlertMs, processUpdate: b.processUpdate, alert: b.alert, log,
    depths: () => ({ pending_depth: b.delivery.depth(), media_queue_depth: b.mediaQueue.depth(),
      webhook_queue_depth: b.webhook.depth() }),
  });
}

// Teszt alatt importalhato; futtatva a poller indul.
if (process.argv[1] && process.argv[1] === fileURLToPath(import.meta.url)) {
  main();
}
