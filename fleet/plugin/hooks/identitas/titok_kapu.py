#!/usr/bin/env python3
"""Titok-kapu: PreToolUse hook, ami nem enged titkot a Claude-kontextusba (H5, 2026-10-29).

    titok_kapu.py --hook     JSON a stdin-en; tiltás esetén deny a stdout-on, különben semmi

Csak TILTHAT. Allow-t és ask-ot soha nem ad: a box headless, és egy engedélyező hook a
Claude Code saját engedélykérését is átugraná. Tilt, ha a hívás
- Read/Edit/Write/NotebookEdit-tel titokfájlt nyit (leltár: ~/.mentat/titkok/leltar.json,
  realpath vagy dev+inode; fájlnév-heurisztika; ~/.claude*/projects/ egésze, csak a saját projekt
  memory/*.md-je szabad),
- Grep-pel titokfájlban, átirat-mappában, ~/.config/<x>/-ben vagy a HOME egészében keres,
- Glob-bal kifejezetten titokfájlt nevez meg,
- Bash-ban olvas, másol, linkel vagy forrásként tölt be ilyet, vagy kiírja a környezetet
  (titok_olvas.py).
Titok-ügyben hibánál is tilt (onFailure: "block" mellett a saját kivételét is deny-ra fordítja).
Az ágens-határ (agens_hatar*.py) hibája viszont NEM zár ki minden ágenst minden eszközből: átenged,
és egy sort ír a ~/.mentat/titkok/hatar-hibak.log-ba (CISO Q5).
"""
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import titok_minta as M  # noqa: E402
import titok_olvas  # noqa: E402

FILE_TOOLS = {"Read": "file_path", "Edit": "file_path", "MultiEdit": "file_path", "Write": "file_path",
              "NotebookEdit": "notebook_path"}
HELP = ("Nevet és helyet a `fleet secrets scan --agent <ágens>` ad (értéket soha); kulcsot átvinni csak "
        "tételes tulajdonosi jóváhagyással lehet: `fleet secrets approve` + `fleet secrets move`. Amit egy "
        "másik ágens kulcsával kell tenni, azt tőle kérd: `fleet ask <fogadó>`. Ne keress kerülőutat "
        "(maszkolás, másolás, symlink, értelmező): a maszkolt kiírás is kiírás.")


def _titkok_dir():
    return os.path.join(M.home(), ".mentat", "titkok")


def _file_tool(tool, inp, cwd, lel):
    p = str(inp.get(FILE_TOOLS[tool]) or "")
    if not p:
        return None
    r = M.resolve(p, cwd)
    if tool != "Read" and r and (r == _titkok_dir() or r.startswith(_titkok_dir() + os.sep)):
        return "a titok-leltár és a jóváhagyások csak a `fleet secrets` eszközzel írhatók"
    why = M.secret(p, cwd, lel)
    return "%s: %s" % (why, os.path.basename(p)) if why else None


def _grep(inp, cwd, lel):
    p = str(inp.get("path") or cwd or os.getcwd())
    r = M.resolve(p, cwd)
    if r is None:
        return None
    g = str(inp.get("glob") or "")
    if g and not M.GLOB.search(os.path.basename(g)) and M.name_hit(os.path.basename(g)):
        return "kulcsfájl-név a szűrőben: %s" % os.path.basename(g)
    if os.path.isfile(r) or not os.path.exists(r):
        why = M.secret(p, cwd, lel)
        return "%s: %s" % (why, os.path.basename(p)) if why else None
    home = M.home()
    if r == home or home.startswith(r.rstrip(os.sep) + os.sep):
        return "a teljes HOME-ban keresne (benne a kulcsok és az átiratok)"
    if M.own_memory(r, cwd):  # a saját projekt auto-memóriája (11-08); a symlinkjeit a _tree nézi
        return M._tree(r, lel, (), cwd)
    if M.in_transcripts(r, cwd) or M.holds_transcripts(r):
        return "átiratokat tartalmazó mappa"
    if any(r == x or x.startswith(r.rstrip(os.sep) + os.sep) for x in
           (os.path.join(home, d) for d in (".config", ".ssh", ".mentat"))):
        return "titok-mappa: %s" % r
    if M.secret_root(r) or M.lel_under_root(lel, r):
        return "titok-mappa: %s" % r
    return None


def _glob(inp, cwd, lel):
    pat = str(inp.get("pattern") or "")
    base = os.path.basename(pat)
    if base and not M.GLOB.search(base) and M.name_hit(base):
        return "kulcsfájl-név a mintában: %s" % base
    full = os.path.join(str(inp.get("path") or cwd or ""), pat)
    return "leltárban (glob)" if M.glob_hit(lel.paths, M.resolve(full, cwd) or "") else None


def decide(tool, inp, cwd, lel=None):
    lel = lel if lel is not None else M.Leltar.load()
    inp = inp if isinstance(inp, dict) else {}
    if tool in FILE_TOOLS:
        return _file_tool(tool, inp, cwd, lel)
    if tool == "Grep":
        return _grep(inp, cwd, lel)
    if tool == "Glob":
        return _glob(inp, cwd, lel)
    if tool == "Bash":
        return titok_olvas.bash(str(inp.get("command", "")), cwd, lel)
    return None


#: Heurisztikus (név- vagy mappa-alapú) tiltás: lehet téves. A téves tiltás kerülőútra tanít
#: (11-07: egy ágens string-összefűzéssel vágta ketté a mezőnevet) — ezért itt bejelentést kérünk.
SUSPECT = ("gyanús", "a mappában", "túl nagy mappa", "a kódban", "a mintában", "a szűrőben", "(glob)",
           "nem elemezhető", "leltárban (mappa")
REPORT = (" Ha ez TÉVES (a fájl/mappa nem titok): NE kerüld meg (összefűzés, másolás, más eszköz) — jelentsd "
          "a tulajdonosnak a pontos parancssal, hogy a kapu javuljon. Rekurzív keresésnél a mappát "
          "kizárhatod: `grep -r --exclude-dir=<mappa> …`.")

#: Az átirat-tiltás SZÁNDÉKOS (11-09): a ~/.claude*/projects/*.jsonl a session teljes szövege,
#: benne minden kiolvasott kulcs és más ágensek beszélgetése — a saját is. Az ok mellé a kiút kell.
TRANSCRIPT = (" Az átirat (~/.claude*/projects/**/*.jsonl, a saját sessioné is) szándékosan zárt: a teljes "
              "beszélgetést tartalmazza, benne minden valaha kiolvasott kulcsot. Amit a korábbi munkából "
              "keresel, azt itt találod: a session memóriája (~/.claude*/projects/<projekt>/memory/*.md), a "
              "motor naplója (<repó>/data/logs/anytime-tick.log), a repó docs/ és git log-ja.")


def deny(reason):
    hint = REPORT if any(s in reason for s in SUSPECT) else ""
    hint += TRANSCRIPT if "átirat" in reason else ""
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": "Titok-kapu: %s. %s%s" % (reason, HELP, hint)}}


def hook(data):
    cwd = data.get("cwd") or os.getcwd()
    try:
        why = decide(data.get("tool_name", ""), data.get("tool_input") or {}, cwd)
    except Exception as e:  # noqa: BLE001 - amit nem értünk, azt nem engedjük át
        return deny("a hívás nem elemezhető (%s), ezért nem dönthető el, nyit-e titkot" % type(e).__name__)
    if why:
        return deny("ez a hívás titkot nyitna meg (%s)" % why)
    why = _hatar(data.get("tool_name", ""), data.get("tool_input") or {}, cwd)
    if why:
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": "Ágens-határ: %s. %s" % why}}
    return None


def _hatar(tool, inp, cwd):
    """(ok, súgó) vagy None. Hibánál átenged és naplóz: egy hibás kiadás ne zárjon ki mindenkit."""
    try:
        import agens_hatar
        import agens_hatar_mod
        import hatar_jel
        merge = hatar_jel.aktiv()
        why = agens_hatar_mod.decide(tool, inp, cwd, merge) or agens_hatar.decide(tool, inp, cwd, merge)
        return (why, agens_hatar.HELP) if why else None
    except Exception as e:  # noqa: BLE001 - az ágens-határ hibája nem titok-ügy
        try:
            import hatar_jel
            hatar_jel.naplo("agens-hatar hiba, atengedve: %s %s" % (tool, type(e).__name__))
        except Exception:  # noqa: BLE001
            pass
        return None


def main(argv):
    if "--hook" not in argv:
        print(__doc__)
        return 2
    try:
        out = hook(json.loads(sys.stdin.read() or "{}"))
    except Exception as e:  # noqa: BLE001 - hibánál nem engedünk át
        out = deny("hiba (%s)" % type(e).__name__)
    if out:
        print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
