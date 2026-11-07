"""F-39: fail-open hooks. A PreToolUse command hook without `onFailure: "block"` lets the
tool call through when the hook crashes, times out or cannot start; Claude Code before
2.1.295 ignores the field. `fleet doctor` reports both — it never edits a settings file.

    hook_problems(repo) -> [problem]          the agent repo's .claude/settings{,.local}.json
    version_problem(text) -> problem | None   `claude --version`; None if not measurable
"""
from __future__ import annotations
import json
import re
import subprocess
from pathlib import Path

from fleet.install_checks import CLAUDE_BIN

MIN_CLAUDE = (2, 1, 295)
FILES = (".claude/settings.json", ".claude/settings.local.json")


def hook_problems(repo: Path) -> list[str]:
    return [p for rel in FILES for p in _file_problems(Path(repo) / rel, rel)]


def user_hook_problems(claude_home: Path) -> list[str]:
    """N1: the user-level settings run their PreToolUse hooks for every agent of that home."""
    label = "~/" + Path(claude_home).name + "/settings.json"
    return _file_problems(Path(claude_home) / "settings.json", label)


def secrets_gate_problems(claude_home: Path) -> list[str]:
    """H5: ha a boxon él a titok-kapu, ebben a Claude-gyökérben is fent kell lennie (onFailure: block)."""
    from fleet import titok_telepit
    return titok_telepit.problems(claude_home)


def _file_problems(path: Path, rel: str) -> list[str]:
    out = []
    if path.is_file():
        try:
            s = json.loads(path.read_text(encoding="utf-8"))
            entries = (s.get("hooks") or {}).get("PreToolUse") or []
        except (OSError, ValueError, AttributeError) as e:
            return [f"{rel} nem olvasható ({type(e).__name__}): a hookok nem ellenőrizhetők"]
        for e in entries if isinstance(entries, list) else []:
            for h in (e.get("hooks") or []) if isinstance(e, dict) else []:
                if isinstance(h, dict) and h.get("type", "command") == "command" and h.get("onFailure") != "block":
                    cmd = str(h.get("command", ""))
                    short = cmd.split("/")[-1][:60] if "/" in cmd else cmd[:60]
                    out.append(f"PreToolUse-hook fail-open ({rel}: onFailure:\"block\" hiányzik): {short}")
    return out


def version_problem(text: str | None) -> str | None:
    m = re.match(r"\s*(\d+)\.(\d+)\.(\d+)", text or "")
    if not m or tuple(map(int, m.groups())) >= MIN_CLAUDE:
        return None
    return (f"Claude Code {m.group(0).strip()} régi: a hook onFailure:\"block\"-ját "
            f"{'.'.join(map(str, MIN_CLAUDE))} előtt figyelmen kívül hagyja (fail-open)")


def claude_version() -> str | None:
    """N3: the binary the unit runs (install_checks.CLAUDE_BIN), never PATH's `claude`."""
    try:
        r = subprocess.run([str(CLAUDE_BIN), "--version"], capture_output=True, text=True, timeout=20)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def version_unknown(text: str | None) -> str | None:
    """N2: an unmeasurable version is reported, not taken as green."""
    if re.match(r"\s*\d+\.\d+\.\d+", text or ""):
        return None
    return f"Claude Code verzió nem mérhető ({CLAUDE_BIN}): az onFailure hatása nem igazolható"
