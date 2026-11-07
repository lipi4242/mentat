// Kimeno darabolas (H1): a 4096-os plafon UTF-16 kodegysegben (JS .length),
// az (i/n) elotag a keretbe beleszamit, osszefuzve pontosan az eredeti.
import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { splitForTelegram } from "../lib/chunk.mjs";

const strip = (p) => p.replace(/^\(\d+\/\d+\) /, "");
const LOW = /^[\uDC00-\uDFFF]/;
const HIGH_END = /[\uD800-\uDBFF]$/;

// determinisztikus al-veletlen (mulberry32), hogy a hiba reprodukalhato legyen
function rng(seed) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const ATOMS = ["a", "é", "ő", "🙂", "👍🏽", " ", "\n", "\n\n", "árvíztűrő"];
function randomText(r, len) {
  let s = "";
  while (s.length < len) s += ATOMS[Math.floor(r() * ATOMS.length)];
  return s;
}

function checkInvariants(s, parts, max) {
  for (const p of parts) assert.ok(p.length <= max, `darab ${p.length} > ${max}`);
  if (parts.length === 1) assert.equal(parts[0], s, "egy darab: elotag nelkul");
  else parts.forEach((p, i) => assert.ok(p.startsWith(`(${i + 1}/${parts.length}) `), p.slice(0, 12)));
  assert.equal(parts.map(strip).join(""), s);
  for (const p of parts) {
    assert.ok(!LOW.test(strip(p)), "alacsony surrogate a darab elejen");
    assert.ok(!HIGH_END.test(p), "magas surrogate a darab vegen");
  }
}

test("<=4096 = egy darab, elotag nelkul", () => {
  assert.deepEqual(splitForTelegram("szia"), ["szia"]);
  const s = "x".repeat(4096);
  assert.deepEqual(splitForTelegram(s), [s]);
  assert.deepEqual(splitForTelegram(""), [""]);
});

test("4097 -> 2 darab, (1/2) (2/2) elotaggal", () => {
  const parts = splitForTelegram("x".repeat(4097));
  assert.equal(parts.length, 2);
  checkInvariants("x".repeat(4097), parts, 4096);
});

test("hatar-preferencia: \\n\\n -> \\n -> szokoz -> kemeny vagas", () => {
  const max = 40, a = "a".repeat(20);
  assert.equal(strip(splitForTelegram(`${a}\n\n${a} b\nc`, max)[0]), `${a}\n\n`);
  assert.equal(strip(splitForTelegram(`${a}\nb ${a}`, max)[0]), `${a}\n`);
  assert.equal(strip(splitForTelegram(`${a} ${a}`, max)[0]), `${a} `);
  const hard = splitForTelegram("b".repeat(100), max);
  assert.equal(hard[0].length, max);
  checkInvariants("b".repeat(100), hard, max);
});

test("surrogate par sosem torik kette kemeny vagasnal", () => {
  for (let off = 0; off < 3; off++) {
    const s = "x".repeat(off) + "🙂".repeat(5000);
    checkInvariants(s, splitForTelegram(s), 4096);
  }
});

test("property: 20 veletlen hossz 1..20000 emoji + \\n keverekkel", () => {
  const r = rng(42);
  for (let k = 0; k < 20; k++) {
    const s = randomText(r, 1 + Math.floor(r() * 20000));
    checkInvariants(s, splitForTelegram(s, 4096), 4096);
  }
});

test("sok darab: az elotag hossza a darabszam jegyeitol fugg (n >= 10)", () => {
  const s = "z".repeat(50000);
  const parts = splitForTelegram(s);
  assert.ok(parts.length >= 10);
  checkInvariants(s, parts, 4096);
  assert.ok(parts[0].startsWith(`(1/${parts.length}) `));
});

// Codex-review: tul kicsi keretnel (az elotag utan < 2 hely) a ciklus sosem allt
// meg. Kulon processzben fut, hogy egy regresszio ne fagyassza a tesztfutast.
function runChild(expr) {
  const src = `import { splitForTelegram } from ${JSON.stringify(new URL("../lib/chunk.mjs", import.meta.url).href)};
try { ${expr}; console.log("NINCS-HIBA"); } catch (e) { console.log(e.name); }`;
  return spawnSync(process.execPath, ["--input-type=module", "-e", src], { encoding: "utf8", timeout: 5000 });
}

test("tul kicsi max -> RangeError, nem vegtelen ciklus", () => {
  const r = runChild(`splitForTelegram("abcdefg", 6)`);
  assert.equal(r.error?.code, undefined, "a hivas fagyott (timeout)");
  assert.equal(r.stdout.trim(), "RangeError");
  assert.throws(() => splitForTelegram("x".repeat(20), 15), RangeError);
});

test("hatarnyi max + oriasi szoveg: a novekvo elotag elfogyasztja a keretet -> RangeError", () => {
  const r = runChild(`splitForTelegram("x".repeat(200000), 16)`);
  assert.equal(r.error?.code, undefined, "a hivas fagyott (timeout)");
  assert.equal(r.stdout.trim(), "RangeError");
  const s = "y".repeat(40);
  checkInvariants(s, splitForTelegram(s, 16), 16);
});
