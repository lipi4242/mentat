"""Guard: a fejlesztő a motor kimenetét (data/outbox, data/state) sem olvassa.

h1-16 (DeepSeek, 20261020-125108): a korlátozott forrásból lett ügy szövege a tickkel a
data/outbox/<nap>.md-be és a data/state/last-plan.json-ba került, és a fejlesztő olvashatta."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import unittest

from test_guard import GuardBase


class GuardMotorKimenet(GuardBase):
    def test_developer_cannot_read_engine_output(self):
        for path in ("data/outbox/2026-10-20.md", "data/state/last-plan.json"):
            p = str(self.root / path)
            self.assertEqual(self.decide("Read", {"file_path": p}, "fejleszto"), "deny", path)
            self.assertEqual(self.decide("Bash", {"command": f"cat {p}"}, "fejleszto"), "deny", path)

    def test_assistant_still_reads_it_and_developer_reads_code(self):
        p = str(self.root / "data/outbox/2026-10-20.md")
        self.assertEqual(self.decide("Read", {"file_path": p}, "asszisztens"), "allow")
        self.assertEqual(self.decide("Read", {"file_path": str(self.root / "src/data.py")}, "fejleszto"), "allow")


if __name__ == "__main__":
    unittest.main()
