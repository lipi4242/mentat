import type { FieldDef } from '../../src/core/fields';
import type { Models } from '../../src/core/models';

export class UsageError extends Error {}
export type Plan = {
  models: Models;
  kind: 'field' | 'entity';
  target: { name: string; label: string };
  field: FieldDef | null;
  slug: string;
  changed: boolean;
};
export function parseArgs(argv: string[]): { cmd?: string; rest: string[]; flags: Record<string, string | boolean>; fields: string[] };
export function addField(models: Models, rest: string[], flags: Record<string, any>): Plan;
export function newEntity(models: Models, rest: string[], flags: Record<string, any>, specs: string[]): Plan;
export function parseFieldSpec(spec: string): FieldDef;
