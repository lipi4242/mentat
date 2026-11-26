// Pure parts of `npm run status`: turn gathered facts into the lines an agent
// quotes. Gathering (systemctl/launchctl, fetch, git, D1) is in scripts/status.mjs.

export function pendingMigrations(files, applied) {
  const done = new Set(applied);
  return [...files].sort().filter((f) => !done.has(f));
}

/** The --port the unit's ExecStart really uses, or null. */
export function portOfUnit(text) {
  const m = /^ExecStart=.*--port (\d+)/m.exec(text ?? '');
  return m ? Number(m[1]) : null;
}

const day = (s) => (s ? String(s).slice(0, 10) : 'never');

const LAUNCHD = { name: 'launchd agent com.mentat.admin', none: 'no launchd agent', log: 'see ~/Library/Logs/mentat-admin.log', restart: 'launchctl kickstart -k gui/$(id -u)/com.mentat.admin' };
const SYSTEMD = { name: 'mentat-admin.service', none: 'no systemd unit', log: 'journalctl --user -u mentat-admin.service', restart: 'systemctl --user restart mentat-admin' };

export function formatStatus(f) {
  const svc = f.manager === 'launchd' ? LAUNCHD : SYSTEMD;
  const urlPort = f.url ? Number(new URL(f.url).port) : null;
  const unit = f.unit === 'none'
    ? `not installed (${svc.none}) — npm run connect -- --local (or npm run dev:local for this terminal only)`
    : `${svc.name} ${f.unit}${f.port ? `, port ${f.port}` : ''}` +
      (f.runs ? `, started ${f.runs}× (KeepAlive restarts it)` : '') +
      (f.port && urlPort && f.port !== urlPort ? ` ≠ the URL's ${urlPort} — rerun connect --local` : '') +
      (f.nodeOk === false ? `; node ${f.node ?? '(none)'} is gone (node upgraded or moved?) — rerun connect --local` : '');
  const m = f.migrations;
  const migrations = m.error
    ? `unknown (${m.error})`
    : `${m.applied.length} applied, ${m.pending.length} pending` +
      (m.pending.length ? `; pending: ${m.pending.join(', ')} — run: npm run migrate:local` : '');
  const tokens = f.tokens.length
    ? f.tokens.map((t, i) => `${i ? '            ' : ''}${t.label}  ${t.scopes}  expires ${day(t.expires_at)}  last used ${day(t.last_used_at)}${t.id ? `  id ${t.id}` : ''}`).join('\n')
    : 'none active';
  return [
    `url:        ${f.url ?? 'unknown (no worker/.dev.vars — not a connect --local admin)'}  (admin UI + API)`,
    `service:    ${unit}`,
    `health:     ${f.health ? 'ok' : `DOWN — ${svc.log}`}`,
    `ui:         ${f.ui ? 'served' : `NOT served — npm --prefix ../admin run build, then ${svc.restart}`}`,
    `version:    ${f.version}, commit ${f.commit} (${f.branch})${f.dirty ? `, ${f.dirty} uncommitted file(s)` : ''}`,
    `migrations: ${migrations}`,
    `tokens:     ${tokens}`,
    `sign in:    ${f.owners.join(', ') || 'nobody (ADMIN_EMAILS empty)'} — npm run login-link`,
  ].join('\n');
}
