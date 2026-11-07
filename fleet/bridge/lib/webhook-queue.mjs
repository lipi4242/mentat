// lib/webhook-queue.mjs — a jovahagyo webhook (3.1) tartos sora.
//
// Az enqueue tartos irasa STRIKT (saveJsonStrict, dob): ha nem sikerul, a
// processUpdate dob, az offset nem lep — ugyanaz a szemantika, mint a
// pending-sornal. A beinjektalas ilyenkor mar megtortent; a kovetkezo
// getUpdates ugyanazt hozza, es a szerver az `event_id`-n deduplikal.
// Az idempotencia a SZERVER dolga; a helyi `done`-halmaz (utolso DONE_CAP
// event_id, a kimerulteket is) csak a felesleges forgalmat csokkenti.
//
// Kimenet: 2xx -> `webhook_ok`, vegleges 4xx (408/429 kivetel) -> `webhook_rejected`
// notice, mindketto `done`-ba, ujraproba nelkul.
// Ujraprobak (408, 429, 5xx, halozati hiba): RETRY_DELAYS_MS utan; a kimerult elem kiesik a sorbol, es egy
// `webhook_failed` notice-sor marad utana a kezbesitesi naploban.
// A token SOSEM kerul a fajlba, a naploba vagy a hibamezokbe: minden hibaszoveg
// a redact()-on at megy (token, URL userinfo/query -> ***).
// Tobbcelu mod (lib/webhook-chain.mjs): `hooks.ready` visszatarthat egy elemet
// (egy masik cel valaszara var), `hooks.before` halozat nelkul lezarhatja
// (`webhook_skipped`), `hooks.onFinal` a vegso kimenetet kapja (valasz-JSON-nal).
// `target`: a cel neve a notice-sorban (a `default` celnal nincs ilyen mezo).
import { saveJsonStrict, loadJsonQuarantine } from "./jsonfile.mjs";
import { logNotice } from "./notice.mjs";
import { postWebhook, redact } from "./webhook.mjs";

export const RETRY_DELAYS_MS = [10_000, 60_000, 300_000];
const DONE_CAP = 500;
// A tartos kimenetbe csak a felso szintu primitivek (a szoveg 256 karakterig) kerulnek.
const slim = (j) => (j && typeof j === "object" ? Object.fromEntries(Object.entries(j).filter(([, v]) =>
  v === null || ["number", "boolean"].includes(typeof v) || (typeof v === "string" && v.length <= 256))) : null);

export function createWebhookQueue({
  file, cfg, post = postWebhook, logDir, log = () => {}, now = Date.now, ca, onCorrupt = () => {},
  hooks = {}, target,
}) {
  const { ready = () => true, before, onFinal = async () => {} } = hooks;
  const loaded = loadJsonQuarantine(file, null, onCorrupt);
  let items = Array.isArray(loaded?.items) ? loaded.items : [];
  let done = Array.isArray(loaded?.done) ? loaded.done : [];
  // A kesz elemek vegso kimenete (event + a valasz-JSON primitiv mezoi), a done-nal
  // korlatozva: a _UNLESS-fuggo ebbol dont, akkor is, ha kesobb kerult a sorba.
  let outcomes = loaded?.outcomes && typeof loaded.outcomes === "object" ? loaded.outcomes : {};
  let running = null;
  let again = false;

  const persist = (nextItems, nextDone) => {
    const keep = new Set(nextDone); // az outcomes a done-nal egyutt fogy
    outcomes = Object.fromEntries(Object.entries(outcomes).filter(([id]) => keep.has(id)));
    saveJsonStrict(file, { items: nextItems, done: nextDone, outcomes }); // dob — a hivo dont
    items = nextItems;
    done = nextDone;
  };
  const persistQuiet = () => {
    try { persist(items, done); } catch (e) { log("webhook-sor iras hiba:", redact(e.message, cfg)); }
  };

  const notice = (event, item, detail) => logNotice(logDir, event, { chat_id: item.body.tg_chat_id,
    msg_id: item.body.tg_message_id, detail, ...(target ? { target } : {}) });
  async function attempt(item) {
    const finish = async (event, detail, res = null) => {
      outcomes[item.event_id] = { event, json: slim(res?.json) };
      try { await onFinal(item, { event, res }); } catch (e) { log("webhook onFinal hiba:", redact(e?.message, cfg)); }
      items = items.filter((i) => i.event_id !== item.event_id);
      done = [...done, item.event_id].slice(-DONE_CAP);
      notice(event, item, detail);
      persistQuiet();
    };
    let pre = null; // before nelkul a POST szinkron indul (mint eddig)
    if (hooks.before) try { pre = await before(item); } catch (e) { log("webhook before hiba:", redact(e?.message, cfg)); }
    if (pre) return finish(pre.event, pre.detail);
    let res;
    try {
      const { event_id: _id, ...bare } = item.body; // _EVENT_ID=off: a sor kulcsa marad, a torzsbol kimarad
      res = await post({ url: cfg.url, token: cfg.token, header: cfg.header, timeoutMs: cfg.timeoutMs,
        body: cfg.eventId === false ? bare : item.body, ca });
    } catch (e) {
      res = { ok: false, error: e?.code || e?.message || "ismeretlen hiba" };
    }
    if (res?.ok) return finish("webhook_ok", `HTTP ${res.status}`, res);
    // 4xx (408/429 kivetel) vegleges: az ujrakuldes ertelmetlen es zajos
    if (res?.status >= 400 && res.status < 500 && res.status !== 408 && res.status !== 429) {
      return finish("webhook_rejected", `HTTP ${res.status}`, res);
    }
    const error = redact(res?.error ?? "ismeretlen hiba", cfg);
    item.attempts += 1;
    item.last_error = error;
    log(`webhook ${item.event_id} proba ${item.attempts} sikertelen: ${error}`);
    // A kimerult elem is a done-ba: visszajatszasnal ne induljon uj 4-es kor.
    if (item.attempts > RETRY_DELAYS_MS.length) return finish("webhook_failed", error);
    item.next_at = now() + RETRY_DELAYS_MS[item.attempts - 1];
    persistQuiet();
  }

  async function runOnce() {
    const t = now();
    for (const item of items.filter((i) => i.next_at <= t && ready(i))) await attempt(item);
  }

  // Egyszerre egy kor. A futas kozben kert tick a kor vegen ujrafut.
  function tick() {
    if (running) { again = true; return running; }
    running = (async () => {
      try {
        do { again = false; await runOnce(); } while (again);
      } catch (e) {
        log("webhook tick hiba:", redact(e?.message, cfg));
      } finally {
        running = null;
      }
    })();
    return running;
  }

  // SZINKRON tartos iras (dob), halozat NELKUL. true: uj elem; false: mar ismert.
  // extra: a lanc-mezok (after, nofooter) — lib/webhook-chain.mjs.
  function persistItem(body, extra = {}) {
    const id = body.event_id;
    if (items.some((i) => i.event_id === id) || done.includes(id)) return false;
    persist([...items, { event_id: id, body, attempts: 0, next_at: now(), ...extra }], done);
    return true;
  }

  // Egy varakozo elem kiegeszitese (a fuggoseg kimenete); tartosan, csendben.
  function annotate(id, patch) {
    const item = items.find((i) => i.event_id === id);
    if (!item) return false;
    Object.assign(item, patch);
    persistQuiet();
    return true;
  }

  // persist + a kuldes a hatterben.
  function enqueue(body) {
    return persistItem(body) ? tick() : Promise.resolve();
  }

  // { known:true, event, json } | { known:false } (kesz, de a kimenet elveszett) | null (nem ismert)
  const outcome = (id) => (outcomes[id] ? { known: true, ...outcomes[id] } : done.includes(id) ? { known: false } : null);

  return { outcome, persist: persistItem, enqueue, tick, annotate, depth: () => items.length,
    has: (id) => items.some((i) => i.event_id === id), find: (id) => items.find((i) => i.event_id === id) };
}
