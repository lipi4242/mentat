import test from "node:test";
import { tempDir } from "./tmp.mjs";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync, readdirSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  loadJson,
  saveJson,
  saveJsonStrict,
  loadJsonQuarantine,
} from "../lib/jsonfile.mjs";

// Igazan irhatatlan ut: egy sima FAJL a konyvtar-komponens helyen (ENOTDIR),
// igy a mkdirSync(recursive) sem menti meg.
function unwritablePath() {
  const dir = tempDir("se-");
  const fileAsDir = join(dir, "not-a-dir");
  writeFileSync(fileAsDir, "x");
  return join(fileAsDir, "state.json");
}

test("saveJson atomic: no tmp leftovers, content readable", () => {
  const d = tempDir("se-");
  const p = join(d, "x.json");
  saveJson(p, { a: 1 });
  assert.deepEqual(JSON.parse(readFileSync(p, "utf8")), { a: 1 });
  assert.ok(!readdirSync(d).some((f) => f.includes(".tmp")));
});

test("loadJson falls back on missing and on corrupt", () => {
  const d = tempDir("se-");
  assert.deepEqual(loadJson(join(d, "nope.json"), { x: 0 }), { x: 0 });
  const p = join(d, "bad.json");
  writeFileSync(p, "{nope");
  assert.deepEqual(loadJson(p, []), []);
});

test("saveJson swallows write errors (non-critical writers)", () => {
  assert.doesNotThrow(() => saveJson(unwritablePath(), { a: 1 }, () => {}));
});

test("saveJsonStrict THROWS on write failure and leaves no tmp behind", () => {
  const d = tempDir("se-");
  const p = join(d, "ok.json");
  saveJsonStrict(p, { a: 1 });
  assert.deepEqual(JSON.parse(readFileSync(p, "utf8")), { a: 1 });

  const bad = unwritablePath();
  assert.throws(() => saveJsonStrict(bad, { a: 1 }), /write error/);
});

test("loadJsonQuarantine: missing file is silent fallback", () => {
  const d = tempDir("se-");
  let called = 0;
  assert.deepEqual(
    loadJsonQuarantine(join(d, "nope.json"), { x: 0 }, () => { called++; }),
    { x: 0 },
  );
  assert.equal(called, 0);
});

test("loadJsonQuarantine: corrupt file is renamed aside, onCorrupt gets the path", () => {
  const d = tempDir("se-");
  const p = join(d, "queue.json");
  writeFileSync(p, "{nope");
  const seen = [];
  const got = loadJsonQuarantine(p, [], (q) => seen.push(q));

  assert.deepEqual(got, []);
  assert.equal(existsSync(p), false, "az eredeti ut felszabadul");
  assert.equal(seen.length, 1);
  assert.match(seen[0], /queue\.json\.corrupt-\d+$/);
  assert.equal(readFileSync(seen[0], "utf8"), "{nope", "a serult tartalom megmarad");
  assert.ok(readdirSync(d).some((f) => f.startsWith("queue.json.corrupt-")));
});

test("loadJsonQuarantine: valid file loads normally, nothing quarantined", () => {
  const d = tempDir("se-");
  const p = join(d, "ok.json");
  saveJsonStrict(p, { a: 1 });
  let called = 0;
  assert.deepEqual(loadJsonQuarantine(p, {}, () => { called++; }), { a: 1 });
  assert.equal(called, 0);
});
