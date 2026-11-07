// The extension path, end to end: a declaration that lives only in this test
// adds a field to cases and a customer + invoice pair of entities; the generator writes the migration the
// agent would commit; the API, the scopes and GET /api/meta follow from it.
// Nothing here ships — config/models.json stays empty.
import { describe, it, expect } from 'vitest';
import { createApp } from '../src/index';
import { pluginsFor } from '../../config/plugins';
import { loadModels } from '../src/core/models';
import { modelSql, schemaOf } from '../src/lib/model-sql.mjs';
import { makeDb, makeEnv, jsonReq } from './helpers';
import { hashToken } from '../src/lib/tokens';

const DEMO = loadModels({
  fields: {
    cases: [{ name: 'priority', label: 'Prioritás', type: 'select', options: ['alacsony', 'normál', 'magas'] }],
  },
  entities: [
    {
      name: 'ugyfelek',
      label: 'Ügyfelek',
      fields: [
        { name: 'nev', label: 'Név', type: 'text', required: true },
        { name: 'email', label: 'E-mail', type: 'email' },
      ],
    },
    {
      name: 'szamlak',
      label: 'Számlák',
      fields: [
        { name: 'ugyfel', label: 'Ügyfél', type: 'ref', ref: 'ugyfelek', required: true },
        { name: 'osszeg', label: 'Összeg', type: 'number', min: 0 },
        { name: 'esedekes', label: 'Esedékes', type: 'date' },
      ],
    },
  ],
});

const GAS = '01JAB6Z9Q3M8K7T2V5W4X1Y0RS';
// The product's migrations only: an instance's own 09NN files (and fields)
// must not change what this test proves.
const productDb = () => makeDb((f) => f < '0900');

async function extended({ migrate = true } = {}) {
  const { DB, raw } = productDb();
  if (migrate) raw.exec(modelSql(DEMO, schemaOf(raw)).join('\n'));
  const tokens: Record<string, string> = { agent: 'ugyfelek:write szamlak:write cases:write', reader: 'ugyfelek:read', other: 'cases:write' };
  for (const [plain, scopes] of Object.entries(tokens)) {
    raw
      .prepare(`INSERT INTO agent_token (id,label,token_hash,scopes,expires_at) VALUES (?,?,?,?,'2999-01-01T00:00:00Z')`)
      .run(plain, plain, await hashToken(plain), scopes);
  }
  const app = createApp(pluginsFor(DEMO));
  const env = makeEnv({ DB });
  const call = async (as: string, method: string, path: string, body?: unknown) => {
    const h = { 'X-Mentat-Token': as };
    const res = await app.request(path, body === undefined ? { method, headers: h } : jsonReq(method, body, h), env);
    return { status: res.status, body: await res.json() as any };
  };
  return { call, raw };
}

describe('the generated migration', () => {
  it('creates the entity tables and adds the case column — and nothing once applied', () => {
    const { raw } = productDb();
    const sql = modelSql(DEMO, schemaOf(raw));
    expect(sql.join('\n')).toMatch(/ALTER TABLE cases_case ADD COLUMN priority TEXT/);
    expect(sql.join('\n')).toMatch(/CREATE TABLE custom_szamlak[\s\S]*ugyfel TEXT NOT NULL REFERENCES custom_ugyfelek\(id\)/);
    raw.exec(sql.join('\n'));
    expect(modelSql(DEMO, schemaOf(raw))).toEqual([]);
  });
});

describe('a new field on cases', () => {
  it('is written, read back and validated', async () => {
    const { call } = await extended();
    const put = await call('agent', 'PUT', `/api/cases/${GAS}`, { title: 'Gázszámla', due_at: '2026-11-10', priority: 'magas' });
    expect(put.status).toBe(201);
    expect(put.body.priority).toBe('magas');
    expect((await call('agent', 'GET', '/api/cases')).body[0].priority).toBe('magas');
    const bad = await call('agent', 'PUT', `/api/cases/${GAS}`, { priority: 'sürgős', version: 1 });
    expect(bad.status).toBe(422);
    expect(bad.body.error).toMatch(/priority/);
  });

  it('says "not migrated yet" before its migration runs, instead of a 500', async () => {
    const { call } = await extended({ migrate: false });
    const res = await call('agent', 'PUT', `/api/cases/${GAS}`, { title: 'x', priority: 'magas' });
    expect(res.status).toBe(503);
    expect(res.body.error).toMatch(/priority/);
    expect((await call('agent', 'GET', '/api/meta')).body.fields.cases[0]).toMatchObject({ name: 'priority', pending: true });
  });
});

describe('a new entity', () => {
  it('has a working API with validation and a reference', async () => {
    const { call } = await extended();
    const anna = await call('agent', 'POST', '/api/ugyfelek', { nev: 'Kertész Anna', email: 'anna@example.com' });
    expect(anna.status).toBe(200);
    const inv = await call('agent', 'POST', '/api/szamlak', { ugyfel: anna.body.id, osszeg: 12000, esedekes: '2026-11-30' });
    expect(inv.status).toBe(200);
    expect((await call('agent', 'GET', `/api/szamlak?ugyfel=${anna.body.id}`)).body).toEqual([
      expect.objectContaining({ id: inv.body.id, osszeg: 12000 }),
    ]);
    expect((await call('agent', 'GET', '/api/szamlak?ugyfel=nobody')).body).toEqual([]);
    expect((await call('agent', 'POST', '/api/ugyfelek', { email: 'x@example.com' })).body.error).toMatch(/nev/);
    expect((await call('agent', 'POST', '/api/ugyfelek', { nev: 'B', email: 'nem-email' })).body.error).toMatch(/email/);
    expect((await call('agent', 'POST', '/api/szamlak', { ugyfel: anna.body.id, osszeg: -1 })).status).toBe(400);
    expect((await call('agent', 'POST', '/api/szamlak', { ugyfel: 'nincs-ilyen' })).status).toBe(409);
    const patched = await call('agent', 'PATCH', `/api/ugyfelek/${anna.body.id}`, { email: 'anna@example.com' });
    expect(patched.status).toBe(200);
    expect((await call('agent', 'GET', `/api/ugyfelek/${anna.body.id}`)).body.email).toBe('anna@example.com');
  });

  it('is reached only with its own scopes', async () => {
    const { call } = await extended();
    const id = (await call('agent', 'POST', '/api/ugyfelek', { nev: 'Anna' })).body.id;
    expect((await call('reader', 'GET', '/api/ugyfelek')).body.map((r: any) => r.id)).toEqual([id]);
    expect((await call('reader', 'POST', '/api/ugyfelek', { nev: 'B' })).status).toBe(403);
    expect((await call('reader', 'GET', '/api/szamlak')).status).toBe(403);
    expect((await call('other', 'GET', '/api/ugyfelek')).status).toBe(403);
  });

  it('is described by /api/meta, as far as the token reaches', async () => {
    const { call } = await extended();
    const all = (await call('agent', 'GET', '/api/meta')).body;
    expect(all.fields.cases.map((f: any) => f.name)).toEqual(['priority']);
    expect(all.entities.map((e: any) => [e.name, e.path, e.scopes.write])).toEqual([
      ['ugyfelek', '/api/ugyfelek', 'ugyfelek:write'],
      ['szamlak', '/api/szamlak', 'szamlak:write'],
    ]);
    expect(all.entities[1].fields[0]).toMatchObject({ name: 'ugyfel', type: 'ref', ref: 'ugyfelek', required: true });
    const reader = (await call('reader', 'GET', '/api/meta')).body;
    expect(reader).toEqual({ fields: {}, entities: [expect.objectContaining({ name: 'ugyfelek' })] });
  });

  it('answers 503 naming the table before its migration runs', async () => {
    const { call } = await extended({ migrate: false });
    const res = await call('agent', 'GET', '/api/ugyfelek');
    expect(res.status).toBe(503);
    expect(res.body.error).toMatch(/custom_ugyfelek/);
  });
});

describe('the models file is checked', () => {
  it.each([
    [{ fields: { cases: [{ name: 'title', label: 'x', type: 'text' }] } }, /built-in/],
    [{ fields: { purchasing: [] } }, /only cases/],
    [{ entities: [{ name: 'Ugyfel', label: 'x', fields: [] }] }, /name must match/],
    [{ entities: [{ name: 'u', label: 'x', fields: [{ name: 'a', label: 'a', type: 'select' }] }] }, /options/],
    [{ entities: [{ name: 'u', label: 'x', fields: [{ name: 'a', label: 'a', type: 'ref', ref: 'nincs' }] }] }, /ref/],
    [{ entities: [{ name: 'u', label: 'x', fields: [{ name: 'a', label: 'a', type: 'szam' }] }] }, /type/],
  ])('rejects %j', (doc, msg) => {
    expect(() => loadModels(doc)).toThrow(msg);
  });
});
