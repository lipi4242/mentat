// lib/jsonfile.mjs — a bridge.mjs loadJson/saveJson kiemelése, saveJson atomikussá téve
// (tmp fájlba írás + renameSync, hogy egy félbeszakadt írás ne hagyjon csonka JSON-t).
import {
  readFileSync,
  writeFileSync,
  existsSync,
  mkdirSync,
  renameSync,
  unlinkSync,
} from "node:fs";
import { dirname } from "node:path";

function defaultLog(...a) {
  console.log(new Date().toISOString(), "[bridge]", ...a);
}

export function loadJson(path, fallback, onError = defaultLog) {
  try {
    if (existsSync(path)) return JSON.parse(readFileSync(path, "utf8"));
  } catch (e) {
    onError(`read error ${path}:`, e.message);
  }
  return fallback;
}

// A NEM kritikus írók (health, offset-mentés, retention) használják: egy
// elhasalt írás naplózódik, de nem dönti meg a hidat.
export function saveJson(path, obj, onError = defaultLog) {
  try {
    saveJsonStrict(path, obj);
  } catch (e) {
    onError(e.message);
  }
}

// A TARTÓSSÁG-KRITIKUS írók (média-sor enqueue, pending, album-puffer) ezt
// használják: ha az egyetlen tartós másolat nem íródott ki, azt nem szabad
// sikernek hazudni — dobunk, és a hívó (poll-ciklus) nem lépteti az offsetet.
export function saveJsonStrict(path, obj) {
  const tmp = `${path}.${process.pid}.${Date.now()}.tmp`;
  try {
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(tmp, JSON.stringify(obj) + "\n");
    renameSync(tmp, path);
  } catch (e) {
    try {
      unlinkSync(tmp);
    } catch {
      /* tmp file may not exist yet */
    }
    throw new Error(`write error ${path}: ${e.message}`);
  }
}

// Sérült állapotfájl: a loadJson csendes fallbackja után a következő mentés
// FELÜLÍRNÁ az egyetlen visszanyerési forrást. Ezért a sérült fájlt előbb
// karanténba tesszük (`<path>.corrupt-<epoch>`), és az onCorrupt hívással
// HANGOSSÁ tesszük — az events-*.jsonl napló marad a visszajátszás forrása.
// Hiányzó fájl = normális első indulás: néma fallback.
export function loadJsonQuarantine(path, fallback, onCorrupt = () => {}) {
  if (!existsSync(path)) return fallback;
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    const quarantined = `${path}.corrupt-${Date.now()}`;
    try {
      renameSync(path, quarantined);
    } catch {
      /* best-effort: ha a rename se megy, a riasztás akkor is menjen ki */
    }
    try {
      onCorrupt(quarantined);
    } catch {
      /* a riasztás hibája sose vigye el a betöltést */
    }
    return fallback;
  }
}
