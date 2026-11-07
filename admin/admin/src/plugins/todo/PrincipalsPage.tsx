import { useState } from 'react';
import { Alert, Avatar, Button, Drawer, Form, Input, Select, Space, Table, Tooltip, Typography } from 'antd';
import { PlusOutlined, RobotOutlined, UserOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { AvatarUpload } from './AvatarUpload';
import { useApi } from '../../lib/useApi';
import { apiSend } from '../../lib/api';
import { API, type Principal } from './meta';
export function PrincipalsPage() {
  const { data, error, loading, reload } = useApi<Principal[]>(`${API}/principals`);
  const [failure, setFailure] = useState(''), [busy, setBusy] = useState(false), [key, setKey] = useState(() => crypto.randomUUID());
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();
  const kind = Form.useWatch('kind', form) ?? 'human';
  const save = async (values: Record<string, string>) => {
    setBusy(true); setFailure('');
    const body = { kind: values.kind, display_name: values.display_name, handle: values.handle, avatar: values.avatar || null,
      auth_email: values.kind === 'human' ? values.auth_email : null, agent_token_id: values.kind === 'agent' ? values.agent_token_id : null, idem_key: key };
    try { await apiSend('POST', `${API}/principals`, body); setKey(crypto.randomUUID()); form.resetFields(); setOpen(false); reload(); }
    catch (e) { setFailure((e as Error).message); } finally { setBusy(false); }
  };
  return <main className="todo-page">
    <header className="todo-heading"><Typography.Title level={4}>Résztvevők</Typography.Title>
      <Tooltip title="Ágenshez a Gépi tokenek oldalán kiadott, todo:write jogosultságú token azonosítója kell."><InfoCircleOutlined aria-label="Résztvevők súgó" /></Tooltip>
      <Button icon={<PlusOutlined />} onClick={() => setOpen(true)}>Hozzáadás</Button>
    </header>
    {error && <Alert type="info" message="A lista még nem érhető el. Hozd létre magad." />}
    <Table<Principal> rowKey="id" loading={loading} dataSource={data ?? []} columns={[
      { title: 'Név', key: 'name', render: (_, p) => <Space><Avatar size={28} src={p.avatar}>{p.display_name.slice(0,1)}</Avatar>{p.display_name}</Space> },
      { title: 'Handle', dataIndex: 'handle', render: handle => `@${handle}` },
      { title: 'Típus', dataIndex: 'kind', render: value => <Tooltip title={value === 'human' ? 'Ember' : 'Ágens'}>{value === 'human' ? <UserOutlined aria-label="Ember" /> : <RobotOutlined aria-label="Ágens" />}</Tooltip> },
    ]} />
    <Drawer title="Új résztvevő" open={open} onClose={() => setOpen(false)}>
      {failure && <Alert type="info" message={failure} />}
    <Form form={form} layout="vertical" initialValues={{ kind: 'human' }} onFinish={save} style={{ width: '100%', maxWidth: 600 }}>
      <Form.Item name="kind" label="Típus"><Select options={[{ value: 'human', label: 'Ember' }, { value: 'agent', label: 'Ágens' }]} /></Form.Item>
      <Form.Item name="display_name" label="Név" rules={[{ required: true }]}><Input /></Form.Item>
      <Form.Item name="handle" label="Handle" extra="Kisbetű, szám és aláhúzás; az említésekhez." rules={[{ required: true, pattern: /^[a-z0-9_]{1,64}$/ }]}><Input /></Form.Item>
      {kind === 'human' ? <Form.Item name="auth_email" label="Belépési e-mail" rules={[{ required: true, type: 'email' }]}><Input /></Form.Item>
        : <Form.Item name="agent_token_id" label="Token azonosító" rules={[{ required: true }]}><Input /></Form.Item>}
      <Form.Item name="avatar" label="Avatar"><AvatarUpload /></Form.Item>
      <Button htmlType="submit" loading={busy}>Résztvevő hozzáadása</Button>
    </Form>
    </Drawer>
  </main>;
}
