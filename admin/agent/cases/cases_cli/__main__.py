"""cases — the cases plugin's agent-side CLI (Python 3.9+ stdlib, vendorable).

Run it as a directory: `python3 .mentat/bin/cases_cli <command>`, from the
agent repo (or `--root`). The backend is `mentat.json` cases.backend:
markdown (<brain>/cases/*.md frontmatter) or admin (the admin API). Same
commands, same output. Exit: 0 ok, 1 refused, 2 manifest diagnostics only,
3 the chosen backend is unavailable (nothing written).

    add --title T --due DATE [--recurrence R] [--next ..] [--set F=V]   one new case, into the backend
        (a first month off the rule stays in the series: --recurrence monthly:10 --due 2026-10-20)
    list [--status open,waiting|all]      due [--days 7 | --until DATE]
    show <id>                             close <id> [--occurrence DATE] [--skip] [--note TEXT] [--next TEXT]
    create --title T [--description ..] [--next ..] [--due DATE | --recurrence R --anchor DATE] [--file PATH]
    update <id> [--title|--description|--status|--next|--due ..]   ("" clears; --due may move the open
           occurrence later inside its period; with --recurrence and no --anchor the anchor follows --due)
           both: --set FIELD=VALUE (repeatable) for the admin's own fields — see `fields`
    fields          admin mode: the instance's own case fields (name, type, allowed values)
    sync            admin mode: context up, the human's changes down, conflicts reported
    propose-scan [--lines N] [--full]     after install: the brain condensed for the proposal (PROPOSE.md)
    export --out DIR                      migrate --to admin|markdown [--dry-run]
    proposal check [--file F]             import --from F [--only id,..]   (.mentat/cases-propose.md)
    status
"""
import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import commands  # noqa: E402
import localday  # noqa: E402
from common import CasesError  # noqa: E402

FLAGS = (("--title", "title"), ("--description", "description"), ("--status", "status"),
         ("--next", "next_action"), ("--due", "due_at"), ("--recurrence", "recurrence"),
         ("--anchor", "anchor_at"))
DUE_HELP = ("the date; with --recurrence the first due date — off the rule it stays in the series "
            "(--recurrence monthly:10 --due 2026-10-20: October on the 20th, then every 10th)")


def own_value(text):
    """`--set amount=12.5` → 12.5, `--set flag=true` → True, `--set x=` → None, else the text."""
    if text == "":
        return None
    try:
        v = json.loads(text)
    except ValueError:
        return text
    return v if isinstance(v, (int, float, bool)) else text


def own_fields(pairs):
    out = {}
    for p in pairs or []:
        k, sep, v = p.partition("=")
        if not sep or not k:
            raise CasesError("--set takes FIELD=VALUE, got %r" % p)
        out[k] = own_value(v)
    return out


def find_root(start):
    for d in [start, *start.parents]:
        if (d / "mentat.json").is_file():
            return d
    raise CasesError("no mentat.json in %s or above — run from the agent repo or pass --root" % start)


def parser():
    p = argparse.ArgumentParser(prog="cases", description=__doc__.split("\n")[0])
    p.add_argument("--root", help="the agent repo (default: nearest mentat.json upwards)")
    p.add_argument("--today", help="pin the date (YYYY-MM-DD); default: today")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("fields")
    sub.add_parser("list").add_argument("--status", default="open,waiting")
    d = sub.add_parser("due")
    d.add_argument("--days", type=int, default=7)
    d.add_argument("--until")
    sub.add_parser("show").add_argument("id")
    for name in ("add", "create", "update"):
        c = sub.add_parser(name)
        if name == "update":
            c.add_argument("id")
        elif name == "create":
            c.add_argument("--file", help="turn this brain file into the case")
        for flag, dest in FLAGS:
            c.add_argument(flag, dest=dest, help=DUE_HELP if dest == "due_at" else None)
        c.add_argument("--set", action="append", metavar="FIELD=VALUE", help="one of the admin's own fields")
    c = sub.add_parser("close")
    c.add_argument("id")
    c.add_argument("--occurrence", help="the date to close (default: the earliest open)")
    c.add_argument("--skip", action="store_true", help="close it as skipped, not done")
    c.add_argument("--done-at")
    c.add_argument("--note")
    c.add_argument("--next", dest="next_step", help="the next step after closing (\"\" clears) — close + update in one")
    sub.add_parser("sync")
    sub.add_parser("export").add_argument("--out", required=True)
    m = sub.add_parser("migrate")
    m.add_argument("--to", required=True, choices=("admin", "markdown"))
    m.add_argument("--dry-run", action="store_true")
    pc = sub.add_parser("proposal").add_subparsers(dest="proposal_cmd", required=True).add_parser("check")
    pc.add_argument("--file", default=None, help="default: .mentat/cases-proposal.json")
    ps = sub.add_parser("propose-scan", help="the brain's notes, condensed to what carries a date or a rhythm")
    ps.add_argument("--lines", type=int, default=3, help="sentences per note (default 3)")
    ps.add_argument("--full", action="store_true", help="every dated sentence, untruncated")
    i = sub.add_parser("import", help="the approved items of a proposal become cases")
    i.add_argument("--from", dest="src", required=True)
    i.add_argument("--only", help="comma-separated item ids (default: all)")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        args.root = Path(args.root).resolve() if args.root else find_root(Path.cwd().resolve())
        args.today = args.today or os.environ.get("CASES_TODAY") or localday.today(args.root)
        if args.cmd == "due" and not args.until:
            args.until = (date.fromisoformat(args.today) + timedelta(days=args.days)).isoformat()
        args.fields = {dest: (getattr(args, dest) or None) for _, dest in FLAGS
                       if getattr(args, dest, None) is not None}
        args.own = own_fields(getattr(args, "set", None))
        out, code = commands.run(args)
    except CasesError as e:
        print("cases: %s" % e, file=sys.stderr)
        return e.code
    if out:
        print(out)
    return code


if __name__ == "__main__":
    sys.exit(main())
