// Seed the todo plugin's principals (todo_principal, migration 0400) from a
// small JSON file, the CLI twin of POST /principals:
//
//   {"humans": [{"email": "anna@example.com", "name": "Anna", "handle": "anna"}],
//    "agents": [{"name": "box-agent", "display_name": "Box", "handle": "box_agent"}]}
//
// A human is mapped by e-mail (it must be in ADMIN_EMAILS to sign in). An
// agent is mapped to the newest live todo:write token whose label is its
// `name` — mint that first. `handle` and `display_name` are optional.
//
// Idempotent: each INSERT only runs when no principal has that e-mail /
// handle / token yet, so a rerun inserts nothing. Like POST /principals it
// writes a principal_created event, with the new principal as actor.
// SQL as text (wrangler cannot bind): values are validated, then quoted.
import { randomBytes } from 'node:crypto';

const q = (v) => `'${String(v).replace(/'/g, "''")}'`;
const EMAIL_RE = /^[^\s@']+@[^\s@']+\.[^\s@']+$/;
const LABEL_RE = /^[A-Za-z0-9][A-Za-z0-9 ._@-]{0,63}$/;
export const CREATED_BY = 'cli:seed-principals';

// Same shape as worker/src/plugins/todo/id.ts newId (time-sortable, 26 chars).
const ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
function newId() {
  let t = Date.now(), prefix = '';
  for (let i = 0; i < 10; i++) { prefix = ALPHABET[t % 32] + prefix; t = Math.floor(t / 32); }
  return prefix + [...randomBytes(16)].map((n) => ALPHABET[n % 32]).join('');
}

const toHandle = (s) => String(s).toLowerCase().replace(/[^a-z0-9_]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 64);
function text(v, what, max = 200) {
  if (typeof v !== 'string' || !v.trim() || v.length > max) throw new Error(`${what} must be nonempty text, max ${max}`);
  return v.trim();
}
function handle(v, fallback, what) {
  const h = v === undefined ? toHandle(fallback) : v;
  if (typeof h !== 'string' || !/^[a-z0-9_]{1,64}$/.test(h)) throw new Error(`${what}: handle must be lowercase letters, digits or underscores`);
  return h;
}

/** The seed file's object → checked entries. Throws on the first bad one. */
export function parseSeed(obj) {
  if (!obj || typeof obj !== 'object') throw new Error('seed file must be a JSON object');
  const extra = Object.keys(obj).filter((k) => k !== 'humans' && k !== 'agents');
  if (extra.length) throw new Error(`unknown keys: ${extra.join(', ')}`);
  const humans = (obj.humans ?? []).map((h, i) => {
    const email = typeof h?.email === 'string' ? h.email.trim().toLowerCase() : '';
    if (!EMAIL_RE.test(email)) throw new Error(`humans[${i}].email is not an e-mail address`);
    const local = email.split('@')[0];
    return { kind: 'human', email, name: text(h.name ?? local, `humans[${i}].name`), handle: handle(h.handle, local, `humans[${i}]`) };
  });
  const agents = (obj.agents ?? []).map((a, i) => {
    if (typeof a?.name !== 'string' || !LABEL_RE.test(a.name)) throw new Error(`agents[${i}].name must be the agent token label`);
    return { kind: 'agent', label: a.name, name: text(a.display_name ?? a.name, `agents[${i}].display_name`), handle: handle(a.handle, a.name, `agents[${i}]`) };
  });
  return [...humans, ...agents];
}

/** One entry → [insert principal … RETURNING id, insert its event if it is new]. */
export function entrySql(e, id = newId()) {
  const common = `${q(id)}, ${q(e.kind)}, ${q(e.handle)}, ${q(e.name)}`;
  const principal = e.kind === 'human'
    ? `INSERT INTO todo_principal (id, kind, handle, display_name, auth_email, created_by, idem_key) ` +
      `SELECT ${common}, ${q(e.email)}, ${q(CREATED_BY)}, ${q(`seed:human:${e.email}`)} ` +
      `WHERE NOT EXISTS (SELECT 1 FROM todo_principal WHERE auth_email = ${q(e.email)} OR handle = ${q(e.handle)}) RETURNING id`
    : `INSERT INTO todo_principal (id, kind, handle, display_name, agent_token_id, created_by, idem_key) ` +
      `SELECT ${common}, t.id, ${q(CREATED_BY)}, ${q(`seed:agent:${e.label}`)} FROM agent_token t ` +
      `WHERE t.label = ${q(e.label)} AND t.active = 1 AND unixepoch(t.expires_at) > unixepoch('now') ` +
      `AND (' ' || t.scopes || ' ') LIKE '% todo:write %' ` +
      `AND NOT EXISTS (SELECT 1 FROM todo_principal p WHERE p.handle = ${q(e.handle)} OR p.agent_token_id = t.id) ` +
      `ORDER BY t.created_at DESC LIMIT 1 RETURNING id`;
  const event =
    `INSERT INTO todo_event (op_id, task_id, at, actor_id, kind, diff_json, recipients_json) ` +
    `SELECT ${q(newId())}, NULL, strftime('%Y-%m-%dT%H:%M:%fZ','now'), id, 'principal_created', ` +
    `json_object('id', id, 'kind', kind, 'handle', handle, 'display_name', display_name, 'avatar', avatar, 'auth_email', auth_email, 'agent_token_id', agent_token_id), ` +
    `json_array(id) FROM todo_principal WHERE id = ${q(id)}`;
  return [principal, event];
}

const LIST = 'SELECT p.kind, p.handle, p.auth_email, t.label AS agent_label FROM todo_principal p LEFT JOIN agent_token t ON t.id = p.agent_token_id';

/** Why an entry that inserted nothing is (or is not) fine. */
function status(e, rows) {
  const mine = rows.find((r) => (e.kind === 'human' ? r.auth_email === e.email : r.kind === 'agent' && r.agent_label === e.label));
  if (mine) return { ok: true, status: `already there (@${mine.handle})` };
  if (rows.some((r) => r.handle === e.handle)) return { ok: false, status: `handle @${e.handle} is taken by someone else — give a "handle"` };
  if (e.kind === 'agent') return { ok: false, status: `no live todo:write token labelled "${e.label}" — mint one first (npm run mint-token -- --agent "${e.label}" --scope todo:write …)` };
  return { ok: false, status: 'not inserted' };
}

/** → [{entry, ok, status}]. With dryRun only the SQL is returned. */
export async function seedPrincipals(queryMany, entries, { dryRun = false } = {}) {
  const sqls = entries.flatMap((e) => entrySql(e));
  if (dryRun) return { sql: sqls };
  const results = await queryMany([...sqls, LIST]);
  const rows = results[results.length - 1];
  return {
    report: entries.map((e, i) => (results[2 * i].length ? { entry: e, ok: true, status: 'inserted' } : { entry: e, ...status(e, rows) })),
  };
}
