"""mentat_google.py gmail / drive / sheets: mail to several outside people, sharing and writing a
sheet, each checked against the approved contract before the call, each read back after it.

Class of error (holdout, 0.3.0): a group mail where everyone saw everyone's address, a sheet
shared wider than agreed, and "it ran" taken for "the right people got it".
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import unittest

from _google_fixture import GOOD_CSV, PROPOSAL, run, setup, write

MAIL = ["gmail", "send", "--contract", "dinner", "--subject", "Dinner on Saturday"]
OUTSIDE = dict(PROPOSAL, audience={"from_records": "email", "allowed": ["@example.org"]})


class Gmail(unittest.TestCase):
    def tearDown(self):
        self.fake.close()

    def mail(self, *extra, proposal=None):
        self.fake, self.root = setup(proposal)
        self.fake.me = "me@example.net"  # the guests are outside the sender's domain
        body = write(self.root, "body.txt", "See you at seven.")
        return run(self.root, self.fake, *MAIL, "--body-file", str(body), *extra)

    def test_a_private_group_mail_goes_in_bcc(self):
        r = self.mail("--to", "anna@example.com,bob@example.com")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        msg = self.fake.messages["m1"]
        self.assertIsNone(msg["To"])
        self.assertIn("anna@example.com", msg["Bcc"])
        self.assertIn("READ BACK", r.stdout)
        self.assertIn("cannot see each other", r.stdout)

    def test_no_word_on_visibility_means_ask_first(self):
        r = self.mail("--to", "anna@example.com,bob@example.com", proposal=OUTSIDE)
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertIn("ASK", r.stdout)
        self.assertEqual(self.fake.writes(), [])

    def test_a_stranger_stops_the_mail(self):
        r = self.mail("--to", "anna@example.com", "--bcc", "stranger@example.net")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("stranger@example.net", r.stdout)
        self.assertEqual(self.fake.writes(), [])


class Drive(unittest.TestCase):
    def setUp(self):
        self.fake, self.root = setup()

    def tearDown(self):
        self.fake.close()

    def test_sharing_is_by_name_and_read_back(self):
        r = run(self.root, self.fake, "drive", "share", "f1", "--contract", "dinner",
                "--email", "anna@example.com", "--role", "reader", "--notify", "no")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        post = [c for c in self.fake.writes() if c[0] == "POST"][0]
        self.assertEqual(post[3], {"type": "user", "role": "reader", "emailAddress": "anna@example.com"})
        self.assertEqual(post[2]["sendNotificationEmail"], "false")
        self.assertIn("who sees it: me@example.com (owner), anna@example.com (reader)", r.stdout)

    def test_a_stranger_or_a_public_link_is_flagged(self):
        r = run(self.root, self.fake, "sheets", "share", "f1", "--contract", "dinner",
                "--email", "stranger@example.org", "--role", "writer", "--notify", "yes")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(self.fake.writes(), [])
        self.fake.perms["f1"].append({"type": "anyone", "role": "reader"})
        r = run(self.root, self.fake, "drive", "read", "f1")
        self.assertIn("ANYONE with the link", r.stdout)

    def test_a_sheet_is_written_only_when_the_rows_pass(self):
        good = write(self.root, "rows.csv", GOOD_CSV)
        r = run(self.root, self.fake, "sheets", "write", "s1", "--range", "Guests!A1",
                "--file", str(good), "--contract", "dinner")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.fake.values[("s1", "Guests!A1")][0], ["name", "email", "date"])
        self.assertIn("READ BACK: 3 rows", r.stdout)
        bad = write(self.root, "bad.csv", GOOD_CSV.replace("date\n", "date,phone\n", 1))
        n = len(self.fake.writes())
        r = run(self.root, self.fake, "sheets", "write", "s1", "--range", "Guests!A1",
                "--file", str(bad), "--contract", "dinner")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(len(self.fake.writes()), n)


if __name__ == "__main__":
    unittest.main()
