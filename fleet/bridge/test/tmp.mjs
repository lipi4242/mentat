// Temp folders for the bridge tests, removed when the test process exits (2026-10-23: the
// receipt tests' fake HOMEs filled the shared tmp quota). Use tempDir() instead of mkdtempSync.
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const made = [];
export function tempDir(prefix) {
  const d = mkdtempSync(join(tmpdir(), prefix));
  made.push(d);
  return d;
}
process.on("exit", () => {
  for (const d of made) {
    try { rmSync(d, { recursive: true, force: true }); } catch { /* best effort at exit */ }
  }
});
