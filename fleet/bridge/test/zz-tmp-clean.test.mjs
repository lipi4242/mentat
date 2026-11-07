// The bridge tests leave nothing in the temp folder (2026-10-23: 338 receipt-* fake HOMEs,
// 564 MB, filled the shared tmp quota of the thufir user twice — EDQUOT for every agent).
// Runs every other bridge test file with a fresh TMPDIR and counts what is left.
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));

test("a full bridge test run leaves 0 folders in TMPDIR", () => {
  const fresh = mkdtempSync(join(tmpdir(), "zz-tmp-clean-"));
  try {
    const files = readdirSync(HERE).filter((f) => f.endsWith(".test.mjs") && f !== basename(fileURLToPath(import.meta.url)))
      .map((f) => join(HERE, f));
    const env = { ...process.env, TMPDIR: fresh };
    delete env.NODE_TEST_CONTEXT; // a nested `node --test` must run its files, not report to us
    const r = spawnSync(process.execPath, ["--test", ...files], { env, encoding: "utf8" });
    assert.equal(r.status, 0, r.stdout.slice(-2000) + r.stderr.slice(-2000));
    const left = readdirSync(fresh);
    assert.deepEqual(left, [], `${left.length} temp folders left: ${left.slice(0, 8).join(", ")}`);
  } finally {
    rmSync(fresh, { recursive: true, force: true });
  }
});
