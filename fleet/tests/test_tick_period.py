import subprocess
import tempfile
import unittest
from pathlib import Path

from fleet import tick_period as T

TIMER = "[Unit]\nDescription=x\n\n[Timer]\nOnCalendar=hourly\nPersistent=true\nUnit=fleet-tick-vilma.service\n"


class CalendarTest(unittest.TestCase):
    def test_ertekek(self):
        self.assertEqual(T.calendar(1800), "*:00/30")
        self.assertEqual(T.calendar(900), "*:00/15")
        self.assertEqual(T.calendar(3600), "hourly")
        self.assertEqual(T.calendar(7200), "00/2:00")
        for bad in (100, 1700, 5000):
            with self.assertRaises(ValueError):
                T.calendar(bad)

    def test_timer_atirasa(self):
        d = Path(tempfile.mkdtemp())
        (d / "fleet-tick-vilma.timer").write_text(TIMER)
        calls = []
        out = T.apply("vilma", 1800, unit_dir=d, run=lambda c, **k: calls.append(c) or subprocess.CompletedProcess(c, 0))
        text = (d / "fleet-tick-vilma.timer").read_text()
        self.assertIn("OnCalendar=*:00/30", text)
        self.assertEqual(text.count("OnCalendar="), 1)
        self.assertIn("Persistent=true", text)
        self.assertIn(["systemctl", "--user", "restart", "fleet-tick-vilma.timer"], calls)
        self.assertIn("*:00/30", out)

    def test_eltero_fajlbol_is_lesz_oncalendar(self):
        """CISO Q4: a regex-csere a `[Timer]\\n` szöveghez kötött; ha a fájl eltér (záró szóköz, CRLF),
        az OnCalendar-t kitörölte és nem írta vissza: a timer soha többé nem tüzelt volna."""
        for variant in (TIMER.replace("[Timer]\n", "[Timer] \n"), TIMER.replace("\n", "\r\n")):
            d = Path(tempfile.mkdtemp())
            (d / "fleet-tick-vilma.timer").write_text(variant)
            T.apply("vilma", 1800, unit_dir=d, run=lambda c, **k: subprocess.CompletedProcess(c, 0))
            lines = (d / "fleet-tick-vilma.timer").read_text().splitlines()
            self.assertIn("OnCalendar=*:00/30", lines, repr(variant))

    def test_systemctl_hiba_hangos(self):
        d = Path(tempfile.mkdtemp())
        (d / "fleet-tick-vilma.timer").write_text(TIMER)
        with self.assertRaises(ValueError) as cm:
            T.apply("vilma", 1800, unit_dir=d, run=lambda c, **k: subprocess.CompletedProcess(c, 1, "", "nincs busz"))
        self.assertIn("daemon-reload", str(cm.exception))

    def test_nincs_timer(self):
        self.assertIn("nincs", T.apply("vilma", 1800, unit_dir=Path(tempfile.mkdtemp()), run=lambda c, **k: None))


if __name__ == "__main__":
    unittest.main()
