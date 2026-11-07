// Vegso review: a riport notice-okat eseményenként szamol, a darabolt kuldes egy valasz.
import test from "node:test";
import assert from "node:assert/strict";
import { makeRow, summarize } from "../lib/delivery-log.mjs";
import { report } from "../delivery.mjs";

const T = Date.parse("2026-10-14T10:00:00Z");
const inbound = (msg) => makeRow({ type: "inbound", chat_id: "1", msg_id: msg, kind: "message", text: "?", ts: T });
// Egy send.mjs-hivas darabjai: ugyanaz a pid, az elso viszi a reply_to-t (lib/send-run.mjs).
function chunked(replyTo, statuses) {
  const n = statuses.length, rows = [];
  statuses.forEach((st, i) => {
    const it = makeRow({ type: "intent", chat_id: "1", action: "message", part: `${i + 1}/${n}`,
      reply_to: i === 0 ? replyTo : undefined, text: `d${i + 1}`, ts: T });
    rows.push(it);
    if (st) rows.push(makeRow({ type: "outcome", send_id: it.id, status: st, message_id: 100 + i, ts: T }));
  });
  return rows;
}

test("darabolt kuldes: 3 confirmed darab = 1 confirmed valasz, a bejovo megvalaszolt", () => {
  const sum = summarize([inbound(7), ...chunked(7, ["confirmed", "confirmed", "confirmed"])]);
  assert.deepEqual(sum.counts, { confirmed: 1, failed: 0, unknown: 0 });
  assert.equal(sum.sends.length, 1);
  assert.equal(sum.sends[0].parts, 3);
  assert.deepEqual(sum.unanswered, []);
});

test("darabolt kuldes reszleges hibaval: 1 failed valasz, a bejovo nincs lezarva", () => {
  const sum = summarize([inbound(7), ...chunked(7, ["confirmed", "failed"])]);
  assert.deepEqual(sum.counts, { confirmed: 0, failed: 1, unknown: 0 });
  assert.deepEqual(sum.unanswered.map((r) => r.msg_id), [7]);
});

test("darabolt kuldes unknown darabbal: 1 unknown valasz a bizonytalanok kozt", () => {
  const sum = summarize([inbound(7), ...chunked(7, ["confirmed", null])]);
  assert.deepEqual(sum.counts, { confirmed: 0, failed: 0, unknown: 1 });
  assert.equal(sum.uncertain.length, 1);
  assert.equal(sum.uncertain[0].reply_to, 7);
});

test("ket kulon darabolt kuldes ket valasz", () => {
  const sum = summarize([inbound(7), inbound(8), ...chunked(7, ["confirmed", "confirmed"]),
    ...chunked(8, ["confirmed", "confirmed"])]);
  assert.equal(sum.counts.confirmed, 2);
  assert.deepEqual(sum.unanswered, []);
});

test("notice-ok esemenyenkent szamolva, a riport kiirja", () => {
  const n = (event) => makeRow({ type: "notice", event, chat_id: "1", ts: T });
  const sum = summarize([n("inbound_unconfirmed"), n("inbound_unconfirmed"), n("webhook_failed"),
    n("deprecated_flag"), n("inbound_confirmed"), n("inbound_confirmed"), n("inbound_confirmed")]);
  assert.deepEqual(sum.notices, { inbound_unconfirmed: 2, webhook_failed: 1, deprecated_flag: 1, inbound_confirmed: 3 });
  const out = report(sum, "2026-10-14");
  assert.match(out, /notice: inbound_unconfirmed 2, webhook_failed 1, deprecated_flag 1, inbound_confirmed 3/);
  assert.equal(sum.counts.confirmed, 0, "notice nem kuldes");
});
