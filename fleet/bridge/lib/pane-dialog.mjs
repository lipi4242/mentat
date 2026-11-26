// lib/pane-dialog.mjs — MI az engedelykero ablak a pane-ben (a pane-guard.mjs csak azt mondja meg, HOGY all-e).
//
// Miert: egy Claude Code-hook (pl. a beepitett adatvedelmi ellenorzes, "[plugin:…]") a
// --dangerously-skip-permissions mellett is jovahagyast kerhet, es a headless agens addig all.
// A tulajdonos riasztasaba az ablak OKA kerul (a hook/plugin neve es elso magyarazo mondata),
// a kerdes es a szamozott opciok — a valaszt pedig az ujjlenyomat koti ugyanahhoz az ablakhoz.
//
// Az ok csak a Claude Code SAJAT szovege (hook-sor, plugin-jelolo, magyarazat). Sima
// engedelykero ablaknal (Bash command …) csak a cim megy ki, a parancs torzse nem: abban
// titok is allhat.
import { createHash } from "node:crypto";
import { TAIL_LINES, permissionDialog } from "./pane-guard.mjs";

const QUESTION = /Do you want to [^\n]{0,200}\?/;
const OPTION = /^(?:❯\s*)?(\d)\.\s+(.+)$/;
const HOOK = /^Hook\b.*\brequires confirmation\b/;
const PLUGIN = /\[plugin:[^\]\s]{1,80}\]/;
const HEAD_MAX = 12; // ennyi sor a kerdes folott tartozhat az ablakhoz
const clip = (s, n = 200) => (s.length > n ? s.slice(0, n - 1) + "…" : s);
// Keret (│ ╭ ╰ ─) es szel-szokoz le: a keretes es a keret nelkuli ablak ugyanugy olvasodik.
const strip = (l) => l.replace(/^[\s│|╭╰─]+/, "").replace(/[\s│|╮╯─]+$/, "");

function firstSentence(lines) {
  const t = lines.join(" ").replace(/\s+/g, " ").trim();
  const m = t.match(/^.*?[.!?](?=\s|$)/);
  return clip(m ? m[0] : t);
}

// {fingerprint, source, hook, why, question, options:[{key,label}]} vagy null. Sosem dob.
export function readDialog(text) {
  if (!permissionDialog(text)) return null;
  const lines = text.replace(/\s+$/, "").split("\n").slice(-TAIL_LINES).map(strip);
  let q = lines.length - 1;
  while (q >= 0 && !QUESTION.test(lines[q])) q--;
  if (q < 0) return null;
  const options = [];
  for (const l of lines.slice(q + 1)) {
    const m = l.match(OPTION);
    if (m) options.push({ key: m[1], label: clip(m[2].trim(), 80) });
    else if (options.length) break;
  }
  let s = q;
  while (s > 0 && lines[s - 1] !== "" && q - s < HEAD_MAX) s--;
  const head = lines.slice(s, q);
  const hi = head.findIndex((l) => HOOK.test(l));
  const hook = hi >= 0 ? clip(head[hi]) : "";
  const plugin = head.join(" ").match(PLUGIN)?.[0] || "";
  const why = hi >= 0 ? firstSentence(head.slice(hi + 1).filter((l) => !PLUGIN.test(l))) : "";
  const source = plugin || hook || clip(head.find(Boolean) || "", 120); // keretes ablaknal a cim
  const block = lines.slice(s, q + 1 + options.length).join("\n");
  const fingerprint = createHash("sha256").update(block).digest("hex").slice(0, 12);
  return { fingerprint, source, hook, why, question: clip(lines[q]), options };
}
