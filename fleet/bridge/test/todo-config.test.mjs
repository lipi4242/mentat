// Todo-ebresztes: a box todo-beallitasa (~/.config/todo), a token sosem latszik.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { parseTodoConfig, MAX_POLL_MS } from "../lib/todo-config.mjs";
import { loadConfig } from "../lib/config.mjs";
import { box, TOKEN, wire } from "./todo-fixture.mjs";

test("todo-config: a box-konvenciobol BE; a handle a handles-fajlbol, az agens a state-konyvtar neve", () => {
  const b = box({ handles: "thufir=thufir\n" });
  const c = parseTodoConfig(b.env, b.stateDir);
  assert.equal(c.enabled, true);
  assert.equal(c.handle, "thufir");
  assert.ok(c.tokenFile.endsWith("thufir.token"));
  assert.ok(c.pollMs <= MAX_POLL_MS);
  assert.ok(!JSON.stringify(c).includes(TOKEN), "a token erteke nincs a configban");
});

test("todo-config: nincs todo a boxon -> csendben KI; HOME nelkul sem nyul a futtato gepehez", () => {
  const b = box();
  assert.deepEqual(parseTodoConfig({ HOME: join(b.home, "nincs") }, b.stateDir), { enabled: false, reason: null });
  assert.deepEqual(parseTodoConfig({}, b.stateDir), { enabled: false, reason: null });
  assert.equal(parseTodoConfig({ ...b.env, BRIDGE_TODO: "off" }, b.stateDir).reason, "BRIDGE_TODO=off");
});

test("todo-config: masnak olvashato token -> KI okkal, a token erteke nem jelenik meg", () => {
  const b = box({ mode: 0o644 });
  const c = parseTodoConfig(b.env, b.stateDir);
  assert.equal(c.enabled, false);
  assert.match(c.reason, /chmod 600/);
  assert.ok(!c.reason.includes(TOKEN));
});

test("todo-config: a poll-periodus legfeljebb 60 s, akarmit allitanak", () => {
  const b = box();
  assert.equal(parseTodoConfig({ ...b.env, BRIDGE_TODO_POLL_MS: "600000" }, b.stateDir).pollMs, 60_000);
  assert.equal(parseTodoConfig({ ...b.env, BRIDGE_TODO_POLL_MS: "x" }, b.stateDir).pollMs, 20_000);
});

test("todo-config: a hid CFG-jeben ott (loadConfig), a tobbi mezo valtozatlan", () => {
  const b = box();
  const CFG = loadConfig({ TELEGRAM_BOT_TOKEN: "t", TELEGRAM_GROUP_CHAT_ID: "-1", TELEGRAM_ALLOWLIST_IDS: "1",
    TMUX_SESSION: "thufir", ...b.env });
  assert.equal(CFG.todo.enabled, true);
});

test("todo-wire: KI allapotban a health megmondja, miert", () => {
  const w = wire({ b: box({ mode: 0o640 }) });
  assert.match(w.health().todo_wake, /^off: .*chmod 600/);
  assert.ok(!readFileSync(w.CFG.healthFile, "utf8").includes(TOKEN));
});

test("hid-drot: a createBridge beköti (todo=on), egy kor halozat nelkul lefut, a health on", async () => {
  const { createBridge } = await import("../bridge.mjs");
  const { fakeApi } = await import("./todo-fixture.mjs");
  const b = box();
  const CFG = loadConfig({ TELEGRAM_BOT_TOKEN: "t", TELEGRAM_GROUP_CHAT_ID: "-1", TELEGRAM_ALLOWLIST_IDS: "1",
    TMUX_SESSION: "thufir", ...b.env });
  const api = fakeApi();
  const br = createBridge(CFG, { todoFetch: api.fetch });
  assert.match(br.todo.summary, /^todo=on handle=thufir poll=20s$/);
  await br.todo.tick();
  const h = JSON.parse(readFileSync(CFG.healthFile, "utf8"));
  assert.equal(h.todo_wake, "on");
  assert.ok(h.todo_last_poll_ok > 0);
  br.webhook.stop();
});

test("health: a todo-mezok irasa nem frissiti a written_at-ot (a csatorna-jel a Telegram-pollert meri)", async () => {
  const { writeHealth } = await import("../lib/health.mjs");
  const { writeFileSync } = await import("node:fs");
  const b = box();
  const f = join(b.stateDir, "telegram-state", "health.json");
  writeFileSync(f, JSON.stringify({ written_at: 1, last_poll_ok: 1 }));
  writeHealth(f, { todo_last_poll_ok: 5 }, { stamp: false });
  const h = JSON.parse(readFileSync(f, "utf8"));
  assert.equal(h.written_at, 1);
  assert.equal(h.todo_last_poll_ok, 5);
  writeHealth(f, { last_poll_ok: 9 });
  assert.ok(JSON.parse(readFileSync(f, "utf8")).written_at > 1);
});
