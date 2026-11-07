"""Képességfa, 2. fázis: new executable code, a unit, a schedule or a new package needs a fresh,
decided capability receipt (`where --find` + `--decide`); without one: deny in BOTH modes, with
the finder's command, because the agent resolves it itself and the USER is not the one to ask.

The receipts are the finder's, not the agent's: writing one by hand (Write, `echo >`, python -c)
is always denied, while `mentat_brain.py where --decide <receipt>` stays open.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time
import unittest

from test_guard_kint import KintBase

R = ".mentat/state/capability-receipts"
GATED_BASH = (
    "systemctl --user enable --now riport.timer",
    "systemctl --user link /x/riport.service",
    "crontab -e",
    "crontab uj.cron",
    "pip install gspread",
    "pip3 install --user google-auth-oauthlib",
    "python3 -m pip install requests",
    "npm install express",
    "npm i -D vite",
    "npm --prefix site install zod --save",
    "echo 'print(1)' > projects/lista/futtat.py",
)
OPEN_BASH = (
    "crontab -l",
    "systemctl --user status riport.timer",
    "systemctl --user list-timers",
    "pip install -r requirements.txt",
    "npm install",
    "npm ci",
    "npm install --silent 2>&1",          # the 2 of 2>&1 is not a package (found in the replay)
    "bun install --frozen-lockfile 2>&1 | tail -3",
    "npm --prefix site install",
    "npm install --silent 2>&1;echo ok",
    "pip list",
    "python3 projects/lista/meglevo.py",
    "echo 'x' > projects/lista/jegyzet.md",
)


class NewCapability(KintBase):
    roles = False

    def setUp(self):
        super().setUp()
        (self.root / "projects" / "lista").mkdir(parents=True)
        (self.root / "projects" / "lista" / "meglevo.py").write_text("print(1)\n")

    def receipt(self, decision="enable", age_h=0.0, name="r1.json", ledger=True):
        d = self.root / R
        d.mkdir(parents=True, exist_ok=True)
        at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - age_h * 3600))
        doc = {"schema": 1, "query": "q", "candidates": [{"id": "engine.cases"}],
               "decision": decision and {"decision": decision, "candidate": "engine.cases", "decided_at": at}}
        body = json.dumps(doc)
        (d / name).write_text(body)
        if decision and ledger:  # what the finder writes next to its decision
            with open(d / "_ledger.jsonl", "a") as f:
                f.write(json.dumps({"receipt": name, "sha256": hashlib.sha256(body.encode()).hexdigest(),
                                    "decided_at": at}) + "\n")

    def write(self, rel, mode="default"):
        return self.d("Write", {"file_path": str(self.root / rel), "content": "x"}, mode=mode)

    def test_new_executable_unit_schedule_or_package_without_a_receipt_is_denied(self):
        for rel in ("projects/lista/kuld.py", "projects/lista/web/app.ts", "riport.timer",
                    "concerns/tagdij.py", "deploy/riport.service"):
            self.assertEqual(self.write(rel), "deny", rel)
            self.assertEqual(self.write(rel, "bypassPermissions"), "deny", "headless: " + rel)
        for cmd in GATED_BASH:
            self.assertEqual(self.bash(cmd), "deny", cmd)
            self.assertEqual(self.bash(cmd, mode="bypassPermissions"), "deny", "headless: " + cmd)

    def test_existing_files_restores_and_reads_stay_open(self):
        self.assertEqual(self.d("Edit", {"file_path": str(self.root / "projects/lista/meglevo.py"),
                                         "old_string": "1", "new_string": "2"}), "allow")
        self.assertEqual(self.write("projects/lista/jegyzet.md"), "allow")
        self.assertEqual(self.write("agy/todos/uj.md"), "allow")
        for cmd in OPEN_BASH:
            self.assertEqual(self.bash(cmd), "allow", cmd)

    def test_a_fresh_decided_receipt_opens_it(self):
        self.receipt("new")
        self.assertEqual(self.write("projects/lista/kuld.py"), "allow")
        self.assertEqual(self.bash("pip install gspread"), "allow")

    def test_undecided_or_old_receipts_do_not_count(self):
        self.receipt(decision=None, name="a.json")
        self.receipt("enable", age_h=7, name="b.json")
        self.assertEqual(self.write("projects/lista/kuld.py"), "deny")

    def test_only_the_finders_ledger_makes_a_receipt_count(self):  # CISO #81, 1
        self.receipt("new", ledger=False, name="kamu.json")
        self.assertEqual(self.write("projects/lista/kuld.py"), "deny")
        self.receipt("new", name="r1.json")
        self.assertEqual(self.write("projects/lista/kuld.py"), "allow")
        p = self.root / R / "r1.json"
        p.write_text(p.read_text().replace("engine.cases", "web.publish"))  # edited after the decision
        self.assertEqual(self.write("projects/lista/kuld.py"), "deny")

    def test_the_real_finder_and_decide_open_it_end_to_end(self):
        brain = pathlib.Path(__file__).resolve().parent.parent / "manifest" / "mentat_brain.py"
        run = lambda *a: subprocess.run([sys.executable, str(brain), "--repo", str(self.root), "where", *a],
                                        capture_output=True, text=True)
        self.assertEqual(self.write("projects/lista/kuld.py"), "deny")
        out = json.loads(run("--find", "minden reggel írd ki, ki nem fizetett", "--json").stdout)
        self.assertEqual(self.write("projects/lista/kuld.py"), "deny")  # found, not decided yet
        r = run("--decide", out["receipt"], "enable", "--candidate", out["candidates"][0]["id"])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.write("projects/lista/kuld.py"), "allow")

    def test_the_deny_names_the_finder_and_is_not_a_question_for_the_user(self):
        for mode in ("default", "bypassPermissions"):
            r = self.run_guard(self.payload("Write", {"file_path": str(self.root / "projects/lista/kuld.py"),
                                                      "content": "x"}, mode))
            reason = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
            for part in ("where --find", "--decide", "nem a FELHASZNÁLÓnak szóló kérdés"):
                self.assertIn(part, reason, mode)


if __name__ == "__main__":
    unittest.main()
