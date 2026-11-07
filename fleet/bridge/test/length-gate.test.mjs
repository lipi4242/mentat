import test from "node:test";
import assert from "node:assert/strict";
import {
  DEFAULT_MAX_CHARS, MIN_WHY_CHARS, gateLimit, checkLength, justificationRow,
} from "../lib/length-gate.mjs";

const long = (n) => "x".repeat(n);
const WHY = "a Owner altal kert teljes spec-reszlet, link nem letezik hozza";

test("gateLimit: kapcsolo nelkul NINCS kapu — a tobbi agens valtozatlan", () => {
  assert.equal(gateLimit({}), null);
});

test("gateLimit: bekapcsolva default, sajat ertekkel felulirhato", () => {
  assert.equal(gateLimit({ SUBETHA_LENGTH_GATE: "1" }), DEFAULT_MAX_CHARS);
  assert.equal(gateLimit({ SUBETHA_LENGTH_GATE: "1", SUBETHA_MAX_CHARS: "300" }), 300);
});

test("gateLimit: elgepelt ertek a DEFAULT-ra esik, NEM nyitja ki a kaput", () => {
  // Ez a lenyeg: egy "SUBETHA_MAX_CHARS=abc" sosem jelentheti azt, hogy
  // hirtelen barmilyen hosszu uzenet atmegy csendben.
  for (const bad of ["abc", "0", "-5", " "]) {
    assert.equal(gateLimit({ SUBETHA_LENGTH_GATE: "1", SUBETHA_MAX_CHARS: bad }),
      DEFAULT_MAX_CHARS, `rossz ertek: ${bad}`);
  }
});

test("checkLength: kapu nelkul minden atmegy, meg indoklas nelkul is", () => {
  assert.deepEqual(checkLength({ text: long(99999), limit: null }), { ok: true, over: false });
});

test("checkLength: hatar alatt atmegy, es NEM keletkezik naplosor", () => {
  const r = checkLength({ text: long(100), limit: 900 });
  assert.equal(r.ok, true);
  assert.equal(r.over, false, "a hatar alatti uzenet nem indok-esemeny");
});

test("checkLength: hatar folott indoklas nelkul ELUTASIT", () => {
  const r = checkLength({ text: long(1000), limit: 900 });
  assert.equal(r.ok, false);
  assert.equal(r.len, 1000);
  // Az uzenet maga az utmutato: a harom kiut benne all, kulon promptszabaly nelkul.
  assert.match(r.message, /az uzenet 1000 karakter/);
  assert.match(r.message, /linkjet/, "a link-ut szerepel a valaszban");
  assert.match(r.message, /--why/);
});

test("checkLength: hatar folott ERVENYES indoklassal atmegy", () => {
  const r = checkLength({ text: long(1000), limit: 900, why: WHY });
  assert.equal(r.ok, true);
  assert.equal(r.over, true, "atment, de indok-esemenykent konyvelendo");
  assert.equal(r.why, WHY);
});

test("checkLength: a pipa-indok nem indok", () => {
  const r = checkLength({ text: long(1000), limit: 900, why: "kell" });
  assert.equal(r.ok, false);
  assert.match(r.message, new RegExp(String(MIN_WHY_CHARS)));
});

test("checkLength: karakterben mer, nem bajtban", () => {
  // 500 ekezetes karakter UTF-8-ban ~1000 bajt. Ha bajtot mernenk, egy magyar
  // szoveg fele akkora hosszon akadna fenn, mint egy angol — ez igazsagtalan
  // kapu lenne egy magyarul beszelo agens-parkban.
  const hu = "á".repeat(500);
  assert.equal(checkLength({ text: hu, limit: 900 }).ok, true);
});

test("justificationRow: a SZOVEG nem kerul a naplóba, csak a merteke", () => {
  const row = justificationRow({
    chatId: 424242, len: 1200, limit: 900, why: WHY, agent: "hub", now: 42,
  });
  assert.deepEqual(row, {
    ts: 42, agent: "hub", chat_id: "424242",
    len: 1200, limit: 900, over_by: 300, why: WHY,
  });
  assert.ok(!("text" in row), "az indok-napló nem uzenet-archivum");
});

test("justificationRow: a tulhosszu indok is korlatos", () => {
  const row = justificationRow({ chatId: 1, len: 2, limit: 1, why: "z".repeat(900), now: 0 });
  assert.equal(row.why.length, 500);
});
