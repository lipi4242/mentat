import test from "node:test";
import assert from "node:assert/strict";
import { capPending } from "../lib/pending.mjs";

test("under cap: appends, nothing dropped", () => {
  const r = capPending([{ line: "a" }], { line: "b" }, 3);
  assert.equal(r.items.length, 2);
  assert.equal(r.dropped, 0);
});

test("at cap: oldest dropped, newest kept", () => {
  const r = capPending([{ line: "a" }, { line: "b" }], { line: "c" }, 2);
  assert.deepEqual(r.items.map((i) => i.line), ["b", "c"]);
  assert.equal(r.dropped, 1);
});
