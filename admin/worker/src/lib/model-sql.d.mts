import type { Models } from '../core/models';

export const EXTENSIBLE_TABLES: Record<string, string>;
export type Schema = Record<string, Set<string>>;
export function modelSql(models: Pick<Models, 'fields' | 'entities'>, schema: Schema): string[];
export function schemaOf(db: { prepare(sql: string): { all(...params: unknown[]): any[] } }): Schema;
