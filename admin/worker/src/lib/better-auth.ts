// better-auth configuration — narrowed to email OTP only.
// A fresh instance per request (a module-level singleton would bake the first
// request's env/D1 binding into the isolate).
import { betterAuth, type Auth } from 'better-auth';
import { drizzleAdapter } from 'better-auth/adapters/drizzle';
import { emailOTP } from 'better-auth/plugins';
import { drizzle } from 'drizzle-orm/d1';
import type { Env } from '../types';
import { adminEmails } from '../types';
import { authUser, authSession, authAccount, authVerification, authRateLimit } from '../db/auth-schema';
import { sendOtpEmail } from './email';

const OTP_LENGTH = 6;
const OTP_EXPIRY_SECONDS = 300;
const OTP_MAX_ATTEMPTS = 3;

function allowedBrowserOrigins(env: Env): string[] {
  return (env.ALLOWED_ORIGINS ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

function buildAuthOptions(env: Env) {
  const db = drizzle(env.DB);
  return {
    baseURL: env.BETTER_AUTH_URL ?? 'http://localhost:8787',
    basePath: '/api/auth',
    secret: env.BETTER_AUTH_SECRET,
    telemetry: { enabled: false },
    database: drizzleAdapter(db, {
      provider: 'sqlite' as const,
      schema: {
        user: authUser,
        session: authSession,
        account: authAccount,
        verification: authVerification,
        rateLimit: authRateLimit,
      },
    }),
    emailAndPassword: { enabled: false },
    session: {
      expiresIn: 60 * 60 * 24 * 30, // 30 days
      updateAge: 60 * 60 * 24, // sliding, refreshed daily
    },
    trustedOrigins: allowedBrowserOrigins(env),
    rateLimit: {
      enabled: true,
      storage: 'database' as const,
      modelName: 'rateLimit',
      window: 60,
      max: 60,
      customRules: {
        '/email-otp/send-verification-otp': { window: 60, max: 3 },
        '/sign-in/email-otp': { window: 60, max: 5 },
      },
    },
    advanced: {
      ipAddress: { ipAddressHeaders: ['cf-connecting-ip'] },
      // SameSite=Lax is required: the admin SPA and the API are served
      // same-site, so a Lax cookie rides along on the SPA's own requests
      // while staying off genuine cross-site ones.
      defaultCookieAttributes: { sameSite: 'lax' as const, httpOnly: true },
    },
    plugins: [
      emailOTP({
        otpLength: OTP_LENGTH,
        expiresIn: OTP_EXPIRY_SECONDS,
        allowedAttempts: OTP_MAX_ATTEMPTS,
        async sendVerificationOTP({ email, otp, type }: { email: string; otp: string; type: string }) {
          // Closed admin circle: a code is only ever sent to an allowlisted
          // address. A request for any other address is silently dropped
          // (no user enumeration, no spam).
          if (type !== 'sign-in') return;
          if (!adminEmails(env).includes(email.toLowerCase())) return;
          await sendOtpEmail(env, email, otp);
        },
      }),
    ],
  };
}

export function createAuth(env: Env): Auth<ReturnType<typeof buildAuthOptions>> {
  return betterAuth(buildAuthOptions(env)) as Auth<ReturnType<typeof buildAuthOptions>>;
}
