// Engedelykero ablak — a bekotes: handler (/igen nem megy a pane-be), createBridge, config.
import test from "node:test";
import assert from "node:assert/strict";
import { createHandlers } from "../lib/handlers.mjs";
import { loadConfig } from "../lib/config.mjs";
import { createBridge } from "../bridge.mjs";
import { tempDir } from "./tmp.mjs";
import { PRIVACY, fakeTmux, setup } from "./fixtures/pane-dialog.mjs";

test("handler: allowlistes /igen -> a valaszolo kapja, a pane-be sor nem megy, naplo kind=dialog", () => {
  const s = setup(PRIVACY);
  s.tick(0); s.tick(60_000);
  const delivered = [], logged = [];
  const h = createHandlers({ groupId: "-1", allowIds: ["42"], requireMention: false, maxFileBytes: 1,
    bot: () => ({ username: "botty", id: 5 }), deliver: (l) => delivered.push(l), enqueueMedia: () => {},
    logInbound: (r) => logged.push(r), onHelp: (a) => s.answer(a) || false });
  h.handleMessage({ message_id: 9, date: 1, chat: { id: -1, type: "group" }, from: { id: 42, first_name: "K" }, text: "/igen" });
  assert.deepEqual(delivered, []);
  assert.equal(logged[0].kind, "dialog");
  assert.deepEqual(s.tmux.keys, [["send-keys", "-t", "s", "-l", "--", "1"]]);
});

test("createBridge: a watch es a valaszolo a deps.spawn-on at latja a pane-t; riasztas nelkul nem valaszol", () => {
  const tmux = fakeTmux(PRIVACY);
  const cfg = loadConfig({ TELEGRAM_BOT_TOKEN: "t", TELEGRAM_GROUP_CHAT_ID: "-100", TELEGRAM_ALLOWLIST_IDS: "42",
    TMUX_SESSION: "s", BRIDGE_STATE_DIR: tempDir("dlg-"), BRIDGE_REQUIRE_MENTION: "false",
    SUBETHA_TELEGRAM_API: "http://127.0.0.1:9" });
  const b = createBridge(cfg, { spawn: tmux.spawn });
  b.dialogs.check();
  assert.equal(b.dialogs.alerted(), null, "turelmi ido elott nincs riasztas");
  b.processUpdate({ update_id: 1, message: { message_id: 3, date: 1, chat: { id: -100, type: "group" },
    from: { id: 42, first_name: "K" }, text: "/igen" } });
  assert.deepEqual(tmux.keys, []);
  assert.equal(b.delivery.depth(), 0, "a parancs nem kerult a pending-sorba");
});

test("config: ujrariasztas percben (alap 10), valaszolok alapbol az allowlist", () => {
  const base = { TELEGRAM_BOT_TOKEN: "t", TELEGRAM_GROUP_CHAT_ID: "-1", TELEGRAM_ALLOWLIST_IDS: "1, 2",
    TMUX_SESSION: "s", BRIDGE_STATE_DIR: "/x" };
  assert.equal(loadConfig(base).dialogReAlertMs, 600_000);
  assert.deepEqual(loadConfig(base).dialogAnswerIds, ["1", "2"]);
  const c = loadConfig({ ...base, BRIDGE_DIALOG_REALERT_MIN: "3", BRIDGE_DIALOG_ANSWER_IDS: "2" });
  assert.equal(c.dialogReAlertMs, 180_000);
  assert.deepEqual(c.dialogAnswerIds, ["2"]);
});
