// Reading what wrangler prints. Its human output changes between versions,
// so each parser looks for the one value it needs, not for a layout, and
// fails loudly when it is not there.

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/;

export const alreadyExists = (text) => /already (exists|in use|taken)|exists already/i.test(text);

/** `wrangler d1 create` → database_id (TOML `database_id = "…"` or JSON `"database_id": "…"`). */
export function parseDatabaseId(text) {
  const m = String(text).match(new RegExp(`database_id"?\\s*[:=]\\s*"(${UUID.source})"`));
  if (!m) throw new Error('could not find database_id in the `wrangler d1 create` output');
  return m[1];
}

/** `wrangler d1 list --json` → the id of the database called `name`. */
export function findDatabase(text, name) {
  let list;
  try {
    list = JSON.parse(text);
  } catch {
    throw new Error('`wrangler d1 list --json` did not print JSON');
  }
  const hit = Array.isArray(list) ? list.find((d) => d && d.name === name) : undefined;
  const id = hit?.uuid ?? hit?.database_id ?? hit?.id;
  if (typeof id !== 'string' || !UUID.test(id)) throw new Error(`database ${name} is not in \`wrangler d1 list\``);
  return id;
}

/** `wrangler whoami` → the one account id. Several → the caller must choose. */
export function parseAccountId(text) {
  const ids = [...new Set(String(text).match(/\b[0-9a-f]{32}\b/g) ?? [])];
  if (ids.length === 1) return ids[0];
  if (!ids.length) throw new Error('no account id in `wrangler whoami` — are you logged in? (npx wrangler login)');
  throw new Error(`\`wrangler whoami\` lists ${ids.length} accounts — pass --account-id <id>`);
}

/** `wrangler deploy` → https://<name>.<subdomain>.workers.dev */
export function parseWorkersUrl(text) {
  const m = String(text).match(/https:\/\/[a-z0-9.-]+\.workers\.dev\b/i);
  if (!m) throw new Error('could not find the *.workers.dev URL in the `wrangler deploy` output');
  return m[0];
}

/** `wrangler pages project create` → https://<sub>.pages.dev, or null. */
export function parsePagesUrl(text) {
  const m = String(text).match(/https:\/\/[a-z0-9-]+\.pages\.dev\b/i);
  return m ? m[0] : null;
}
