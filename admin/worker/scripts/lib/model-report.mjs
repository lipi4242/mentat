// `npm run model`: the closing lines — what is done, where the user sees it
// (menu item + a ready sign-in link), how the agent writes and reads it. Pure.
const SCREEN = (name) => (name === 'cases' ? 'ugyek' : `adatok/${name}`);
const MENU = (target) => (target.name === 'cases' ? 'Ügyek' : `Saját adatok → ${target.label}`);

/**
 * `rebind`: false when /api/meta already showed the model to the agent's token.
 * `extra.widened`: the line widenToken printed (then no rebind hint is needed).
 * `extra.login`: a one-time sign-in link for the owner.
 */
export function usage(url, models, { target, field }, repo, rebind, extra = {}) {
  const origin = url ?? 'http://<admin-url>';
  const screen = `${origin}/${SCREEN(target.name)}`;
  const out = [`see it: menu "${MENU(target)}" — ${screen}${extra.login ? `  (sign in first: ${extra.login})` : ''}`];
  if (target.name === 'cases') {
    out.push(`agent writes: python3 .mentat/bin/cases_cli update <id> --set ${field.name}=<value>   reads: cases_cli show <id> (or GET /api/cases)`);
  } else {
    const e = models.entities.find((x) => x.name === target.name);
    out.push(`agent writes/reads: POST|GET /api/${e.name}, GET|PATCH /api/${e.name}/<id> with X-Mentat-Token (scope ${e.name}:write, read: ${e.name}:read)`);
    if (extra.widened) out.push(extra.widened);
    else if (rebind) {
      const scopes = ['cases:write', ...models.entities.map((x) => `${x.name}:write`)].join(',');
      out.push(`token: the agent's token has no ${e.name} scope — pass --repo <agent repo> to widen it, or: npm run connect -- --repo ${repo ?? '<agent repo>'} --url ${origin} --local --plugins cases --scope ${scopes}`);
    }
  }
  out.push('bad value: send it anyway and quote the admin answer verbatim (its error text) to the user — do not guess a cause.');
  return out;
}
