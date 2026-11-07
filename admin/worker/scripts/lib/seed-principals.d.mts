import type { QueryMany } from './dump.mjs';
export type SeedEntry =
  | { kind: 'human'; email: string; name: string; handle: string }
  | { kind: 'agent'; label: string; name: string; handle: string };
export const CREATED_BY: string;
export function parseSeed(obj: unknown): SeedEntry[];
export function entrySql(e: SeedEntry, id?: string): string[];
export function seedPrincipals(
  queryMany: QueryMany | null,
  entries: SeedEntry[],
  opts?: { dryRun?: boolean },
): Promise<{ sql?: string[]; report?: { entry: SeedEntry; ok: boolean; status: string }[] }>;
