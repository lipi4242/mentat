import { useState } from 'react';
import { Alert, Button, Input, Modal, Select, Space, Tooltip } from 'antd';
import { verbLabel, verbsFor, type ItemDetail, type Me, type Principal, type Verb } from './meta';
import { ReviewPanel } from './ReviewPanel';
import { useVerb } from './useVerb';
const NEEDS_NOTE: Verb[] = ['hold', 'drop', 'handback'], REQUIRED: Verb[] = ['handback'];
const WHY: Partial<Record<Verb, string>> = { hold: 'Mi miatt tesszük félre?', drop: 'Miért engedjük el?', handback: 'Miért adod vissza?' };
export function ItemActions({ item, me, principals, reload }: { item: ItemDetail; me: Me; principals: Principal[]; reload: () => void }) {
  const { run, error, busy } = useVerb(item, reload);
  const [ask, setAsk] = useState<Verb | null>(null), [note, setNote] = useState(''), [dev, setDev] = useState<string>();
  const verbs = verbsFor(item, me), round = item.reports.filter(r => !r.pm_verdict).at(-1);
  const noAc = !item.acs.length, plain = verbs.filter(v => v !== 'accept' && v !== 'reject');
  const close = () => { setAsk(null); setNote(''); };
  const go = async () => {
    if (!ask) return;
    const payload = ask === 'issue' ? { dev } : NEEDS_NOTE.includes(ask) ? (note.trim() ? { note: note.trim() } : {}) : {};
    if (await run(ask, payload)) close();
  };
  const people = principals.filter(p => !p.disabled_at).map(p => ({ value: p.handle, label: p.display_name }));
  return <section className="bl-actions" aria-label="Műveletek">
    {error && <Alert type="info" message={error} />}
    {verbs.includes('accept') && round && <ReviewPanel report={round} busy={busy} run={run} />}
    <Space wrap>{plain.map(v => {
      const off = busy || (v === 'issue' && noAc);
      const btn = <Button key={v} type={v === 'issue' || v === 'take' ? 'primary' : 'default'} disabled={off}
        onClick={() => ['resume', 'take'].includes(v) ? void run(v) : setAsk(v)}>{verbLabel[v]}</Button>;
      return v === 'issue' && noAc ? <Tooltip key={v} title="Előbb adj meg legalább egy „Kész, ha” feltételt."><span>{btn}</span></Tooltip> : btn;
    })}</Space>
    {ask && <Modal open title={verbLabel[ask]} okText={verbLabel[ask]} cancelText="Mégse" onCancel={close} onOk={go} confirmLoading={busy}
      okButtonProps={{ disabled: ask === 'issue' ? !dev : REQUIRED.includes(ask) && !note.trim() }}>
      {ask === 'issue' ? <Select aria-label="Fejlesztő" style={{ width: '100%' }} placeholder="Kinek adod ki?" value={dev} onChange={setDev} options={people} />
        : <Input.TextArea aria-label={WHY[ask]} placeholder={`${WHY[ask]}${REQUIRED.includes(ask) ? '' : ' (nem kötelező)'}`} autoSize={{ minRows: 2 }} value={note} onChange={e => setNote(e.target.value)} />}
    </Modal>}
  </section>;
}
