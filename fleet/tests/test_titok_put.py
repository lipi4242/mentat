"""`fleet secrets put`: a titok értéke csak stdin-ről jön (soha argv, env, kimenet, nyugta), tételes
`put:NÉV:stdin:HOVA:MIÉRT` jóváhagyással; a cél 0600, atomikus, symlinkre nem ír."""
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from fleet import cli, titok_hely as H, titok_jovahagy as J, titok_mozgat as M
from test_titok_mozgat import Base

VALUE = "PUT-HAMIS-ERTEK-7731"


class Stdin(io.TextIOWrapper):
    def __init__(self, data: bytes, tty=False):
        super().__init__(io.BytesIO(data), encoding="utf-8")
        self._tty = tty

    def isatty(self):
        return self._tty


class PutBase(Base):
    def put(self, data: bytes, aid: str, name="UJ_TOKEN", to="vilma", tty=False):
        out, err = io.StringIO(), io.StringIO()
        old = os.environ["HOME"]
        os.environ["HOME"] = str(self.home)
        try:
            with mock.patch.object(sys, "stdin", Stdin(data, tty)), redirect_stdout(out), redirect_stderr(err):
                rc = cli.main(["secrets", "put", "--name", name, "--to", to, "--approval", aid])
        finally:
            os.environ["HOME"] = old
        return rc, out.getvalue() + err.getvalue()

    def receipts(self):
        p = H.receipts_path(self.home)
        return p.read_text() if p.exists() else ""


class Put(PutBase):
    def test_put_writes_0600_and_the_value_shows_nowhere(self):
        aid = self.approve("put:UJ_TOKEN:stdin:vilma:a fogadó küld")
        rc, text = self.put((VALUE + "\n").encode(), aid)
        self.assertEqual(rc, 0, text)
        dest = self.home / ".config/vilma/vilma.env"
        self.assertIn(f"UJ_TOKEN={VALUE}\n", dest.read_text())
        self.assertEqual(dest.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(VALUE, text)
        rec = self.receipts()
        self.assertNotIn(VALUE, rec)
        self.assertEqual(json.loads(rec.splitlines()[-1])["op"], "put")
        self.assertEqual(self.put(VALUE.encode(), aid)[0], 2)  # egyszer használható

    def test_empty_too_big_multiline_and_tty_are_refused(self):
        aid = self.approve("put:UJ_TOKEN:stdin:vilma:a fogadó küld")
        for data, tty in ((b"", False), (b"\n", False), (b"x" * (64 * 1024 + 1), False),
                          (b"a\nb\n", False), (VALUE.encode(), True)):
            rc, text = self.put(data, aid, tty=tty)
            self.assertEqual(rc, 2, (len(data), tty, text))
            self.assertNotIn(VALUE, text)
        self.assertFalse((self.home / ".config/vilma/vilma.env").exists() and
                         "UJ_TOKEN" in (self.home / ".config/vilma/vilma.env").read_text())
        self.assertEqual(self.put(VALUE.encode(), aid)[0], 0)  # a visszautasítások nem használták el

    def test_bad_expired_wrong_item_and_wrong_op_approvals(self):
        for aid in ("nincs-ilyen", "rossz/id",
                    self.approve("put:UJ_TOKEN:stdin:vilma:x", now=0),
                    self.approve("put:MAS_TOKEN:stdin:vilma:x"),
                    self.approve("copy:UJ_TOKEN:szervezo:vilma:x")):
            rc, text = self.put(VALUE.encode(), aid)
            self.assertEqual(rc, 2, (aid, text))
            self.assertNotIn(VALUE, text)

    def test_symlink_target_and_bad_name_are_refused(self):
        real = self.home / "valahol.env"
        real.write_text("")
        link = self.home / ".config/vilma/link.env"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(real)
        aid = self.approve(f"put:UJ_TOKEN:stdin:{link}:x")
        rc, text = self.put(VALUE.encode(), aid, to=str(link))
        self.assertEqual(rc, 2, text)
        self.assertEqual(real.read_text(), "")
        rc, _ = self.put(VALUE.encode(), self.approve("put:A B:stdin:vilma:x"), name="A B")
        self.assertEqual(rc, 2)

    def test_put_item_must_read_from_stdin(self):
        with self.assertRaises(J.Refused):
            J.parse_item("put:UJ_TOKEN:szervezo:vilma:x")
        self.assertEqual(J.parse_item("put:UJ_TOKEN:stdin:vilma:x")["op"], "put")


class ParentSwap(PutBase):
    """Az ellenőrzés után a cél szülőmappája symlinkre cserélődik (TOCTOU): az írás nem mehet ki."""
    def swap_after_check(self):
        real, out = self.home / ".config/vilma", self.home / "kint"
        out.mkdir()

        def swap(*_a):
            if not real.is_symlink():
                real.rename(self.home / "vilma.eredeti")
                real.symlink_to(out, target_is_directory=True)
        return mock.patch.object(M, "check_env_value", side_effect=swap), out

    def test_put_stops_when_the_parent_becomes_a_symlink(self):
        aid = self.approve("put:UJ_TOKEN:stdin:vilma:a fogadó küld")
        patch, out = self.swap_after_check()
        with patch:
            rc, text = self.put(VALUE.encode(), aid)
        self.assertEqual(list(out.iterdir()), [], "az írás kiment a mappából a symlinken át")
        self.assertNotEqual(rc, 0, text)
        self.assertNotIn(VALUE, text)

    def test_copy_stops_when_the_parent_becomes_a_symlink(self):
        aid = self.approve("copy:SZ_TOKEN:szervezo:vilma:x")
        patch, out = self.swap_after_check()
        with patch, self.assertRaises(OSError):
            M.run("copy", "SZ_TOKEN", "szervezo", "vilma", aid, self.home)
        self.assertEqual(list(out.iterdir()), [], "az írás kiment a mappából a symlinken át")


if __name__ == "__main__":
    unittest.main()
