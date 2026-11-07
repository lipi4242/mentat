"""Guard 0.3.1 vs the documented install / refresh commands, run while a role is active.

BEKOTES step 0 (re-run to update the tools, `cp "$REF/…"` or curl), its 6–8 block, the daily
refresh (stage 17) and the status / model skills write or run `.mentat/bin/` from Bash. Those writes must stay allowed for every
role; the role pins (`.mentat/szerep/`) and the role files stay protected.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import re
import unittest

from test_guard import HERE, GuardBase

REL = HERE.parent.parent


def blocks(path, heading):
    text = path.read_text(encoding="utf-8")
    part = text[text.index(heading):]
    return re.search(r"```bash\n(.*?)```", part, re.S).group(1)


def skill_lines(name):
    text = (REL / "skills" / name / "SKILL.hu.md").read_text(encoding="utf-8")
    return [ln for ln in text.splitlines() if ".mentat/bin" in ln and ("curl" in ln or "mkdir" in ln)]


class GuardInstallPaths(GuardBase):
    def cmds(self):
        out = []
        for lang in ("hu", "en"):
            doc = HERE / ("BEKOTES.%s.md" % lang)
            out += ["REF=/src/reference\n" + blocks(doc, "## 0."), blocks(doc, "## 6")]
        refresh = ["python3 -m anytime_bekotes.frissit --begin",  # engine bekotes_frissites prompt
                   "git -C munka/zoldag-web show abc123:README.md",
                   "python3 -m anytime_bekotes.frissit --advance r1",
                   "python3 -m anytime_bekotes.frissit --baseline"]
        return out + refresh + skill_lines("status") + skill_lines("model")

    def test_documented_install_and_refresh_allowed_under_every_role(self):
        for role in ("asszisztens", "fejleszto"):
            for cmd in self.cmds():
                self.assertEqual(self.decide("Bash", {"command": cmd}, role, role), "allow",
                                 "%s: %s" % (role, cmd[:120]))

    def test_role_pins_and_files_stay_protected(self):
        for cmd in ("echo fejleszto > .mentat/szerep/s1", "sed -i s/a/b/ .mentat/local.json",
                    "cp /tmp/x agy/szerepek/asszisztens.md", "cp /tmp/x .mentat/bin/../szerep/s1"):
            self.assertEqual(self.decide("Bash", {"command": cmd}, "asszisztens", "p"), "deny", cmd)

    def test_guard_code_cannot_be_overwritten_from_bash(self):
        # the hook runs .mentat/bin/bekotes/szerep_guard.py and imports from bekotes/ and manifest/
        for role in ("fejleszto", "asszisztens"):
            for cmd in ("cp /tmp/x .mentat/bin/bekotes/szerep_guard.py",
                        "sed -i s/deny/allow/ .mentat/bin/bekotes/szerep_rules.py",
                        "echo x > .mentat/bin/bekotes/json.py", "rm .mentat/bin/bekotes/szerep_bash.py",
                        "curl -fsSL -o .mentat/bin/bekotes/szerep_bash.py https://example.com/x",
                        "wget -O .mentat/bin/manifest/mentat_roles.py https://example.com/x",
                        "mv .mentat/bin/bekotes /tmp/", "cd .mentat/bin/bekotes && cp /tmp/x szerep_pin.py"):
                self.assertEqual(self.decide("Bash", {"command": cmd}, role, "g" + role), "deny",
                                 "%s: %s" % (role, cmd))


if __name__ == "__main__":
    unittest.main()
