import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from fleet import registry_set as R


class RegistrySetTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "agents.json").write_text(json.dumps([{"agent": "szervezo"}, {"agent": "vilma"}]))

    def test_dormant_nyugtaval(self):
        out = R.apply("szervezo", "status=dormant", "Igen, mehet a dormant.", self.d)
        self.assertIn("dormant", out)
        self.assertEqual(json.loads((self.d / "agents.json").read_text())[0]["status"], "dormant")
        self.assertIn("mehet", (self.d / "registry-nyugtak.jsonl").read_text())

    def test_git_commit_a_tulajdonos_igenjevel(self):
        subprocess.run(["git", "init", "-q", str(self.d)], check=True)
        g = ["git", "-C", str(self.d), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run(g + ["add", "agents.json"], check=True)
        subprocess.run(g + ["commit", "-qm", "init"], check=True)
        R.apply("vilma", "status=dormant", "👍", self.d)
        log = subprocess.run(["git", "-C", str(self.d), "log", "-1", "--format=%B"], capture_output=True, text=True).stdout
        self.assertIn("A tulajdonos igene: 👍", log)

    def test_tiltott_kulcs_es_ertek(self):
        for asg in ("unit=x.service", "status=torolt", "tick_period_s=10", "tick_period_s=1700", "status"):
            with self.assertRaises(ValueError):
                R.apply("vilma", asg, "igen", self.d)

    def test_agensnev_ellenorzott(self):
        """CISO Q4: az ágensnév a timer fájlnevébe kerül; út-elem és furcsa karakter nem mehet át."""
        bad_names = ("../vilma", "Vilma", "-x", "a b", "vilma/x")
        (self.d / "agents.json").write_text(json.dumps([{"agent": n} for n in bad_names]))
        for bad in bad_names:
            with self.assertRaises(ValueError, msg=bad):
                R.apply(bad, "status=dormant", "igen", self.d)

    def test_owner_text_nelkul(self):
        with self.assertRaises(ValueError):
            R.apply("vilma", "status=dormant", " ", self.d)

    def test_ismeretlen_agens(self):
        with self.assertRaises(ValueError):
            R.apply("nincs", "status=dormant", "igen", self.d)


if __name__ == "__main__":
    unittest.main()
