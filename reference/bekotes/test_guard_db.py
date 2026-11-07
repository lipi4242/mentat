"""Direct database writes from the shell need the USER (friction log #26).

The class: an agent "fixes the data" with a database CLI instead of the app's own path,
so the only boundary left is the credential's scope. one agent's D1 write ban rested on the
Cloudflare token alone. Gated (ask interactively, deny headless): `wrangler d1 execute` /
`d1 migrations apply`, sqlite3, psql and mysql, when the SQL writes or cannot be read.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import unittest

from test_guard_kint import KintBase

GATED = (
    'wrangler d1 execute crm --remote --command "UPDATE leads SET status=\'lost\'"',
    "npx wrangler d1 execute crm --remote --file=fix.sql",            # the file deletes
    "npx wrangler d1 execute crm --file nincs.sql",                    # unreadable: undecidable
    "wrangler d1 execute crm --remote",                                # no SQL given: undecidable
    "wrangler d1 migrations apply crm --remote",
    'sqlite3 app.db "DELETE FROM orders"',
    "sqlite3 app.db < fix.sql",
    "sqlite3 app.db",                                                  # interactive: undecidable
    'psql "$DATABASE_URL" -c "drop table users"',
    "psql -f fix.sql shop",
    'mysql -e "INSERT INTO t VALUES (1)" shop',
    "mysql shop < fix.sql",
    'sqlite3 app.db "PRAGMA journal_mode=WAL"',
    # CISO, #76: D-1 the destructive d1 subcommands, D-2 runner variants, D-3 sqlite3 dot commands
    "wrangler d1 delete crm",
    "wrangler d1 time-travel restore crm --bookmark 00000085",
    "wrangler d1 create crm2",
    'npx --yes wrangler@3 d1 execute crm --remote --command "DELETE FROM leads"',
    'npm exec -- wrangler d1 execute crm --remote --command "DELETE FROM leads"',
    "npm x wrangler d1 delete crm",
    'npx -p wrangler@3 wrangler d1 execute crm --command "DROP TABLE leads"',
    "sqlite3 app.db '.import data.csv leads'",
    "sqlite3 app.db '.restore backup.db'",
    "sqlite3 -cmd 'DELETE FROM leads' app.db",
    "sqlite3 -cmd 'DELETE FROM leads' app.db 'SELECT 1'",  # the -cmd value is SQL too
    "sqlite3 app.db '.read fix.txt'",
)
FINE = (
    'wrangler d1 execute crm --remote --command "SELECT count(*) FROM leads"',
    "npx wrangler d1 execute crm --file=read.sql",
    "wrangler d1 list",
    "wrangler deploy",
    'sqlite3 app.db "SELECT * FROM orders LIMIT 5"',
    'psql shop -c "select 1"',
    'mysql -e "SHOW TABLES" shop',
    "wrangler d1 info crm",
    "wrangler d1 export crm --remote --output backup.sql",
    "npx wrangler@3 d1 list",
    "sqlite3 app.db '.tables'",
    "sqlite3 app.db '.schema leads'",
)


class DbWrite(KintBase):
    roles = False

    def setUp(self):
        super().setUp()
        (self.root / "fix.sql").write_text("-- javítás\nDELETE FROM leads WHERE id = 7;\n")
        (self.root / "read.sql").write_text("SELECT * FROM leads;\n")

    def test_writes_and_undecidable_sql_are_gated(self):
        for cmd in GATED:
            self.assertEqual(self.bash(cmd), "ask", cmd)
            self.assertEqual(self.bash(cmd, mode="bypassPermissions"), "deny", "headless: " + cmd)

    def test_reads_stay_open(self):
        for cmd in FINE:
            self.assertEqual(self.bash(cmd), "allow", cmd)


if __name__ == "__main__":
    unittest.main()
