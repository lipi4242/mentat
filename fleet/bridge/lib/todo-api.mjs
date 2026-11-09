// lib/todo-api.mjs — a todo API (Mentat Admin todo plugin) olvaso klense a hidnak.
// Csak GET: /me, /principals, /changes, /tasks/:id, /items/:id. Fejlec: X-Mentat-Token, sajat
// User-Agent (a Cloudflare a gyari UA-t 403-mal utasitja el, lasd anytime_todo/api.py).
// Hivasonkent fali oras idokorlat: egy elakadt fetch kulonben orokre fagyasztana a pollert.
// A hibaszovegben sosincs token: a hiba HTTP-kod vagy a halozati hiba neve, a torzs nem.
import { readToken } from "./todo-config.mjs";

export const TIMEOUT_MS = 10_000;

export class TodoApiError extends Error {
  constructor(message, status = null) { super(message); this.status = status; }
}

export function createTodoApi({ api, tokenFile, version = "0", fetchFn = globalThis.fetch, timeoutMs = TIMEOUT_MS }) {
  const base = api.replace(/\/+$/, "");
  async function get(path, query = {}) {
    const url = new URL(base + path);
    for (const [k, v] of Object.entries(query)) url.searchParams.set(k, String(v));
    const token = readToken(tokenFile); // dob: a hivo ugyanugy kezeli, mint egy API-hibat
    let res;
    try {
      // redirect:"error": a fetch a sajat fejlecet (a tokent) egy masik hostra is tovabbvinne.
      res = await fetchFn(url, { method: "GET", redirect: "error", signal: AbortSignal.timeout(timeoutMs),
        headers: { "X-Mentat-Token": token, Accept: "application/json", "User-Agent": `mentat-sub-etha/${version}` } });
    } catch (e) {
      throw new TodoApiError(`todo API elérhetetlen (${e?.name === "TimeoutError" ? "timeout" : e?.cause?.code || e?.name || "hiba"})`);
    }
    if (!res.ok) throw new TodoApiError(`todo API ${path.split("?")[0].replace(/\/[^/]{12,}$/, "/:id")}: HTTP ${res.status}`, res.status);
    try { return await res.json(); } catch { throw new TodoApiError(`todo API ${path}: nem JSON válasz`); }
  }
  return {
    me: () => get("/me"),
    principals: () => get("/principals"),
    changes: (handle, since, limit = 100) => get("/changes", { for: handle, since, limit }),
    task: (id) => get(`/tasks/${encodeURIComponent(id)}`),
    item: (id) => get(`/items/${encodeURIComponent(id)}`),
  };
}
