// An instance's own extension (config/models.json + a 09NN migration) must
// survive a `git pull`/reset: committed on a local instance branch, mode 0644.
import { describe, it, expect, afterEach } from 'vitest';
import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { commitInstance, INSTANCE_BRANCH, writeInstanceFile } from '../scripts/lib/instance-files.mjs';

const git = (cwd: string, ...a: string[]) => execFileSync('git', ['-C', cwd, ...a], { encoding: 'utf8' }).trim();

function repo(branch = 'master') {
  const d = mkdtempSync(join(tmpdir(), 'inst-'));
  git(d, 'init', '-q', '-b', branch);
  git(d, 'config', 'user.email', 'dev@example.com');
  git(d, 'config', 'user.name', 'dev');
  mkdirSync(join(d, 'config'));
  mkdirSync(join(d, 'worker', 'migrations'), { recursive: true });
  writeFileSync(join(d, 'config', 'models.json'), '{"fields":{},"entities":[]}\n');
  git(d, 'add', '-A');
  git(d, 'commit', '-qm', 'product');
  return d;
}

function extend(d: string) {
  writeFileSync(join(d, 'config', 'models.json'), '{"fields":{"cases":[{"name":"osszeg"}]},"entities":[]}\n');
  writeInstanceFile(join(d, 'worker', 'migrations', '0900_osszeg.sql'), 'ALTER TABLE cases_case ADD COLUMN osszeg;\n');
  return ['config/models.json', 'worker/migrations/0900_osszeg.sql'];
}

const umask = process.umask();
afterEach(() => process.umask(umask));

describe('writeInstanceFile', () => {
  it('is 0644 even under a wide-open umask', () => {
    process.umask(0);
    const d = mkdtempSync(join(tmpdir(), 'mode-'));
    writeInstanceFile(join(d, 'a.sql'), 'x');
    expect(statSync(join(d, 'a.sql')).mode & 0o777).toBe(0o644);
  });
});

describe('commitInstance', () => {
  it('on the product branch: moves to the instance branch and commits both files there', () => {
    const d = repo();
    const out = commitInstance({ root: d, files: extend(d), message: 'chore(peldany): osszeg' });
    expect(out).toMatchObject({ committed: true, branch: INSTANCE_BRANCH });
    expect(git(d, 'branch', '--show-current')).toBe(INSTANCE_BRANCH);
    expect(git(d, 'status', '--porcelain')).toBe('');
    expect(git(d, 'log', '-1', '--format=%s')).toBe('chore(peldany): osszeg');
    expect(git(d, 'log', 'master', '-1', '--format=%s')).toBe('product');
  });

  it('on an instance branch already: commits there', () => {
    const d = repo();
    git(d, 'switch', '-qc', 'my-box');
    expect(commitInstance({ root: d, files: extend(d), message: 'm' })).toMatchObject({ committed: true, branch: 'my-box' });
  });

  it('commits only its own files', () => {
    const d = repo();
    writeFileSync(join(d, 'stray.txt'), 'not mine');
    commitInstance({ root: d, files: extend(d), message: 'm' });
    expect(git(d, 'status', '--porcelain')).toBe('?? stray.txt');
  });

  it('works without a git identity on the box', () => {
    const d = repo();
    git(d, 'config', '--unset', 'user.email');
    git(d, 'config', '--unset', 'user.name');
    const env = { ...process.env, GIT_CONFIG_GLOBAL: '/dev/null', GIT_CONFIG_NOSYSTEM: '1' };
    expect(commitInstance({ root: d, files: extend(d), message: 'm', env })).toMatchObject({ committed: true });
  });

  it('will not switch onto an existing instance branch with work in the tree — says what to do', () => {
    const d = repo();
    git(d, 'branch', INSTANCE_BRANCH);
    const out = commitInstance({ root: d, files: extend(d), message: 'm' });
    expect(out.committed).toBe(false);
    expect(out.reason).toContain(`git switch ${INSTANCE_BRANCH}`);
    expect(git(d, 'branch', '--show-current')).toBe('master');
  });

  it('outside a git checkout: nothing to commit, says so', () => {
    const d = mkdtempSync(join(tmpdir(), 'nogit-'));
    expect(commitInstance({ root: d, files: [], message: 'm' })).toMatchObject({ committed: false });
  });
});
