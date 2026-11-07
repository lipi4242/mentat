"""A temp agent repo with a two-weeks-old markdown brain (design §9), and a
runner that calls the CLI exactly as an agent would: `python3 <cases_cli> ...`.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import fake_admin

CLI = Path(__file__).resolve().parent.parent / "cases_cli"
TODAY = "2026-10-15"
GAZ_ID = "01JAB6Z9Q3M8K7T2V5W4X1Y0RS"

GAZ = f"""---
type: case
case_id: {GAZ_ID}   # ULID, generated once
title: Gázszámla
status: open
next_action: Átutalni, amint megjön a számla
due_at: 2026-10-10
recurrence: monthly:10
anchor_at: 2026-09-10
category: háztartás
occurrences:
  - {{ due_at: 2026-09-10, status: done, done_at: 2026-09-08, note: átutalva }}
extra: {{}}
tags: [háztartás, pénzügy]
---

**Mi ez:** A havi gázszámla, 10-én esedékes.

**Számítás:** 12 400 Ft átalány.
"""
ADO = "---\ntype: case\ncase_id: 01JAB6Z9Q3M8K7T2V5W4X1Y0RT\ntitle: Adóbevallás\nstatus: open\nnext_action: Beküldeni\ndue_at: 2027-05-20\n---\n\nSZJA.\n"
KAR = ("---\ntype: case\ncase_id: 01JAB6Z9Q3M8K7T2V5W4X1Y0RV\ntitle: Kárigény\nstatus: waiting\nwaiting_on: a biztosító\n"
       "next_action: Rákérdezni\ndue_at: 2026-10-20\n---\n\nA csőtörés.\n")
LAKBER = ("---\ntype: case\ncase_id: 01JAB6Z9Q3M8K7T2V5W4X1Y0RW\ntitle: Lakbér\nstatus: open\nrecurrence: monthly:31\n"
          "anchor_at: 2026-08-31\ndue_at: 2026-08-31\n---\n\nHónap utolsó napja.\n")
PROJEKT = "---\ntype: project\ntitle: Gondolkodás\n---\n"
TEENDO = "---\ntype: todo\ntitle: Elmosogatni\n---\n"


class Repo(unittest.TestCase):
    files = {"gazszamla.md": GAZ, "ado.md": ADO, "karigeny.md": KAR, "lakber.md": LAKBER,
             "projekt.md": PROJEKT, "teendo.md": TEENDO}
    backend = "markdown"
    with_admin = False

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="cases-cli-"))
        (self.root / "mentat.json").write_text(json.dumps({
            "schema": 1, "agent": {"name": "teszt", "language": "hu"},
            "components": {"brain": {"root": "agy"}, "admin": {"plugins": ["cases"]}},
            "cases": {"backend": self.backend}}))
        local = {"schema": 1, "installed": {"brain": "0.2.0"}}
        self.srv = None
        if self.with_admin:
            self.srv = fake_admin.start()
            local["admin"] = {"url": "http://localhost:%d" % self.srv.server_port, "token_env": "CASES_T"}
            (self.root / ".env").write_text("CASES_T=%s\n" % fake_admin.TOKEN)
        (self.root / ".mentat").mkdir()
        (self.root / ".mentat" / "local.json").write_text(json.dumps(local))
        cases = self.root / "agy" / "cases"
        cases.mkdir(parents=True)
        for name, text in self.files.items():
            (cases / name).write_text(text)

    def tearDown(self):
        if self.srv:
            self.srv.shutdown()
            self.srv.server_close()
        shutil.rmtree(self.root, ignore_errors=True)

    @property
    def store(self):
        return self.srv.store

    def cli(self, *args, ok=True, today=TODAY):
        env = {k: v for k, v in os.environ.items() if k != "CASES_T"}
        p = subprocess.run([sys.executable, str(CLI), "--root", str(self.root), "--today", today, *args],
                           capture_output=True, text=True, env=env, timeout=60)
        if ok and p.returncode != 0:
            self.fail("cases %s -> %d\n%s%s" % (" ".join(args), p.returncode, p.stdout, p.stderr))
        return p

    def js(self, *args):
        return json.loads(self.cli("--json", *args).stdout)

    def text(self, name):
        return (self.root / "agy" / "cases" / name).read_text()

    def manifest(self):
        return json.loads((self.root / "mentat.json").read_text())
