"""mentat_accept.py --part: a single reminder is one part of the agreed set.

The engine sends one reminder per record besides the morning list; checked as the whole set,
every reminder would be red for the records it does not name. With --part a missing record
is not an error; a record that is not eligible, left-out data or a date outside the window
still is.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import unittest

from _contract_fixture import approved, brain, run, write

TOOL = "mentat_accept.py"
ONE = "name,email,date\nAnna,anna@example.com,2026-11-03\n"


class Part(unittest.TestCase):
    def setUp(self):
        self.root = brain()
        approved(self.root)

    def accept(self, text, *flags):
        return run(TOOL, self.root, *flags, "dinner", str(write(self.root, "one.csv", text)))

    def test_one_eligible_record_is_green_only_as_a_part(self):
        self.assertEqual(self.accept(ONE).returncode, 1)
        r = self.accept(ONE, "--part")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_part_is_still_red_for_what_must_not_go_out(self):
        for bad in (ONE.replace("Anna,anna@", "Péter,peter@"),          # declined: not eligible
                    ONE.replace("2026-11-03", "2026-11-12"),             # outside the window
                    ONE.replace("Anna,", "Anna (+36 1 333 3333),")):      # left-out data
            self.assertEqual(self.accept(bad, "--part").returncode, 1, bad)


if __name__ == "__main__":
    unittest.main()
