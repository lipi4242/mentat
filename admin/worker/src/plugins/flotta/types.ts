// A flotta-egészség plugin közös típusai és apró segédei.
export type Fleet = {
  id: string; name: string; owner_email: string | null; deadman_min: number; escalate_min: number; debounce_reports: number;
  repeat_min: number; max_open_incidents: number; max_open_per_box: number; max_tasks_per_hour: number; max_mails_per_hour: number; updated_at: string;
  managers_version: number; managers_digest: string | null;
};
export type Manager = { id: string; fleet_id: string; principal_id: string; agent: string; scope: string; rank: number; created_at: string };
export type Box = {
  id: string; fleet_id: string; name: string; token_id: string | null; created_at: string;
  disabled_at: string | null; last_report_at: string | null; last_attempt_at: string | null; rejected_count: number; last_reject: string | null; fleet_version: string | null; release_json: string | null;
  repair_ok: number | null; repair_detail: string | null; kind: 'box' | 'desktop';
};
export type Incident = {
  id: string; fleet_id: string; box_id: string; subject: string; agent: string | null; check_key: string;
  status: 'open' | 'resolved'; detail: string | null; opened_at: string; last_red_at: string; red_count: number;
  resolved_at: string | null; resolve_note: string | null; todo_task_id: string | null;
  assigned_principal_id: string | null; claimed_by: string | null; claimed_at: string | null; attempts: number;
  first_mail_at: string | null; last_mail_at: string | null; mail_count: number; resolved_mail_at: string | null;
  // flotta-menedzser: állapotgép, fencing, ellenőrzés (0501)
  state: string; version: number; move_id: string | null; state_at: string | null; fence: number; claim_hash: string | null;
  assigned_at: string | null; attempt_until: string | null; handovers: number; tried_json: string; drain: string | null;
  nonce_hash: string | null; nonce_fence: number | null; verified_boot_id: string | null; human_reason: string | null; human_by: string | null;
};
export type Row = Incident & { box_name: string };

/** A box tokenjének egyetlen jogköre. Más scope mellette: a kötés elutasítja. */
export const REPORT_SCOPE = 'flotta:report';
export const READ_SCOPE = 'flotta:read';
/** A menedzser-lista kiadójának egyetlen jogköre (`fleet managers publish`); a box-token nem írhat konfigot. */
export const CONFIG_SCOPE = 'flotta:config';
/** A dead-man incidens ellenőrzés-kulcsa. */
export const DEADMAN = 'deadman';
/** Az összegző (túlterhelés) incidens kulcsa; alanya `fleet:<id>`. */
export const OVERLOAD = 'tulterheles';
/** A box egymás után többször elutasított jelentése (alanya `box:<név>`). */
export const REJECTED = 'elutasitott-jelentes';

/** Az ellenőrzés-kulcsok zárt listája, magyar címkével. A box kulcsa ennek egyike lesz:
 *  `kapu-…` → `kapu`, minden más ismeretlen → `egyeb`. A feladat szövege csak ezekből épül. */
export const CHECKS: Record<string, string> = {
  kuldes: 'a Telegram-küldés', todo: 'a todo-elérés (mentat-todo)', allapot: 'a saját állapotfájlok olvasása',
  git: 'a git a saját repóban', repo: 'az ágens repója', token: 'a híd tokenje a unit env-jében',
  'nema-kuldes': 'token nélküli küldés a naplóban',
  'todo-ebresztes': 'a todo-ébresztés (a híd todo-pollja vagy egy feldolgozatlan ébresztés)', kapu: 'a titok-kapu tilt egy alapfunkciót',
  egyeb: 'egyéb alapfunkció', [DEADMAN]: 'a box nem jelent', [OVERLOAD]: 'túl sok hiba egyszerre — összevonva',
  [REJECTED]: 'a box jelentéseit a központ elutasítja',
  // flotta-menedzser: a lefutott tick nyoma régi; a box javító-próbája (a végrehajtó önellenőrzése)
  tick: 'az ütemezett tick nem futott le', javito: 'a javító végrehajtó (repair-exec) a boxon',
};

export function normalizeCheck(raw: string): string {
  if (raw === DEADMAN || raw === OVERLOAD || raw === REJECTED) return 'egyeb';   // ezeket csak a szerver nyitja
  if (raw in CHECKS) return raw;
  return raw.startsWith('kapu-') ? 'kapu' : 'egyeb';
}

export type RejectCode = 'invalid' | 'box-mismatch' | 'cross-box' | 'too-large';
const REJECT_CODES: readonly string[] = ['invalid', 'box-mismatch', 'cross-box', 'too-large'];
export const isRejectCode = (c: string | undefined): c is RejectCode => c !== undefined && REJECT_CODES.includes(c);

export class Problem extends Error {
  /** `code`: a box-jelentés elutasításának zárt oka (RejectCode, rejection.ts), vagy a menedzser-végpontok
   *  409-es kódja (stale, claim, budget…). Elutasításként csak a RejectCode számít (isRejectCode). */
  constructor(message: string, public status: 400 | 401 | 403 | 404 | 409 | 422 | 429 = 422, public code?: string) { super(message); }
}

export const iso = (d: Date) => d.toISOString();
export const minutesBetween = (from: string, to: Date) => (to.getTime() - Date.parse(from)) / 60000;

export async function event(db: D1Database, incident: string, at: Date, kind: string, body: unknown = null) {
  await db.prepare('INSERT INTO flotta_incident_event (incident_id, at, kind, body) VALUES (?1, ?2, ?3, ?4)')
    .bind(incident, iso(at), kind, body === null ? null : JSON.stringify(body)).run();
}

export const DEFAULT_FLEET = 'default';

/** A flotta sora; az alapflotta ('default') az első kérdezéskor jön létre. */
export async function getFleet(db: D1Database, id: string) {
  if (id === DEFAULT_FLEET) {
    await db.prepare(`INSERT OR IGNORE INTO flotta_fleet (id, name, updated_at) VALUES (?1, 'Flotta', ?2)`).bind(id, iso(new Date())).run();
  }
  return db.prepare('SELECT * FROM flotta_fleet WHERE id = ?1').bind(id).first<Fleet>();
}
