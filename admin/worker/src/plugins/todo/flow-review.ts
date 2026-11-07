// submit, accept, reject: the developer's AC report and the PM's verdict.
// The report is frozen at submit (one result per live AC, with the AC text);
// pm_ok and pm_note are written only here, by accept and reject.
import { newId } from './id';
import { marked, now } from './store';
import { keys, object, Problem, textField } from './types';
import type { Item } from './item-store';
import type { Move } from './flow';

type Result = { ac_id: string; verdict: string; evidence: string };
type Check = { ac_id: string; pm_ok: boolean; pm_note: string | null };

/** Each id of `expected` exactly once: unknown, removed, duplicate or missing ids are refused. */
function exactlyOnce(ids: string[], expected: string[], what: string) {
  const seen = new Set<string>();
  for (const id of ids) {
    if (!expected.includes(id)) throw new Problem(`${what}: ${id} is not a live AC of this item`);
    if (seen.has(id)) throw new Problem(`${what}: ${id} appears twice`);
    seen.add(id);
  }
  const missing = expected.filter(id => !seen.has(id));
  if (missing.length) throw new Problem(`${what}: missing ${missing.join(', ')}`);
}
const list = (v: unknown, name: string) => {
  if (!Array.isArray(v) || v.length > 200) throw new Problem(`${name} must be a list`);
  return v.map(x => object(x));
};

export async function submitMove(db: D1Database, item: Item, actor: string, body: Record<string, unknown>): Promise<Move> {
  const last = (await db.prepare('SELECT max(round) AS r FROM backlog_report WHERE item_id = ?').bind(item.id).first<{ r: number | null }>())?.r ?? 0;
  if (body.round !== last + 1) throw new Problem(`round must be ${last + 1}`, 409, item);
  const live = (await db.prepare('SELECT id FROM backlog_ac WHERE item_id = ? AND removed_at IS NULL').bind(item.id).all<{ id: string }>()).results.map(a => a.id);
  if (!live.length) throw new Problem('submit needs at least one live AC; ask the PM to add one');
  const results: Result[] = list(body.results, 'results').map(r => {
    keys(r, ['ac_id', 'verdict', 'evidence']);
    if (!['met', 'not_met', 'na'].includes(String(r.verdict))) throw new Problem('verdict must be met, not_met or na');
    return { ac_id: textField(r.ac_id, 'ac_id'), verdict: String(r.verdict), evidence: textField(r.evidence, 'evidence', 10000) };
  });
  exactlyOnce(results.map(r => r.ac_id), live, 'results');
  const summary = textField(body.summary, 'summary', 2000);
  const text = body.body == null ? null : textField(body.body, 'body', 100000);
  const sha = body.head_sha ?? null;
  if (sha !== null && (typeof sha !== 'string' || !/^[0-9a-f]{7,64}$/.test(sha))) throw new Problem('head_sha must be a hex commit id');
  const links = body.links === undefined ? [] : list(body.links, 'links').map(l => {
    keys(l, ['kind', 'url', 'title']);
    if (l.kind !== undefined && l.kind !== 'pr') throw new Problem('submit links are pr links');
    if (typeof l.url !== 'string' || l.url.length > 2000 || !/^https?:\/\/\S+$/.test(l.url)) throw new Problem('links[].url must be an http(s) URL');
    return { url: l.url, title: l.title == null ? null : textField(l.title, 'title', 500) };
  });
  const id = newId(), at = now();
  return { verb: 'submit', from: ['taken'], by: 'dev', to: 'review', assignee: null,
    diff: { report_id: id, round: last + 1, summary, results: results.map(r => ({ ac_id: r.ac_id, verdict: r.verdict })) },
    guard: 'NOT EXISTS (SELECT 1 FROM backlog_report WHERE item_id = ? AND round > ?)', guardArgs: [item.id, last],
    related: op => [
      db.prepare(`INSERT INTO backlog_report (id,item_id,round,submitted_by,submitted_at,head_sha,summary,body) SELECT ?,?,?,?,?,?,?,? WHERE ${marked}`)
        .bind(id, item.id, last + 1, actor, at, sha, summary, text, op),
      ...results.map(r => db.prepare(`INSERT INTO backlog_ac_result (report_id,ac_id,ac_text,verdict,evidence)
        SELECT ?, a.id, a.text, ?, ? FROM backlog_ac a WHERE a.id = ? AND a.item_id = ? AND a.removed_at IS NULL AND ${marked}`)
        .bind(id, r.verdict, r.evidence, r.ac_id, item.id, op)),
      ...links.map(l => db.prepare(`INSERT INTO backlog_link (id,item_id,kind,url,title,created_by,created_at) SELECT ?,?,'pr',?,?,?,?
        WHERE ${marked} AND NOT EXISTS (SELECT 1 FROM backlog_link WHERE item_id = ? AND kind = 'pr' AND url = ? AND removed_at IS NULL)`)
        .bind(newId(), item.id, l.url, l.title, actor, at, op, item.id, l.url)),
    ] };
}

export async function verdictMove(db: D1Database, item: Item, actor: string, body: Record<string, unknown>, accept: boolean): Promise<Move> {
  const report = await db.prepare('SELECT id, round FROM backlog_report WHERE item_id = ? AND pm_verdict IS NULL ORDER BY round DESC LIMIT 1')
    .bind(item.id).first<{ id: string; round: number }>();
  if (!report && item.stage === 'review') throw new Problem('no open report to decide', 409);
  const results = report ? (await db.prepare('SELECT ac_id, verdict FROM backlog_ac_result WHERE report_id = ?').bind(report.id).all<{ ac_id: string; verdict: string }>()).results : [];
  const checks: Check[] = list(body.checks, 'checks').map(k => {
    keys(k, ['ac_id', 'pm_ok', 'pm_note']);
    if (![true, false, 1, 0].includes(k.pm_ok as never)) throw new Problem('pm_ok must be true/false (or 1/0)');
    return { ac_id: textField(k.ac_id, 'ac_id'), pm_ok: k.pm_ok === true || k.pm_ok === 1, pm_note: k.pm_note == null ? null : textField(k.pm_note, 'pm_note', 10000) };
  });
  if (report) exactlyOnce(checks.map(k => k.ac_id), results.map(r => r.ac_id), 'checks');
  const note = body.note == null ? null : textField(body.note, 'note', 10000);
  // The report must still cover every live AC, so an AC that arrived after submit is never accepted unread.
  const covers = `NOT EXISTS (SELECT 1 FROM backlog_ac a WHERE a.item_id = ? AND a.removed_at IS NULL
    AND a.id NOT IN (SELECT ac_id FROM backlog_ac_result WHERE report_id = ?))`;
  if (accept && report && !(await db.prepare(`SELECT ${covers} AS ok`).bind(item.id, report.id).first<{ ok: number }>())?.ok) {
    throw new Problem('the report does not cover every live AC; reject so the developer reports again', 409, item);
  }
  if (accept) {
    if (checks.some(k => !k.pm_ok)) throw new Problem('accept needs pm_ok true on every AC; reject instead');
    if (results.some(r => r.verdict === 'not_met')) throw new Problem('accept needs every AC met or n/a; reject instead');
  } else {
    if (!checks.some(k => !k.pm_ok)) throw new Problem('reject needs at least one AC with pm_ok false');
    if (checks.some(k => !k.pm_ok && !k.pm_note)) throw new Problem('every AC with pm_ok false needs a pm_note');
    if (!note) throw new Problem('reject needs a note');
  }
  const at = now(), verdict = accept ? 'accepted' : 'rejected';
  return { verb: accept ? 'accept' : 'reject', from: ['review'], by: 'pm', to: accept ? 'done' : 'taken',
    assignee: accept ? null : item.dev_id,
    diff: { report_id: report?.id ?? null, round: report?.round ?? null, verdict, note, checks },
    guard: `EXISTS (SELECT 1 FROM backlog_report WHERE id = ? AND pm_verdict IS NULL)${accept ? ` AND ${covers}` : ''}`,
    guardArgs: [report?.id ?? null, ...(accept ? [item.id, report?.id ?? null] : [])],
    related: op => report ? [
      ...checks.map(k => db.prepare(`UPDATE backlog_ac_result SET pm_ok = ?, pm_note = ? WHERE report_id = ? AND ac_id = ? AND ${marked}`)
        .bind(k.pm_ok ? 1 : 0, k.pm_note, report.id, k.ac_id, op)),
      db.prepare(`UPDATE backlog_report SET pm_verdict = ?, pm_note = ?, decided_by = ?, decided_at = ? WHERE id = ? AND ${marked}`)
        .bind(verdict, note, actor, at, report.id, op),
    ] : [] };
}
