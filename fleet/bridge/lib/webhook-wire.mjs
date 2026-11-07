// lib/webhook-wire.mjs — a webhook-celok (3.1 + tobbcelu) bekotese a hidba.
// KI-allapotu cel: egy `[bridge] WEBHOOK KI[ (<cel>)]: ...` sor a stderr-re, a
// hid (es a tobbi cel) ettol fut tovabb. A naplosorba csak a host kerul.
// Celonkent sajat tartos sor: a `default` (SUBETHA_REPLY_WEBHOOK) a regi
// BRIDGE_WEBHOOK_QUEUE_FILE-ban, a nevesitett a mellette levo webhook-queue-<cel>.json-ban.
import { dirname, join } from "node:path";
import { writeHealth } from "./health.mjs";
import { createWebhookQueue } from "./webhook-queue.mjs";
import { matchTargets } from "./webhook-match.mjs";
import { createChain } from "./webhook-chain.mjs";
import { DEFAULT_TIMEOUT_MS } from "./webhook.mjs";
import { createReplySender } from "./outbound.mjs";

// Kezzel osszerakott CFG (csak CFG.webhook): a regi egycelu alak.
function targetsOf(CFG) {
  if (Array.isArray(CFG.webhooks)) return CFG.webhooks;
  const wh = CFG.webhook || { enabled: false, reason: null };
  if (!wh.enabled && !wh.reason) return [];
  return [{ ...wh, name: "default", legacy: true, header: "X-Bridge-Token", match: { reply: true },
    timeoutMs: DEFAULT_TIMEOUT_MS, from: null, reply: null, unless: null, nofooter: null }];
}

const OFF = { summary: "webhook=off", queue: null, onApprovalCandidate: () => {}, start: () => {},
  depth: () => 0, drain: async () => {}, stop: () => {} };

// tg: a cel _REPLY-ja ezen megy a szalba (kezbesitesi naploval); sendReply: teszt-csere.
export function createWebhookWire(CFG, { post, log = () => {}, warn = (s) => console.error(s), onCorrupt,
  tg, sendReply = tg ? createReplySender({ tg, logDir: CFG.inboxDir, log }) : undefined, ca, now } = {}) {
  const all = targetsOf(CFG);
  for (const t of all) {
    if (!t.enabled && t.reason) warn(`[bridge] WEBHOOK KI${t.legacy ? "" : ` (${t.name})`}: ${t.reason}`);
  }
  const targets = all.filter((t) => t.enabled);
  if (!targets.length) {
    writeHealth(CFG.healthFile, { webhook: "off" });
    return OFF;
  }
  const queues = new Map();
  const chain = createChain({ targets, queues, sendReply, log });
  for (const t of targets) {
    const file = t.legacy ? CFG.webhookQueueFile : join(dirname(CFG.webhookQueueFile), `webhook-queue-${t.name}.json`);
    queues.set(t.name, createWebhookQueue({ file, cfg: t, logDir: CFG.inboxDir, log, onCorrupt, ca,
      hooks: chain.hooksFor(t), target: t.legacy ? undefined : t.name, ...(post ? { post } : {}), ...(now ? { now } : {}) }));
  }
  writeHealth(CFG.healthFile, { webhook: "on" });
  const tickAll = () => Promise.all([...queues.values()].map((q) => q.tick()));
  const depth = () => [...queues.values()].reduce((n, q) => n + q.depth(), 0);
  // A beinjektalas ELOTT hivodik: a tartos iras hibaja DOB (semmi nem
  // injektalodott, az offset nem lep). A kuldest a visszaadott fuggveny inditja.
  // ctx: { kind: "message"|"reaction", replyToFromId, botId, replyToText }.
  const onApprovalCandidate = (body, ctx = { kind: "message" }) => {
    const hits = matchTargets(targets, body, ctx);
    if (!hits.length) return undefined;
    try {
      for (const h of hits) queues.get(h.target.name).persist(h.body, h.extra);
    } catch (e) {
      writeHealth(CFG.healthFile, { last_webhook_queue_error: Date.now() });
      throw e;
    }
    return () => { for (const h of hits) queues.get(h.target.name).tick(); };
  };
  let timer = null;
  const start = () => {
    if (timer) return; // idempotens: masodik hivas nem ad uj intervallumot
    tickAll();
    timer = setInterval(() => tickAll(), 5000);
    timer.unref?.();
  };
  // Tesztnek/leallasnak: addig tickel, amig a sor fogy (az esedekes es kesz elemek).
  const drain = async (rounds = 10) => {
    for (let i = 0, prev = -1; i < rounds && depth() && depth() !== prev; i++) { prev = depth(); await tickAll(); }
  };
  const one = targets.length === 1 && targets[0].legacy;
  return {
    summary: one ? `webhook=on host=${targets[0].host}`
      : `webhook=on targets=${targets.map((t) => `${t.name}@${t.host}`).join(",")}`,
    queue: queues.get("default") || queues.values().next().value, queues, onApprovalCandidate, start, depth,
    drain, stop: () => { clearInterval(timer); timer = null; },
  };
}
