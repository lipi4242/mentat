// macOS twin of the systemd unit: a launchd agent in ~/Library/LaunchAgents
// that runs scripts/local-dev.mjs at login (RunAtLoad) and starts it again when
// it dies (KeepAlive). The node path is pinned into the plist, so a node
// upgrade can break it — launchdState reports that instead of hiding it.
// `run(cmd, args) → {status, stdout}` is injectable; the tests fake launchctl.
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

export const LABEL = 'com.mentat.admin';
export const plistPath = (home) => join(home, 'Library', 'LaunchAgents', `${LABEL}.plist`);
export const logPath = (home) => join(home, 'Library', 'Logs', 'mentat-admin.log');

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const str = (s) => `<string>${esc(s)}</string>`;
const unesc = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');

export function renderPlist({ workerDir, nodeBin, port, log }) {
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
    '<plist version="1.0">',
    '<dict>',
    `  <key>Label</key>\n  ${str(LABEL)}`,
    '  <key>ProgramArguments</key>',
    '  <array>',
    ...[`${nodeBin}/node`, `${workerDir}/scripts/local-dev.mjs`, '--port', port].map((a) => `    ${str(a)}`),
    '  </array>',
    `  <key>WorkingDirectory</key>\n  ${str(workerDir)}`,
    '  <key>EnvironmentVariables</key>',
    '  <dict>',
    `    <key>PATH</key>\n    ${str(`${nodeBin}:/usr/local/bin:/usr/bin:/bin`)}`,
    `    <key>WRANGLER_SEND_METRICS</key>\n    ${str('false')}`,
    '  </dict>',
    '  <key>RunAtLoad</key>\n  <true/>',
    '  <key>KeepAlive</key>\n  <true/>',
    '  <key>ThrottleInterval</key>\n  <integer>5</integer>',
    `  <key>StandardOutPath</key>\n  ${str(log)}`,
    `  <key>StandardErrorPath</key>\n  ${str(log)}`,
    '</dict>',
    '</plist>',
    '',
  ].join('\n');
}

const programArgs = (text) => {
  const block = /<key>ProgramArguments<\/key>\s*<array>([\s\S]*?)<\/array>/.exec(text ?? '');
  return block ? [...block[1].matchAll(/<string>([^<]*)<\/string>/g)].map((m) => unesc(m[1])) : [];
};
/** The node binary the plist runs, or null. */
export const nodeOfPlist = (text) => programArgs(text)[0] ?? null;
/** The --port the plist really runs on, or null. */
export function portOfPlist(text) {
  const a = programArgs(text);
  const i = a.indexOf('--port');
  return i >= 0 && a[i + 1] ? Number(a[i + 1]) : null;
}

/** Write the plist and (re)load it into the user's gui domain. */
export function installLaunchAgent({ home, uid, workerDir, nodeBin, port, run }) {
  const path = plistPath(home);
  mkdirSync(join(home, 'Library', 'LaunchAgents'), { recursive: true });
  mkdirSync(join(home, 'Library', 'Logs'), { recursive: true });
  writeFileSync(path, renderPlist({ workerDir, nodeBin, port, log: logPath(home) }));
  run('launchctl', ['bootout', `gui/${uid}/${LABEL}`]); // an older copy may be loaded; absent is fine
  if (run('launchctl', ['bootstrap', `gui/${uid}`, path]).status !== 0) {
    throw new Error(`${LABEL} did not start (launchctl bootstrap gui/${uid} ${path}) — see: ${logPath(home)}`);
  }
  return { installed: true, unitPath: path, note: 'launchd starts it when you log in and restarts it if it stops' };
}

/** Unload it and remove the plist and its log; nothing else is touched. */
export function uninstallLaunchAgent({ home, uid, run }) {
  const removed = [plistPath(home), logPath(home)].filter((p) => existsSync(p));
  if (existsSync(plistPath(home))) run('launchctl', ['bootout', `gui/${uid}/${LABEL}`]);
  for (const p of removed) rmSync(p, { force: true });
  return { removed };
}

/** `launchctl print` → the fields status shows. */
export function parsePrint(out) {
  const get = (k) => new RegExp(`^\\s*${k} = (.+)$`, 'm').exec(out ?? '')?.[1].trim();
  const num = (v) => (v === undefined ? null : Number(v));
  return { state: get('state') ?? 'unknown', pid: num(get('pid')), runs: num(get('runs')), lastExit: get('last exit code') ?? null };
}

export function launchdState({ home, uid, run, exists = existsSync }) {
  if (!existsSync(plistPath(home))) return { installed: false };
  const text = readFileSync(plistPath(home), 'utf8');
  const node = nodeOfPlist(text);
  const p = run('launchctl', ['print', `gui/${uid}/${LABEL}`]);
  const live = p.status === 0 ? parsePrint(p.stdout) : { state: 'not loaded', pid: null, runs: null, lastExit: null };
  return { installed: true, ...live, node, nodeOk: !!node && exists(node), port: portOfPlist(text) };
}
