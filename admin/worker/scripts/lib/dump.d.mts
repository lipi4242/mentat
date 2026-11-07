// Types for dump.mjs (the scripts stay plain JS so they run on a bare Node).
export type Row = Record<string, unknown>;
export type QueryMany = (sqls: string[]) => Promise<Row[][]>;
export type Dump = {
  format: string;
  version: number;
  exported_at: string;
  migrations: string[];
  skipped: string[];
  order: string[];
  tables: Record<string, Row[]>;
};
export const FORMAT: string;
export const VERSION: number;
export const SKIPPED: string[];
export function ident(name: string): string;
export function literal(v: unknown): string;
export function dependencyOrder(tables: string[], parentsOf: Record<string, string[]>): string[];
export function listTables(queryMany: QueryMany): Promise<string[]>;
export function exportDb(queryMany: QueryMany, opts?: { only?: string[]; now?: Date }): Promise<Dump>;
export function planRestore(dump: unknown, opts?: { only?: string[] }): string[];
export function assertRestorable(queryMany: QueryMany, tables: string[]): Promise<void>;
export function restoreSql(dump: Dump, tables: string[]): string;
export function isInternal(table: string): boolean;
