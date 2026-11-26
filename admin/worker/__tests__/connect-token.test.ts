// `connect` when the repo already has a token: a token whose scopes do not
// cover the plugins asked for is replaced — the new one is minted, written and
// proven to work first, only then the old one is revoked — and with todo the
// agent's principal follows the token, so `todo me` answers with no manual step.
// Real migrations on SQLite, the real app for "does it work" and /me.
import { describe, it, expect } from 'vitest';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import app from '../src/index';
import { makeDb, makeEnv } from './helpers';
import { connect } from '../scripts/lib/connect.mjs';
import { mint } from '../scripts/lib/mint.mjs';
import { bindToken, neededScopes, pluginsFor } from '../scripts/lib/connect-token.mjs';

const ORIGIN = 'http://localhost:8787';
function setup() {
  const { DB, raw } = makeDb();
  const env = makeEnv({ DB });
  const query = async (sqls: string[]) => sqls.map((s) => {
    const st = raw.prepare(s);
    return st.reader ? (st.all() as Record<string, unknown>[]) : (st.run(), []);
  });
  const repo = mkdtempSync(join(tmpdir(), 'repo-'));
  execFileSync('git', ['init', '-q', repo]);
  writeFileSync(join(repo, '.gitignore'), '.env\n.mentat/\n');
  writeFileSync(join(repo, 'mentat.json'), JSON.stringify({ schema: 1, agent: { name: 'anna-agent' } }));
  const get = (path: string, token: string) => app.request(path, { headers: { 'X-Mentat-Token': token } }, env);
  const works = async (token: string) => (await get('/api/todo/v1/labels', token)).status !== 401;
  const env_ = () => readFileSync(join(repo, '.env'), 'utf8').match(/^MENTAT_ADMIN_TOKEN=(.*)$/m)![1];
  const doc = () => JSON.parse(readFileSync(join(repo, 'mentat.json'), 'utf8'));
  const tokens = () => raw.prepare('SELECT id, scopes, active FROM agent_token ORDER BY created_at, rowid').all() as { id: string; scopes: string; active: number }[];
  const connectFn = (scopes: string, plugins: string[]) =>
    connect({ repo, url: ORIGIN, scopes, plugins, mintFn: (req: any) => mint(query, req) });
  const bind = (asked?: string[], extra: Record<string, unknown> = {}) =>
    bindToken({ query, repo, origin: ORIGIN, tokenEnv: 'MENTAT_ADMIN_TOKEN', asked, works, connectFn, ...extra });
  return { raw, query, repo, get, works, env_, doc, tokens, bind };
}

describe('pluginsFor / neededScopes', () => {
  it('adds to what the repo already has (no plugins key = cases) and asks one scope per plugin', () => {
    expect(pluginsFor({ components: { admin: {} } }, ['todo'])).toEqual(['cases', 'todo']);
    expect(pluginsFor({ components: { admin: { plugins: ['todo'] } } }, undefined)).toEqual(['todo']);
    expect(pluginsFor({}, undefined)).toEqual(['cases']);
    expect(neededScopes(['cases', 'todo'])).toBe('cases:write todo:write');
  });
});

describe('bindToken', () => {
  it('a cases:write token + --plugins todo → a new token with todo:write; new proven first, then the old revoked; todo me answers', async () => {
    const t = setup();
    await t.bind(['cases']);
    const old = t.env_();
    const [first] = t.tokens();
    expect(first.scopes).toBe('cases:write');

    const order: string[] = [];
    const out = await t.bind(['todo'], {
      works: async (tok: string) => {
        order.push(`works ${tok === old ? 'old' : 'new'}; old active=${t.tokens()[0].active}`);
        return t.works(tok);
      },
    });
    expect(out.minted!.scopes).toBe('cases:write todo:write');
    expect(out.revoked).toEqual([first.id]);
    expect(order.at(-1)).toBe('works new; old active=1');
    expect(t.tokens().map((r) => r.active)).toEqual([0, 1]);
    expect(t.env_()).not.toBe(old);
    expect((await t.get('/api/todo/v1/me', old)).status).toBe(401);

    const me = await t.get('/api/todo/v1/me', t.env_());
    expect(me.status).toBe(200);
    expect(await me.json()).toMatchObject({ kind: 'agent', handle: 'anna_agent' });
    expect(t.doc().components.admin).toEqual({ plugins: ['cases', 'todo'], todo_handle: 'anna_agent' });
    expect(readFileSync(join(t.repo, 'mentat.json'), 'utf8')).not.toContain('mentat_');
  });

  it('a rerun keeps a token that already covers everything', async () => {
    const t = setup();
    await t.bind(['cases', 'todo']);
    const tok = t.env_();
    const out = await t.bind(['todo']);
    expect(out.kept).toBeTruthy();
    expect(t.env_()).toBe(tok);
    expect(t.tokens()).toHaveLength(1);
  });

  it('a rotation carries the same principal over to the new token', async () => {
    const t = setup();
    await t.bind(['todo'], { handle: 'anna' });
    const before = await (await t.get('/api/todo/v1/me', t.env_())).json();
    await t.bind(['cases']);
    const after = await (await t.get('/api/todo/v1/me', t.env_())).json();
    expect(after).toMatchObject({ id: (before as any).id, handle: 'anna' });
    expect(t.doc().components.admin.todo_handle).toBe('anna');
  });

  it('a new token that does not work: the old one stays in .env and active, the new one is revoked', async () => {
    const t = setup();
    await t.bind(['cases']);
    const old = t.env_();
    await expect(t.bind(['todo'], { works: async (tok: string) => tok === old })).rejects.toThrow(/did not work.*nothing of the old one was revoked/);
    expect(t.env_()).toBe(old);
    expect(t.tokens().map((r) => r.active)).toEqual([1, 0]);
  });
});
