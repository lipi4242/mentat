"""Titok-kapu: a SAJÁT projekt auto-memóriája (~/.claude*/projects/<saját>/memory/*.md) bármely
eszközzel írható/olvasható; minden más a projects/ alatt (átirat, más projekt memóriája) tiltva (11-08).
Kitalált projektek, hamis tartalom, ideiglenes HOME.
Futtatás: python3 -I -m unittest discover -s security/eszkozok/identitas -q
"""
import os
import pathlib
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import titok_kapu as K  # noqa: E402
import titok_minta as M  # noqa: E402

JEGYZET = """# Ütemezés
- a `*` glob és a `cat *` minta csak szöveg; $(date) és `ls ~/.claude/projects/*` sem fut
* felsorolás csillaggal
"""


class SajatMemoria(unittest.TestCase):
    def setUp(self):
        self.old = {k: os.environ.get(k) for k in ("HOME", "CLAUDE_CONFIG_DIR", "CLAUDE_PROJECT_DIR",
                                                   "FLEET_AGENT", "FLEET_REGISTRY")}
        self.home = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home, True)
        os.environ["HOME"] = self.home
        for k in ("CLAUDE_CONFIG_DIR", "CLAUDE_PROJECT_DIR", "FLEET_AGENT", "FLEET_REGISTRY"):
            os.environ.pop(k, None)
        self.cwd = os.path.join(self.home, "repo")
        os.makedirs(os.path.join(self.cwd, ".git"))
        os.makedirs(os.path.join(self.cwd, "src"))
        slug = re.sub(r"[^A-Za-z0-9]", "-", self.cwd)  # a Claude Code szabálya (a `_` és a `.` is „-")
        self.proj = os.path.join(self.home, ".claude", "projects", slug)
        self.mem = os.path.join(self.proj, "memory")
        self.mas = os.path.join(self.home, ".claude", "projects", slug + "-masik", "memory")
        for d in (self.mem, self.mas):
            os.makedirs(d)
        self.put(os.path.join(self.mem, "MEMORY.md"), "- [a](a.md)\n")
        self.put(os.path.join(self.mem, "a.md"), "jegyzet\n")
        self.put(os.path.join(self.mas, "MEMORY.md"), "más ágensé\n")
        self.sajat_atirat = self.put(os.path.join(self.proj, "s1.jsonl"), "{}\n")
        self.put(os.path.join(self.cwd, ".env"), "X=HAMIS\n")
        self.put(os.path.join(self.cwd, "src", "app.py"), "print(1)\n")
        st = os.stat(os.path.join(self.cwd, ".env"))
        self.lel = M.Leltar([{"path": os.path.join(self.cwd, ".env"), "dev": st.st_dev, "ino": st.st_ino}])

    def tearDown(self):
        for k, v in self.old.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def put(self, p, text):
        with open(p, "w") as f:
            f.write(text)
        return p

    def d(self, tool, inp, cwd=None):
        return K.decide(tool, inp, cwd or self.cwd, self.lel)

    def b(self, cmd, cwd=None):
        return self.d("Bash", {"command": cmd}, cwd)

    def test_bash_heredoc_hozzafuzes(self):
        for m in ("~/.claude/projects/%s/memory/uj.md" % os.path.basename(self.proj), self.mem + "/a.md"):
            for q in ("'E'", '"E"'):
                cmd = "cat >> %s <<%s\n%sE\n" % (m, q, JEGYZET)
                self.assertIsNone(self.b(cmd), cmd)

    def test_idezetlen_heredoc_backtickje_fut(self):
        cmd = "cat >> %s/a.md <<E\n`cat %s`\nE\n" % (self.mem, self.sajat_atirat)
        self.assertTrue(self.b(cmd))

    def test_idezett_heredocnak_latszo_szoveg_nem_rejt(self):
        t = self.sajat_atirat
        for cmd in ("echo \"<<'E'\"\ncat %s\nE\n" % t,
                    "printf %%s \"<<'HAMIS'\" <<VALODI\n$(cat %s >&2)\nVALODI\nHAMIS\n" % t,  # Codex 11-08
                    "cat <<<'a'\ncat %s\na\n" % t, "echo $((1<<2))\ncat %s\n2\n" % t,
                    "let x=1<<2\ncat %s\n2\n" % t, ": # <<EOF\ncat %s\nEOF\n" % t):  # Codex 11-08
            self.assertTrue(self.b(cmd), cmd)

    def test_eszkozok_sajat_memoriara(self):
        a = os.path.join(self.mem, "a.md")
        for tool, inp in (("Read", {"file_path": a}), ("Edit", {"file_path": a}),
                          ("Write", {"file_path": os.path.join(self.mem, "uj.md")}),
                          ("Read", {"file_path": os.path.join(self.mem, "MEMORY.md")}),
                          ("Grep", {"pattern": "x", "path": self.mem}),
                          ("Glob", {"pattern": "*.md", "path": self.mem})):
            self.assertIsNone(self.d(tool, inp), (tool, inp))
        for cmd in ("cat %s" % a, "ls %s" % self.mem, "ls -la %s/" % self.mem, "cat %s/*.md" % self.mem,
                    "grep -rn jegyzet %s" % self.mem):
            self.assertIsNone(self.b(cmd), cmd)

    def test_alkonyvtarbol_is_sajat(self):
        self.assertIsNone(self.d("Read", {"file_path": os.path.join(self.mem, "a.md")}, os.path.join(self.cwd, "src")))

    def test_mas_projekt_memoriaja_tiltva(self):
        m = os.path.join(self.mas, "MEMORY.md")
        for tool, inp in (("Read", {"file_path": m}), ("Write", {"file_path": m}), ("Edit", {"file_path": m}),
                          ("Grep", {"pattern": "x", "path": self.mas})):
            self.assertTrue(self.d(tool, inp), (tool, inp))
        for cmd in ("cat %s" % m, "cat >> %s <<'E'\nx\nE\n" % m, "grep -r x %s" % self.mas, "cat %s/*" % self.mas):
            self.assertTrue(self.b(cmd), cmd)

    def test_sajat_atirat_es_tobbi_tiltva(self):
        fh = os.path.join(self.home, ".claude", "file-history")
        os.makedirs(fh)
        for p in (self.sajat_atirat, os.path.join(self.proj, "s1", "tool-results", "x.txt"),
                  os.path.join(self.mem, "..", "s1.jsonl"), os.path.join(self.mem, "al", "x.md"),
                  os.path.join(self.mem, "x.jsonl")):
            self.assertTrue(self.d("Read", {"file_path": p}), p)
            self.assertTrue(self.b("cat %s" % p), p)
        self.assertTrue(self.b("cat %s/*" % self.proj))
        for cmd in ("cd %s && cat s1.jsonl" % self.proj, "cd %s; cd .. && cat s1.jsonl" % self.mem,
                    "pushd %s >/dev/null; cat ../s1.jsonl" % self.mem):  # relatív út a `cd` után
            self.assertTrue(self.b(cmd), cmd)
        self.assertIsNone(self.b("cd src && cat app.py"))
        for cmd in ("pushd %s && pushd %s && popd && cat MEMORY.md" % (self.mas, self.mem),  # Codex 11-08
                    "cd %s; cd %s; cd - && cat MEMORY.md" % (self.mas, self.mem), "cd $X && cat MEMORY.md",
                    "popd; cat x.md", "cd $X; cat < MEMORY.md"):
            self.assertTrue(self.b(cmd), cmd)
        self.assertIsNone(self.b("pushd src && popd && cat src/app.py"))
        self.assertTrue(self.b("cat %s/../*.jsonl" % self.mem))

    def test_feloldhatatlan_valtozo_az_atiratok_kozt(self):  # Codex 11-08: a `$` eddig átengedett
        for cmd in ("cat %s/${S}.jsonl" % self.proj, "cat %s/$(echo s1).jsonl" % self.proj,
                    "F=$(echo ../s1.jsonl); cat %s/$F" % self.mem, "cat ~/.claude/$X",
                    "cat ~/.claude${X}/projects/%s/s1.jsonl" % os.path.basename(self.proj), "cat ~/$A/x"):
            self.assertTrue(self.b(cmd), cmd)
        self.assertIsNone(self.b("cat src/$X"))

    def test_megjegyzes_es_osszevont_jel_nem_rejt(self):  # a shlex `#`-a és `);`-je eddig elnyelte
        t = self.sajat_atirat
        for cmd in ("echo hi # x\ncat %s" % t, "echo x#; cat %s" % t, "x=$(true); cat %s" % t,
                    "(echo a); cat %s" % t):
            self.assertTrue(self.b(cmd), cmd)
        self.assertIsNone(self.b("cat src/app.py # megjegyzés"))

    def _cd_masikba(self):
        masik = self.cwd + "-masik"  # a slugja a self.mas memóriáé
        os.makedirs(os.path.join(masik, ".git"))
        m = os.path.join(self.mas, "MEMORY.md")
        for tool, inp in (("Write", {"file_path": m}), ("Edit", {"file_path": m}), ("Read", {"file_path": m})):
            why = self.d(tool, inp, masik)
            self.assertTrue(why and "a `cd` nem teszi sajáttá" in why, (tool, why))
        for cmd in ("cat >> %s <<'E'\nx\nE\n" % m, "cd %s && cat MEMORY.md" % self.mas):
            self.assertTrue(self.b(cmd, masik), cmd)
        self.assertIsNone(self.d("Write", {"file_path": os.path.join(self.mem, "uj.md")}, masik))

    def test_cd_masik_projektbe_claude_project_dir(self):
        os.environ["CLAUDE_PROJECT_DIR"] = self.cwd
        self._cd_masikba()

    def test_cd_masik_projektbe_registry_workdir(self):
        reg = os.path.join(self.home, "reg")
        os.makedirs(reg)
        self.put(os.path.join(reg, "agents.json"),
                 '{"agents": [{"agent": "en", "workdir": "%h/repo"}, {"agent": "mas", "workdir": "%h/x"}]}')
        os.environ.update(FLEET_AGENT="en", FLEET_REGISTRY=reg)
        self._cd_masikba()

    def test_symlink_es_hardlink_a_memoriaban(self):
        ln = os.path.join(self.mem, "csapda.md")
        os.symlink(self.sajat_atirat, ln)
        hl = os.path.join(self.mem, "kemeny.md")
        os.link(self.sajat_atirat, hl)
        for p in (ln, hl):
            self.assertTrue(self.d("Read", {"file_path": p}), p)
            self.assertTrue(self.b("cat %s" % p), p)
        self.assertTrue(self.b("cat %s/*.md" % self.mem))
        os.remove(hl)
        self.assertTrue(self.b("grep -R x %s" % self.mem))
        self.assertTrue(self.d("Grep", {"pattern": "x", "path": self.mem}))

    def test_glob_csillag_nem_lep_at_perjelet(self):
        os.makedirs(os.path.join(self.cwd, "al"))
        os.rename(os.path.join(self.cwd, ".env"), os.path.join(self.cwd, "al", ".env"))
        self.lel = M.Leltar([{"path": os.path.join(self.cwd, "al", ".env")}])
        self.assertIsNone(self.b("head -1 *"))
        self.assertTrue(self.b("cat al/*"))
        self.assertTrue(self.b("cat **/.env"))


if __name__ == "__main__":
    unittest.main()
