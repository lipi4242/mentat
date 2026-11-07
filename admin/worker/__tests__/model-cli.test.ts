// `npm run model` (scripts/model.mjs): the request → models.json document.
// The assertions run the PRODUCT's validators on what the command produced,
// so a CLI that drifts from the worker's rules goes red here.
import { describe, it, expect } from 'vitest';
import { loadModels } from '../src/core/models';
import { fieldProblem, FIELD_TYPES } from '../src/core/fields';
import { modelSql, schemaOf } from '../src/lib/model-sql.mjs';
import { addField, newEntity, parseArgs, UsageError } from '../scripts/lib/model-spec.mjs';
import { badValue } from '../scripts/lib/model-probe.mjs';
import { makeDb } from './helpers';

const empty = () => ({ fields: {}, entities: [] }) as any;
const add = (m: any, argv: string[]) => {
  const a = parseArgs(['add-field', ...argv]);
  return addField(m, a.rest, a.flags);
};
const create = (m: any, argv: string[]) => {
  const a = parseArgs(['new', ...argv]);
  return newEntity(m, a.rest, a.flags, a.fields);
};

describe('add-field', () => {
  it('declares a non-negative amount on cases, valid for the worker, with the column in the migration', () => {
    const p = add(empty(), ['cases', 'osszeg', '--type', 'integer', '--min', '0', '--label', 'Összeg (Ft)']);
    expect(p.field).toEqual({ name: 'osszeg', label: 'Összeg (Ft)', type: 'integer', min: 0 });
    expect(p.slug).toBe('cases_osszeg');
    const models = loadModels(p.models);
    const { raw } = makeDb((f: string) => f < '0900');
    expect(modelSql(models, schemaOf(raw)).join('\n')).toMatch(/ALTER TABLE cases_case ADD COLUMN osszeg INTEGER/);
    expect(fieldProblem(p.field!, -500)).toMatch(/osszeg must be at least 0/);
  });

  it('is idempotent and refuses to redefine a field', () => {
    const once = add(empty(), ['cases', 'osszeg', '--type', 'integer', '--min', '0']);
    const again = add(once.models, ['cases', 'osszeg', '--type', 'integer', '--min', '0']);
    expect(again.changed).toBe(false);
    expect(() => add(once.models, ['cases', 'osszeg', '--type', 'text'])).toThrow(/already declared differently/);
  });

  it('adds a field to an own entity, and accepts the ugyek alias for cases', () => {
    const e = create(empty(), ['ugyfelek', '--field', 'nev:text:required']);
    const p = add(e.models, ['ugyfelek', 'telefon', '--type', 'text']);
    expect(p.models.entities[0].fields.map((f: any) => f.name)).toEqual(['nev', 'telefon']);
    expect(add(empty(), ['ugyek', 'x', '--type', 'text']).target.name).toBe('cases');
  });

  it.each([
    [['cases', 'x'], /needs --type/],
    [['cases', 'x', '--type', 'money'], /unknown type "money"/],
    [['cases', 'x', '--type', 'text', '--min', '0'], /min\/max does not apply to type text/],
    [['cases', 'x', '--type', 'select'], /needs options/],
    [['cases', 'x', '--type', 'ref'], /needs the entity/],
    [['cases', 'title', '--type', 'text'], /built-in field/],
    [['nincs', 'x', '--type', 'text'], /unknown model "nincs"/],
    [['cases', 'x', '--type', 'integer', '--min', 'sok'], /--min must be a number/],
    [['cases', 'X!', '--type', 'text'], /name must match/],
    [['cases', 'x', '--bogus', '1'], /unknown option --bogus/],
  ])('refuses %j', (argv, msg) => {
    expect(() => add(empty(), argv as string[])).toThrow(UsageError);
    expect(() => add(empty(), argv as string[])).toThrow(msg as RegExp);
  });

  it('every type the worker knows has a way to be declared (no type is left to a silent default)', () => {
    for (const t of FIELD_TYPES) {
      const extra = t === 'select' ? ['--options', 'a,b'] : t === 'ref' ? ['--ref', 'ugyfelek'] : [];
      const base = t === 'ref' ? create(empty(), ['ugyfelek', '--field', 'nev:text']).models : empty();
      expect(add(base, ['cases', 'f', '--type', t, ...extra]).field!.type).toBe(t);
    }
  });
});

describe('new', () => {
  it('declares a client and an invoice that points at it (--ref by prefix)', () => {
    const c = create(empty(), ['ugyfelek', '--label', 'Ügyfelek', '--field', 'nev:text:required', '--field', 'email:email']);
    const s = create(c.models, ['szamlak', '--label', 'Számlák', '--ref', 'ugyfel', '--field', 'osszeg:integer:min=0', '--field', 'esedekes:date']);
    const inv = s.models.entities[1];
    expect(inv.fields[2]).toMatchObject({ name: 'ugyfel', type: 'ref', ref: 'ugyfelek', required: true });
    const models = loadModels(s.models);
    const { raw } = makeDb((f: string) => f < '0900');
    expect(modelSql(models, schemaOf(raw)).join('\n')).toMatch(/CREATE TABLE custom_szamlak[\s\S]*REFERENCES custom_ugyfelek\(id\)/);
  });

  it.each([
    [['x'], /at least one --field/],
    [['x', '--field', 'nev'], /expected name:type/],
    [['x', '--field', 'nev:text:bogus'], /unknown part "bogus"/],
    [['x', '--field', 'nev:text', '--ref', 'senki'], /no such entity/],
    [['cases', '--field', 'nev:text'], /is taken/],
    [['meta', '--field', 'nev:text'], /is taken/],
  ])('refuses %j', (argv, msg) => {
    expect(() => create(empty(), argv as string[])).toThrow(msg as RegExp);
  });
});

describe('the invalid value the probe sends', () => {
  it('is refused by the worker validator for every type that has a rule', () => {
    const fields: any[] = [
      { name: 'a', label: 'a', type: 'integer', min: 0 }, { name: 'b', label: 'b', type: 'number', max: 5 },
      { name: 'c', label: 'c', type: 'integer' }, { name: 'd', label: 'd', type: 'date' },
      { name: 'e', label: 'e', type: 'email' }, { name: 'f', label: 'f', type: 'select', options: ['x'] },
      { name: 'g', label: 'g', type: 'checkbox' },
    ];
    for (const f of fields) expect(fieldProblem(f, badValue(f)), f.type).not.toBeNull();
  });
});
