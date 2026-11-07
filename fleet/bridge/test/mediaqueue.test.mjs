import test from "node:test";
import { tempDir } from "./tmp.mjs";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, chmodSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { MediaQueue } from "../lib/mediaqueue.mjs";

const qfile = () => join(tempDir("se-"), "q.json");

test("enqueue persists synchronously, worker drains one at a time", async () => {
  const p = qfile();
  const seen = [];
  const q1 = new MediaQueue(p, async (item) => { seen.push(item.id); });
  q1.enqueue({ id: "a" });
  q1.enqueue({ id: "b" });
  await q1.drain();
  assert.deepEqual(seen, ["a", "b"]);
  assert.equal(q1.depth(), 0);
});

test("crash-safe: a second instance picks up what the first left", async () => {
  const p = qfile();
  const q1 = new MediaQueue(p, async () => { throw new Error("crash"); });
  q1.enqueue({ id: "x" });
  await q1.drain();            // processor throws -> item STAYS queued
  assert.equal(q1.depth(), 1);
  const seen = [];
  const q2 = new MediaQueue(p, async (i) => { seen.push(i.id); });
  await q2.drain();            // fresh instance resumes from the file
  assert.deepEqual(seen, ["x"]);
});

test("reentrant drain does not double-process", async () => {
  const p = qfile();
  let count = 0;
  const q = new MediaQueue(p, async () => { count++; await new Promise(r => setTimeout(r, 20)); });
  q.enqueue({ id: "a" });
  const d1 = q.drain();
  const d2 = q.drain();   // no-op while running
  await Promise.all([d1, d2]);
  assert.equal(count, 1);
});

test("enqueue THROWS when the queue file cannot be written", () => {
  // Sima FAJL a konyvtar-komponens helyen -> ENOTDIR, a mkdir sem menti meg.
  const dir = tempDir("se-");
  const fileAsDir = join(dir, "not-a-dir");
  writeFileSync(fileAsDir, "x");
  const q = new MediaQueue(join(fileAsDir, "q.json"), async () => {});
  // Ha ez nem dobna, a hivo (poll-ciklus) sikernek hinne, es leptetne az
  // offsetet egy sosem perzisztalt elem folott — pontosan a nema vesztes.
  assert.throws(() => q.enqueue({ id: "a" }), /write error/);
});

test("drain: sikeres feldolgozas + irhatatlan sorfajl -> az elem NEM vesz el", async () => {
  const d = tempDir("se-");
  const p = join(d, "q.json");
  const seen = [];
  const q = new MediaQueue(p, async (i) => { seen.push(i.id); });
  q.enqueue({ id: "a" });
  q.enqueue({ id: "b" });

  // A konyvtar csak olvashato: a feldolgozas megy, a torles-iras (tmp+rename)
  // elhasal. Duplikacio > vesztes: az elemek a sorban MARADNAK.
  chmodSync(d, 0o500);
  try {
    await q.drain();
    assert.deepEqual(seen, ["a"], "a torles utan megallunk, nem porgunk tovabb");
    assert.equal(q.depth(), 2, "egyetlen elem sem tunt el a sorbol");
  } finally {
    chmodSync(d, 0o700);
  }

  // Irhato konyvtarral a sor rendesen lefut vegig — az 'a' ujra jon (at-least-once).
  const seen2 = [];
  const q2 = new MediaQueue(p, async (i) => { seen2.push(i.id); });
  await q2.drain();
  assert.deepEqual(seen2, ["a", "b"]);
  assert.equal(q2.depth(), 0);
});

test("corrupt queue file: quarantined, onCorrupt hivva, sor uresen indul", async () => {
  const p = qfile();
  writeFileSync(p, "{nope");
  const corrupt = [];
  const q = new MediaQueue(p, async () => {}, { onCorrupt: (c) => corrupt.push(c) });
  assert.equal(q.depth(), 0);
  assert.equal(corrupt.length, 1);
  assert.match(corrupt[0], /\.corrupt-\d+$/);
});
