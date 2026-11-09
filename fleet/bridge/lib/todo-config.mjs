// lib/todo-config.mjs — a todo-ebresztes beallitasa: hol a todo API, ki vagyok, hol a token.
//
// Ugyanaz a box-konvencio, amit a fleet/bin/mentat-todo es az engine anytime_todo/settings.py `_box`
// hasznal: ~/.config/todo/env (TODO_API=), ~/.config/todo/handles ("agens=handle", kulonben az agens
// neve), ~/.config/todo/<handle>.token (0600, egyetlen sor). Az agens neve: FLEET_AGENT, kulonben a
// BRIDGE_STATE_DIR utolso tagja (~/.config/<agens>). Az env (TODO_API / TODO_HANDLE / TODO_TOKEN_FILE)
// elsobbseget kap. A token ERTEKE sosem kerul naploba, health-be vagy hibauzenetbe: csak az utja.
//
// KI (nem hiba): nincs todo-beallitas a boxon, vagy BRIDGE_TODO=off. A beallitott, de hasznalhatatlan
// token (hianyzik, masnak olvashato, tobbsoros) KI + ok: a health ezt mutatja, a flotta-ellenorzes
// pirosnak jelzi (fleet/src/fleet/kepesseg.py).
import { readFileSync, statSync } from "node:fs";
import { basename, join } from "node:path";

export const DEFAULT_POLL_MS = 20_000;
export const MAX_POLL_MS = 60_000; // AC: legfeljebb percenkent
export const DEFAULT_COALESCE_MS = 60_000;
export const DEFAULT_HANDLED_MS = 30 * 60_000;

function dotenv(path, key) {
  let text;
  try { text = readFileSync(path, "utf8"); } catch { return null; }
  for (const raw of text.split("\n")) {
    const line = raw.trim().replace(/^export /, "");
    const i = line.indexOf("=");
    if (i > 0 && line.slice(0, i).trim() === key) return line.slice(i + 1).trim().replace(/^["']|["']$/g, "") || null;
  }
  return null;
}

const num = (v, def, min, max) => {
  const n = Number(v);
  return v != null && v !== "" && Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : def;
};

// A token beolvasasa (a hivas pillanataban, nem induláskor: a forgatott token is el).
// Dob: Error, ami csak az utat es az okot nevezi meg.
export function readToken(file) {
  let st, text;
  try { st = statSync(file); text = readFileSync(file, "utf8").trim(); } catch (e) {
    throw new Error(`todo token nem olvasható: ${file} (${e.code || "hiba"})`);
  }
  if (st.mode & 0o077) throw new Error(`todo token ${file} másnak is olvasható: chmod 600`);
  if (!text || text.includes("\n")) throw new Error(`todo token ${file}: pontosan egy token kell`);
  return text;
}

// opts (desktop, todo-once.mjs): { agent, stateFile } — a hid nelkuli session ugyanezzel a koddal fut.
export function parseTodoConfig(env, stateDir, opts = {}) {
  const off = (reason) => ({ enabled: false, reason });
  if ((env.BRIDGE_TODO || "").toLowerCase() === "off") return off("BRIDGE_TODO=off");
  const home = env.HOME; // a unit mindig adja; HOME nelkul (kezi teszt) nem nyulunk a futtato ~/.config-jahoz
  if (!home) return off(null);
  let cfg = join(env.XDG_CONFIG_HOME || join(home, ".config"), "todo");
  try { statSync(cfg); } catch { cfg = join(home, ".config", "todo"); }
  const agent = env.FLEET_AGENT || ("agent" in opts ? opts.agent || "" : stateDir ? basename(stateDir) : "");
  const api = (env.TODO_API || dotenv(join(cfg, "env"), "TODO_API") || "").replace(/\/+$/, "");
  if (!api) return off(null); // nincs todo ezen a boxon: csendben KI
  if (!/^https?:\/\//.test(api)) return off("TODO_API nem http(s) URL");
  const handle = env.TODO_HANDLE || (agent && dotenv(join(cfg, "handles"), agent)) || agent;
  if (!handle) return off("nincs ágens-név (FLEET_AGENT) és TODO_HANDLE");
  const tokenFile = env.TODO_TOKEN_FILE || join(cfg, `${handle}.token`);
  try { readToken(tokenFile); } catch (e) { return off(e.message); }
  const tsDir = join(stateDir, "telegram-state");
  return {
    enabled: true, reason: null, api, handle, tokenFile,
    pollMs: num(env.BRIDGE_TODO_POLL_MS, DEFAULT_POLL_MS, 1000, MAX_POLL_MS),
    coalesceMs: num(env.BRIDGE_TODO_COALESCE_MS, DEFAULT_COALESCE_MS, 0, 5 * 60_000),
    handledMs: num(env.BRIDGE_TODO_HANDLED_MS, DEFAULT_HANDLED_MS, 60_000, 24 * 3600_000),
    stateFile: env.BRIDGE_TODO_STATE_FILE || opts.stateFile || join(tsDir, "todo-state.json"),
  };
}
