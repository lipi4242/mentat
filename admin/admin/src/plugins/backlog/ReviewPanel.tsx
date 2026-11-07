import { useState } from 'react';
import { Button, Checkbox, Input, Space, Typography } from 'antd';
import type { Report } from './meta';
type Run = (verb: string, payload?: Record<string, unknown>) => Promise<boolean>;
const said = { met: 'Teljesült', not_met: 'Nem teljesült', na: 'Nem releváns' };
/** The developer's AC form for the current round; the PM ticks each AC, then accepts or sends it back. */
export function ReviewPanel({ report, busy, run }: { report: Report; busy: boolean; run: Run }) {
  const [ok, setOk] = useState<Record<string, boolean>>({}), [notes, setNotes] = useState<Record<string, string>>({}), [note, setNote] = useState('');
  const checks = report.results.map(r => ({ ac_id: r.ac_id, pm_ok: !!ok[r.ac_id], ...(notes[r.ac_id]?.trim() ? { pm_note: notes[r.ac_id].trim() } : {}) }));
  const allOk = report.results.every(r => ok[r.ac_id] && r.verdict !== 'not_met');
  const rejectable = report.results.some(r => !ok[r.ac_id]) && report.results.every(r => ok[r.ac_id] || notes[r.ac_id]?.trim());
  return <div className="bl-review">
    <Typography.Title level={5}>{report.round}. kör: {report.summary}</Typography.Title>
    <ol className="bl-results">{report.results.map(r => <li key={r.ac_id}>
      <Checkbox aria-label={`${r.ac_text} rendben`} checked={!!ok[r.ac_id]} onChange={e => setOk({ ...ok, [r.ac_id]: e.target.checked })}>{r.ac_text}</Checkbox>
      <div className="bl-evidence"><b>{said[r.verdict]}.</b> {r.evidence}</div>
      {!ok[r.ac_id] && <Input aria-label={`Megjegyzés: ${r.ac_text}`} placeholder="Mit javítson ennél?" value={notes[r.ac_id] ?? ''}
        onChange={e => setNotes({ ...notes, [r.ac_id]: e.target.value })} />}
    </li>)}</ol>
    <Input.TextArea aria-label="Üzenet a fejlesztőnek" placeholder="Üzenet a fejlesztőnek (nem kötelező)" autoSize={{ minRows: 1 }} value={note} onChange={e => setNote(e.target.value)} />
    <Space wrap style={{ marginTop: 12 }}>
      <Button type="primary" disabled={busy || !allOk} onClick={() => void run('accept', { checks })}>Elfogadás</Button>
      <Button disabled={busy || !rejectable} onClick={() => void run('reject', { checks, note: note.trim() || checks.find(c => !c.pm_ok)?.pm_note })}>Visszautasítás</Button>
    </Space>
    {!allOk && <div className="bl-hint">Az elfogadáshoz minden feltételt pipálj ki, és mind teljesüljön.</div>}
  </div>;
}
