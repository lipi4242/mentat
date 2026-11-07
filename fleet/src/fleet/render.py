"""Pure systemd --user unit renderer. No I/O.

A sablon a registry-bejegyzésből tölt ki. Ami ma KÉZZEL volt a unitokban
(`--remote-control`, a strict MCP-konfig, a saját env-fájl, a promptra váró
startup), az itt a szabály — ezért nem tud csendben kiesni egy újratelepítéskor.
"""
from __future__ import annotations

import re

from fleet.registry import SHARED_ACCOUNT

#: Ami a renderelt unitba kerül, az systemd- ÉS shell-értelmezésen megy át.
#: Ezért nem escape-elünk, hanem TILTUNK: a loop_cmd és az azonosítók csak
#: ártalmatlan karaktereket tartalmazhatnak (Codex F1-review).
_SAFE_CMD = re.compile(r"^[A-Za-z0-9 /:_.,=-]+$")
_SAFE_PATH = re.compile(r"^[A-Za-z0-9/_.%-]+$")


def validate_for_render(entry: dict) -> list[str]:
    """Pure: miért NEM renderelhető ez a bejegyzés (üres = rendben)."""
    out = []
    for key in ("agent", "session", "rc_name"):
        if not re.match(r"^[a-z][a-z0-9-]{0,39}$", entry.get(key, "") or ""):
            out.append(f"{key} nem slug: {entry.get(key)!r}")
    if not _SAFE_PATH.match(entry.get("workdir", "") or ""):
        out.append(f"workdir tiltott karaktert tartalmaz: {entry.get('workdir')!r}")
    if not re.match(r"^[A-Za-z0-9_.-]+$", entry.get("env_file", "") or ""):
        out.append(f"env_file nem fájlnév: {entry.get('env_file')!r}")
    if not re.match(r"^[A-Za-z0-9.-]+$", entry.get("model", "opus") or "opus"):
        out.append(f"model tiltott karaktert tartalmaz: {entry.get('model')!r}")
    lc = entry.get("loop_cmd")
    if lc and not _SAFE_CMD.match(lc):
        out.append(f"loop_cmd tiltott karaktert tartalmaz (engedett: betű, szám, szóköz / : _ . , = -): {lc!r}")
    acc = entry.get("claude_account") or SHARED_ACCOUNT
    if not re.match(r"^[a-z0-9-]+$", acc):
        out.append(f"claude_account nem slug: {acc!r}")
    desc = entry.get("description") or ""
    if any(c in desc for c in "\n%"):
        out.append("description nem tartalmazhat sortörést vagy %-jelet")
    return out

#: A plugin-poller (telegram-plugin) ELLEN. Üres MCP-lista, szigorúan: az
#: ágens egyetlen MCP-szervert sem indít, a Telegramot a híd viszi. Egy éles
#: ágensnél 2026-08 óta bizonyítottan 0 db 409.
STRICT_MCP = "--strict-mcp-config --mcp-config %h/.config/fleet/mcp-empty.json"


def claude_flags(entry: dict) -> str:
    """Pure: a claude bináris kapcsolói (a --resume és a --model nélkül)."""
    # --disallowedTools AskUserQuestion (FL-03): the bridge presses Enter after every injected
    # line, so a question menu would be answered for the user; the ban is enforced, not prompted.
    parts = ["--dangerously-skip-permissions", f"--remote-control {entry['rc_name']}",
             "--disallowedTools AskUserQuestion"]
    if entry.get("strict_mcp", True):
        parts.append(STRICT_MCP)
    return " ".join(parts)


def account_env(entry: dict) -> str:
    """Pure: a fiók-környezet sora, vagy üres. A `shared` a közös ~/.claude."""
    acc = entry.get("claude_account") or SHARED_ACCOUNT
    if acc == SHARED_ACCOUNT:
        return ""
    return f"Environment=CLAUDE_CONFIG_DIR=%h/.claude-{acc}\n"


def account_shell(entry: dict) -> str:
    """Pure: a fiók beállítása a pane launcherén BELÜL. A közös tmux-szerver
    globális környezete egy másik ágens fiókját is hozhatná; ezért a shared
    explicit unset, a nevesített explicit export (Codex F1-review)."""
    acc = entry.get("claude_account") or SHARED_ACCOUNT
    if acc == SHARED_ACCOUNT:
        return "unset CLAUDE_CONFIG_DIR;"
    return f"export CLAUDE_CONFIG_DIR=$HOME/.claude-{acc};"


def render_unit(entry: dict, *, template: str, fleet_root: str = "%h/src/mentat/fleet") -> str:
    """Pure: a teljes unit szövege a registry-bejegyzésből.

    A session-gate NEM itt van: az fleet-szabály, drop-inben él, hogy a
    kézzel írt unitokra is vonatkozzon (lásd install.install_drop_in).
    """
    problems = validate_for_render(entry)
    if problems:
        raise ValueError("nem renderelhető: " + "; ".join(problems))
    agent = entry["agent"]
    workdir = entry["workdir"]
    session = entry["session"]
    pre = ""
    post = ""
    if entry.get("proactive"):
        # Az előző futás heartbeatje félrevezető: ha a folyamat meghalt, a
        # fájl ott marad, és a felügyelet élőnek látná a halottat.
        pre = f"ExecStartPre=/bin/rm -f {workdir}/data/state/orchestrator-heartbeat.json\n"
        loop_cmd = entry.get("loop_cmd") or ""
        if loop_cmd:
            # A promptra várunk, nem fix sleep-re: 2026-08-03-án a 25 s kevés
            # volt, a billentyűk a boot-képernyőre estek, az ágens NÉMÁN nem tickelt.
            post = (f"ExecStartPost={fleet_root}/bin/agent-startup-seed.sh "
                    f"{session} '{loop_cmd}'\n")
    out = template
    out = out.replace("@@EXECSTARTPRE@@", pre)
    out = out.replace("@@EXECSTARTPOST@@", post)
    out = out.replace("@@ACCOUNT_ENV@@", account_env(entry))
    out = out.replace("@@ACCOUNT_SHELL@@", account_shell(entry))
    out = out.replace("@@DESCRIPTION@@", entry.get("description") or agent)
    out = out.replace("@@AGENT@@", agent)
    out = out.replace("@@SESSION@@", session)
    out = out.replace("@@WORKDIR@@", workdir)
    out = out.replace("@@MODEL@@", entry.get("model") or "opus")
    out = out.replace("@@ENV_FILE@@", f"%h/.config/{agent}/{entry['env_file']}")
    out = out.replace("@@FLAGS@@", claude_flags(entry))
    if "@@" in out:
        raise ValueError(f"unsubstituted placeholder remains in rendered unit for {agent!r}")
    return out
