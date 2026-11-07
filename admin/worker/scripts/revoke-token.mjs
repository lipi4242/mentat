#!/usr/bin/env node
// Revoke agent tokens: one by id, or every active token of an agent.
//
//   npm run revoke-token -- --id <token-id> --local|--remote
//   npm run revoke-token -- --agent <name>  --local|--remote
//
// Revoked tokens stay in the table (inactive) so the audit trail's
// actor_token_id keeps pointing somewhere.
import { revoke } from './lib/mint.mjs';
import { d1Query, flag, parseTarget } from './lib/d1.mjs';

const argv = process.argv.slice(2);
const target = parseTarget(argv);
if (!target) {
  console.error('usage: npm run revoke-token -- (--id <id> | --agent <name>) --local|--remote');
  process.exit(1);
}
try {
  const ids = await revoke(d1Query(target), { id: flag(argv, '--id'), label: flag(argv, '--agent') });
  console.log(ids.length ? `revoked: ${ids.join(', ')}` : 'nothing to revoke (no matching active token)');
} catch (err) {
  console.error(`revoke-token: ${err instanceof Error ? err.message : err}`);
  process.exit(1);
}
