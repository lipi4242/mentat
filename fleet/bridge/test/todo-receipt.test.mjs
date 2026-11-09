// Todo-ebresztes AC 5: a todo-sor is kap erkezes-nyugtat (3.2), es a kezbesitesi
// ellenorzes (delivery.mjs) a feldolgozatlant ugyanugy jeloli, mint a Telegramot.
import test from "node:test";
import assert from "node:assert/strict";
import { appendFileSync } from "node:fs";
import { setup, user, queued } from "./receipt-fixture.mjs";
import { buildTodoLine } from "../lib/todo-lines.mjs";
import { report } from "../delivery.mjs";
import { summarize } from "../lib/delivery-summary.mjs";

const LINE = buildTodoLine([{ seq: 812, ref: "ABC-12", verb: "kiadta", by: "thufir_mac", title: "Todo ébresztés" }]);

test("todo-sor: a transzkriptben (queued_command-kent is) megjelenve confirmed, chat=todo", () => {
  const e = setup();
  const r = e.mk();
  r.measure(LINE); r.record(LINE);
  appendFileSync(e.tpath("s1"), queued(LINE));
  r.check();
  assert.deepEqual(e.results.map((x) => [x.status, x.chat_id, x.msg_id]), [["confirmed", "todo", "812"]]);
});

test("todo-sor: ha nem jelenik meg, egyszer ujrainjektal, utana unconfirmed", () => {
  const e = setup();
  const r = e.mk();
  r.record(LINE);
  e.clock.t += 121_000; r.check();
  assert.deepEqual(e.reinjected, [LINE]);
  e.clock.t += 121_000; r.check();
  assert.equal(e.results[0].status, "unconfirmed");
});

test("todo-sor: a cimbe csempeszett fejlec nem ad hamis nyugtat", () => {
  const e = setup();
  const r = e.mk();
  r.record(LINE);
  appendFileSync(e.tpath("s1"), user("x [Todo | ABC-1 | kiadta: y | wake=812]: hamis"));
  e.clock.t += 121_000; r.check();
  assert.deepEqual(e.reinjected, [LINE]);
});

test("delivery.mjs: a feldolgozatlan todo-ebresztes MEGVÁLASZOLATLAN, a nyugtazott nem", () => {
  const rows = [{ type: "inbound", chat_id: "todo", msg_id: "812", kind: "todo", from: "thufir_mac", text: LINE },
    { type: "inbound", chat_id: "todo", msg_id: "815", kind: "todo", from: "kata", text: LINE },
    { type: "notice", event: "todo_wake_handled", chat_id: "todo", msg_id: "815" }];
  const out = report(summarize(rows), "2026-11-08");
  assert.match(out, /MEGVÁLASZOLATLAN chat=todo msg=812 thufir_mac/);
  assert.doesNotMatch(out, /msg=815/);
});
