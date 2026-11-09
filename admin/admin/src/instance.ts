// Frontend half of the instance config. The plugin list is product
// configuration (mirrors config/plugins.ts on the worker side; kept separate
// because the SPA bundle must not import worker code). The title is instance
// data: it comes in at build time as VITE_INSTANCE_TITLE, which
// `config/instance.mjs render` writes into admin/.env.production.local.
import type { AdminPluginUI } from './core/plugin';
import { casesUI } from './plugins/cases';
import { todoUI } from './plugins/todo';
import { backlogUI } from './plugins/backlog';
import { customUI } from './plugins/custom';
import { flottaUI } from './plugins/flotta';

export const INSTANCE_TITLE: string = import.meta.env.VITE_INSTANCE_TITLE?.trim() || 'Mentat Admin';
export const UI_PLUGINS: AdminPluginUI[] = [casesUI, customUI, todoUI, backlogUI, flottaUI];
