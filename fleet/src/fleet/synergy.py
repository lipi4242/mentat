"""A flotta szinergiái a többi lego-elemmel (LG1 spec 3. pont).

agy + flotta:   a CLAUDE.md betölti-e az AGENTS.md-t (2026-07-20-án egy
                elveszett `@AGENTS.md` sor egy hétre elnémította a kiadási
                szabályt — ezért ellenőrzi a join).
motor + flotta: a flotta veszi át a tick ütemezését (5. szabály, `fleet.tick_schedule`).
"""
from __future__ import annotations
import re
from pathlib import Path

INCLUDE = "@AGENTS.md"


def claude_md_loads_agents(repo: Path) -> bool | None:
    """True/False, vagy None, ha nincs AGENTS.md (akkor nincs mit betölteni)."""
    repo = Path(repo)
    if not (repo / "AGENTS.md").exists():
        return None
    try:
        text = (repo / "CLAUDE.md").read_text()
    except OSError:
        return False
    return any(re.match(r"^\s*@(\./)?AGENTS\.md\s*$", line) for line in text.splitlines())


def fix_claude_md(repo: Path) -> str:
    """A betöltő sor a CLAUDE.md elejére. Más tartalomhoz nem nyúl."""
    p = Path(repo) / "CLAUDE.md"
    old = p.read_text() if p.exists() else ""
    p.write_text(f"{INCLUDE}\n\n{old}" if old else f"{INCLUDE}\n")
    return f"CLAUDE.md: `{INCLUDE}` beírva az elejére"


def check_brain(repo: Path, *, fix: bool) -> list[str]:
    ok = claude_md_loads_agents(repo)
    if ok is None or ok:
        return []
    if fix:
        return [fix_claude_md(repo)]
    return [f"FIGYELEM: a CLAUDE.md nem tölti be az AGENTS.md-t — az ágens agya nem töltődik be "
            f"minden sessionben. Javítás: `fleet join … --fix-claude-md` (egy `{INCLUDE}` sort ír az elejére)"]


def gitignore_note(repo: Path, run) -> list[str]:
    """A `.mentat/local.json` gépenkénti tény: nem kerülhet commitba."""
    r = run(["git", "-C", str(repo), "check-ignore", "-q", ".mentat/local.json"])
    if r.returncode == 0:
        return []
    return ["FIGYELEM: a .mentat/ nincs a .gitignore-ban — a local.json gépenkénti tény, ne commitold"]
