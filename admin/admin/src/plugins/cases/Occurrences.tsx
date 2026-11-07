import { useState } from 'react';
import { Alert, Button, List, Space, Tag, Typography } from 'antd';
import { apiSend } from '../../lib/api';
import { today, type CaseDetail } from './meta';

/**
 * A recurring case's dates: the open ones (from the earliest) and the closed
 * ones. Only the earliest open date has a close button — the worker refuses
 * any other, so an unpaid month cannot hide behind a paid later one.
 */
export function Occurrences({ row, onChanged }: { row: CaseDetail; onChanged: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const close = async (due_at: string, status: 'done' | 'skipped') => {
    setBusy(true);
    setError(null);
    try {
      await apiSend('POST', `/api/cases/${row.id}/occurrences`, { due_at, status, done_at: today() });
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'A lezárás nem sikerült.');
    } finally {
      setBusy(false);
    }
  };

  const now = today();
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      {error && <Alert type="error" showIcon message={error} />}
      <List
        size="small"
        header={<Typography.Text strong>Nyitott</Typography.Text>}
        locale={{ emptyText: 'nincs nyitott előfordulás' }}
        dataSource={row.open_occurrences}
        renderItem={(d, i) => (
          <List.Item
            actions={
              i === 0
                ? [
                    <Button key="done" size="small" type="primary" loading={busy} onClick={() => close(d, 'done')}>
                      Lezárás
                    </Button>,
                    <Button key="skip" size="small" loading={busy} onClick={() => close(d, 'skipped')}>
                      Kihagyás
                    </Button>,
                  ]
                : []
            }
          >
            {d} {d < now && <Tag color="red">lejárt</Tag>}
          </List.Item>
        )}
      />
      <List
        size="small"
        header={<Typography.Text strong>Lezárt</Typography.Text>}
        locale={{ emptyText: 'még nincs lezárt előfordulás' }}
        dataSource={[...row.occurrences].reverse()}
        renderItem={(o) => (
          <List.Item>
            {o.due_at} <Tag color={o.status === 'done' ? 'green' : 'default'}>{o.status === 'done' ? 'kész' : 'kihagyva'}</Tag>
            {o.done_at && <Typography.Text type="secondary">{o.done_at}</Typography.Text>} {o.note}
          </List.Item>
        )}
      />
    </Space>
  );
}
