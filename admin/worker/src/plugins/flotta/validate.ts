// A box jelentésének alakja. Szigorú, mert gépi bemenet: ami nem ilyen, 400.
import { normalizeCheck, Problem } from './types';

export type RedCheck = { check: string; detail: string };
/** Az utolsó LEFUTOTT tick (csak a tick írja; flotta-menedzser): az ütemezés kívülről is lekérdezhető. */
export type Tick = { owner: 'fleet' | 'session' | 'none'; period_s: number | null; last_tick_at: string | null; age_s: number | null };
export type AgentReport = { agent: string; measured_at: string | null; red: RedCheck[]; unknown: string[]; ok: string[]; tick: Tick | null; desktop: boolean };
export type Report = {
  box: string; fleet_version: string | null; sent_at: string | null;
  release: { here: string | null; latest: string | null; lag: string | null } | null;
  agents: AgentReport[];
  /** A box javító-próbája (a végrehajtó önellenőrzése, flotta-menedzser). null = nem mért. */
  repair: { ok: boolean; detail: string | null } | null;
};

export const NAME_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;
export const CHECK_RE = /^[a-z0-9][a-z0-9:_-]{0,63}$/;
const MAX_AGENTS = 100, MAX_LINES = 50, MAX_TEXT = 500;

const obj = (v: unknown, what: string) => {
  if (!v || typeof v !== 'object' || Array.isArray(v)) throw new Problem(`${what} must be an object`, 400, 'invalid');
  return v as Record<string, unknown>;
};
const optText = (v: unknown, what: string, max = 200): string | null => {
  if (v === undefined || v === null) return null;
  if (typeof v !== 'string' || v.length > max) throw new Problem(`${what} must be text up to ${max}`, 400, 'invalid');
  return v;
};
const optTime = (v: unknown, what: string) => {
  const t = optText(v, what, 40);
  if (t !== null && Number.isNaN(Date.parse(t))) throw new Problem(`${what} must be an ISO timestamp`, 400, 'invalid');
  return t;
};
const lines = (v: unknown, what: string): string[] => {
  if (v === undefined) return [];
  if (!Array.isArray(v) || v.length > MAX_LINES) throw new Problem(`${what} must be a list up to ${MAX_LINES}`, 400, 'invalid');
  return v.map((x, i) => optText(x, `${what}[${i}]`, MAX_TEXT) ?? '');
};

export function parseReport(input: unknown): Report {
  const b = obj(input, 'body');
  const box = optText(b.box, 'box', 64);
  if (!box || !NAME_RE.test(box)) throw new Problem('box must be a box name', 400, 'invalid');
  if (!Array.isArray(b.agents) || b.agents.length > MAX_AGENTS) throw new Problem(`agents must be a list up to ${MAX_AGENTS}`, 400, 'invalid');
  const seen = new Set<string>();
  const agents = b.agents.map((raw, i): AgentReport => {
    const a = obj(raw, `agents[${i}]`);
    const agent = optText(a.agent, `agents[${i}].agent`, 64);
    if (!agent || !NAME_RE.test(agent)) throw new Problem(`agents[${i}].agent must be an agent name`, 400, 'invalid');
    if (seen.has(agent)) throw new Problem(`agent ${agent} appears twice`, 400, 'invalid');
    seen.add(agent);
    if (a.red !== undefined && (!Array.isArray(a.red) || a.red.length > MAX_LINES)) throw new Problem(`agents[${i}].red must be a list`, 400, 'invalid');
    const red = ((a.red as unknown[] | undefined) ?? []).map((r, j) => {
      const x = obj(r, `agents[${i}].red[${j}]`);
      const check = optText(x.check, 'check', 64);
      if (!check || !CHECK_RE.test(check)) throw new Problem(`agents[${i}].red[${j}].check must match ${CHECK_RE}`, 400, 'invalid');
      // a kulcs a zárt listára kerül (ismeretlen → egyeb); a részlet csak tárolt adat, sosem utasítás
      return { check: normalizeCheck(check), detail: optText(x.detail, 'detail', MAX_TEXT) ?? '' };
    });
    const tk = a.tick === undefined || a.tick === null ? null : obj(a.tick, `agents[${i}].tick`);
    const num = (v: unknown, what: string) => {
      if (v === undefined || v === null) return null;
      if (!Number.isInteger(v) || (v as number) < 0) throw new Problem(`${what} must be a non-negative integer`, 400);
      return v as number;
    };
    if (tk && !['fleet', 'session', 'none'].includes(tk.owner as string)) throw new Problem(`agents[${i}].tick.owner must be fleet, session or none`, 400);
    const tick = tk && { owner: tk.owner as Tick['owner'], period_s: num(tk.period_s, 'tick.period_s'),
      last_tick_at: optTime(tk.last_tick_at, 'tick.last_tick_at'), age_s: num(tk.age_s, 'tick.age_s') };
    if (a.desktop !== undefined && typeof a.desktop !== 'boolean') throw new Problem(`agents[${i}].desktop must be a boolean`, 400);
    return { agent, tick, desktop: a.desktop === true, measured_at: optTime(a.measured_at, 'measured_at'), red,
      unknown: lines(a.unknown, `agents[${i}].unknown`), ok: lines(a.ok, `agents[${i}].ok`) };
  });
  const rel = b.release === undefined || b.release === null ? null : obj(b.release, 'release');
  const rep = b.repair === undefined || b.repair === null ? null : obj(b.repair, 'repair');
  if (rep && typeof rep.ok !== 'boolean') throw new Problem('repair.ok must be a boolean', 400);
  return {
    repair: rep && { ok: rep.ok as boolean, detail: optText(rep.detail, 'repair.detail', MAX_TEXT) },
    box, agents, fleet_version: optText(b.fleet_version, 'fleet_version', 40), sent_at: optTime(b.sent_at, 'sent_at'),
    release: rel && { here: optText(rel.here, 'release.here', 80), latest: optText(rel.latest, 'release.latest', 80),
      lag: optText(rel.lag, 'release.lag', MAX_TEXT) },
  };
}
