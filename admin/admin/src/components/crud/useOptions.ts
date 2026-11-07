import { useMemo } from 'react';
import { useList } from '@refinedev/core';

/**
 * Select options for a foreign key. Every id in this schema is a UUID, so a
 * raw text input for `case_id` / `supplier_id` / `offer_id` would be a
 * copy-paste exercise — the list endpoints are unpaginated anyway, so the
 * whole table is one request.
 */
export function useOptions(
  resource: string,
  labelOf: (row: Record<string, any>) => string,
): { value: string; label: string }[] {
  const { data } = useList<Record<string, any>>({ resource, pagination: { mode: 'off' } });
  return useMemo(
    () => (data?.data ?? []).map((r) => ({ value: String(r.id), label: labelOf(r) })),
    // labelOf is defined inline at every call site, so it is a new function on
    // every render — depending on it would defeat the memo entirely.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [data],
  );
}
