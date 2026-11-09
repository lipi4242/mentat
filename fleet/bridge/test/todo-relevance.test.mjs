// Todo-ebresztes AC 2: mi ebreszt es mi nem — a kozos eset-lista (a desktop-hook is ezen fut).
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { classify, contentFree, mentions } from "../lib/todo-relevance.mjs";

const FIX = JSON.parse(readFileSync(new URL("./fixtures/todo-relevance.json", import.meta.url), "utf8"));

for (const c of FIX.cases) {
  test(`relevancia: ${c.name}`, () => {
    const r = classify({ seq: 1, task_id: "T1", ...c.event }, FIX.me, { id: "T1", ...c.task });
    assert.equal(r ? r.verb : null, c.verb);
  });
}

test("relevancia: a tetel nelkul (404) csak a tetel-fuggetlen szabaly ebreszt", () => {
  const me = FIX.me;
  assert.equal(classify({ kind: "item_issue", actor_id: "X", diff_json: '{"dev_id":"P_ME"}' }, me, null).verb, "kiadta");
  assert.equal(classify({ kind: "commented", actor_id: "X", diff_json: '{"body":"szia"}' }, me, null), null);
  assert.equal(classify({ kind: "commented", actor_id: "X", diff_json: "nem json" }, me, null), null);
});

test("megemlites: pontos handle, szohatar", () => {
  assert.ok(mentions("@thufir!", "thufir"));
  assert.ok(!mentions("@thufir_mac nezd", "thufir"));
  assert.ok(!mentions("a@thufir", "thufir"));
});

test("tartalom nelkuli komment: rovid nyugta igen, erdemi mondat nem", () => {
  for (const b of ["ok", "@kata ok 👍", "köszi!", "rendben", "+1", "", null]) assert.ok(contentFree(b), String(b));
  assert.ok(!contentFree("@kata a migráció a 0500-as sávba kerül, a teszt zöld"));
});
