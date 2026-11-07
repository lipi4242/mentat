import test from "node:test";
import assert from "node:assert/strict";
import { injectLine } from "../lib/inject.mjs";

// Fake spawnSync: rogziti a hivasokat, es a megadott eredmenyeket adja vissza.
// A pane-olvasas (capture-pane, F-17 or) ures pane-t ad, es nem szamit hivasnak.
function fakeSpawn(results) {
  const calls = [];
  const fn = (cmd, args, opts) => {
    if (args[0] === "capture-pane") return { status: 0, stdout: "" };
    calls.push({ cmd, args, opts });
    return results[calls.length - 1] ?? { status: 0 };
  };
  return { fn, calls };
}

test("injectLine: ket send-keys hivas, literal szoveg + Enter", () => {
  const { fn, calls } = fakeSpawn([{ status: 0 }, { status: 0 }]);
  const res = injectLine("beta", "[room x | bot gamma(-)]: szia", fn);

  assert.deepEqual(res, { ok: true });
  assert.equal(calls.length, 2);
  // A szoveg SOHA nem er shell-t: tomb-argv, `-l` literal, `--` opciok vege.
  assert.deepEqual(calls[0].args, [
    "send-keys", "-t", "beta", "-l", "--", "[room x | bot gamma(-)]: szia",
  ]);
  assert.equal(calls[0].cmd, "tmux");
  assert.equal(calls[0].opts.encoding, "utf8");
  assert.deepEqual(calls[1].args, ["send-keys", "-t", "beta", "Enter"]);
});

test("injectLine: a szoveg-hivas hibaja megallitja az Enter-t", () => {
  const { fn, calls } = fakeSpawn([{ status: 1, stderr: "no such session" }]);
  const res = injectLine("nincs", "hello", fn);

  assert.equal(res.ok, false);
  assert.match(res.error, /send-keys\(text\) failed: no such session/);
  assert.equal(calls.length, 1, "Enter nem mehet ki, ha a szoveg se ment");
});

test("injectLine: az Enter hibaja is {ok:false}", () => {
  const { fn } = fakeSpawn([{ status: 0 }, { status: 1, stderr: "boom" }]);
  const res = injectLine("s", "hello", fn);

  assert.equal(res.ok, false);
  assert.match(res.error, /send-keys\(Enter\) failed: boom/);
});

test("injectLine: spawn-hiba (status null, error objektum) sem dob", () => {
  const { fn } = fakeSpawn([{ status: null, error: new Error("ENOENT tmux") }]);
  const res = injectLine("s", "hello", fn);

  assert.equal(res.ok, false);
  assert.match(res.error, /ENOENT tmux/);
});

test("injectLine: a sor-tartalom verbatim megy at (nincs csonkitas/idezojelezes)", () => {
  const weird = 'a "b" $(c) `d` \\e --f';
  const { fn, calls } = fakeSpawn([{ status: 0 }, { status: 0 }]);
  injectLine("s", weird, fn);
  assert.equal(calls[0].args[5], weird);
});

// Elnyelt Enter (2.1.302, elo proba): hosszu sornal a TUI a szoveget paste-kent
// kezeli, es a kozvetlenul utana jovo Entert elnyeli. A ket send-keys koze
// varakozas kell; a sorrendet egy kozos esemenynaplo bizonyitja.
function recorder() {
  const ev = [];
  const spawn = (cmd, args) => {
    if (args[0] === "capture-pane") return { status: 0, stdout: "" };
    ev.push(["spawn", args.at(-1)]); return { status: 0 };
  };
  const wait = (ms) => ev.push(["wait", ms]);
  return { ev, spawn, wait };
}

test("injectLine: rovid sornal nincs varakozas a szoveg es az Enter kozott", () => {
  const { ev, spawn, wait } = recorder();
  assert.deepEqual(injectLine("s", "x".repeat(1000), spawn, wait), { ok: true });
  assert.deepEqual(ev.map((e) => e[0]), ["spawn", "spawn"]);
});

test("injectLine: hosszu sornal varakozas a ket send-keys kozott", () => {
  const { ev, spawn, wait } = recorder();
  assert.deepEqual(injectLine("s", "x".repeat(6067), spawn, wait), { ok: true });
  assert.deepEqual(ev.map((e) => e[0]), ["spawn", "wait", "spawn"]);
  assert.equal(ev[2][1], "Enter", "pontosan egy Enter, a varakozas utan");
  assert.ok(ev[1][1] >= 300, `varakozas ms: ${ev[1][1]}`);
});

test("injectLine: hosszu sornal, ha a szoveg nem ment ki, nincs varakozas se Enter", () => {
  const ev = [];
  const spawn = (cmd, args) => {
    if (args[0] === "capture-pane") return { status: 0, stdout: "" };
    ev.push("spawn"); return { status: 1, stderr: "x" };
  };
  const res = injectLine("s", "x".repeat(6067), spawn, () => ev.push("wait"));
  assert.equal(res.ok, false);
  assert.deepEqual(ev, ["spawn"]);
});
