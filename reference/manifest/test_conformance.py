"""Runs every conformance/*.json fixture through the reference reader.

Run: python3 -m unittest discover -s release/reference/manifest
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mentat_manifest as mm  # noqa: E402

FIXTURES = sorted((HERE / "conformance").glob("*.json"))


def _write_repo(case):
    root = pathlib.Path(tempfile.mkdtemp())
    if case.get("manifest_raw") is not None:
        (root / "mentat.json").write_text(case["manifest_raw"])
    elif case["manifest"] is not None:
        (root / "mentat.json").write_text(json.dumps(case["manifest"]))
    if case["local"] is not None:
        (root / ".mentat").mkdir()
        (root / ".mentat" / "local.json").write_text(json.dumps(case["local"]))
    return root


class Conformance(unittest.TestCase):
    def test_there_are_fixtures(self):
        self.assertGreaterEqual(len(FIXTURES), 16)

    def test_fixtures(self):
        for path in FIXTURES:
            case = json.loads(path.read_text())
            with self.subTest(fixture=path.name):
                got = mm.evaluate_root(_write_repo(case))
                self.assertEqual(got, case["expect"], case["description"])

    def test_present_matches_fixture(self):
        for path in FIXTURES:
            case = json.loads(path.read_text())
            root = _write_repo(case)
            for elem, want in case["expect"]["present"].items():
                with self.subTest(fixture=path.name, elem=elem):
                    self.assertEqual(mm.present(elem, root), want)


if __name__ == "__main__":
    unittest.main()
