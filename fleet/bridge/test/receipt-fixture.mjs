// Kozos tmp-kornyezet a nyugta-tesztekhez (nem teszt-fajl: a glob nem futtatja).
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tempDir } from "./tmp.mjs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createReceipts } from "../lib/receipt.mjs";

export const LINE = "[Telegram inbound | J id=1 | chat=-100 | msg=7]: x";
export const user = (text) => JSON.stringify({ type: "user", message: { role: "user", content: text } }) + "\n";

export function setup(sid = "s1") {
  const dir = tempDir("receipt-");
  const root = join(dir, "projects");
  mkdirSync(join(root, "-proj"), { recursive: true });
  const sessionIdFile = join(dir, "session.id");
  writeFileSync(sessionIdFile, `${sid}\n`);
  const tpath = (s) => join(root, "-proj", `${s}.jsonl`);
  writeFileSync(tpath(sid), JSON.stringify({ type: "summary" }) + "\n");
  const clock = { t: 1_000_000 };
  const reinjected = [], results = [];
  const mk = () => createReceipts({
    file: join(dir, "telegram-state", "receipts.json"), sessionIdFile, transcriptRoot: root,
    windowMs: 120_000, now: () => clock.t,
    reinject: (l) => reinjected.push(l), onResult: (r) => results.push(r),
  });
  return { dir, root, sessionIdFile, tpath, clock, reinjected, results, mk };
}

// Az agens dolgozik: a tmux-ba gepelt prompt `queued_command` csatolmanykent all.
export const queued = (prompt) => JSON.stringify({ type: "attachment",
  attachment: { type: "queued_command", prompt, commandMode: "prompt" } }) + "\n";
// Kitolto sorok (nem Telegram) — nagy transzkript szimulalasa.
export const filler = (bytes) => {
  const line = JSON.stringify({ type: "assistant", message: { content: "y".repeat(1000) } }) + "\n";
  return line.repeat(Math.ceil(bytes / line.length));
};
