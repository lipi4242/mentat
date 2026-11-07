// instance:seed-principals against a real SQLite with the real migrations:
// the SQL it builds must satisfy todo_principal's constraints and be safe to
// run twice.
import { describe, it, expect } from 'vitest';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fakeBins } from './fake-bins';
import { makeDb } from './helpers';
import { parseSeed, seedPrincipals } from '../scripts/lib/seed-principals.mjs';
import { buildMint } from '../scripts/lib/mint.mjs';

function setup() {
  const { raw } = makeDb();
  const query = async (sqls: string[]) => sqls.map((s) => {
    const st = raw.prepare(s);
    return st.reader ? (st.all() as Record<string, unknown>[]) : (st.run(), []);
  });
  const token = (label: string, scopes: string, id: string) =>
    raw.exec(buildMint({ label, scopes }, { id, hash: id.replace(/-/g, '').padEnd(64, '0').slice(0, 64) }).sql);
  return { raw, query, token };
}

const SEED = {
  humans: [{ email: 'Owner@Acme.example', name: 'Owner' }, { email: 'ops@acme.example' }],
  agents: [{ name: 'box-agent', display_name: 'Box' }],
};

describe('seed-principals', () => {
  it('inserts humans and agents once; a rerun changes nothing', async () => {
    const t = setup();
    t.token('box-agent', 'cases:write todo:write', 'aaaaaaaa-0000-4000-8000-000000000001');
    t.token('other', 'todo:write', 'aaaaaaaa-0000-4000-8000-000000000002');
    const entries = parseSeed(SEED);

    const first = await seedPrincipals(t.query, entries);
    expect(first.report!.map((r) => [r.ok, r.status])).toEqual([[true, 'inserted'], [true, 'inserted'], [true, 'inserted']]);
    const rows = t.raw.prepare('SELECT kind, handle, display_name, auth_email, agent_token_id FROM todo_principal ORDER BY handle').all();
    expect(rows).toEqual([
      { kind: 'agent', handle: 'box_agent', display_name: 'Box', auth_email: null, agent_token_id: 'aaaaaaaa-0000-4000-8000-000000000001' },
      { kind: 'human', handle: 'ops', display_name: 'ops', auth_email: 'ops@acme.example', agent_token_id: null },
      { kind: 'human', handle: 'owner', display_name: 'Owner', auth_email: 'owner@acme.example', agent_token_id: null },
    ]);
    const events = t.raw.prepare("SELECT actor_id, kind, json_extract(diff_json, '$.handle') AS handle FROM todo_event").all() as { handle: string }[];
    expect(events.map((e) => e.handle).sort()).toEqual(['box_agent', 'ops', 'owner']);

    const second = await seedPrincipals(t.query, parseSeed(SEED));
    expect(second.report!.every((r) => r.ok && /already there/.test(r.status))).toBe(true);
    expect(t.raw.prepare('SELECT count(*) AS n FROM todo_principal').get()).toEqual({ n: 3 });
    expect(t.raw.prepare('SELECT count(*) AS n FROM todo_event').get()).toEqual({ n: 3 });
  });

  it('reports an agent without a live todo:write token instead of inserting it', async () => {
    const t = setup();
    t.token('box-agent', 'cases:write', 'aaaaaaaa-0000-4000-8000-000000000003');
    const { report } = await seedPrincipals(t.query, parseSeed({ agents: [{ name: 'box-agent' }] }));
    expect(report![0].ok).toBe(false);
    expect(report![0].status).toMatch(/no live todo:write token/);
    expect(t.raw.prepare('SELECT count(*) AS n FROM todo_principal').get()).toEqual({ n: 0 });
  });

  it('refuses a taken handle and bad input; dry-run only builds SQL', async () => {
    const t = setup();
    await seedPrincipals(t.query, parseSeed({ humans: [{ email: 'anna@x.example' }] }));
    const { report } = await seedPrincipals(t.query, parseSeed({ humans: [{ email: 'anna@y.example' }] }));
    expect(report![0]).toMatchObject({ ok: false, status: expect.stringMatching(/handle @anna is taken/) });
    expect(() => parseSeed({ humans: [{ email: "x'@y" }] })).toThrow(/e-mail/);
    expect(() => parseSeed({ agents: [{ name: "a'); DROP TABLE x; --" }] })).toThrow(/label/);
    expect(() => parseSeed({ humans: [], robots: [] })).toThrow(/unknown keys/);
    const dry = await seedPrincipals(null, parseSeed(SEED), { dryRun: true });
    expect(dry.sql).toHaveLength(6);
  });
});

describe('seed-principals CLI', () => {
  it('--dry-run prints the SQL and never calls wrangler', () => {
    const bins = fakeBins();
    const file = join(mkdtempSync(join(tmpdir(), 'seed-')), 'p.json');
    writeFileSync(file, JSON.stringify(SEED));
    const r = spawnSync(process.execPath, [join(__dirname, '..', 'scripts', 'seed-principals.mjs'), '--file', file, '--local', '--dry-run'], {
      encoding: 'utf8', env: { PATH: process.env.PATH, HOME: mkdtempSync(join(tmpdir(), 'home-')), ...bins.env },
    });
    expect(r.status, r.stderr).toBe(0);
    expect(r.stdout).toContain('INSERT INTO todo_principal');
    expect(bins.calls()).toEqual([]);
  });
});
