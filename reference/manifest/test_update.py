"""Writer rules: ownership, merge, lock, refusal on unknown schema or bad paths."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import multiprocessing
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mentat_manifest as mm  # noqa: E402


def _read(root, name):
    return json.loads((root / name).read_text())


def _bump(args):
    root, elem, n = args
    for i in range(n):
        mm.update(elem, "components", {"n%d" % i: i}, root)


class Update(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())

    def test_creates_files_with_schema(self):
        mm.update("brain", "components", {"root": "agy"}, self.root)
        mm.update("brain", "installed", "0.2.0", self.root)
        self.assertEqual(_read(self.root, "mentat.json"),
                         {"schema": 1, "components": {"brain": {"root": "agy"}}})
        self.assertEqual(_read(self.root, ".mentat/local.json"),
                         {"schema": 1, "installed": {"brain": "0.2.0"}})
        self.assertTrue((self.root / ".mentat" / "lock").exists())

    def test_merge_keeps_unknown_fields_of_own_and_other_sections(self):
        (self.root / "mentat.json").write_text(json.dumps(
            {"schema": 1, "x": 1, "components": {"brain": {"root": "agy", "later": True}, "engine": {"path": "e"}}}))
        mm.update("brain", "components", {"root": "brain"}, self.root)
        got = _read(self.root, "mentat.json")
        self.assertEqual(got["components"]["brain"], {"root": "brain", "later": True})
        self.assertEqual(got["components"]["engine"], {"path": "e"})
        self.assertEqual(got["x"], 1)

    def test_only_the_owner_writes_a_shared_section(self):
        with self.assertRaises(mm.ManifestError):
            mm.update("engine", "agent", {"name": "x"}, self.root)
        with self.assertRaises(mm.ManifestError):
            mm.update("brain", "fleet", {"host": "x"}, self.root)
        mm.update("brain", "agent", {"name": "x"}, self.root)
        mm.update("fleet", "fleet", {"host": "box"}, self.root)

    def test_brain_may_only_seed_cases(self):
        mm.update("brain", "cases", {"backend": "markdown"}, self.root, seed=True)
        with self.assertRaises(mm.ManifestError):  # admin not connected yet
            mm.update("cases", "cases", {"backend": "admin"}, self.root)
        mm.update("admin", "components", {}, self.root)
        mm.update("admin", "admin", {"url": "http://localhost:8787"}, self.root)
        mm.update("cases", "cases", {"backend": "admin"}, self.root)
        mm.update("brain", "cases", {"backend": "markdown"}, self.root, seed=True)
        self.assertEqual(_read(self.root, "mentat.json")["cases"], {"backend": "admin"})
        with self.assertRaises(mm.ManifestError):
            mm.update("brain", "cases", {"backend": "markdown"}, self.root)

    def test_refuses_unknown_schema(self):
        (self.root / "mentat.json").write_text(json.dumps({"schema": 2}))
        with self.assertRaises(mm.ManifestError):
            mm.update("brain", "components", {"root": "agy"}, self.root)
        self.assertEqual(_read(self.root, "mentat.json"), {"schema": 2})

    def test_refuses_to_write_a_path_outside_the_repo(self):
        with self.assertRaises(mm.ManifestError):
            mm.update("brain", "components", {"root": "../elsewhere"}, self.root)
        self.assertFalse((self.root / "mentat.json").exists())

    def test_concurrent_writers_lose_nothing(self):
        args = [(self.root, e, 15) for e in ("brain", "engine", "fleet", "admin")]
        with multiprocessing.get_context("spawn").Pool(4) as pool:
            pool.map(_bump, args)
        comps = _read(self.root, "mentat.json")["components"]
        for elem in ("brain", "engine", "fleet", "admin"):
            self.assertEqual(len(comps[elem]), 15, elem)


if __name__ == "__main__":
    unittest.main()
