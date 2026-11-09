import type { AppEnv } from '../../types';
export type Principal = { id: string; kind: 'human' | 'agent'; handle: string; display_name: string; avatar: string | null; about?: string | null };
export type TodoEnv = { Bindings: AppEnv['Bindings']; Variables: AppEnv['Variables'] & { principal: Principal | null; email: string | null; tokenScopes: string | null } };
export type Task = {
  id: string; parent_id: string | null; position: string; title: string; description: string | null;
  status: 'open' | 'done' | 'dropped'; due_date: string | null; due_time: string | null; planned_date: string | null;
  tz: string; owner_id: string; assignee_id: string | null; assignee_note: string | null;
  repeat_rule: string | null; repeat_from: 'schedule' | 'completion';
  kind: 'todo' | 'case' | 'item'; rev: number; archived: number; created_by: string; idem_key: string;
  created_at: string; updated_at: string; updated_by: string; done_at: string | null; done_by: string | null;
};
export type Fields = Record<string, string | number | null>;
export class Problem extends Error {
  constructor(message: string, public status: 403 | 404 | 409 | 422 = 422, public current?: unknown) { super(message); }
}
export function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Problem('body must be an object');
  return value as Record<string, unknown>;
}
export function keys(body: Record<string, unknown>, allowed: readonly string[]) {
  const bad = Object.keys(body).find(k => !allowed.includes(k));
  if (bad) throw new Problem(`unknown field: ${bad}`);
}
export function textField(value: unknown, name: string, max = 200): string {
  if (typeof value !== 'string' || !value.trim() || value.length > max) throw new Problem(`${name} must be nonempty text, max ${max}`);
  return value;
}
