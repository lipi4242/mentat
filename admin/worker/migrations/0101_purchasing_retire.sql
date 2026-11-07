-- Purchasing plugin retired (AD2). Band 0100–0199 stays reserved
-- (config/plugins.ts RETIRED_BANDS); 0100_purchasing.sql is left as it was,
-- because D1 tracks applied migrations by name.
--
-- The plugin never went into use. Its rows are not migrated anywhere: the
-- way to keep them is the export that `npm run migrate:local|remote` writes
-- to config/backups/ before applying this file (and that stops the migration
-- if it fails). Untouched here: auth_* (the user), agent_token (the tokens),
-- and the core "case" / case_event tables.
--
-- Children before parents: allocation RESTRICTs on need_item, so dropping a
-- parent first would fail on any surviving allocation row.
DROP TABLE IF EXISTS allocation;
DROP TABLE IF EXISTS intent_item;
DROP TABLE IF EXISTS purchase_intent;
DROP TABLE IF EXISTS offer;
DROP TABLE IF EXISTS product;
DROP TABLE IF EXISTS supplier;
DROP TABLE IF EXISTS need_item;
DROP TABLE IF EXISTS purchase_need;
