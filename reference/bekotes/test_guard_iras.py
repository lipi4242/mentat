"""The gates' own files: only a real WRITE at the resolved path is denied (szerep_kapu_iras), the
way the fleet's F-41 gate decides (its vedett.py).

The class of the Mac gate's bug (2026-10-24): a rule on the raw text denied every command that
named the path, so the brain's own tools could not run. Positive controls here: running and
reading the tools, a commit message, heredoc prose, a command for another machine stay open.
Plus: the step-back when a verified user-level F-41 gate runs, and ~/.ssh/config read for hosts only.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import unittest
from pathlib import Path

from test_guard_kint import KintBase

R = ".mentat/state/capability-receipts"
J = ".mentat/identitas.json"
ADDR = "teszt.elek@example.com"
OPENALEX = "https://api.openalex.org/works?mailto=" + ADDR
FREE = (
    'python3 -I .mentat/bin/mentat_brain.py where --find "tedd ki a netre"',
    "python3 .mentat/bin/mentat_brain.py where --decide %s/x.json use --candidate web.publish" % R,
    "python3 .mentat/bin/bekotes/szerep_id_javaslat.py",
    "cat %s; ls %s" % (J, R),
    'git commit -qm "fix: %s, %s és ~/.mentat/elsofel.txt"' % (R, J),
    "cat > jegyzet.md <<'EOF'\nA kapu a %s fájlt védi: echo x > %s\nEOF" % (J, J),
    "ssh doboz 'echo x > %s'" % J,
    "python3 -c \"print(open('%s').read())\"" % J,  # code that names it but only reads
)
DENIED = (
    "echo x > %s" % J,
    "python3 -c \"open('%s', 'w')\"" % J,
    "python3 - <<'PY'\nopen('%s/k.json', 'w').write('{}')\nPY" % R,
    "rm -rf .mentat",
    "echo '{}' > %s/k.json" % R,
    "bash <<'SH'\necho x > %s\nSH" % J,  # a heredoc fed to a shell is commands
    "scp doboz:x %s" % J,
)


class OnlyRealWrites(KintBase):
    roles = False

    def test_running_reading_and_mentioning_stay_open(self):
        for cmd in FREE:
            self.assertEqual(self.bash(cmd), "allow", cmd)
        self.assertEqual(self.d("Read", {"file_path": str(self.root / J)}), "allow")

    def test_real_writes_are_denied(self):
        for cmd in DENIED:
            self.assertEqual(self.bash(cmd), "deny", cmd)


class UserGateStepsBack(KintBase):
    roles = False

    def setUp(self):
        super().setUp()
        (self.home / ".mentat").mkdir()
        (self.home / ".mentat" / "identitas.txt").write_text(ADDR + "\n")
        self.kapu = self.home / ".mentat" / "bin" / "identitas-kapu" / "current" / "kapu.py"

    def settings(self, base, block=True, exists=True):
        if exists:
            self.kapu.parent.mkdir(parents=True, exist_ok=True)
            self.kapu.write_text("#")
        hook = {"type": "command", "command": "/usr/bin/python3 -I %s --hook" % self.kapu}
        if block:
            hook["onFailure"] = "block"
        base.mkdir(parents=True, exist_ok=True)
        (base / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [hook]}]}}))

    def fetch(self):
        return self.d("WebFetch", {"url": OPENALEX, "prompt": "x"})

    def test_a_verified_user_gate_outside_the_repo_takes_over(self):
        self.assertEqual(self.fetch(), "ask")
        self.settings(self.home / ".claude")
        self.assertEqual(self.fetch(), "allow")  # the user-level gate asks instead

    def test_same_rule_as_the_fleets_tarolo(self):  # matcher may be absent; the path is absolute
        import szerep_kapu_id
        self.settings(self.home / ".claude")
        s = self.home / ".claude" / "settings.json"
        doc = json.loads(s.read_text())
        del doc["hooks"]["PreToolUse"][0]["matcher"]
        s.write_text(json.dumps(doc))
        self.assertTrue(szerep_kapu_id.user_gate_active(self.root))
        h = doc["hooks"]["PreToolUse"][0]["hooks"][0]
        h["command"] = "cd %s && python3 identitas-kapu/current/kapu.py --hook" % self.home
        s.write_text(json.dumps(doc))
        self.assertFalse(szerep_kapu_id.user_gate_active(self.root))

    def test_unverified_or_in_repo_settings_do_not_count(self):
        self.settings(self.home / ".claude", block=False)
        self.assertEqual(self.fetch(), "ask")
        self.settings(self.home / ".claude", exists=False)
        self.kapu.unlink()
        self.assertEqual(self.fetch(), "ask")
        (self.home / ".claude" / "settings.json").unlink()
        self.settings(self.root / ".claude")  # inside the repo: the agent can write it
        self.assertEqual(self.fetch(), "ask")
        import szerep_kapu_id
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.root / ".claude")
        try:
            self.assertFalse(szerep_kapu_id.user_gate_active(self.root))
        finally:
            del os.environ["CLAUDE_CONFIG_DIR"]


class SshConfigHostsOnly(unittest.TestCase):
    def test_only_host_names_and_addresses_are_taken(self):
        import tempfile
        import szerep_id_javaslat as jav
        cfg = Path(tempfile.mkdtemp()) / "config"
        cfg.write_text("Host doboz tartalek\n  HostName box.example.net\n  User titkos-felhasznalo\n"
                       "  IdentityFile ~/.ssh/kulcs-fajl\n  Port 2222\nHost *\n  ForwardAgent no\n")
        got = jav._ssh_hosts(str(cfg))
        self.assertEqual(got, ["doboz", "tartalek", "box.example.net"])
        for leaked in ("titkos-felhasznalo", "kulcs-fajl", "2222", "*"):
            self.assertNotIn(leaked, " ".join(got))


if __name__ == "__main__":
    unittest.main()
