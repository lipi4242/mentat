// The CLI mint builds SQL as text (wrangler cannot bind parameters), so the
// guard is validation first, escaping second, and the plaintext never in it.
import { describe, it, expect } from 'vitest';
import { prepareMint, revoke } from '../scripts/lib/mint.mjs';
import { hashToken } from '../src/lib/tokens';

describe('CLI mint', () => {
  it('stores the hash, never the plaintext, with an explicit expiry', async () => {
    const m = await prepareMint({ label: 'agent1', scopes: 'cases:write,cases:read', days: '30' }, new Date('2026-10-15T00:00:00Z'));
    expect(m.sql).not.toContain(m.token);
    expect(m.sql).toContain(await hashToken(m.token));
    expect(m.scopes).toBe('cases:write cases:read');
    expect(m.expires_at).toBe('2026-11-14 00:00:00');
  });

  it.each([
    [{ label: "x'); DROP TABLE agent_token; --", scopes: 'cases:write' }, /label/],
    [{ label: 'x', scopes: "cases:write'" }, /scope/],
    [{ label: 'x', scopes: 'cases:write', days: '1e3' }, /days/],
    [{ label: 'x', scopes: 'cases:write', days: 400 }, /days/],
  ])('refuses before building any SQL: %#', async (req, msg) => {
    await expect(prepareMint(req)).rejects.toThrow(msg);
  });

  it('revokes by id or by agent, never both or neither', async () => {
    const seen: string[] = [];
    const q = async (sqls: string[]) => (seen.push(...sqls), [[{ id: 'a' }]]);
    expect(await revoke(q, { label: 'agent1' })).toEqual(['a']);
    expect(seen[0]).toMatch(/WHERE label = 'agent1' AND active = 1/);
    await expect(revoke(q, {})).rejects.toThrow(/exactly one/);
    await expect(revoke(q, { id: 'not-a-uuid' })).rejects.toThrow(/uuid/);
  });
});
