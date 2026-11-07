import { useCallback, useEffect, useState } from 'react';
import { apiGet } from './api';

export type ApiState<T> = { data: T | null; error: Error | null; loading: boolean; reload: () => void };

/**
 * Read one non-CRUD endpoint (e.g. `/api/needs/:id/coverage`).
 *
 * Not Refine's `useCustom`: `dataProvider` deliberately implements only
 * getList/getOne/create/update, so `useCustom` would call a `custom` method
 * that does not exist. This goes straight through `apiGet`, which already
 * carries the session cookie and maps statuses to Hungarian messages.
 *
 * A `null` path means "nothing to fetch yet" (the id is still undefined) and
 * leaves the hook idle rather than requesting `/api/needs/undefined/coverage`.
 */
export function useApi<T>(path: string | null): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(path !== null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (path === null) {
      setLoading(false);
      return;
    }
    // A response that arrives after the path changed (or after unmount) must
    // not overwrite the newer one — last request wins, not last response.
    let live = true;
    setLoading(true);
    apiGet<T>(path)
      .then((d) => {
        if (!live) return;
        setData(d);
        setError(null);
      })
      .catch((e: unknown) => {
        if (!live) return;
        setError(e instanceof Error ? e : new Error(String(e)));
        setData(null);
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [path, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { data, error, loading, reload };
}
