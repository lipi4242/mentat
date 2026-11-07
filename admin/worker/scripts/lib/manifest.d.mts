export const KNOWN_SCHEMA: number;
export function withLock<T>(repo: string, fn: () => Promise<T> | T): Promise<T>;
export function readJson(path: string): any;
export function assertKnownSchema(doc: unknown, path: string): void;
export function mergeSection(doc: any, keyPath: string[], data: Record<string, unknown>): any;
export function writeJsonAtomic(path: string, doc: unknown): void;
