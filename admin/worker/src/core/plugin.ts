import type { Hono } from 'hono';
import type { AppEnv } from '../types';

export interface AdminPlugin {
  /** Stable id, also the migration-band owner name. */
  id: string;
  /** Inclusive migration number band this plugin owns, e.g. [100, 199]. */
  migrationBand: [number, number];
  /** Table names this plugin owns — used by the band test to detect cross-plugin refs. */
  tables: string[];
  /** Other plugins' tables this plugin's migrations may add columns to
   *  (the instance's own fields, config/models.json). Nothing else. */
  extends?: string[];
  registerRoutes(app: Hono<AppEnv>): void;
}
