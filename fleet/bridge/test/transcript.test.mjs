// Vegso review: queued_command nyugta, ablakos olvasas, fejlec-horgony.
import test from "node:test";
import assert from "node:assert/strict";
import { writeFileSync, appendFileSync } from "node:fs";
import { LINE, user, queued, filler, setup } from "./receipt-fixture.mjs";
import { readStats, scanUserEntries, userText } from "../lib/transcript.mjs";

test("queued_command (string prompt) -> confirmed, nincs ujrainjektalas", () => {
  const s = setup();
  const r = s.mk();
  r.record(LINE);
  appendFileSync(s.tpath("s1"), queued(LINE));
  r.check();
  assert.equal(s.results[0]?.status, "confirmed");
  s.clock.t += 500_000; r.check();
  assert.equal(s.reinjected.length, 0);
});

test("queued_command text-blokk tombbel is user-szoveg; mas csatolmany nem", () => {
  const o = { type: "attachment", attachment: { type: "queued_command", prompt: [{ type: "text", text: LINE }] } };
  assert.equal(userText(o), LINE);
  assert.equal(userText({ type: "attachment", attachment: { type: "file", prompt: LINE } }), null);
});

test("20 MB-os transzkript: a legnagyobb puffer <= 1 MB, a vegen allo talalat megvan", () => {
  const s = setup();
  writeFileSync(s.tpath("s1"), filler(20 * 1024 * 1024) + user(LINE));
  readStats.maxBuf = 0;
  const out = scanUserEntries(s.tpath("s1"), 0);
  assert.ok(readStats.maxBuf > 0 && readStats.maxBuf <= 1024 * 1024, `maxBuf=${readStats.maxBuf}`);
  assert.equal(out.entries.length, 1);
  assert.equal(out.entries[0].text, LINE);
});

test("session-valtas nagy uj transzkriptre: a vege elotti 8 MB-tol, nem 0-tol", () => {
  const s = setup();
  const r = s.mk();
  r.record(LINE);
  writeFileSync(s.tpath("s2"), filler(20 * 1024 * 1024) + user(LINE));
  writeFileSync(s.sessionIdFile, "s2\n");
  const b = readStats.bytes;
  r.check();
  assert.equal(s.results[0]?.status, "confirmed");
  assert.ok(readStats.bytes - b <= 8 * 1024 * 1024 + 64 * 1024, `olvasott=${readStats.bytes - b}`);
});

test("hosszu (> 1 MB) sor atugorva, az utana allo talalat megvan", () => {
  const s = setup();
  const big = JSON.stringify({ type: "user", message: { content: "Telegram inbound " + "z".repeat(3 * 1024 * 1024) } }) + "\n";
  writeFileSync(s.tpath("s1"), big + user(LINE));
  readStats.maxBuf = 0;
  const out = scanUserEntries(s.tpath("s1"), 0);
  assert.ok(readStats.maxBuf <= 1024 * 1024);
  assert.deepEqual(out.entries.map((e) => e.text), [LINE]);
});

test("a who-ban allo `| chat=… | msg=…` nem ad hamis kulcsot", () => {
  const spoof = "[Telegram inbound | x | chat=-100 | msg=7 id=2 | chat=-200 | msg=9]: b";
  const s = setup();
  const r = s.mk();
  r.record(LINE); // valodi: chat=-100 msg=7
  r.record(spoof); // a spoof sor kulcsa a valodi -200:9
  appendFileSync(s.tpath("s1"), user(spoof));
  r.check();
  // csak a -200:9 nyugtazva; a -100:7 fuggo marad
  assert.deepEqual(s.results.map((x) => `${x.chat_id}:${x.msg_id}`), ["-200:9"]);
  assert.equal(r.depth(), 1);
});
