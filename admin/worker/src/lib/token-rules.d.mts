export const LABEL_RE: RegExp;
export const SCOPE_RE: RegExp;
export const MAX_DAYS: number;
export const DEFAULT_DAYS: number;
export type MintRequest = { label: string; scopes: string; days: number };
export function checkMint(req: { label: unknown; scopes: unknown; days?: unknown }): MintRequest | { error: string };
export function expiryFrom(now: Date, days: number): string;
export function newToken(): Promise<{ id: string; plain: string; hash: string }>;
