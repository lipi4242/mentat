// `npm run model -- --help`: the complete syntax in one read, so nobody has to
// open model.mjs or model-spec.mjs to learn it. The type list comes from the
// product's own validator; the tests parse every `new` example below.
import { FIELD_TYPES } from '../../src/lib/model-rules.mjs';

const COMMON = [
  'Common options:',
  '  --check        validate + show the migration it would write; change nothing',
  '  --repo <path>  the agent repo: its token is used for the probe and widened to reach a new entity',
  '  --no-probe     skip looking at the running admin',
  'One run edits config/models.json, writes + applies the migration (backup first), commits both on the',
  'local instance branch, checks the running admin and prints the screen, a sign-in link and the agent commands.',
  'Re-running the same request is harmless.',
];

const ADD = [
  'npm run model -- add-field <model> <field> --type <type> [--label "Text"] [--required]',
  '    [--min N] [--max N] [--options a,b,c] [--ref <entity>] [--pattern <regex>]',
  '  <model>: cases (alias: ugyek) or an own entity. --min/--max: number|integer only; --options: select only;',
  '  --ref: ref only; --pattern: text|textarea|email only. Changing a declared field is a hand-written migration.',
  '  npm run model -- add-field cases osszeg --type integer --min 0 --label "Összeg (Ft)"',
];

const NEW = [
  'npm run model -- new <entity> --label "Plural label" --field <spec> [--field <spec> …] [--ref <other-entity>]',
  '  <entity>: [a-z][a-z0-9_]*, up to 40 chars. --ref <other> adds a required ref field pointing at it (a unique',
  '  name prefix is enough). Every entity has at least one --field (or --ref).',
  '  <spec> = name:type[:required][:min=N][:max=N][:options=a|b|c][:ref=entity][:label=Text][:pattern=regex]',
  '  npm run model -- new ugyfelek --label "Ügyfelek" --field nev:text:required --field email:email',
  '  npm run model -- new szamlak --label "Számlák" --ref ugyfel --field osszeg:integer:min=0:label=Összeg --field esedekes:date',
];

/** Which help the argv asks for: 'all' | 'new' | 'add-field', or null when it is a normal run. */
export function helpTopic(argv) {
  const [cmd] = argv;
  const asked = argv.includes('--help') || argv.includes('-h');
  if (!cmd || cmd === '--help' || cmd === '-h' || cmd === 'help') return 'all';
  if (asked && (cmd === 'new' || cmd === 'add-field')) return cmd;
  return asked ? 'all' : null;
}

export function helpText(topic = 'all') {
  const types = `Field types: ${FIELD_TYPES.join(' | ')}  (checkbox, date = YYYY-MM-DD, select needs options)`;
  const parts = topic === 'new' ? [NEW] : topic === 'add-field' ? [ADD] : [ADD, NEW];
  return [...parts.flatMap((p) => [...p, '']), types, '', ...COMMON].join('\n');
}
