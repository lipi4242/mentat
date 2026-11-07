import { useState } from 'react';
import { Alert, Button, Card, Descriptions, Skeleton, Space, Tag, Typography } from 'antd';
import { Link, useParams } from 'react-router-dom';
import { useApi } from '../../lib/useApi';
import { ownFields, useModels } from '../../lib/useModels';
import { showValue } from '../../components/crud/fromModel';
import { CaseEvents } from './CaseEvents';
import { CaseFormModal, type FormTarget } from './CaseFormModal';
import { Occurrences } from './Occurrences';
import { STATUS, isOverdue, recurrenceLabel, type CaseDetail } from './meta';

/**
 * One case: the tracked fields, its dates, the brain context (read-only — the
 * agent mirrors it from `brain_ref`), and the trail of who changed what.
 * The route param is `:id`, matching the resource's `show: '/ugyek/:id'`.
 */
export function CaseShowPage() {
  const { id } = useParams();
  const { data: row, loading, error, reload } = useApi<CaseDetail>(id ? `/api/cases/${encodeURIComponent(id)}` : null);
  const [target, setTarget] = useState<FormTarget>(null);
  const own = ownFields(useModels().models, 'cases');

  if (error) {
    return (
      <div style={{ padding: 24 }}>
        <Alert type="error" showIcon message={error.message} />
        <Link to="/ugyek">Vissza az ügyekhez</Link>
      </div>
    );
  }
  if (loading || !row) return <Skeleton active style={{ padding: 24 }} />;
  const st = STATUS[row.status];

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%', padding: 24 }}>
      <Space style={{ justifyContent: 'space-between', width: '100%' }} align="start" wrap>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {row.title} <Tag color={st?.color}>{st?.label ?? row.status}</Tag>
        </Typography.Title>
        <Button onClick={() => setTarget({ row })}>Szerkesztés</Button>
      </Space>

      <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
        <Descriptions.Item label="Esedékes">
          {row.due_at || '—'} {isOverdue(row) && <Tag color="red">lejárt</Tag>}
        </Descriptions.Item>
        <Descriptions.Item label="Ismétlődés">
          {recurrenceLabel(row.recurrence)}
          {row.anchor_at ? ` (első: ${row.anchor_at})` : ''}
        </Descriptions.Item>
        <Descriptions.Item label="Leírás" span={2}>{row.description || '—'}</Descriptions.Item>
        <Descriptions.Item label="Következő lépés">{row.next_action || '—'}</Descriptions.Item>
        {own.map((f) => (
          <Descriptions.Item key={f.name} label={f.label}>{showValue(f, row[f.name])}</Descriptions.Item>
        ))}
        <Descriptions.Item label="Módosítva">
          {row.updated_at} · v{row.version}
        </Descriptions.Item>
      </Descriptions>

      {row.recurrence && (
        <Card title="Előfordulások" size="small">
          <Occurrences row={row} onChanged={reload} />
        </Card>
      )}

      <Card title={`Háttér az agyból${row.brain_ref ? ` — ${row.brain_ref}` : ''}`} size="small">
        {row.context ? (
          <Typography.Paragraph style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{row.context}</Typography.Paragraph>
        ) : (
          <Typography.Text type="secondary">Az ágens még nem küldte fel.</Typography.Text>
        )}
      </Card>

      <Card title="Események" size="small">
        <CaseEvents events={row.events} />
      </Card>

      <CaseFormModal own={own} target={target} onClose={() => setTarget(null)} onSaved={reload} />
    </Space>
  );
}
