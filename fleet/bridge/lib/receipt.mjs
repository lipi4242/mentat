// lib/receipt.mjs — erkezes-nyugta (3.2): a beinjektalt sor megjelent-e a transzkriptben.
//
// Miert: a `tmux send-keys` sikere nem bizonyitja, hogy az agens megkapta a
// sort (tomorites, felugro dialogus, foglalt prompt nyelheti el). Ha a sor
// `windowMs` alatt nem jelenik meg user-bejegyzeskent, EGYSZER ujrainjektalunk;
// ha utana sem, `unconfirmed` — a hivo riaszt. Az offset az injektalas ELOTT
// rogzul (measure), hogy a gyorsan beirt sor se csusszon a meres moge; a
// kesve megerkezo ELSO injektalas is nyugta (a mar atnezett bajtokon tul).
import { saveJson, loadJsonQuarantine } from "./jsonfile.mjs";
import { readSessionId, findTranscript, sizeOf, identOf, headerRe, HEADER_HEAD, TODO_HEAD, scanUserEntries, tailOffset } from "./transcript.mjs";

const DONE_MAX = 500;

// A fejlec ugyanazzal a horgonyzott, lusta mintaval, mint a transzkript-illesztes
// (transcript.mjs) — a reakcio-sorban nincs msg=, az kimarad.
// Szandekos: a szerkesztett uzenet sora ugyanazt a chat/msg fejlecet viseli,
// tehat ugyanaz a kulcs — fuggo vagy lezart kulcsra nem indul uj ciklus (dedup).
// A todo-ebresztes sora chat=todo, msg=<wake-seq> kulccsal kap nyugtat.
const keyOf = (line) => {
  const m = String(line).match(new RegExp(String.raw`${HEADER_HEAD}(-?\d+) \| msg=(\d+)(?=[ |\]])`));
  if (m) return { chat_id: m[1], msg_id: m[2], key: `${m[1]}:${m[2]}` };
  const t = String(line).match(new RegExp(String.raw`${TODO_HEAD}(\d+)\]: `));
  return t ? { chat_id: "todo", msg_id: t[1], key: `todo:${t[1]}` } : null;
};
const keyOfItem = (it) => `${it.chat_id}:${it.msg_id}`;

export function createReceipts({
  file, sessionIdFile, transcriptRoot, windowMs = 120_000, reinject = () => {},
  onResult = () => {}, onCheckEnd = () => {}, now = Date.now, log = () => {}, onCorrupt = () => {},
}) {
  const loaded = loadJsonQuarantine(file, {}, onCorrupt);
  // Regi alak (puszta tomb) is betoltheto.
  let items = Array.isArray(loaded) ? loaded : Array.isArray(loaded?.items) ? loaded.items : [];
  // Lezart kulcsok (korlatos): a pending-bol kesve kezbesitett ujrainjektalas ne inditson uj ciklust.
  let done = Array.isArray(loaded?.done) ? loaded.done.slice(-DONE_MAX) : [];
  let measured = null; // egyetlen hely: a sikertelen inject merese a kovetkezovel felulirodik
  const save = () => saveJson(file, { items, done }, log);

  const snapshot = () => {
    const sid = readSessionId(sessionIdFile);
    const path = findTranscript(transcriptRoot, sid);
    return { sid, path, offset: path ? sizeOf(path) : 0, ident: path ? identOf(path) : null };
  };

  // beforeInject: a transzkript hossza az injektalas ELOTT (csak memoriaban).
  function measure(line) {
    measured = keyOf(line) ? { line, ...snapshot() } : null;
  }

  // onInjected: a sikeres injektalas utan tartossa tesszuk.
  function record(line) {
    const k = keyOf(line);
    if (!k) return;
    const m = measured && measured.line === line ? measured : { line, ...snapshot() };
    measured = null;
    if (done.includes(k.key) || items.some((it) => keyOfItem(it) === k.key)) return;
    items.push({ chat_id: k.chat_id, msg_id: k.msg_id, line, sid: m.sid, path: m.path, offset: m.offset,
      paths: m.path ? [{ path: m.path, offset: m.offset, ident: m.ident }] : [], deadline: now() + windowMs, attempt: 0 });
    save();
  }

  const finish = (it, status, detail) => {
    done.push(keyOfItem(it));
    if (done.length > DONE_MAX) done = done.slice(-DONE_MAX);
    try {
      const r = onResult({ status, chat_id: it.chat_id, msg_id: it.msg_id, line: it.line,
        ...(detail ? { detail } : {}) });
      r?.catch?.((e) => log("receipt onResult hiba:", e.message));
    } catch (e) { log("receipt onResult hiba:", e.message); }
  };

  // Utvonalankent EGY olvasas, a legkisebb fuggo offsettol.
  function scanAll() {
    const from = new Map();
    for (const it of items) for (const p of it.paths) {
      const id = identOf(p.path);
      if (p.ident === undefined) p.ident = id; // regi rekord: az elso latott azonossag
      // csere (akar nagyobb is) / csonkitas: a vege elotti TAIL-tol, nem 0-tol (OOM)
      if (id !== p.ident) { p.ident = id; p.offset = tailOffset(p.path); }
      if (sizeOf(p.path) < p.offset) p.offset = tailOffset(p.path);
      if (!from.has(p.path) || p.offset < from.get(p.path)) from.set(p.path, p.offset);
    }
    const scans = new Map();
    for (const [path, off] of from) scans.set(path, scanUserEntries(path, off));
    return scans;
  }

  function check() {
    if (!items.length) return;
    const cur = readSessionId(sessionIdFile);
    const curPath = findTranscript(transcriptRoot, cur);
    for (const it of items) {
      if (!Array.isArray(it.paths)) it.paths = it.path ? [{ path: it.path, offset: it.offset || 0 }] : [];
      // Session-valtas (vagy kesobb megjelent transzkript): az uj a vege elotti
      // TAIL-tol (kicsinel az elejetol); a regi marad.
      if (cur) it.sid = cur;
      if (curPath && !it.paths.some((p) => p.path === curPath))
        it.paths.push({ path: curPath, offset: tailOffset(curPath), ident: identOf(curPath) });
    }
    const scans = scanAll();
    const keep = [];
    const reinjects = [];
    for (const it of items) {
      const re = headerRe(it.chat_id, it.msg_id);
      const hit = it.paths.some((p) => scans.get(p.path).entries.some((e) => e.pos >= p.offset && re.test(e.text)));
      if (hit) { finish(it, "confirmed"); continue; }
      for (const p of it.paths) p.offset = Math.max(p.offset, scans.get(p.path).end); // atnezve
      const t = now();
      if (t < it.deadline) { keep.push(it); continue; }
      if (!it.paths.length) { finish(it, "unconfirmed", "no transcript"); continue; }
      // Rég lejart (pl. a hid sokaig allt): az ujrainjektalas mar nem segit, csak zavar.
      if (t - it.deadline > 2 * windowMs) { finish(it, "unconfirmed", "stale"); continue; }
      if (it.attempt === 0) {
        it.attempt = 1;
        it.deadline = t + windowMs;
        keep.push(it);
        reinjects.push(it.line);
        continue;
      }
      finish(it, "unconfirmed");
    }
    items = keep;
    save(); // ELOBB tartos (attempt=1), csak utana az ujrainjektalas
    for (const l of reinjects) {
      try { reinject(l); } catch (e) { log("receipt ujrainjektalas hiba:", e.message); }
    }
    try { onCheckEnd(); } catch (e) { log("receipt onCheckEnd hiba:", e.message); }
  }

  return { measure, record, check, depth: () => items.length };
}
