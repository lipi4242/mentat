import { Checkbox, Form, Input, InputNumber, Select } from 'antd';
import { selectOptions, type FieldSpec } from './values';
import { useOptions } from './useOptions';

/** The first non-id string value of a row — what a reference shows instead of a UUID. */
const labelOf = (row: Record<string, unknown>) =>
  String(Object.entries(row).find(([k, v]) => k !== 'id' && typeof v === 'string' && v)?.[1] ?? row.id);

/** antd passes `value`/`onChange` through Form.Item; the options come from the referenced list. */
function RefSelect({ resource, ...rest }: { resource: string; value?: unknown; onChange?: (v: unknown) => void }) {
  const options = useOptions(resource, labelOf);
  return <Select allowClear showSearch optionFilterProp="label" options={options} {...rest} />;
}

/**
 * Renders a FieldSpec list as antd Form.Items. `required` only guards the
 * create path — a PATCH body is legitimately partial on the worker side, so
 * the edit modal passes `enforceRequired={false}` and lets a cleared field
 * become an explicit null.
 */
export function CrudFields({ fields, enforceRequired }: { fields: readonly FieldSpec[]; enforceRequired: boolean }) {
  return (
    <>
      {fields.map((f) => (
        <Form.Item
          key={f.name}
          name={f.name}
          label={f.label}
          valuePropName={f.type === 'checkbox' ? 'checked' : undefined}
          rules={enforceRequired && f.required ? [{ required: true, message: 'Kötelező mező' }] : undefined}
        >
          {f.type === 'number' ? (
            <InputNumber style={{ width: '100%' }} placeholder={f.placeholder} min={f.min} />
          ) : f.type === 'textarea' ? (
            <Input.TextArea rows={3} placeholder={f.placeholder} />
          ) : f.type === 'select' ? (
            <Select allowClear options={selectOptions(f)} placeholder={f.placeholder} showSearch optionFilterProp="label" />
          ) : f.type === 'ref' && f.ref ? (
            <RefSelect resource={f.ref} />
          ) : f.type === 'checkbox' ? (
            <Checkbox>{f.placeholder ?? 'Igen'}</Checkbox>
          ) : (
            <Input placeholder={f.placeholder} />
          )}
        </Form.Item>
      ))}
    </>
  );
}
