// Covers the whole send path with a stubbed `fetch` — no real network call is
// ever made. What is NOT covered: Resend's actual acceptance of the payload
// (domain verification, deliverability) — that only shows up in production.
import { describe, it, expect, vi, afterEach } from 'vitest';
import { otpEmail, sendOtpEmail } from '../src/lib/email';
import app from '../src/index';
import { makeEnv, jsonReq } from './helpers';
import { renderTransactionalEmail } from '../src/lib/email-template';
import { brand, type Env } from '../src/types';

const OTP = '424242';
const baseEnv = { DB: {} as Env['DB'], ADMIN_EMAILS: 'owner@example.com' };
// Instance data comes from [vars]; tests use a fixture brand, never a real one.
const BRAND = { name: 'Example Admin', siteUrl: 'https://admin.example.com' };
const SENDER = 'admin-mail@example.com';
const LOCAL = 'http://localhost:8787';
const PROD = 'https://mentat-admin-api.workers.dev';

/** Replaces global fetch; records the call and returns the given response. */
function stubFetch(res: { ok: boolean; status: number; body?: unknown }) {
  const spy = vi.fn(async () => ({
    ok: res.ok,
    status: res.status,
    text: async () => JSON.stringify(res.body ?? {}),
    json: async () => res.body ?? {},
  }));
  vi.stubGlobal('fetch', spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('otpEmail', () => {
  it('puts the code in both the plain-text and HTML variants', () => {
    const { subject, text, html } = otpEmail(OTP, BRAND);
    expect(subject).toBe('Belépési kód — Example Admin');
    expect(text).toContain(OTP);
    expect(html).toContain(OTP);
  });

  it('the footer names the instance brand and its site host', () => {
    const { text, html } = otpEmail('999999', BRAND);
    expect(text).toContain('Example Admin · admin.example.com');
    expect(html).toContain('href="https://admin.example.com"');
    expect(html).toContain('admin.example.com</a>');
  });

  it('without a SITE_URL the mail carries the name only — no link to anyone else', () => {
    const { text, html } = otpEmail('999999', { name: 'Example Admin' });
    expect(text.trimEnd().endsWith('Example Admin')).toBe(true);
    expect(html).not.toContain('href=');
  });
});

describe('brand', () => {
  it('falls back to the product name when the instance sets no title', () => {
    expect(brand({ ...baseEnv }).name).toBe('Mentat Admin');
    expect(brand({ ...baseEnv, INSTANCE_TITLE: '  ' }).name).toBe('Mentat Admin');
    expect(brand({ ...baseEnv, INSTANCE_TITLE: 'X Admin', SITE_URL: 'https://x.example' })).toEqual({
      name: 'X Admin',
      siteUrl: 'https://x.example',
    });
  });
});

describe('sendOtpEmail dry-run guard', () => {
  it('logs and returns without a network call when local', async () => {
    const f = stubFetch({ ok: true, status: 200 });
    await expect(
      sendOtpEmail({ ...baseEnv, OTP_DRY_RUN: '1', BETTER_AUTH_URL: LOCAL }, 'to@example.com', OTP),
    ).resolves.toBeUndefined();
    expect(f).not.toHaveBeenCalled();
  });

  it('treats an unset BETTER_AUTH_URL as production, not local (it is a separately-set secret)', async () => {
    await expect(sendOtpEmail({ ...baseEnv, OTP_DRY_RUN: '1' }, 'to@example.com', OTP)).rejects.toThrow(
      /outside local development/,
    );
  });

  it('refuses to silently drop the code when OTP_DRY_RUN is set outside local dev', async () => {
    await expect(
      sendOtpEmail({ ...baseEnv, OTP_DRY_RUN: '1', BETTER_AUTH_URL: PROD }, 'to@example.com', OTP),
    ).rejects.toThrow(/outside local development/);
  });

  it('does not treat a lookalike remote host (localhost.evil.com) as local', async () => {
    await expect(
      sendOtpEmail(
        { ...baseEnv, OTP_DRY_RUN: '1', BETTER_AUTH_URL: 'http://localhost.evil.com' },
        'to@example.com',
        OTP,
      ),
    ).rejects.toThrow(/outside local development/);
  });

  it('treats the loopback IP (127.0.0.1) as local too', async () => {
    await expect(
      sendOtpEmail({ ...baseEnv, OTP_DRY_RUN: '1', BETTER_AUTH_URL: 'http://127.0.0.1:8787' }, 'to@example.com', OTP),
    ).resolves.toBeUndefined();
  });
});

describe('sendOtpEmail missing RESEND_API_KEY', () => {
  it('logs and returns on a local deployment (plain `wrangler dev` with no secret)', async () => {
    const f = stubFetch({ ok: true, status: 200 });
    const log = vi.spyOn(console, 'log').mockImplementation(() => {});
    await expect(sendOtpEmail({ ...baseEnv, BETTER_AUTH_URL: LOCAL }, 'to@example.com', OTP)).resolves.toBeUndefined();
    expect(f).not.toHaveBeenCalled();
    expect(log).toHaveBeenCalled();
  });

  it('throws rather than silently dropping the code on a non-local deployment', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    await expect(sendOtpEmail({ ...baseEnv, BETTER_AUTH_URL: PROD }, 'to@example.com', OTP)).rejects.toThrow(
      /RESEND_API_KEY/,
    );
  });

  // Pins the live deployment's exact config (BETTER_AUTH_URL is the public
  // SPA origin, no key yet) — this is the branch that fires in production
  // today, so it must throw and leave the greppable log marker, never
  // return as if the mail went out.
  it('throws and logs otp-delivery-failed under the deployed config', async () => {
    const f = stubFetch({ ok: true, status: 200 });
    const err = vi.spyOn(console, 'error').mockImplementation(() => {});
    await expect(
      sendOtpEmail({ ...baseEnv, BETTER_AUTH_URL: 'https://admin.example.com' }, 'owner@example.com', OTP),
    ).rejects.toThrow('RESEND_API_KEY missing on a non-local deployment');
    expect(f).not.toHaveBeenCalled();
    expect(err.mock.calls[0][0]).toBe('otp-delivery-failed');
  });
});

describe('sendOtpEmail Resend request', () => {
  const env = {
    ...baseEnv,
    BETTER_AUTH_URL: PROD,
    RESEND_API_KEY: 'resend-test-key',
    INSTANCE_TITLE: BRAND.name,
    SITE_URL: BRAND.siteUrl,
    OTP_SENDER: SENDER,
  };

  it('POSTs the expected JSON to the Resend API', async () => {
    const f = stubFetch({ ok: true, status: 200, body: { id: 'abc' } });
    await sendOtpEmail(env, 'to@example.com', OTP);
    expect(f).toHaveBeenCalledTimes(1);
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('https://api.resend.com/emails');
    expect(init.method).toBe('POST');
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer resend-test-key');
    expect(headers['Content-Type']).toBe('application/json');

    const body = JSON.parse(init.body as string);
    expect(body.from).toBe(`Example Admin <${SENDER}>`);
    expect(body.to).toEqual(['to@example.com']); // array, per the Resend API
    expect(body.subject).toBe('Belépési kód — Example Admin');
    expect(body.text).toContain(OTP);
    expect(body.html).toContain(OTP);
    expect(body.html).toContain('<!doctype html>');
  });

  it('honours OTP_SENDER as the from address', async () => {
    const f = stubFetch({ ok: true, status: 200 });
    await sendOtpEmail({ ...env, OTP_SENDER: 'admin@example.com' }, 'to@example.com', OTP);
    const body = JSON.parse((f.mock.calls[0] as unknown as [string, RequestInit])[1].body as string);
    expect(body.from).toBe('Example Admin <admin@example.com>');
  });

  it('refuses to send when OTP_SENDER is blank — no fallback to anyone else\'s mailbox', async () => {
    // `Brand <>` is what an empty var used to produce — Resend answers that
    // with a bare 422 that names nothing. A product-level default sender would
    // be another installation's address, so a missing sender fails loudly.
    vi.spyOn(console, 'error').mockImplementation(() => {});
    for (const OTP_SENDER of ['', '   ', undefined]) {
      const f = stubFetch({ ok: true, status: 200 });
      await expect(sendOtpEmail({ ...env, OTP_SENDER }, 'to@example.com', OTP)).rejects.toThrow(/OTP_SENDER missing/);
      expect(f).not.toHaveBeenCalled();
    }
  });

  it('a CR/LF in the sender cannot forge a header either — `from` is interpolated', async () => {
    // The deleted MIME path had an explicit from-injection check; `from` is
    // still the one field built by string concatenation, so keep pinning it.
    const f = stubFetch({ ok: true, status: 200 });
    await sendOtpEmail({ ...env, OTP_SENDER: 'a@example.com\r\nBcc: attacker@example.com' }, 'to@example.com', OTP);
    const init = (f.mock.calls[0] as unknown as [string, RequestInit])[1];
    const raw = init.body as string;
    expect(raw).not.toMatch(/[\r\n]/);
    expect(JSON.parse(raw).from).toBe('Example Admin <a@example.com\r\nBcc: attacker@example.com>');
    // Nor may it reach an actual HTTP header, where a CR/LF really would
    // split the request rather than being escaped as JSON data.
    for (const v of Object.values(init.headers as Record<string, string>)) {
      expect(v).not.toMatch(/[\r\n]/);
    }
  });

  it('a CR/LF in the address cannot forge a header — JSON encodes it as data', async () => {
    const f = stubFetch({ ok: true, status: 200 });
    await sendOtpEmail(env, 'x@example.com\r\nBcc: attacker@example.com', OTP);
    const raw = (f.mock.calls[0] as unknown as [string, RequestInit])[1].body as string;
    expect(raw).not.toMatch(/[\r\n]/); // JSON.stringify escaped them
    const body = JSON.parse(raw);
    expect(body.to).toEqual(['x@example.com\r\nBcc: attacker@example.com']);
  });

  it('throws with the status when Resend rejects the send', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const f = stubFetch({ ok: false, status: 422, body: { message: 'domain not verified' } });
    await expect(sendOtpEmail(env, 'to@example.com', OTP)).rejects.toThrow(/422/);
    expect(f).toHaveBeenCalledTimes(1);
  });

  it('never leaks the OTP into a thrown message or a log line on the send path', async () => {
    const seen: string[] = [];
    for (const level of ['log', 'error', 'warn', 'info'] as const) {
      vi.spyOn(console, level).mockImplementation((...args: unknown[]) => {
        seen.push(args.map((a) => (a instanceof Error ? `${a.message}\n${a.stack ?? ''}` : String(a))).join(' '));
      });
    }
    // Resend echoing our own payload back in its error body is the worst case.
    stubFetch({ ok: false, status: 400, body: { message: `bad request: text contains ${OTP}` } });
    await expect(sendOtpEmail(env, 'to@example.com', OTP)).rejects.toThrow(
      expect.objectContaining({ message: expect.not.stringContaining(OTP) }) as Error,
    );
    expect(seen.join('\n')).not.toContain(OTP);
  });
});

describe('renderTransactionalEmail', () => {
  it('is reusable: a codeless email still renders', () => {
    const html = renderTransactionalEmail({ heading: 'Test', bodyHtml: '<p>Hi!</p>' }, BRAND);
    expect(html).toContain('Test');
    expect(html).toContain('<p>Hi!</p>');
    expect(html).not.toContain('letter-spacing:14px'); // no code box
  });

  it('has client-robust foundations (table + inline styles, no <style>) and no banner image', () => {
    const html = renderTransactionalEmail({ heading: 'Test', code: '4242' }, BRAND);
    expect(html).toContain('role="presentation"');
    expect(html).toContain('<meta charset="utf-8"/>');
    expect(html).not.toContain('<style');
    expect(html).not.toContain('<script');
    expect(html).not.toContain('<img');
    expect(html).not.toContain('banner');
    expect(html).toContain('4242');
  });
});

// End-to-end over the real endpoint, not just sendOtpEmail: better-auth
// swallows the throw and answers {success:true} either way, so the log
// marker is the ONLY signal that sign-in mail is dead. This pins both halves
// of that contract — and that no code escapes on the failure path.
describe('sign-in request with no RESEND_API_KEY (the deployment today)', () => {
  const prodEnv = () =>
    makeEnv({
      BETTER_AUTH_URL: 'https://mentat-admin-api.example.workers.dev',
      OTP_DRY_RUN: undefined,
      RESEND_API_KEY: undefined,
      BETTER_AUTH_SECRET: 'x'.repeat(40),
      ALLOWED_ORIGINS: 'https://admin.example.com',
    });

  const sendTo = async (email: string) => {
    const lines: string[] = [];
    for (const level of ['log', 'error', 'warn'] as const) {
      vi.spyOn(console, level).mockImplementation((...args: unknown[]) =>
        lines.push(args.map((a) => (a instanceof Error ? a.message : String(a))).join(' ')));
    }
    const res = await app.fetch(
      new Request('https://api.example.com/api/auth/email-otp/send-verification-otp',
        jsonReq('POST', { email, type: 'sign-in' })),
      prodEnv(), {} as ExecutionContext);
    return { res, body: await res.text(), lines };
  };

  it('answers the client non-committally while logging otp-delivery-failed', async () => {
    const { res, body, lines } = await sendTo('owner@example.com');
    expect(res.status).toBe(200);
    expect(JSON.parse(body)).toEqual({ success: true });
    expect(lines).toContainEqual(
      expect.stringContaining('otp-delivery-failed RESEND_API_KEY missing on a non-local deployment'),
    );
    // Nothing that could be a six-digit code anywhere the operator can read.
    expect(`${lines.join(' ')} ${body}`).not.toMatch(/\b\d{6}\b/);
  });

  it('a non-allowlisted address never reaches the sender, so the marker stays specific', async () => {
    const { res, lines } = await sendTo('stranger@example.com');
    expect(res.status).toBe(200);
    expect(lines.some((l) => l.startsWith('otp-delivery-failed'))).toBe(false);
  });
});
