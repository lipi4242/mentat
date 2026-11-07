// An instance's own extension — config/models.json and its 09NN migrations —
// is instance data that lives in the product checkout. Uncommitted, one
// `git reset`, `git stash` or `git clean` takes it away. So model:migration
// writes it 0644 and commits it on a LOCAL instance branch (never pushed):
// the product never writes models.json or the 900 band, so updating is a
// clean `git pull origin master` on that branch (agent/EXTENDING.md).
import { spawnSync } from 'node:child_process';
import { chmodSync, writeFileSync } from 'node:fs';

export const INSTANCE_BRANCH = 'peldany';
const PRODUCT_BRANCHES = ['master', 'main'];
const FALLBACK_IDENT = ['-c', 'user.name=mentat-admin', '-c', 'user.email=mentat-admin@localhost'];

/** Write a generated file 0644, whatever the umask (a box with umask 0 made them 0666). */
export function writeInstanceFile(path, body) {
  writeFileSync(path, body);
  chmodSync(path, 0o644);
}

/**
 * Commit `files` (repo-relative) in `root`. On a product branch it first
 * moves to INSTANCE_BRANCH (created at HEAD — the tree does not change).
 * → { committed: true, branch, sha } | { committed: false, reason }.
 */
export function commitInstance({ root, files, message, env = process.env }) {
  const git = (...a) => {
    const r = spawnSync('git', ['-C', root, ...a], { encoding: 'utf8', env });
    return { ok: r.status === 0, out: (r.stdout ?? '').trim(), err: (r.stderr ?? '').trim() };
  };
  if (!git('rev-parse', '--is-inside-work-tree').ok) {
    return { committed: false, reason: `${root} is not a git checkout — nothing committed` };
  }
  let branch = git('branch', '--show-current').out;
  if (!branch || PRODUCT_BRANCHES.includes(branch)) {
    if (git('rev-parse', '--verify', '--quiet', `refs/heads/${INSTANCE_BRANCH}`).ok) {
      return {
        committed: false,
        reason: `on ${branch || 'a detached HEAD'}, and the instance branch exists — run: git switch ${INSTANCE_BRANCH} ` +
          `(your change comes along), then: git add ${files.join(' ')} && git commit -m "${message}"`,
      };
    }
    const sw = git('switch', '-c', INSTANCE_BRANCH);
    if (!sw.ok) return { committed: false, reason: `git switch -c ${INSTANCE_BRANCH}: ${sw.err}` };
    branch = INSTANCE_BRANCH;
  }
  const add = git('add', '--', ...files);
  if (!add.ok) return { committed: false, reason: `git add: ${add.err}` };
  const ident = git('config', 'user.email').out ? [] : FALLBACK_IDENT;
  const commit = git(...ident, 'commit', '-q', '-m', message, '--', ...files);
  if (!commit.ok) return { committed: false, reason: `git commit: ${commit.err || commit.out}` };
  return { committed: true, branch, sha: git('rev-parse', '--short', 'HEAD').out };
}
