// Nyugta VALODI Claude Code transzkripten (2.1.302, tmux send-keys -l + Enter, mint a hid).
// A fixtura szemelyes adat nelkuli kivonat: 123 (rovid), 124 (hosszu, CSONKA),
// 125 (ekezet+emoji) — a 124 es 125 EGY user-bejegyzesben, "\n"-nel osszefuzve
// (a hosszu sor Enterje nem kuldte el a promptot, a kovetkezo vitte magaval) —,
// 126 (egy futo `!sleep` alatt gepelve, a vegen sima user-bejegyzes).
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, appendFileSync } from "node:fs";
import { setup } from "./receipt-fixture.mjs";
import { headerRe, scanUserEntries } from "../lib/transcript.mjs";

const LIVE = readFileSync(new URL("./fixtures/claude-transcript-live.jsonl", import.meta.url), "utf8");
const CHAT = "-1009999";
const line = (msg) => `[Telegram inbound | Teszt Elek id=4242 | chat=${CHAT} | msg=${msg}]: x`;

test("valodi transzkript: mind a 4 injektalt sor confirmed, msg=12 nem", () => {
  const s = setup();
  const r = s.mk();
  for (const m of [123, 124, 125, 126, 12]) { r.measure(line(m)); r.record(line(m)); }
  appendFileSync(s.tpath("s1"), LIVE);
  r.check();
  const ok = s.results.filter((x) => x.status === "confirmed").map((x) => x.msg_id).sort();
  assert.deepEqual(ok, ["123", "124", "125", "126"]);
  assert.equal(r.depth(), 1); // a msg=12 fuggo marad
});

test("valodi transzkript: az osszefuzott bejegyzes masodik fejlece is illeszkedik", () => {
  const s = setup();
  appendFileSync(s.tpath("s1"), LIVE);
  const { entries } = scanUserEntries(s.tpath("s1"), 0);
  const merged = entries.find((e) => e.text.includes("msg=125"));
  assert.ok(merged && merged.text.startsWith(line(124).slice(0, 60)), "a 125 a 124 bejegyzeseben all");
  assert.ok(headerRe(CHAT, 125).test(merged.text));
  assert.ok(!entries.some((e) => headerRe(CHAT, 12).test(e.text)));
});

test("sor kozepen allo (nem sorkezdo) fejlec tovabbra sem illeszkedik", () => {
  const t = `elozo szoveg ${line(125)}`;
  assert.ok(!headerRe(CHAT, 125).test(t));
  assert.ok(headerRe(CHAT, 125).test(`elozo szoveg\n${line(125)}`));
});
