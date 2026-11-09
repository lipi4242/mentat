// Kozos kornyezet a todo-ebresztes tesztjeihez (nem teszt-fajl: a glob nem futtatja).
// Izolalt HOME (tmp), hamis todo API (fetch-csere, halozat nelkul), stub inject.
import { chmodSync, mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { tempDir } from "./tmp.mjs";
import { parseTodoConfig } from "../lib/todo-config.mjs";
import { createDeliverer } from "../lib/deliverer.mjs";
import { createTodoWire } from "../lib/todo-wire.mjs";
import { createInboundLogger } from "../lib/inbox.mjs";

export const TOKEN = "mt_HAMIS_todo_token_0123456789abcdef";
export const API = "https://admin.example/api/todo/v1";

export function box({ token = TOKEN, mode = 0o600, handles = "thufir=thufir\n" } = {}) {
  const home = tempDir("todo-home-");
  const cfg = join(home, ".config", "todo");
  mkdirSync(cfg, { recursive: true });
  writeFileSync(join(cfg, "env"), `TODO_API=${API}\n`);
  writeFileSync(join(cfg, "handles"), handles);
  const tf = join(cfg, "thufir.token");
  writeFileSync(tf, `${token}\n`);
  chmodSync(tf, mode);
  const stateDir = join(home, ".config", "thufir");
  mkdirSync(join(stateDir, "telegram-state"), { recursive: true });
  return { home, stateDir, env: { HOME: home, BRIDGE_STATE_DIR: stateDir } };
}

// A todo worker /changes, /me, /principals, /tasks/:id, /items/:id valaszai memoriabol.
export function fakeApi() {
  const s = { events: [], tasks: {}, items: {}, seq: 0, calls: [], fail: null,
    principals: [{ id: "P_ME", handle: "thufir" }, { id: "P_KRISZ", handle: "krisz" }, { id: "P_KATA", handle: "kata" },
      { id: "P_MAC", handle: "thufir_mac" }] };
  s.add = (kind, actor, task, diff = {}, at = new Date().toISOString()) => {
    s.events.push({ seq: ++s.seq, op_id: `op${s.seq}`, task_id: task, at, actor_id: actor, kind,
      diff_json: JSON.stringify(diff), recipients_json: "[]" });
    return s.seq;
  };
  s.fetch = async (url, opts) => {
    s.calls.push({ url: String(url), token: opts.headers["X-Mentat-Token"], ua: opts.headers["User-Agent"] });
    if (s.fail) return { ok: false, status: s.fail, json: async () => ({ error: "x" }) };
    const u = new URL(url);
    const p = u.pathname.replace(/^\/api\/todo\/v1/, "");
    const ok = (body) => ({ ok: true, status: 200, json: async () => body });
    if (p === "/me") return ok({ id: "P_ME", handle: "thufir" });
    if (p === "/principals") return ok(s.principals);
    if (p === "/changes") {
      const since = Number(u.searchParams.get("since")), limit = Number(u.searchParams.get("limit"));
      return ok(s.events.filter((e) => e.seq > since).slice(0, limit));
    }
    const m = /^\/(tasks|items)\/(.+)$/.exec(p);
    const row = m && (m[1] === "tasks" ? s.tasks : s.items)[decodeURIComponent(m[2])];
    return row ? ok(row) : { ok: false, status: 404, json: async () => ({ error: "not found" }) };
  };
  return s;
}

// A teljes hid-oldali lanc: config -> drot -> deliverer (stub inject). clock.t a "most".
export function wire({ env = {}, inject = () => ({ ok: true }), b = box(), alerts = [] } = {}) {
  const api = fakeApi();
  const clock = { t: Date.parse("2026-11-08T10:00:00Z") };
  const injected = [];
  const CFG = { todo: parseTodoConfig({ ...b.env, ...env }, b.stateDir), healthFile: join(b.stateDir, "telegram-state", "health.json"),
    inboxDir: join(b.stateDir, "telegram-inbox") };
  const delivery = createDeliverer({ session: "s", pendingFile: join(b.stateDir, "telegram-state", "p.json"), maxPending: 50,
    pendingAlertMs: 1e12, healthFile: CFG.healthFile, label: "thufir",
    inject: (_s, line) => { const r = inject(line); if (r.ok) injected.push(line); return r; } });
  const logs = [];
  const w = createTodoWire(CFG, { deliver: delivery.deliver, fetchFn: api.fetch, now: () => clock.t,
    log: (...a) => logs.push(a.join(" ")), alert: async (t) => { alerts.push(t); },
    logInbound: createInboundLogger({ inboxDir: CFG.inboxDir, healthFile: CFG.healthFile }) });
  const health = () => JSON.parse(readFileSync(CFG.healthFile, "utf8"));
  const deliveryRows = () => {
    const f = join(CFG.inboxDir, `delivery-${new Date().toISOString().slice(0, 10)}.jsonl`);
    return existsSync(f) ? readFileSync(f, "utf8").trim().split("\n").map((l) => JSON.parse(l)) : [];
  };
  return { api, clock, injected, CFG, w, delivery, logs, alerts, health, deliveryRows, b };
}

export const task = (id, over = {}) => ({ id, kind: "todo", title: `Cím ${id}`, owner_id: "P_KRISZ", assignee_id: "P_ME", ...over });
