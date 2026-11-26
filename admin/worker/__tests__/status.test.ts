// `npm run status`: what an agent may quote about the local admin.
import { describe, it, expect } from 'vitest';
import { formatStatus, pendingMigrations, portOfUnit } from '../scripts/lib/status.mjs';

const facts = {
  url: 'http://localhost:8787',
  unit: 'active',
  port: 8787,
  health: true,
  ui: true,
  version: '0.1.0',
  commit: '51d9c95',
  branch: 'peldany',
  dirty: 0,
  migrations: { applied: ['0001_auth.sql', '0002_core.sql'], pending: [] },
  tokens: [{ id: 'tok-1', label: 'agent1', scopes: 'cases:write', expires_at: '2027-01-13T10:00:00Z', last_used_at: '2026-10-15 21:00:00' }],
  owners: ['anna@example.com'],
};

describe('formatStatus', () => {
  it('says the real URL, commit, migrations and token scopes', () => {
    const out = formatStatus(facts);
    expect(out).toContain('url:        http://localhost:8787  (admin UI + API)');
    expect(out).toContain('service:    mentat-admin.service active, port 8787');
    expect(out).toContain('commit 51d9c95 (peldany)');
    expect(out).toContain('migrations: 2 applied, 0 pending');
    expect(out).toContain('agent1  cases:write  expires 2027-01-13');
    expect(out).toContain('id tok-1'); // revoke-token --id needs it
    expect(out).toContain('sign in:    anna@example.com — npm run login-link');
  });

  it('names what is wrong and the command that fixes it', () => {
    const out = formatStatus({
      ...facts,
      unit: 'inactive',
      port: 9000,
      health: false,
      ui: false,
      dirty: 2,
      migrations: { applied: ['0001_auth.sql'], pending: ['0900_cases_osszeg.sql'] },
      tokens: [],
    });
    expect(out).toMatch(/health:\s+DOWN/);
    expect(out).toMatch(/port 9000 ≠ the URL's 8787/);
    expect(out).toContain('ui:         NOT served');
    expect(out).toContain('2 uncommitted file(s)');
    expect(out).toContain('pending: 0900_cases_osszeg.sql — run: npm run migrate:local');
    expect(out).toContain('tokens:     none active');
  });
});

describe('formatStatus on macOS (launchd)', () => {
  const mac = { ...facts, manager: 'launchd', unit: 'running', runs: 3, node: '/opt/homebrew/bin/node', nodeOk: true };

  it('names the launchd agent and how often launchd has started it', () => {
    const out = formatStatus(mac);
    expect(out).toContain('service:    launchd agent com.mentat.admin running, port 8787, started 3× (KeepAlive restarts it)');
    expect(out).not.toContain('systemctl');
  });

  it('says plainly when the node in the plist is gone', () => {
    const out = formatStatus({ ...mac, unit: 'not loaded', nodeOk: false, health: false });
    expect(out).toContain('node /opt/homebrew/bin/node is gone (node upgraded or moved?) — rerun connect --local');
    expect(out).toMatch(/health:\s+DOWN — see ~\/Library\/Logs\/mentat-admin.log/);
  });

  it('no plist → how to install it', () => {
    expect(formatStatus({ ...facts, manager: 'launchd', unit: 'none' })).toContain('not installed (no launchd agent) — npm run connect -- --local');
  });
});

describe('pendingMigrations', () => {
  it('is the files the database has not applied, in order', () => {
    expect(pendingMigrations(['0002_b.sql', '0001_a.sql', '0900_c.sql'], ['0001_a.sql'])).toEqual(['0002_b.sql', '0900_c.sql']);
  });
});

describe('portOfUnit', () => {
  it('reads the port the unit really runs on', () => {
    expect(portOfUnit('ExecStart=/n/node /w/scripts/local-dev.mjs --port 9000\n')).toBe(9000);
    expect(portOfUnit('ExecStart=/n/node wrangler.js dev --ip 127.0.0.1 --port 8787\n')).toBe(8787);
    expect(portOfUnit('')).toBeNull();
  });
});
