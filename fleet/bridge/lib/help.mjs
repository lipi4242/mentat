// lib/help.mjs — /help es "sugo" Telegramon: ugyanaz a valasz, mint a Claude Code /mentat
// parancsae. A hid az agens repojaban futtatja a .mentat/bin/mentat_help.py-t (kezzel irt,
// verziozott szoveg + mentat.json), es a kimenetet valaszkent kuldi. LLM nem fogalmaz, a
// pane-be nem megy. Ha nincs eszkoz, hibazik, vagy a kuldes elbukik: a sima kezbesites marad
// (az agens maga valaszol), tehat a kerest sosem nyeljuk el.
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const TOOL = [".mentat", "bin", "mentat_help.py"];
const MAX = 4000; // a Telegram 4096-os plafonja alatt; a sugo ennel joval rovidebb

// "/help", "/help@bot", "súgó"/"sugo", opcionalisan " status" vagy " todo"; egy elotte
// allo @botnev (mention-kapus csoport) lekerul. Minden mas null — a parameter fix lista,
// soha nem szabad szoveg, igy a python-hivas argumentuma sem lehet tetszoleges.
export function helpRequest(text, botUsername = "") {
  let t = String(text ?? "").trim();
  if (botUsername) t = t.replace(new RegExp(`^@${botUsername}\\s+`, "i"), "");
  const m = t.match(/^(?:\/help(?:@\w+)?|s[uú]g[oó])(?:\s+(status|todo))?$/i);
  return m ? { arg: (m[1] || "").toLowerCase() } : null;
}

// A kimenet, vagy null (nincs eszkoz, nem-nulla kilepes, idotullepes, ures kimenet).
export function runHelp({ repo, arg, python = "python3", timeoutMs = 5000 }) {
  if (!repo || !existsSync(join(repo, ...TOOL))) return null;
  try {
    const out = execFileSync(python, [join(repo, ...TOOL), ...(arg ? [arg] : [])],
      { cwd: repo, timeout: timeoutMs, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
    return out.trim() ? out.trim().slice(0, MAX) : null;
  } catch {
    return null;
  }
}

// Az agens repoja: BRIDGE_HELP_REPO, kulonben a tmux-session pane-jenek mappaja (a claude
// a repo gyokerebol indul). Nem talalhato -> null, es a sugo-ut nem el.
export function paneRepo(session, env = process.env) {
  if (env.BRIDGE_HELP_REPO) return env.BRIDGE_HELP_REPO;
  try {
    return execFileSync("tmux", ["display-message", "-p", "-t", session, "#{pane_current_path}"],
      { encoding: "utf8", timeout: 2000, stdio: ["ignore", "pipe", "ignore"] }).trim() || null;
  } catch {
    return null;
  }
}

// Telegramon a parancs neve /help: a sugo-kimenet /mentat parancsnevei cserelodnek (csak a
// szokozzel/sor elejen allo /mentat, igy utvonal es URL — ~/src/mentat, …/mentat/tree — marad).
export const forTelegram = (text) => String(text).replace(/(^|\s)\/mentat(?=\s|$)/gm, "$1/help");

// onHelp({text, chatId, messageId, fallback}) -> true, ha ez sugo-keres, a valasz elkeszult
// es a kuldes elindult; false, ha nem (a hivo ilyenkor sima kezbesitest csinal). Kuldesi
// hibanal a fallback() fut: a kerest akkor is megkapja az agens.
export function createHelp({ resolveRepo, tg, bot = () => ({}), log = () => {}, run = runHelp }) {
  return ({ text: asked, chatId, messageId, fallback }) => {
    const req = helpRequest(asked, bot().username);
    if (!req) return false;
    const out = run({ repo: resolveRepo(), arg: req.arg });
    if (!out) return false;
    const text = forTelegram(out);
    tg("sendMessage", { chat_id: chatId, text, reply_to_message_id: messageId })
      .then((r) => { if (r?.body && r.body.ok === false) throw new Error(r.body.description || "not ok"); })
      .catch((e) => { log(`help: a küldés nem sikerült (${e.message}); a kérés a pane-be megy`); fallback(); });
    return true;
  };
}
