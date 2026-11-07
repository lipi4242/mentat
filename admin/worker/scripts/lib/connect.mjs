// Bind an agent repo to this admin (LG1): the token's value goes to the
// agent's .env (0600, must be gitignored), the admin URL and the env var's
// NAME to .mentat/local.json `admin`, and `components.admin` to mentat.json.
// The token is never printed and never returned.
import { execFileSync } from 'node:child_process';
import { chmodSync, existsSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { isIP } from 'node:net';
import { join } from 'node:path';
import { checkMint } from '../../src/lib/token-rules.mjs';
import { assertKnownSchema, mergeSection, readJson, withLock, writeJsonAtomic } from './manifest.mjs';

const ENV_NAME_RE = /^[A-Z][A-Z0-9_]*$/;
const PLUGIN_RE = /^[a-z0-9_-]+$/;
const LOOPBACK = ['127.0.0.1', '::1'];

/** True when git would not track `rel` (or `repo` is not a git work tree at all). */
export function gitIgnores(repo, rel) {
  try {
    execFileSync('git', ['-C', repo, 'rev-parse', '--is-inside-work-tree'], { stdio: 'ignore' });
  } catch {
    return true;
  }
  try {
    execFileSync('git', ['-C', repo, 'check-ignore', '-q', rel], { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

/** Contract rule 3: a hostname, not an IP address (loopback excepted, for local dev). */
export function checkUrl(url) {
  let u;
  try {
    u = new URL(url);
  } catch {
    throw new Error(`not a URL: ${url}`);
  }
  if (!['http:', 'https:'].includes(u.protocol)) throw new Error(`admin URL must be http(s): ${url}`);
  const host = u.hostname.replace(/^\[|\]$/g, '');
  if (isIP(host) && !LOOPBACK.includes(host)) throw new Error(`admin URL must use a hostname, not an IP address: ${url}`);
  return u.origin;
}

/** Set KEY=value in a dotenv file, keeping every other line. 0600, atomic. */
export function upsertEnv(path, key, value) {
  const lines = existsSync(path) ? readFileSync(path, 'utf8').split('\n') : [];
  if (lines.at(-1) === '') lines.pop();
  const i = lines.findIndex((l) => l.startsWith(`${key}=`));
  if (i >= 0) lines[i] = `${key}=${value}`;
  else lines.push(`${key}=${value}`);
  const tmp = `${path}.${process.pid}.tmp`;
  writeFileSync(tmp, lines.join('\n') + '\n', { mode: 0o600 });
  chmodSync(tmp, 0o600);
  renameSync(tmp, path);
}

/**
 * `mintFn(request) → {id, token, label, scopes, expires_at}` mints in the
 * admin's database (scripts/lib/mint.mjs in the CLI, a fake in the tests).
 * Everything that can be checked is checked before minting; a failure after
 * the mint names the token id so it can be revoked.
 */
export async function connect({ repo, url, tokenEnv = 'MENTAT_ADMIN_TOKEN', agent, scopes = 'cases:write', days, plugins, mintFn, ignores = gitIgnores }) {
  const origin = checkUrl(url);
  if (!ENV_NAME_RE.test(tokenEnv)) throw new Error(`invalid env var name: ${tokenEnv}`);
  if (plugins && plugins.some((p) => !PLUGIN_RE.test(p))) throw new Error(`invalid plugin id in ${plugins.join(',')}`);
  for (const rel of ['.env', '.mentat/local.json']) {
    if (!ignores(repo, rel)) throw new Error(`${rel} is not gitignored in ${repo} — refusing to write a secret or machine fact where git would pick it up`);
  }
  const mentatPath = join(repo, 'mentat.json');
  const localPath = join(repo, '.mentat', 'local.json');

  return withLock(repo, async () => {
    const doc = readJson(mentatPath);
    if (doc === null) throw new Error(`no mentat.json in ${repo} — the brain's installer creates it; connect only adds components.admin`);
    assertKnownSchema(doc, mentatPath);
    const local = readJson(localPath);
    assertKnownSchema(local, localPath);
    const request = { label: agent ?? doc.agent?.name, scopes, ...(days !== undefined ? { days } : {}) };
    const checked = checkMint(request);
    if ('error' in checked) throw new Error(checked.error);

    const minted = await mintFn(request);
    try {
      upsertEnv(join(repo, '.env'), tokenEnv, minted.token);
      writeJsonAtomic(localPath, mergeSection(local ?? { schema: 1 }, ['admin'], { url: origin, token_env: tokenEnv }));
      writeJsonAtomic(mentatPath, mergeSection(doc, ['components', 'admin'], plugins ? { plugins } : {}));
    } catch (e) {
      throw new Error(`token ${minted.id} was minted but the repo was not fully bound (${e.message}) — revoke it: npm run revoke-token -- --id ${minted.id}`);
    }
    const { token: _secret, ...rest } = minted;
    return { ...rest, url: origin, tokenEnv, envFile: join(repo, '.env') };
  });
}
