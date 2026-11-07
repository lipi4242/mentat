import { useEffect, useState } from 'react';
import { Alert, Form, Input, Modal, Select } from 'antd';
import { apiSend } from '../../lib/api';
import { CrudFields } from '../../components/crud/CrudFields';
import { toFieldSpec } from '../../components/crud/fromModel';
import { normalizeValues } from '../../components/crud/values';
import type { ModelField } from '../../lib/useModels';
import { STATUS, type CaseRow } from './meta';
import { newUlid } from './ulid';

/** null = closed; `{}` = create; a row = edit that row. */
export type FormTarget = null | { row?: CaseRow };

const DATE = /^\d{4}-\d{2}-\d{2}$/;
const TEXT = ['title', 'description', 'next_action', 'brain_ref'] as const;

/**
 * Create and edit through the one write path the agent uses too: PUT to the
 * case's ULID. An edit sends the version it read, so a change made in the
 * meantime (by the agent) is a 409 here, not a silent overwrite. A recurring
 * case's due date is computed by the server and is not sent; the brain
 * context is the agent's mirror and is never sent from here. `own` are the
 * instance's own case fields (GET /api/meta): drawn and sent like the rest.
 */
export function CaseFormModal({ target, onClose, onSaved, own = [] }: { target: FormTarget; onClose: () => void; onSaved: (id: string) => void; own?: ModelField[] }) {
  const [form] = Form.useForm();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const row = target?.row;
  const recurrence = Form.useWatch('recurrence', form) as string | undefined;

  useEffect(() => {
    if (!target) return;
    setError(null);
    form.resetFields();
    form.setFieldsValue(row ?? { status: 'open' });
  }, [target, row, form]);

  const submit = async () => {
    const v = await form.validateFields();
    const body: Record<string, unknown> = { status: v.status };
    for (const k of TEXT) body[k] = v[k]?.trim() || null;
    body.title = v.title.trim();
    const rec = v.recurrence?.trim() || null;
    body.recurrence = rec;
    body.anchor_at = v.anchor_at || null;
    if (!rec) body.due_at = v.due_at || null;
    Object.assign(body, normalizeValues(v, own.map(toFieldSpec), row ? 'edit' : 'create'));
    if (row) body.version = row.version;
    const id = row?.id ?? newUlid();
    setBusy(true);
    try {
      await apiSend('PUT', `/api/cases/${id}`, body);
      onSaved(id);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'A mentés nem sikerült.');
    } finally {
      setBusy(false);
    }
  };

  const date = { pattern: DATE, message: 'ÉÉÉÉ-HH-NN alakban' };
  return (
    <Modal open={!!target} destroyOnClose title={row ? 'Ügy szerkesztése' : 'Új ügy'} okText="Mentés" cancelText="Mégse" confirmLoading={busy} onOk={submit} onCancel={onClose}>
      {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}
      <Form form={form} layout="vertical">
        <Form.Item name="title" label="Cím" rules={[{ required: true, whitespace: true, message: 'Mi az ügy?' }]}>
          <Input />
        </Form.Item>
        <Form.Item name="status" label="Állapot">
          <Select options={Object.entries(STATUS).map(([value, s]) => ({ value, label: s.label }))} />
        </Form.Item>
        <Form.Item name="description" label="Leírás">
          <Input.TextArea rows={2} placeholder="miről szól, egy-két mondatban" />
        </Form.Item>
        <Form.Item name="next_action" label="Következő lépés" extra="akár: várunk a biztosítóra">
          <Input placeholder="egy mondat" />
        </Form.Item>
        <Form.Item name="recurrence" label="Ismétlődés" extra="monthly:10 · quarterly:20 (az első esedékesség hónapjától) · yearly:05-20 · weekly:mon — üresen: egyszeri">
          <Input />
        </Form.Item>
        {recurrence?.trim() ? (
          <Form.Item name="anchor_at" label="Első esedékesség" rules={[{ required: true, message: 'Ismétlődéshez kell' }, date]}>
            <Input placeholder="2026-10-10" />
          </Form.Item>
        ) : (
          <Form.Item name="due_at" label="Határidő" rules={[date]}>
            <Input placeholder="2026-10-10" />
          </Form.Item>
        )}
        <CrudFields fields={own.map(toFieldSpec)} enforceRequired={!row} />
        <Form.Item name="brain_ref" label="Agy-fájl" extra="pl. agy/cases/gazszamla.md">
          <Input />
        </Form.Item>
      </Form>
    </Modal>
  );
}
