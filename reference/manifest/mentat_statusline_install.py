#!/usr/bin/env python3
"""Install the Mentat status line (project .claude/settings.json) and the /whoami and /mentat commands.

    python3 mentat_statusline_install.py [--force] [--repo .]

A statusLine the USER already has (project, local or user level) is never replaced without --force,
which the agent passes only after the USER said yes. Either way the decision is recorded in
.mentat/statusline.json. /whoami and /mentat (.claude/commands/) are written only if missing or ours.
"""
import argparse
import datetime
import json
import os
import pathlib
import sys
for _s in (sys.stdin, sys.stdout, sys.stderr):  # Windows: a pipe is the ANSI code page, not UTF-8
    getattr(_s, "reconfigure", lambda **k: None)(encoding="utf-8", errors="replace")

MARK = "mentat_statusline.py"
COMMAND = 'python3 "${CLAUDE_PROJECT_DIR:-.}/.mentat/bin/mentat_statusline.py"'
WHOAMI = {
    "hu": "---\ndescription: Ki vagy, melyik modellen, melyik mappában és ágon: a státuszsor tartalma (Desktopon is)\n"
          "allowed-tools: Bash(python3 .mentat/bin/mentat_statusline.py --whoami)\n---\n\n"
          "Futtasd a repó gyökeréből: `python3 .mentat/bin/mentat_statusline.py --whoami`\n\n"
          "A kimenetét szó szerint mutasd meg. Ha nincs benne `Modell:` sor, tedd hozzá annak a modellnek a nevét, "
          "amelyen most futsz. Semmi mást ne írj hozzá.\n",
    "en": "---\ndescription: Who you are, on which model, in which folder and branch: the status line, also on Desktop\n"
          "allowed-tools: Bash(python3 .mentat/bin/mentat_statusline.py --whoami)\n---\n\n"
          "Run from the repo root: `python3 .mentat/bin/mentat_statusline.py --whoami`\n\n"
          "Show its output verbatim. If it has no `Model:` line, add the name of the model you are running on. "
          "Add nothing else.\n",
}
MENTAT = {
    "hu": "---\ndescription: Mentat súgó: mit tud ez az ágens, kezdőfeladatok; /mentat status, /mentat todo\n"
          "allowed-tools: Bash(python3 .mentat/bin/mentat_help.py:*)\n---\n\n"
          "Futtasd a repó gyökeréből: `python3 .mentat/bin/mentat_help.py $ARGUMENTS`\n\n"
          "A kimenetét szó szerint mutasd meg. Semmi mást ne írj hozzá.\n",
    "en": "---\ndescription: Mentat help: what this agent can do, first tasks; /mentat status, /mentat todo\n"
          "allowed-tools: Bash(python3 .mentat/bin/mentat_help.py:*)\n---\n\n"
          "Run from the repo root: `python3 .mentat/bin/mentat_help.py $ARGUMENTS`\n\n"
          "Show its output verbatim. Add nothing else.\n",
}
KEPT = ("a meglévő statusLine marad (%s); a Mentat státuszsora csak a FELHASZNÁLÓ igenje után kerül a helyére: "
        "python3 .mentat/bin/mentat_statusline_install.py --force")


def _read(path):
    try:
        got = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except ValueError:
        raise ValueError("%s nem olvasható JSON" % path)
    if not isinstance(got, dict):
        raise ValueError("%s nem JSON-objektum" % path)
    return got


def user_settings(env=os.environ, home=None):
    base = env.get("CLAUDE_CONFIG_DIR") or str(pathlib.Path(home or pathlib.Path.home()) / ".claude")
    return pathlib.Path(base) / "settings.json"


def foreign(repo, env=os.environ, home=None):
    """(path, command) of a statusLine that is not ours, highest level first; or None."""
    for path in (repo / ".claude" / "settings.local.json", repo / ".claude" / "settings.json", user_settings(env, home)):
        try:
            line = _read(path).get("statusLine")
        except ValueError:
            continue
        if isinstance(line, dict) and MARK not in str(line.get("command", "")):
            return path, str(line.get("command", ""))
    return None


def _record(repo, decision, where, command):
    p = repo / ".mentat" / "statusline.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes((json.dumps({"decision": decision, "where": str(where), "command": command,
                             "at": datetime.date.today().isoformat()}, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def install(repo, force=False, env=os.environ, home=None):
    repo, log = pathlib.Path(repo), []
    other = foreign(repo, env, home)
    if other and not force:
        _record(repo, "kept", *other)
        log.append(KEPT % other[0])
    else:
        path = repo / ".claude" / "settings.json"
        settings = _read(path)
        if settings.get("statusLine") != {"type": "command", "command": COMMAND, "padding": 0}:
            settings["statusLine"] = {"type": "command", "command": COMMAND, "padding": 0}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((json.dumps(settings, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
            log.append("statusLine: .claude/settings.json")
        if other:
            _record(repo, "replaced-with-yes", *other)
    lang = (_read(repo / "mentat.json").get("agent") or {}).get("language")
    for name, texts, mark in (("whoami.md", WHOAMI, MARK), ("mentat.md", MENTAT, "mentat_help.py")):
        cmd = repo / ".claude" / "commands" / name
        if not cmd.exists() or mark in cmd.read_text(encoding="utf-8"):
            text = texts["en" if lang == "en" else "hu"]
            if not cmd.exists() or cmd.read_text(encoding="utf-8") != text:
                cmd.parent.mkdir(parents=True, exist_ok=True)
                cmd.write_bytes(text.encode("utf-8"))
                log.append("parancs: .claude/commands/%s" % name)
        else:
            log.append("a .claude/commands/%s nem a Mentaté, nem írtam át" % name)
    return log


def scaffold_lines(root):
    try:
        return ["status  %s" % x for x in install(root)]
    except ValueError as e:
        return ["WARNING %s - the status line is not installed" % e]


def main(argv=None):
    p = argparse.ArgumentParser(prog="mentat_statusline_install.py")
    p.add_argument("--force", action="store_true", help="only after the USER said yes")
    p.add_argument("--repo", default=".")
    a = p.parse_args(argv)
    try:
        print("\n".join(install(a.repo, a.force)) or "statusLine: változatlan")
    except ValueError as e:
        print("HIBA: %s; nem írtam át." % e)
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
