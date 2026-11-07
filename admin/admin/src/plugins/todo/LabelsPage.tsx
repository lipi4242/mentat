import { useState } from 'react';
import { Alert, Button, Form, Input, Space, Table, Typography } from 'antd';
import { useApi } from '../../lib/useApi';
import { apiSend } from '../../lib/api';
import { API, type Label } from './meta';
export function LabelsPage() {
  const { data, error, loading, reload } = useApi<Label[]>(`${API}/labels`);
  const [failure, setFailure] = useState(''), [busy, setBusy] = useState(false), [key, setKey] = useState(() => crypto.randomUUID());
  const [form] = Form.useForm();
  const save = async (values: { name: string; color?: string }) => {
    setBusy(true); setFailure('');
    try { await apiSend('POST', `${API}/labels`, { ...values, color: values.color || null, idem_key: key }); setKey(crypto.randomUUID()); form.resetFields(); reload(); }
    catch (e) { setFailure((e as Error).message); } finally { setBusy(false); }
  };
  return <Space direction="vertical" size="large" style={{ padding: 24, width: '100%' }}>
    <Typography.Title level={4}>Címkék</Typography.Title>
    {(error || failure) && <Alert type="info" message={failure || error?.message} />}
    <Form form={form} layout="inline" onFinish={save}>
      <Form.Item name="name" label="Név" rules={[{ required: true, whitespace: true }]}><Input /></Form.Item>
      <Form.Item name="color" label="Szín"><Input placeholder="#889399" /></Form.Item>
      <Button htmlType="submit" loading={busy}>Címke hozzáadása</Button>
    </Form>
    <Table rowKey="id" loading={loading} dataSource={data ?? []} columns={[{ title: 'Név', dataIndex: 'name' }, { title: 'Szín', dataIndex: 'color' }]} />
  </Space>;
}
