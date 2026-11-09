// lib/config.mjs — a hid env-szerzodese. A kotelezo mezoknek NINCS defaultjuk:
// egy rossz agent ala inditott hid rossz botot pollozna es rossz tmux sessionbe
// injektalna — inkabb fatalisan alljon le.
import { homedir } from "node:os";
import { join } from "node:path";
import { parseWebhookConfig } from "./webhook-config.mjs";
import { parseWebhookTargets } from "./webhook-targets.mjs";
import { parseTodoConfig } from "./todo-config.mjs";

const REQUIRED = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_GROUP_CHAT_ID",
  "TELEGRAM_ALLOWLIST_IDS", "TMUX_SESSION", "BRIDGE_STATE_DIR"];

// Nem-szam, vegtelen vagy <1000 ms -> 30 s (a tul suru onellenorzes csak terhel).
const lockCheckMs = (v) => {
  const n = Number(v);
  return v != null && v !== "" && Number.isFinite(n) && n >= 1000 ? n : 30_000;
};

export function loadConfig(env) {
  const missing = REQUIRED.filter((k) => !env[k]);
  if (missing.length) throw new Error(`missing required env: ${missing.join(", ")}`);
  const startupBacklog = env.BRIDGE_STARTUP_BACKLOG || "skip";
  if (!["skip", "process"].includes(startupBacklog))
    throw new Error(`BRIDGE_STARTUP_BACKLOG must be skip|process, got ${startupBacklog}`);
  const stateDir = env.BRIDGE_STATE_DIR;
  return {
    token: env.TELEGRAM_BOT_TOKEN,
    groupId: String(env.TELEGRAM_GROUP_CHAT_ID),
    allowIds: env.TELEGRAM_ALLOWLIST_IDS.split(",").map((s) => s.trim()).filter(Boolean),
    session: env.TMUX_SESSION,
    stateDir,
    offsetFile: env.BRIDGE_OFFSET_FILE || `${stateDir}/telegram-state/bridge-offset.json`,
    pendingFile: env.BRIDGE_PENDING_FILE || `${stateDir}/telegram-state/bridge-pending.json`,
    inboxDir: env.BRIDGE_INBOX_DIR || `${stateDir}/telegram-inbox`,
    healthFile: env.BRIDGE_HEALTH_FILE || `${stateDir}/telegram-state/health.json`,
    mediaQueueFile: env.BRIDGE_MEDIA_QUEUE_FILE || `${stateDir}/telegram-state/media-queue.json`,
    maxFileBytes: Number(env.BRIDGE_MAX_FILE_BYTES || 12 * 1024 * 1024),
    retentionDays: Number(env.BRIDGE_RETENTION_DAYS || 14),
    albumDebounceMs: Number(env.BRIDGE_ALBUM_DEBOUNCE_MS || 2500),
    pendingRetryMs: Number(env.BRIDGE_PENDING_RETRY_MS || 30_000),
    pendingAlertMs: Number(env.BRIDGE_PENDING_ALERT_MS || 10 * 60_000),
    conflictAlertMs: Number(env.BRIDGE_CONFLICT_ALERT_MS || 15 * 60_000),
    maxPending: Number(env.BRIDGE_MAX_PENDING || 500),
    requireMention: (env.BRIDGE_REQUIRE_MENTION || "true") !== "false",
    startupBacklog,
    // selfAlert megszolal a csoportnak — a felirat mondja meg, MELYIK agent
    // hidja szol, hogy tobb telepitett hid eseten ne egy fix nev beszeljen mindig.
    // Default a session neve, sose fix nev.
    agentLabel: env.BRIDGE_AGENT_LABEL || env.TMUX_SESSION,
    // Tokenenkenti zar (H5): felhasznalonkent KOZOS hely, NEM a state-bol szarmaztatva
    // — kulonbozo szuloju state-ek ugyanarra a tokenre igy is utkoznek. Nem fugg az
    // XDG_RUNTIME_DIR-tol: a systemd alatti es a kezi/cron futas ugyanazt a zarat latja.
    lockDir: env.BRIDGE_LOCK_DIR || join(env.HOME || homedir(), ".config", "sub-etha-locks"),
    // Jovahagyo webhook (3.1): hibas beallitas nem fatalis, csak KI (reason).
    webhook: parseWebhookConfig(env),
    // Tobb nevesitett cel (SUBETHA_WEBHOOKS) + a fenti mint `default` cel.
    webhooks: parseWebhookTargets(env),
    webhookQueueFile: env.BRIDGE_WEBHOOK_QUEUE_FILE || `${stateDir}/telegram-state/webhook-queue.json`,
    lockCheckMs: lockCheckMs(env.BRIDGE_LOCK_CHECK_MS),
    // Erkezes-nyugta (3.2): agensenkent kapcsolva, mint a BRIDGE_REPLY_HINT.
    receipt: env.BRIDGE_RECEIPT === "1",
    sessionIdFile: env.BRIDGE_SESSION_ID_FILE || `${stateDir}/session.id`,
    transcriptRoot: env.BRIDGE_TRANSCRIPT_ROOT || join(env.HOME || "", ".claude", "projects"),
    receiptFile: `${stateDir}/telegram-state/receipts.json`,
    // Todo-ebresztes: a box todo-beallitasabol; nincs todo = KI, sosem fatalis.
    todo: parseTodoConfig(env, stateDir),
    // Csak tesztnek (helyi hamis Telegram) — ugyanaz a nev, mint a send.mjs-ben.
    telegramApi: env.SUBETHA_TELEGRAM_API || "https://api.telegram.org",
  };
}
