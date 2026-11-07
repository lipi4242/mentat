// Dev: empty, so the Vite /api proxy reaches the local worker (same-origin cookie).
// Prod: the build runs with VITE_API_URL (e.g. https://api.example.com).
export const API_BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/+$/, '');

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}
