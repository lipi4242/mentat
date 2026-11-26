// /help es "sugo" Telegramon: a hid az agens mentat_help.py-jat futtatja, es a kimenetet
// valaszkent kuldi — a pane-be nem megy, LLM nem fogalmaz. Az allowlist es a mention-kapu
// elotte all, valtozatlanul; hiba eseten a sima kezbesites marad.
import test from "node:test";
import assert from "node:assert/strict";
import { mkdirSync, writeFileSync, chmodSync } from "node:fs";
import { join } from "node:path";
import { tempDir } from "./tmp.mjs";
import { createHandlers } from "../lib/handlers.mjs";
import { helpRequest, runHelp, createHelp, forTelegram } from "../lib/help.mjs";

function fakeRepo(body = 'import sys; print("SUGO " + " ".join(sys.argv[1:]))') {
  const repo = tempDir("hid-sugo-");
  mkdirSync(join(repo, ".mentat", "bin"), { recursive: true });
  writeFileSync(join(repo, ".mentat", "bin", "mentat_help.py"), body);
  chmodSync(join(repo, ".mentat", "bin", "mentat_help.py"), 0o644);
  return repo;
}

test("helpRequest: /help, /help@bot, sugo/súgó, opcionalis status|todo; mas nem", () => {
  const ok = [["/help", ""], ["/help@botty", ""], ["  /HELP  ", ""], ["súgó", ""], ["Sugo", ""],
    ["/help status", "status"], ["súgó todo", "todo"], ["@botty /help", ""], ["@botty súgó status", "status"]];
  for (const [t, arg] of ok) assert.deepEqual(helpRequest(t, "botty"), { arg }, t);
  for (const t of ["help", "/helpme", "kérek súgót", "/help rm -rf", "/help status x", "/start", ""])
    assert.equal(helpRequest(t, "botty"), null, t);
});

test("runHelp: a repo mentat_help.py-ja fut, a kimenete jon vissza; nincs eszkoz -> null", () => {
  const repo = fakeRepo();
  assert.equal(runHelp({ repo, arg: "" }), "SUGO");
  assert.equal(runHelp({ repo, arg: "status" }), "SUGO status");
  assert.equal(runHelp({ repo: tempDir("hid-ures-"), arg: "" }), null);
  assert.equal(runHelp({ repo: fakeRepo("import sys; sys.exit(3)"), arg: "" }), null);
});

function harness(onHelp) {
  const delivered = [], logged = [];
  const h = createHandlers({
    groupId: "-100", allowIds: ["1"], requireMention: false, maxFileBytes: 1e6,
    bot: () => ({ username: "botty", id: 99 }),
    deliver: (l) => delivered.push(l), enqueueMedia: () => {}, logInbound: (r) => logged.push(r), onHelp,
  });
  return { h, delivered, logged };
}
const msg = (o = {}) => ({ message_id: 7, date: 1, chat: { id: -100, type: "group" },
  from: { id: 1, first_name: "J" }, text: "/help", ...o });

test("handler: allowlistes /help -> onHelp, a pane-be semmi; naplosor kind=help", () => {
  const calls = [];
  const { h, delivered, logged } = harness((r) => { calls.push(r); return true; });
  h.handleMessage(msg());
  assert.equal(calls.length, 1);
  assert.deepEqual([calls[0].text, calls[0].chatId, calls[0].messageId], ["/help", "-100", 7]);
  assert.equal(delivered.length, 0);
  assert.equal(logged[0].kind, "help");
});

test("handler: nem allowlistes kuldo /help-je el sem jut az onHelp-ig (az allowlist elotte all)", () => {
  const calls = [];
  const { h, delivered } = harness((r) => { calls.push(r); return true; });
  h.handleMessage(msg({ from: { id: 2, first_name: "Idegen" } }));
  assert.equal(calls.length, 0);
  assert.equal(delivered.length, 0);
});

test("handler: ha a sugo nem all elo (onHelp false), sima kezbesites; szerkesztett /help is sima", () => {
  const { h, delivered } = harness(() => false);
  h.handleMessage(msg());
  assert.equal(delivered.length, 1);
  const calls = [];
  const b = harness((r) => { calls.push(r); return true; });
  b.h.handleMessage(msg(), { edited: true });
  assert.equal(calls.length, 0);
  assert.equal(b.delivered.length, 1);
});

test("createHelp: a kimenet valaszkent megy a chatbe; kuldesi hibanal a pane kapja", async () => {
  const repo = fakeRepo();
  const sent = [], fallback = [];
  const help = createHelp({ resolveRepo: () => repo, tg: async (m, p) => { sent.push([m, p]); return { body: { ok: true } }; },
    log: () => {} });
  assert.equal(help({ text: "szia", chatId: "-100", messageId: 6, fallback: () => {} }), false, "not a help request");
  assert.equal(help({ text: "súgó todo", chatId: "-100", messageId: 7, fallback: () => fallback.push(1) }), true);
  await new Promise((r) => setTimeout(r, 20));
  assert.deepEqual(sent[0], ["sendMessage", { chat_id: "-100", text: "SUGO todo", reply_to_message_id: 7 }]);
  const bad = createHelp({ resolveRepo: () => repo, tg: async () => { throw new Error("net"); }, log: () => {} });
  bad({ text: "/help", chatId: "-100", messageId: 8, fallback: () => fallback.push(2) });
  await new Promise((r) => setTimeout(r, 20));
  assert.deepEqual(fallback, [2]);
  const none = createHelp({ resolveRepo: () => null, tg: async () => ({}), log: () => {} });
  assert.equal(none({ text: "/help", chatId: "-100", messageId: 9, fallback: () => {} }), false);
});

test("forTelegram: a /mentat parancsnevek /help-re cserelodnek, mas nem", () => {
  assert.equal(forTelegram("1. /mentat status\n/mentat todo     x\n/mentat\n/whoami · /fleet:roster"),
    "1. /help status\n/help todo     x\n/help\n/whoami · /fleet:roster");
  assert.equal(forTelegram("Következő lépés: a todo bekapcsolása: /mentat todo"),
    "Következő lépés: a todo bekapcsolása: /help todo");
  assert.equal(forTelegram("~/src/mentat/admin és github.com/lipi4242/mentat/tree"),
    "~/src/mentat/admin és github.com/lipi4242/mentat/tree", "paths and URLs stay");
});

test("createHelp: a kuldott szovegben /help all, nem /mentat", async () => {
  const sent = [];
  const help = createHelp({ resolveRepo: () => "x", run: () => "Lépés: /mentat todo", log: () => {},
    tg: async (m, p) => { sent.push(p.text); return { body: { ok: true } }; } });
  help({ text: "/help status", chatId: "-1", messageId: 1, fallback: () => {} });
  await new Promise((r) => setTimeout(r, 10));
  assert.deepEqual(sent, ["Lépés: /help todo"]);
});
