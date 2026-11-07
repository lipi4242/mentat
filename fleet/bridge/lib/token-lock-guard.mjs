// lib/token-lock-guard.mjs — a token-zar (H5) a hid main()-jeben.
// A 75 (EX_TEMPFAIL) a Restart=always mellett hangos hurok a journalban, nem
// nema kieses. A lemezirasok szinkronok, igy a jelkezelo sosem vag felbe
// irast; az exit-kezelo csak a SAJAT nonce-u zarat torli.
import { acquireTokenLock, stillHeld } from "./token-lock.mjs";

const fatal = (msg) => {
  console.error(`[bridge] FATAL: ${msg}`);
  process.exit(75);
};

export function holdTokenLockOrExit({ lockDir, token, checkMs = 30_000 }) {
  let lock;
  try {
    lock = acquireTokenLock({ lockDir, token });
  } catch (e) {
    return fatal(`token-zár könyvtár nem írható (${lockDir}): ${e.code || e.message}`);
  }
  if (!lock.ok) {
    return fatal(lock.corrupt
      ? `token-zár sérült (${lock.path}) — kézi ellenőrzés után töröld ezt a fájlt.`
      : `token-zár foglalt (${lock.path}, pid=${lock.holder}) — ` +
        "ezen a gépen már fut egy poller erre a bot-tokenre. Egy tokenre EGY poller.");
  }
  process.on("exit", lock.release);
  for (const s of ["SIGTERM", "SIGINT"]) process.on(s, () => process.exit(0));
  // Onellenorzes: ha a zarat elvettek (kezi torles, versenyben atvetel), leallunk.
  setInterval(() => {
    if (!stillHeld(lock)) fatal(`token-zár elveszett (${lock.path}) — már nem a miénk, a poller leáll.`);
  }, checkMs).unref?.();
  return lock;
}
