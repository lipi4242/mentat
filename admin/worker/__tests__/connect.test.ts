// `connect` against a throwaway agent repo (git init in a temp dir). The mint
// is faked; the files, git-ignore checks and the flock are real.
import { describe, it, expect } from 'vitest';
import { execFileSync, spawn } from 'node:child_process';
import { mkdtempSync, readFileSync, statSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { connect, checkUrl } from '../scripts/lib/connect.mjs';
import { withLock } from '../scripts/lib/manifest.mjs';

const SECRET = 'mentat_fake-token-value';
const fakeMint = async (req: any) => ({ id: 'tok-1', token: SECRET, label: req.label, scopes: req.scopes, expires_at: '2027-01-01 00:00:00' });

function agentRepo({ ignore = '.env\n.mentat/\n', mentat = { schema: 1, agent: { name: 'teszt-agent', language: 'hu' }, components: { brain: { root: 'agy' } }, cases: { backend: 'markdown' } } as any } = {}) {
  const repo = mkdtempSync(join(tmpdir(), 'agent-'));
  execFileSync('git', ['init', '-q', repo]);
  writeFileSync(join(repo, '.gitignore'), ignore);
  if (mentat) writeFileSync(join(repo, 'mentat.json'), JSON.stringify(mentat));
  return repo;
}
const json = (p: string) => JSON.parse(readFileSync(p, 'utf8'));

describe('connect', () => {
  it('binds a repo: token to .env (0600), URL + env name to local.json, components.admin to mentat.json', async () => {
    const repo = agentRepo();
    mkdirSync(join(repo, '.mentat'));
    writeFileSync(join(repo, '.mentat', 'local.json'), JSON.stringify({ schema: 1, fleet: { agent_id: 'x' }, admin: { keep: 1 } }));
    writeFileSync(join(repo, '.env'), 'OTHER=1\nMENTAT_ADMIN_TOKEN=old\n');

    const out = await connect({ repo, url: 'http://localhost:8787/', mintFn: fakeMint, plugins: ['cases'] });

    expect(JSON.stringify(out)).not.toContain(SECRET);
    expect(readFileSync(join(repo, '.env'), 'utf8')).toBe(`OTHER=1\nMENTAT_ADMIN_TOKEN=${SECRET}\n`);
    expect(statSync(join(repo, '.env')).mode & 0o777).toBe(0o600);
    expect(json(join(repo, '.mentat', 'local.json'))).toEqual({
      schema: 1,
      fleet: { agent_id: 'x' },
      admin: { keep: 1, url: 'http://localhost:8787', token_env: 'MENTAT_ADMIN_TOKEN' },
    });
    const m = json(join(repo, 'mentat.json'));
    expect(m.components).toEqual({ brain: { root: 'agy' }, admin: { plugins: ['cases'] } });
    expect(m.agent).toEqual({ name: 'teszt-agent', language: 'hu' });
    expect(m.cases).toEqual({ backend: 'markdown' });
    expect(readFileSync(join(repo, 'mentat.json'), 'utf8')).not.toContain('localhost');
  });

  it('uses the agent name from mentat.json as the token label', async () => {
    let seen: any;
    await connect({ repo: agentRepo(), url: 'https://admin.example.com', mintFn: async (r) => ((seen = r), fakeMint(r)) });
    expect(seen).toMatchObject({ label: 'teszt-agent', scopes: 'cases:write' });
  });

  it.each([
    ['.env not gitignored', { ignore: '.mentat/\n' }, /\.env is not gitignored/],
    ['local.json not gitignored', { ignore: '.env\n' }, /local\.json is not gitignored/],
    ['no mentat.json', { mentat: null }, /no mentat\.json/],
    ['a newer schema', { mentat: { schema: 2, agent: { name: 'a' } } }, /schema 2 is newer/],
  ])('refuses — and mints nothing — when %s', async (_l, setup, msg) => {
    const repo = agentRepo(setup as any);
    let minted = 0;
    await expect(connect({ repo, url: 'http://localhost:8787', mintFn: async (r) => (minted++, fakeMint(r)) })).rejects.toThrow(msg);
    expect(minted).toBe(0);
    expect(existsSync(join(repo, '.env'))).toBe(false);
  });

  it('rejects an IP-address URL, but allows loopback for local dev', () => {
    expect(() => checkUrl('http://203.0.113.7:8787')).toThrow(/hostname/);
    expect(checkUrl('http://127.0.0.1:8787/x')).toBe('http://127.0.0.1:8787');
    expect(() => checkUrl('ftp://admin.example.com')).toThrow(/http/);
  });

  it('waits for a Python writer holding .mentat/lock (same fcntl.flock)', async () => {
    const repo = agentRepo();
    mkdirSync(join(repo, '.mentat'));
    const py = spawn('python3', ['-c', [
      'import fcntl, os, sys, time',
      `fd = os.open(${JSON.stringify(join(repo, '.mentat', 'lock'))}, os.O_RDWR | os.O_CREAT)`,
      'fcntl.flock(fd, fcntl.LOCK_EX)',
      "print('held', flush=True)",
      'time.sleep(0.7)',
    ].join('\n')]);
    await new Promise((r) => py.stdout.once('data', r));
    const t0 = Date.now();
    await withLock(repo, () => undefined);
    expect(Date.now() - t0).toBeGreaterThanOrEqual(500);
  });
});
