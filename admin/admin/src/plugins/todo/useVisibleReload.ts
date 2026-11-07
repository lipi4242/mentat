import { useEffect } from 'react';
export function useVisibleReload(reload: () => void) {
  useEffect(() => {
    const visible = () => { if (document.visibilityState === 'visible') reload(); };
    document.addEventListener('visibilitychange', visible);
    return () => document.removeEventListener('visibilitychange', visible);
  }, [reload]);
}
