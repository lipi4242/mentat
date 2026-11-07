import { useState } from 'react';
import { Alert, App, Form, Input, InputNumber, Modal, Typography } from 'antd';
import { apiSend } from '../../lib/api';

export type Minted = { id: string; label: string; scopes: string; expires_at: string; token: string };

/**
 * Two steps in one modal: the form, then the token — shown exactly once.
 * The worker keeps only the hash, so closing this is the last chance to
 * copy it; nothing in the app can show it again.
 */
export function MintTokenModal({ open, onClose }: { open: boolean; onClose: (minted: boolean) => void }) {
  const [form] = Form.useForm();
  const [busy, setBusy] = useState(false);
  const [minted, setMinted] = useState<Minted | null>(null);
  const { message } = App.useApp();

  const submit = async () => {
    const values = await form.validateFields();
    setBusy(true);
    try {
      setMinted(await apiSend<Minted>('POST', '/api/tokens', values));
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'A token kiadása nem sikerült.');
    } finally {
      setBusy(false);
    }
  };

  const close = () => {
    const done = minted !== null;
    setMinted(null);
    form.resetFields();
    onClose(done);
  };

  if (minted) {
    return (
      <Modal key="reveal" open={open} destroyOnClose title="Az új token" okText="Elmentettem" cancelButtonProps={{ style: { display: 'none' } }} onOk={close} onCancel={close}>
        <Alert type="warning" showIcon message="Most látod utoljára — másold az ágens .env fájljába (0600)." style={{ marginBottom: 16 }} />
        <Typography.Paragraph copyable code data-testid="minted-token">
          {minted.token}
        </Typography.Paragraph>
        <Typography.Text type="secondary">
          {minted.label} · {minted.scopes} · lejár: {minted.expires_at} UTC
        </Typography.Text>
      </Modal>
    );
  }

  return (
    <Modal key="form" open={open} destroyOnClose title="Új gépi token" okText="Kiadás" cancelText="Mégse" confirmLoading={busy} onOk={submit} onCancel={close}>
      <Form form={form} layout="vertical" initialValues={{ scopes: 'cases:write', days: 90 }}>
        <Form.Item name="label" label="Ágens" rules={[{ required: true, message: 'Melyik ágensé?' }]}>
          <Input placeholder="pl. agent1" />
        </Form.Item>
        <Form.Item name="scopes" label="Hatókörök (szóközzel)" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item name="days" label="Érvényesség (nap, legfeljebb 365)" rules={[{ required: true }]}>
          <InputNumber min={1} max={365} />
        </Form.Item>
      </Form>
    </Modal>
  );
}
