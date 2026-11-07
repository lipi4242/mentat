import { Hono } from 'hono';
import type { AdminPlugin } from '../../core/plugin';
import { authenticate } from './auth';
import { Problem, type TodoEnv } from './types';
import { registerRead } from './read';
import { registerWrite } from './write';
import { registerTree } from './tree';
import { registerComplete } from './complete';
import { registerHandback } from './handback';
import { registerComments } from './comments';
import { registerLabels } from './labels';
import { registerPrincipals } from './principals';
import { registerDeps } from './deps';
import { registerEvents } from './events';
import { registerCases } from './cases';
import { registerProjects } from './projects';
import { registerItems } from './items';
import { registerAcs } from './acs';
import { registerFlow } from './flow-routes';
import { registerImport } from './import';
export const todoPlugin: AdminPlugin = {
  id: 'todo', migrationBand: [400, 499],
  tables: ['todo_principal','todo_task','todo_label','todo_task_label','todo_dep','todo_comment','todo_mention','todo_event',
    'todo_case','backlog_project','backlog_item','backlog_ac','backlog_report','backlog_ac_result','backlog_link'],
  registerRoutes(app) {
    const routes = new Hono<TodoEnv>();
    routes.use('*', authenticate);
    routes.onError((error, c) => {
      if (error instanceof Problem) return c.json({ error: error.message, ...(error.current ? { current: error.current } : {}) }, error.status);
      if (error instanceof SyntaxError) return c.json({ error: 'body must be valid JSON' }, 400);
      throw error;
    });
    for (const register of [registerRead, registerWrite, registerTree, registerComplete, registerHandback,
      registerComments, registerLabels, registerPrincipals, registerDeps, registerEvents, registerCases,
      registerProjects, registerImport, registerItems, registerAcs, registerFlow]) register(routes);
    app.route('/api/todo/v1', routes);
  },
};
