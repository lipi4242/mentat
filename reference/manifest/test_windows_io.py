"""Windows text I/O: the ANSI code page (cp1252) is the default there for files, pipes and stdin.

A Windows run showed it: `mentat_init.py` died printing its own Hungarian result, the role guard
could not read a role file (so it denied everything), and `/mentat` help crashed. Every shipped
tool names UTF-8 for its files and child processes, and every entry point switches its standard
streams to UTF-8 before it prints anything.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import ast
import os
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
SHIPPED = sorted(p for d in (HERE, HERE.parent / "bekotes") for p in d.glob("*.py")
                 if not p.name.startswith(("test_", "_")))
SUBP = {"run", "check_output", "Popen", "check_call", "call"}


def _kw(call, name):
    return next((k for k in call.keywords if k.arg == name), None)


def _on(k):
    return k is not None and not (isinstance(k.value, ast.Constant) and not k.value.value)


def _text_call_without_encoding(call):
    f = call.func
    name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
    if _kw(call, "encoding") or any(k.arg is None for k in call.keywords):
        return False
    if name in ("read_text", "write_text"):
        return isinstance(f, ast.Attribute)
    if name in ("open", "fdopen"):
        if name == "open" and isinstance(f, ast.Attribute) and getattr(f.value, "id", "") in ("os", "opener"):
            return False  # os.open: a file descriptor; opener.open: a URL
        idx = 0 if isinstance(f, ast.Attribute) and name == "open" else 1
        mode = _kw(call, "mode")
        mode = mode.value if mode else (call.args[idx] if len(call.args) > idx else None)
        return not (isinstance(mode, ast.Constant) and "b" in str(mode.value))
    return name in SUBP and (_on(_kw(call, "text")) or _on(_kw(call, "universal_newlines")))


def _is_entry(tree):
    return any(isinstance(n, ast.If) and "__main__" in ast.dump(n.test) for n in tree.body)


class TextIO(unittest.TestCase):
    def test_every_text_file_and_child_process_names_utf8(self):
        bad = []
        for p in SHIPPED:
            for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
                if isinstance(n, ast.Call) and _text_call_without_encoding(n):
                    bad.append("%s:%d" % (p.name, n.lineno))
        self.assertEqual(bad, [], "text I/O without encoding= (cp1252 on Windows)")

    def test_every_text_write_keeps_lf(self):
        # Windows text mode writes CRLF: a receipt hashed as LF never matched its own file, and a
        # brain shared with a Mac churns. write_text(newline=) is 3.10+, the floor is 3.9: bytes.
        bad = []
        for p in SHIPPED:
            for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
                if not isinstance(n, ast.Call):
                    continue
                f = n.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
                if name == "write_text" and isinstance(f, ast.Attribute):
                    bad.append("%s:%d write_text" % (p.name, n.lineno))
                elif name in ("open", "fdopen") and not _kw(n, "newline") and \
                        not (name == "open" and getattr(getattr(f, "value", None), "id", "") in ("os", "opener")):
                    idx = 0 if isinstance(f, ast.Attribute) and name == "open" else 1
                    m = _kw(n, "mode")
                    m = m.value if m else (n.args[idx] if len(n.args) > idx else None)
                    if isinstance(m, ast.Constant) and "b" not in str(m.value) and set(str(m.value)) & set("wax+"):
                        bad.append("%s:%d open" % (p.name, n.lineno))
        self.assertEqual(bad, [])

    def test_every_entry_point_switches_its_streams_to_utf8(self):
        bad = [p.name for p in SHIPPED if _is_entry(ast.parse(p.read_text(encoding="utf-8")))
               and "\"reconfigure\", lambda **k: None)(encoding=\"utf-8\"" not in p.read_text(encoding="utf-8")]
        self.assertEqual(bad, [])

    def test_a_non_utf8_pipe_gets_the_hungarian_result_not_a_crash(self):
        d = pathlib.Path(_tmp_run.RUN_TMP) / "ansi" / ".mentat" / "bin"
        d.mkdir(parents=True, exist_ok=True)
        (d / "mentat_init.py").write_bytes((HERE / "mentat_init.py").read_bytes())
        (d / "mentat_verify.py").write_bytes((HERE / "mentat_verify.py").read_bytes())
        # a Windows pipe is the ANSI code page (cp1252 has no "ő"); ascii is the strict stand-in
        env = dict(os.environ, PYTHONIOENCODING="ascii:strict")
        r = subprocess.run([sys.executable, str(d / "mentat_init.py")], cwd=d, env=env, capture_output=True)
        out = r.stdout.decode("utf-8")
        self.assertIn("MENTAT-INIT HIBA", out)
        self.assertNotIn("UnicodeEncodeError", r.stderr.decode("utf-8", "replace"))


class OwnFilesAreGitPaths(unittest.TestCase):
    """git names files with "/": a Windows "\\" own-file list made the upgrade refuse its own skills."""

    def test_the_skill_paths_use_slashes_with_windows_path_rules(self):
        import mentat_scaffold
        import mentat_skills
        root = pathlib.Path(_tmp_run.RUN_TMP) / "own"
        for n in mentat_skills.SKILLS:
            (root / ".claude" / "skills" / n).mkdir(parents=True, exist_ok=True)
            (root / ".claude" / "skills" / n / "SKILL.md").write_text("x", encoding="utf-8")
        with mock.patch.object(mentat_skills.pathlib, "Path", pathlib.PureWindowsPath):
            own = mentat_scaffold.own_files(root, "hu")
        skills = [p for p in own if "skills" in p]
        self.assertTrue(skills)
        self.assertEqual([p for p in skills if "\\" in p], [])


class NoTimeZoneDatabase(unittest.TestCase):
    """Windows Python ships no IANA database: the message names the one-line fix (tzdata)."""

    def test_the_brain_says_install_tzdata(self):
        import zoneinfo
        import mentat_brain_types as bt
        with mock.patch.object(zoneinfo, "ZoneInfo", side_effect=zoneinfo.ZoneInfoNotFoundError("x")), \
                mock.patch.object(zoneinfo, "available_timezones", return_value=set()), \
                mock.patch.dict(os.environ, {"ANYTIME_TZ": "Europe/Budapest"}):
            with self.assertRaises(SystemExit) as e:
                bt.local_today(_tmp_run.RUN_TMP)
        self.assertIn("tzdata", str(e.exception))

    def test_a_contract_window_says_install_tzdata(self):
        import mentat_contract_terms as ct
        import zoneinfo
        with mock.patch.object(ct, "ZoneInfo", side_effect=ct.ZoneInfoNotFoundError("x")), \
                mock.patch.object(zoneinfo, "available_timezones", return_value=set()):
            errs = ct._window({"start": "2026-11-01", "end": "2026-11-30", "tz": "Europe/Budapest"})
        self.assertTrue(any("tzdata" in e for e in errs), errs)


if __name__ == "__main__":
    unittest.main()
