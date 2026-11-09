"""11-07: az ágensek alapfunkciói (essentials) a titok-kapu szemével, MIELŐTT egy boxszintű
változás (kapu-telepítés, új leltár) élesbe megy — és a doctorban utána is.

    commands(entry, home) -> [(címke, eszköz, bemenet)]   amit az ágensnek mindig tudnia kell
    gate_denials(entry, home, code) -> [hiba]              a `code`/titok_kapu.py --hook döntése, az
                                                           ágens FLEET_AGENT-jével és cwd-jével
    probe(agents, home, code) -> {ágens: {"red", "warn", "unknown"}}   kapu + előfeltételek
    format_probe(res) -> str

11-07: a `fleet secrets scan` a box minden Claude-gyökerébe feltette a kaput, az új leltár pedig
a telegram.env-et (és egy 0700-as job-szkriptet) tiltotta: két ágens némán nem tudott írni a
tulajdonosnak. Ezért minden ilyen változás előtt ez a próba fut, és piros ágensnél megáll.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

from fleet import essentials_env as E

MAX_JOBS = 20


def commands(entry: dict, home: Path) -> list[tuple[str, str, dict]]:
    a = entry["agent"]
    out = []
    if E.bridged(entry):
        send = f"node ~/.config/{a}/sub-etha/send.mjs"
        out += [("Telegram-küldés", "Bash", {"command": f"{send} --chat 1 -- x"}),
                ("Telegram-küldés stdinről", "Bash", {"command": f"printf x | {send} --chat 1 --text-stdin"}),
                ("Telegram-reakció", "Bash", {"command": f"{send} --chat 1 --react 👍 --message 1"}),
                ("kézbesítési napló", "Bash", {"command": f"node ~/.config/{a}/sub-etha/delivery.mjs"})]
    out += [("todo: ki vagyok", "Bash", {"command": "mentat-todo me"}),
            ("todo: változások (poll)", "Bash", {"command": "mentat-todo changes"}),
            ("git status a repóban", "Bash", {"command": "git status --short"}),
            ("git commit a saját repóban", "Bash", {"command": "git commit -m essentials-proba"}),
            ("git push a saját ágra", "Bash", {"command": "git push origin HEAD"})]
    wd = E.workdir(entry, home)
    for rel in ("data/state/anytime-state.json", "scripts/anytime/anytime-state-v2.json",
                "scripts/review-state/current.json", "data/state/todo-cursor.json"):
        if (wd / rel).is_file():  # a motor saját állapota: az ágensnek olvasnia kell
            out.append((f"saját állapot olvasása ({rel})", "Read", {"file_path": str(wd / rel)}))
    jobs = home / ".config" / a / "jobs"
    for p in sorted(jobs.glob("*"))[:MAX_JOBS] if jobs.is_dir() else []:
        run = {".py": "python3", ".sh": "sh", ".mjs": "node", ".js": "node"}.get(p.suffix)
        if run:
            out.append((f"job: {p.name}", "Bash", {"command": f"{run} ~/.config/{a}/jobs/{p.name}"}))
    out += [(f"registry-essential: {c}", "Bash", {"command": c}) for c in entry.get("essentials") or []
            if isinstance(c, str)]
    return out


def _env(entry: dict, home: Path) -> dict:
    env = {**os.environ, "HOME": str(home), "FLEET_AGENT": entry["agent"],
           "CLAUDE_PROJECT_DIR": str(E.workdir(entry, home))}
    acc = entry.get("claude_account") or "shared"
    if acc == "shared":
        env.pop("CLAUDE_CONFIG_DIR", None)
    else:
        env["CLAUDE_CONFIG_DIR"] = str(home / f".claude-{acc}")
    return env


def run_gate(cmd: list[str], tool: str, inp: dict, cwd: Path, env: dict) -> str | None:
    """None = átengedte; különben az ok (tiltás vagy futási hiba — mindkettő piros)."""
    data = json.dumps({"tool_name": tool, "tool_input": inp, "cwd": str(cwd)})
    try:
        r = subprocess.run(cmd, input=data, capture_output=True, text=True, timeout=20, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"a kapu nem fut ({type(e).__name__})"
    if r.returncode != 0:
        return f"a kapu hibával lépett ki ({r.returncode})"
    if '"deny"' not in r.stdout:
        return None
    try:
        return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"][:160]
    except (ValueError, KeyError, TypeError):
        return "megtagadva"


def gate_cmd(home: Path, code: Path | None = None, command: str | None = None) -> list[str]:
    from fleet import titok_telepit as T
    return (command or T.entry(home, code=code)["hooks"][0]["command"]).split()


def gate_denials(entry: dict, home: Path, code: Path | None = None, command: str | None = None) -> list[str]:
    cmd, env = gate_cmd(home, code, command), _env(entry, home)
    wd = E.workdir(entry, home)
    cwd = wd if wd.is_dir() else home
    out = []
    for label, tool, inp in commands(entry, home):
        why = run_gate(cmd, tool, inp, cwd, env)
        if why:
            out.append(f"{label} TILTVA: {why}")
    return out


def probe(agents: list[dict], home: Path, code: Path | None = None, command: str | None = None,
          gate: bool = True) -> dict:
    res = {}
    for e in agents:
        if e.get("status") == "dormant" or e.get("supervision") == "none":
            continue
        red = gate_denials(e, home, code, command) if gate else []
        tok, unk = E.token_problem(e, home)
        res[e["agent"]] = {"red": red + ([tok] if tok else []), "unknown": [unk] if unk else [],
                           "warn": E.sourcing_warnings(e, home)}
    return res


def blocking(res: dict) -> bool:
    return any(r["red"] for r in res.values())


def format_probe(res: dict) -> str:
    lines = []
    for a, r in sorted(res.items()):
        lines.append(f"{'❌' if r['red'] else '✅'} {a}")
        lines += [f"   ! {x}" for x in r["red"]] + [f"   ⚠ {x}" for x in r["warn"]]
        lines += [f"   ? {x}" for x in r["unknown"]]
    return "\n".join(lines) or "essentials: nincs ágens ezen a boxon (registry)"


def local_agents() -> list[dict]:
    """A registry ezen a boxon futó ágensei; registry nélkül üres (és ezt a hívó kiírja)."""
    try:
        from fleet.registry import agents_for_host, local_host
        host = local_host()
        return agents_for_host(host) if host else []
    except Exception as e:  # noqa: BLE001 - a registry hiánya nem omlaszthatja össze a próbát
        print(f"essentials: a registry nem olvasható ({type(e).__name__}) — nincs ágens-próba", file=sys.stderr)
        return []
