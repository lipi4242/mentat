"""`fleet retire` (visszavonható nyugdíjazás) és a box-feloldás (`remote.resolve`).

2026-10-29: a donor-ágenst előbb leállítjuk, később töröljük — különben a gyógyult login
feléleszti, és a cronjai a fogadóval párhuzamosan írnak kifelé.
"""
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import os
import subprocess
import tempfile
import unittest

from fleet import maintenance, retire
from fleet.remote import resolve, ssh_target_of

# rc_name: a registry normalize-a mindig kitölti; /proc-os gépen az agentctl.stop() generáció-jelölése olvassa
ENTRY = {"agent": "donor", "rc_name": "donor", "unit": "donor.service", "session": "donor", "workdir": "%h/donor-repo",
         "bridge": {"unit": "donor-telegram-bridge.service"}}
TIMERS = ("Thu 2026-10-29 09:00:00 UTC 1h left - - donor-meeting.timer donor-meeting.service\n"
          "Thu 2026-10-29 09:05:00 UTC 1h left - - other.timer other.service\n")
CRON = "# comment donor\n0 7 * * 1-5 cd ~/donor-repo && ./daily.sh\n0 8 * * * ~/other/x.sh\n"


class Runner:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd):
        self.calls.append(cmd)
        out = {"list-timers": TIMERS, "crontab": CRON, "timedatectl": "UTC\n"}
        key = next((k for k in out if k in cmd or (cmd and cmd[0] == k)), None)
        return subprocess.CompletedProcess(cmd, 0, out.get(key, ""), "")


class TestRetire(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.saved = os.environ.get("FLEET_MAINTENANCE_DIR")
        os.environ["FLEET_MAINTENANCE_DIR"] = self._t.name

    def tearDown(self):
        os.environ.pop("FLEET_MAINTENANCE_DIR", None) if self.saved is None else \
            os.environ.__setitem__("FLEET_MAINTENANCE_DIR", self.saved)
        self._t.cleanup()

    def test_lock_stop_disable_bridge_and_checklist(self):
        run = Runner()
        r = retire.retire(ENTRY, run=run)
        self.assertTrue(r["ok"], r)
        self.assertTrue(maintenance.is_locked("donor"))
        sysctl = [c[2:] for c in run.calls if c[:2] == ["systemctl", "--user"]]
        for want in (["stop", "donor.service"], ["disable", "donor.service"],
                     ["stop", "donor-telegram-bridge.service"], ["disable", "donor-telegram-bridge.service"]):
            self.assertIn(want, sysctl)
        self.assertLess(sysctl.index(["stop", "donor.service"]), sysctl.index(["disable", "donor.service"]))
        self.assertEqual(r["leftovers"], ["timer: Thu 2026-10-29 09:00:00 UTC 1h left - - donor-meeting.timer "
                                          "donor-meeting.service", "cron: 0 7 * * 1-5 cd ~/donor-repo && ./daily.sh"])
        self.assertEqual(r["tz"], "UTC")
        text = "\n".join(r["checklist"])
        self.assertIn('"status": "dormant"', text)
        self.assertIn("donor-meeting.timer", text)
        self.assertIn("git pull", text)

    def test_registry_is_never_written(self):
        run = Runner()
        retire.retire(ENTRY, run=run)
        self.assertFalse(any("agents.json" in " ".join(c) for c in run.calls))

    def test_failed_stop_is_not_ok_and_does_not_disable(self):
        def run(cmd):
            rc = 1 if cmd[:3] == ["systemctl", "--user", "stop"] else 0
            return subprocess.CompletedProcess(cmd, rc, "", "boom")
        calls = []
        r = retire.retire(ENTRY, run=lambda c: (calls.append(c), run(c))[1])
        self.assertFalse(r["ok"])
        self.assertFalse(any("disable" in c for c in calls))


class TestResolve(unittest.TestCase):
    AGENTS = [{"agent": "a1", "host": "box-a", "claude_account": "acc"}, {"agent": "a2", "host": "box-b"}]
    BOXES = [{"key": "box-a", "hostname": "a.example", "unix_user": "agent"},
             {"key": "box-b", "hostname": "b.example", "ssh_target": "ops@b"}]

    def r(self, name, **kw):
        return resolve(name, agents=self.AGENTS, boxes=self.BOXES, here="box-b", **kw)

    def test_remote_box_from_registry(self):
        e, t = self.r("a1")
        self.assertEqual((e["agent"], t.ssh), ("a1", "agent@a.example"))

    def test_same_box_is_local(self):
        self.assertIsNone(self.r("a2")[1].ssh)

    def test_unknown_name_is_ssh_target(self):
        e, t = self.r("someone@elsewhere")
        self.assertEqual((e, t.ssh), (None, "someone@elsewhere"))

    def test_ssh_override_keeps_entry_data(self):
        e, t = self.r("a1", ssh="root@old-box")
        self.assertEqual((e["claude_account"], t.ssh), ("acc", "root@old-box"))

    def test_ssh_target_of(self):
        self.assertEqual(ssh_target_of({"key": "k"}), "k")
        self.assertEqual(ssh_target_of(self.BOXES[1]), "ops@b")

    def test_ssh_argv_has_batchmode_and_no_secret_slot(self):
        _, t = self.r("a1")
        argv = t.argv("echo hi")
        self.assertIn("BatchMode=yes", argv)
        self.assertEqual(argv[argv.index("--") + 1], "agent@a.example")


if __name__ == "__main__":
    unittest.main()
