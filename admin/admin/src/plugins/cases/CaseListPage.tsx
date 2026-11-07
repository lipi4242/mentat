import { useState } from 'react';
import { Button, Segmented, Space, Table, Tag, Typography } from 'antd';
import { Link, useNavigate } from 'react-router-dom';
import { useApi } from '../../lib/useApi';
import { ownFields, useModels } from '../../lib/useModels';
import { showValue } from '../../components/crud/fromModel';
import { CaseFormModal, type FormTarget } from './CaseFormModal';
import { STATUS, isOverdue, recurrenceLabel, type CaseRow } from './meta';

/**
 * Cases by due date (the worker orders them: earliest first, undated last).
 * The default view hides closed cases — what still needs doing is the point.
 */
export function CaseListPage() {
  const [scope, setScope] = useState<'active' | 'all'>('active');
  const { data, loading, error, reload } = useApi<CaseRow[]>(scope === 'active' ? '/api/cases?status=open,waiting' : '/api/cases');
  const [target, setTarget] = useState<FormTarget>(null);
  const navigate = useNavigate();
  const own = ownFields(useModels().models, 'cases');

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ width: '100%', justifyContent: 'space-between' }} wrap>
        <Typography.Title level={4}>Ügyek</Typography.Title>
        <Space>
          <Segmented
            value={scope}
            onChange={(v) => setScope(v as 'active' | 'all')}
            options={[
              { label: 'Teendő', value: 'active' },
              { label: 'Mind', value: 'all' },
            ]}
          />
          <Button type="primary" onClick={() => setTarget({})}>
            Új ügy
          </Button>
        </Space>
      </Space>
      {error && <Typography.Text type="danger">{error.message}</Typography.Text>}
      <Table<CaseRow>
        rowKey="id"
        loading={loading}
        dataSource={data ?? []}
        pagination={{ pageSize: 50, hideOnSinglePage: true }}
        columns={[
          { title: 'Cím', dataIndex: 'title', render: (t: string, row) => <Link to={`/ugyek/${row.id}`}>{t}</Link> },
          {
            title: 'Esedékes',
            dataIndex: 'due_at',
            render: (d: string | null, row) => (
              <Space size={4}>
                {d || '—'}
                {isOverdue(row) && <Tag color="red">lejárt</Tag>}
              </Space>
            ),
          },
          { title: 'Állapot', dataIndex: 'status', render: (s: CaseRow['status']) => <Tag color={STATUS[s]?.color}>{STATUS[s]?.label ?? s}</Tag> },
          { title: 'Ismétlődés', dataIndex: 'recurrence', render: recurrenceLabel },
          { title: 'Következő lépés', dataIndex: 'next_action', render: (n: string | null) => n || '—' },
          ...own.map((f) => ({ title: f.label, dataIndex: f.name, render: (v: unknown) => showValue(f, v) })),
        ]}
      />
      <CaseFormModal
        own={own}
        target={target}
        onClose={() => setTarget(null)}
        onSaved={(id) => {
          reload();
          navigate(`/ugyek/${id}`);
        }}
      />
    </div>
  );
}
