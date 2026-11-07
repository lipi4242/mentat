#!/usr/bin/env node
// Mint an agent token. Prints the plaintext ONCE — only its hash is stored.
//
//   npm run mint-token -- --agent <name> --scope cases:write [--days 90] --local|--remote [--dry-run]
//
// --scope takes a comma- or space-separated list. Every token expires
// (default 90 days, at most 365). To bind the token straight into an agent
// repo without ever seeing it, use `npm run connect` instead.
//
// Minting for an agent on ANOTHER box, without the secret ever leaving it:
//
//   npm run mint-token -- --agent <name> --scope todo:write --remote \
//       --on <ssh-target> --token-file '~/.config/<agent>/admin-token' [--remote-node <path>]
//
// The token is made on the target (scripts/lib/mint-on.mjs) and written there
// 0600; this machine sees only its id and hash, and prints neither the token
// nor anything derived from it beyond the id. An existing token file is never
// overwritten. Quote a `~/` path so your shell does not expand it locally.
import { buildMint, prepareMint, mint } from './lib/mint.mjs';
import { mintOn, sshArgs } from './lib/mint-on.mjs';
import { d1Query, flag, parseTarget } from './lib/d1.mjs';

const argv = process.argv.slice(2);
const target = parseTarget(argv);
const request = { label: flag(argv, '--agent'), scopes: flag(argv, '--scope'), ...(flag(argv, '--days') ? { days: flag(argv, '--days') } : {}) };
const on = flag(argv, '--on');
const tokenFile = flag(argv, '--token-file');
const remoteNode = flag(argv, '--remote-node');
if (!target || !request.label || !request.scopes || (on && !tokenFile) || (!on && tokenFile)) {
  console.error('usage: npm run mint-token -- --agent <name> --scope <resource:action>[,…] [--days N] --local|--remote [--dry-run]\n' +
    '                    [--on <ssh-target> --token-file <path on the target> [--remote-node <path>]]');
  process.exit(1);
}

try {
  if (argv.includes('--dry-run')) {
    // With --on the id and hash come from the target: show placeholders.
    const { sql } = on ? buildMint(request, { id: '0'.repeat(8) + '-0000-0000-0000-' + '0'.repeat(12), hash: '0'.repeat(64) }) : await prepareMint(request);
    if (on) {
      console.log(`[dry-run] would run: ssh ${sshArgs(on, remoteNode).join(' ')}  (token-rules + driver on stdin)`);
      console.log(`[dry-run] the token would be written on ${on} to ${tokenFile} (0600, never overwritten)`);
      console.log('[dry-run] then, with the id and hash from there:');
    }
    console.log(`[dry-run] would execute on the ${target} database:\n\n${sql}\n\n[dry-run] no token was minted.`);
    process.exit(0);
  }
  if (on) {
    const t = await mintOn(d1Query(target), request, { on, tokenFile, remoteNode });
    console.log(`\nToken minted on ${on} and stored there: ${t.file} (0600). It was not shown here.\n`);
    console.log(`id=${t.id} agent="${t.label}" scopes="${t.scopes}" expires=${t.expires_at} UTC`);
    console.log(`revoke: npm run revoke-token -- --id ${t.id} --${target}`);
    process.exit(0);
  }
  const t = await mint(d1Query(target), request);
  console.log(`\nToken (store it now, it is not recoverable):\n\n  ${t.token}\n`);
  console.log(`id=${t.id} agent="${t.label}" scopes="${t.scopes}" expires=${t.expires_at} UTC`);
  console.log(`revoke: npm run revoke-token -- --id ${t.id} --${target}`);
} catch (err) {
  console.error(`mint-token: ${err instanceof Error ? err.message : err}`);
  process.exit(1);
}
