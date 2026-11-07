// lib/token-lock.mjs — EGY getUpdates-hivo tokenenkent ezen a gepen (H5).
// Ket poller ugyanazon a tokenen 409-et kap, es a Telegram az update-eket
// kozottuk osztja szet: az egyik agens neman lemarad. A zar a token HASH-ere
// szol, nem az agensre — ket rosszul konfiguralt agens-konyvtar is utkozik.
//
// Node-ban nincs flock. A zarfajl SOSEM ures: a tartalom elobb egy egyedi
// tmp-fajlba irodik, es `linkSync(tmp, path)` teszi a helyere (atomikus,
// EEXIST, ha foglalt). Halott tulajdonos zarja `rename`-mel veheto at: ket
// versengo kozul csak az egyiknek sikerul. Serult zarat NEM torlunk — kezi dontes.
import { createHash, randomUUID } from "node:crypto";
import { mkdirSync, writeFileSync, readFileSync, linkSync, renameSync, unlinkSync } from "node:fs";
import { join } from "node:path";

export const lockName = (token) =>
  `tg-${createHash("sha256").update(token).digest("hex").slice(0, 12)}.lock`;

// Elo-e a pid, ES a hid-e az (pid-ujrahasznositas ellen, ahol van /proc).
// EPERM = el, csak nem a mienk. Olvashatatlan cmdline: ovatosan elonek vesszuk.
export function isBridgePid(pid, { procRoot = "/proc" } = {}) {
  try { process.kill(pid, 0); } catch (e) { if (e.code !== "EPERM") return false; }
  let cmd;
  try { cmd = readFileSync(join(procRoot, String(pid), "cmdline"), "utf8"); } catch (e) {
    return true; // nincs /proc (macOS) vagy nem olvashato: csak a kill-proba szamit
  }
  return cmd.includes("bridge.mjs");
}

const unlinkQuiet = (p) => { try { unlinkSync(p); } catch { /* mar nincs */ } };

// Tulajdonos-onellenorzes: a fajlban meg a SAJAT nonce all-e. Egy kezzel
// torolt vagy atvett zar mellett a hid nem pollozhat tovabb (ket poller).
export function stillHeld(lock) {
  try { return JSON.parse(readFileSync(lock.path, "utf8")).nonce === lock.nonce; } catch { return false; }
}

// -> {ok:true, path, nonce, release} | {ok:false, path, holder} | {ok:false, path, corrupt:true}
// `rename` csak teszt-varrat (a visszateves-verseny eloallitasahoz).
export function acquireTokenLock({ lockDir, token, pidAlive = isBridgePid, pid = process.pid,
  warn = (m) => console.error(m), rename = renameSync }) {
  mkdirSync(lockDir, { recursive: true, mode: 0o700 });
  const path = join(lockDir, lockName(token));
  const nonce = randomUUID();
  const tmp = `${path}.${pid}.${nonce}.tmp`;
  writeFileSync(tmp, JSON.stringify({ pid, nonce, started_at: new Date().toISOString() }),
    { flag: "wx", mode: 0o600 });
  const release = () => {
    try {
      if (JSON.parse(readFileSync(path, "utf8")).nonce === nonce) unlinkSync(path);
    } catch { /* nincs zar, vagy mar nem a mienk */ }
  };
  try {
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        linkSync(tmp, path);
        return { ok: true, path, nonce, release };
      } catch (e) {
        if (e.code !== "EEXIST") throw e;
      }
      let raw, held;
      try { raw = readFileSync(path, "utf8"); } catch (e) {
        if (e.code === "ENOENT") continue; // kozben eltunt: ujra link
        throw e;
      }
      try { held = JSON.parse(raw); } catch { held = null; }
      if (!held || !Number.isInteger(held.pid) || held.pid <= 0) return { ok: false, path, corrupt: true };
      if (pidAlive(held.pid)) return { ok: false, path, holder: held.pid };
      // Halott tulajdonos: rename-mel vesszuk el. Ha kozben valaki mas mar
      // atvette es UJ zarat tett a helyere, azt loptuk volna el — ellenorizzuk.
      const stale = `${path}.stale-${held.pid}.${nonce}`;
      try { rename(path, stale); } catch (e) {
        if (e.code === "ENOENT") continue;
        throw e;
      }
      let moved = null;
      try { moved = readFileSync(stale, "utf8"); } catch { /* ures marad */ }
      if (moved !== raw) {
        // Elo zarat mozditottunk el: vissza a helyere (link: nem ir felul).
        try { linkSync(stale, path); } catch (e) {
          // Kozben egy harmadik is zarat szerzett: az elmozditott tulajdonos
          // azt hiszi, nala a zar. A stillHeld-ora 30 s-on belul leallitja.
          warn(`[bridge] HIBA: token-zár visszatétele sikertelen (${path}: ${e.code}) — ` +
            "két poller is futhat, amíg a tulajdonos-ellenőrzés le nem állítja az egyiket.");
        }
        unlinkQuiet(stale);
        let h = null;
        try { h = JSON.parse(moved).pid; } catch { /* serult */ }
        return { ok: false, path, holder: h };
      }
      unlinkQuiet(stale);
    }
    return { ok: false, path, holder: null };
  } finally {
    unlinkQuiet(tmp);
  }
}
