// 11-07: `send.mjs --dry-run` — a kepesseg-proba utja. Token/chat/kapcsolo/kapu/naplo
// ellenorzes, de SEMMI nem megy ki (a hamis Telegram-cim nem is letezik), es a naploba sem ir.
import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { tempDir } from "./tmp.mjs";

const SEND = join(dirname(fileURLToPath(import.meta.url)), "..", "send.mjs");
const TOKEN = "123456789:HAMIS_ertek_nem_valodi_0123456789abcd";
const run = (args, extra = {}) => {
  const dir = tempDir("send-dry-");
  const r = spawnSync(process.execPath, [SEND, ...args], { encoding: "utf8", input: "x",
    env: { PATH: process.env.PATH, BRIDGE_INBOX_DIR: dir, SUBETHA_TELEGRAM_API: "http://127.0.0.1:9", ...extra } });
  return { ...r, dir };
};
const rows = (dir) => (existsSync(dir) ? readdirSync(dir).filter((f) => f.startsWith("delivery-")) : []);

test("dry-run: minden rendben -> 0, semmi nem ment ki, naplo-sor sincs", () => {
  const r = run(["--dry-run", "--chat", "-100123", "--", "proba"], { TELEGRAM_BOT_TOKEN: TOKEN });
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /dry-run OK/);
  assert.doesNotMatch(r.stdout + r.stderr, /HAMIS_ertek/);
  assert.deepEqual(rows(r.dir), []);
});

test("dry-run: token nelkul -> 1, es NEM ir missing_token notice-t (a proba nem kuldes)", () => {
  const r = run(["--dry-run", "--chat", "1", "--", "x"]);
  assert.equal(r.status, 1);
  assert.match(r.stderr, /missing TELEGRAM_BOT_TOKEN/);
  assert.deepEqual(rows(r.dir), []);
});

test("dry-run: hibas alaku token -> 1, az ertek nem latszik", () => {
  const r = run(["--dry-run", "--chat", "1", "--", "x"], { TELEGRAM_BOT_TOKEN: "rossz-ertek-xyz" });
  assert.equal(r.status, 1);
  assert.match(r.stderr, /alakja hibas/);
  assert.doesNotMatch(r.stderr, /rossz-ertek/);
});

test("dry-run: chat nelkul vagy rossz chattel -> 1", () => {
  assert.equal(run(["--dry-run", "--", "x"], { TELEGRAM_BOT_TOKEN: TOKEN }).status, 1);
  assert.equal(run(["--dry-run", "--chat", "nem-chat", "--", "x"], { TELEGRAM_BOT_TOKEN: TOKEN }).status, 1);
});

test("dry-run: a hosszusag-kapu is el (exit 4)", () => {
  const r = run(["--dry-run", "--chat", "1", "--", "x".repeat(50)],
    { TELEGRAM_BOT_TOKEN: TOKEN, SUBETHA_LENGTH_GATE: "1", SUBETHA_MAX_CHARS: "10" });
  assert.equal(r.status, 4);
});

test("dry-run: a -- utani `--dry-run` szoveg, nem kapcsolo (a kuldes utja marad)", () => {
  const r = run(["--chat", "1", "--", "--dry-run"]);
  assert.equal(r.status, 1);
  assert.match(r.stderr, /missing TELEGRAM_BOT_TOKEN \(a unit env-jebol kell jonnie; a hiba/);
});
