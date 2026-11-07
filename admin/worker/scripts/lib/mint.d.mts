import type { QueryMany } from './dump.mjs';
export type Minted = { id: string; token: string; label: string; scopes: string; expires_at: string };
export type MintRequest = { label: unknown; scopes: unknown; days?: unknown };
export function checkRequest(request: MintRequest): { label: string; scopes: string; days: number };
export function buildMint(request: MintRequest, made: { id: string; hash: string }, now?: Date): Omit<Minted, 'token'> & { sql: string };
export function prepareMint(request: { label: unknown; scopes: unknown; days?: unknown }, now?: Date): Promise<Minted & { sql: string }>;
export function mint(queryMany: QueryMany, request: { label: unknown; scopes: unknown; days?: unknown }): Promise<Minted>;
export function revoke(queryMany: QueryMany, by: { id?: string; label?: string }): Promise<string[]>;
export function revokeOthers(queryMany: QueryMany, by: { label: string; keep: string }): Promise<string[]>;
