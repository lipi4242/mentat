// Runs instance steps in order, skipping the ones the state file marks done
// and saving the state after every step — a failure leaves a state that the
// next run continues from.
import { WORKER_DIR } from './d1.mjs';
import { saveState } from './instance-state.mjs';
import { runTool } from './tools.mjs';

/**
 * The step's view of the outside world. Every child gets the instance file
 * (MENTAT_ADMIN_INSTANCE), renders into its own dir (MENTAT_RENDER_DIR,
 * never the checkout's config/rendered/) and, once known, the account (CLOUDFLARE_ACCOUNT_ID,
 * so wrangler never stops to ask which one).
 */
export function makeExec({ instanceFile, renderDir, values, env = process.env }) {
  const childEnv = (extra) => ({
    ...env,
    MENTAT_ADMIN_INSTANCE: instanceFile,
    MENTAT_RENDER_DIR: renderDir,
    ...(values.account_id ? { CLOUDFLARE_ACCOUNT_ID: values.account_id } : {}),
    ...extra,
  });
  const attempt = (tool, args, { input, cwd = WORKER_DIR, env: extra } = {}) =>
    runTool(tool, args, { input, cwd, env: childEnv(extra) });
  return {
    try: attempt,
    sh(tool, args, opts) {
      const r = attempt(tool, args, opts);
      if (r.status !== 0) {
        const tail = (r.stderr.trim() || r.stdout.trim()).split('\n').slice(-15).join('\n');
        throw new Error(`${tool} ${args.slice(0, 3).join(' ')} failed (exit ${r.status})${tail ? `:\n${tail}` : ''}`);
      }
      return r.stdout;
    },
  };
}

/** → true when every step is done. Logs one line per step. */
export function runSteps({ steps, state, statePath, exec, log = console.log }) {
  for (const [i, step] of steps.entries()) {
    const tag = `[${i + 1}/${steps.length}] ${step.id}`;
    if (state.done.includes(step.id)) {
      log(`${tag}: done earlier, skipped`);
      continue;
    }
    log(`${tag}: ${step.what}`);
    try {
      step.run(exec, state.values);
    } catch (err) {
      saveState(statePath, state);
      log(`${tag}: FAILED — ${err instanceof Error ? err.message : err}`);
      log(`\nFix the cause and rerun the same command: done steps are skipped (${statePath}).`);
      return false;
    }
    state.done.push(step.id);
    saveState(statePath, state);
  }
  return true;
}
