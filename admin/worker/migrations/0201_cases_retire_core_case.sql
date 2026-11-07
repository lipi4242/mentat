-- Retire the core's legacy "case" / case_event tables (0002_core.sql), now
-- that the cases plugin (0200_cases.sql) owns cases. Since the plugin PR no
-- code reads or writes them.
--
-- The rows are not carried over: in production they are 3 test cases with
-- the old Hungarian statuses (design doc §8). The way to keep them is the
-- export `npm run migrate:local|remote` writes to config/backups/ before it
-- applies this file (and the migration stops if that export fails).
--
-- Numbered in the cases band on purpose, not the core's: it must run after
-- 0101_purchasing_retire.sql, because the retired purchasing tables point at
-- "case" (ON DELETE CASCADE) and dropping "case" first would cascade into
-- them. Child before parent: case_event RESTRICTs on "case".
DROP TABLE IF EXISTS case_event;
DROP TABLE IF EXISTS "case";
