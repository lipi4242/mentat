// Todo-ebresztes AC 4: az agensek kozti beszelgetes nem akad el; csak a nyilvanvalo
// elszabadulas lassul, es az mindig jelez — semmi nem esik ki.
import test from "node:test";
import assert from "node:assert/strict";
import { wire, task } from "./todo-fixture.mjs";
import { summarize } from "../lib/delivery-summary.mjs";
import { createRunaway } from "../lib/todo-runaway.mjs";

async function started() {
  const w = wire();
  w.api.tasks.T1 = task("T1", { owner_id: "P_KATA", assignee_id: "P_KATA" }); // a labda Katanal
  await w.w.tick();
  w.step = async (ms = 20_000) => { w.clock.t += ms; return w.w.tick(); };
  return w;
}

test("tiz erdemi komment ket agens kozott egy tetelen: mind ebreszt, nincs fek", async () => {
  const w = await started();
  for (let i = 0; i < 10; i++) {
    w.api.add("commented", "P_KATA", "T1", { body: `@thufir ${i}. kérdés: a migráció melyik sávba kerül?` }, new Date(w.clock.t).toISOString());
    await w.step(); await w.step();
    w.api.add("commented", "P_ME", "T1", { body: `@kata ${i}. válasz: a 0500-as sávba, a teszt zöld` }, new Date(w.clock.t).toISOString());
    await w.step();
  }
  assert.equal(w.injected.length, 10);
  assert.equal(w.alerts.length, 0);
  assert.equal(summarize(w.deliveryRows()).notices.todo_runaway, undefined);
});

test("sok tartalom nelkuli oda-vissza: lassul, jelez (notice + riasztas + health), de kimegy", async () => {
  const w = await started();
  for (let i = 0; i < 6; i++) {
    w.api.add("commented", "P_KATA", "T1", { body: "@thufir ok" }, new Date(w.clock.t).toISOString());
    w.api.add("commented", "P_ME", "T1", { body: "@kata ok" }, new Date(w.clock.t).toISOString());
    await w.step(10_000);
  }
  const before = w.injected.length;
  assert.equal(w.alerts.length, 1, "egy jelzes a fek-idoszakra");
  assert.match(w.alerts[0], /tartalom nélküli oda-vissza/);
  assert.equal(summarize(w.deliveryRows()).notices.todo_runaway, 1);
  assert.equal(w.health().todo_runaway, 1);
  w.api.add("commented", "P_KATA", "T1", { body: "@thufir ok" }, new Date(w.clock.t).toISOString());
  await w.step(); await w.step();
  assert.equal(w.injected.length, before, "a fek alatt gyulik");
  await w.step(5 * 60_000);
  assert.equal(w.injected.length, before + 1, "a fek vegen egy ebresztes megy ki: semmi nem veszett el");
  assert.match(w.injected.at(-1), /LASSÍTVA/);
});

test("runaway: egy szerzo sok rovid kommentje nem oda-vissza", () => {
  const sig = [];
  const r = createRunaway({ onSignal: (s) => sig.push(s) });
  for (let i = 0; i < 20; i++) r.observe({ kind: "commented", task_id: "T", actor_id: "A", diff_json: '{"body":"ok"}' }, i * 1000);
  assert.equal(sig.length, 0);
});
