// Egy implementacio a hidnak es a desktopnak: a fleet plugin hooks/todo/ alatt a todo-once.mjs es a
// teljes import-lezartja BAJTRA azonos masolat (a plugin csak a sajat konyvtarat szallitja).
// Ha piros: `node bridge/test/todo-plugin-copy.test.mjs --sync` (a fleet/ alol) ujramasolja.
import test from "node:test";
import assert from "node:assert/strict";
import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const BRIDGE = join(dirname(fileURLToPath(import.meta.url)), "..");
const PLUGIN = join(BRIDGE, "..", "plugin", "hooks", "todo");

export function closure(entry = "todo-once.mjs") {
  const seen = new Set();
  const walk = (rel) => {
    if (seen.has(rel)) return;
    seen.add(rel);
    const src = readFileSync(join(BRIDGE, rel), "utf8");
    for (const m of src.matchAll(/^(?:import|export) [^;]*?from "(\.[^"]+)";/gms)) walk(normalize(join(dirname(rel), m[1])));
  };
  walk(entry);
  return [...seen].sort();
}

if (process.argv.includes("--sync")) {
  for (const rel of closure()) { mkdirSync(dirname(join(PLUGIN, rel)), { recursive: true }); copyFileSync(join(BRIDGE, rel), join(PLUGIN, rel)); }
  console.log(`szinkronizalva: ${closure().join(", ")}`);
} else {
  test("plugin todo-masolat: a todo-once.mjs import-lezartja bajtra azonos a hidéval", () => {
    for (const rel of closure()) {
      const p = join(PLUGIN, rel);
      assert.ok(existsSync(p), `hianyzik a pluginbol: ${rel} (futtasd: node bridge/test/todo-plugin-copy.test.mjs --sync)`);
      assert.ok(readFileSync(p).equals(readFileSync(join(BRIDGE, rel))), `elter: ${rel} (--sync)`);
    }
  });
  test("plugin todo-masolat: nincs benne felesleges (regi) fajl", () => {
    const want = new Set(closure());
    const have = ["todo-once.mjs", ...readdirSync(join(PLUGIN, "lib")).map((f) => `lib/${f}`)].filter((f) => f.endsWith(".mjs"));
    assert.deepEqual(have.filter((f) => !want.has(f)), []);
  });
}
