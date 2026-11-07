import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import unittest

from test_leltar import LeltarFixture


class LeltarNoPath(LeltarFixture):
    """Súrlódás #21: path/export nélküli forrás ember-olvasható okkal blokkolt, nem nyers KeyError."""

    def test_live_without_path_has_readable_reason(self):
        cfg = json.loads(self.cfg.read_text())
        cfg["sources"].append({"name": "d1", "kind": "live"})
        cfg["sources"].append({"name": "lin2", "kind": "linear", "team": "X"})
        self.cfg.write_text(json.dumps(cfg))
        r = self.go()
        self.assertEqual(r.returncode, 0, r.stderr)
        src = {s["name"]: s for s in json.loads(self.out.read_text())["sources"]}
        for name, field in (("d1", "path"), ("lin2", "export")):
            self.assertEqual(src[name]["state"], "blokkolt")
            self.assertNotIn("KeyError", src[name]["reason"])
            self.assertIn(field, src[name]["reason"])


if __name__ == "__main__":
    unittest.main()
