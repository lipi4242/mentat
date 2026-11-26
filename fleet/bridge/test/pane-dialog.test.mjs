// Engedelykero ablak a pane-ben: az ok kiolvasasa, a riasztas, es a tulajdonos valasza
// Telegramrol — csak ugyanarra az ablakra (ujjlenyomat), Enter nelkul, magatol soha.
import test from "node:test";
import assert from "node:assert/strict";
import { readDialog } from "../lib/pane-dialog.mjs";
import { dialogCommand } from "../lib/dialog-wire.mjs";
import { PRIVACY, BOXED, setup } from "./fixtures/pane-dialog.mjs";

test("readDialog: a hook-ablak oka, kerdese, opcioi; stabil ujjlenyomat", () => {
  const d = readDialog("korabbi kimenet\n".repeat(30) + PRIVACY);
  assert.equal(d.source, "[plugin:cc-plugin-privacy]");
  assert.equal(d.hook, "Hook tool.check requires confirmation for this command:");
  assert.equal(d.why, "This call's input holds your account email address, which may leave this machine.");
  assert.equal(d.question, "Do you want to proceed?");
  assert.deepEqual(d.options, [{ key: "1", label: "Yes" }, { key: "2", label: "No" }]);
  assert.match(d.fingerprint, /^[0-9a-f]{12}$/);
  assert.equal(readDialog(PRIVACY + "\n").fingerprint, readDialog(PRIVACY).fingerprint);
  assert.notEqual(readDialog(PRIVACY.replace("draft.py", "other.py")).fingerprint, d.fingerprint);
});

test("readDialog: keretes ablak — cim az ok, a parancs torzse nem kerul ki", () => {
  const d = readDialog(BOXED);
  assert.equal(d.source, "Bash command");
  assert.equal(d.why, "");
  assert.equal(d.options.length, 3);
  assert.equal(d.options[2].label, "No, and tell Claude what to do (esc)");
});

test("readDialog: nem ablak -> null", () => {
  for (const t of [null, "", "⏺ Do you want to proceed? Megnezem.\n> ", "1. Yes\n2. No"])
    assert.equal(readDialog(t), null);
});

test("dialogCommand: /igen, /nem, @bot, opcionalis kod; mas nem", () => {
  assert.deepEqual(dialogCommand("/igen"), { answer: "igen", code: "" });
  assert.deepEqual(dialogCommand(" /NEM@botty a1b2c3 "), { answer: "nem", code: "a1b2c3" });
  for (const t of ["igen", "/igenis", "/nem 1; rm", "/help", ""]) assert.equal(dialogCommand(t), null, t);
});

test("watch: riasztas a turelmi ido utan, okkal es parancsokkal; egyszeri ujrariasztas /nem javaslattal", () => {
  const s = setup(PRIVACY);
  s.tick(0);
  assert.equal(s.alerts.length, 0, "egy pillanatnyi ablak meg nem riaszt");
  s.tick(60_000);
  assert.equal(s.alerts.length, 1);
  assert.match(s.alerts[0], /\[plugin:cc-plugin-privacy\]/);
  assert.match(s.alerts[0], /account email address/);
  assert.match(s.alerts[0], /1\. Yes · 2\. No/);
  assert.match(s.alerts[0], /\/igen/);
  assert.match(s.alerts[0], /magamtól nem válaszolok/);
  s.tick(5 * 60_000);
  assert.equal(s.alerts.length, 1);
  s.tick(5 * 60_000);
  assert.equal(s.alerts.length, 2);
  assert.match(s.alerts[1], /\/nem/);
  s.tick(30 * 60_000);
  assert.equal(s.alerts.length, 2, "csak egyszer riaszt ujra");
  assert.deepEqual(s.tmux.keys, [], "magatol soha nem nyom semmit");
});

test("answer: /igen ugyanarra az ablakra -> az opcio szama, Enter nelkul, naplozva", async () => {
  const s = setup(PRIVACY);
  s.tick(0); s.tick(60_000);
  assert.equal(s.answer({ text: "/igen", chatId: "-1", messageId: 7, fromId: "42" }), "dialog");
  assert.deepEqual(s.tmux.keys, [["send-keys", "-t", "s", "-l", "--", "1"]]);
  assert.ok(s.logs.some((l) => /from=42/.test(l) && /billentyű=1/.test(l)));
  await new Promise((r) => setImmediate(r));
  assert.match(s.t.sent[0].text, /elküldtem: 1\. Yes/);
  s.tick(20 * 60_000);
  assert.equal(s.alerts.length, 1, "megvalaszolt ablakra nincs ujrariasztas");
});

test("answer: /nem a No opciot valasztja (harom opcional is)", () => {
  const s = setup(BOXED);
  s.tick(0); s.tick(60_000);
  s.answer({ text: "/nem", chatId: "-1", messageId: 7, fromId: "42" });
  assert.deepEqual(s.tmux.keys, [["send-keys", "-t", "s", "-l", "--", "3"]]);
});

test("answer: nem kuld semmit — idegen kuldo, nincs ablak, mas ablak, nem riasztott ablak, rossz kod", async () => {
  const s = setup(PRIVACY);
  s.answer({ text: "/igen", chatId: "-1", messageId: 1, fromId: "42" }); // meg nem riasztott
  s.tick(0); s.tick(60_000);
  s.answer({ text: "/igen", chatId: "-1", messageId: 2, fromId: "99" }); // nem a tulajdonos
  s.answer({ text: "/igen ffffff", chatId: "-1", messageId: 3, fromId: "42" }); // rossz kod
  s.tmux.state.pane = PRIVACY.replace("draft.py", "other.py");
  s.answer({ text: "/igen", chatId: "-1", messageId: 4, fromId: "42" }); // megvaltozott ablak
  s.tmux.state.pane = "kesz.\n> ";
  s.answer({ text: "/nem", chatId: "-1", messageId: 5, fromId: "42" }); // eltunt
  assert.deepEqual(s.tmux.keys, []);
  await new Promise((r) => setImmediate(r));
  assert.equal(s.t.sent.length, 5, "minden elutasitas valaszt kap");
  assert.ok(s.t.sent.every((m) => /nem küldtem semmit/.test(m.text)));
});

test("answer: nem parancs -> false (a sima kezbesites marad)", () => {
  const s = setup(PRIVACY);
  assert.equal(s.answer({ text: "szia", chatId: "-1", messageId: 1, fromId: "42" }), false);
});

test("answer: a riasztasban latott kod is eleg, ha az az ablak all", () => {
  const s = setup(PRIVACY);
  s.tick(0); s.tick(60_000);
  const fp = readDialog(PRIVACY).fingerprint.slice(0, 6);
  assert.equal(s.answer({ text: `/igen ${fp}`, chatId: "-1", messageId: 1, fromId: "42" }), "dialog");
  assert.equal(s.tmux.keys.length, 1);
});
