// Pure text of the agent-facing onboarding: the managed block in the agent
// repo's AGENTS.md, `npm run where`, and the closing lines of `connect`.
// The effectful half (files, processes) is lib/agent-setup.mjs.
export const BLOCK_START = '<!-- mentat:admin:start -->';
export const BLOCK_END = '<!-- mentat:admin:end -->';

const trim = (s) => s.replace(/\/+$/, '');

/** Upsert the managed block at the END of an AGENTS.md text (the top stays a stable cache prefix). */
export function upsertBlock(text, block) {
  const a = text.indexOf(BLOCK_START);
  const b = text.indexOf(BLOCK_END);
  if (a >= 0 && b > a) return text.slice(0, a) + block + text.slice(b + BLOCK_END.length);
  return `${text.trimEnd()}${text.trim() ? '\n\n' : ''}${block}\n`;
}

/**
 * The block (<= 12 lines). `dir` is the admin's worker dir as the agent should
 * type it; `cases` false when the cases plugin is not bound.
 */
export function adminBlock({ origin, dir, local, cases = true }) {
  const o = trim(origin);
  const login = local ? `sign in: \`npm run login-link\` (in ${dir})` : 'sign in: the e-mail code the admin sends';
  return [
    BLOCK_START,
    '## Admin: the source of truth',
    ...(cases
      ? [
          '- Cases and the user\'s own data models live in the admin, not in notes. For a fact (amount, date, status) run',
          '  `python3 .mentat/bin/cases_cli show <id>` or `list`; a note is background only and can be stale.',
        ]
      : ['- The user\'s own data models live in the admin, not in notes.']),
    `- Something new to keep track of: extend the admin, never a file. In ${dir}: \`npm run model -- add-field …\` (a field on cases),`,
    '  `npm run model -- new … --repo <this repo>` (a new data model; the token is widened by the command); `npm run model -- --help` = full syntax.',
    `- Where the user sees it: ${cases ? `${o}/ugyek (menu "Ügyek"; the "Új ügy" button is the form), ` : ''}own models at ${o}/adatok/<model> (menu "Saját adatok" → the model); ${login}.`,
    '- A value the admin refuses: send it anyway and quote the admin\'s own answer to the user, word for word; never guess a cause.',
    ...(cases ? ['- Admin not running: case commands refuse (exit 3, nothing written, no queue, no markdown fallback); `cases_cli status` says if it answers; start it, rerun.'] : []),
    `- What exists right now: \`npm run where\` in ${dir}.`,
    BLOCK_END,
  ].join('\n');
}

const FORM = 'the "Új" button on the list';

function fieldsLine(fields) {
  return fields.length ? fields.map((f) => `${f.name} (${f.type})`).join(', ') : '(none yet)';
}

/** `npm run where`: models and fields with their list/form URLs. `models` = config/models.json. */
export function whereLines({ origin, models, local, owners = [] }) {
  const o = trim(origin);
  const own = models?.fields?.cases ?? [];
  const out = [
    `admin:   ${o}`,
    `sign in: ${local ? 'npm run login-link (one-time link, this machine)' : 'e-mail code'}${owners.length ? ` — ${owners.join(', ')}` : ''}`,
    `cases    list ${o}/ugyek   form: the "Új ügy" button on the list`,
    `         own fields: ${fieldsLine(own)}`,
  ];
  for (const e of models?.entities ?? []) {
    out.push(`${e.name.padEnd(8)} list ${o}/adatok/${e.name}   form: ${FORM}`, `         fields: ${fieldsLine(e.fields ?? [])}`);
  }
  if (!(models?.entities ?? []).length) out.push('no own data models yet — new: npm run model -- new …');
  return out;
}

/** The last thing `connect` prints: done / next / sign in / where. */
export function closingLines({ origin, dir, local, cases, nextSteps }) {
  const o = trim(origin);
  return [
    '',
    `done: the admin at ${o} is bound to this agent${cases ? ', cases_cli installed in .mentat/bin' : ''}.`,
    `next: ${nextSteps.join(' | ')}`,
    local ? `sign in: cd ${dir} && npm run login-link   (one-time link, 10 min, this machine)` : `sign in: ${o} (e-mail code)`,
    ...(cases ? [`cases: list ${o}/ugyek   form: the "Új ügy" button on the list`] : []),
    `state: cd ${dir} && npm run status   models: npm run where`,
  ];
}
