// OTP email delivery via Resend (https://resend.com). Resend takes a JSON
// body — `from`/`to`/`subject`/`text`/`html` — so there is no MIME assembly,
// no base64 bodies and no RFC 2047 header encoding here: the provider builds
// the message. This file owns message content and the send/dry-run decision.
//
// This throws on any real delivery failure rather than pretending the code
// was sent — but the throw never reaches the client. better-auth wraps the
// call in `runInBackgroundOrAwait`, which without an
// `advanced.backgroundTasks.handler` (we configure none, see better-auth.ts)
// *awaits* this inline inside its own try/catch and then returns
// `{success:true}` regardless. Two consequences worth knowing while
// debugging: the sign-in request really does wait for Resend, so a provider
// outage shows up as a slow login, not a fast one; and the only trace of the
// failure is a log line — ours (`otp-delivery-failed`) plus better-auth's
// own "Failed to run background task". The only path that skips sending
// entirely is the OTP_DRY_RUN switch, and it is itself gated to local dev
// (see sendOtpEmail) so it can't silently swallow codes in production.
import { brand, senderAddress, type Brand, type Env } from '../types';
import { renderTransactionalEmail, siteHost } from './email-template';

const RESEND_ENDPOINT = 'https://api.resend.com/emails';

/** The sign-in code email — plain text and HTML variants. */
export function otpEmail(otp: string, b: Brand): { subject: string; text: string; html: string } {
  const BRAND_NAME = b.name;
  const subject = `Belépési kód — ${BRAND_NAME}`;
  const text = [
    'Belépési kódod',
    '',
    `Ezzel a kóddal tudsz belépni a ${BRAND_NAME} felületre:`,
    '',
    `    ${otp}`,
    '',
    'A kód 5 percig érvényes.',
    '',
    'Ha nem te kérted: valaki megadta ezt az e-mail-címet belépéskor. A kód',
    'nélkül nem tudnak belépni — nyugodtan hagyd figyelmen kívül ezt a levelet,',
    'és ne oszd meg a kódot senkivel.',
    '',
    b.siteUrl ? `${BRAND_NAME} · ${siteHost(b.siteUrl)}` : BRAND_NAME,
  ].join('\r\n');
  const html = renderTransactionalEmail({
    heading: 'Belépési kódod',
    introHtml: `Ezzel a kóddal tudsz belépni a <strong style="color:#292524;">${BRAND_NAME}</strong> felületre:`,
    code: otp,
    afterCodeHtml: 'A kód 5 percig érvényes.',
    footnoteHtml:
      '<strong>Ha nem te kérted:</strong> valaki megadta ezt az e-mail-címet belépéskor. ' +
      'A kód nélkül nem tudnak belépni — nyugodtan hagyd figyelmen kívül ezt a levelet, ' +
      'és ne oszd meg a kódot senkivel.',
  }, b);
  return { subject, text, html };
}

/** OTP_DRY_RUN only ever applies against a local BETTER_AUTH_URL. Without
 *  this second condition, setting the var on the deployed Worker would make
 *  login look completely healthy while every code went only to a log line
 *  readable by anyone with dashboard access — silently converting a
 *  secret-delivery system into a secret-publishing one.
 *
 * Unset counts as production: BETTER_AUTH_URL is a separately-set secret,
 * and nothing else in the app fails loudly without it (createAuth() quietly
 * defaults it to localhost, index.ts gates on BETTER_AUTH_SECRET instead) —
 * so "missing" must not be the condition that re-enables code-to-log. Local
 * `wrangler dev` needs BETTER_AUTH_URL set explicitly (e.g. in .dev.vars)
 * for the dry-run bypass to apply. */
export function isLocalEnv(env: Env): boolean {
  // A plain startsWith('http://localhost') would also match
  // http://localhost.evil.com (a remote host) while missing
  // http://127.0.0.1:8787 (also local) — require a delimiter (or end of
  // string) right after the hostname so the match is exact.
  return /^http:\/\/(localhost|127\.0\.0\.1)([:/]|$)/.test(env.BETTER_AUTH_URL ?? '');
}

export async function sendOtpEmail(env: Env, to: string, otp: string): Promise<void> {
  try {
    const isLocal = isLocalEnv(env);
    if (env.OTP_DRY_RUN === '1') {
      if (!isLocal) throw new Error('OTP_DRY_RUN is set outside local development');
      console.log(`[otp dry-run] to=${to} otp=${otp}`);
      return;
    }
    if (!env.RESEND_API_KEY) {
      // Same reasoning as the dry-run gate: a missing key on a deployment must
      // never degrade into "code goes to the log instead of the mailbox".
      if (!isLocal) throw new Error('RESEND_API_KEY missing on a non-local deployment');
      console.log(`[otp no-key] to=${to} otp=${otp}`);
      return;
    }
    await resendSend(env, to, otpEmail(otp, brand(env)));
  } catch (err) {
    // Distinct, greppable marker: better-auth runs this as a background
    // task, so the thrown error never reaches the client — this log line is
    // the only trace of a total delivery outage.
    console.error('otp-delivery-failed', err);
    throw err;
  }
}

export type Mail = { subject: string; text: string; html: string };

/** The one Resend call: the OTP mail and every other notice (e.g. the fleet
 *  check's escalation mail) go through here. Throws on a non-2xx.
 *
 *  Header injection is structurally impossible here: `to` is a JSON string
 *  value, so a CR/LF inside it is escaped as \r\n data and reaches Resend as
 *  part of the address — it can never start a new header.
 *
 *  Deliberately NOT including res.text() in the error. Resend's validation
 *  errors quote the offending field, and for the OTP mail the fields carrying
 *  the code are `text` and `html` — echoing the body back would put the OTP
 *  into this error message and from there into the Worker log. The status
 *  alone distinguishes the realistic failures (401 key, 403 unverified domain,
 *  422 payload, 429 rate limit). */
export async function resendSend(env: Env, to: string, mail: Mail): Promise<void> {
  const from = `${brand(env).name} <${senderAddress(env)}>`;
  const res = await fetch(RESEND_ENDPOINT, {
    method: 'POST',
    headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ from, to: [to], subject: mail.subject, text: mail.text, html: mail.html }),
  });
  if (!res.ok) throw new Error(`resend send failed: ${res.status}`);
}

/** A non-OTP notice. No key: on local dev it is logged (subject only), on a
 *  deployment it throws — the caller records the failure and retries. */
export async function sendNotice(env: Env, to: string, mail: Mail): Promise<'sent' | 'logged'> {
  if (!env.RESEND_API_KEY) {
    if (!isLocalEnv(env)) throw new Error('RESEND_API_KEY missing on a non-local deployment');
    console.log(`[notice no-key] to=${to} subject=${mail.subject}`);
    return 'logged';
  }
  await resendSend(env, to, mail);
  return 'sent';
}
