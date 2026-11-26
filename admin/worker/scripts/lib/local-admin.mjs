// What `connect --local` adds so a local admin outlives the shell it was
// started from: node/npm/npx on the login PATH (~/.local/bin), and a systemd
// user unit that runs scripts/local-dev.mjs (wrangler dev: API + built UI on
// one port) at boot (with linger, also before login). On macOS the same job is
// a launchd agent (lib/launchd.mjs); Windows has neither and says so.
// `run(cmd, args) → {status, stdout}` is injectable; the tests fake it.
import { spawnSync } from 'node:child_process';
import { existsSync, lstatSync, mkdirSync, rmSync, symlinkSync, unlinkSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { installLaunchAgent, uninstallLaunchAgent } from './launchd.mjs';

export const UNIT = 'mentat-admin.service';
const SYSTEM_BINS = ['/usr/bin', '/usr/local/bin', '/bin'];
const LOOPBACK = ['localhost', '127.0.0.1', '[::1]'];
const LOGIN_PATH = fileURLToPath(new URL('../login-path.sh', import.meta.url));

export const defaultRun = (cmd, args) => {
  const r = spawnSync(cmd, args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  return { status: r.error ? 127 : r.status, stdout: r.stdout ?? '' };
};

/** The port of a local admin URL; it must be loopback and name its port. */
export function localPort(url) {
  const u = new URL(url);
  if (!LOOPBACK.includes(u.hostname)) throw new Error(`--local needs a localhost URL, got ${url}`);
  if (!u.port) throw new Error(`--local needs the port in --url, e.g. http://localhost:8787`);
  return Number(u.port);
}

/**
 * Symlink node, npm and npx from `nodeBin` into ~/.local/bin and make sure
 * the login shell's profile puts that dir on PATH (scripts/login-path.sh:
 * ~/.profile, plus ~/.zprofile for zsh or ~/.bash_profile for bash). A node already in a system dir needs
 * nothing; a real (non-symlink) file in ~/.local/bin is never replaced.
 */
export function linkNode({ home, nodeBin, shell = process.env.SHELL ?? '' }) {
  const linked = [];
  const skipped = [];
  if (SYSTEM_BINS.includes(nodeBin)) return { linked, skipped, profiles: [] };
  const dir = join(home, '.local', 'bin');
  mkdirSync(dir, { recursive: true });
  for (const b of ['node', 'npm', 'npx']) {
    const dst = join(dir, b);
    let st = null;
    try {
      st = lstatSync(dst);
    } catch {}
    if (st && !st.isSymbolicLink()) {
      skipped.push(b);
      continue;
    }
    if (st) unlinkSync(dst);
    symlinkSync(join(nodeBin, b), dst);
    linked.push(b);
  }
  const r = spawnSync('sh', [LOGIN_PATH], { encoding: 'utf8', env: { ...process.env, HOME: home, SHELL: shell } });
  if (r.status !== 0) throw new Error(`login-path.sh failed: ${(r.stderr || '').trim()}`);
  return { linked, skipped, profiles: r.stdout.trim().split('\n').filter(Boolean) };
}

export function renderUnit({ workerDir, nodeBin, port }) {
  return [
    '[Unit]',
    `Description=Mentat Admin, local (admin UI + API on http://localhost:${port})`,
    'After=network.target',
    '',
    '[Service]',
    `WorkingDirectory=${workerDir}`,
    `Environment=PATH=${nodeBin}:/usr/local/bin:/usr/bin:/bin`,
    'Environment=WRANGLER_SEND_METRICS=false',
    `ExecStart=${nodeBin}/node ${workerDir}/scripts/local-dev.mjs --port ${port}`,
    'Restart=always',
    'RestartSec=5',
    '',
    '[Install]',
    'WantedBy=default.target',
    '',
  ].join('\n');
}

const unitFile = (home) => join(home, '.config', 'systemd', 'user', UNIT);

/**
 * macOS: a launchd agent (lib/launchd.mjs). Elsewhere: write
 * ~/.config/systemd/user/mentat-admin.service, enable and (re)start it, and
 * turn on linger so it starts at boot without a login. Windows, or no systemd
 * user manager (a container) → `installed: false` + reason.
 */
export function installService({ home, uid, user, workerDir, nodeBin, port, run = defaultRun, platform = process.platform }) {
  if (platform === 'darwin') return installLaunchAgent({ home, uid, workerDir, nodeBin, port, run });
  if (platform === 'win32') {
    return { installed: false, reason: `Windows is not supported as a service — the admin runs only while "npm run dev:local -- --port ${port}" runs in worker/` };
  }
  if (run('systemctl', ['--user', 'show-environment']).status !== 0) {
    return { installed: false, reason: `no systemd user manager here — the admin will not start on its own; run "npm run dev:local -- --port ${port}" in worker/ yourself` };
  }
  const unitPath = unitFile(home);
  mkdirSync(join(home, '.config', 'systemd', 'user'), { recursive: true });
  writeFileSync(unitPath, renderUnit({ workerDir, nodeBin, port }));
  for (const args of [['daemon-reload'], ['enable', UNIT], ['restart', UNIT]]) {
    if (run('systemctl', ['--user', ...args]).status !== 0) {
      throw new Error(`${UNIT} did not start (systemctl --user ${args.join(' ')}) — see: journalctl --user -u ${UNIT}`);
    }
  }
  let linger = run('loginctl', ['show-user', user, '--property=Linger', '--value']).stdout.trim() === 'yes';
  if (!linger) linger = run('loginctl', ['enable-linger', user]).status === 0;
  const hint = linger ? undefined : `without linger the admin starts only after you log in; fix: sudo loginctl enable-linger ${user}`;
  return { installed: true, unitPath, linger, hint };
}

/** Stop the service and remove what installService wrote (plist + log, or the unit). */
export function uninstallService({ home, uid, run = defaultRun, platform = process.platform }) {
  if (platform === 'darwin') return uninstallLaunchAgent({ home, uid, run });
  if (!existsSync(unitFile(home))) return { removed: [] };
  run('systemctl', ['--user', 'disable', '--now', UNIT]);
  rmSync(unitFile(home), { force: true });
  run('systemctl', ['--user', 'daemon-reload']);
  return { removed: [unitFile(home)] };
}

/** Poll <origin>/api/health until it answers ok (wrangler dev takes a few seconds). */
export async function waitHealthy(origin, { timeoutMs = 60000, fetchFn = fetch } = {}) {
  const until = Date.now() + timeoutMs;
  while (Date.now() < until) {
    try {
      const r = await fetchFn(`${origin}/api/health`);
      if (r.ok && (await r.json()).ok === true) return true;
    } catch {}
    await new Promise((res) => setTimeout(res, 1000));
  }
  return false;
}
