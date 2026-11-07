// The agent-facing onboarding text and the idempotent steps in the agent repo.
import { describe, it, expect } from 'vitest';
import { mkdtempSync, readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { adminBlock, upsertBlock, whereLines, closingLines, BLOCK_START, BLOCK_END } from '../scripts/lib/onboard.mjs';
import { installCli, cliState, writeBlock, blockState, envValue } from '../scripts/lib/agent-setup.mjs';

const opts = { origin: 'http://localhost:8787/', dir: '~/mentat-admin/worker', local: true };

describe('adminBlock', () => {
  it('is at most 12 lines and names source of truth, commands, URLs and sign-in', () => {
    const b = adminBlock(opts);
    expect(b.split('\n').length).toBeLessThanOrEqual(12);
    expect(b).toContain('cases_cli show');
    expect(b).toContain('npm run model -- add-field');
    expect(b).toContain('npm run model -- new');
    expect(b).toContain('http://localhost:8787/ugyek');
    expect(b).toContain('http://localhost:8787/adatok/<model>');
    expect(b).toContain('npm run login-link');
    expect(b).toContain('npm run where');
  });
  it('says what an offline admin does, where the user clicks, and to quote the admin\'s own answer', () => {
    const b = adminBlock(opts);
    expect(b).toMatch(/exit 3.*nothing written.*no queue/);
    expect(b).toContain('Saját adatok');
    expect(b).toMatch(/admin'?s? (own )?answer|admin answer/);
    expect(b).toContain('npm run model -- --help');
    expect(b.split('\n').length).toBeLessThanOrEqual(12);
    expect(adminBlock({ ...opts, cases: false })).not.toContain('exit 3');
  });
  it('leaves the cases lines out when the cases plugin is not bound', () => {
    expect(adminBlock({ ...opts, cases: false })).not.toContain('cases_cli');
  });
});

describe('upsertBlock', () => {
  it('appends at the END, keeps the top byte for byte, and replaces on a second run', () => {
    const top = '# Agent\n\nStable rules.\n';
    const once = upsertBlock(top, adminBlock(opts));
    expect(once.startsWith(top)).toBe(true);
    expect(once.trimEnd().endsWith(BLOCK_END)).toBe(true);
    const twice = upsertBlock(once, adminBlock({ ...opts, origin: 'http://localhost:9000' }));
    expect(twice.split(BLOCK_START).length).toBe(2);
    expect(twice).toContain(':9000/ugyek');
    expect(twice).not.toContain(':8787');
    expect(twice.startsWith(top)).toBe(true);
  });
});

describe('whereLines', () => {
  const models = {
    fields: { cases: [{ name: 'osszeg', label: 'Összeg', type: 'number' }] },
    entities: [{ name: 'ugyfelek', label: 'Ügyfelek', fields: [{ name: 'nev', label: 'Név', type: 'text' }] }],
  };
  it('lists every model with fields and list/form URL', () => {
    const out = whereLines({ origin: 'http://localhost:8787', models, local: true, owners: ['a@example.com'] }).join('\n');
    expect(out).toContain('cases    list http://localhost:8787/ugyek');
    expect(out).toContain('osszeg (number)');
    expect(out).toContain('ugyfelek list http://localhost:8787/adatok/ugyfelek');
    expect(out).toContain('nev (text)');
    expect(out).toContain('a@example.com');
  });
  it('says so when there are no own models', () => {
    expect(whereLines({ origin: 'http://x:1', models: { fields: {}, entities: [] }, local: true }).join('\n')).toContain('no own data models yet');
  });
});

describe('closingLines', () => {
  it('says done / next / sign in / where in a few lines', () => {
    const out = closingLines({ origin: 'http://localhost:8787', dir: '~/ma/worker', local: true, cases: true, nextSteps: ['migrate'] });
    expect(out.join('\n')).toMatch(/done:[\s\S]*next: migrate[\s\S]*sign in:[\s\S]*\/ugyek/);
    expect(out.length).toBeLessThanOrEqual(7);
  });
});

describe('agent repo steps', () => {
  const repo = () => mkdtempSync(join(tmpdir(), 'agent-'));
  it('installCli copies once, then reports current; a changed copy is replaced', () => {
    const r = repo();
    expect(cliState(r)).toBe('missing');
    expect(installCli(r)).toBe('installed');
    expect(existsSync(join(r, '.mentat/bin/cases_cli/__main__.py'))).toBe(true);
    expect(installCli(r)).toBe('current');
    writeFileSync(join(r, '.mentat/bin/cases_cli/__main__.py'), '# old');
    expect(cliState(r)).toBe('stale');
    expect(installCli(r)).toBe('updated');
    expect(cliState(r)).toBe('current');
  });
  it('writeBlock creates AGENTS.md, then is current, then updates when the URL changes', () => {
    const r = repo();
    mkdirSync(r, { recursive: true });
    writeFileSync(join(r, 'AGENTS.md'), '# Brain\n');
    expect(writeBlock(r, opts)).toBe('added');
    expect(writeBlock(r, opts)).toBe('current');
    expect(blockState(r, { ...opts, origin: 'http://localhost:9' }).state).toBe('stale');
    expect(writeBlock(r, { ...opts, origin: 'http://localhost:9' })).toBe('updated');
    expect(readFileSync(join(r, 'AGENTS.md'), 'utf8').startsWith('# Brain\n')).toBe(true);
  });
  it('envValue reads one key', () => {
    const r = repo();
    writeFileSync(join(r, '.env'), 'A=1\nMENTAT_ADMIN_TOKEN=abc\n');
    expect(envValue(r, 'MENTAT_ADMIN_TOKEN')).toBe('abc');
    expect(envValue(r, 'NOPE')).toBe('');
  });
});
