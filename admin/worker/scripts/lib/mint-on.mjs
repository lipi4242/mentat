// Mint a token ON the box that will use it. The secret never crosses zones:
//
//   1. this machine pipes src/lib/token-rules.mjs + a small driver over ssh
//      stdin into `node --input-type=module` on the target;
//   2. the target makes the token, writes the plaintext to --token-file
//      (O_EXCL, 0600, parent created 0700) and prints ONLY {id, hash, file};
//   3. this machine checks that answer and runs the same INSERT as
//      `mint-token --local|--remote` (buildMint in mint.mjs).
//
// Nothing here ever holds the plaintext, so nothing here can print it.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { buildMint, checkRequest } from './mint.mjs';
import { WORKER_DIR } from './d1.mjs';
import { runTool } from './tools.mjs';

const RULES = join(WORKER_DIR, 'src', 'lib', 'token-rules.mjs');

/** The program the target runs. token-rules must stay import-free. */
export function remoteScript(tokenFile) {
  const rules = readFileSync(RULES, 'utf8');
  if (/^\s*import\s/m.test(rules)) throw new Error('token-rules.mjs gained an import — it can no longer run alone on the target');
  return `${rules}
// ---- mint-on driver ----
import { closeSync, existsSync, fsyncSync, mkdirSync, openSync, writeSync } from 'node:fs';
import { dirname, isAbsolute } from 'node:path';
import { homedir } from 'node:os';
import { webcrypto } from 'node:crypto';
if (!globalThis.crypto) globalThis.crypto = webcrypto; // node < 19
const raw = ${JSON.stringify(tokenFile)};
const file = raw.startsWith('~/') ? homedir() + raw.slice(1) : raw;
const die = (m) => { process.stderr.write('mint-on: ' + m + '\\n'); process.exit(3); };
if (!isAbsolute(file)) die('--token-file must be absolute (or start with ~/): ' + raw);
if (existsSync(file)) die('token file already exists, nothing minted: ' + file);
mkdirSync(dirname(file), { recursive: true, mode: 0o700 });
const { id, plain, hash } = await newToken();
let fd;
try { fd = openSync(file, 'wx', 0o600); } catch (e) { die('cannot create ' + file + ': ' + e.message); }
writeSync(fd, plain + '\\n');
fsyncSync(fd);
closeSync(fd);
process.stdout.write(JSON.stringify({ id, hash, file }) + '\\n');
`;
}

/** The target's answer → {id, hash, file}. Anything else is refused. */
export function parseRemote(stdout) {
  const lines = String(stdout).split('\n').map((l) => l.trim()).filter(Boolean);
  if (lines.length !== 1) throw new Error(`target answered ${lines.length} lines, expected one JSON line`);
  let out;
  try {
    out = JSON.parse(lines[0]);
  } catch {
    throw new Error('target answer is not JSON');
  }
  if (!out || typeof out !== 'object' || Array.isArray(out)) throw new Error('target answer is not an object');
  const keys = Object.keys(out).sort().join(',');
  if (keys !== 'file,hash,id') throw new Error(`target answer has fields [${keys}], expected exactly id, hash, file`);
  if (Object.values(out).some((v) => typeof v !== 'string' || /mentat_[A-Za-z0-9_-]{20,}/.test(v))) {
    throw new Error('target answer carries a token-like value — refused, nothing written to the database');
  }
  if (!/^[0-9a-f-]{36}$/.test(out.id) || !/^[0-9a-f]{64}$/.test(out.hash)) throw new Error('target answer: bad id or hash');
  return out;
}

/** ssh argv (after the ssh binary) for a target. */
export function sshArgs(target, remoteNode = 'node') {
  if (!/^[A-Za-z0-9_.@:-]+$/.test(target)) throw new Error(`--on: not an ssh target: ${target}`);
  if (!/^[A-Za-z0-9_./~-]+$/.test(remoteNode)) throw new Error(`--remote-node: not a path: ${remoteNode}`);
  return ['-T', '-o', 'BatchMode=yes', target, `${remoteNode} --input-type=module`];
}

/**
 * Mint on `on`, insert through `queryMany`. → {id, label, scopes, expires_at, file}.
 * The request is validated before anything reaches the target.
 */
export async function mintOn(queryMany, request, { on, tokenFile, remoteNode, env = process.env, now = new Date() }) {
  checkRequest(request);
  if (!tokenFile) throw new Error('--on needs --token-file <path on the target>');
  const r = runTool('ssh', sshArgs(on, remoteNode), { input: remoteScript(tokenFile), env });
  if (r.status !== 0) throw new Error(`on ${on}: ${r.stderr.trim() || `exit ${r.status}`}`);
  const made = parseRemote(r.stdout);
  const { sql, ...minted } = buildMint(request, made, now);
  try {
    await queryMany([sql]);
  } catch (err) {
    throw new Error(`the token file was written on ${on} (${made.file}) but the database INSERT failed — delete that file: ${err instanceof Error ? err.message : err}`);
  }
  return { ...minted, file: made.file };
}
