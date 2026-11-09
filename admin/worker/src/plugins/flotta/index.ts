// Flotta-egészség (11-07): a boxok ide jelentik az ágenseik képesség-eredményét;
// a worker incidenst nyit, a felelős ágensnek todo-feladatot ad, és cronból
// e-mailben eszkalál a tulajdonoshoz. Telepítés: a plugin INSTALL-ja (admin docs, flotta).
import { Hono } from 'hono';
import type { AdminPlugin } from '../../core/plugin';
import type { AppEnv } from '../../types';
import { registerBoxes } from './boxes';
import { runCron } from './cron';
import { registerReport } from './report-route';
import { registerStatus } from './status';
import { registerFleetConfig } from './fleet-config';
import { Problem } from './types';
import { Conflict } from './states';
import { registerPublish } from './publish';
import { registerClaim } from './claim-route';
import { registerOps } from './ops-route';
import { registerVerify } from './verify-route';
import { registerHuman } from './human-route';

export const flottaPlugin: AdminPlugin = {
  id: 'flotta',
  migrationBand: [500, 599],
  tables: ['flotta_fleet', 'flotta_manager', 'flotta_box', 'flotta_agent', 'flotta_report', 'flotta_incident', 'flotta_incident_event',
    'flotta_repair_op', 'flotta_restart_budget'],
  registerRoutes(app: Hono<AppEnv>) {
    const routes = new Hono<AppEnv>();
    routes.onError((error, c) => {
      if (error instanceof Problem) return c.json({ error: error.message, ...(error.code ? { code: error.code } : {}) }, error.status);
      if (error instanceof Conflict) return c.json({ error: error.message, code: error.code }, 409);
      throw error;
    });
    for (const register of [registerReport, registerStatus, registerFleetConfig, registerBoxes,
      registerPublish, registerClaim, registerOps, registerVerify, registerHuman]) register(routes);
    app.route('/', routes);
  },
  async scheduled(env, now) {
    await runCron(env, now);
  },
};
