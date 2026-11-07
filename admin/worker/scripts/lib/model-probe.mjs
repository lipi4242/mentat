// `npm run model`: look at the RUNNING local admin after the migration —
// /api/meta lists the new thing without `pending`, and one invalid value is
// refused by the admin. Nothing live is created: the refused write is
// rejected before it stores anything. Every outcome is a line, never a throw.
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const CROCKFORD = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** A throwaway case id (first digit ≤ 7, like the product's ULIDs). */
export const ulid = () => '01234567'[Math.floor(Math.random() * 8)] + Array.from({ length: 25 }, () => CROCKFORD[Math.floor(Math.random() * 32)]).join('');

/** The agent token: $MENTAT_ADMIN_TOKEN, else the one in <repo>/.env (name from .mentat/local.json). */
export function findToken(repo, env = process.env) {
  if (env.MENTAT_ADMIN_TOKEN) return env.MENTAT_ADMIN_TOKEN;
  if (!repo || !existsSync(join(repo, '.env'))) return '';
  let name = 'MENTAT_ADMIN_TOKEN';
  try { name = JSON.parse(readFileSync(join(repo, '.mentat', 'local.json'), 'utf8')).admin?.token_env ?? name; } catch { /* default */ }
  const line = readFileSync(join(repo, '.env'), 'utf8').split('\n').find((l) => l.startsWith(`${name}=`));
  return line ? line.slice(name.length + 1).trim().replace(/^['"]|['"]$/g, '') : '';
}

/** A value the field must refuse, or undefined when it has no rule that could (optional free text). */
export function badValue(f) {
  if (f.type === 'number' || f.type === 'integer') return f.min !== undefined ? f.min - 1 : f.max !== undefined ? f.max + 1 : 'not-a-number';
  if (f.type === 'date') return 'not-a-date';
  if (f.type === 'email') return 'not an address';
  if (f.type === 'select') return '__not-an-option__';
  if (f.type === 'checkbox') return 'maybe';
  return undefined;
}

async function call(url, token, method, path, body) {
  try {
    const r = await fetch(url + path, {
      method,
      headers: { 'X-Mentat-Token': token, 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(8000),
    });
    return { status: r.status, body: await r.json().catch(() => ({})) };
  } catch (e) {
    return { status: 0, body: { error: e.message } };
  }
}

/** The refused write for this request: [method, path, body, the field it should name]. */
function refusal(kind, target, field, entity) {
  if (kind === 'field' && target.name === 'cases') {
    const v = badValue(field);
    return v === undefined && !field.required ? null : ['PUT', `/api/cases/${ulid()}`, { title: 'model probe - must not exist', ...(v === undefined ? {} : { [field.name]: v }) }, field.name];
  }
  const e = entity;
  const req = e.fields.find((f) => f.required);
  if (req) return ['POST', `/api/${e.name}`, {}, req.name];
  const f = kind === 'field' ? field : e.fields.find((x) => badValue(x) !== undefined);
  return f && badValue(f) !== undefined ? ['POST', `/api/${e.name}`, { [f.name]: badValue(f) }, f.name] : null;
}

/** → { ok: true|false|null (null = could not check), listed (this token sees it), lines: [...] } */
export async function probe({ url, token, kind, target, field, models }) {
  if (!url) return { ok: null, lines: ['not probed: no worker/.dev.vars — this is not a connect --local admin'] };
  if (!(await call(url, token, 'GET', '/api/health')).status) return { ok: null, lines: [`not probed: nothing answers on ${url} (npm run status says why)`] };
  if (!token) return { ok: null, lines: ['not probed: no token — rerun the same command with --repo <agent repo> (or set MENTAT_ADMIN_TOKEN)'] };
  const entity = kind === 'entity' || target.name !== 'cases' ? models.entities.find((e) => e.name === target.name) : null;
  let seen = null;
  for (let i = 0; i < 12 && !seen; i++) {
    const m = await call(url, token, 'GET', '/api/meta');
    if (m.status === 401) return { ok: false, lines: ['/api/meta: 401 — the token is invalid or expired'] };
    const list = target.name === 'cases' ? m.body.fields?.cases : m.body.entities?.find((e) => e.name === target.name)?.fields;
    const hit = field ? list?.find((f) => f.name === field.name) : (list ? { name: target.name } : null);
    if (hit && !hit.pending) seen = hit;
    else if (i < 11) await sleep(1500);
  }
  if (!seen) return { ok: null, lines: [`/api/meta does not list ${target.name}${field ? `.${field.name}` : ''} (yet) for this token — a token sees only the models its scopes reach: see "token" below`] };
  const lines = [`/api/meta lists ${target.name}${field ? `.${field.name}` : ''} (no "pending")`];
  const r = refusal(kind, target, field, entity);
  if (!r) return { ok: true, listed: true, lines: [...lines, 'no rule that refuses a value (optional free text) — nothing to try'] };
  const [method, path, body, names] = r;
  const res = await call(url, token, method, path, body);
  const msg = String(res.body?.error ?? '');
  if (res.status === 400 || res.status === 422) return { ok: true, listed: true, lines: [...lines, `an invalid value is refused by the admin: ${res.status} "${msg}"${msg.includes(names) ? '' : ` (expected it to name ${names})`}`] };
  if (res.status === 401 || res.status === 403) return { ok: null, listed: true, lines: [...lines, `refusal not tried: ${res.status} — the token has no write scope for ${target.name}`] };
  return { ok: false, listed: true, lines: [...lines, `the admin did NOT refuse an invalid value: ${res.status || 'no answer'} ${msg}${res.status === 200 || res.status === 201 ? ` — it stored ${method} ${path}: remove that row` : ''}`] };
}
