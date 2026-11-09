// 11-07: token nelkul a send.mjs nem csak stderr-re ir: notice missing_token a kezbesitesi
// naploba, amit a `fleet doctor` piros jelkent mutat. Semmi nem megy ki, a kilepesi kod 1.
import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { tempDir } from "./tmp.mjs";
import { readDay } from "../lib/delivery-log.mjs";

const SEND = join(dirname(fileURLToPath(import.meta.url)), "..", "send.mjs");
const today = () => new Date().toISOString().slice(0, 10);

for (const shape of [["--chat", "1", "--", "x"], ["--chat", "1", "--text-stdin"]]) {
  test(`token nelkul: notice missing_token a naploban (${shape.join(" ")})`, () => {
    const dir = tempDir("send-notoken-");
    const r = spawnSync(process.execPath, [SEND, ...shape], {
      env: { PATH: process.env.PATH, BRIDGE_INBOX_DIR: dir, FLEET_AGENT: "probe" }, input: "x", encoding: "utf8",
    });
    assert.equal(r.status, 1);
    assert.match(r.stderr, /missing TELEGRAM_BOT_TOKEN/);
    const rows = readDay(dir, today());
    assert.equal(rows.length, 1);
    assert.equal(rows[0].type, "notice");
    assert.equal(rows[0].event, "missing_token");
    assert.equal(rows[0].detail, "probe");
  });
}
