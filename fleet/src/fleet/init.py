"""`fleet init [<ágens>] [--repo .]` — a registry-bejegyzés EGY parancsa.

06-flotta mérés: az ágens ~27 KB doksit olvasott, a registry/preflight
forrását grep-elte, majd kézzel írta az agents.json-t. Itt a bejegyzés a
repóból épül (mentat.json `agent.name`, különben a könyvtár neve), a
registry hiányában egy minimális jön létre `~/.config/fleet/registry.d`-ben,
`fleet validate` ellenőrzi, a hiányzó előfeltételt (tmux, claude, login)
egy sorban a javító paranccsal mondja, és kiírja a következő lépést.
Idempotens: a már meglévő bejegyzéshez nem nyúl.
"""
from __future__ import annotations
import os
import re
import socket
from pathlib import Path

from fleet import RegistryNotConfigured, claude_auth, names, registry_dir, registry_pointer_file
from fleet import mentat_manifest as mm
from fleet import registry as reg
from fleet.install_checks import CLAUDE_BIN, TMUX_BIN, tmux_problem


def _fail(res: dict, msg: str) -> dict:
    res.update(status="failed", summary=f"fleet init {res['agent'] or ''}: NEM KÉSZ — {msg}".replace("  ", " "))
    return res


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", s.lower()).strip("-")[:40]


def _registry(home: Path) -> tuple[Path, str]:
    try:
        return registry_dir(home), "meglévő"
    except RegistryNotConfigured:
        if os.environ.get("FLEET_REGISTRY", "").strip():
            raise
    d = home / ".config" / "fleet" / "registry.d"
    d.mkdir(parents=True, exist_ok=True)
    ptr = registry_pointer_file(home)
    ptr.parent.mkdir(parents=True, exist_ok=True)
    ptr.write_text(f"{d}\n")
    return d, "új"


def _box(rdir: Path, host_name: str) -> str:
    """A gép box-kulcsa; ha a boxes.json nem ismeri, felveszi."""
    raw = reg.load_json(rdir / "boxes.json", {})
    doc = raw if isinstance(raw, dict) else {}
    boxes = reg.load_boxes(rdir / "boxes.json")
    known = reg.local_host(boxes)
    if known:
        return known
    key = _slug(host_name) or "box"
    boxes.append({"key": key, "hostname": host_name})
    reg.save_json(rdir / "boxes.json", {**doc, "boxes": boxes})
    return key


def _prereqs(entry: dict, home: Path, claude_bin: Path, tmux_bin: Path) -> list[str]:
    out = list(tmux_problem(tmux_bin))
    if not claude_bin.is_file():
        out.append(f"hiányzik a claude ({claude_bin}) — telepítsd: `curl -fsSL https://claude.ai/install.sh | bash`")
    elif not claude_auth.logged_in(entry, claude_bin=claude_bin, home=home) \
            and not os.environ.get(claude_auth.TOKEN_VAR):
        if claude_auth.systemd_token():   # a gép systemd-környezetében van token, a shellben nincs
            out.append(f"nincs bejelentkezve a claude, de a felhasználói systemd-környezetben van token — "
                       f"`fleet auth {entry['agent']} --from-systemd`")
        else:
            out.append(f"nincs bejelentkezve a claude — abban a shellben, ahol be van jelentkezve: "
                       f"`fleet auth {entry['agent']}`, vagy ezen a boxon `claude auth login`")
    return out


def init(agent: str | None = None, *, repo: Path = Path("."), model: str = "opus", home: Path | None = None,
         claude_bin: Path = CLAUDE_BIN, tmux_bin: Path = TMUX_BIN, host_name: str | None = None) -> dict:
    from fleet.validate import validate
    home = home or Path.home()
    repo = Path(repo).resolve()
    doc = mm.load(repo) or {}
    agent = agent or _slug(str((doc.get("agent") or {}).get("name") or repo.name))
    res = {"agent": agent, "status": "failed", "summary": ""}
    if not names.is_valid_agent_name(agent):
        return _fail(res, f"az ágens neve nem slug (kisbetű, szám, kötőjel): {agent!r}")
    if not (repo / ".git").exists():
        return _fail(res, f"a repó nem git repó ({repo}) — `cd {repo} && git init`")
    try:
        rdir, how = _registry(home)
    except RegistryNotConfigured as e:
        return _fail(res, str(e))
    host = _box(rdir, host_name or socket.gethostname())
    agents = reg.load_json(rdir / "agents.json", [])
    existing = reg.get_agent(agent, [reg.normalize(a) for a in agents if isinstance(a, dict)])
    if existing is None:
        h = str(home.resolve())
        wd = "%h" + str(repo)[len(h):] if str(repo).startswith(h + os.sep) else str(repo)
        agents.append({"agent": agent, "description": f"{agent} — always-on ágens", "unit": f"{agent}.service",
                       "session": agent, "workdir": wd, "model": model, "host": host,
                       "status": "active", "proactive": False, "runbook": f"runbooks/{agent}.md"})
        reg.save_json(rdir / "agents.json", agents)
    rb = rdir / "runbooks" / f"{agent}.md"
    if not rb.exists():
        rb.parent.mkdir(parents=True, exist_ok=True)
        rb.write_text(f"# {agent}\n\nFut: `{host}` · repó: `{repo.name}` · indítás/ellenőrzés: "
                      f"`fleet setup {agent}`, `fleet doctor {agent}`.\n")
    entry = reg.get_agent(agent, [reg.normalize(a) for a in reg.load_json(rdir / "agents.json", [])
                                  if isinstance(a, dict) and a.get("agent")])
    from fleet.setup import _own
    n, problems = validate(rdir)
    own = _own(agent, problems)
    if own:
        return _fail(res, own[0])
    state = "bejegyzés írva" if existing is None else "már a registryben (nem írtam át)"
    head = f"fleet init {agent}: registry {rdir} ({how}) · box {host} · {state} · validate ok"
    missing = _prereqs(entry, home, claude_bin, tmux_bin)
    rest = (f"fleet setup {agent}   # az utolsó sora az eredmény, exit 0 = healthy\n"
            f"  fleet stop {agent}; fleet wait-up {agent}   # próba: magától visszajön-e (új processz)")
    if missing:
        res.update(status="failed", summary=f"{head}\nelőfeltétel hiányzik: {missing[0]}"
                   + "".join(f"\n  és: {m}" for m in missing[1:])
                   + f"\nhátra (sorban, nincs más teendő): a fenti javítás(ok) → {rest}")
        return res
    res.update(status="ok", summary=f"{head}\nhátra (sorban, nincs más teendő): {rest}")
    return res
