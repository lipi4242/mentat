// lib/webhook-config.mjs — a jovahagyo webhook (3.1) env-szerzodese.
// URL nelkul csendesen KI. Hibas beallitas: KI, okkal — a hid ettol fut tovabb.
// A `reason` SOSEM tartalmazza a tokent vagy az URL-t (a query titkot vihet).
// A tobbcelu valtozat (SUBETHA_WEBHOOKS) a lib/webhook-targets.mjs-ben; a mai
// SUBETHA_REPLY_WEBHOOK a `default` nevu cel.

// Kozos URL/token-ellenorzes: https, ervenyes URL, token kotelezo.
export function checkEndpoint(url, token, { urlName, tokenName }) {
  let u;
  try { u = new URL(url); } catch { return { enabled: false, reason: `${urlName} nem ervenyes URL` }; }
  if (u.protocol !== "https:") return { enabled: false, reason: `csak https:// engedett (kapott: ${u.protocol})` };
  if (!token) return { enabled: false, reason: `${tokenName} hianyzik` };
  return { enabled: true, url: u.href, host: u.host, token };
}

export function parseWebhookConfig(env) {
  const url = env.SUBETHA_REPLY_WEBHOOK, token = env.SUBETHA_REPLY_WEBHOOK_TOKEN;
  if (!url) return { enabled: false, reason: null };
  return checkEndpoint(url, token, { urlName: "SUBETHA_REPLY_WEBHOOK", tokenName: "SUBETHA_REPLY_WEBHOOK_TOKEN" });
}
