import { useState } from 'react';
import { App, Button, Popconfirm, Space, Table, Tag, Typography } from 'antd';
import { useApi } from '../../lib/useApi';
import { apiSend } from '../../lib/api';
import { MintTokenModal } from './MintTokenModal';

type TokenRow = {
  id: string;
  label: string;
  scopes: string;
  active: number;
  expires_at: string;
  created_at: string;
  last_used_at: string | null;
};

/** Agent tokens: who can write as a machine, until when, and a way to stop it. */
export function TokensPage() {
  const { data, loading, error, reload } = useApi<TokenRow[]>('/api/tokens');
  const [minting, setMinting] = useState(false);
  const { message } = App.useApp();

  const revoke = async (id: string) => {
    try {
      await apiSend('POST', `/api/tokens/${id}/revoke`, {});
      reload();
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'A visszavonás nem sikerült.');
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <Typography.Title level={4}>Gépi tokenek</Typography.Title>
        <Button type="primary" onClick={() => setMinting(true)}>
          Új token
        </Button>
      </Space>
      {error && <Typography.Text type="danger">{error.message}</Typography.Text>}
      <Table<TokenRow>
        rowKey="id"
        loading={loading}
        dataSource={data ?? []}
        pagination={false}
        columns={[
          { title: 'Ágens', dataIndex: 'label' },
          { title: 'Hatókörök', dataIndex: 'scopes' },
          { title: 'Állapot', dataIndex: 'active', render: (a: number) => (a ? <Tag color="green">aktív</Tag> : <Tag>visszavonva</Tag>) },
          { title: 'Lejár (UTC)', dataIndex: 'expires_at' },
          { title: 'Utoljára használva', dataIndex: 'last_used_at', render: (v: string | null) => v || '—' },
          {
            title: '',
            key: 'revoke',
            render: (_: unknown, row) =>
              row.active ? (
                <Popconfirm title="Visszavonod?" description="Az ágens ezzel a tokennel többé nem ír." okText="Visszavonás" cancelText="Mégse" onConfirm={() => revoke(row.id)}>
                  <Button size="small" danger>
                    Visszavonás
                  </Button>
                </Popconfirm>
              ) : null,
          },
        ]}
      />
      <MintTokenModal
        open={minting}
        onClose={(minted) => {
          setMinting(false);
          if (minted) reload();
        }}
      />
    </div>
  );
}
