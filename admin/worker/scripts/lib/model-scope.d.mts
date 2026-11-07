import type { QueryMany } from './dump.mjs';
export function scopesFor(models: { entities: { name: string }[] }): string;
export function widenToken(o: { repo: string; url: string; models: { entities: { name: string }[] }; entity: string; query: QueryMany }): Promise<{ state: 'has' | 'widened' | 'skipped'; line: string }>;
