"""Env-sorba csak héj-semleges érték kerül (a unit `sh -c '. fájl'`-lal tölti be: `$(…)` futna, a szóköz
kiürítené, a `\\x0b` sort törne), a jóváhagyás tétele atomikusan egyszer használható, a nyugta
hibája megmondja, hogy a cél megváltozott-e, és a nyugta lenyomata sózott HMAC. A put és a
move/copy ugyanazon az íráson megy."""
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import hashlib
import hmac
import json
import unittest
from unittest import mock

from fleet import titok_hely as H, titok_iras as W, titok_jovahagy as J
from test_titok_put import PutBase

BAD = ["$(touch /tmp/x)", "`id`", "ket szo", "a\x0bB=1", "'q'", '"q"', "a;b", "a$b", "a\\b", "a|b", "a\tb", "~root", "a~b"]
# tipikus kulcs-alakok, darabokból (a titokszkenner ne lássa bennük valódi kulcsot)
GOOD = ["-".join(("sk", "ant", "api03", "AbC_d", "123")), "ghp" + "_ABCdef0123456789", "AKIA0123/abc+def==",
        "-".join(("xoxb", "1", "2", "abc")), ".".join(("eyJhbGciOi", "eyJzdWIi", "sig_-")), "user@host:8080",
        "a.b_c"]


class Allowlist(PutBase):
    def test_shell_active_values_are_refused_without_echoing_them(self):
        for v in BAD:
            aid = self.approve("put:UJ_TOKEN:stdin:vilma:x")
            rc, text = self.put(v.encode(), aid)
            self.assertEqual(rc, 2, (repr(v), text))
            self.assertIn("nem megengedett karakter", text)
            self.assertNotIn(v, text)
        env = self.home / ".config/vilma/vilma.env"
        self.assertFalse(env.exists() and "UJ_TOKEN" in env.read_text())

    def test_typical_api_key_shapes_pass(self):
        for i, v in enumerate(GOOD):
            aid = self.approve(f"put:K{i}:stdin:vilma:x")
            rc, text = self.put(v.encode(), aid, name=f"K{i}")
            self.assertEqual(rc, 0, (v, text))
            self.assertIn(f"K{i}={v}\n", (self.home / ".config/vilma/vilma.env").read_text())

    def test_copy_uses_the_same_allowlist(self):
        src = self.home / ".config/szervezo/rossz.env"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("ROSSZ=$(id)\n")
        aid = self.approve(f"copy:ROSSZ:{src}:vilma:x")
        rc, text = self.run_cli("secrets", "copy", "--name", "ROSSZ", "--from", str(src), "--to", "vilma",
                                "--approval", aid)
        self.assertEqual(rc, 2, text)
        self.assertNotIn("$(id)", text)


    def test_a_trailing_newline_does_not_slip_through(self):
        from fleet import titok_iras as I
        for v in ("abc\n", "abc\r", "\nabc"):
            with self.assertRaises(J.Refused):
                I.check_env_value("K", v)


class Once(PutBase):
    def test_a_claimed_item_cannot_pass_check_again(self):
        aid = self.approve("put:UJ_TOKEN:stdin:vilma:x")
        J.check(aid, "put", "UJ_TOKEN", "stdin", "vilma", self.home)
        J.claim(aid, "put", "UJ_TOKEN", "stdin", "vilma", self.home)  # a másik folyamat már elvitte
        with self.assertRaises(J.Refused):
            J.claim(aid, "put", "UJ_TOKEN", "stdin", "vilma", self.home)
        with self.assertRaises(J.Refused):
            J.check(aid, "put", "UJ_TOKEN", "stdin", "vilma", self.home)
        self.assertEqual(self.put(b"abc", aid)[0], 2)

    def test_receipt_failure_says_the_target_changed(self):
        aid = self.approve("put:UJ_TOKEN:stdin:vilma:x")
        with mock.patch.object(H, "append_line", side_effect=OSError("tele")):
            rc, text = self.put(b"abc123", aid)
        self.assertEqual(rc, 1, text)
        self.assertIn("MEGVÁLTOZOTT", text)
        self.assertIn("UJ_TOKEN=abc123", (self.home / ".config/vilma/vilma.env").read_text())
        self.assertNotIn("abc123", text)
        want = hmac.new(H.receipt_salt_path(self.home).read_bytes(), b"abc123", hashlib.sha256).hexdigest()
        self.assertIn(f"hmac {want}", text)            # a kézi feljegyzéshez a kulcsolt lenyomat
        self.assertNotIn(hashlib.sha256(b"abc123").hexdigest()[:8], text)


class WriteSecret(PutBase):
    """A dirfd-láncos írás: hiányzó mappa 0700, cél 0600, ideiglenes fájl nem marad, symlinken át nem ír."""
    def test_creates_missing_dirs_and_leaves_no_temp(self):
        dest = self.home / ".config/uj/al/uj.env"
        W.write_secret(self.home, dest, "A=1\n")
        W.write_secret(self.home, dest, lambda old: old + "B=2\n")
        self.assertEqual(dest.read_text(), "A=1\nB=2\n")
        self.assertEqual(dest.stat().st_mode & 0o777, 0o600)
        self.assertEqual(dest.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual([p.name for p in dest.parent.iterdir()], ["uj.env"])

    def test_symlink_anywhere_on_the_path_is_refused(self):
        out = self.home / "kint"
        out.mkdir()
        (self.home / ".config/link").symlink_to(out, target_is_directory=True)
        (self.home / ".config/vilma/l.env").symlink_to(out / "x.env")
        for dest in (self.home / ".config/link/a.env", self.home / ".config/link/uj/a.env",
                     self.home / ".config/vilma/l.env"):
            with self.assertRaises(OSError):
                W.write_secret(self.home, dest, "A=1\n")
        self.assertEqual(list(out.iterdir()), [])


class ReceiptMac(PutBase):
    """A nyugta lenyomata HMAC-SHA256 boxonkénti sóval: rövid kulcsnál sem fejthető vissza."""
    SHORT = "ab12"

    def last(self):
        return json.loads(self.receipts().splitlines()[-1])

    def test_receipt_has_no_short_hash_and_no_value(self):
        rc, text = self.put((self.SHORT + "\n").encode(), self.approve("put:UJ_TOKEN:stdin:vilma:x"))
        self.assertEqual(rc, 0, text)
        raw, rec = self.receipts(), self.last()
        short = hashlib.sha256(self.SHORT.encode()).hexdigest()
        self.assertNotIn("hash8", rec)
        self.assertNotIn(short[:8], raw)
        self.assertNotIn(self.SHORT, raw)
        self.assertNotIn(short[:8], text)
        salt = H.receipt_salt_path(self.home)
        self.assertEqual(salt.stat().st_mode & 0o777, 0o600)
        want = hmac.new(salt.read_bytes(), self.SHORT.encode(), hashlib.sha256).hexdigest()
        self.assertEqual(rec["hmac"], want)

    def test_salt_is_made_once_and_reused(self):
        self.put(b"elso\n", self.approve("put:UJ_TOKEN:stdin:vilma:x"))
        salt = H.receipt_salt_path(self.home).read_bytes()
        first = self.last()["hmac"]
        self.put(b"elso\n", self.approve("put:UJ_TOKEN:stdin:vilma:y"))
        self.assertEqual(H.receipt_salt_path(self.home).read_bytes(), salt)
        self.assertEqual(self.last()["hmac"], first)
        self.assertGreaterEqual(len(salt), 32)

    def test_symlinked_salt_is_refused(self):
        real = self.home / "mashol-so"
        real.write_bytes(b"x" * 32)
        p = H.receipt_salt_path(self.home)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.symlink_to(real)
        rc, text = self.put(b"ertek\n", self.approve("put:UJ_TOKEN:stdin:vilma:x"))
        self.assertNotEqual(rc, 0, text)
        self.assertNotIn("ertek", self.receipts())


if __name__ == "__main__":
    unittest.main()
