// Az incidens állapotgépe (flotta-menedzser). Minden átmenet EGY tranzakció (D1 batch) verzió-CAS-sal:
// az UPDATE csak a látott verzióra hat, és az eseménysor csak akkor íródik, ha az UPDATE hatott
// (a sor az átmenet egyedi `move_id`-jére feltételes — a verzió-szám ehhez nem elég: a vesztes
// batch-e a nyertes által már elért verziót látná).
// Két egyidejű átmenetből (cron + végrehajtó, két cron-kör) így pontosan egy nyer.
//   nyitott → kiosztva → átvéve → javít → ellenőrzés → megoldva
//   mellékágak: átadva (a lánc következőjének), ember-kell (lánc/keret elfogyott, fedetlen, biztonsági ok)
import { iso, type Incident } from './types';

export const STATES = ['nyitott', 'kiosztva', 'atveve', 'javit', 'ellenorzes', 'megoldva', 'atadva', 'ember-kell'] as const;
export type State = typeof STATES[number];

/** Engedett átmenetek. A megoldás csak ellenőrzésből (nonce) vagy fence nélküli állapotból jöhet. */
const NEXT: Record<State, readonly State[]> = {
  nyitott: ['kiosztva', 'ember-kell', 'megoldva'],
  kiosztva: ['atveve', 'atadva', 'nyitott', 'ember-kell', 'megoldva'],
  atadva: ['atveve', 'atadva', 'nyitott', 'ember-kell', 'megoldva'],
  atveve: ['atveve', 'javit', 'ellenorzes', 'atadva', 'ember-kell'],
  javit: ['javit', 'ellenorzes', 'atadva', 'ember-kell'],
  ellenorzes: ['ellenorzes', 'megoldva', 'javit', 'atadva', 'ember-kell'],
  'ember-kell': ['ember-kell', 'megoldva'],
  megoldva: [],
};

/** Állapotok, amelyekben egy menedzser fence-t tart (átvette); ezekből zöld jelentés NEM zár. */
export const CLAIMED: readonly State[] = ['atveve', 'javit', 'ellenorzes'];
/** Kiosztva, de még nem vette át senki: ebben fut a 10 perces claim-időzítő. */
export const OFFERED: readonly State[] = ['kiosztva', 'atadva'];

export const CLAIM_WAIT_MIN = 10;     // ennyi idő a claimre, utána átadás
export const ATTEMPT_MIN = 30;        // fix kísérleti keret, meghosszabbítás nincs
export const RESTART_BUDGET = 3;      // ágensenként óránként
export const STEPS = ['doctor', 'doctor-fix', 'bridge-install', 'unquarantine', 'postcheck'] as const;
export type Step = typeof STEPS[number];
export const RESTART_STEPS: readonly Step[] = ['doctor-fix', 'bridge-install', 'unquarantine'];
export const STEP_TIMEOUT_MIN: Record<Step, number> = { doctor: 5, 'doctor-fix': 15, 'bridge-install': 10, unquarantine: 2, postcheck: 10 };
/** A csak-olvasó javító-próba ellenőrzés-kulcsai: ha a menedzser ágensén ezek pirosak, alkalmatlan. */
export const REPAIR_CHECKS = ['todo', 'javito'];

export class Conflict extends Error {
  constructor(public code: string, message = code) { super(message); }
}

type Set_ = Record<string, string | number | null>;

/**
 * CAS-átmenet. `false`: valaki közben léptette (a hívó újraolvas vagy feladja).
 * A `set` csak belső, rögzített oszlopneveket kaphat (nem felhasználói kulcsokat).
 */
export async function move(db: D1Database, inc: Incident, to: State, at: Date, set: Set_ = {}, ev?: { kind: string; body?: unknown }): Promise<boolean> {
  const from = inc.state as State;
  if (!NEXT[from]?.includes(to)) throw new Conflict('state', `illegal transition ${from} → ${to}`);
  const cols: Set_ = { ...set, state: to, state_at: iso(at), status: to === 'megoldva' ? 'resolved' : 'open' };
  if (to === 'megoldva') {
    // lezáráskor minden token érvénytelen: új fence, nincs claim és nonce
    Object.assign(cols, { resolved_at: cols.resolved_at ?? iso(at), claim_hash: null, nonce_hash: null, nonce_fence: null, drain: null });
    cols.fence = inc.fence + 1;
  }
  const mark = secret();   // a nyertes átmenet jele: az eseménysor csak erre íródik (a vesztes batch-é nem)
  cols.move_id = mark;
  const keys = Object.keys(cols);
  const upd = db.prepare(`UPDATE flotta_incident SET ${keys.map((k, i) => `${k} = ?${i + 1}`).join(', ')}, version = version + 1
      WHERE id = ?${keys.length + 1} AND version = ?${keys.length + 2}`).bind(...Object.values(cols), inc.id, inc.version);
  const evt = db.prepare(`INSERT INTO flotta_incident_event (incident_id, at, kind, body)
      SELECT ?1, ?2, ?3, ?4 WHERE EXISTS (SELECT 1 FROM flotta_incident WHERE id = ?1 AND move_id = ?5)`)
    .bind(inc.id, iso(at), ev?.kind ?? `state:${to}`, JSON.stringify({ from, to, ...(ev?.body as object ?? {}) }), mark);
  const [r] = await db.batch([upd, evt]);
  return r.meta.changes === 1;
}

export async function load(db: D1Database, id: string) {
  return db.prepare('SELECT * FROM flotta_incident WHERE id = ?1').bind(id).first<Incident>();
}

export const tried = (inc: Incident): string[] => { try { return JSON.parse(inc.tried_json) as string[]; } catch { return []; } };
/** Véletlen titok (claim, nonce): a nyílt érték csak a válaszban, a DB-ben a hash. */
export function secret(): string {
  const b = crypto.getRandomValues(new Uint8Array(24));
  return btoa(String.fromCharCode(...b)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export const plusMin = (at: Date, m: number) => iso(new Date(at.getTime() + m * 60000));

/** Emberhez: minden automatikus token érvénytelen (új fence, nincs claim/nonce). */
export const toHuman = (db: D1Database, inc: Incident, at: Date, reason: string, kind = 'human_needed') =>
  move(db, inc, 'ember-kell', at, { fence: inc.fence + 1, claim_hash: null, nonce_hash: null, nonce_fence: null, drain: null,
    claimed_by: null, attempt_until: null, human_reason: reason.slice(0, 500) }, { kind, body: { reason } });
