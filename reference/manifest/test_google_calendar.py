"""mentat_google.py calendar: an invitation goes only to the contract's audience, hidden, with an
explicit notification choice, and the answer says who was notified and who sees what.

Class of error (holdout, 0.3.0): invitations to several outside people where everyone saw the
guest list, sent without saying who got a notification; the guest list was chosen by hand.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import unittest

from _google_fixture import PROPOSAL, setup, run

EVENT = ["calendar", "create", "--title", "Dinner", "--start", "2026-11-07T19:00:00",
         "--end", "2026-11-07T22:00:00", "--tz", "Europe/Budapest"]


class Create(unittest.TestCase):
    def setUp(self):
        self.fake, self.root = setup()

    def tearDown(self):
        self.fake.close()

    def create(self, *extra):
        return run(self.root, self.fake, *EVENT, *extra)

    def test_guests_from_the_contract_hidden_and_the_notification_said(self):
        r = self.create("--contract", "dinner", "--guests", "contract", "--notify", "all")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        ev = self.fake.events["e1"]
        self.assertFalse(ev["guestsCanSeeOtherGuests"])
        self.assertEqual(sorted(a["email"] for a in ev["attendees"]), ["anna@example.com", "bob@example.com"])
        post = [c for c in self.fake.writes() if c[0] == "POST"][0]
        self.assertEqual(post[2]["sendUpdates"], "all")
        self.assertIn("notified: anna@example.com, bob@example.com", r.stdout)
        self.assertIn("cannot see each other", r.stdout)
        self.assertIn("READ BACK", r.stdout)

    def test_the_notification_choice_is_required(self):
        r = self.create("--contract", "dinner", "--guests", "contract")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.fake.writes(), [])

    def test_a_guest_outside_the_audience_stops_the_send(self):
        r = self.create("--contract", "dinner", "--guests", "anna@example.com,stranger@example.org",
                        "--notify", "all")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("stranger@example.org", r.stdout)
        self.assertEqual(self.fake.writes(), [])

    def test_guests_without_a_contract_or_visible_against_it_stop(self):
        r = self.create("--guests", "anna@example.com", "--notify", "none")
        self.assertEqual(r.returncode, 2, r.stdout)
        r = self.create("--contract", "dinner", "--guests", "contract", "--notify", "all",
                        "--guests-see-each-other")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(self.fake.writes(), [])

    def test_left_out_data_in_the_description_stops_the_send(self):
        r = self.create("--contract", "dinner", "--guests", "contract", "--notify", "none",
                        "--description", "call Péter at +36 1 333 3333")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(self.fake.writes(), [])

    def test_an_own_event_needs_no_contract(self):
        r = self.create("--notify", "none")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("no guests", r.stdout)


class Update(unittest.TestCase):
    def setUp(self):
        self.fake, self.root = setup(dict(PROPOSAL, audience=dict(PROPOSAL["audience"])))
        r = run(self.root, self.fake, *EVENT, "--contract", "dinner", "--guests", "contract", "--notify", "none")
        assert r.returncode == 0, r.stdout + r.stderr
        self.fake.events["e1"]["guestsCanSeeOtherGuests"] = True  # changed by hand in the calendar

    def tearDown(self):
        self.fake.close()

    def test_an_update_of_an_event_with_guests_is_checked_and_hides_them_again(self):
        r = run(self.root, self.fake, "calendar", "update", "e1", "--title", "Dinner (moved)", "--notify", "all")
        self.assertEqual(r.returncode, 2, r.stdout)  # it reaches people: the contract is needed
        r = run(self.root, self.fake, "calendar", "update", "e1", "--title", "Dinner (moved)",
                "--notify", "externalOnly", "--contract", "dinner")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        patch = [c for c in self.fake.writes() if c[0] == "PATCH"]
        self.assertEqual(len(patch), 1)
        self.assertFalse(patch[0][3]["guestsCanSeeOtherGuests"])
        self.assertEqual(patch[0][2]["sendUpdates"], "externalOnly")
        self.assertIn("Dinner (moved)", r.stdout)


if __name__ == "__main__":
    unittest.main()
