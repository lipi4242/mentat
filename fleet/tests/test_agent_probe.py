"""`fleet probe`: a box saját szemével mért auth, valódi modell és checkout-lemaradás
(2026-10-29: két ágens napokig „Login expired", egy box fleet-checkoutja hetek óta elavult)."""
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from fleet import agent_probe, authsig, probe
from fleet.remote import Target
from test_auth_signal import FAIL1, FAIL2, OK, OVERLOAD, RECOVERED, USER

SYN_OK = '{"type":"assistant","timestamp":"2026-10-01T21:00:00Z","message":{"model":"<synthetic>","content":[]}}'


def git(*a, cwd=None):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=main", *a],
                   cwd=cwd, check=True, capture_output=True)


def repo_behind(root: Path, name: str) -> Path:
    """Egy klón, ami az originje mögött van 1 committal (a fetch után látszik)."""
    origin, ahead, live = root / f"{name}.git", root / f"{name}-dev", root / name
    git("init", "--bare", str(origin))
    git("clone", str(origin), str(ahead))
    (ahead / "bin").mkdir()
    (ahead / "bin" / "fleet").write_text("#!/bin/sh\necho 'fleet 9.9.9'\n")
    (ahead / "bin" / "fleet").chmod(0o755)
    git("add", "-A", cwd=ahead); git("commit", "-m", "1", cwd=ahead); git("push", "origin", "HEAD", cwd=ahead)
    git("clone", str(origin), str(live))
    (ahead / "x").write_text("2"); git("add", "-A", cwd=ahead); git("commit", "-m", "2", cwd=ahead)
    git("push", "origin", "HEAD", cwd=ahead)
    return live


class TestParityWithAuthsig(unittest.TestCase):
    """A szonda önálló (a régi boxon nincs új fleet-kód), de ugyanazt kell mondania, mint az authsig."""
    CASES = [[OK], [OK, FAIL1, FAIL2], [OK, FAIL1, FAIL2, RECOVERED], [USER, OVERLOAD], [FAIL1, OK, FAIL1, FAIL2]]

    def test_same_verdict_and_count(self):
        for lines in self.CASES:
            state, _, data = authsig.auth_verdict(authsig.auth_events(lines))
            f = agent_probe.assistant_facts(lines)
            self.assertEqual(f["auth"] or "unknown", state, lines)
            if state == "expired":
                self.assertEqual(f["failed"], data["failed"])

    def test_model_is_last_real_reply_not_synthetic(self):
        f = agent_probe.assistant_facts([OK, FAIL1, RECOVERED, SYN_OK])
        self.assertEqual((f["model"], f["model_at"]), ("claude-opus-5", "2026-10-01T20:17:00Z"))


class TestProbeOnBox(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.home = Path(self._t.name) / "home"
        (self.home / ".config" / "agx").mkdir(parents=True)
        (self.home / ".config" / "agx" / "session.id").write_text("sid-1\n")
        tdir = self.home / ".claude-acc" / "projects" / "-w"
        tdir.mkdir(parents=True)
        (tdir / "sid-1.jsonl").write_text("\n".join([OK, FAIL1, FAIL2]) + "\n")
        fl = repo_behind(Path(self._t.name), "fleet-leader")
        (self.home / ".local" / "bin").mkdir(parents=True)
        (self.home / ".local" / "bin" / "fleet").symlink_to(fl / "bin" / "fleet")
        reg = repo_behind(Path(self._t.name), "fleet-ops")
        (reg / "fleet").mkdir()
        (self.home / ".config" / "fleet").mkdir(parents=True)
        (self.home / ".config" / "fleet" / "registry").write_text(str(reg / "fleet") + "\n")
        self.saved = {k: os.environ.get(k) for k in ("HOME", "FLEET_REGISTRY", "FLEET_SSH")}
        os.environ.pop("FLEET_REGISTRY", None)

    def tearDown(self):
        for k, v in self.saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        self._t.cleanup()

    def test_direct(self):
        p = agent_probe.probe({"agent": "agx", "account": "acc", "fetch": True}, home=self.home)
        self.assertEqual((p["auth"], p["failed"]), ("expired", 2))
        self.assertEqual(p["model"], "claude-opus-5")
        self.assertEqual((p["fleet"]["behind"], p["fleet"]["fetched"], p["fleet"]["version"]), (1, True, "fleet 9.9.9"))
        self.assertEqual(p["registry"]["git"]["behind"], 1)
        self.assertTrue(p["registry"]["realpath"].endswith("fleet-ops/fleet"))
        probs = probe.problems(p)
        self.assertTrue(any("login lejárt" in x for x in probs))
        self.assertEqual(sum("1 committal az origin mögött" in x for x in probs), 2)

    def test_without_fetch_behind_is_stale_and_says_so(self):
        p = agent_probe.probe({"agent": "agx", "account": "acc", "fetch": False}, home=self.home)
        self.assertEqual(p["fleet"]["behind"], 0)
        self.assertTrue(any("fetch nem futott" in x for x in probe.problems(p)))

    def test_missing_session_is_error_not_ok(self):
        p = agent_probe.probe({"agent": "nincs", "account": "acc"}, home=self.home)
        self.assertIsNone(p["auth"])
        self.assertTrue(p["errors"])
        self.assertTrue(any("auth ismeretlen" in x for x in probe.problems(p)))

    def test_over_fake_ssh_via_stdin(self):
        """A teljes út: a szonda szövege a távoli python3 stdin-jén megy, a box HOME-jával fut."""
        fake = Path(self._t.name) / "fake-ssh"
        log = Path(self._t.name) / "ssh-calls"
        fake.write_text('#!/bin/sh\nwhile [ "$1" != "--" ]; do shift; done; shift\n'
                        f'echo "$1" >> {log}; shift\nexec sh -c "$1"\n')
        fake.chmod(0o755)
        os.environ.update(FLEET_SSH=str(fake), HOME=str(self.home))
        resolver = lambda name, ssh=None: ({"agent": "agx", "claude_account": "acc", "model": "opus"},  # noqa: E731
                                           Target("agent@box", "box"))
        p = probe.run_probe("agx", resolver=resolver)
        self.assertTrue(p["reachable"])
        self.assertEqual(log.read_text().strip(), "agent@box")
        self.assertEqual((p["auth"], p["expected_model"]), ("expired", "opus"))
        self.assertIn("login lejárt", probe.format_probe(p))

    def test_unreachable_is_a_problem(self):
        p = probe.run_probe("agx", ssh="x", resolver=lambda n, ssh=None: (None, _Broken()))
        self.assertFalse(p["reachable"])
        self.assertTrue(p["problems"])
        self.assertIn("ELÉRHETETLEN", probe.format_probe(p))


class _Broken:
    label = "halott-box"

    def sh(self, *_a, **_k):
        return subprocess.CompletedProcess([], 255, "", "ssh: connect to host: Connection refused")


if __name__ == "__main__":
    unittest.main()
