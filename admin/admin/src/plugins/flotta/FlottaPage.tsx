import { Alert, Descriptions, Space, Table, Tag, Timeline, Tooltip, Typography } from 'antd';
import { InfoCircleOutlined } from '@ant-design/icons';
import { Link } from 'react-router-dom';
import { useApi } from '../../lib/useApi';
import { API, age, EVENT_LABEL, managerLine, when, type Agent, type Box, type Incident, type IncidentEvent, type Status, stateOf } from './meta';

function History({ id }: { id: string }) {
  const { data, error } = useApi<Incident & { events: IncidentEvent[] }>(`${API}/incidents/${id}`);
  if (error) return <Alert type="info" message="A történet most nem érhető el." />;
  if (!data) return null;
  return <Timeline items={data.events.map(e => ({ children: <span>{when(e.at)} · {EVENT_LABEL[e.kind] ?? e.kind}</span> }))} />;
}

const subject = (i: Incident) => (i.agent ? `${i.agent} (${i.box_name})` : `box ${i.box_name}`);

export function FlottaPage() {
  const { data, error, loading } = useApi<Status>(`${API}/status`);
  const fleet = data?.fleets[0];
  return <main className="todo-page">
    <header className="todo-heading"><Typography.Title level={4}>Flotta</Typography.Title>
      <Tooltip title="A boxok 10 percenként jelentik az ágenseik képesség-próbáját. A piros incidens a menedzser-lánc első alkalmas tagjáé (átvétel 10 percen belül, 30 perces keret, utána a helyettes); ha a lánc üres vagy elfogy, e-mail megy a tulajdonosnak.">
        <InfoCircleOutlined aria-label="Flotta súgó" /></Tooltip>
    </header>
    {error && <Alert type="info" message="A flotta állapota most nem érhető el." />}
    {fleet && <Descriptions size="small" column={{ xs: 1, md: 3 }} items={[
      { key: 'r', label: 'Felelős ágensek', children: managerLine(fleet.managers) ?? 'nincs — a hiba e-mailben megy' },
      { key: 'o', label: 'Tulajdonos e-mail', children: fleet.effective_owner_email ?? 'nincs beállítva' },
      { key: 'c', label: 'Fedetlen célok', children: fleet.coverage ? (fleet.coverage.uncovered.length
        ? <Tooltip title={fleet.coverage.uncovered.map(u => `${u.target}: ${u.why}`).join('\n')}><Tag color="orange">{fleet.coverage.uncovered.length}</Tag></Tooltip> : 'nincs') : '—' },
      { key: 't', label: 'Küszöbök', children: `csend ${fleet.deadman_min} p · eszkaláció ${fleet.escalate_min} p · ismétlés ${fleet.repeat_min} p` },
    ]} />}
    <Typography.Title level={5}>Incidensek</Typography.Title>
    <Table<Incident> rowKey="id" loading={loading} dataSource={data?.incidents ?? []} pagination={{ pageSize: 20 }}
      expandable={{ expandedRowRender: i => <History id={i.id} /> }} columns={[
        { title: 'Állapot', key: 'state', render: (_, i) => { const [l, c] = stateOf(i); return <Tooltip title={i.human_reason ?? undefined}><Tag color={c}>{l}</Tag></Tooltip>; } },
        { title: 'Alany', key: 'subject', render: (_, i) => subject(i) },
        { title: 'Ellenőrzés', dataIndex: 'check_key' },
        { title: 'Részlet', dataIndex: 'detail', ellipsis: true },
        { title: 'Nyílt', dataIndex: 'opened_at', render: when },
        { title: 'Levél', dataIndex: 'mail_count' },
        { title: 'Feladat', dataIndex: 'todo_task_id', render: t => t ? <Link to={`/feladatok/${t}`}>megnyitás</Link> : '—' },
      ]} />
    <Typography.Title level={5}>Boxok</Typography.Title>
    <Table<Box> rowKey="id" loading={loading} dataSource={data?.boxes ?? []} pagination={false} columns={[
      { title: 'Box', dataIndex: 'name' },
      { title: 'Utolsó jelentés', key: 'age', render: (_, b) => b.disabled_at ? <Tag>kivezetve</Tag>
        : <Space>{b.stale ? <Tag color="red">néma</Tag> : <Tag color="green">él</Tag>}{age(b.age_min)}
          {b.rejected_count ? <Tooltip title={`utolsó ok: ${b.last_reject ?? '?'}`}><Tag color="red">elutasítva {b.rejected_count}×</Tag></Tooltip> : null}</Space> },
      { title: 'Flotta-verzió', dataIndex: 'fleet_version', render: v => v ?? '—' },
      { title: 'Kiadás', key: 'release', render: (_, b) => b.release?.lag ? <Tooltip title={b.release.lag}><Tag color="orange">{b.release.here ?? '?'}</Tag></Tooltip>
        : b.release?.here ?? '—' },
    ]} />
    <Typography.Title level={5}>Ágensek</Typography.Title>
    <Table<Agent> rowKey="id" loading={loading} dataSource={data?.agents ?? []} pagination={false} columns={[
      { title: 'Ágens', dataIndex: 'name' },
      { title: 'Box', dataIndex: 'box_name' },
      { title: 'Képesség', key: 'cap', render: (_, a) => a.result.red.length
        ? <Space wrap>{a.result.red.map(r => <Tooltip key={r.check} title={r.detail}><Tag color="red">{r.check}</Tag></Tooltip>)}</Space>
        : <Tag color="green">zöld · {a.result.ok.length} lépés</Tag> },
      { title: 'Mérve', dataIndex: 'measured_at', render: when },
    ]} />
  </main>;
}
