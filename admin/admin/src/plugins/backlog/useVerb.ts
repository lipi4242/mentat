import { useState } from 'react';
import { apiSend, ApiError } from '../../lib/api';
import { API, type Item } from './meta';
/** One state-machine call with the item's rev; a 409 reloads instead of failing loudly. */
export function useVerb(item: Pick<Item, 'id' | 'rev'>, reload: () => void) {
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const run = async (verb: string, payload: Record<string, unknown> = {}) => {
    setBusy(true); setError('');
    try { await apiSend('POST', `${API}/items/${item.id}/${verb}`, { ...payload, expected_rev: item.rev }); reload(); return true; }
    catch (e) {
      setError(e instanceof ApiError && e.statusCode === 409 ? 'Közben valaki módosította, frissítettem.' : (e as Error).message);
      if (e instanceof ApiError && e.statusCode === 409) reload();
      return false;
    } finally { setBusy(false); }
  };
  return { run, error, busy };
}
