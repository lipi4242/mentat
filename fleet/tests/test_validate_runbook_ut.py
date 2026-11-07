"""validate: a runbook útvonala a registry könyvtárához VAGY az azt tartalmazó repó gyökeréhez
relatív (L17: a boxon a registry `<repo>/fleet`, a runbook-mező `fleet/runbooks/<x>.md`, és a
validate mind a 13 ágensre „runbook hiányzik”-ot adott, így a `fleet setup` senkinek nem futott)."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fleet import validate as v  # noqa: E402


class RunbookUt(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo, True)
        ex = ROOT / "examples" / "registry"
        self.rdir = self.repo / "fleet"
        shutil.copytree(ex, self.rdir)
        doc = json.loads((self.rdir / "agents.json").read_text())
        self.agents = doc

    def set_runbook(self, value):
        doc = json.loads((self.rdir / "agents.json").read_text())
        items = doc["agents"] if isinstance(doc, dict) else doc
        for e in items:
            e["runbook"] = value.format(agent=e["agent"])
        (self.rdir / "agents.json").write_text(json.dumps(doc))

    def runbook_problems(self):
        return [p for p in v.validate(self.rdir)[1] if "runbook" in p]

    def test_registry_relative_path_still_works(self):
        self.set_runbook("runbooks/{agent}.md")
        self.assertEqual(self.runbook_problems(), [])

    def test_repo_root_relative_path_is_accepted(self):
        self.set_runbook("fleet/runbooks/{agent}.md")
        self.assertEqual(self.runbook_problems(), [])

    def test_a_truly_missing_runbook_is_still_reported(self):
        self.set_runbook("fleet/runbooks/nincs-{agent}.md")
        self.assertTrue(self.runbook_problems())


if __name__ == "__main__":
    unittest.main()
