// lib/telegram.mjs — a hid Bot API klense (GET, query-parameterekkel).
// timeoutMs alap 30 s; a getUpdates a hosszu-poll `timeout` folotti erteket
// kap a hivotol. AbortSignal nelkul egy elakadt fetch orokre fagyasztana a
// pollert — systemd szerint `active`, valojaban nema.
export function createTelegram(token, base = "https://api.telegram.org") {
  const api = `${base}/bot${token}`;
  async function tg(method, params, timeoutMs = 30_000) {
    const url = new URL(`${api}/${method}`);
    for (const [k, v] of Object.entries(params || {})) {
      url.searchParams.set(k, typeof v === "string" ? v : JSON.stringify(v));
    }
    const res = await fetch(url, { method: "GET", signal: AbortSignal.timeout(timeoutMs) });
    return { status: res.status, body: await res.json() };
  }
  return { tg, fileApi: `${base}/file/bot${token}` };
}
