// `mint-token --on`: the token is made on the target and stays there. The
// target is a temp HOME behind a fake ssh; D1 is a fake wrangler (--local).
import { describe, it, expect } from 'vitest';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { parseRemote } from '../scripts/lib/mint-on.mjs';
import { fakeBins } from './fake-bins';

const CLI = join(__dirname, '..', 'scripts', 'mint-token.mjs');
const ID = '00000000-0000-4000-8000-000000000001';
const HASH = 'a'.repeat(64);

function run(extraEnv: Record<string, string> = {}, args: string[] = []) {
  const bins = fakeBins();
  bins.setRules([{ match: '^d1 execute', stdout: '[{"results":[]}]' }]);
  const target = mkdtempSync(join(tmpdir(), 'target-'));
  const r = spawnSync(process.execPath, [CLI, '--agent', 'box-agent', '--scope', 'todo:write', '--local', '--on', 'ops@box', '--token-file', '~/.config/box-agent/admin-token', ...args], {
    encoding: 'utf8',
    env: { PATH: process.env.PATH, HOME: mkdtempSync(join(tmpdir(), 'home-')), FAKE_TARGET_HOME: target, ...bins.env, ...extraEnv },
  });
  return { r, bins, target, file: join(target, '.config', 'box-agent', 'admin-token') };
}

describe('mint-token --on', () => {
  it('writes the token only on the target (0600) and inserts its hash', () => {
    const { r, bins, file } = run();
    expect(r.status, r.stderr).toBe(0);
    const plain = readFileSync(file, 'utf8').trim();
    expect(plain).toMatch(/^mentat_[A-Za-z0-9_-]{43}$/);
    expect(statSync(file).mode & 0o777).toBe(0o600);
    expect(statSync(join(file, '..')).mode & 0o777).toBe(0o700);
    expect(r.stdout + r.stderr).not.toContain(plain);
    expect(r.stdout).toContain(file);
    const d1 = bins.calls().filter((c) => c.argv[0] === 'd1');
    expect(d1).toHaveLength(1);
    const sql = d1[0].argv[d1[0].argv.indexOf('--command') + 1];
    expect(sql).toContain(createHash('sha256').update(plain).digest('hex'));
    expect(sql).toMatch(/INSERT INTO agent_token .*'box-agent'.*'todo:write'/);
    expect(bins.rawLog()).not.toContain(plain);
    expect(readFileSync(`${bins.env.FAKE_LOG}.ssh`, 'utf8')).toContain('ops@box node --input-type=module');
  });

  it('refuses when the token file already exists — no overwrite, no INSERT', () => {
    const target = mkdtempSync(join(tmpdir(), 'target-'));
    const file = join(target, '.config', 'box-agent', 'admin-token');
    mkdirSync(join(file, '..'), { recursive: true });
    writeFileSync(file, 'keep me\n');
    const { r, bins } = run({ FAKE_TARGET_HOME: target });
    expect(r.status).toBe(1);
    expect(r.stderr).toMatch(/already exists/);
    expect(readFileSync(file, 'utf8')).toBe('keep me\n');
    expect(bins.calls()).toHaveLength(0);
  });

  it.each([
    ['not JSON', 'Welcome to the box!'],
    ['a plaintext-looking field', JSON.stringify({ id: ID, hash: HASH, file: '/x', token: `mentat_${'x'.repeat(43)}` })],
    ['a bad hash', JSON.stringify({ id: ID, hash: 'nope', file: '/x' })],
  ])('refuses malformed target output (%s) and inserts nothing', (_l, answer) => {
    const { r, bins } = run({ FAKE_SSH_ANSWER: answer });
    expect(r.status).toBe(1);
    expect(r.stderr).toMatch(/target answer/);
    expect(bins.calls()).toHaveLength(0);
  });

  it('validates the request before anything reaches the target', () => {
    const { r, bins, file } = run({}, ['--days', '999']);
    expect(r.status).toBe(1);
    expect(existsSync(`${bins.env.FAKE_LOG}.ssh`)).toBe(false);
    expect(existsSync(file)).toBe(false);
  });
});

describe('parseRemote', () => {
  it('accepts exactly {id, hash, file}', () => {
    expect(parseRemote(`${JSON.stringify({ id: ID, hash: HASH, file: '/a/b' })}\n`)).toEqual({ id: ID, hash: HASH, file: '/a/b' });
    expect(() => parseRemote(`${JSON.stringify({ id: ID, hash: HASH, file: '/a' })}\nextra`)).toThrow(/2 lines/);
    expect(() => parseRemote(JSON.stringify({ id: ID, hash: HASH, file: `/x/mentat_${'y'.repeat(43)}` }))).toThrow(/token-like/);
  });
});
