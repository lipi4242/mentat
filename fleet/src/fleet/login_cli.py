"""A `fleet login` parancssora (a logika: login.py)."""
from __future__ import annotations
import getpass
import subprocess
import sys

from fleet import login
from fleet.remote import resolve


def _code(a) -> str:
    if a.from_clipboard:
        for cmd in (["pbpaste"], ["wl-paste", "-n"], ["xclip", "-o", "-selection", "clipboard"]):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                continue
            if r.returncode == 0:
                return r.stdout
        raise SystemExit("nincs olvasható vágólap (pbpaste / wl-paste / xclip)")
    if sys.stdin.isatty():
        return getpass.getpass("a böngészőben kapott kód (nem látszik): ")
    return sys.stdin.readline()


def cmd_login(a) -> int:
    entry, tgt = resolve(a.target, ssh=a.ssh)
    account = login.check_account(a.account or (entry or {}).get("claude_account") or "shared")
    model = a.model or (entry or {}).get("model") or "opus"
    where = f"{tgt.label}, fiók: {account}"
    if a.cancel:
        tgt.sh(login.cleanup_script(account), timeout=20)
        print(f"login-session takarítva ({where})")
        return 0
    if not (a.code or a.from_clipboard):
        r = login.start(tgt, account)
        if not r["ok"]:
            print("\n".join(r["notes"]), file=sys.stderr)
            return 1
        print(r["url"])
        if not sys.stdin.isatty():
            again = f"fleet login {a.target}" + (f" --ssh {a.ssh}" if a.ssh else "") + \
                    (f" --account {account}" if a.account else "")
            print(f"nyisd meg az URL-t, majd a kapott kód: `{again} --code` (stdin) vagy "
                  f"`… --code --from-clipboard`; mégsem: `… --cancel`", file=sys.stderr)
            return 3
    r = login.finish(tgt, account, _code(a), model)
    print(f"{where}: " + "\n".join(r["notes"]), file=sys.stdout if r["ok"] else sys.stderr)
    if r["ok"] and entry:
        print(f"következő: `fleet probe {entry['agent']}` — az auth a következő valódi válasz után zöld")
    return 0 if r["ok"] else 1


def add_parser(sub) -> None:
    x = sub.add_parser("login", help="`claude auth login` egy (távoli) boxon: URL ki, kód be stdin-en, "
                                     "1 tokenes próba, takarítás (0 kész · 3 kódra vár · 1 hiba)")
    x.add_argument("target", metavar="ágens|ssh-cél")
    x.add_argument("--ssh", metavar="user@box", help="a box felülírása (régi/hiányzó registry)")
    x.add_argument("--account", help="Claude-fiók (alap: az ágens claude_account-ja, különben shared)")
    x.add_argument("--model", help="a próba modellje (alap: az ágens modellje, különben opus)")
    x.add_argument("--code", action="store_true", help="2. lépés: a kód stdin-ről (vagy --from-clipboard)")
    x.add_argument("--from-clipboard", action="store_true")
    x.add_argument("--cancel", action="store_true", help="a login-session és a fifo takarítása")
    x.set_defaults(fn=cmd_login)
