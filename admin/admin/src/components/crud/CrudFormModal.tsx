import { useEffect, useState } from 'react';
import { App, Form, Modal } from 'antd';
import { useCreate, useUpdate } from '@refinedev/core';
import { CrudFields } from './CrudFields';
import { normalizeValues, type FieldSpec, type FormValues } from './values';

export type EditTarget = { mode: 'create' } | { mode: 'edit'; record: Record<string, unknown> } | null;

type Props = {
  resource: string;
  title: string;
  fields: readonly FieldSpec[];
  target: EditTarget;
  onClose: () => void;
  onSaved?: () => void;
  /** Merged into every create body — e.g. `need_id` on a need's detail page. */
  fixed?: FormValues;
};

/**
 * The single create/edit dialog behind every table here. One component rather
 * than a modal per screen so the create/edit body rules in `normalizeValues`
 * are applied in exactly one place.
 */
export function CrudFormModal({ resource, title, fields, target, onClose, onSaved, fixed }: Props) {
  const [form] = Form.useForm();
  const { message } = App.useApp();
  const { mutate: create } = useCreate();
  const { mutate: update } = useUpdate();
  // Guards a double submit: the modal stays open until the request settles,
  // and OK is clickable throughout.
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!target) return;
    form.resetFields();
    if (target.mode === 'edit') form.setFieldsValue(target.record);
  }, [target, form]);

  const submit = async () => {
    if (saving || !target) return;
    let raw: FormValues;
    try {
      raw = await form.validateFields();
    } catch {
      return; // antd already marks the offending fields
    }
    setSaving(true);
    const values = { ...normalizeValues(raw, fields, target.mode), ...(target.mode === 'create' ? fixed : undefined) };
    const done = {
      onSuccess: () => {
        setSaving(false);
        onClose();
        onSaved?.();
      },
      onError: (e: unknown) => {
        setSaving(false);
        message.error(e instanceof Error ? e.message : 'A mentés nem sikerült.');
      },
    };
    if (target.mode === 'create') create({ resource, values }, done);
    else update({ resource, id: String(target.record.id), values }, done);
  };

  return (
    <Modal
      open={target !== null}
      title={target?.mode === 'edit' ? `${title} szerkesztése` : `Új ${title.toLowerCase()}`}
      okText="Mentés"
      cancelText="Mégse"
      confirmLoading={saving}
      onOk={submit}
      onCancel={() => !saving && onClose()}
      destroyOnClose
    >
      <Form form={form} layout="vertical" preserve={false}>
        <CrudFields fields={fields} enforceRequired={target?.mode === 'create'} />
      </Form>
    </Modal>
  );
}
