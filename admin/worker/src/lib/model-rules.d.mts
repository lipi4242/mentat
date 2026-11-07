export const FIELD_TYPES: readonly ['text', 'textarea', 'email', 'date', 'number', 'integer', 'checkbox', 'select', 'ref'];
export const RESERVED: Record<string, string[]>;
export const ENTITY_SYSTEM: string[];
export const NAME_RE: RegExp;
export function modelsErrors(m: unknown): string[];
