// macOS: `connect --local` makes the local admin a launchd agent (RunAtLoad +
// KeepAlive), so it outlives the terminal and comes back when killed. No real
// LaunchAgent is loaded: a temp HOME, and launchctl is faked through `run`.
import { describe, it, expect } from 'vitest';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { LABEL, launchdState, logPath, nodeOfPlist, parsePrint, plistPath, renderPlist } from '../scripts/lib/launchd.mjs';
import { installService, uninstallService } from '../scripts/lib/local-admin.mjs';

const tmp = (p: string) => mkdtempSync(join(tmpdir(), p));
function fakeRun(answers: Record<string, { status?: number; stdout?: string }> = {}) {
  const calls: string[] = [];
  const run = (cmd: string, args: string[]) => {
    const key = [cmd, ...args].join(' ');
    calls.push(key);
    const hit = Object.keys(answers).find((k) => key.startsWith(k));
    return { status: hit ? answers[hit].status ?? 0 : 0, stdout: hit ? answers[hit].stdout ?? '' : '' };
  };
  return { run, calls };
}
const PRINT = `gui/501/${LABEL} = {\n\tactive count = 1\n\tstate = running\n\truns = 3\n\tpid = 4242\n\tlast exit code = 9: Killed\n}\n`;
const mac = (home: string, run: any) => ({ home, uid: 501, user: 'anna', workerDir: '/w', nodeBin: '/n/bin', port: 8787, run, platform: 'darwin' });

describe('renderPlist', () => {
  it('runs local-dev.mjs with an absolute node, at login, and keeps it alive', () => {
    const p = renderPlist({ workerDir: '/h/src/mentat/admin/worker', nodeBin: '/opt/homebrew/bin', port: 8787, log: '/h/Library/Logs/mentat-admin.log' });
    expect(p).toContain(`<key>Label</key>\n  <string>${LABEL}</string>`);
    expect(p).toContain('<string>/opt/homebrew/bin/node</string>\n    <string>/h/src/mentat/admin/worker/scripts/local-dev.mjs</string>\n    <string>--port</string>\n    <string>8787</string>');
    expect(p).toContain('<key>WorkingDirectory</key>\n  <string>/h/src/mentat/admin/worker</string>');
    expect(p).toMatch(/<key>RunAtLoad<\/key>\s*<true\/>/);
    expect(p).toMatch(/<key>KeepAlive<\/key>\s*<true\/>/);
    expect(p).toContain('<string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>');
    expect(p).toContain('<key>StandardErrorPath</key>\n  <string>/h/Library/Logs/mentat-admin.log</string>');
    expect(nodeOfPlist(p)).toBe('/opt/homebrew/bin/node');
  });

  it('escapes XML in paths', () => {
    expect(renderPlist({ workerDir: '/a&b/<w>', nodeBin: '/n', port: 1, log: '/l' })).toContain('<string>/a&amp;b/&lt;w&gt;</string>');
  });
});

describe('installService on macOS', () => {
  it('writes the plist and bootstraps it into the gui domain (no systemd asked)', () => {
    const home = tmp('home-');
    const { run, calls } = fakeRun({ 'launchctl bootout': { status: 3 } });
    const out = installService(mac(home, run));
    expect(out).toMatchObject({ installed: true, unitPath: plistPath(home) });
    expect(readFileSync(plistPath(home), 'utf8')).toContain('<string>8787</string>');
    expect(calls).toEqual([`launchctl bootout gui/501/${LABEL}`, `launchctl bootstrap gui/501 ${plistPath(home)}`]);
    expect(out.note).toMatch(/log in/);
  });

  it('fails loudly when launchd does not take it', () => {
    const { run } = fakeRun({ 'launchctl bootstrap': { status: 5 } });
    expect(() => installService(mac(tmp('home-'), run))).toThrow(/did not start.*launchctl bootstrap/);
  });

  it('Windows: nothing installed, and it says so', () => {
    const out = installService({ ...mac(tmp('home-'), fakeRun().run), platform: 'win32' });
    expect(out.installed).toBe(false);
    expect(out.reason).toMatch(/Windows/);
  });
});

describe('uninstallService on macOS', () => {
  it('boots it out and leaves no plist and no log behind', () => {
    const home = tmp('home-');
    installService(mac(home, fakeRun().run));
    mkdirSync(join(home, 'Library', 'Logs'), { recursive: true });
    writeFileSync(logPath(home), 'x');
    const { run, calls } = fakeRun();
    const out = uninstallService({ home, uid: 501, run, platform: 'darwin' });
    expect(calls).toEqual([`launchctl bootout gui/501/${LABEL}`]);
    expect(existsSync(plistPath(home))).toBe(false);
    expect(existsSync(logPath(home))).toBe(false);
    expect(out.removed).toEqual([plistPath(home), logPath(home)]);
  });

  it('is a no-op when nothing is installed', () => {
    expect(uninstallService({ home: tmp('home-'), uid: 501, run: fakeRun().run, platform: 'darwin' }).removed).toEqual([]);
  });
});

describe('launchdState', () => {
  it('reads state, pid and how many times launchd started it (a restart after a kill shows)', () => {
    expect(parsePrint(PRINT)).toEqual({ state: 'running', pid: 4242, runs: 3, lastExit: '9: Killed' });
    const home = tmp('home-');
    installService(mac(home, fakeRun().run));
    const s = launchdState({ home, uid: 501, run: fakeRun({ 'launchctl print': { stdout: PRINT } }).run, exists: () => true });
    expect(s).toMatchObject({ installed: true, state: 'running', runs: 3, node: '/n/bin/node', nodeOk: true, port: 8787 });
  });

  it('a plist whose node is gone (node upgrade) is reported, not hidden', () => {
    const home = tmp('home-');
    installService(mac(home, fakeRun().run));
    const s = launchdState({ home, uid: 501, run: fakeRun({ 'launchctl print': { status: 113 } }).run, exists: () => false });
    expect(s).toMatchObject({ installed: true, state: 'not loaded', nodeOk: false });
  });

  it('no plist → not installed', () => {
    expect(launchdState({ home: tmp('home-'), uid: 501, run: fakeRun().run }).installed).toBe(false);
  });
});
