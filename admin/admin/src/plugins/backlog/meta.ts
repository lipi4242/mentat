// Feltételezett szerződés: backlog SPEC v2 §2–§3 (lásd a jelentést).
export { API, type Principal, type Comment } from '../todo/meta';
export type Stage = 'draft' | 'issued' | 'taken' | 'review' | 'done' | 'hold' | 'dropped';
export type Verb = 'issue' | 'take' | 'handback' | 'hold' | 'resume' | 'drop' | 'accept' | 'reject';
export type Project = { id: string; prefix: string; name: string };
export type Item = { id: string; key: string; project_id: string; title: string; stage: Stage; priority: number;
  owner_id: string; assignee_id: string | null; dev_id: string | null; parent_id: string | null; position: string; rev: number };
export type Ac = { id: string; text: string; position: string };
export type Result = { ac_id: string; ac_text: string; verdict: 'met' | 'not_met' | 'na'; evidence: string; pm_ok: 0 | 1 | boolean | null; pm_note: string | null };
export type Report = { id: string; round: number; summary: string; body: string | null; head_sha: string | null;
  submitted_at: string; pm_verdict: 'accepted' | 'rejected' | null; results: Result[] };
export type ItemDetail = Item & { description: string | null; request_quote: string | null; acs: Ac[];
  links: Array<{ id: string; kind: string; url: string | null; title: string | null }>; reports: Report[];
  comments: import('../todo/meta').Comment[] };
export type Me = { id: string; kind: string; handle: string };
/** The project prefix is the part of the key before the number. */
export const prefixOf = (key: string) => key.replace(/-\d+$/, '');
export const stageLabel: Record<Stage, string> = { draft: 'Tervezet', issued: 'Kiadva', taken: 'Átvéve', review: 'Átnézésre vár',
  done: 'Kész', hold: 'Félretéve', dropped: 'Elvetve' };
export const verbLabel: Record<Verb, string> = { issue: 'Kiadás', take: 'Átvétel', handback: 'Visszaadás', hold: 'Félretétel',
  resume: 'Folytatás', drop: 'Elvetés', accept: 'Elfogadás', reject: 'Visszautasítás' };
const PM: Record<Stage, Verb[]> = { draft: ['issue', 'hold', 'drop'], issued: ['hold', 'drop'], taken: ['hold', 'drop'],
  review: ['accept', 'reject', 'hold', 'drop'], hold: ['resume', 'drop'], done: [], dropped: [] };
const DEV: Partial<Record<Stage, Verb[]>> = { issued: ['take', 'handback'], taken: ['handback'] };
/** Only the verbs the stage and the actor allow (SPEC §3.2). A human session may do PM verbs; dev verbs are the dev's only. */
export function verbsFor(item: Pick<Item, 'stage' | 'owner_id' | 'dev_id'>, me: Me): Verb[] {
  const pm = me.kind === 'human' || me.id === item.owner_id;
  return [...(pm ? PM[item.stage] : []), ...(me.id === item.dev_id ? DEV[item.stage] ?? [] : [])];
}
/** A printable-ASCII position strictly between a (or the start) and b; null when no room is left. */
export function between(a: string, b: string): string | null {
  let out = '', free = false;
  for (let i = 0; i < 140; i++) {
    const ca = a.charCodeAt(i) || 32, cb = free ? 127 : b.charCodeAt(i) || 127;
    if (ca + 1 < cb) return out + String.fromCharCode(Math.floor((ca + cb) / 2));
    if (ca === 32) return null;
    out += String.fromCharCode(ca);
    if (ca < cb) free = true;
  }
  return null;
}
