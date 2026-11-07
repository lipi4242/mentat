// H5: egy tokenre EGY getUpdates-hivo ezen a gepen. Egysegszint (lib/token-lock)
// es folyamatszint (ket valodi `node bridge.mjs`, hamis Telegrammal).
import test from "node:test";
import { tempDir } from "./tmp.mjs";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, renameSync, readFileSync, readdirSync, existsSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { acquireTokenLock, lockName, isBridgePid, stillHeld } from "../lib/token-lock.mjs";
import { loadConfig } from "../lib/config.mjs";

const tmp = () => tempDir("tl-");
const live = () => true;
const dead = () => false;

test("zarfajl a token hash-ere szol, tartalma pid+nonce+started_at, a token NEM", () => {
  const lockDir = join(tmp(), "locks");
  const l = acquireTokenLock({ lockDir, token: "SECRET-TOKEN", pidAlive: live });
  assert.equal(l.ok, true);
  assert.match(lockName("SECRET-TOKEN"), /^tg-[0-9a-f]{12}\.lock$/);
  assert.equal(l.path, join(lockDir, lockName("SECRET-TOKEN")));
  const raw = readFileSync(l.path, "utf8");
  assert.equal(raw.includes("SECRET-TOKEN"), false);
  const o = JSON.parse(raw);
  assert.equal(o.pid, process.pid);
  assert.equal(typeof o.nonce, "string");
  assert.ok(o.started_at);
  assert.equal(statSync(l.path).mode & 0o777, 0o600);
  assert.equal(statSync(lockDir).mode & 0o777, 0o700);
  assert.deepEqual(readdirSync(lockDir), [lockName("SECRET-TOKEN")]); // tmp eltakaritva
  l.release();
  assert.equal(existsSync(l.path), false);
});

test("elo tulajdonos mellett a masodik acquire ok:false, holder = pid", () => {
  const lockDir = tmp();
  const a = acquireTokenLock({ lockDir, token: "T", pidAlive: live });
  const b = acquireTokenLock({ lockDir, token: "T", pidAlive: live });
  assert.equal(a.ok, true);
  assert.equal(b.ok, false);
  assert.equal(b.holder, process.pid);
  assert.equal(existsSync(a.path), true);
});

test("halott pid zarja atveheto, az uj tulajdonos nonce-a all a fajlban", () => {
  const lockDir = tmp();
  const path = join(lockDir, lockName("T"));
  writeFileSync(path, JSON.stringify({ pid: 999999, nonce: "old", started_at: 1 }));
  const l = acquireTokenLock({ lockDir, token: "T", pidAlive: dead });
  assert.equal(l.ok, true);
  assert.equal(JSON.parse(readFileSync(path, "utf8")).nonce, l.nonce);
  assert.deepEqual(readdirSync(lockDir), [lockName("T")]);
});

test("release idegen nonce mellett NEM torol", () => {
  const lockDir = tmp();
  const l = acquireTokenLock({ lockDir, token: "T", pidAlive: live });
  writeFileSync(l.path, JSON.stringify({ pid: 4242, nonce: "masik", started_at: 1 }));
  l.release();
  assert.equal(existsSync(l.path), true);
});

test("serult zar: ok:false corrupt:true, a fajl NEM torlodik", () => {
  const lockDir = tmp();
  const path = join(lockDir, lockName("T"));
  writeFileSync(path, "");
  const l = acquireTokenLock({ lockDir, token: "T", pidAlive: dead });
  assert.equal(l.ok, false);
  assert.equal(l.corrupt, true);
  assert.equal(l.path, path);
  assert.equal(existsSync(path), true);
});

test("isBridgePid: /proc cmdline-nal a bridge.mjs-nek benne kell lennie", () => {
  const proc = tmp();
  mkdirSync(join(proc, String(process.pid)));
  writeFileSync(join(proc, String(process.pid), "cmdline"), "node\0/x/other.mjs\0");
  assert.equal(isBridgePid(process.pid, { procRoot: proc }), false); // ujrahasznositott pid
  writeFileSync(join(proc, String(process.pid), "cmdline"), "node\0/x/bridge.mjs\0");
  assert.equal(isBridgePid(process.pid, { procRoot: proc }), true);
  assert.equal(isBridgePid(process.pid, { procRoot: join(proc, "nincs") }), true); // nincs /proc: csak kill
  assert.equal(isBridgePid(999999, { procRoot: proc }), false);
});

test("config: lockDir BRIDGE_LOCK_DIR > $HOME/.config/sub-etha-locks (XDG_RUNTIME_DIR-tol fuggetlen); telegramApi varrat", () => {
  const base = { TELEGRAM_BOT_TOKEN: "t", TELEGRAM_GROUP_CHAT_ID: "-1", TELEGRAM_ALLOWLIST_IDS: "1",
    TMUX_SESSION: "s", BRIDGE_STATE_DIR: "/srv/agent-a/state", HOME: "/home/a" };
  const shared = "/home/a/.config/sub-etha-locks";
  assert.equal(loadConfig(base).lockDir, shared);
  // kulonbozo szuloju state-ek ugyanarra a tokenre: UGYANAZ a zarkonyvtar
  assert.equal(loadConfig({ ...base, BRIDGE_STATE_DIR: "/home/b/x/y/state" }).lockDir, shared);
  // systemd (XDG_RUNTIME_DIR) es kezi/cron futas (nincs) ugyanazt a zarat latja
  assert.equal(loadConfig({ ...base, XDG_RUNTIME_DIR: "/run/user/1" }).lockDir, shared);
  assert.equal(loadConfig({ ...base, XDG_RUNTIME_DIR: "/run/user/1", BRIDGE_LOCK_DIR: "/l" }).lockDir, "/l");
  assert.equal(loadConfig(base).telegramApi, "https://api.telegram.org");
  assert.equal(loadConfig({ ...base, SUBETHA_TELEGRAM_API: "http://x" }).telegramApi, "http://x");
});

test("stillHeld: sajat nonce -> true; atirt, torolt zar -> false", () => {
  const lockDir = tmp();
  const l = acquireTokenLock({ lockDir, token: "T", pidAlive: live });
  assert.equal(stillHeld(l), true);
  writeFileSync(l.path, JSON.stringify({ pid: 4242, nonce: "masik", started_at: 1 }));
  assert.equal(stillHeld(l), false);
  l.release(); // idegen: marad
  writeFileSync(l.path, "{");
  assert.equal(stillHeld(l), false);
});

test("visszateves-verseny: elmozditott elo zar + harmadik szerzo -> hangos warn, ok:false", () => {
  const lockDir = tmp();
  const path = join(lockDir, lockName("T"));
  const dead = JSON.stringify({ pid: 999999, nonce: "halott", started_at: 1 });
  writeFileSync(path, dead);
  const warns = [];
  // A halott zar olvasasa utan B atveszi (uj tartalom), a mi rename-unk
  // utan C is szerez: a visszateves EEXIST-re fut.
  const l = acquireTokenLock({
    lockDir, token: "T", warn: (m) => warns.push(m),
    pidAlive: (p) => { if (p === 999999) writeFileSync(path, JSON.stringify({ pid: 5, nonce: "B" })); return p !== 999999; },
    rename: (a, b) => { renameSync(a, b); writeFileSync(path, JSON.stringify({ pid: 6, nonce: "C" })); },
  });
  assert.equal(l.ok, false);
  assert.equal(l.holder, 5);
  assert.equal(warns.length, 1);
  assert.match(warns[0], /token-zár visszatétele sikertelen/);
  assert.equal(JSON.parse(readFileSync(path, "utf8")).nonce, "C");
});
