// Ki mit próbált egy incidensen (flotta-menedzser): az e-mail és a feladat-komment összefoglalója a
// D1-auditból (flotta_repair_op + átadások). Titok nincs benne: a lépés neve, a kimenet és a
// végrehajtó saját (már szűrt) összefoglalója, rövidítve.
const STATE_HU: Record<string, string> = {
  intent: 'fut / nem zárult le', ok: 'sikerült', failed: 'nem sikerült', uncertain: 'bizonytalan', assessed: 'felmérve',
  busy: 'az ágens dolgozott, nem indítottam újra', refused: 'a végrehajtó elutasította',
};

export async function attemptLines(db: D1Database, incidentId: string, max = 12): Promise<string[]> {
  const ops = (await db.prepare(`SELECT o.created_at, o.step, o.state, o.summary, p.handle FROM flotta_repair_op o
      LEFT JOIN todo_principal p ON p.id = o.principal_id WHERE o.incident_id = ?1 ORDER BY o.created_at LIMIT ?2`)
    .bind(incidentId, max).all<{ created_at: string; step: string; state: string; summary: string | null; handle: string | null }>()
    .catch(() => ({ results: [] }))).results;
  const moves = (await db.prepare(`SELECT at, kind, body FROM flotta_incident_event WHERE incident_id = ?1
      AND kind IN ('assigned', 'claimed', 'handover', 'uncovered', 'budget_exhausted', 'human_needed') ORDER BY id LIMIT ?2`)
    .bind(incidentId, max).all<{ at: string; kind: string; body: string | null }>()).results;
  const lines = moves.map(m => {
    const b = m.body ? JSON.parse(m.body) as Record<string, unknown> : {};
    const to = typeof b.to === 'string' ? b.to : typeof b.by === 'string' ? b.by : '';
    return `${m.at.slice(0, 16)} ${m.kind}${to ? ` → ${to}` : ''}${typeof b.why === 'string' ? ` (${b.why})` : ''}${typeof b.reason === 'string' ? ` (${b.reason})` : ''}`;
  });
  for (const o of ops) lines.push(`${o.created_at.slice(0, 16)} ${o.handle ?? '?'}: ${o.step} — ${STATE_HU[o.state] ?? o.state}${o.summary ? `: ${o.summary.slice(0, 160)}` : ''}`);
  return lines.sort();
}
