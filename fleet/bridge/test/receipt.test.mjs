// Erkezes-nyugta (3.2): a beinjektalt sor megjelenik-e a Claude-transzkriptben.
// Hamis ora (`now`), tmp konyvtar, `transcriptRoot` parameter — a valodi ~/.claude-hoz nem nyul.
import test from "node:test";
import assert from "node:assert/strict";
import { writeFileSync, appendFileSync, readFileSync, renameSync } from "node:fs";
import { join } from "node:path";
import { LINE, user, setup } from "./receipt-fixture.mjs";

test("rogzites utan megjelenő user-sor -> confirmed, nincs ujrainjektalas; az ELOTTE levo nem szamit", () => {
  const s = setup();
  appendFileSync(s.tpath("s1"), user(LINE)); // mar ott volt
  const r = s.mk();
  r.record(LINE);
  s.clock.t += 130_000;
  r.check();
  assert.deepEqual(s.reinjected, [LINE], "az elozo sor nem nyugta: deadline -> ujrainjektalas");
  assert.equal(s.results.length, 0);
  appendFileSync(s.tpath("s1"), user(LINE));
  r.check();
  assert.equal(s.results.length, 1);
  assert.equal(s.results[0].status, "confirmed");
  assert.equal(s.results[0].chat_id, "-100");
  assert.equal(s.results[0].msg_id, "7");
  assert.equal(r.depth(), 0);
  assert.equal(s.reinjected.length, 1);
});

test("a rekord mezoi a receipts.json-ban", () => {
  const s = setup();
  const r = s.mk();
  const size = readFileSync(s.tpath("s1")).length;
  r.record(LINE);
  const [it] = JSON.parse(readFileSync(join(s.dir, "telegram-state", "receipts.json"), "utf8")).items;
  assert.deepEqual(
    { chat_id: it.chat_id, msg_id: it.msg_id, line: it.line, sid: it.sid, path: it.path, offset: it.offset,
      deadline: it.deadline, attempt: it.attempt },
    { chat_id: "-100", msg_id: "7", line: LINE, sid: "s1", path: s.tpath("s1"), offset: size,
      deadline: 1_120_000, attempt: 0 });
});

test("pontos illesztes: msg=12 nem nyugtazza msg=123-at, assistant-bejegyzes sem szamit; tomb-content igen", () => {
  const s = setup();
  const r = s.mk();
  r.record("[Telegram inbound | J id=1 | chat=-100 | msg=12]: a");
  appendFileSync(s.tpath("s1"), user("[Telegram inbound | J id=1 | chat=-100 | msg=123]: a"));
  appendFileSync(s.tpath("s1"), JSON.stringify({ type: "assistant",
    message: { role: "assistant", content: "[Telegram inbound | J id=1 | chat=-100 | msg=12]: a" } }) + "\n");
  appendFileSync(s.tpath("s1"), user("idezem: chat=-100 | msg=12"));
  r.check();
  assert.equal(s.results.length, 0);
  appendFileSync(s.tpath("s1"), JSON.stringify({ type: "user", message: { role: "user",
    content: [{ type: "text", text: "[Telegram inbound | J id=1 | chat=-100 | msg=12 | reply_to=3]: a" }] } }) + "\n");
  r.check();
  assert.equal(s.results[0]?.status, "confirmed");
});

test("csak teljes sor szamit; csonkitott (rovidebb) fajl -> offset 0", () => {
  const s = setup();
  const r = s.mk();
  r.record(LINE);
  appendFileSync(s.tpath("s1"), user(LINE).trimEnd()); // nincs \n
  r.check();
  assert.equal(s.results.length, 0, "felig irt sor nem nyugta");
  appendFileSync(s.tpath("s1"), "\n");
  r.check();
  assert.equal(s.results[0]?.status, "confirmed", "a befejezett sor mar nyugta");
  const s2 = setup();
  appendFileSync(s2.tpath("s1"), JSON.stringify({ type: "summary", pad: "x".repeat(500) }) + "\n");
  const r2 = s2.mk();
  r2.record(LINE);
  writeFileSync(s2.tpath("s1"), user(LINE)); // rovidebb lett
  r2.check();
  assert.equal(s2.results[0]?.status, "confirmed");
});

test("deadline -> pontosan 1 ujrainjektalas; a kesei elso is nyugta", () => {
  const s = setup();
  const r = s.mk();
  r.record(LINE);
  s.clock.t += 121_000;
  r.check();
  r.record(LINE); // az ujrainjektalas a deliver-en at ujra rogzitene — fuggoben van, no-op
  r.check();
  assert.deepEqual(s.reinjected, [LINE]);
  appendFileSync(s.tpath("s1"), user(LINE));
  s.clock.t += 500_000;
  r.check();
  assert.equal(s.results.length, 1);
  assert.equal(s.results[0].status, "confirmed");
  assert.equal(s.reinjected.length, 1);
});

test("ujrainjektalas utan sem -> egyszer unconfirmed", () => {
  const s = setup();
  const r = s.mk();
  r.record(LINE);
  s.clock.t += 121_000; r.check();
  s.clock.t += 121_000; r.check();
  s.clock.t += 121_000; r.check();
  assert.equal(s.reinjected.length, 1);
  assert.equal(s.results.length, 1);
  assert.equal(s.results[0].status, "unconfirmed");
  assert.equal(r.depth(), 0);
});

test("']' a megjelenitett nevben (Alice [work]): rogzul es nyugtazodik; msg=12 tovabbra sem msg=123", () => {
  const s = setup();
  const r = s.mk();
  const l12 = "[Telegram inbound | Alice [work] id=1 | chat=-100 | msg=12]: a";
  r.record(l12);
  assert.equal(r.depth(), 1);
  appendFileSync(s.tpath("s1"), user("[Telegram inbound | Alice [work] id=1 | chat=-100 | msg=123]: a"));
  r.check();
  assert.equal(s.results.length, 0);
  appendFileSync(s.tpath("s1"), user(l12));
  r.check();
  assert.equal(s.results[0]?.status, "confirmed");
});

test("ugyanazon az uton kicserelt, NAGYOBB transzkript (mas inode) -> 0-tol", () => {
  const s = setup();
  const r = s.mk();
  r.record(LINE);
  const tmp = s.tpath("s1") + ".new";
  writeFileSync(tmp, user(LINE) + JSON.stringify({ type: "summary", pad: "x".repeat(500) }) + "\n");
  renameSync(tmp, s.tpath("s1"));
  r.check();
  assert.equal(s.results[0]?.status, "confirmed");
});
