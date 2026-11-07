"""Ágens-határ a CISO PR #112 javításai után (2026-10-29): hatókör-kapcsoló (Q2), hiba-viselkedés (Q5),
szűkebb téves tiltás (4.) és olcsón zárható kerülőutak (5.). Ideiglenes HOME, kitalált ágensek.
Futtatás: python3 -I -m unittest discover -s security/eszkozok/identitas -q
"""
import json
import os
import pathlib
import subprocess
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hatar_jel as J  # noqa: E402
import titok_kapu as K  # noqa: E402
from test_agens_hatar import Base  # noqa: E402


class Hook(Base):
    def setUp(self):
        super().setUp()
        self.addCleanup(os.environ.pop, "CLAUDE_PROJECT_DIR", None)
        os.environ.pop("CLAUDE_PROJECT_DIR", None)

    def marker(self, since=None, until=None):
        now = time.time()
        os.makedirs(os.path.join(self.h, ".mentat", "titkok"), exist_ok=True)
        pathlib.Path(J.path()).write_text(json.dumps({"since": since or now, "until": until or now + 3600,
                                                      "reason": "teszt", "set_by": ["plan-merge"]}))

    def hook(self, cmd, tool="Bash", cwd=None):
        inp = {"command": cmd} if tool == "Bash" else {"file_path": cmd}
        out = K.hook({"tool_name": tool, "tool_input": inp, "cwd": cwd or self.ops})
        return out["hookSpecificOutput"]["permissionDecisionReason"] if out else None


class Hatokor(Hook):
    """Q2: Rilí minden tickben `git reset --hard` + commit a kezelt repók fő ágán — jelző nélkül szabad."""
    MERGE_ONLY = ("git -C {v} fetch -q && git -C {v} reset --hard origin/main", "git -C {v} commit -qm x",
                  "tmux send-keys -t vilma Enter", "cd {v} && ./bin/meeting email-teszt m@p.example")

    def test_jelzo_nelkul_szabad(self):
        for c in self.MERGE_ONLY:
            self.assertIsNone(self.hook(c.format(v=self.vilma)), c)

    def test_jelzovel_tilt(self):
        self.marker()
        for c in self.MERGE_ONLY:
            self.assertTrue(self.hook(c.format(v=self.vilma)), c)

    def test_lejart_vagy_7_napnal_hosszabb_jelzo_nem_el(self):
        now = time.time()
        self.marker(since=now - 7200, until=now - 60)
        self.assertFalse(J.aktiv())
        self.marker(since=now, until=now + 8 * 86400)
        self.assertFalse(J.aktiv())
        self.marker()
        self.assertTrue(J.aktiv())

    def test_mindig_tilos(self):
        unit = self.h + "/.config/systemd/user/vilma.timer"
        self.assertTrue(self.hook(unit, "Write"))
        self.assertTrue(self.hook(self.vilma + "/AGENTS.md", "Edit"))
        os.makedirs(self.h + "/.config/fleet")
        reg = os.path.join(self.h, "reg")
        os.makedirs(reg)
        pathlib.Path(self.h, ".config/fleet/registry").write_text(reg)
        self.assertTrue(self.hook(reg + "/agents.json", "Write"))
        self.assertTrue(self.hook("sed -i s/active/dormant/ %s/agents.json" % reg))


class Hiba(Hook):
    """Q5: az ágens-határ hibája ne zárjon ki mindenkit; a titok-ügy továbbra is fail-closed."""

    def test_import_hiba_atenged_es_naplo(self):
        with mock.patch.dict(sys.modules, {"agens_hatar": None}):
            self.assertIsNone(self.hook(self.vilma + "/AGENTS.md", "Edit"))
        log = pathlib.Path(self.h, ".mentat/titkok/hatar-hibak.log").read_text()
        self.assertIn("atengedve: Edit", log)

    def test_titok_tovabbra_is_tilt(self):
        pathlib.Path(self.vilma, ".env").write_text("T=HAMIS\n")
        with mock.patch.dict(sys.modules, {"agens_hatar": None}):
            self.assertIn("Titok-kapu", self.hook("cat " + self.vilma + "/.env"))


class TevesTiltas(Hook):
    def setUp(self):
        super().setUp()
        self.marker()

    def test_git_config_olvasas(self):
        for c in ("git -C {v} config --get remote.origin.url", "git -C {v} config -l", "git -C {v} config user.email"):
            self.assertIsNone(self.hook(c.format(v=self.vilma)), c)
        self.assertTrue(self.hook("git -C %s config user.email a@b" % self.vilma))

    def test_ssh_tmux_a_tavoli_gepen(self):
        self.assertIsNone(self.hook('ssh thufir "tmux send-keys -t rili Enter"'))

    def test_dry_run(self):
        self.assertIsNone(self.hook("%s/bin/notify-check --dry-run" % self.vilma))
        self.assertTrue(self.hook("%s/bin/notify-check" % self.vilma))

    def test_symlinkes_cwd_a_sajat_repo(self):
        """A hook cwd-je lehet symlinkes út (macOS: /var → /private/var): attól még a saját repó."""
        link = os.path.join(self.h, "link-ops")
        os.symlink(self.vilma, link)
        for c in ("tmux capture-pane -p -t sender", "python3 send_mail.py"):
            self.assertIsNone(self.hook(c, cwd=link), c)

    def test_fixtura_agents_json(self):
        self.assertIsNone(self.hook(self.ops + "/tests/fixtures/agents.json", "Write"))


class Kerulout(Hook):
    def test_cd_utan_relativ(self):
        self.assertTrue(self.hook("cd %s && echo x >> AGENTS.md" % self.vilma))

    def test_ertelmezo_kodja_es_valtozo(self):
        self.assertTrue(self.hook("python3 -c \"open('%s/AGENTS.md','a').write('x')\"" % self.vilma))
        self.assertTrue(self.hook("F=%s/CLAUDE.md; echo x > $F" % self.vilma))
        self.assertTrue(self.hook("python3 - <<'PY'\nopen('%s/.config/systemd/user/a.timer','w')\nPY" % self.h))

    def test_masolas_forraskent_szabad(self):
        self.assertIsNone(self.hook("cp %s/AGENTS.md /tmp/x.md" % self.vilma))

    def test_cd_utani_git_a_projekt_konyvtarbol(self):
        """A session `cd`-vel a fogadóba lép: a saját könyvtára a CLAUDE_PROJECT_DIR marad."""
        self.marker()
        os.environ["CLAUDE_PROJECT_DIR"] = self.ops
        self.assertTrue(self.hook("git merge feat", cwd=self.vilma))
        subprocess.run(["git", "-C", self.vilma, "checkout", "-q", "-b", "ag"], check=True)
        self.assertIsNone(self.hook("git commit -qm x", cwd=self.vilma))


if __name__ == "__main__":
    unittest.main()
