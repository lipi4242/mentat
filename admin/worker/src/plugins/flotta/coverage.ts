// Lefedettség (flotta-menedzser): célonként és hibatartományonként (box). Fedetlen az a cél, amelynek
// a lánca (reach + alkalmasság után) üres. A box TELJES kiesése külön tartomány: ehhez másik
// boxon ülő, a boxot elérő menedzser kell — v1-ben (csak saját box) ilyen nincs, ezért minden
// box fedetlen tartományként szerepel, és az ilyen incidens azonnal e-mailt ad. A desktop gép
// kikapcsolása a normál állapota: az nem tartomány (nincs dead-man), az ágensei célként igen. A box-jelentés
// válasza ennek a boxra vonatkozó szeletét viszi vissza (doctor box-sor).
import { chain, facts, unfit } from './managers';
import type { Fleet } from './types';

export type Coverage = {
  uncovered: Array<{ target: string; why: string }>;
  unfit: Array<{ agent: string; why: string }>;
  human_needed: Array<{ incident: string; target: string; why: string | null }>;
  handovers: Array<{ incident: string; target: string; handovers: number }>;
};

export async function coverage(db: D1Database, fleet: Fleet, now: Date, box?: string): Promise<Coverage> {
  const f = await facts(db, fleet, now), out: Coverage = { uncovered: [], unfit: [], human_needed: [], handovers: [] };
  const mine = (b: string) => box === undefined || b === box;
  for (const [agent, a] of [...f.agentBox].sort()) {
    if (!mine(a.box)) continue;
    const c = chain({ agent, box: a.box }, f);
    if (!c.chain.length) out.uncovered.push({ target: `agent:${agent}`, why: c.excluded.map(e => `${e.handle}: ${e.why}`).join('; ') || 'nincs hatókörében menedzser' });
  }
  for (const b of [...f.boxes.values()].filter(b => !b.disabled_at && b.kind !== 'desktop' && mine(b.name)).sort((x, y) => x.name.localeCompare(y.name))) {
    out.uncovered.push({ target: `box:${b.name}`, why: 'a box teljes kiesésére nincs másik boxon ülő, elérő menedzser (v1: csak saját box)' });
  }
  for (const m of f.managers) {
    const at = f.agentBox.get(m.agent)?.box;
    if (box !== undefined && at !== box) continue;
    const why = unfit(m, f);
    if (why && !out.unfit.some(u => u.agent === m.agent)) out.unfit.push({ agent: m.agent, why });
  }
  const { results } = await db.prepare(`SELECT i.id, i.subject, i.state, i.handovers, i.human_reason, b.name AS box FROM flotta_incident i
      JOIN flotta_box b ON b.id = i.box_id WHERE i.fleet_id = ?1 AND i.status = 'open' ORDER BY i.opened_at`)
    .bind(fleet.id).all<{ id: string; subject: string; state: string; handovers: number; human_reason: string | null; box: string }>();
  for (const i of results.filter(r => mine(r.box))) {
    if (i.state === 'ember-kell') out.human_needed.push({ incident: i.id, target: i.subject, why: i.human_reason });
    if (i.handovers > 2) out.handovers.push({ incident: i.id, target: i.subject, handovers: i.handovers });
  }
  return out;
}
