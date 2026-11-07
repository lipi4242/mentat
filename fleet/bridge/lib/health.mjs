// lib/health.mjs — a hid eletjele a flotta-audit fele. Best-effort: sosem dob;
// egy health-iras hibaja nem dontheti meg a hidat, aminek a leteet jelzi.
import { loadJson, saveJson } from "./jsonfile.mjs";

export function writeHealth(path, fields) {
  try {
    saveJson(path, { ...loadJson(path, {}), ...fields, written_at: Date.now() }, () => {});
  } catch {
    /* szandekosan nema */
  }
}
