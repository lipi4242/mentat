"""`fleet upgrade --pr` (a fleet-place blokk PR-ként) és a doctor drift-sora. Helyi bare origin, hamis `gh`."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp)
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fleet import cli, deliver, place_drift  # noqa: E402

EX = Path(__file__).resolve().parents[1] / "examples" / "registry"
SELF = "<!-- mentat:managed:start self-image -->\nkép\n<!-- mentat:managed:end self-image -->\n"
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.org", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.org", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}


def g(cwd, *args):
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, env={**os.environ, **GIT_ENV})
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


class FakeGh:
    def __init__(self, open_pr="", labels="release:queue\nrelease:track/agy\nmás"):
        self.calls, self.open_pr, self.labels = [], open_pr, labels

    def __call__(self, args, cwd):
        self.calls.append(list(args))
        if args[:3] == ["gh", "pr", "list"]:
            return 0, self.open_pr
        if args[:3] == ["gh", "label", "list"]:
            return 0, self.labels
        if args[:3] == ["gh", "pr", "create"]:
            return 0, "https://example.org/o/r/pull/1"
        return 1, "ismeretlen"

    def creates(self):
        return [c for c in self.calls if c[:3] == ["gh", "pr", "create"]]


def real_git(args, cwd):
    r = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, env={**os.environ, **GIT_ENV})
    return r.returncode, r.stdout.strip()


class Base(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.reg = self.d / "reg"
        shutil.copytree(EX, self.reg)
        self.old = os.environ.get("FLEET_REGISTRY")
        os.environ["FLEET_REGISTRY"] = str(self.reg)
        self.origin = self.d / "origin.git"
        g(self.d, "init", "-q", "--bare", "-b", "main", str(self.origin))
        self.repo = self.d / "demo-agent"
        g(self.d, "clone", "-q", str(self.origin), str(self.repo))
        g(self.repo, "checkout", "-q", "-b", "main")
        (self.repo / "AGENTS.md").write_text("# Ágens\n" + SELF + "\nMás rész.\n")
        (self.repo / ".claude").mkdir()
        (self.repo / ".claude" / "fleet.json").write_text(json.dumps({"agent": "demo-agent"}))
        (self.repo / ".release-agent").mkdir()
        (self.repo / ".release-agent" / "config.json").write_text(json.dumps({"tracks": {"agy": {"paths": ["AGENTS.md"]}}}))
        g(self.repo, "add", "-A")
        g(self.repo, "commit", "-q", "-m", "init")
        g(self.repo, "push", "-q", "origin", "main")

    def tearDown(self):
        if self.old is None:
            os.environ.pop("FLEET_REGISTRY", None)
        else:
            os.environ["FLEET_REGISTRY"] = self.old
        shutil.rmtree(self.d, ignore_errors=True)

    def deliver(self, gh):
        from fleet import deliver_cli
        from fleet.fleet_place_cli import _load
        fmap, _ = _load()
        return deliver.deliver(self.repo, fmap, "demo-agent", deliver_cli.place_renderer("standalone"),
                               branch="fleet/place-demo-agent", title="chore(fleet): fleet-place", body="b",
                               base="main", git=real_git, gh=gh)


class Deliver(Base):
    def test_opens_one_pr_where_only_the_block_changes(self):
        gh = FakeGh()
        r = self.deliver(gh)
        self.assertEqual((r["status"], r["files"]), ("opened", ["AGENTS.md"]))
        self.assertEqual(len(gh.creates()), 1)
        c = gh.creates()[0]
        self.assertEqual([c[i + 1] for i, x in enumerate(c) if x == "--label"], ["release:queue", "release:track/agy"])
        self.assertEqual(g(self.origin, "diff", "--name-only", "main", "fleet/place-demo-agent"), "AGENTS.md")
        diff = g(self.origin, "diff", "-U0", "main", "fleet/place-demo-agent")
        added = [l for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
        self.assertIn("fleet-place", "\n".join(added))
        self.assertFalse([l for l in diff.splitlines() if l.startswith("-") and not l.startswith("---")])
        self.assertTrue(any("Otthon:" in l for l in added))
        self.assertEqual(g(self.repo, "status", "--porcelain"), "")  # a saját checkout érintetlen

    def test_labels_only_if_repo_has_them(self):
        gh = FakeGh(labels="egyéb")
        self.deliver(gh)
        self.assertNotIn("--label", gh.creates()[0])

    def test_second_run_without_change_opens_nothing_new(self):
        gh = FakeGh()
        self.deliver(gh)
        gh2 = FakeGh(open_pr="1")
        r = self.deliver(gh2)
        self.assertEqual((r["status"], r["pr"]), ("up-to-date", 1))
        self.assertEqual(gh2.creates(), [])

    def test_unchanged_map_after_merge_opens_no_pr(self):
        self.deliver(FakeGh())
        g(self.repo, "fetch", "-q", "origin")
        g(self.repo, "merge", "-q", "--ff-only", "origin/fleet/place-demo-agent")
        g(self.repo, "push", "-q", "origin", "main")
        gh = FakeGh()
        self.assertEqual(self.deliver(gh)["status"], "unchanged")
        self.assertEqual(gh.creates(), [])

    def test_existing_open_pr_is_updated_not_duplicated(self):
        self.deliver(FakeGh())
        m = json.loads((self.reg / "fleet-map.json").read_text())
        m["agents"]["demo-agent"]["reports_to"] = "human:Más Ember"
        (self.reg / "fleet-map.json").write_text(json.dumps(m))
        before = g(self.origin, "rev-parse", "fleet/place-demo-agent")
        gh = FakeGh(open_pr="1")
        r = self.deliver(gh)
        self.assertEqual((r["status"], r["pr"]), ("updated", 1))
        self.assertEqual(gh.creates(), [])
        self.assertNotEqual(g(self.origin, "rev-parse", "fleet/place-demo-agent"), before)

    def test_cli_flag_unchanged_exit(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cli.main(["upgrade", str(self.repo), "--pr", "--agent", "nincs-ilyen"])
        self.assertEqual(rc, 1)


class Doctor(Base):
    def entry(self):
        return {"agent": "demo-agent", "workdir": str(self.repo)}

    def test_drift_is_named_per_repo_and_silent_without_drift(self):
        w = place_drift.warnings_for(self.entry())
        self.assertEqual(len(w), 1)
        self.assertIn(str(self.repo), w[0])
        with redirect_stdout(io.StringIO()):
            cli.main(["map", "render", "demo-agent", "--repo", str(self.repo)])
        self.assertEqual(place_drift.warnings_for(self.entry()), [])

    def test_silent_without_map_or_local_repo(self):
        (self.reg / "fleet-map.json").unlink()
        self.assertEqual(place_drift.warnings_for(self.entry()), [])
        shutil.rmtree(self.repo)
        self.assertEqual(place_drift.warnings_for(self.entry()), [])

    def test_drift_when_map_changes(self):
        with redirect_stdout(io.StringIO()):
            cli.main(["map", "render", "demo-agent", "--repo", str(self.repo)])
        m = json.loads((self.reg / "fleet-map.json").read_text())
        m["agents"]["demo-agent"]["reports_to"] = "human:Más Ember"
        (self.reg / "fleet-map.json").write_text(json.dumps(m))
        self.assertEqual(len(place_drift.warnings_for(self.entry())), 1)


if __name__ == "__main__":
    unittest.main()
