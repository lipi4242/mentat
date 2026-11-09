"""Titok-kapu: a cd-követés nem nyithat rést a main-hez képest (CISO 0.6.0, B-01). A cd lehet
sikertelen, feltételes, alhéjas vagy háttérben futó: a relatív út a hook cwd-je ÉS minden cd-cél
ellen mérve tilt. A CISO regressziós korpuszának cd-szakasza, dummy HOME alatt.
Futtatás: python3 -I -m unittest discover -s security/eszkozok/identitas -q
"""
import os
import pathlib
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import titok_kapu as K  # noqa: E402
import titok_minta as M  # noqa: E402

DENY = """cd /nonexistent_dir_x; cat conf/settings.local
cd /nonexistent_dir_x 2>/dev/null; cat ../.claude/projects/*/s2.jsonl
cd /nonexistent_dir_x; cat ../.config/agentx/conn.dat
(cd /tmp); cat conf/settings.local
(cd /tmp) && cat conf/settings.local
cd /tmp | true; cat conf/settings.local
cd /tmp & cat conf/settings.local
true || cd /tmp; cat conf/settings.local
false && cd /tmp; cat conf/settings.local
bash -c 'cd /tmp'; cat conf/settings.local
cd /tmp; cd -; cat conf/settings.local
cd ~/.claude/projects && cat */s2.jsonl
cd @OTH && cat s2.jsonl
pushd /tmp; popd; cat conf/settings.local
pushd -n /tmp; cat conf/settings.local
cd -P /tmp; cat conf/settings.local
cd /tmp; cat < conf/settings.local
cd /nonexistent_dir_x; cat < conf/settings.local
cd /nonexistent_dir_x; cp conf/settings.local /tmp/o
cd /nonexistent_dir_x; grep -r . conf
cd /nonexistent_dir_x; tar cf - conf
cd /nonexistent_dir_x && cat conf/settings.local
{ cd /tmp; }; cat conf/settings.local
cd /tmp; exec 3< conf/settings.local; cat <&3
if false; then cd /tmp; fi; cat conf/settings.local
cd "$(mktemp -d)"; cat conf/settings.local
cd $NOPE; cat conf/settings.local
cd /tmp; cat @H/.claude/projects/../projects/*/s2.jsonl
cd @H/.claude/projects/; cat ./*/s2.jsonl
cd @OWN/memory && cat ../s1.jsonl
cd /tmp || true; cat conf/settings.local
[ -d x ] && cd /tmp; cat conf/settings.local
(cd /tmp); cd conf; cat settings.local
CDPATH=@H/repo; cd conf; cat settings.local""".splitlines()

ALLOW = """cat docs/x.md
cd docs && cat x.md
cd @OWN/memory && cat a.md
cd /tmp; cat docs/x.md
cat <<'E'
$(cat conf/settings.local)
E
cat <<"E"
`cat conf/settings.local`
E""".split("\n")


class CdRegresszio(unittest.TestCase):
    def setUp(self):
        keys = ("HOME", "CLAUDE_CONFIG_DIR", "CLAUDE_PROJECT_DIR", "FLEET_AGENT", "FLEET_REGISTRY")
        self.old = {k: os.environ.get(k) for k in keys}
        self.h = h = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, h, True)
        os.environ["HOME"] = h
        for k in keys[1:]:
            os.environ.pop(k, None)
        self.repo, other = h + "/repo", h + "/other"
        os.environ["CLAUDE_PROJECT_DIR"] = self.repo
        slug = lambda d: "".join(c if c.isalnum() else "-" for c in d)  # noqa: E731
        self.own, self.oth = h + "/.claude/projects/" + slug(self.repo), h + "/.claude/projects/" + slug(other)
        for d in (self.repo + "/.git", other + "/.git"):
            os.makedirs(d)
        for p in (self.own + "/memory/a.md", self.own + "/s1.jsonl", self.oth + "/memory/b.md", self.oth + "/s2.jsonl",
                  h + "/.config/agentx/conn.dat", self.repo + "/conf/settings.local", self.repo + "/docs/x.md"):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as f:
                f.write("x\n")
        self.lel = M.Leltar([{"path": h + "/.config/agentx/conn.dat"}, {"path": self.repo + "/conf/settings.local"}])

    def tearDown(self):
        for k, v in self.old.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def b(self, cmd):
        cmd = cmd.replace("@OWN", self.own).replace("@OTH", self.oth).replace("@H", self.h)
        return K.decide("Bash", {"command": cmd}, self.repo, self.lel)

    def test_bizonytalan_cd_utan_a_relativ_ut_tilt(self):
        for cmd in DENY:
            self.assertTrue(self.b(cmd), cmd)

    def test_cdpath_kornyezetbol(self):  # Codex 11-08
        os.environ["CDPATH"] = self.repo
        self.addCleanup(os.environ.pop, "CDPATH", None)
        cmd = "cd conf; cat settings.local"  # a hook cwd-je alatt nincs conf: csak a CDPATH viszi oda
        self.assertTrue(K.decide("Bash", {"command": cmd}, self.h + "/other", self.lel))

    def test_biztos_es_artalmatlan_esetek_szabadok(self):
        cmds, i = [], 0
        while i < len(ALLOW):  # a heredoc-esetek több sorosak
            if ALLOW[i].startswith("cat <<"):
                cmds.append("\n".join(ALLOW[i:i + 3]))
                i += 3
            else:
                cmds.append(ALLOW[i])
                i += 1
        for cmd in cmds:
            self.assertIsNone(self.b(cmd), cmd)


if __name__ == "__main__":
    unittest.main()
