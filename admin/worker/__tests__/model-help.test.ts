// `npm run model -- --help`: the whole syntax in one read, so the agent never
// opens scripts/model.mjs or model-spec.mjs to learn it (mérés 13/14).
import { describe, it, expect } from 'vitest';
import { FIELD_TYPES } from '../src/core/fields';
import { helpText, helpTopic } from '../scripts/lib/model-help.mjs';
import { parseArgs, newEntity } from '../scripts/lib/model-spec.mjs';
import { usage } from '../scripts/lib/model-report.mjs';

describe('help', () => {
  it('names every field type the worker knows, the field-spec parts and a working example', () => {
    const t = helpText();
    for (const type of FIELD_TYPES) expect(t, type).toContain(type);
    for (const part of [':required', ':min=', ':max=', ':label=', ':options=', ':ref=', '--ref', '--label', '--check', '--repo']) expect(t, part).toContain(part);
    expect(t).toMatch(/npm run model -- new \S+ .*--field \S+:\S+/);
  });

  it('every example in the help is accepted by the real parser', () => {
    const t = helpText();
    const lines = t.split('\n').filter((l) => /^\s+npm run model -- new /.test(l));
    expect(lines.length).toBeGreaterThan(0);
    let models = { fields: {}, entities: [] } as any;
    for (const l of lines) {
      const argv = l.trim().replace(/^npm run model -- /, '').match(/"[^"]*"|\S+/g)!.map((s) => s.replace(/^"|"$/g, ''));
      const a = parseArgs(argv);
      expect(() => { models = newEntity(models, a.rest, a.flags, a.fields).models; }, l).not.toThrow();
    }
  });

  it('knows the help flags and the per-command topics', () => {
    expect(parseArgs(['new', '--help']).flags.help).toBe(true);
    expect(helpTopic(['--help'])).toBe('all');
    expect(helpTopic([])).toBe('all');
    expect(helpTopic(['-h'])).toBe('all');
    expect(helpTopic(['new', '--help'])).toBe('new');
    expect(helpTopic(['add-field', '--help'])).toBe('add-field');
    expect(helpTopic(['new', 'x'])).toBeNull();
    expect(helpText('add-field')).toContain('--type');
    expect(helpText('add-field').length).toBeLessThan(helpText('all').length);
  });
});

describe('closing lines', () => {
  const models = { fields: {}, entities: [{ name: 'ugyfelek', label: 'Ügyfelek', fields: [] }] } as any;
  const plan = { target: { name: 'ugyfelek', label: 'Ügyfelek' }, field: null } as any;

  it('names the menu item and carries the ready sign-in link', () => {
    const l = usage('http://localhost:8787', models, plan, undefined, false, { login: 'http://localhost:8787/api/local-login/abc', widened: 'x' }).join('\n');
    expect(l).toContain('Saját adatok → Ügyfelek');
    expect(l).toContain('http://localhost:8787/api/local-login/abc');
    expect(l).toContain('x');
  });

  it('tells the agent to report the admin\'s own answer to a refused value', () => {
    const l = usage('http://localhost:8787', models, plan, undefined, false, {}).join('\n');
    expect(l).toMatch(/admin (válasz|answer)/i);
  });
});
