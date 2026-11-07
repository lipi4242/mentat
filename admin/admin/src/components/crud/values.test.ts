import { describe, it, expect } from 'vitest';
import { normalizeValues } from './values';

const fields = [
  { name: 'title', label: 'Cím' },
  { name: 'qty', label: 'Mennyiség', type: 'number' as const },
  { name: 'in_stock', label: 'Raktáron', type: 'checkbox' as const },
];

describe('normalizeValues', () => {
  it('drops empty values on create so SQL defaults still apply', () => {
    // The worker's `pick` writes any key that is *present*. Sending
    // `status: null` on a create would override the column default with NULL
    // and trip its NOT NULL constraint, so an untouched field must not be
    // sent at all.
    expect(normalizeValues({ title: 'Kréta', qty: undefined, in_stock: undefined }, fields, 'create')).toEqual({
      title: 'Kréta',
    });
    expect(normalizeValues({ title: 'Kréta', qty: '' }, fields, 'create')).toEqual({ title: 'Kréta' });
  });

  it('sends null on edit so a cleared field really clears', () => {
    // The opposite case: on a PATCH, omitting the key means "leave it alone",
    // so clearing an input has to be an explicit null or the old value sticks.
    expect(normalizeValues({ title: '', qty: null }, fields, 'edit')).toEqual({ title: null, qty: null });
  });

  it('coerces number fields and refuses an unparseable one', () => {
    expect(normalizeValues({ qty: '3.5' }, fields, 'create')).toEqual({ qty: 3.5 });
    expect(normalizeValues({ qty: 0 }, fields, 'create')).toEqual({ qty: 0 });
    expect(normalizeValues({ qty: 'sok' }, fields, 'edit')).toEqual({ qty: null });
  });

  it('passes booleans through — the worker maps them to SQLite 0/1', () => {
    expect(normalizeValues({ in_stock: false }, fields, 'create')).toEqual({ in_stock: false });
    expect(normalizeValues({ in_stock: true }, fields, 'edit')).toEqual({ in_stock: true });
  });

  it('keeps a checkbox the user never touched', () => {
    // D1 returns offer.in_stock as INTEGER 0/1, and setFieldsValue puts that
    // straight into the form — an untouched box never becomes a boolean.
    // Reading "not a boolean" as "cleared" nulled the column on every
    // unrelated edit of the row, while the box on screen stayed ticked.
    expect(normalizeValues({ title: 'x', in_stock: 1 }, fields, 'edit')).toEqual({ title: 'x', in_stock: true });
    expect(normalizeValues({ title: 'x', in_stock: 0 }, fields, 'edit')).toEqual({ title: 'x', in_stock: false });
    // A genuinely absent value still clears on edit.
    expect(normalizeValues({ in_stock: undefined }, fields, 'edit')).toEqual({ in_stock: null });
  });

  it('ignores keys that are not declared fields', () => {
    expect(normalizeValues({ title: 'x', bogus: 'y' } as never, fields, 'create')).toEqual({ title: 'x' });
  });

  it('trims strings so a space-only value is treated as empty', () => {
    expect(normalizeValues({ title: '   ' }, fields, 'create')).toEqual({});
    expect(normalizeValues({ title: '  Kréta ' }, fields, 'create')).toEqual({ title: 'Kréta' });
  });
});
