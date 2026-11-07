export const IDENTIFIER_PREFIX: string;
export const TTL_MINUTES: number;
export function checkEmail(raw: unknown): string;
export function newLink(opts: { origin: string; email: string; now?: number; ttlMinutes?: number }): {
  url: string;
  expires: number;
  sql: string[];
};
