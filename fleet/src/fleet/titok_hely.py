"""A titok-eszközök (`fleet secrets`) helyei és az atomikus 0600-írás.

    base()                 ~/.mentat/titkok/ (leltar.json, nyugtak.jsonl, jovahagyas/<id>.json)
    agent_roots(agent)     ahol egy ágens titkai laknak: repó, ~/.config/<a>/, ~/.claude-<a>/, <repó>/.mentat/
    unit_env_files(agent)  a systemd --user unitok `EnvironmentFile=` sorai, amik az ágenshez tartoznak
    write_atomic(p, data)  0600, ideiglenes fájl + os.replace; symlinkre soha nem ír

A ~/.mentat/ a kapu védett útja (security/eszkozok/identitas/vedett_ut.py): az ágens Write/Edit
eszköze nem írhatja, csak ez a kód.
"""
from __future__ import annotations
import os
import re
import tempfile
from pathlib import Path

from fleet import RegistryNotConfigured


def base(home: Path | None = None) -> Path:
    return Path(home or Path.home()) / ".mentat" / "titkok"


def inventory_path(home: Path | None = None) -> Path:
    return base(home) / "leltar.json"


def receipts_path(home: Path | None = None) -> Path:
    return base(home) / "nyugtak.jsonl"


def approvals_dir(home: Path | None = None) -> Path:
    return base(home) / "jovahagyas"


def write_atomic(path: Path, data: bytes | str, mode: int = 0o600) -> Path:
    path = Path(path)
    if path.is_symlink():
        raise OSError(f"symlinkre nem írok: {path}")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data.encode() if isinstance(data, str) else data)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path


def append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "a") as f:
        f.write(line.rstrip("\n") + "\n")


def agent_repo(agent: str, home: Path | None = None) -> Path | None:
    """A registry `workdir`-je; registry nélkül ~/<ágens>, ha létezik."""
    h = Path(home or Path.home())
    try:
        from fleet import registry as reg
        e = reg.get_agent(agent)
    except (RegistryNotConfigured, OSError, ValueError):
        e = None
    if e and e.get("workdir"):
        return Path(str(e["workdir"]).replace("%h", str(h)))
    guess = h / agent
    return guess if guess.is_dir() else None


def agent_roots(agent: str, repo: Path | None = None, home: Path | None = None) -> list[tuple[str, Path]]:
    h = Path(home or Path.home())
    repo = repo or agent_repo(agent, h)
    out = [("repó", repo)] if repo else []
    out += [("config", h / ".config" / agent), ("claude", h / f".claude-{agent}")]
    out += [("mentat", repo / ".mentat")] if repo else []
    return [(k, p) for k, p in out if p.is_dir()]


ENVFILE = re.compile(r"^\s*EnvironmentFile\s*=\s*-?(.+?)\s*$")


def unit_env_files(agent: str, home: Path | None = None) -> list[Path]:
    h = Path(home or Path.home())
    udir = h / ".config" / "systemd" / "user"
    files = [p for p in udir.glob(f"{agent}*.service")] + list(udir.glob(f"{agent}*.service.d/*.conf"))
    out = []
    for u in sorted(files):
        try:
            text = u.read_text(errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            m = ENVFILE.match(line)
            if m:
                out.append(Path(m.group(1).replace("%h", str(h)).replace("${HOME}", str(h))))
    return sorted(set(out))
