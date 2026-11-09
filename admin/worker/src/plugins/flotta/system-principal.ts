// A flotta-ellenőrzés saját todo-résztvevője (CISO AD-10): a rendszer a feladatot a
// SAJÁT nevében hozza létre, kommenteli és zárja, nem a menedzserében — a todo
// eseménynaplója így igazat mond arról, ki mit tett.
//
// A todo séma ágens-résztvevőhöz gépi tokent köt (agent_token_id NOT NULL). Ez egy
// INAKTÍV, lejárt, jogkör nélküli token-sor, aminek a hash-e nem egy valódi token
// SHA-256-ja: ezzel senki nem tud belépni. A résztvevő letiltott (disabled_at), így
// senki nem jelentkezhet be vele és nem osztható ki rá munka; a sorai olvashatók maradnak.
export const SYSTEM_PRINCIPAL = 'flotta-rendszer';

export async function ensureSystemPrincipal(db: D1Database): Promise<string> {
  await db.batch([
    db.prepare(`INSERT OR IGNORE INTO agent_token (id, label, token_hash, scopes, active, expires_at)
        VALUES (?1, 'flotta-rendszer', 'disabled:flotta-rendszer', '', 0, '1970-01-01 00:00:00')`).bind(SYSTEM_PRINCIPAL),
    db.prepare(`INSERT OR IGNORE INTO todo_principal (id, kind, handle, display_name, agent_token_id, created_by, idem_key, disabled_at)
        VALUES (?1, 'agent', 'flotta_rendszer', 'Flotta-ellenőrzés', ?1, 'flotta', 'flotta-rendszer', '1970-01-01T00:00:00Z')`).bind(SYSTEM_PRINCIPAL),
  ]);
  return SYSTEM_PRINCIPAL;
}
