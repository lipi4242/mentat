// A kezbesitesi naplo semaja es olvasoja (docs/delivery-log.md).
import test from "node:test";
import { tempDir } from "./tmp.mjs";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  makeRow, appendDelivery, readDay, resolveSends, summarize, logPath,
  resolveLogDir, LOG_VERSION,
} from "../lib/delivery-log.mjs";

const tmp = () => tempDir("dl-");
const DAY = "2026-10-14";
const T = Date.parse(`${DAY}T10:00:00Z`);

test("logPath: delivery-YYYY-MM-DD.jsonl a megadott konyvtarban (UTC nap)", () => {
  assert.equal(logPath("/x", T), "/x/delivery-2026-10-14.jsonl");
});

test("makeRow: kozos mezok + tipus-validalas", () => {
  const r = makeRow({ type: "intent", chat_id: "-100", action: "message", reply_to: 5, text: "hi", ts: T });
  assert.equal(r.v, LOG_VERSION);
  assert.equal(r.type, "intent");
  assert.match(r.id, /^\d+-\d+-\d+$/);
  assert.equal(r.reply_to, 5);
  assert.throws(() => makeRow({ type: "out" }), /type/);
  assert.throws(() => makeRow({ type: "outcome", send_id: "x", status: "maybe" }), /status/);
  assert.throws(() => makeRow({ type: "outcome", status: "confirmed" }), /send_id/);
});

test("makeRow: a sor 4 KB alatt marad hosszu, tobb-bajtos szovegnel is", () => {
  const r = makeRow({ type: "inbound", chat_id: "1", msg_id: 1, text: "é".repeat(5000), ts: T });
  assert.ok(Buffer.byteLength(JSON.stringify(r)) <= 4096);
});

test("appendDelivery: irhatatlan konyvtar -> {ok:false}, nem dob", () => {
  const d = tmp();
  writeFileSync(join(d, "f"), "");
  const res = appendDelivery(join(d, "f", "sub"), makeRow({ type: "inbound", chat_id: "1", msg_id: 1, ts: T }));
  assert.equal(res.ok, false);
});

test("appendDelivery + readDay: visszaolvashato, a csonka utolso sort atugorja", () => {
  const d = tmp();
  appendDelivery(d, makeRow({ type: "inbound", chat_id: "1", msg_id: 7, text: "szia", ts: T }), T);
  const p = logPath(d, T);
  writeFileSync(p, readFileSync(p, "utf8") + '{"v":1,"type":"int');
  const rows = readDay(d, DAY);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].msg_id, 7);
  assert.deepEqual(readDay(d, "1999-01-01"), []);
});

test("resolveSends: szandek kimenet nelkul = unknown (osszeomlas a keres utan)", () => {
  const i = makeRow({ type: "intent", chat_id: "1", action: "message", reply_to: 7, text: "x", ts: T });
  const [s] = resolveSends([i]);
  assert.equal(s.status, "unknown");
  assert.equal(s.send_id, i.id);
  assert.equal(s.reply_to, 7);
  assert.equal(s.has_outcome, false);
});

test("resolveSends: a kimenet a szandekhoz kotodik send_id-vel", () => {
  const a = makeRow({ type: "intent", chat_id: "1", action: "message", reply_to: 7, text: "a", ts: T });
  const b = makeRow({ type: "intent", chat_id: "1", action: "reaction", target_msg_id: 7, text: "👍", ts: T });
  const c = makeRow({ type: "intent", chat_id: "1", action: "message", text: "c", ts: T });
  const rows = [a, b, c,
    makeRow({ type: "outcome", send_id: a.id, status: "confirmed", message_id: 99, ts: T }),
    makeRow({ type: "outcome", send_id: b.id, status: "failed", error: "400", ts: T }),
    makeRow({ type: "outcome", send_id: c.id, status: "unknown", error: "timeout", ts: T })];
  const by = Object.fromEntries(resolveSends(rows).map((s) => [s.send_id, s]));
  assert.equal(by[a.id].status, "confirmed");
  assert.equal(by[a.id].message_id, 99);
  assert.equal(by[b.id].status, "failed");
  assert.equal(by[c.id].status, "unknown");
  assert.equal(by[c.id].has_outcome, true);
});

test("summarize: a bejovo es a valasz osszekotve (chat + reply_to); reakcio nem valasz", () => {
  const in1 = makeRow({ type: "inbound", chat_id: "1", msg_id: 7, kind: "message", text: "?", ts: T });
  const in2 = makeRow({ type: "inbound", chat_id: "1", msg_id: 8, kind: "message", text: "??", ts: T });
  const in3 = makeRow({ type: "inbound", chat_id: "2", msg_id: 7, kind: "message", text: "masik chat", ts: T });
  const re = makeRow({ type: "inbound", chat_id: "1", msg_id: null, target_msg_id: 8, kind: "reaction", text: "👍", ts: T });
  const s1 = makeRow({ type: "intent", chat_id: "1", action: "message", reply_to: 7, text: "valasz", ts: T });
  const s2 = makeRow({ type: "intent", chat_id: "1", action: "reaction", target_msg_id: 8, text: "👀", ts: T });
  const rows = [in1, in2, in3, re, s1, s2,
    makeRow({ type: "outcome", send_id: s1.id, status: "confirmed", message_id: 50, ts: T }),
    makeRow({ type: "outcome", send_id: s2.id, status: "confirmed", ts: T })];
  const sum = summarize(rows);
  assert.equal(sum.inbound, 3, "a reakcio nem szamit bejovo kerdesnek");
  assert.deepEqual(sum.counts, { confirmed: 2, failed: 0, unknown: 0 });
  assert.deepEqual(sum.unanswered.map((r) => `${r.chat_id}:${r.msg_id}`), ["1:8", "2:7"]);
});

test("summarize: unknown valasz nem zarja le a bejovot, de kulon latszik", () => {
  const in1 = makeRow({ type: "inbound", chat_id: "1", msg_id: 7, kind: "message", text: "?", ts: T });
  const s1 = makeRow({ type: "intent", chat_id: "1", action: "message", reply_to: 7, text: "v", ts: T });
  const sum = summarize([in1, s1]);
  assert.equal(sum.unanswered.length, 1);
  assert.equal(sum.counts.unknown, 1);
  assert.equal(sum.uncertain.length, 1);
});

test("resolveLogDir: env elobb, aztan a sub-etha telepitesi hely, kulonben null", () => {
  assert.equal(resolveLogDir({ BRIDGE_INBOX_DIR: "/a" }, "/x/sub-etha/send.mjs"), "/a");
  assert.equal(resolveLogDir({ BRIDGE_STATE_DIR: "/s" }, "/x/sub-etha/send.mjs"), "/s/telegram-inbox");
  assert.equal(resolveLogDir({}, "/home/u/.config/ag/sub-etha/send.mjs"), "/home/u/.config/ag/telegram-inbox");
  assert.equal(resolveLogDir({}, "/repo/bridge/send.mjs"), null);
});

test("delivery.mjs: megvalaszolatlan es unknown -> exit 2, a riport megnevezi oket", async () => {
  const { main } = await import("../delivery.mjs");
  const d = tmp();
  const now = Date.now();
  appendDelivery(d, makeRow({ type: "inbound", chat_id: "1", msg_id: 7, kind: "message", from: "J", text: "kerdes" }), now);
  appendDelivery(d, makeRow({ type: "intent", chat_id: "1", action: "message", reply_to: 7, text: "valasz" }), now);
  const out = [];
  const orig = console.log;
  console.log = (s) => out.push(s);
  try {
    assert.equal(main([], { BRIDGE_INBOX_DIR: d }), 2);
    assert.equal(main(["--day", "1999-01-01"], { BRIDGE_INBOX_DIR: d }), 0);
  } finally { console.log = orig; }
  assert.match(out[0], /MEGVÁLASZOLATLAN chat=1 msg=7/);
  assert.match(out[0], /UNKNOWN chat=1 reply_to=7 \(a küldő folyamat a kérés közben leállt\)/);
  assert.match(out[1], /0 bejövő/);
});
