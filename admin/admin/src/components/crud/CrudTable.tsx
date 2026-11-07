import { useState, type ReactNode } from 'react';
import { useList } from '@refinedev/core';
import { Alert, Button, Space, Table, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { CrudFormModal, type EditTarget } from './CrudFormModal';
import { ArchiveButton } from './ArchiveButton';
import type { FieldSpec, FormValues } from './values';

type Row = Record<string, any>;

type Props = {
  resource: string;
  /** Singular, lowercase-able noun used in the button and modal titles. */
  title: string;
  heading?: string;
  fields: readonly FieldSpec[];
  columns: ColumnsType<Row>;
  /** Client-side: the worker's list endpoints have no filter parameter. */
  filter?: (row: Row) => boolean;
  fixed?: FormValues;
  archivable?: boolean;
  onChanged?: () => void;
  rowActions?: (row: Row, reload: () => void) => ReactNode;
};

/**
 * List + create + edit for one worker table.
 *
 * Paging is client-side on purpose: `worker/src/core/crud.ts` has no LIMIT
 * and `dataProvider.getList` returns the whole array, so sending paging
 * params would only describe a request nothing on the other side reads.
 */
export function CrudTable({
  resource,
  title,
  heading,
  fields,
  columns,
  filter,
  fixed,
  archivable,
  onChanged,
  rowActions,
}: Props) {
  const { data, isLoading, isError, error, refetch } = useList<Row>({ resource, pagination: { mode: 'off' } });
  const [target, setTarget] = useState<EditTarget>(null);

  const reload = () => {
    void refetch();
    onChanged?.();
  };

  const rows = (data?.data ?? []).filter((r) => (filter ? filter(r) : true));
  const actions: ColumnsType<Row> = [
    {
      title: '',
      key: 'actions',
      width: 1,
      render: (_: unknown, row: Row) => (
        <Space size="small">
          {rowActions?.(row, reload)}
          <Button size="small" onClick={() => setTarget({ mode: 'edit', record: row })}>
            Szerkesztés
          </Button>
          {archivable ? <ArchiveButton resource={resource} id={String(row.id)} onDone={reload} /> : null}
        </Space>
      ),
    },
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Space style={{ justifyContent: 'space-between', width: '100%' }}>
        {heading ? <Typography.Title level={5} style={{ margin: 0 }}>{heading}</Typography.Title> : <span />}
        <Button type="primary" onClick={() => setTarget({ mode: 'create' })}>
          {`Új ${title.toLowerCase()}`}
        </Button>
      </Space>
      {isError ? (
        <Alert
          type="error"
          showIcon
          message={error instanceof Error ? error.message : 'A lista betöltése nem sikerült.'}
        />
      ) : null}
      <Table<Row>
        rowKey="id"
        size="small"
        loading={isLoading}
        dataSource={rows}
        columns={[...columns, ...actions]}
        pagination={rows.length > 20 ? { pageSize: 20, showSizeChanger: false } : false}
        locale={{ emptyText: 'Még nincs egy sem.' }}
      />
      <CrudFormModal
        resource={resource}
        title={title}
        fields={fields}
        target={target}
        fixed={fixed}
        onClose={() => setTarget(null)}
        onSaved={reload}
      />
    </Space>
  );
}
