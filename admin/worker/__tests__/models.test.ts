// config/models.json is the one file an agent edits to extend the admin
// (agent/EXTENDING.md). These keep it honest: it must load, and every field it
// declares must exist after the migrations — a declaration whose migration was
// never written fails here, not as a 503 in production.
import { describe, it, expect } from 'vitest';
import { MODELS } from '../../config/plugins';
import { modelSql, schemaOf } from '../src/lib/model-sql.mjs';
import { makeDb } from './helpers';

describe('config/models.json', () => {
  it('has a migration for everything it declares', () => {
    const { raw } = makeDb();
    const missing = modelSql(MODELS, schemaOf(raw));
    expect(missing, `run: npm run model:migration -- <slug>\n${missing.join('\n')}`).toEqual([]);
  });
});
