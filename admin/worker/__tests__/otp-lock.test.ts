// The e-mail code sign-in under a guessing attack from many IPs: the per-address lock holds across
// IPs and across fresh codes, an address outside ADMIN_EMAILS never gets a user row, and the
// second guessing path (check-verification-otp) answers the same for every address.
import { afterEach, describe, expect, it, vi } from 'vitest';
import app from '../src/index';
import { createAuth } from '../src/lib/better-auth';
import { OTP_LOCK_MAX_FAILS } from '../src/lib/otp-lock';
import { makeDb } from './helpers';

const SECRET = 'test-secret-at-least-thirty-two-characters';
const OWNER = 'owner@example.com';

function env() {
  const { DB, raw } = makeDb();
  return {
    raw,
    env: { DB, ADMIN_EMAILS: OWNER, BETTER_AUTH_URL: 'http://localhost:8787', OTP_DRY_RUN: '1',
           BETTER_AUTH_SECRET: SECRET, OTP_SENDER: 'Mentat <noreply@example.com>' } as any,
  };
}

const post = (e: any, path: string, body: unknown, ip: string) =>
  app.request(`/api/auth${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'cf-connecting-ip': ip },
    body: JSON.stringify(body),
  }, e);

/** A fresh code for the address, read from the dry-run log (the only way to see it here). */
async function newCode(e: any, ip: string, email = OWNER): Promise<string> {
  const logged: string[] = [];
  const spy = vi.spyOn(console, 'log').mockImplementation((...a: unknown[]) => void logged.push(a.join(' ')));
  try {
    const r = await post(e, '/email-otp/send-verification-otp', { email, type: 'sign-in' }, ip);
    expect(r.status).toBe(200);
  } finally {
    spy.mockRestore();
  }
  const otp = logged.map((l) => /otp=(\d+)/.exec(l)?.[1]).find(Boolean);
  expect(otp).toBeTruthy();
  return otp!;
}

const wrong = (otp: string) => String((Number(otp) + 1) % 1_000_000).padStart(otp.length, '0');
const ip = (i: number) => `203.0.113.${i % 10}`; // ten source addresses, documentation range

/** `n` failed sign-ins spread over ten IPs; a code dies after three, so a fresh one is asked for. */
async function fail(e: any, n: number, start = 0) {
  for (let i = start; i < start + n; i++) {
    const otp = await newCode(e, ip(i));
    const r = await post(e, '/sign-in/email-otp', { email: OWNER, otp: wrong(otp) }, ip(i + 1));
    expect(r.status).toBeGreaterThanOrEqual(400);
  }
}

afterEach(() => vi.restoreAllMocks());

describe('per-address lock for the e-mail code', () => {
  it('after 10 failures from 10 IPs even the right code is refused, for the lock time', async () => {
    const { env: e, raw } = env();
    await fail(e, OTP_LOCK_MAX_FAILS);
    for (let i = 0; i < 10; i++) { // attempts 11..20, each with the RIGHT code, from every IP
      const otp = await newCode(e, ip(i));
      const r = await post(e, '/sign-in/email-otp', { email: OWNER, otp }, ip(i));
      expect(r.status).toBe(429);
      expect(r.headers.get('set-cookie') ?? '').not.toContain('session_token');
    }
    raw.prepare(`UPDATE auth_rate_limit SET lastRequest = lastRequest - ? WHERE key LIKE 'otp-fail:%'`).run(16 * 60 * 1000);
    const otp = await newCode(e, ip(1));
    const ok = await post(e, '/sign-in/email-otp', { email: OWNER, otp }, ip(1));
    expect(ok.status).toBe(200); // the lock ends; the owner gets in
    expect(raw.prepare(`SELECT count(*) n FROM auth_rate_limit WHERE key LIKE 'otp-fail:%'`).get()).toEqual({ n: 0 });
  });

  it('a fresh code does not reset the per-address count', async () => {
    const { env: e } = env();
    await fail(e, OTP_LOCK_MAX_FAILS - 1);
    const fresh = await newCode(e, ip(3)); // a new code ...
    await post(e, '/sign-in/email-otp', { email: OWNER, otp: wrong(fresh) }, ip(4)); // ... and the 10th miss
    const otp = await newCode(e, ip(5));
    expect((await post(e, '/sign-in/email-otp', { email: OWNER, otp }, ip(5))).status).toBe(429);
  });

  it('a right code below the limit clears the count', async () => {
    const { env: e, raw } = env();
    await fail(e, 5);
    const otp = await newCode(e, ip(7));
    expect((await post(e, '/sign-in/email-otp', { email: OWNER, otp }, ip(7))).status).toBe(200);
    expect(raw.prepare(`SELECT count(*) n FROM auth_rate_limit WHERE key LIKE 'otp-fail:%'`).get()).toEqual({ n: 0 });
  });

  it('no row in the table names the address', async () => {
    const { env: e, raw } = env();
    await fail(e, 2);
    const rows = raw.prepare(`SELECT id, key FROM auth_rate_limit`).all() as { id: string; key: string }[];
    expect(rows.length).toBeGreaterThan(0);
    expect(JSON.stringify(rows)).not.toContain('owner');
  });
});

describe('only ADMIN_EMAILS can ever get a user row', () => {
  it('a valid code for another address signs nobody in and creates no user', async () => {
    const { env: e, raw } = env();
    const stranger = 'stranger@example.com';
    // the attacker's best case: a valid code exists for the address (requested, never mailed)
    const otp = await createAuth(e).api.createVerificationOTP({ body: { email: stranger, type: 'sign-in' } });
    const r = await post(e, '/sign-in/email-otp', { email: stranger, otp }, ip(2));
    expect(r.status).toBe(400);
    expect(r.headers.get('set-cookie') ?? '').not.toContain('session_token');
    expect(raw.prepare(`SELECT count(*) n FROM auth_user`).get()).toEqual({ n: 0 });
    const miss = await post(e, '/sign-in/email-otp', { email: stranger, otp: wrong(otp) }, ip(2));
    expect([miss.status, await miss.json()]).toEqual([r.status, await r.clone().json()]); // same answer as a wrong code
  });
});

describe('check-verification-otp', () => {
  it('answers the same for a known and an unknown address', async () => {
    const { env: e } = env();
    const known = await post(e, '/email-otp/check-verification-otp', { email: OWNER, type: 'sign-in', otp: '123456' }, ip(1));
    const unknown = await post(e, '/email-otp/check-verification-otp', { email: 'x@example.com', type: 'sign-in', otp: '123456' }, ip(2));
    expect(known.status).toBe(404);
    expect([unknown.status, await unknown.text()]).toEqual([known.status, await known.text()]);
  });
});
