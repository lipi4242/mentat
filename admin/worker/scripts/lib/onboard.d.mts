export const BLOCK_START: string;
export const BLOCK_END: string;
export function upsertBlock(text: string, block: string): string;
export function adminBlock(o: { origin: string; dir: string; local: boolean; cases?: boolean }): string;
export function whereLines(o: { origin: string; models: any; local: boolean; owners?: string[] }): string[];
export function closingLines(o: { origin: string; dir: string; local: boolean; cases: boolean; nextSteps: string[] }): string[];
