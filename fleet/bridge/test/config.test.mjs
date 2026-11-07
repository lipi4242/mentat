import test from "node:test";
import assert from "node:assert/strict";
import { loadConfig } from "../lib/config.mjs";

const FULL = {
  TELEGRAM_BOT_TOKEN: "t", TELEGRAM_GROUP_CHAT_ID: "-1", TELEGRAM_ALLOWLIST_IDS: "1,2",
  TMUX_SESSION: "s", BRIDGE_STATE_DIR: "/tmp/x",
};

test("all required present -> config with parsed fields", () => {
  const c = loadConfig(FULL);
  assert.equal(c.session, "s");
  assert.deepEqual(c.allowIds, ["1", "2"]);
  assert.equal(c.requireMention, true);
  assert.equal(c.startupBacklog, "skip");
});

test("missing required env is fatal and names ALL missing", () => {
  assert.throws(() => loadConfig({ TELEGRAM_BOT_TOKEN: "t" }),
    (e) => e.message.includes("TMUX_SESSION") && e.message.includes("BRIDGE_STATE_DIR"));
});

test("startup backlog only accepts skip|process", () => {
  assert.equal(loadConfig({ ...FULL, BRIDGE_STARTUP_BACKLOG: "process" }).startupBacklog, "process");
  assert.throws(() => loadConfig({ ...FULL, BRIDGE_STARTUP_BACKLOG: "yolo" }));
});

test("mention gating default true, opt-out explicit", () => {
  assert.equal(loadConfig({ ...FULL, BRIDGE_REQUIRE_MENTION: "false" }).requireMention, false);
});

test("agentLabel defaults to session name, explicit env wins", () => {
  assert.equal(loadConfig(FULL).agentLabel, "s");
  assert.equal(
    loadConfig({ ...FULL, BRIDGE_AGENT_LABEL: "Gamma" }).agentLabel,
    "Gamma",
  );
});

test("BRIDGE_LOCK_CHECK_MS: nem-szam vagy <1000 -> 30000", () => {
  assert.equal(loadConfig(FULL).lockCheckMs, 30_000);
  assert.equal(loadConfig({ ...FULL, BRIDGE_LOCK_CHECK_MS: "5000" }).lockCheckMs, 5000);
  for (const v of ["abc", "0", "999", "-5", "NaN", "Infinity"])
    assert.equal(loadConfig({ ...FULL, BRIDGE_LOCK_CHECK_MS: v }).lockCheckMs, 30_000, v);
});
