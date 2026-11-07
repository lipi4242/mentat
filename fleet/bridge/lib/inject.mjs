// lib/inject.mjs — a tmux-kezbesites nyers magja (a lib/deliverer.mjs hivja).
//
// Szandekosan MINIMALIS: egyetlen sor betolese egy tmux sessionbe. Ami NEM ide
// tartozik: a pending-sor, a health-iras, a riasztas — azok a hivo
// (lib/deliverer.mjs) dolgai, mert kezbesitesi POLITIKAT jelentenek, nem mechanikat.
//
// Biztonsagi kikotesek (valtozatlanul a bridge-bol):
//   - spawnSync TOMB-argumentumokkal: a szoveg SOHA nem er shell-t;
//   - `-l` => literal (nincs kulcsnev-ertelmezes, tehat egy "C-c" szoveg nem
//     lesz billentyu-kombinacio), `--` => opciok vege;
//   - a sor lezarasa KULON send-keys Enter — a literal modban a \n maga nem
//     kuldene el a promptot.
//   - HOSSZU sornal (LONG_LINE_CHARS felett) a szoveg es az Enter kozott
//     PASTE_SETTLE_MS varakozas: a Claude-felulet (2.1.302) a nagy bemenetet
//     paste-kent gyujti, es a kozvetlenul utana jovo Entert ELNYELI — a sor
//     elkuldetlenul ul a promptban, a kovetkezo sor Enterje viszi el ketto
//     egy bejegyzesben (elo proba: varakozas nelkul 5/135 elnyelt Enter, vele 0/120).
//     Egy Enter megy ki, nem ketto: a dupla Enter szukseget a meres nem igazolta.
//   - ENGEDELYKERO ABLAKNAL (lib/pane-guard.mjs, F-17) semmi nem megy ki: se a
//     szoveg, se az Enter — {ok:false, dialog:true}, a hivo pending-sorba teszi.
//     Ha a pane nem olvashato, a regi ut fut (a send-keys ugyis elbukna).
import { spawnSync } from "node:child_process";
import { capturePane, permissionDialog } from "./pane-guard.mjs";

export const LONG_LINE_CHARS = 1000;
export const PASTE_SETTLE_MS = 300;

// Szinkron alvas busy-loop nelkul (a hivok szinkron API-t varnak).
export function sleepMs(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

// Visszater: {ok:true} | {ok:false, error:"<olvashato ok>"}
// SOSEM dob: a spawnSync hibajat (a.error) is az error mezoben adja vissza —
// a hivo kezbesitesi utja igy egyetlen agon fut, nem try/catch-ben.
// A `spawn` parameter TESZT-varrat (injektalt spawnSync), alapertelmezetten
// a valos node:child_process spawnSync; a `wait` szinten varrat (sleepMs).
export function injectLine(session, line, spawn = spawnSync, wait = sleepMs) {
  if (permissionDialog(capturePane(session, spawn))) {
    return { ok: false, dialog: true,
      error: "engedélykérő ablak áll a pane-ben — nem írok bele, nem nyomok Entert (F-17)" };
  }
  const a = spawn("tmux", ["send-keys", "-t", session, "-l", "--", line], {
    encoding: "utf8",
  });
  if (!a || a.status !== 0) {
    return { ok: false, error: `send-keys(text) failed: ${a?.stderr || a?.error?.message}` };
  }
  if (line.length > LONG_LINE_CHARS) wait(PASTE_SETTLE_MS);
  const b = spawn("tmux", ["send-keys", "-t", session, "Enter"], {
    encoding: "utf8",
  });
  if (!b || b.status !== 0) {
    return { ok: false, error: `send-keys(Enter) failed: ${b?.stderr || b?.error?.message}` };
  }
  return { ok: true };
}
