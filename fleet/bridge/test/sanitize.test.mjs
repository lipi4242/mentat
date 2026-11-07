// lib/sanitize.mjs testjei — a bridge.mjs-bol kiemelt tiszta fuggvenyek
// (sanitize, safeName) viselkedese nem valtozhatott a kiemeleskor.

import test from "node:test";
import assert from "node:assert/strict";
import { sanitize, sanitizeBody, safeName } from "../lib/sanitize.mjs";

test("sanitize eltavolitja a kontroll-karaktereket (ESC, NUL, BEL) es szokozre cseréli", () => {
  assert.equal(sanitize("hello\x1bworld"), "hello world");
  assert.equal(sanitize("a\x00\x01b"), "a b");
});

test("sanitize egysorositi az ujsorokat es CRLF-et", () => {
  assert.equal(sanitize("line1\nline2\r\nline3"), "line1 line2 line3");
});

test("sanitize levagja a bidi- es zero-width karaktereket", () => {
  // U+200B (zero width space), U+200C (zero width non-joiner), U+FEFF (BOM)
  assert.equal(sanitize("​zero‌width﻿"), "zerowidth");
  // U+202E (RTL override) ... U+202C (pop directional formatting nincs a
  // tiltolistan, csak 202A-202E) — a tényleges viselkedést nézzük:
  assert.equal(sanitize("‮evil‬"), "evil");
});

test("sanitize tobbszoros szokozt egyre redukal es szeleket vagja", () => {
  assert.equal(sanitize("  spaced   out  "), "spaced out");
});

test("sanitize 2000 karaktert NEM vag (a regi 1500-as nema plafon megszunt)", () => {
  const long = "x".repeat(2000);
  assert.equal(sanitize(long), long);
});

test("sanitize valtozatlanul hagyja a magyar ekezetes szoveget", () => {
  const hu = "árvíztűrő tükörfúrógép ŐÁÉÍÓÚÜŰ";
  assert.equal(sanitize(hu), hu);
});

test("safeName csak A-Za-z0-9_.- karaktereket enged at, tobbit alahuzasra cserel", () => {
  assert.equal(safeName("ok_name-123.txt"), "ok_name-123.txt");
  assert.equal(safeName("../../etc/passwd"), ".._.._etc_passwd");
});

test("safeName 64 karakterre vagja", () => {
  const out = safeName("a".repeat(100));
  assert.equal(out.length, 64);
  assert.equal(out, "a".repeat(64));
});


test("sanitize: 4096-ig NEM vag; folotte lathato jellel vag", () => {
  const long = "a".repeat(2473);
  assert.equal(sanitize(long), long);                       // 1500 felett is teljes
  const cut = sanitize("b".repeat(5000));
  assert.ok(cut.startsWith("b".repeat(4096)));
  assert.ok(cut.includes("[…csonkítva: +904 karakter"));
  assert.equal(sanitize("c".repeat(20), 10), "cccccccccc […csonkítva: +10 karakter, a teljes szöveg az events logban]");
});

test("sanitizeBody: 6000 felett a torzs eleje + CSONKA-jel, a jellel EGYUTT <= 6000", () => {
  const marker = " [CSONKA: teljes szöveg events-2026-10-18.jsonl update_id=5]";
  const out = sanitizeBody("y".repeat(7000), { where: "events-2026-10-18.jsonl update_id=5" });
  assert.equal(out.length, 6000);
  assert.equal(out, "y".repeat(6000 - marker.length) + marker);
  assert.equal(sanitizeBody("y".repeat(6000)), "y".repeat(6000));
  assert.equal(sanitizeBody("y".repeat(6001)).length <= 6000, true);
});

test("sanitizeBody: a vagas nem tor kette surrogate part", () => {
  const marker = " [CSONKA: teljes szöveg az events-naploban]";
  for (const pad of [0, 1]) {
    const out = sanitizeBody("a".repeat(pad) + "🙂".repeat(4000));
    assert.ok(out.length <= 6000, String(out.length));
    assert.ok(out.endsWith(marker));
    const body = out.slice(0, -marker.length);
    assert.ok(!/[\uD800-\uDBFF]$/.test(body), `pad=${pad}: magas surrogate a vegen`);
  }
});

test("sanitizeBody: tisztitas azonos a sanitize-evel", () => {
  assert.equal(sanitizeBody("a\x1bb\nc‮d​"), "a b cd");
});
