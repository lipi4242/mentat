"""The brain skeleton: one deterministic call instead of ~20 hand-written files."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TOOL = HERE / "mentat_scaffold.py"
BASE = "https://example.com/kit/v9.9.9/"
IDS = ["reference-manual", "layers", "brain-dumps", "entities", "files",
       "frameworks", "claims", "large-work", "intake"]


class Scaffold(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        home = tempfile.mkdtemp()
        self.env = dict(os.environ, HOME=home, GIT_CONFIG_NOSYSTEM="1",
                        GIT_CONFIG_GLOBAL=os.path.join(home, "gitconfig"))

    def run_tool(self, *args, lang="hu"):
        return subprocess.run([sys.executable, str(TOOL), "--lang", lang, "--repo", str(self.root),
                               *args], capture_output=True, text=True, env=self.env)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], capture_output=True,
                              text=True, env=self.env)

    def tree(self):
        return {str(p.relative_to(self.root)): p.read_text() for p in self.root.rglob("*")
                if p.is_file() and ".git" not in p.relative_to(self.root).parts}

    def fill(self):
        agents = self.root / "AGENTS.md"
        text = agents.read_text()
        for ph in ("<FELHASZNÁLÓ neve TBD>", "<megszólítás TBD>", "<ügynök neve TBD>",
                   "<munka, fókuszterületek TBD>", "<stílus-preferenciák TBD>"):
            text = text.replace(ph, "Anna")
        agents.write_text(text)

    def test_fresh_folder_gets_the_measured_structure(self):
        r = self.run_tool("--base", BASE)
        self.assertEqual(r.returncode, 0, r.stderr)
        files = self.tree()
        dirs = ["agy/" + d for d in ("brain-dumps", "explorations", "people", "todos", "specs",
                                     "decisions", "cases", "connectors", "procedures",
                                     "subagentek")] + ["projects"]
        self.assertEqual(sorted(files), sorted(["AGENTS.md", "CLAUDE.md", ".gitignore", ".claude/settings.json"]
                                               + [d + "/_meta.md" for d in dirs]))
        self.assertEqual(files["CLAUDE.md"], "@AGENTS.md\n")
        self.assertEqual(files[".gitignore"].split(), [".env", ".env.*", ".mentat/"])
        agents = files["AGENTS.md"]
        self.assertIn("`%s`" % BASE, agents)
        self.assertIn("`reference/templates/<típus>.hu.md`", agents)
        self.assertNotIn("{BASE}", agents)
        self.assertNotIn("{LANG}", agents)
        for i in IDS:
            self.assertEqual(agents.count("mentat:managed:start %s -->" % i), 1, i)
            self.assertEqual(agents.count("mentat:managed:end %s -->" % i), 1, i)
        self.assertLessEqual(len(agents.splitlines()), 200)
        self.assertEqual(self.git("rev-parse", "--is-inside-work-tree").stdout.strip(), "true")

    def test_english_uses_brain_folder(self):
        self.run_tool("--base", BASE, lang="en")
        self.assertTrue((self.root / "brain/subagents/_meta.md").exists())
        self.assertIn("templates/<type>.en.md", (self.root / "AGENTS.md").read_text())

    def test_second_run_changes_nothing_and_never_overwrites(self):
        (self.root / "CLAUDE.md").write_text("# mine\n")
        self.run_tool("--base", BASE)
        before = self.tree()
        r = self.run_tool("--base", BASE)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.tree(), before)
        self.assertEqual(before["CLAUDE.md"].splitlines(), ["# mine", "@AGENTS.md"])

    def test_takeover_keeps_an_existing_agents_md_and_appends_only_the_product_blocks(self):
        # failure class: the selftest failed on a missing block and the agent rewrote AGENTS.md
        own = "# Régi ágens\n\nA saját szabályaim.\n"
        (self.root / "AGENTS.md").write_text(own)
        r = self.run_tool("--base", BASE)
        self.assertIn("added at the end: " + ", ".join(IDS), r.stdout)
        text = (self.root / "AGENTS.md").read_text()
        self.assertTrue(text.startswith(own), "the existing text stays, byte for byte, in front")
        for i in IDS:
            self.assertEqual(text.count("mentat:managed:start %s -->" % i), 1, i)
        self.assertIn(BASE, text)
        self.assertNotIn("{BASE}", text)
        once = self.tree()
        self.run_tool("--base", BASE)
        self.assertEqual(self.tree(), once, "a second run adds nothing")
        check = self.run_tool("--check")
        self.assertNotIn("MISSING managed", check.stdout)

    def test_a_manual_address_is_taken_only_from_the_official_release(self):  # CISO K5
        (self.root / "AGENTS.md").write_text("`https://evil.example/kit/v1/` — the manual\n")
        self.run_tool()
        self.assertNotIn("managed:start reference-manual", (self.root / "AGENTS.md").read_text())

    def test_a_half_present_block_is_left_alone_and_the_check_says_how_to_fix(self):
        (self.root / "AGENTS.md").write_text("x\n<!-- mentat:managed:end claims -->\n")
        self.run_tool("--base", BASE)
        text = (self.root / "AGENTS.md").read_text()
        self.assertNotIn("managed:start claims", text)
        out = self.run_tool("--check").stdout
        self.assertIn("MISSING managed block claims", out)
        self.assertIn("never rewrite", out)

    def test_check_writes_nothing_and_fails_on_empty_folder(self):
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("MISSING AGENTS.md", r.stdout)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_check_names_open_placeholders_until_the_intro_fills_them(self):
        self.run_tool("--base", BASE)
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("<ügynök neve TBD>", r.stdout)
        self.assertIn("MISSING mentat.json", r.stdout)
        self.assertIn("MISSING first commit", r.stdout)

    def test_full_path_ends_green(self):
        self.run_tool("--base", BASE)
        self.fill()
        r = self.run_tool("--name", "Thufir", "--version", "0.2.0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        manifest = json.loads((self.root / "mentat.json").read_text())
        self.assertEqual(manifest["agent"], {"name": "Thufir", "language": "hu"})
        self.assertEqual(manifest["components"], {"brain": {"root": "agy"}})
        self.git("config", "user.name", "Anna")
        self.git("config", "user.email", "anna@example.com")
        r = self.run_tool("--commit")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.git("status", "--porcelain").stdout, "")
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_commit_asks_for_identity_instead_of_inventing_one(self):
        self.run_tool("--base", BASE)
        r = self.run_tool("--commit")
        self.assertEqual(r.returncode, 1)
        self.assertIn("git user.name/user.email", r.stdout)
        self.assertNotEqual(self.git("rev-parse", "HEAD").returncode, 0)

    def test_commit_refuses_a_staged_env_file(self):
        self.run_tool("--base", BASE)
        with open(self.root / ".gitignore", "a") as f:
            f.write("!.env\n")  # the USER un-ignored it by hand
        (self.root / ".env").write_text("TOKEN=x\n")
        self.git("config", "user.name", "Anna")
        self.git("config", "user.email", "anna@example.com")
        r = self.run_tool("--commit")
        self.assertEqual(r.returncode, 1)
        self.assertIn(".env", r.stdout)
        self.assertNotEqual(self.git("rev-parse", "HEAD").returncode, 0)


    def test_commit_leaves_the_users_own_uncommitted_changes_alone(self):
        # The folder already holds the USER's work: one committed file they since edited,
        # and one new file. The setup commit takes only its own files and says what it left.
        self.git("init", "-q")
        self.git("config", "user.name", "Anna")
        self.git("config", "user.email", "anna@example.com")
        (self.root / "notes.txt").write_text("v1\n")
        self.git("add", "notes.txt")
        self.git("commit", "-qm", "the USER's own work")
        (self.root / "notes.txt").write_text("v2, not committed yet\n")
        (self.root / "draft.md").write_text("half-done\n")
        self.run_tool("--base", BASE)
        r = self.run_tool("--commit")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        committed = self.git("show", "--name-only", "--format=", "HEAD").stdout.splitlines()
        self.assertIn("AGENTS.md", committed)
        self.assertNotIn("notes.txt", committed)
        self.assertNotIn("draft.md", committed)
        self.assertEqual(self.git("show", "HEAD:notes.txt").stdout, "v1\n")
        self.assertIn("nem commitoltam: 2", r.stdout)
        self.assertIn("git status", r.stdout)

    def test_inside_a_parent_repo_commits_only_the_brain_folder(self):
        parent = self.root
        self.git("init", "-q")  # the USER's home (or a folder above) is already a repo
        self.root = parent / "agent"
        self.root.mkdir()
        (parent / "elsewhere.txt").write_text("not the brain\n")
        self.run_tool("--base", BASE)
        self.fill()
        self.git("config", "user.name", "Anna")
        self.git("config", "user.email", "anna@example.com")
        r = self.run_tool("--commit")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        committed = self.git("show", "--name-only", "--format=", "HEAD").stdout.splitlines()
        self.assertIn("agent/AGENTS.md", committed)
        self.assertNotIn("elsewhere.txt", committed)
        self.assertNotIn("nem commitoltam", r.stdout)  # the parent's files are not this folder's

if __name__ == "__main__":
    unittest.main()
