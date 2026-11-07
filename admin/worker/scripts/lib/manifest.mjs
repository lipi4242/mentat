// mentat.json + .mentat/local.json, the admin's side of the shared contract
// (LG1). Node counterpart of the reference mentat_manifest.py, same rules:
//
//  - rule 1, own keys only: the admin writes `components.admin` in
//    mentat.json and `admin` in .mentat/local.json, nothing else; unknown
//    fields inside its own section survive the merge;
//  - rule 2, locked writes: an exclusive fcntl.flock on .mentat/lock around
//    read → merge → tmp + rename. Node has no flock, and the Python writers
//    use a real one, so the lock is held by a tiny python3 helper — the same
//    syscall, so Node and Python writers exclude each other;
//  - rule 6, unknown (newer) schema → diagnostics only, nothing written;
//  - rule 7, unknown keys are tolerated.
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';

export const KNOWN_SCHEMA = 1;

const LOCK_HELPER = [
  'import fcntl, os, sys',
  'fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o600)',
  'fcntl.flock(fd, fcntl.LOCK_EX)',
  "sys.stdout.write('locked\\n'); sys.stdout.flush()",
  'sys.stdin.read()',
].join('\n');

/** Run `fn` while holding the exclusive lock on <repo>/.mentat/lock. */
export async function withLock(repo, fn) {
  mkdirSync(join(repo, '.mentat'), { recursive: true });
  const child = spawn('python3', ['-c', LOCK_HELPER, join(repo, '.mentat', 'lock')], {
    stdio: ['pipe', 'pipe', 'inherit'],
  });
  const exited = new Promise((res) => child.once('exit', res));
  await new Promise((resolve, reject) => {
    child.once('error', (e) => reject(new Error(`python3 is needed to hold .mentat/lock (fcntl.flock): ${e.message}`)));
    child.stdout.once('data', (d) => (String(d).startsWith('locked') ? resolve() : reject(new Error('lock helper failed'))));
    exited.then((code) => reject(new Error(`lock helper exited (${code}) before locking`)));
  });
  try {
    return await fn();
  } finally {
    child.stdin.end();
    await exited;
  }
}

/** Parsed JSON, or null when the file does not exist. */
export function readJson(path) {
  if (!existsSync(path)) return null;
  try {
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch (e) {
    throw new Error(`${path}: not valid JSON (${e.message})`);
  }
}

/** Rule 6: a newer schema than this reader knows means hands off. */
export function assertKnownSchema(doc, path) {
  if (doc === null) return;
  if (typeof doc !== 'object' || Array.isArray(doc)) throw new Error(`${path}: not a JSON object`);
  const s = doc.schema;
  if (!Number.isInteger(s) || s < 1) throw new Error(`${path}: missing or invalid "schema"`);
  if (s > KNOWN_SCHEMA) {
    throw new Error(`${path}: schema ${s} is newer than this admin knows (${KNOWN_SCHEMA}) — diagnostics only, nothing written`);
  }
}

/** Merge `data` into the section at `keyPath`, leaving everything else as it was. */
export function mergeSection(doc, keyPath, data) {
  const out = structuredClone(doc);
  let node = out;
  for (const k of keyPath.slice(0, -1)) {
    if (node[k] === undefined) node[k] = {};
    if (typeof node[k] !== 'object' || node[k] === null || Array.isArray(node[k])) {
      throw new Error(`"${keyPath.join('.')}": "${k}" is not an object`);
    }
    node = node[k];
  }
  const last = keyPath.at(-1);
  const existing = node[last];
  if (existing !== undefined && (typeof existing !== 'object' || existing === null || Array.isArray(existing))) {
    throw new Error(`"${keyPath.join('.')}" is not an object`);
  }
  node[last] = { ...(existing ?? {}), ...data };
  return out;
}

/** tmp + rename in the same directory: a reader sees the old file or the new one. */
export function writeJsonAtomic(path, doc) {
  const tmp = join(dirname(path), `.${process.pid}.${Date.now()}.tmp`);
  writeFileSync(tmp, JSON.stringify(doc, null, 2) + '\n');
  renameSync(tmp, path);
}
