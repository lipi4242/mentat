import { apiUrl } from '../config';

/**
 * Human-readable message per HTTP status.
 *
 * Not every error means "sign in again" — a 500 is a system error unrelated
 * to the session, and treating it as an auth failure would send the user
 * into a pointless re-login loop.
 */
export function httpMessage(status: number): string {
  if (status === 400) return 'Érvénytelen kérés — hiányzó vagy hibás mező.';
  if (status === 401) return 'Lejárt a belépésed — jelentkezz be újra.';
  if (status === 403) return 'Ehhez nincs jogosultságod.';
  if (status === 404) return 'Nincs ilyen tétel — lehet, hogy időközben lezárult.';
  if (status === 409) return 'Ütközés — a hivatkozott tétel nem létezik vagy időközben megváltozott.';
  if (status === 422) return 'A szerver nem fogadta el az adatot.';
  if (status === 429) return 'Túl sok próbálkozás — várj egy kicsit, aztán próbáld újra.';
  if (status >= 500) return 'Rendszerhiba — próbáld újra pár perc múlva.';
  return `Váratlan hiba (${status}).`;
}

/** Lets the caller (e.g. a 404 empty-state) distinguish error kinds by status. */
export class ApiError extends Error {
  constructor(
    readonly statusCode: number,
    message: string = httpMessage(statusCode),
    /** The parsed error body, when there was one (e.g. a 409's current `version`). */
    readonly body: unknown = null,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * A failed response as an ApiError. A 409 or 422 is the caller's own mistake
 * and the worker's `error` text names the field or date to fix, so it is
 * appended; every other status keeps only the generic Hungarian message.
 */
async function failure(res: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = JSON.parse(await res.text());
  } catch {
    body = null;
  }
  const detail = body && typeof (body as { error?: unknown }).error === 'string' ? (body as { error: string }).error : null;
  const own = detail && (res.status === 409 || res.status === 422);
  return new ApiError(res.status, own ? `${httpMessage(res.status)} (${detail})` : httpMessage(res.status), body);
}

/**
 * Reads a JSON body defensively.
 *
 * An OK status is no guarantee of JSON: a misrouted `/api/*` request falls
 * through to the SPA and comes back as `index.html` with a 200, and an empty
 * body (204, or a write that returns nothing) is not parseable either. Both
 * used to escape as a raw `SyntaxError` — internal noise shown to the user
 * instead of the Hungarian messages above.
 */
async function readJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!text.trim()) return null as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError(res.status, 'A szerver váratlan választ küldött — frissíts rá, és ha marad, szólj.');
  }
}

async function request(path: string): Promise<Response> {
  const res = await fetch(apiUrl(path), { credentials: 'include' });
  if (!res.ok) throw await failure(res);
  return res;
}

/**
 * Shared JSON request — carries the session cookie, uniform error handling.
 *
 * `credentials: 'include'` is REQUIRED: the worker's admin routes only
 * accept a better-auth session, not the agent token. Without the cookie,
 * every call comes back 401.
 */
export async function requestJson<T>(method: string, path: string, body?: unknown): Promise<T> {
  const hasBody = body !== undefined;
  const res = await fetch(apiUrl(path), {
    method,
    credentials: 'include',
    headers: hasBody ? { 'Content-Type': 'application/json' } : undefined,
    body: hasBody ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw await failure(res);
  return readJson<T>(res);
}

/** Shared read fetch. */
export async function apiGet<T>(path: string): Promise<T> {
  return readJson<T>(await request(path));
}

/** Same, but also returns the total-count header used for pagination. */
export async function apiGetWithTotal<T>(path: string): Promise<{ items: T; total: number }> {
  const res = await request(path);
  const items = await readJson<T>(res);
  // A missing or non-numeric header must not become a NaN total — antd's
  // pagination renders nothing at all for one.
  const raw = res.headers.get('X-Total-Count');
  const parsed = raw === null ? Number.NaN : Number(raw);
  const total = Number.isFinite(parsed) ? parsed : Array.isArray(items) ? items.length : 0;
  return { items, total };
}

/**
 * Write helper for plugin UI code outside the Refine dataProvider (e.g. a
 * one-off action button that isn't a plain create/update).
 */
export async function apiSend<T>(
  method: 'POST' | 'PUT' | 'PATCH',
  path: string,
  body: unknown,
): Promise<T> {
  return requestJson<T>(method, path, body ?? null);
}
