#!/usr/bin/env node
// todo-once.mjs — EGY todo-ebresztes kor hid nelkul (desktop session), ugyanazzal a koddal, mint a hid.
//   node todo-once.mjs --session-start | --prompt        (stdin: a Claude Code hook-JSON-ja, `cwd`-vel)
//
// A fleet plugin SessionStart + UserPromptSubmit hookja futtatja (a plugin hooks/todo/ alatt ennek a
// fajlnak es a lib/ todo-reszenek BAJTRA AZONOS masolata el; test/todo-plugin-copy.test.mjs orzi).
// Ugyanaz a relevancia, sor-formatum, kurzor, sajat-iras-szures, nyugta-konyveles es elszabadulas-fek,
// mint a hidban (lib/todo-wire.mjs); a kulonbseg csak az, hogy a sor a stdoutra megy (a hook ezt a
// kontextusba teszi), es az egy futason beluli esemenyek mind egy sorba vonodnak.
// AZ EGYETLEN ELVI KULONBSEG: a lezart desktop sessiont semmi nem ebreszti fel — az esemeny addig var,
// amig valaki nem ir a sessionbe (vagy uj sessiont nem nyit).
//
// Beallitas: a box-konvencio (lib/todo-config.mjs) vagy TODO_API/TODO_HANDLE/TODO_TOKEN_FILE; az agens a
// FLEET_AGENT vagy a repo .claude/fleet.json-ja. Allapot + health + kezbesitesi naplo:
// $XDG_STATE_HOME/mentat/todo/<agens>/ (alapbol ~/.local/state). Friss todo-ebresztos hid ugyanennek az
// agensnek: nema (a hid mar szolt). Barmi hiba: exit 0 — a hook sosem akaszthatja meg az uzenetet.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseTodoConfig } from "./lib/todo-config.mjs";
import { createTodoWire } from "./lib/todo-wire.mjs";
import { createInboundLogger } from "./lib/inbox.mjs";
import { loadJson } from "./lib/jsonfile.mjs";

export const STALE_MS = 10 * 60_000;
const NOTE = "(desktop: valódi ébresztés nincs — a session elején és minden új üzenetednél nézem; a lezárt sessiont semmi nem ébreszti)";
const quiet = () => {};

function agentOf(env, cwd) {
  if (env.FLEET_AGENT) return env.FLEET_AGENT;
  try { return JSON.parse(readFileSync(join(cwd, ".claude", "fleet.json"), "utf8")).agent || ""; } catch { return ""; }
}

export async function runOnce({ argv = process.argv.slice(2), env = process.env, input = "", fetchFn, now = Date.now } = {}) {
  const start = argv.includes("--session-start");
  let cwd = ".";
  try { cwd = JSON.parse(input || "{}").cwd || "."; } catch { /* nincs hook-JSON */ }
  const agent = agentOf(env, cwd);
  if (!env.HOME || (!agent && !env.TODO_HANDLE)) return [];
  // A hid fedi: friss todo-poll ugyanennek az agensnek -> nema (ne szoljon ketszer).
  if (agent) {
    const h = loadJson(join(env.HOME, ".config", agent, "telegram-state", "health.json"), {}, quiet);
    if (h.todo_wake === "on" && now() - Number(h.todo_last_poll_ok || 0) < STALE_MS) return [];
  }
  const dir = join(env.XDG_STATE_HOME || join(env.HOME, ".local", "state"), "mentat", "todo", agent || env.TODO_HANDLE);
  const todo = parseTodoConfig(env, dir, { agent, stateFile: join(dir, "todo-state.json") });
  if (!todo.enabled) return todo.reason && start ? [`[todo] a todo-figyelés KI: ${todo.reason} ${NOTE}`] : [];
  // Egy futason belul minden uj esemeny egy sor (coalesce 0: nincs kovetkezo kor, amire varni lehetne).
  const CFG = { todo: { ...todo, coalesceMs: 0 }, healthFile: join(dir, "health.json"), inboxDir: join(dir, "log") };
  const lines = [];
  const wire = createTodoWire(CFG, { deliver: (l) => lines.push(l), log: quiet, now, timeoutMs: 4000,
    alert: async (t) => { lines.push(`[todo] FIGYELEM: ${t}`); }, ...(fetchFn ? { fetchFn } : {}),
    logInbound: createInboundLogger({ inboxDir: CFG.inboxDir, healthFile: CFG.healthFile }) });
  await wire.tick();
  // Health a desktopon is: az utolso sikeres poll kora, feldolgozatlan ebresztesek (ugyanazok a mezok).
  const h = loadJson(CFG.healthFile, {}, quiet);
  const okAt = Number(h.todo_last_poll_ok || 0);
  const out = [];
  if (now() - okAt > STALE_MS) {
    out.push(`[todo] a todo-figyelés NEM MŰKÖDIK: ${okAt ? `${Math.round((now() - okAt) / 60_000)} perce` : "még soha"} nincs sikeres lekérés`
      + `${h.todo_last_error ? ` (${h.todo_last_error})` : ""} ${NOTE}`);
  }
  if (lines.length) out.push(`[todo] új esemény a labdádon ${NOTE}:`, ...lines);
  if (start && !lines.length && !out.length) {
    const n = Number(h.todo_unhandled || 0);
    out.push(`[todo] nincs új todo-esemény; utolsó sikeres lekérés most${n ? `; ${n} korábbi ébresztés feldolgozatlan` : ""} ${NOTE}`);
  }
  return out;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  let input = "";
  try { input = readFileSync(0, "utf8"); } catch { /* nincs stdin */ }
  runOnce({ input }).then((out) => { if (out.length) console.log(out.join("\n")); })
    .catch(() => {}).finally(() => process.exit(0));
}
