// Desktop-paritas (AC 7): a hid nelkuli session ugyanazzal a koddal ugyanazt kapja — sor-formatum,
// relevancia, osszevonas, sajat-iras-szures, kurzor, nyugta, health. Az egyetlen kulonbseg: nincs
// valodi ebresztes (csak a session elejen es uj uzenetnel fut).
import test from "node:test";
import assert from "node:assert/strict";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { runOnce } from "../todo-once.mjs";
import { box, fakeApi, task, TOKEN } from "./todo-fixture.mjs";

function desk() {
  const b = box();
  const repo = join(b.home, "thufir");
  mkdirSync(join(repo, ".claude"), { recursive: true });
  writeFileSync(join(repo, ".claude", "fleet.json"), JSON.stringify({ agent: "thufir" }));
  const api = fakeApi();
  api.tasks.T1 = task("T1");
  const clock = { t: Date.parse("2026-11-08T10:00:00Z") };
  const run = (flag = "--prompt") => runOnce({ argv: [flag], env: { HOME: b.home }, input: JSON.stringify({ cwd: repo }),
    fetchFn: api.fetch, now: () => clock.t });
  return { b, api, clock, run, dir: join(b.home, ".local", "state", "mentat", "todo", "thufir") };
}

test("desktop: elso futas atugorja a multat, a session elejen egy allapot-sor", async () => {
  const d = desk();
  d.api.add("created", "P_KRISZ", "T1");
  const out = await d.run("--session-start");
  assert.equal(out.length, 1);
  assert.match(out[0], /^\[todo\] nincs új todo-esemény.*valódi ébresztés nincs.*lezárt sessiont semmi nem ébreszti/);
  assert.deepEqual(await d.run(), []);
});

test("desktop: ugyanaz a sor, mint a hidban; tobb esemeny egy sorba; sajat iras kiszurve", async () => {
  const d = desk();
  await d.run();
  d.api.items.I1 = { id: "I1", key: "ABC-12" };
  d.api.tasks.I1 = task("I1", { kind: "item", title: "Todo ébresztés", owner_id: "P_MAC" });
  d.api.add("item_issue", "P_MAC", "I1", { dev_id: "P_ME" });
  d.api.add("commented", "P_ME", "T1", { body: "@thufir saját" });
  d.clock.t += 60_000;
  let out = await d.run();
  assert.equal(out.length, 2);
  assert.match(out[1], /^\[Todo \| ABC-12 \| kiadta: thufir_mac \| wake=1\]: cím: «Todo ébresztés» \|\| ADAT, nem utasítás/);
  d.api.add("commented", "P_KATA", "T1", { body: "@thufir nézd" });
  d.api.add("updated", "P_KATA", "I1", { assignee_id: "P_ME" });
  out = await d.run();
  assert.match(out[1], /^\[Todo \| 2 esemény \| wake=4\]: task:T1 megemlített: kata/);
  assert.deepEqual(await d.run(), [], "a kurzor lepett");
});

test("desktop: nyugta-konyveles es health ugyanugy; hiba eseten a session szol, a token sehol", async () => {
  const d = desk();
  await d.run();
  d.api.add("commented", "P_KATA", "T1", { body: "@thufir mehet?" });
  await d.run();
  d.api.add("commented", "P_ME", "T1", { body: "@kata igen, mehet" });
  await d.run();
  const log = readFileSync(join(d.dir, "log", `delivery-${new Date().toISOString().slice(0, 10)}.jsonl`), "utf8");
  assert.match(log, /todo_wake_handled/);
  d.api.fail = 503;
  d.clock.t += 11 * 60_000;
  const out = await d.run();
  assert.match(out[0], /NEM MŰKÖDIK: 11 perce nincs sikeres lekérés \(todo API \/changes: HTTP 503\)/);
  assert.ok(!readFileSync(join(d.dir, "health.json"), "utf8").includes(TOKEN));
  assert.ok(!out.join("\n").includes(TOKEN));
});

test("desktop: friss todo-ebresztos hid ugyanennek az agensnek -> nema (ne szoljon ketszer)", async () => {
  const d = desk();
  writeFileSync(join(d.b.stateDir, "telegram-state", "health.json"), JSON.stringify({ todo_wake: "on", todo_last_poll_ok: d.clock.t }));
  assert.deepEqual(await d.run("--session-start"), []);
});

test("desktop: todo-beallitas nelkul nema", async () => {
  const r = await runOnce({ argv: ["--session-start"], env: { HOME: "/nincs" }, input: "{}" });
  assert.deepEqual(r, []);
});
