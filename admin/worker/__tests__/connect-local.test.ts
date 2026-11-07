// `connect --local` makes a local admin durable: node on the login PATH, a
// systemd user unit that starts wrangler dev at boot. Everything runs against
// a temp HOME; systemctl/loginctl are faked through `run`.
import { describe, it, expect } from 'vitest';
import { existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, readlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { installService, linkNode, localPort, renderUnit } from '../scripts/lib/local-admin.mjs';

const tmp = (p: string) => mkdtempSync(join(tmpdir(), p));
function nodeDir() {
  const d = tmp('node-');
  mkdirSync(join(d, 'bin'));
  for (const b of ['node', 'npm', 'npx']) writeFileSync(join(d, 'bin', b), '#!/bin/sh\n', { mode: 0o755 });
  return join(d, 'bin');
}
type Call = string[];
function fakeRun(answers: Record<string, number> = {}) {
  const calls: Call[] = [];
  const run = (cmd: string, args: string[]) => {
    calls.push([cmd, ...args]);
    const key = [cmd, ...args].join(' ');
    const hit = Object.keys(answers).find((k) => key.startsWith(k));
    const status = hit ? answers[hit] : 0;
    return { status, stdout: key.includes('Linger') ? 'no\n' : '' };
  };
  return { run, calls };
}

describe('localPort', () => {
  it('needs a loopback URL with an explicit port', () => {
    expect(localPort('http://localhost:8787')).toBe(8787);
    expect(localPort('http://127.0.0.1:9000/')).toBe(9000);
    expect(() => localPort('http://localhost')).toThrow(/port/);
    expect(() => localPort('https://admin.example.com:8787')).toThrow(/localhost/);
  });
});

describe('linkNode', () => {
  it('links node, npm and npx into ~/.local/bin and puts that dir on the login PATH', () => {
    const home = tmp('home-');
    const bin = nodeDir();
    const out = linkNode({ home, nodeBin: bin });
    for (const b of ['node', 'npm', 'npx']) {
      expect(lstatSync(join(home, '.local/bin', b)).isSymbolicLink()).toBe(true);
      expect(readlinkSync(join(home, '.local/bin', b))).toBe(join(bin, b));
    }
    expect(readFileSync(join(home, '.profile'), 'utf8')).toContain('$HOME/.local/bin');
    expect(out.linked).toEqual(['node', 'npm', 'npx']);
    // Idempotent: a second run does not add a second PATH line.
    linkNode({ home, nodeBin: bin });
    expect(readFileSync(join(home, '.profile'), 'utf8').match(/PATH="\$HOME\/\.local\/bin/g)!.length).toBe(1);
  });

  it('leaves a system node alone and never replaces a real file', () => {
    const home = tmp('home-');
    expect(linkNode({ home, nodeBin: '/usr/bin' }).linked).toEqual([]);
    expect(existsSync(join(home, '.local/bin/node'))).toBe(false);
    mkdirSync(join(home, '.local/bin'), { recursive: true });
    writeFileSync(join(home, '.local/bin/node'), 'mine');
    const out = linkNode({ home, nodeBin: nodeDir() });
    expect(readFileSync(join(home, '.local/bin/node'), 'utf8')).toBe('mine');
    expect(out.skipped).toEqual(['node']);
  });
});

describe('renderUnit', () => {
  it('runs the API and the built UI on one port with an absolute node, restarts, starts at boot', () => {
    const u = renderUnit({ workerDir: '/srv/svc/mentat-admin/worker', nodeBin: '/srv/svc/.local/node/bin', port: 8787 });
    expect(u).toContain('WorkingDirectory=/srv/svc/mentat-admin/worker');
    expect(u).toContain('ExecStart=/srv/svc/.local/node/bin/node /srv/svc/mentat-admin/worker/scripts/local-dev.mjs --port 8787');
    expect(u).toContain('admin UI + API on http://localhost:8787');
    expect(u).toContain('Environment=PATH=/srv/svc/.local/node/bin:');
    expect(u).toMatch(/Restart=always/);
    expect(u).toContain('WantedBy=default.target');
  });
});

describe('installService', () => {
  const opts = (home: string, run: any) => ({ home, user: 'anna', workerDir: '/w', nodeBin: '/n', port: 8787, run });

  it('writes the unit, enables it now and turns on linger', () => {
    const home = tmp('home-');
    const { run, calls } = fakeRun();
    const out = installService(opts(home, run));
    expect(out).toMatchObject({ installed: true, linger: true });
    expect(readFileSync(join(home, '.config/systemd/user/mentat-admin.service'), 'utf8')).toContain('--port 8787');
    const cmds = calls.map((c) => c.join(' '));
    expect(cmds).toContain('systemctl --user daemon-reload');
    expect(cmds).toContain('systemctl --user enable mentat-admin.service');
    expect(cmds).toContain('systemctl --user restart mentat-admin.service');
    expect(cmds).toContain('loginctl enable-linger anna');
  });

  it('without a systemd user manager it installs nothing and says why', () => {
    const home = tmp('home-');
    const { run } = fakeRun({ 'systemctl --user show-environment': 1 });
    const out = installService(opts(home, run));
    expect(out.installed).toBe(false);
    expect(out.reason).toMatch(/systemd/);
    expect(existsSync(join(home, '.config/systemd/user/mentat-admin.service'))).toBe(false);
  });

  it('reports linger it could not turn on, with the command that fixes it', () => {
    const { run } = fakeRun({ 'loginctl enable-linger': 1 });
    const out = installService(opts(tmp('home-'), run));
    expect(out).toMatchObject({ installed: true, linger: false });
    expect(out.hint).toContain('sudo loginctl enable-linger anna');
  });

  it('fails loudly when the unit does not start', () => {
    const { run } = fakeRun({ 'systemctl --user restart': 1 });
    expect(() => installService(opts(tmp('home-'), run))).toThrow(/mentat-admin.service did not start/);
  });
});
