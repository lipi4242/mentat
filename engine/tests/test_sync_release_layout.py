"""sync-to.sh in the one-repo release: LICENSE/NOTICE live once at the repo root
(mentat/LICENSE), not next to the script (mentat/engine/). The vendored copy must
still carry both; a fresh install stopped here before (0.5.0 smoke)."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent  # engine/release (dev) or engine/ (release)
if not (ENGINE / "sync-to.sh").is_file():  # the vendored copy in an agent repo has no sync-to.sh
    raise unittest.SkipTest("sync-to.sh not present (vendored copy)")


class SyncReleaseLayout(unittest.TestCase):
    def _run(self, keep_next_to_script: bool, at_root: bool, extra=()):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        eng = tmp / "mentat" / "engine"
        shutil.copytree(ENGINE, eng, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        lic = next(p for p in (ENGINE / "LICENSE", ENGINE.parent / "LICENSE", ENGINE.parent.parent / "LICENSE") if p.is_file())
        note = lic.with_name("NOTICE")
        for f in ("LICENSE", "NOTICE"):
            (eng / f).unlink(missing_ok=True)
            if keep_next_to_script:
                shutil.copy(lic.with_name(f), eng / f)
            if at_root:
                shutil.copy(lic.with_name(f), tmp / "mentat" / f)
        agent = tmp / "agent"
        agent.mkdir()
        subprocess.run(["git", "init", "-q", str(agent)], check=True)
        if extra:  # egy valódi ágens-repónak van mentat.json-ja; a csomag ebbe listázódik
            (agent / "mentat.json").write_text('{"schema": 1, "components": {"brain": {"root": "agy"}, "engine": {}}}')
        r = subprocess.run(["bash", str(eng / "sync-to.sh"), str(agent), *extra], capture_output=True, text=True,
                           env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": str(tmp)})
        return r, agent

    def test_release_layout_takes_license_from_repo_root(self):
        r, agent = self._run(keep_next_to_script=False, at_root=True)
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        self.assertTrue((agent / "anytime_engine" / "LICENSE").is_file())
        self.assertTrue((agent / "anytime_engine" / "NOTICE").is_file())

    def test_missing_license_everywhere_fails_loudly(self):
        r, _ = self._run(keep_next_to_script=False, at_root=False)
        self.assertNotEqual(r.returncode, 0)

    def test_todo_pack_is_vendored_and_listed(self):
        # 11-07: a 0.5.0 backlogja (anytime_todo) nem volt vendorolható, mert a
        # sync-to.sh csak a calendar/cases/bekotes csomagot ismerte.
        r, agent = self._run(keep_next_to_script=False, at_root=True, extra=("--pack", "todo"))
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        self.assertTrue((agent / "anytime_todo" / "cli.py").is_file())
        import json
        eng = json.loads((agent / "mentat.json").read_text())["components"]["engine"]
        self.assertIn("anytime_todo", eng["plugins"])


if __name__ == "__main__":
    unittest.main()
