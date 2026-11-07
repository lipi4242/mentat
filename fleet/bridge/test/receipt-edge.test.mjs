// Erkezes-nyugta (3.2): session-valtas, ujrainditas, hianyzo transzkript, meres.
import test from "node:test";
import assert from "node:assert/strict";
import { writeFileSync, appendFileSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { LINE, user, setup } from "./receipt-fixture.mjs";
import { readStats } from "../lib/transcript.mjs";

test("session-valtas: az uj transzkript elejetol, a regi a regi offsettol", () => {
  const s = setup();
  const r = s.mk();
  r.record(LINE);
  writeFileSync(s.tpath("s2"), user(LINE)); // az uj session mar a sorral indul
  writeFileSync(s.sessionIdFile, "s2\n");
  r.check();
  assert.equal(s.results[0]?.status, "confirmed");

  const t = setup();
  const r2 = t.mk();
  r2.record(LINE);
  writeFileSync(t.tpath("s2"), user("mas"));
  writeFileSync(t.sessionIdFile, "s2\n");
  r2.check();
  assert.equal(t.results.length, 0);
  appendFileSync(t.tpath("s1"), user(LINE)); // a regibe kesve
  r2.check();
  assert.equal(t.results[0]?.status, "confirmed");
});

test("ujrainditas utan a fuggo ellenorzes folytatodik", () => {
  const s = setup();
  s.mk().record(LINE);
  const r = s.mk();
  assert.equal(r.depth(), 1);
  appendFileSync(s.tpath("s1"), user(LINE));
  r.check();
  assert.equal(s.results[0]?.status, "confirmed");
});

test("nincs transzkript a deadline-kor -> unconfirmed 'no transcript', nincs ujrainjektalas", () => {
  const s = setup();
  writeFileSync(s.sessionIdFile, "ismeretlen\n");
  const r = s.mk();
  r.record(LINE);
  s.clock.t += 121_000;
  r.check();
  assert.equal(s.reinjected.length, 0);
  assert.equal(s.results[0]?.status, "unconfirmed");
  assert.equal(s.results[0]?.detail, "no transcript");
});

test("reakcio-sor (nincs msg=) nem kerul ellenorzesre", () => {
  const s = setup();
  const r = s.mk();
  r.record("[Telegram inbound | J id=1 | chat=-100 | reaction]: 👍 on message 5");
  assert.equal(r.depth(), 0);
});

test("measure az injektalas ELOTT: a kozben irt sor is nyugta; sikertelen inject merese eldobodik", () => {
  const s = setup();
  const r = s.mk();
  r.measure(LINE);
  appendFileSync(s.tpath("s1"), user(LINE)); // az agens gyorsabb, mint az onInjected
  r.record(LINE);
  r.check();
  assert.equal(s.results[0]?.status, "confirmed");

  const t = setup();
  const r2 = t.mk();
  r2.measure(LINE); // az inject elbukik: nincs record
  r2.measure("[Telegram inbound | J id=1 | chat=-100 | msg=8]: y");
  appendFileSync(t.tpath("s1"), user(LINE));
  r2.record(LINE); // kesobb, mas meressel: friss offset -> az elobbi sor nem szamit
  r2.check();
  assert.equal(t.results.length, 0);
});

test("negativ atnezes utan az offset lep: a masodik check csak az uj bajtokat olvassa, utvonalankent egyszer", () => {
  const s = setup();
  const r = s.mk();
  r.record(LINE);
  r.record("[Telegram inbound | J id=1 | chat=-100 | msg=8]: y");
  const chunk = user("mas") + user("meg mas");
  appendFileSync(s.tpath("s1"), chunk);
  let b = readStats.bytes;
  r.check();
  assert.equal(readStats.bytes - b, Buffer.byteLength(chunk), "ket fuggo elem, egy olvasas");
  const more = user("harmadik");
  appendFileSync(s.tpath("s1"), more);
  b = readStats.bytes;
  r.check();
  assert.equal(readStats.bytes - b, Buffer.byteLength(more), "csak az uj bajtok");
  appendFileSync(s.tpath("s1"), user(LINE));
  r.check();
  assert.equal(s.results[0]?.status, "confirmed");
  assert.equal(r.depth(), 1);
});

test("lezart kulcs: a pending-bol kesve kezbesitett ujrainjektalas nem indit uj ciklust (ujrainditas utan sem)", () => {
  const s = setup();
  const r = s.mk();
  r.record(LINE);
  s.clock.t += 121_000; r.check();
  s.clock.t += 121_000; r.check();
  assert.equal(s.results[0]?.status, "unconfirmed");
  r.record(LINE); // a pending-sorba kerult ujrainjektalas most ert at
  assert.equal(r.depth(), 0);
  s.mk().record(LINE);
  assert.equal(s.mk().depth(), 0);
});

test("rég lejart elem: nincs ujrainjektalas, unconfirmed 'stale'", () => {
  const s = setup();
  const r = s.mk();
  r.record(LINE);
  s.clock.t += 120_000 + 2 * 120_000 + 1; // a hid sokaig allt
  r.check();
  assert.equal(s.reinjected.length, 0);
  assert.equal(s.results[0]?.status, "unconfirmed");
  assert.equal(s.results[0]?.detail, "stale");
});
