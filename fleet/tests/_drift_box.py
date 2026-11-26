"""Közös fixture a prompt-drift tesztekhez: git-repó munkakönyvtár (a kiadás =
commit), izolált HOME, a TERMELŐ reconcile.reconcile() és execute(); csak a
systemctl, a postcheck, a pane-beküldés és a Telegram kamu."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import functools
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fleet import alerts, prompt_drift, prompt_drift_report, reconcile  # noqa: E402
from fleet.registry import normalize  # noqa: E402

T0 = float(int(time.time()))
IDLE, BUSY = 3600, 5


class Box(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="fleet-drift-"))
        self.wd = self.d / "repo"
        (self.wd / ".claude" / "rules").mkdir(parents=True)
        (self.wd / "CLAUDE.md").write_text("\n".join(["# agy", "@AGENTS.md", ""]))
        (self.wd / "AGENTS.md").write_text("szabályok\n@docs/extra.md\n")
        (self.wd / "docs").mkdir()
        (self.wd / "docs" / "extra.md").write_text("include-lánc vége\n")
        (self.wd / ".claude" / "rules" / "r.md").write_text("egy szabály\n")
        self.git("init", "-q"); self.git("add", "-A"); self.git("commit", "-qm", "alap")
        subprocess.run(["git", "init", "-q", "--bare", str(self.d / "origin.git")], check=True, capture_output=True)
        self.git("remote", "add", "origin", str(self.d / "origin.git"))
        self.git("push", "-q", "origin", "HEAD"); self.git("remote", "set-head", "origin", "-a")
        self.backdate()
        (self.d / "home").mkdir()
        p = mock.patch.dict(os.environ, {"FLEET_MAINTENANCE_DIR": str(self.d / "maint"), "HOME": str(self.d / "home")})
        p.start(); self.addCleanup(p.stop)
        self.alerts, self.sent, self.calls = [], [], []
        for obj, attr, val in [(reconcile, "STATE_DIR", self.d / "st"), (reconcile, "LOCK_PATH", self.d / "st" / "lock"),
                               (reconcile, "controller_is_us", lambda: True), (reconcile, "local_host", lambda: "box"),
                               (prompt_drift_report, "LOG_PATH", self.d / "st" / "prompt-drift.log"),
                               (alerts, "ALERTS_PATH", self.d / "st" / "alerts.json"),
                               (alerts, "UNDELIVERED", self.d / "st" / "undelivered.jsonl"),
                               (alerts, "send_telegram", lambda *a, **k: self.alerts.append(a[0]) or True)]:
            p = mock.patch.object(obj, attr, val); p.start(); self.addCleanup(p.stop)
        p = mock.patch("fleet.tick_gate_inject.send", lambda s, line: self.sent.append(line) or (True, "ok"))
        p.start(); self.addCleanup(p.stop)
        self.agents = [self._entry("probe-agent")]
        self.gen = {"probe-agent": 100}
        self.started = T0 - 50

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.wd), "-c", "user.name=t", "-c", "user.email=t@x.invalid",
                        "-c", "commit.gpgsign=false", *args], check=True, capture_output=True)

    def change(self, rel, text, commit=True, push=True):
        """Egy kiadás: a fájl átírva, (alapból) commitolva és az originre küldve, ahogy egy
        checkout hozná; push=False: helyi commit, ami nincs az origin alapágán."""
        p = self.wd / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        if commit:
            self.git("add", "-A"); self.git("commit", "-qm", "kiadas")
            if push:
                self.git("push", "-q", "origin", "HEAD")

    def settle(self, t, age=IDLE):
        """Észlelés t-kor, majd egy kör a stabilitási idő után."""
        self.round(t, age=age)
        return self.round(t + prompt_drift.STABLE_S + 1, age=age)

    def backdate(self):
        """A fixture-fájlok a processz indulása ELŐTT készültek (az mtime-tartalék ne lássa őket)."""
        for f in self.d.rglob("*"):
            if f.is_file():
                os.utime(f, (T0 - 1000, T0 - 1000))

    def _entry(self, name):
        return normalize({"agent": name, "workdir": str(self.wd), "host": "box"})

    def measure(self, age):
        def m(e):
            sig = lambda s, data=None: {"state": s, "detail": "", "data": data or {}}
            return {"agent": e["agent"], "transcript_age_s": age, "pollers": [], "rearm_age_s": None,
                    "signals": {"process": sig("up", {"pid": self.gen[e["agent"]], "started_s": self.started}),
                                "schedule": sig("n/a"), "channel": sig("n/a"), "rc": sig("n/a"), "auth": sig("ok")}}
        return m

    def round(self, now, age=IDLE):
        ex = functools.partial(reconcile.execute, sysctl=lambda *a: self.calls.append(a) or 0, run=lambda *a, **k: None,
                               do_postcheck=lambda e, **k: {"status": "ok", "ok": True, "pending": [], "problems": []})
        return reconcile.reconcile(agents=self.agents, now=now, measure=self.measure(age), unit_active=lambda u: True,
                                   execute_fn=ex, oom_sweep=lambda: {"protected": 0}, procs=None)["lines"]

    def restarts(self):
        return [c for c in self.calls if c[0] == "restart"]

    def st(self, name="probe-agent"):
        return reconcile.load_state(name)
