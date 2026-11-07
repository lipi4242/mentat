import { afterEach, vi } from 'vitest';
import { tick } from '../../test-render';
import { show as showPage } from '../cases/testkit';
import type { Detail, Principal } from './meta';
export { stubApi, button, click, type } from '../cases/testkit';
export { tick };
export const task: Detail = {
  id: 'one', title: 'Reggeli rutin', description: 'Egy lépés', parent_id: null, position: 'U', status: 'open',
  due_date: null, due_time: null, planned_date: null, tz: 'Europe/Budapest', owner_id: 'p', assignee_id: null,
  assignee_note: null, repeat_rule: null, repeat_from: 'schedule', progress: null, archived: 0, rev: 3, children: [], labels: [], comments: [],
};
export const principal: Principal = { id: 'p', kind: 'human', handle: 'owner', display_name: 'Gipsz Jakab',
  disabled_at: null, avatar: null, auth_email: 'owner@example.com', agent_token_id: null };
export const detailRoute = (url: string, row = task) => ({ body: url.endsWith('/principals') ? [principal]
  : url.endsWith('/labels') ? [{ id: 'l', name: 'Otthon' }] : url.endsWith('/tasks') ? [row] : row });
const unmounts: Array<() => void> = [];
export async function show(...args: Parameters<typeof showPage>) {
  const view = await showPage(...args); unmounts.push(view.unmount); return view;
}
afterEach(() => {
  for (const unmount of unmounts.splice(0)) unmount();
  vi.unstubAllGlobals(); document.body.innerHTML = '';
});
export async function key(selector: string, options: KeyboardEventInit = {}) {
  const input = document.querySelector(selector)!;
  for (const name of ['keydown', 'keyup']) input.dispatchEvent(new KeyboardEvent(name, { key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true, ...options }));
  await tick(150);
}
