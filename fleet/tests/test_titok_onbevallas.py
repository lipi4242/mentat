"""`fleet secrets approve --owner-msg`: a tulajdonos igenjét hordozó üzenet azonosítója (CISO #112, 7.).

Az `--owner-text` naplózott önbevallás, nem hitelesítés; az üzenet-azonosító nélküli jóváhagyást a
`fleet secrets audit` „önbevallás”-ként jelenti. A híd által aláírt jóváhagyás v2.
"""
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import json
import unittest

from fleet import titok_jovahagy as J
from test_titok_mozgat import Base

ITEM = "copy:SZ_TOKEN:szervezo:vilma:a fogadó küldi a levelet"


class OwnerMsg(Base):
    def test_approve_eltarolja_az_uzenet_azonositot(self):
        rc, out = self.run_cli("secrets", "approve", "--item", ITEM, "--owner-text", "igen", "--owner-msg", "4711",
                               "--id", "uzenettel")
        self.assertEqual(rc, 0, out)
        doc = json.loads((J.H.approvals_dir(self.home) / "uzenettel.json").read_text())
        self.assertEqual(doc["owner_msg"], "4711")

    def test_audit_onbevallasnak_jelzi_az_uzenet_nelkulit(self):
        self.run_cli("secrets", "approve", "--item", ITEM, "--owner-text", "igen", "--id", "csak-szoveg")
        self.run_cli("secrets", "approve", "--item", ITEM, "--owner-text", "igen", "--owner-msg", "9", "--id", "uzenet")
        rc, out = self.run_cli("secrets", "audit")
        line = next(ln for ln in out.splitlines() if ln.startswith("önbevallás"))
        self.assertIn("csak-szoveg", line)
        self.assertNotIn("uzenet", line.replace("csak-szoveg", ""))
        self.assertEqual(J.self_declared(self.home), ["csak-szoveg"])


if __name__ == "__main__":
    unittest.main()
