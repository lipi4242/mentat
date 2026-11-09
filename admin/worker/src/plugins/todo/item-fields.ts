// Validation of the backlog item spec fields shared by POST /items and PATCH /items/:id.
import { Problem, textField, type Fields } from './types';
import { enabledPrincipal } from './kinds';

/** One cap for an item's ACs: create, add and import (a report holds at most this many results). */
export const MAX_ACS = 200;
export const SPEC_FIELDS = ['title', 'description', 'priority', 'estimate', 'pm', 'request_quote', 'request_ref'];

export function optionalText(value: unknown, name: string, max: number) {
  if (value === undefined || value === null) return null;
  if (typeof value !== 'string' || value.length > max) throw new Problem(`${name} must be text up to ${max} characters, or null`);
  return value;
}

/** Splits the spec into anchor (todo_task) and extension (backlog_item) columns. */
export async function itemFields(db: D1Database, body: Record<string, unknown>) {
  const task: Fields = {}, item: Fields = {};
  if ('title' in body) task.title = textField(body.title, 'title', 1000);
  if ('description' in body) task.description = optionalText(body.description, 'description', 100000);
  if ('pm' in body) task.owner_id = await enabledPrincipal(db, body.pm, 'pm');
  if ('priority' in body) {
    if (!Number.isInteger(body.priority) || (body.priority as number) < 0 || (body.priority as number) > 4) throw new Problem('priority must be 0 (none) to 4 (low)');
    item.priority = body.priority as number;
  }
  if ('estimate' in body) {
    if (body.estimate !== null && (!Number.isInteger(body.estimate) || (body.estimate as number) < 0)) throw new Problem('estimate must be a nonnegative integer or null');
    item.estimate = body.estimate as number | null;
  }
  if ('request_quote' in body) item.request_quote = optionalText(body.request_quote, 'request_quote', 10000);
  if ('request_ref' in body) item.request_ref = optionalText(body.request_ref, 'request_ref', 2000);
  return { task, item };
}

export function acTexts(value: unknown) {
  if (value === undefined) return [];
  if (!Array.isArray(value) || value.length > MAX_ACS) throw new Problem(`acs must be a list of up to ${MAX_ACS} texts`);
  return value.map((v, i) => acText(v, `acs[${i}]`));
}
// A 422 nevezze meg a hibás mezőt: POST /items acs[i], az AC-végpontokon text (11-08 terep).
export const acText = (v: unknown, name = 'text') => textField(v, name, 10000);
