import { describe, expect, it } from 'vitest';
import { todoApp } from './todo-fixture';

describe('todo transaction races', () => {
  it('returns the winning create after a concurrent unique-key collision', async () => {
    const { call, create, env, count } = await todoApp();
    const batch = env.DB.batch.bind(env.DB); let winner: any;
    env.DB.batch = (async statements => {
      env.DB.batch = batch;
      winner = await create({ title: 'Winner', idem_key: 'race' });
      return batch(statements);
    }) as typeof env.DB.batch;
    const res = await call('POST', '/tasks', { title: 'Loser', idem_key: 'race' });
    expect(res.status).toBe(200); expect(res.body.id).toBe(winner.id); expect(res.body.title).toBe('Winner'); expect(count()).toBe(1);
  });
  it('rejects an inverse dependency created after the initial cycle check', async () => {
    const { create, call, env, raw, count } = await todoApp(); const a = await create(), b = await create();
    const batch = env.DB.batch.bind(env.DB);
    env.DB.batch = (async statements => {
      raw.prepare('INSERT INTO todo_dep VALUES (?,?)').run(b.id, a.id);
      return batch(statements);
    }) as typeof env.DB.batch;
    expect((await call('POST', `/tasks/${a.id}/deps`, { depends_on_id: b.id, expected_rev: 1 })).status).toBe(409);
    expect(count()).toBe(2); expect(count('todo_dep')).toBe(1);
  });
});
