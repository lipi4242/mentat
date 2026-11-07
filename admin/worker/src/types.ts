// Single Env declaration — every route and lib imports from here.
export type Env = {
  DB: D1Database;
  ALLOWED_ORIGINS?: string;
  ADMIN_EMAILS?: string;
  OTP_SENDER?: string;
  // Instance branding (wrangler [vars], from the instance file on deploy).
  INSTANCE_TITLE?: string;
  SITE_URL?: string;
  BETTER_AUTH_SECRET?: string;
  BETTER_AUTH_URL?: string;
  RESEND_API_KEY?: string;
  // test switch: do not send OTP mail, just log it
  OTP_DRY_RUN?: string;
};

/** Who performed a write — carried into a plugin's audit trail (e.g. cases_event). */
export type Actor = { actor: 'user' | 'agent'; actorTokenId: string | null };

export type AppEnv = { Bindings: Env; Variables: { actor: Actor } };

export function adminEmails(env: Env): string[] {
  return (env.ADMIN_EMAILS ?? '')
    .split(',')
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);
}

/** Product default when an instance sets no INSTANCE_TITLE. */
export const DEFAULT_TITLE = 'Mentat Admin';

/** How this installation names itself in mail. Instance data, from [vars]. */
export type Brand = { name: string; siteUrl?: string };

export function brand(env: Env): Brand {
  const siteUrl = env.SITE_URL?.trim();
  return { name: env.INSTANCE_TITLE?.trim() || DEFAULT_TITLE, ...(siteUrl ? { siteUrl } : {}) };
}

/** The mailbox outgoing mail is sent from (email.ts builds the Resend `from`
 *  as `<brand> <this>`). Its domain must be verified in the Resend account,
 *  otherwise Resend rejects the send.
 *
 *  There is deliberately no product default: the sender is instance data, and
 *  a fallback address would be some other installation's mailbox. Blank
 *  counts as unset — `??` alone let an empty OTP_SENDER through and produced
 *  `Brand <>`, which Resend rejects with a bare 422 that points at nothing. */
export function senderAddress(env: Env): string {
  const sender = env.OTP_SENDER?.trim();
  if (!sender) throw new Error('OTP_SENDER missing — set it in the instance file');
  return sender;
}
