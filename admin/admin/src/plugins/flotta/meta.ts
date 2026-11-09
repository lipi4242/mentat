// A flotta-ellenőrzés képernyőjének API-útja és típusai (worker: worker/src/plugins/flotta/).
export const API = '/api/flotta/v1';
export type Manager = { id: string; principal_id: string; agent: string; scope: string; rank: number; handle: string | null; disabled_at: string | null };
export type Coverage = { uncovered: Array<{ target: string; why: string }>; unfit: Array<{ agent: string; why: string }>;
  human_needed: Array<{ incident: string; target: string }>; handovers: Array<{ incident: string; handovers: number }> };
export type Fleet = { id: string; name: string; managers: Manager[]; coverage?: Coverage; managers_version?: number;
  effective_owner_email: string | null; deadman_min: number; escalate_min: number; debounce_reports: number; repeat_min: number };
export type Box = { id: string; name: string; fleet_id: string; last_report_at: string | null; age_min: number | null; stale: boolean;
  fleet_version: string | null; disabled_at: string | null; rejected_count?: number; last_reject?: string | null; release: { here: string | null; latest: string | null; lag: string | null } | null };
export type Agent = { id: string; name: string; box_name: string; last_seen_at: string; measured_at: string | null;
  result: { red: Array<{ check: string; detail: string }>; unknown: string[]; ok: string[] } };
export type Incident = { id: string; subject: string; agent: string | null; check_key: string; status: 'open' | 'resolved';
  detail: string | null; box_name: string; opened_at: string; resolved_at: string | null; resolve_note: string | null;
  red_count: number; mail_count: number; todo_task_id: string | null;
  state?: string; handovers?: number; human_reason?: string | null };
export type IncidentEvent = { id: number; at: string; kind: string; body: string | null };
export type Status = { fleets: Fleet[]; boxes: Box[]; agents: Agent[]; incidents: Incident[]; now: string };

export const EVENT_LABEL: Record<string, string> = {
  opened: 'megnyílt', resolved: 'megoldódott', task: 'feladat a felelős ágensnek', task_closed: 'feladat lezárva',
  assigned: 'kiosztva', claimed: 'átvéve', handover: 'átadva', uncovered: 'fedetlen — emberhez', draining: 'átadás a futó lépés után',
  released: 'a menedzser feladta', op_intent: 'javító lépés indul', op_result: 'javító lépés eredménye', op_busy: 'az ágens dolgozott',
  stale_result: 'elavult eredmény (elutasítva)', verify_start: 'ellenőrzés indul', verified: 'ellenőrizve, lezárva', verify_red: 'az ellenőrzés piros',
  budget_exhausted: 'újraindítási keret elfogyott', human_needed: 'ember kell', human_claim_requested: 'emberi átvétel', human_resolved: 'kézzel lezárva',
  waiting: 'a box-incidensre vár',
  mail_first: 'e-mail a tulajdonosnak', mail_repeat: 'ismételt e-mail', mail_resolved: '„megoldva” e-mail', mail_failed: 'e-mail sikertelen',
};

/** „12 perce”, „3 órája”; null → „soha”. */
export function age(min: number | null): string {
  if (min === null) return 'soha';
  if (min < 1) return 'most';
  if (min < 60) return `${min} perce`;
  if (min < 48 * 60) return `${Math.floor(min / 60)} órája`;
  return `${Math.floor(min / 1440)} napja`;
}

export const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString('hu-HU', { timeZone: 'Europe/Budapest' }) : '—');

/** „1. gondnok (minden) · 2. helyettes (beta)”; üres lista → null. */
export function managerLine(ms: Manager[]): string | null {
  if (!ms.length) return null;
  return ms.map(m => `${m.rank}. ${m.handle ?? m.agent}${m.disabled_at ? ' (letiltva)' : ''} (${m.scope === '*' ? 'minden' : m.scope})`).join(' · ');
}

/** Az állapotgép (flotta-menedzser) címkéi; régi sorhoz (state nélkül) a status dönt. */
export const STATE_LABEL: Record<string, [string, string]> = {
  nyitott: ['nyitott', 'red'], kiosztva: ['kiosztva', 'orange'], atadva: ['átadva', 'orange'], atveve: ['átvéve', 'blue'],
  javit: ['javít', 'blue'], ellenorzes: ['ellenőrzés', 'blue'], 'ember-kell': ['ember kell', 'magenta'], megoldva: ['megoldva', 'default'],
};
export const stateOf = (i: Incident) => STATE_LABEL[i.state ?? (i.status === 'open' ? 'nyitott' : 'megoldva')] ?? [i.state ?? i.status, 'default'];
