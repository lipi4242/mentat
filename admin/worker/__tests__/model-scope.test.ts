// After `model new` the agent's token must reach the new entity without a
// hand-made revoke + connect dance (mérés 14).
import { describe, it, expect } from 'vitest';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { scopesFor, widenToken } from '../scripts/lib/model-scope.mjs';

const models = { fields: {}, entities: [{ name: 'ugyfelek', label: 'Ügyfelek', fields: [] }, { name: 'szamlak', label: 'Számlák', fields: [] }] } as any;

function repo() {
  const r = mkdtempSync(join(tmpdir(), 'agent-'));
  execFileSync('git', ['init', '-q', r]);
  writeFileSync(join(r, '.gitignore'), '.env\n.mentat/\n');
  writeFileSync(join(r, 'mentat.json'), JSON.stringify({ schema: 1, agent: { name: 'teszt-thufir' }, components: { admin: { plugins: ['cases'] } } }));
  mkdirSync(join(r, '.mentat'));
  writeFileSync(join(r, '.mentat', 'local.json'), JSON.stringify({ schema: 1, admin: { url: 'http://localhost:8787', token_env: 'MENTAT_ADMIN_TOKEN' } }));
  writeFileSync(join(r, '.env'), 'MENTAT_ADMIN_TOKEN=old\n');
  return r;
}
const fakeQuery = (rows: any[], log: string[]) => async (sqls: string[]) => sqls.map((s) => { log.push(s); return /^SELECT/.test(s) ? rows : [{ id: 'old-1' }]; });

describe('scopesFor', () => {
  it('is cases plus every declared entity, write scope', () => {
    expect(scopesFor(models)).toBe('cases:write ugyfelek:write szamlak:write');
  });
});

describe('widenToken', () => {
  it('does nothing when an active token already has the scope', async () => {
    const log: string[] = [];
    const out = await widenToken({ repo: repo(), url: 'http://localhost:8787', models, entity: 'ugyfelek', query: fakeQuery([{ id: 'a', scopes: 'cases:write ugyfelek:write' }], log) });
    expect(out.state).toBe('has');
    expect(log).toHaveLength(1);
  });

  it('mints a token with the old + new scopes, binds it, revokes the old one — one call', async () => {
    const r = repo();
    const log: string[] = [];
    const out = await widenToken({ repo: r, url: 'http://localhost:8787', models, entity: 'ugyfelek', query: fakeQuery([{ id: 'old-1', scopes: 'cases:write' }], log) });
    expect(out.state).toBe('widened');
    expect(out.line).toMatch(/ugyfelek:write/);
    expect(readFileSync(join(r, '.env'), 'utf8')).toMatch(/^MENTAT_ADMIN_TOKEN=mentat_/);
    expect(readFileSync(join(r, '.env'), 'utf8')).not.toContain('old');
    const ins = log.find((s) => s.startsWith('INSERT'))!;
    expect(ins).toContain('cases:write ugyfelek:write');
    expect(log.find((s) => s.startsWith('UPDATE'))).toMatch(/id != /);
    expect(out.line).not.toContain('mentat_');
  });

  it('skips with a reason when the repo has no mentat.json', async () => {
    const out = await widenToken({ repo: mkdtempSync(join(tmpdir(), 'x-')), url: 'u', models, entity: 'ugyfelek', query: fakeQuery([], []) });
    expect(out.state).toBe('skipped');
  });
});
