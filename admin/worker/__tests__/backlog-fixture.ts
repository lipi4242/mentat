// Backlog fixture: agents a (PM), b (developer), c (outsider) from todoApp, plus a
// signed-in human admin, a WEB project and helpers that drive an item to a stage.
import app from '../src/index';
import { todoApp } from './todo-fixture';
import { signIn } from './sign-in';

export async function backlogApp() {
  const t = await todoApp();
  t.env.BETTER_AUTH_SECRET = 'test-secret-at-least-thirty-two-characters';
  t.env.OTP_SENDER = 'Mentat <noreply@example.com>';
  const human = { cookie: (await signIn(app, t.env, 'owner@example.com'))! };
  await t.call('POST', '/principals', { kind: 'human', auth_email: 'owner@example.com', handle: 'owner', display_name: 'Owner', idem_key: 'self' }, human);
  const as = (who: string) => (who === 'human' ? human : { 'X-Mentat-Token': who });
  const project = (await t.call('POST', '/projects', { prefix: 'WEB', name: 'Web', idem_key: 'web' }, human)).body;
  const get = async (id: string) => (await t.call('GET', `/items/${id}`)).body;
  const item = async (body: Record<string, unknown> = {}, who = 'a') =>
    (await t.call('POST', '/items', { project: 'WEB', title: 'Item', acs: ['AC one', 'AC two'], idem_key: crypto.randomUUID(), ...body }, as(who))).body;
  /** One verb with the item's current rev; `body` overrides it. */
  const act = async (id: string, verb: string, body: Record<string, unknown> = {}, who = 'a') =>
    t.call('POST', `/items/${id}/${verb}`, { expected_rev: (await get(id)).rev, ...body }, as(who));
  const results = async (id: string, verdict = 'met') =>
    (await get(id)).acs.map((a: any) => ({ ac_id: a.id, verdict, evidence: `checked ${a.text}` }));
  const submit = async (id: string, extra: Record<string, unknown> = {}, who = 'b') => {
    const rounds = (await get(id)).reports.length;
    return act(id, 'submit', { round: rounds + 1, summary: 'done', results: await results(id), ...extra }, who);
  };
  const checks = async (id: string, ok = true) =>
    (await get(id)).reports.at(-1).results.map((r: any) => ({ ac_id: r.ac_id, pm_ok: ok, ...(ok ? {} : { pm_note: 'not yet' }) }));
  /** Drive a fresh item to `stage` along the happy path (PM a, dev b). */
  const at = async (stage: string, body: Record<string, unknown> = {}) => {
    const row = await item(body);
    const path: Record<string, (() => Promise<unknown>)[]> = {
      draft: [], issued: [() => act(row.id, 'issue', { dev: 'b' })],
      taken: [() => act(row.id, 'issue', { dev: 'b' }), () => act(row.id, 'take', {}, 'b')],
      review: [() => act(row.id, 'issue', { dev: 'b' }), () => act(row.id, 'take', {}, 'b'), () => submit(row.id)],
      done: [() => act(row.id, 'issue', { dev: 'b' }), () => act(row.id, 'take', {}, 'b'), () => submit(row.id),
        async () => act(row.id, 'accept', { checks: await checks(row.id) })],
      hold: [() => act(row.id, 'hold', { note: 'wait' })],
      dropped: [() => act(row.id, 'drop', { note: 'no' })],
    };
    for (const step of path[stage]) {
      const res = await step() as { status: number; body: unknown };
      if (res.status !== 200) throw new Error(`fixture step to ${stage} failed: ${JSON.stringify(res.body)}`);
    }
    return get(row.id);
  };
  return { ...t, human, as, project, get, item, act, results, submit, checks, at };
}
