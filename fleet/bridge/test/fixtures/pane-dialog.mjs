// Kozos hamis pane-ek es tmux/Telegram a pane-dialog tesztekhez.
import { createDialogWatch, createDialogAnswer } from "../../lib/dialog-wire.mjs";

export const PRIVACY = [
  "⏺ Bash(python3 scripts/draft.py)",
  " Hook tool.check requires confirmation for this command:",
  " This call's input holds your account email address, which may leave this",
  " machine. If nobody asked to send it, go on without it.",
  " [plugin:cc-plugin-privacy]",
  " Do you want to proceed?",
  " ❯ 1. Yes",
  "   2. No",
  " Esc to cancel · Tab to amend",
].join("\n");
export const BOXED = [
  "╭──────────────────────────────────────────────╮",
  "│ Bash command                                 │",
  "│   rm -rf $D/$n                               │",
  "│ Do you want to proceed?                      │",
  "│ ❯ 1. Yes                                     │",
  "│   2. Yes, and don't ask again                │",
  "│   3. No, and tell Claude what to do (esc)    │",
  "╰──────────────────────────────────────────────╯",
].join("\n");

export function fakeTmux(pane) {
  const keys = [];
  const state = { pane };
  const spawn = (cmd, args) => {
    if (args[0] === "capture-pane") return { status: 0, stdout: state.pane };
    keys.push(args);
    return { status: 0 };
  };
  return { spawn, keys, state };
}
export function fakeTg() {
  const sent = [];
  return { sent, tg: async (method, body) => { sent.push({ method, ...body }); return { body: { ok: true } }; } };
}

export function setup(pane, opts = {}) {
  const tmux = fakeTmux(pane);
  const t = fakeTg();
  const alerts = [];
  const logs = [];
  let now = 0;
  const watch = createDialogWatch({ session: "s", spawn: tmux.spawn, label: "agens",
    alert: async (x) => alerts.push(x), log: (x) => logs.push(x), now: () => now,
    graceMs: 60_000, reAlertMs: 10 * 60_000 });
  const answer = createDialogAnswer({ session: "s", spawn: tmux.spawn, watch, tg: t.tg,
    log: (x) => logs.push(x), answerIds: opts.answerIds ?? ["42"] });
  return { tmux, t, alerts, logs, watch, answer, tick: (ms) => { now += ms; watch.check(); } };
}

