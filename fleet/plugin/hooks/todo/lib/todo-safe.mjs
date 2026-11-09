// lib/todo-safe.mjs — a todo-ebresztes sorának mezoi ADATKENT (CISO-lelet: a sor agensek kozti
// utasitas-csatorna lenne). A sorba csak szerver-oldali, szerkezeti mezo kerul, mind zart alakra
// szukitve: kulcs (PREFIX-N) vagy task-id, ige (zart lista), handle ([a-z0-9_]), es a cim — az egyetlen
// szabad szoveg — tisztitva es ~80 karakterre vagva, «» koze zarva. Komment-torzs SOHA nem kerul a
// sorba: a tartalmat az agens maga olvassa el a CLI-vel (mentat-todo item|task).
import { stripInvisible } from "./sanitize.mjs";

export const VERBS = new Set(["kiadta", "visszaadta", "visszadobta", "folytatásra visszaadta", "elfogadásra küldte",
  "megemlített", "kommentelt"]);
export const TITLE_MAX = 80;

// A lathatatlan/kontroll-szures a hid kozos szurojebol jon (lib/sanitize.mjs stripInvisible:
// NFKC, Cc/Zl/Zp -> szokoz; Cf/Co/Cs/Default_Ignorable, tag- es variacio-valaszto sav ki). Itt csak a
// keret: a «»|[] kiesik a cimbol, egy sor, TITLE_MAX kodpontra vagva.
export function safeTitle(s, max = TITLE_MAX) {
  const t = stripInvisible(String(s ?? "")).replace(/[«»|\[\]]/g, " ").replace(/\s+/g, " ").trim();
  const chars = [...t]; // kodpontonkent: surrogate-par nem torik ketté
  return chars.length > max ? `${chars.slice(0, max - 1).join("")}…` : t;
}

export const safeId = (s) => (/^[A-Za-z0-9_-]{1,40}$/.test(String(s ?? "")) ? String(s) : "?");
export const safeHandle = (s) => (/^[a-z0-9_]{1,64}$/.test(String(s ?? "")) ? String(s) : "?");
export const safeVerb = (v) => String(v ?? "").split(", ").filter((x) => VERBS.has(x)).join(", ") || "esemény";
export const safeBy = (v) => String(v ?? "").split(", ").map(safeHandle).join(", ");
export function safeRef(ref) {
  const r = String(ref ?? "");
  if (/^[A-Z][A-Z0-9]{0,7}-\d{1,9}$/.test(r)) return r;
  return r.startsWith("task:") ? `task:${safeId(r.slice(5))}` : "task:?";
}
