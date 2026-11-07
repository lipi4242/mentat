// F-17 (CISO 2026-10-24): engedelykero ablaknal a hid se szoveget, se Entert nem kuld.
import test from "node:test";
import assert from "node:assert/strict";
import { join } from "node:path";
import { permissionDialog, capturePane } from "../lib/pane-guard.mjs";
import { injectLine } from "../lib/inject.mjs";
import { createDeliverer } from "../lib/deliverer.mjs";
import { tempDir } from "./tmp.mjs";

const DIALOG = [
  "⏺ Bash(rm -rf $D/$n)",
  "╭──────────────────────────────────────────────╮",
  "│ Bash command                                 │",
  "│   rm -rf $D/$n                               │",
  "│ Do you want to proceed?                      │",
  "│ ❯ 1. Yes                                     │",
  "│   2. No, and tell Claude what to do (esc)    │",
  "╰──────────────────────────────────────────────╯",
].join("\n");
const EDIT = "Do you want to make this edit to kapu.py?\n❯ 1. Yes\n  2. Yes, and don't ask again\n  3. No";

test("permissionDialog: a valodi ablakalakok", () => {
  assert.equal(permissionDialog(DIALOG), true);
  assert.equal(permissionDialog(EDIT), true);
  assert.equal(permissionDialog("x\n".repeat(500) + DIALOG), true, "a pane alja szamit");
});

test("permissionDialog: nem ablak — kerdes vagy opcio onmagaban, regi ablak a pane tetejen", () => {
  assert.equal(permissionDialog("⏺ Do you want to proceed? Megnezem.\n> "), false);
  assert.equal(permissionDialog("1. Yes, ez az elso pont\n2. No"), false);
  assert.equal(permissionDialog(DIALOG + "\n" + "kesz.\n".repeat(60) + "> "), false);
  for (const x of [null, undefined, "", 42, {}]) assert.equal(permissionDialog(x), false);
});

test("capturePane: hiba, dobas, nem-szoveg -> null", () => {
  assert.equal(capturePane("s", () => ({ status: 1 })), null);
  assert.equal(capturePane("s", () => { throw new Error("x"); }), null);
  assert.equal(capturePane("s", () => ({ status: 0, stdout: 5 })), null);
  assert.equal(capturePane("s", () => ({ status: 0, stdout: "ok" })), "ok");
});

function spawnWithPane(paneText) {
  const keys = [];
  const fn = (cmd, args) => {
    if (args[0] === "capture-pane") return { status: 0, stdout: paneText };
    keys.push(args);
    return { status: 0 };
  };
  return { fn, keys };
}

test("injectLine: ablaknal SEMMI nem megy ki (se szoveg, se Enter)", () => {
  const { fn, keys } = spawnWithPane(DIALOG);
  const res = injectLine("s", "1", fn);
  assert.equal(res.ok, false);
  assert.equal(res.dialog, true);
  assert.match(res.error, /engedélykérő ablak/);
  assert.deepEqual(keys, []);
});

test("injectLine: ablak nelkul es olvashatatlan pane-nel a regi ut fut", () => {
  const { fn, keys } = spawnWithPane("> ");
  assert.deepEqual(injectLine("s", "szia", fn), { ok: true });
  assert.equal(keys.length, 2);
  const keys2 = [];
  const fn2 = (cmd, args) => (args[0] === "capture-pane" ? { status: 1 } : (keys2.push(args), { status: 0 }));
  assert.deepEqual(injectLine("s", "szia", fn2), { ok: true });
  assert.equal(keys2.length, 2);
});

test("deliverer: ablaknal a sor pending-be megy, a riasztas megnevezi az okot", async () => {
  const d = tempDir("paneguard-");
  const alerts = [];
  const del = createDeliverer({
    session: "s", pendingFile: join(d, "p.json"), maxPending: 10, pendingAlertMs: -1,
    healthFile: join(d, "h.json"), label: "Rilí", alert: async (m) => alerts.push(m),
    inject: (s, line) => injectLine(s, line, spawnWithPane(DIALOG).fn),
  });
  del.deliver("1");
  assert.equal(del.depth(), 1);
  await del.retryPending();
  assert.equal(del.depth(), 1);
  assert.match(alerts.join("\n"), /engedélykérő ablak/);
});
