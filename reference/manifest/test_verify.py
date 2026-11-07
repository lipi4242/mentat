"""The install checks what it downloaded before it runs any of it (CISO, 0.3.1 one-prompt install).

release.json lists a sha256 for every file the initialization's curl step puts in .mentat/bin/;
mentat_init.py checks them before it imports anything else, and stops with one sentence on a
mismatch. The list is generated from the curl step itself, and this test keeps it current.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TREE = HERE.parent.parent  # release/
sys.path.insert(0, str(HERE))
import mentat_verify as mv  # noqa: E402


def install(tree):
    """What the curl step of initialization.md does, from the local tree: .mentat/bin/ in a fresh folder."""
    root = pathlib.Path(tempfile.mkdtemp())
    for dest, src in mv.listing((tree / "reference" / "initialization.md").read_text(encoding="utf-8")):
        (root / ".mentat/bin" / dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(tree / src, root / ".mentat/bin" / dest)
    return root


class Listing(unittest.TestCase):
    def test_the_curl_step_is_read_as_dest_and_source(self):
        pairs = dict(mv.listing((TREE / "reference" / "initialization.md").read_text(encoding="utf-8")))
        self.assertEqual(pairs["mentat_init.py"], "reference/manifest/mentat_init.py")
        self.assertEqual(pairs["bekotes/szerep_guard.py"], "reference/bekotes/szerep_guard.py")
        self.assertEqual(pairs["bekotes/mentat_roles.py"], "reference/manifest/mentat_roles.py")
        self.assertEqual(pairs["capabilities/brain.json"], "reference/manifest/capabilities/brain.json")
        self.assertNotIn("release.json", pairs, "the list cannot hash the file it lives in")

    def test_release_json_lists_every_downloaded_file_current_once_frozen(self):
        meta = json.loads((TREE / "release.json").read_text(encoding="utf-8"))
        listed = meta.get("files")
        self.assertIsInstance(listed, dict)
        for dest, digest in listed.items():  # before the cut: the shape only (team-lead, 0.3.1)
            self.assertRegex(digest, r"^[0-9a-f]{64}$", dest)
            self.assertNotIn("..", dest)
        for name, digest in meta.get("files_known", {}).items():
            self.assertRegex(digest, r"^[0-9a-f]{64}$", name)
        if meta.get("files_frozen"):  # the release cut: the list must be current
            fix = "stale: rerun python3 release/reference/manifest/mentat_verify.py --write release --freeze"
            self.assertEqual(listed, mv.generate(TREE), fix)
            self.assertEqual(meta.get("files_known"), mv.known(TREE), fix)

    def test_freeze_writes_a_current_list_and_the_flag(self):
        tree = pathlib.Path(tempfile.mkdtemp())
        shutil.copytree(TREE / "reference", tree / "reference")
        (tree / "release.json").write_text(json.dumps({"version": "9.9.9", "files": {}}), encoding="utf-8")
        subprocess.run([sys.executable, str(HERE / "mentat_verify.py"), "--write", str(tree), "--freeze"],
                       check=True, capture_output=True)
        meta = json.loads((tree / "release.json").read_text(encoding="utf-8"))
        self.assertTrue(meta["files_frozen"])
        self.assertEqual(meta["files"], mv.generate(tree))


class Verify(unittest.TestCase):
    def setUp(self):
        self.root = install(TREE)
        meta = json.loads((TREE / "release.json").read_text(encoding="utf-8"))
        meta["files"] = mv.generate(TREE)  # what --freeze writes at the cut; the tree's list may be stale
        meta["files_known"] = mv.known(TREE)
        (self.root / ".mentat/bin/release.json").write_text(json.dumps(meta), encoding="utf-8")
        self.bin = self.root / ".mentat/bin"

    def test_an_untouched_download_passes(self):
        self.assertIsNone(mv.verify(self.bin))

    def test_a_changed_file_stops_the_install_before_it_runs(self):
        p = self.bin / "bekotes" / "szerep_guard.py"
        p.write_text(p.read_text(encoding="utf-8") + "\nprint('x')\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(self.bin / "mentat_init.py"), "--repo", str(self.root),
                            "--lang", "en", "--user", "A B", "--address", "tegez", "--agent", "T",
                            "--base", "https://example.com/v9/", "--no-prove"], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("MENTAT-INIT HIBA", r.stdout)
        self.assertIn("bekotes/szerep_guard.py", r.stdout)
        self.assertFalse((self.root / "AGENTS.md").exists(), "nothing runs after a mismatch")

    def test_no_list_in_an_installed_copy_is_a_stop_not_a_pass(self):
        meta = json.loads((self.bin / "release.json").read_text(encoding="utf-8"))
        meta.pop("files")
        (self.bin / "release.json").write_text(json.dumps(meta), encoding="utf-8")
        self.assertIn("release.json", mv.verify(self.bin))

    def test_a_missing_release_json_in_an_installed_copy_stops(self):
        (self.bin / "release.json").unlink()
        self.assertIsNotNone(mv.verify(self.bin))

    def run_init(self, *py_flags):
        return subprocess.run([sys.executable, *py_flags, str(self.bin / "mentat_init.py"), "--repo", str(self.root),
                               "--lang", "en", "--user", "A B", "--address", "tegez", "--agent", "T",
                               "--base", "https://example.com/v9/", "--no-prove"], capture_output=True, text=True)

    def test_a_missing_listed_file_stops_with_its_name(self):  # CISO: a partial download
        (self.bin / "bekotes" / "szerep_kapu.py").unlink()
        self.assertIn("bekotes/szerep_kapu.py", mv.verify(self.bin))

    def test_an_unlisted_py_stops_and_is_not_deleted(self):  # CISO: leftovers of an old install
        (self.bin / "bekotes" / "x.py").write_text("print('x')\n", encoding="utf-8")
        self.assertIn("bekotes/x.py", mv.verify(self.bin))
        self.assertTrue((self.bin / "bekotes" / "x.py").exists())

    def test_a_tool_a_later_step_fetches_passes(self):  # google.md downloads more into .mentat/bin/
        shutil.copyfile(HERE / "mentat_google.py", self.bin / "mentat_google.py")
        self.assertIsNone(mv.verify(self.bin))

    def test_a_planted_stdlib_name_never_runs_before_the_check(self):  # CISO: json.py shadowing
        marker = self.root / "planted-ran"
        (self.bin / "json.py").write_text("open(%r, 'w').write('x')\nfrom json import *\n" % str(marker),
                                          encoding="utf-8")
        r = self.run_init("-I")
        self.assertFalse(marker.exists(), "the planted json.py ran")
        self.assertIn("MENTAT-INIT HIBA", r.stdout)
        self.assertIn("json.py", r.stdout)
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_the_dev_tree_is_not_checked(self):
        self.assertIsNone(mv.verify(HERE))

    def tamper(self):
        p = self.bin / "mentat_brain.py"
        p.write_text(p.read_text(encoding="utf-8") + "\n# x\n", encoding="utf-8")

    def test_a_mismatch_is_never_waivable_and_the_second_one_ends_the_install(self):
        self.tamper()
        first = mv.verify(self.bin)
        self.assertIn("EGYSZER", first)  # one clean re-download, the same command
        self.assertNotIn("kérdezd meg a FELHASZNÁLÓT, mi legyen", first)
        final = mv.verify(self.bin)
        for must in ("megáll", "semmi nincs telepítve", "release.json", "saját megoldást", "jónak látod"):
            self.assertIn(must, final)
        self.assertNotEqual(first, final)

    def test_a_clean_download_resets_the_count(self):
        good = (self.bin / "mentat_brain.py").read_bytes()
        self.tamper()
        mv.verify(self.bin)
        (self.bin / "mentat_brain.py").write_bytes(good)
        self.assertIsNone(mv.verify(self.bin))
        self.tamper()
        self.assertIn("EGYSZER", mv.verify(self.bin))

    def test_a_failed_download_is_never_called_a_mismatch_and_never_ends_the_install(self):
        (self.bin / "mentat_brain.py").unlink()  # what a broken connection leaves behind
        for _ in range(3):
            msg = mv.verify(self.bin)
            self.assertIn("mentat_brain.py", msg)
            self.assertIn("később", msg)
            self.assertNotIn("nem egyezik", msg)
            self.assertNotIn("megáll", msg)

    def test_a_kept_copy_of_an_edited_list_ends_the_install_at_once(self):
        # an edited list next to its original: recomputed sums are not a pass, whatever they say
        (self.bin / "release.json.orig").write_text("{}", encoding="utf-8")
        msg = mv.verify(self.bin)
        self.assertIn("megáll", msg)
        self.assertIn("release.json.orig", msg)


class InstalledImports(unittest.TestCase):
    """Every local module an installed tool imports is installed with it (a tool that crashes at
    import is a check that never runs: mentat_done once imported a file the install never fetched)."""

    def test_every_local_import_of_an_installed_tool_is_installed(self):
        import ast
        pairs = mv.listing((TREE / "reference" / "initialization.md").read_text(encoding="utf-8"))
        dests = {d for d, _ in pairs}
        tools = {p.stem for d in mv.TOOL_DIRS for p in (TREE / d).glob("*.py")}
        missing = []
        for dest, src in pairs:
            if not src.endswith(".py"):
                continue
            tree = ast.parse((TREE / src).read_text(encoding="utf-8"))
            optional = {id(n) for t in ast.walk(tree) if isinstance(t, ast.Try) for n in ast.walk(t)}
            for n in ast.walk(tree):
                if id(n) in optional:
                    continue
                names = ([a.name for a in n.names] if isinstance(n, ast.Import) else
                         [n.module] if isinstance(n, ast.ImportFrom) and n.module else
                         [n.args[0].value] if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "__import__"
                         and n.args and isinstance(n.args[0], ast.Constant) else [])
                for m in {x.split(".")[0] for x in names} & tools:
                    folder = pathlib.PurePosixPath(dest).parent
                    near = {str(folder / (m + ".py")), m + ".py", "bekotes/%s.py" % m}
                    if not near & dests:
                        missing.append("%s imports %s" % (dest, m))
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
