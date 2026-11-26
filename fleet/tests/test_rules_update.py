"""A szabályfájl frissítése: doctor/status jelzés, box-upgrade terv és PR, a második renderelő a deliver úton."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("FLEET_MAINTENANCE_DIR", tempfile.mkdtemp(prefix="fleet-test-locks-"))

from fleet import box_rules, deliver_cli, doctor, join, rules_state, status  # noqa: E402
from fleet.box_ctx import Ctx  # noqa: E402
from test_deliver import GIT_ENV, FakeGh, g, real_git  # noqa: E402
from test_truthful_health import _entry, _m  # noqa: E402

OLD_TMPL = "<!-- Mentat fleet rules v@@FLEET_VERSION@@ -->\n@@AGENT@@ régi szabály\n"
TARGET_TMPL = "<!-- Mentat fleet rules v@@FLEET_VERSION@@ -->\n@@AGENT@@ új szabály\n"


def make_repo(root: Path, name: str, *, modified: bool = False, current: bool = False) -> Path:
    """Egy ágens-repó bare origin-nel; a szabályfájl régi (vagy naprakész / helyben módosított)."""
    origin = root / f"{name}.git"
    g(root, "init", "-q", "--bare", "-b", "main", str(origin))
    repo = root / name
    g(root, "clone", "-q", str(origin), str(repo))
    g(repo, "checkout", "-q", "-b", "main")
    rules = join.render_rules(name) if current else join.render_rules(name, template=OLD_TMPL.replace("@@FLEET_VERSION@@", "0.0.1"))
    (repo / ".claude" / "rules").mkdir(parents=True)
    (repo / ".claude" / "fleet.json").write_text(json.dumps(
        {"agent": name, "components": {"fleet": "0.0.1"}, "rules_sha": join._sha(rules)}))
    (repo / ".claude" / "rules" / "fleet.md").write_text(rules + ("helyi sor\n" if modified else ""))
    g(repo, "add", "-A")
    g(repo, "commit", "-q", "-m", "init")
    g(repo, "push", "-q", "origin", "main")
    return repo


class Base(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)


class Signals(Base):
    def test_doctor_names_both_versions_and_stays_silent_when_current(self):
        stale = make_repo(self.d, "a-stale")
        w = rules_state.warnings_for({"agent": "a-stale", "workdir": str(stale)})
        self.assertEqual(len(w), 1)
        st = rules_state.state(stale)
        self.assertIn(f"szabályok {st['have_sha']} < telepített {st['want_sha']}", w[0])
        self.assertIn("v0.0.1 <", w[0])
        self.assertIn("--pr --rules", w[0])
        fresh = make_repo(self.d, "b-fresh", current=True)
        self.assertEqual(rules_state.warnings_for({"agent": "b-fresh", "workdir": str(fresh)}), [])

    def test_doctor_report_carries_the_warning(self):
        stale = make_repo(self.d, "probe-agent")
        e = _entry(workdir=str(stale))
        unit_dir = Path(tempfile.mkdtemp())
        (unit_dir / f"{e['unit']}.d").mkdir()
        (unit_dir / f"{e['unit']}.d" / "10-session-gate.conf").write_text("")
        with mock.patch.object(doctor, "load_agents", return_value=[e]), \
                mock.patch.object(doctor, "local_host", return_value="probe-host"), \
                mock.patch.object(doctor, "load_state", return_value={"quarantined": False}), \
                mock.patch.object(doctor, "_sysctl_prop", return_value="active"), \
                mock.patch.object(doctor, "UNIT_DIR", str(unit_dir)), \
                mock.patch("fleet.signals.measure", return_value=_m()), \
                mock.patch("fleet.hookguard.claude_version", return_value="2.1.309 (Claude Code)"), \
                mock.patch("fleet.envjel.check", return_value=(None, None)):
            out = doctor.doctor(agent="probe-agent")
        self.assertTrue(any("szabályok" in w and "<" in w for w in out[0]["warnings"]), out[0]["warnings"])

    def test_status_notes_stale_rules_only_when_stale(self):
        stale = make_repo(self.d, "s-stale")
        r = status.status("s-stale", repo=stale)
        self.assertTrue(any("szabályok" in n for n in r["notes"]))
        fresh = make_repo(self.d, "s-fresh", current=True)
        self.assertFalse(any("szabályok" in n for n in status.status("s-fresh", repo=fresh)["notes"]))


class Renderer(Base):
    def run_cli(self, repo, gh, *extra):
        a = argparse.Namespace(repo=str(repo), pr=True, place=False, rules=True, agent=None, base="main", mode="standalone")
        out = io.StringIO()
        with redirect_stdout(out):
            rc = deliver_cli.run(a, git=real_git, gh=gh)
        return rc, [json.loads(x) for x in out.getvalue().splitlines()]

    def test_pr_changes_only_rules_and_manifest(self):
        repo = make_repo(self.d, "r-stale")
        gh = FakeGh()
        rc, res = self.run_cli(repo, gh)
        self.assertEqual((rc, res[0]["status"], res[0]["kind"]), (0, "opened", "rules"))
        self.assertEqual(len(gh.creates()), 1)
        self.assertEqual(sorted(g(repo.parent / "r-stale.git", "diff", "--name-only", "main", "fleet/rules-r-stale").split()),
                         [".claude/fleet.json", ".claude/rules/fleet.md"])
        self.assertEqual(g(repo, "status", "--porcelain"), "")

    def test_locally_modified_rules_are_skipped_with_reason(self):
        repo = make_repo(self.d, "r-mod", modified=True)
        gh = FakeGh()
        rc, res = self.run_cli(repo, gh)
        self.assertEqual((rc, res[0]["status"]), (0, "skipped"))
        self.assertIn("helyi módosítás", res[0]["reason"])
        self.assertEqual(gh.creates(), [])

    def test_current_rules_open_no_pr(self):
        repo = make_repo(self.d, "r-fresh", current=True)
        gh = FakeGh()
        self.assertEqual(self.run_cli(repo, gh)[1][0]["status"], "unchanged")
        self.assertEqual(gh.creates(), [])


class BoxStep(Base):
    def setUp(self):
        super().setUp()
        self.home = self.d / "home"
        self.src = self.home / "src" / "mentat"
        (self.src / "fleet" / "templates" / "rules").mkdir(parents=True)
        (self.src / "fleet" / "src" / "fleet").mkdir(parents=True)
        (self.src / "fleet" / "templates" / "rules" / "fleet.md.tmpl").write_text(TARGET_TMPL)
        (self.src / "fleet" / "src" / "fleet" / "__init__.py").write_text('__version__ = "9.9.9"\n')
        g(self.src, "init", "-q", "-b", "main")
        g(self.src, "add", "-A")
        g(self.src, "commit", "-q", "-m", "v9")
        self.repos = {n: make_repo(self.home, n, **kw) for n, kw in
                      (("alfa", {}), ("beta", {"modified": True}), ("gamma", {"current": False}))}
        # gamma és a delta naprakész a CÉL-sablonhoz mérve
        tgt = join.render_rules("delta", template=TARGET_TMPL.replace("@@FLEET_VERSION@@", "9.9.9"))
        self.repos["delta"] = make_repo(self.home, "delta")
        (self.repos["delta"] / ".claude" / "rules" / "fleet.md").write_text(tgt)
        m = json.loads((self.repos["delta"] / ".claude" / "fleet.json").read_text())
        m["rules_sha"] = join._sha(tgt)
        (self.repos["delta"] / ".claude" / "fleet.json").write_text(json.dumps(m))
        self.lines, self.calls = [], []
        self.sha = g(self.src, "rev-parse", "HEAD")

    def ctx(self, rules_pr=False):
        c = Ctx(home=self.home, tag="v9", say=self.lines.append, run=self.fake_run)
        c.state.update(target_sha=self.sha, rules_pr=rules_pr,
                       registry_agents=[{"agent": n, "workdir": str(r), "host": "h"} for n, r in self.repos.items()])
        return c

    def fake_run(self, cmd):
        if cmd[0] == str(Ctx(home=self.home, tag="v9").new_fleet):
            self.calls.append(cmd)
            repo, agent = cmd[2], cmd[cmd.index("--agent") + 1]
            a = argparse.Namespace(repo=repo, pr=True, place=False, rules=True, agent=agent, base="main", mode="standalone")
            out = io.StringIO()
            with redirect_stdout(out):
                deliver_cli.run(a, git=real_git, gh=self.gh)
            return subprocess.CompletedProcess(cmd, 0, out.getvalue(), "")
        return subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, **GIT_ENV})

    gh = FakeGh()

    def test_dry_run_plan_lists_exactly_the_stale_repos(self):
        text = "\n".join(box_rules.plan(self.ctx()))
        for n in ("alfa", "beta", "gamma"):
            self.assertIn(f"  {n}:", text)
        self.assertNotIn("  delta:", text)
        self.assertIn("PR nincs kérve", text)
        self.assertIn("PR nem nyitható", text)  # beta: helyi módosítás

    def test_plan_without_target_says_so(self):
        c = self.ctx()
        c.state.pop("target_sha")
        self.assertIn("váltás után", box_rules.plan(c)[0])

    def test_without_flag_no_pr_but_the_output_says_why(self):
        box_rules.apply(self.ctx())
        self.assertEqual(self.calls, [])
        self.assertTrue(any("PR nincs kérve" in x for x in self.lines))

    def test_with_flag_each_stale_repo_gets_a_pr_or_a_reason(self):
        self.gh = FakeGh()
        box_rules.apply(self.ctx(rules_pr=True))
        text = "\n".join(self.lines)
        self.assertEqual(sorted(Path(c[2]).name for c in self.calls), ["alfa", "gamma"])
        self.assertEqual(len(self.gh.creates()), 2)
        self.assertIn("alfa: opened", text)
        self.assertIn("beta: nem nyitok PR-t — helyi módosítás", text)
        self.assertNotIn("delta", text)

    def test_step_never_fails_the_upgrade(self):
        c = self.ctx(rules_pr=True)
        c.run = mock.Mock(side_effect=OSError("nincs gh"))
        box_rules.apply(c)   # nem dob
        self.assertTrue(any("nem sikerült" in x for x in self.lines))


if __name__ == "__main__":
    unittest.main()
