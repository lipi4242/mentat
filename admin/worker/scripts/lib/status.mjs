// Pure parts of `npm run status`: turn gathered facts into the lines an agent
// quotes. Gathering (systemctl, fetch, git, D1) is in scripts/status.mjs.

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

export function formatStatus(f) {
  const urlPort = f.url ? Number(new URL(f.url).port) : null;
  const unit = f.unit === 'none'
    ? 'not installed (no systemd unit) — npm run dev:local'
    : `mentat-admin.service ${f.unit}${f.port ? `, port ${f.port}` : ''}` +
      (f.port && urlPort && f.port !== urlPort ? ` ≠ the URL's ${urlPort} — rerun connect --local` : '');
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
    `health:     ${f.health ? 'ok' : 'DOWN — journalctl --user -u mentat-admin.service'}`,
    `ui:         ${f.ui ? 'served' : 'NOT served — npm --prefix ../admin run build, then systemctl --user restart mentat-admin'}`,
    `version:    ${f.version}, commit ${f.commit} (${f.branch})${f.dirty ? `, ${f.dirty} uncommitted file(s)` : ''}`,
    `migrations: ${migrations}`,
    `tokens:     ${tokens}`,
    `sign in:    ${f.owners.join(', ') || 'nobody (ADMIN_EMAILS empty)'} — npm run login-link`,
  ].join('\n');
}
