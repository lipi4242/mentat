"""F-41, a flotta prototípusának (elsofel.py) átvétele. Első-fél allowlist: ahova a felhasználó azonosítója mehet (F-41).

    Allow.load(ids) -> Allow ;  .host_ok(host) ;  .tool_ok(tool_name)

Generált: a felhasználó saját e-mail-domainjei (a nyilvános levelezők kivételével), a
beépített alap (GitHub, a Google API-k a saját fióknál, localhost), és a csak a
felhasználó által írható fájl (`~/.mentat/elsofel.txt`): soronként egy host-minta
(`*.pelda.workers.dev`, `fotok.pelda.hu`, a saját box IP-je) vagy egy MCP-eszköz-előtag
(`mcp__claude_ai_Gmail__`). A fájlt az ágens nem írhatja (a kapu védi, mint az
engedélylistát).
"""
import fnmatch
import os

FILE = os.path.expanduser("~/.mentat/elsofel.txt")
PUBLIC_MAIL = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "yahoo.com",
               "icloud.com", "me.com", "proton.me", "protonmail.com", "gmx.com", "gmx.net", "aol.com",
               "freemail.hu", "citromail.hu", "t-online.hu", "users.noreply.github.com"}
BASE_HOSTS = ["localhost", "127.0.0.1", "::1", "[::1]", "github.com", "*.github.com",
              "*.githubusercontent.com", "*.googleapis.com", "accounts.google.com",
              "api.anthropic.com", "claude.ai", "*.claude.ai", "api.cloudflare.com"]
# A saját fiókon dolgozó connectorok: ide a cím a saját fiók része, nem harmadik fél.
BASE_TOOLS = ["mcp__claude_ai_Gmail__", "mcp__claude_ai_Google_Calendar__",
              "mcp__claude_ai_Google_Drive__", "mcp__plugin_telegram_telegram__"]
# Helyi, hálózatot nem érintő eszközök (a beépítettek közül).
LOCAL_TOOLS = {"Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "NotebookRead", "Glob", "Grep",
               "TodoWrite", "Task", "Agent", "SendMessage", "Skill", "ToolSearch", "AskUserQuestion",
               "ExitPlanMode", "TaskStop", "CronCreate", "CronDelete", "CronList", "Monitor", "LSP"}


def _lines(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:  # an odd file never stops the gate
            return [ln.split("#", 1)[0].strip() for ln in f if ln.split("#", 1)[0].strip()]
    except (OSError, ValueError):
        return []


class Allow:
    def __init__(self, hosts, tools):
        self.hosts = [h.lower() for h in hosts]
        self.tools = list(tools)

    @classmethod
    def load(cls, ids=None, path=FILE, gh_logins=None):
        """gh_logins: a saját GitHub-fiók(ok) és szervezet(ek); a `gh -R <owner>/…` csak ezekre első fél."""
        own = [d for d in (ids.domains() if ids else []) if d not in PUBLIC_MAIL]
        extra = _lines(path)
        hosts = BASE_HOSTS + own + ["*." + d for d in own] + [x for x in extra if not x.startswith("mcp__")]
        tools = BASE_TOOLS + [x for x in extra if x.startswith("mcp__")]
        hosts += ["github:" + g.lower() for g in (gh_logins or [])]
        return cls(hosts, tools)

    def host_ok(self, host):
        h = (host or "").lower().rstrip(".").split("@")[-1]
        if h.startswith("ssh:"):  # an ssh target: first party only if listed (or loopback), like any host
            h = h[4:]
        h = h.rsplit(":", 1)[0] if h.count(":") == 1 and not h.startswith("github:") else h
        return bool(h) and any(fnmatch.fnmatchcase(h, p) for p in self.hosts)

    def tool_ok(self, tool):
        return any(tool.startswith(p) for p in self.tools)
