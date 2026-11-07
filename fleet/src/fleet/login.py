"""`fleet login <ágens|ssh-cél>` — `claude auth login` egy távoli boxon, kézi tmux-babrálás nélkül.

2026-10-29: két ágens napok óta „Login expired"-ben állt. A gyógyítás kézzel: tmux-session
a boxon, a `claude auth login` stdin-je egy fifo (`exec 3<>fifo`: írva-olvasva nyitva, így
nem ér EOF-et, amíg a kód meg nem jön), a pane-ből az URL ki, a kód a fifo-ba be, utána egy
1 tokenes próba. Itt ugyanez két lépésben, mert az URL-t ember nyitja meg:

  fleet login <cél>                       → csak az URL (TTY-n utána rejtett kódbekérés)
  fleet login <cél> --code [--from-clipboard]   → a kód stdin-ről / vágólapról a fifo-ba,
                                             „Login successful" + próba, takarítás
  fleet login <cél> --cancel              → takarítás

A kód sosem kerül argv-be, naplóba, kimenetbe: ssh-n stdin-en megy, és ha a pane-t ki
kell írni (hiba), a kód előtte ki van takarva.
"""
from __future__ import annotations
import json
import re
import shlex
import time

from fleet.remote import Target

URL = re.compile(r"https://[^\s\"'<>]+")
EXIT = re.compile(r"FLEET-LOGIN-EXIT=(\d+)")
OK_RE = re.compile(r"login successful|logged in as|successfully logged in", re.I)
UNSET = "env -u CLAUDE_CODE_OAUTH_TOKEN -u ANTHROPIC_API_KEY -u CLAUDE_API_KEY "


def session(account: str) -> str:
    return "fleet-login-" + account


def _dir(account: str) -> str:
    return '"$HOME/.cache/fleet-login/%s"' % account


def _cfg(account: str) -> str:
    return "" if account == "shared" else 'CLAUDE_CONFIG_DIR="$HOME/.claude-%s" ' % account


def check_account(account: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", account or ""):
        raise ValueError(f"érvénytelen fióknév: {account!r}")
    return account


def start_script(account: str) -> str:
    s, d = session(account), _dir(account)
    inner = 'exec 3<>%s/in; %s%sclaude auth login <&3; echo FLEET-LOGIN-EXIT=$?; sleep 900' % (
        d, _cfg(account), UNSET)
    return ("set -e; d=%s; tmux kill-session -t =%s 2>/dev/null || true; rm -rf \"$d\"; "
            "mkdir -p -m 700 \"$d\"; mkfifo -m 600 \"$d/in\"; "
            "tmux new-session -d -s %s -x 400 -y 60 %s") % (d, s, s, shlex.quote(inner))


def capture_script(account: str) -> str:
    return "tmux capture-pane -p -J -t =%s -S -300" % session(account)


def send_script(account: str) -> str:
    return "cat > %s/in" % _dir(account)        # a kód stdin-en jön, nem argv-ben


def probe_script(account: str, model: str) -> str:
    return "%s%sclaude -p --model %s --output-format json 'Reply with OK'" % (
        _cfg(account), UNSET, shlex.quote(model))


def cleanup_script(account: str) -> str:
    return "tmux kill-session -t =%s 2>/dev/null; rm -rf %s; true" % (session(account), _dir(account))


def login_url(pane: str) -> str | None:
    """Pure: a bejelentkezési URL a pane-ből (a -J a tördelt sort összefűzi)."""
    urls = URL.findall(pane)
    pick = [u for u in urls if "oauth" in u or "authorize" in u] or urls
    return pick[-1].rstrip(".,)") if pick else None


def redact(text: str, secret: str) -> str:
    return text.replace(secret, "***") if secret else text


def probe_models(stdout: str) -> tuple[bool, list[str]]:
    """Pure: a `claude -p --output-format json` eredményéből (sikerült-e, modelUsage kulcsai)."""
    try:
        j = json.loads(stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return False, []
    return (not j.get("is_error") and j.get("subtype", "success") == "success",
            sorted((j.get("modelUsage") or {}).keys()))


def _poll(tgt: Target, account: str, until, timeout: float, sleep, clock) -> str:
    t0, pane = clock(), ""
    while True:
        pane = tgt.sh(capture_script(account), timeout=20).stdout or ""
        if until(pane) or clock() - t0 >= timeout:
            return pane
        sleep(2)


def start(tgt: Target, account: str, *, timeout: float = 60, sleep=time.sleep, clock=time.time) -> dict:
    check_account(account)
    r = tgt.sh(start_script(account), timeout=30)
    if r.returncode != 0:
        return {"ok": False, "notes": [f"a login-session nem indult (kód {r.returncode}): {r.stderr.strip()[-300:]}"]}
    pane = _poll(tgt, account, lambda p: login_url(p) or EXIT.search(p), timeout, sleep, clock)
    url = login_url(pane)
    if not url:
        tgt.sh(cleanup_script(account), timeout=20)
        return {"ok": False, "notes": ["nem jött URL a pane-be:", pane.strip()[-600:]]}
    return {"ok": True, "url": url}


def finish(tgt: Target, account: str, code: str, model: str, *, timeout: float = 90,
           sleep=time.sleep, clock=time.time) -> dict:
    check_account(account)
    code = code.strip()
    try:
        if not code:
            return {"ok": False, "notes": ["üres kód"]}
        r = tgt.sh(send_script(account), stdin=code + "\n", timeout=20)
        if r.returncode != 0:
            return {"ok": False, "notes": [f"a kód nem jutott el a fifo-ba (kód {r.returncode}) — "
                                           f"fut még a login-session? Újra: `fleet login` (kód nélkül)"]}
        pane = _poll(tgt, account, lambda p: OK_RE.search(p) or EXIT.search(p), timeout, sleep, clock)
        m = EXIT.search(pane)
        if not OK_RE.search(pane) or (m and m.group(1) != "0"):
            return {"ok": False, "notes": ["a login nem sikerült; a pane vége (a kód kitakarva):",
                                           redact(pane, code).strip()[-600:]]}
        p = tgt.sh(probe_script(account, model), timeout=120)
        ok, models = probe_models(p.stdout or "")
        note = (f"1 tokenes próba: OK, modelUsage: {', '.join(models) or '?'}" if ok and p.returncode == 0 else
                f"Login successful, de a próba bukott (kód {p.returncode}) — `fleet probe` és a unit tokenje "
                f"(claude-auth.env) felülírhatja a credential-t")
        return {"ok": ok and p.returncode == 0, "models": models, "notes": ["Login successful", note]}
    finally:
        tgt.sh(cleanup_script(account), timeout=20)
