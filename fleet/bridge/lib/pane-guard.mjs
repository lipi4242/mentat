// lib/pane-guard.mjs — all-e engedelykero ablak a pane-ben (F-17, CISO 2026-10-24).
//
// Miert: a hid minden sort `send-keys -l <szoveg>` + `Enter`-rel ad at. Ha a
// claude eppen egy engedelykero ablaknal all ("Do you want to proceed?" /
// "1. Yes"), a beirt szoveg (pl. egy "1") es az Enter a FELHASZNALO nevében
// valaszolna: hamis emberi jovahagyas. Ilyenkor a sort NEM adjuk at, hanem a
// pending-sorba megy, es a meglevo riasztas szol.
//
// A mintak a Claude Code 2.1.310 bináris szovegeibol: a kerdes ("Do you want
// to …?") ES egy "1. Yes" opcio-sor EGYUTT kell — az ugynok kimeneteben a kerdes
// onmagaban elofordulhat. Csak a pane alja szamit (ott all az ablak).
export const TAIL_LINES = 40;
const QUESTION = /Do you want to [^\n]{0,200}\?/;
const YES_OPTION = /^[\s│|]*(?:❯\s*)?1\.\s+Yes\b/m;

export function permissionDialog(text) {
  if (typeof text !== "string" || !text) return false;
  const tail = text.split("\n").slice(-TAIL_LINES).join("\n");
  return QUESTION.test(tail) && YES_OPTION.test(tail);
}

// A pane lathato szovege, vagy null (nincs session / nincs tmux / hiba).
// SOSEM dob. A `spawn` ugyanaz a varrat, mint az injectLine-e.
export function capturePane(session, spawn) {
  try {
    const r = spawn("tmux", ["capture-pane", "-p", "-t", session], { encoding: "utf8" });
    return r && r.status === 0 && typeof r.stdout === "string" ? r.stdout : null;
  } catch {
    return null;
  }
}
