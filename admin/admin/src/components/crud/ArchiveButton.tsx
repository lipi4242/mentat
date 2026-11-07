import { App, Button, Popconfirm } from 'antd';
import { useUpdate } from '@refinedev/core';

/**
 * Archiving, not deleting. `dataProvider.deleteOne` rejects by design and the
 * worker has no DELETE route at all — `archived = 1` is how a row leaves the
 * listings while staying reachable by id (and while the allocations that
 * explain a purchase stay intact).
 */
export function ArchiveButton({ resource, id, onDone }: { resource: string; id: string; onDone?: () => void }) {
  const { mutate, isLoading } = useUpdate();
  const { message } = App.useApp();

  return (
    <Popconfirm
      title="Archiválod?"
      description="Eltűnik a listából, de megmarad."
      okText="Archiválás"
      cancelText="Mégse"
      onConfirm={() =>
        mutate(
          { resource, id, values: { archived: 1 } },
          {
            onSuccess: () => onDone?.(),
            onError: (e: unknown) => message.error(e instanceof Error ? e.message : 'Az archiválás nem sikerült.'),
          },
        )
      }
    >
      <Button size="small" danger loading={isLoading}>
        Archiválás
      </Button>
    </Popconfirm>
  );
}
