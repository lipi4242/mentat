// Fake external programs for the CLI tests (scripts/lib/tools.mjs reads
// MENTAT_WRANGLER / MENTAT_SSH / MENTAT_NPM / MENTAT_PBPASTE). Nothing here
// reaches Cloudflare or a real host.
//
// wrangler: appends {argv, stdin} as one JSON line to $FAKE_LOG, then answers
//   from $FAKE_RULES (a JSON list of {match, stdout?, stderr?, status?}; the
//   first rule whose `match` regex hits the space-joined argv wins).
// ssh: ignores its arguments and runs the piped program with node, as if on
//   the target: HOME=$FAKE_TARGET_HOME. FAKE_SSH_ANSWER replaces the answer.
import { chmodSync, mkdtempSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const WRANGLER = `#!/usr/bin/env node
const fs = require('node:fs');
const argv = process.argv.slice(2);
let stdin = '';
try { stdin = fs.readFileSync(0, 'utf8'); } catch {}
fs.appendFileSync(process.env.FAKE_LOG, JSON.stringify({ argv, stdin }) + '\\n');
const rules = process.env.FAKE_RULES && fs.existsSync(process.env.FAKE_RULES) ? JSON.parse(fs.readFileSync(process.env.FAKE_RULES, 'utf8')) : [];
const hit = rules.find((r) => new RegExp(r.match).test(argv.join(' ')));
if (hit && hit.stdout) process.stdout.write(hit.stdout);
if (hit && hit.stderr) process.stderr.write(hit.stderr);
process.exit(hit && hit.status ? hit.status : 0);
`;

const SSH = `#!/bin/sh
echo "$@" >> "$FAKE_LOG.ssh"
if [ -n "$FAKE_SSH_ANSWER" ]; then cat >/dev/null; printf '%s\\n' "$FAKE_SSH_ANSWER"; exit 0; fi
HOME="$FAKE_TARGET_HOME" exec node --input-type=module
`;

const ECHO = (name: string) => `#!/usr/bin/env node
const fs = require('node:fs');
let stdin = '';
try { stdin = fs.readFileSync(0, 'utf8'); } catch {}
fs.appendFileSync(process.env.FAKE_LOG, JSON.stringify({ tool: '${name}', argv: process.argv.slice(2), stdin }) + '\\n');
if ('${name}' === 'pbpaste') process.stdout.write(process.env.FAKE_CLIPBOARD || '');
`;

export type Call = { argv: string[]; stdin: string; tool?: string };

export function fakeBins() {
  const dir = mkdtempSync(join(tmpdir(), 'fakebin-'));
  const write = (name: string, body: string) => {
    const p = join(dir, name);
    writeFileSync(p, body);
    chmodSync(p, 0o755);
    return p;
  };
  const log = join(dir, 'calls.jsonl');
  const rules = join(dir, 'rules.json');
  const env = {
    MENTAT_WRANGLER: write('wrangler', WRANGLER),
    MENTAT_SSH: write('ssh', SSH),
    MENTAT_NPM: write('npm', ECHO('npm')),
    MENTAT_PBPASTE: write('pbpaste', ECHO('pbpaste')),
    FAKE_LOG: log,
    FAKE_RULES: rules,
  };
  return {
    dir,
    env,
    setRules: (r: { match: string; stdout?: string; stderr?: string; status?: number }[]) => writeFileSync(rules, JSON.stringify(r)),
    calls: (): Call[] => (existsSync(log) ? readFileSync(log, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l)) : []),
    rawLog: () => (existsSync(log) ? readFileSync(log, 'utf8') : ''),
  };
}
