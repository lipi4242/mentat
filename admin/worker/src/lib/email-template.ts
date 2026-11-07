/**
 * Reusable HTML shell for transactional mail (today: sign-in OTP; later: case
 * notices, reminders). Table-based layout + inline styles — the only
 * combination that renders consistently in Gmail, Outlook, and Apple Mail.
 * No banner image: the product ships no hosted asset, and a broken <img> in
 * a login email is worse than none.
 *
 * NEW MAIL TYPE: don't copy the shell — call `renderTransactionalEmail` with
 * a new body (see `email.ts` → `otpEmail`).
 */

import type { Brand } from '../types';

export const BRAND_TAGLINE = 'admin';

/** The site's bare host for display, e.g. `https://admin.example.com/` →
 *  `admin.example.com`. Falls back to the raw string if it isn't a URL. */
export function siteHost(siteUrl: string): string {
  try {
    return new URL(siteUrl).host;
  } catch {
    return siteUrl;
  }
}

const BG = '#FAFAF9';
const SURFACE = '#FFFFFF';
const INK = '#292524';
const MUTED = '#57534E';
const LIGHT = '#78716C';
const PRIMARY = '#A05A48';
const GOLD = '#B08D55';
const GOLD_LIGHT = '#E8DCC8';
const BORDER = '#E7E5E4';
const SERIF = "Georgia, 'Times New Roman', serif";
const SANS = "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";

/**
 * EVERY `*Html` field is interpolated RAW — no escaping. Only ever pass
 * copy we authored ourselves; NEVER user input.
 */
export interface TransactionalEmailOptions {
  /** Big heading, e.g. "Your sign-in code". */
  heading: string;
  /** One-line intro under the heading, centered. */
  introHtml?: string;
  /** Left-aligned body block for longer copy. */
  bodyHtml?: string;
  /** The code — large, spaced out, in a bordered box. */
  code?: string;
  /** Small note under the code (e.g. expiry). */
  afterCodeHtml?: string;
  /** Faint "if this wasn't you" block at the bottom, above a thin divider. */
  footnoteHtml?: string;
}

const codeBlock = (code: string): string => `
  <tr><td style="padding:10px 32px 0;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:${GOLD_LIGHT};border:1px solid ${GOLD};border-radius:14px;">
      <tr><td align="center" style="padding:24px 12px;font-family:${SANS};font-size:34px;line-height:1;font-weight:700;letter-spacing:14px;text-indent:14px;color:${PRIMARY};">${code}</td></tr>
    </table>
  </td></tr>`;

const footnoteBlock = (html: string): string => `
  <tr><td style="padding:8px 32px 0;"><hr style="border:none;border-top:1px solid ${BORDER};margin:26px 0 20px;"/></td></tr>
  <tr><td style="padding:0 32px;font-family:${SANS};font-size:13px;line-height:20px;color:${MUTED};">${html}</td></tr>`;

export function renderTransactionalEmail(o: TransactionalEmailOptions, b: Brand): string {
  const title = b.siteUrl
    ? `<a href="${b.siteUrl}" target="_blank" style="color:${INK};text-decoration:none;">${b.name}</a>`
    : b.name;
  const footerLink = b.siteUrl
    ? `<br/>\n    <a href="${b.siteUrl}" target="_blank" style="color:${PRIMARY};text-decoration:none;">${siteHost(b.siteUrl)}</a>`
    : '';
  return `<!doctype html>
<html lang="hu"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="color-scheme" content="light"/>
<title>${o.heading}</title></head>
<body style="margin:0;padding:0;background:${BG};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:${BG};">
<tr><td align="center" style="padding:24px 12px 40px;">
<table role="presentation" width="480" cellpadding="0" cellspacing="0" style="width:480px;max-width:480px;background:${SURFACE};border:1px solid ${BORDER};border-radius:18px;overflow:hidden;">

  <tr><td align="center" style="padding:32px 32px 0;font-family:${SERIF};font-size:27px;line-height:1;letter-spacing:1px;color:${INK};">
    ${title}
  </td></tr>
  <tr><td align="center" style="padding:7px 32px 0;font-family:${SANS};font-size:11px;line-height:1;letter-spacing:3px;text-transform:uppercase;color:${LIGHT};">${BRAND_TAGLINE}</td></tr>

  <tr><td align="center" style="padding:26px 32px 0;font-family:${SERIF};font-size:24px;line-height:31px;font-weight:700;color:${INK};">${o.heading}</td></tr>

  ${o.introHtml ? `<tr><td align="center" style="padding:12px 32px 0;font-family:${SANS};font-size:15px;line-height:23px;color:${MUTED};">${o.introHtml}</td></tr>` : ''}

  ${o.bodyHtml ? `<tr><td align="left" style="padding:20px 32px 0;font-family:${SANS};font-size:15px;line-height:23px;color:${INK};">${o.bodyHtml}</td></tr>` : ''}

  ${o.code ? codeBlock(o.code) : ''}

  ${o.afterCodeHtml ? `<tr><td align="center" style="padding:14px 32px 0;font-family:${SANS};font-size:13px;line-height:20px;color:${LIGHT};">${o.afterCodeHtml}</td></tr>` : ''}

  ${o.footnoteHtml ? footnoteBlock(o.footnoteHtml) : ''}

  <tr><td style="padding:32px 32px 0;"><hr style="border:none;border-top:1px solid ${BORDER};margin:0 0 18px;"/></td></tr>
  <tr><td align="center" style="padding:0 32px 30px;font-family:${SANS};font-size:12px;line-height:19px;color:${LIGHT};">
    <strong style="color:${MUTED};font-weight:600;">${b.name}</strong>${footerLink}
  </td></tr>

</table>
</td></tr>
</table>
</body></html>`;
}
