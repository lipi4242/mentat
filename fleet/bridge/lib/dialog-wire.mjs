// lib/dialog-wire.mjs — engedelykero ablak: riasztas okkal, es a tulajdonos valasza Telegramrol.
//
//   watch.check()   a pending-retry ritmusaban: ha ugyanaz az ablak (ujjlenyomat) graceMs ota all,
//                   EGY riasztas (ok, kerdes, opciok, /igen /nem); reAlertMs utan meg egyszer, /nem
//                   javaslattal. Magatol a hid SOHA nem valaszol.
//   answer({...})   "/igen" | "/nem" [kod]: csak az answerIds kuldojetol, csak ha a pane-ben MOST
//                   allo ablak ujjlenyomata a riasztotte (vagy a megadott kod) — akkor az opcio
//                   SZAMA megy ki, `send-keys -l`, Enter NELKUL (az F-17 Enter-tilalma marad).
//                   Minden mas esetben semmi nem megy a pane-be, a kuldo valaszt kap. Naplozva.
import { spawnSync } from "node:child_process";
import { capturePane } from "./pane-guard.mjs";
import { readDialog } from "./pane-dialog.mjs";

export function dialogCommand(text) {
  const m = String(text ?? "").trim().match(/^\/(igen|nem)(?:@\w+)?(?:\s+([0-9a-f]{6,12}))?$/i);
  return m ? { answer: m[1].toLowerCase(), code: (m[2] || "").toLowerCase() } : null;
}

const opts = (d) => d.options.map((o) => `${o.key}. ${o.label}`).join(" · ");
const code = (d) => d.fingerprint.slice(0, 6);

export function formatAlert(d, label) {
  return [`engedélykérő ablak áll a pane-ben, ${label} nem dolgozik (ablak ${code(d)}).`,
    `Ok: ${d.source}${d.why ? ` — ${d.why}` : ""}`,
    `Kérdés: ${d.question}`, `Opciók: ${opts(d)}`,
    `Válasz: /igen vagy /nem — csak erre az ablakra; magamtól nem válaszolok.`].join("\n");
}

export function createDialogWatch({ session, spawn = spawnSync, alert, log = () => {}, label = session,
  now = Date.now, graceMs = 60_000, reAlertMs = 10 * 60_000 }) {
  let st = null; // {d, since, alertedAt, realerted, answered}
  function check() {
    const d = readDialog(capturePane(session, spawn));
    if (!d) {
      if (st) log(`engedélykérő ablak eltűnt (ablak ${code(st.d)})`);
      st = null;
      return;
    }
    if (!st || st.d.fingerprint !== d.fingerprint) st = { d, since: now(), alertedAt: 0, realerted: false };
    if (st.answered) return;
    if (!st.alertedAt && now() - st.since >= graceMs) {
      st.alertedAt = now();
      log(`engedélykérő ablak riasztás: ablak ${code(d)} ok=${d.source}`);
      alert(formatAlert(d, label)).catch(() => {});
    } else if (st.alertedAt && !st.realerted && now() - st.alertedAt >= reAlertMs) {
      st.realerted = true;
      alert(`még mindig áll az engedélykérő ablak (ablak ${code(d)}, ${d.source}). ` +
        `Ha senki nem kérte, válaszolj: /nem`).catch(() => {});
    }
  }
  const alerted = () => (st && st.alertedAt ? st.d.fingerprint : null);
  const answered = (fp) => { if (st && st.d.fingerprint === fp) st.answered = true; };
  return { check, alerted, answered };
}

const pick = (d, answer) => d.options.find((o) => (answer === "igen" ? /^Yes\b/ : /^No\b/).test(o.label));

export function createDialogAnswer({ session, spawn = spawnSync, watch, tg, log = () => {}, answerIds = [] }) {
  const owners = new Set(answerIds.map(String));
  return ({ text, chatId, messageId, fromId }) => {
    const cmd = dialogCommand(text);
    if (!cmd) return false;
    const reply = (t) => tg("sendMessage", { chat_id: chatId, text: t, reply_to_message_id: messageId })
      .catch((e) => log(`dialog-válasz: a küldés nem sikerült (${e.message})`));
    const refuse = (why) => {
      log(`dialog-válasz elutasítva: from=${fromId} ${cmd.answer} — ${why}`);
      reply(`${why} — nem küldtem semmit.`);
      return "dialog";
    };
    if (!owners.has(String(fromId))) return refuse("az ablakra csak a tulajdonos válaszolhat");
    const d = readDialog(capturePane(session, spawn));
    if (!d) return refuse("nincs engedélykérő ablak a pane-ben");
    const want = cmd.code || watch.alerted();
    if (!want) return refuse("erről az ablakról még nem ment riasztás");
    if (!d.fingerprint.startsWith(want)) return refuse(`a pane-ben már másik ablak áll (ablak ${code(d)})`);
    const o = pick(d, cmd.answer);
    if (!o) return refuse(`az ablaknak nincs „${cmd.answer}” opciója (${opts(d)})`);
    const r = spawn("tmux", ["send-keys", "-t", session, "-l", "--", o.key], { encoding: "utf8" });
    if (!r || r.status !== 0) return refuse("a billentyű nem ment ki (tmux hiba)");
    watch.answered(d.fingerprint);
    log(`dialog-válasz: from=${fromId} ablak=${code(d)} billentyű=${o.key} (${o.label}) ok=${d.source}`);
    reply(`elküldtem: ${o.key}. ${o.label} (ablak ${code(d)}).`);
    return "dialog";
  };
}

// A hid osszedrotozasa (bridge.mjs): egy watch es a hozza kotott valaszolo a CFG-bol.
export function createDialogs(CFG, { spawn, alert, log, tg }) {
  const watch = createDialogWatch({ session: CFG.session, spawn, alert, log, label: CFG.agentLabel,
    reAlertMs: CFG.dialogReAlertMs });
  return { watch, answer: createDialogAnswer({ session: CFG.session, spawn, watch, tg, log, answerIds: CFG.dialogAnswerIds }) };
}
