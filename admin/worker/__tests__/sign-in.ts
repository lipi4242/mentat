// Sign in through the real e-mail OTP flow (shared by the guard and token tests).
import { vi } from 'vitest';

/**
 * Drive the real email-OTP flow against the emulator and return the session
 * cookie. OTP_DRY_RUN=1 makes sendOtpEmail log the code instead of sending it,
 * which is the only way to read it back here.
 */
export async function signIn(app: any, env: any, email: string): Promise<string | null> {
  const logged: string[] = [];
  const spy = vi.spyOn(console, 'log').mockImplementation((...a: unknown[]) => {
    logged.push(a.join(' '));
  });
  try {
    await app.request(
      '/api/auth/email-otp/send-verification-otp',
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, type: 'sign-in' }) },
      env,
    );
    const otp = logged.map((l) => /\[otp dry-run\] to=\S+ otp=(\d+)/.exec(l)?.[1]).find(Boolean);
    if (!otp) return null; // no code was sent — not on the allowlist
    const res = await app.request(
      '/api/auth/sign-in/email-otp',
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, otp }) },
      env,
    );
    const cookie = res.headers.get('set-cookie');
    return cookie ? cookie.split(';')[0] : null;
  } finally {
    spy.mockRestore();
  }
}

