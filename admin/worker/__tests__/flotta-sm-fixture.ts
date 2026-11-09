// flotta-menedzser tesztterep: két menedzser (gondnok rang 1, helyettes rang 2) és a beteg `vilma`
// ugyanazon a boxon (v1: csak saját box érhető el). A `live(t)` a box friss jelentése (a
// menedzserek alkalmasak maradnak), az `exec` a végrehajtó hívása a box tokenjével.
import { flottaApp, green, min, red } from './flotta-fixture';

export const GONDNOK = 'plain-gondnok-agent', HELYETTES = 'plain-helyettes-agent', BOX = 'plain-box-gondnok';

export async function smApp({ deadman = 100000 } = {}) {
  const f = await flottaApp();
  f.manager('p-helyettes', 'helyettes', '*', 2);
  f.raw.prepare('UPDATE flotta_fleet SET deadman_min = ?').run(deadman);
  const live = (t: number, extra: unknown[] = [red('vilma', 'kuldes')], repair: unknown = { ok: true }) =>
    f.report('gondnok', [green('gondnok'), green('helyettes'), ...extra], min(t), undefined, repair);
  await live(0);
  const id = f.incidents()[0].id as string;
  const inc = () => f.raw.prepare('SELECT * FROM flotta_incident WHERE id = ?').get(id) as any;
  const claim = (t: number, token = GONDNOK) => f.call('POST', `/api/flotta/v1/incidents/${id}/claim`, {}, token, min(t));
  const exec = (t: number, path: string, body: Record<string, unknown>) => f.call('POST', `/api/flotta/v1/incidents/${id}${path}`, body, BOX, min(t));
  const ops = () => f.raw.prepare('SELECT * FROM flotta_repair_op WHERE incident_id = ? ORDER BY created_at, id').all(id) as any[];
  const events = () => (f.raw.prepare('SELECT kind FROM flotta_incident_event WHERE incident_id = ? ORDER BY id').all(id) as any[]).map(e => e.kind);
  /** Átvétel + egy teljes lépés (check → intent → result). */
  const run = async (t: number, c: { fence: number; claim: string }, step: string, op: string, outcome = 'ok', extra: Record<string, unknown> = {}) => {
    const b = { fence: c.fence, claim: c.claim, step, target: 'agent:vilma' };
    const check = await exec(t, '/ops/check', { ...b, op_id: op });
    if (check.status !== 200) return { check };
    const intent = await exec(t, `/ops/${op}/intent`, b);
    if (intent.status !== 200) return { check, intent };
    const result = await exec(t, `/ops/${op}/result`, { fence: c.fence, claim: c.claim, outcome, summary: `${step} kész`, ...extra });
    return { check, intent, result };
  };
  return { ...f, id, inc, claim, exec, ops, events, run, live };
}

export { min };
