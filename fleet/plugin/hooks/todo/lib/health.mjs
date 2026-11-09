// lib/health.mjs — a hid eletjele a flotta-audit fele. Best-effort: sosem dob;
// egy health-iras hibaja nem dontheti meg a hidat, aminek a leteet jelzi.
import { loadJson, saveJson } from "./jsonfile.mjs";

// stamp:false — a `written_at` marad: a flotta csatorna-jele (signals.py) ebbol meri, el-e a
// Telegram-poller; a todo-ebresztes 20 s-os irasai ezt nem fedhetik el.
export function writeHealth(path, fields, { stamp = true } = {}) {
  try {
    const old = loadJson(path, {});
    saveJson(path, { ...old, ...fields, ...(stamp || !old.written_at ? { written_at: Date.now() } : {}) }, () => {});
  } catch {
    /* szandekosan nema */
  }
}
