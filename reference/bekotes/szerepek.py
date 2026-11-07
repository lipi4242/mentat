"""`szerepek`: role files, guard hooks, the /szerep command, roles, e-mail template folder."""
import argparse
import pathlib
import re
import sys

import hely
import szerep_hook
import mentat_roles
import mentat_rules as rules

HERE = pathlib.Path(__file__).resolve().parent
ROLE_CMD = "MENTAT_ROLE=$ARGUMENTS python3 .mentat/bin/mentat_cli.py role --json"
COMMAND = {
    "hu": ("Szerepváltás erre a futásra (a jogosultság az indításkori marad)", "Futtasd a repó gyökeréből:",
           "Ha a kilépési kód 0: olvasd be a kimenet `file` mezőjében álló fájlt, és ettől kezdve "
           "annak a szerepnek a felelőssége és korlátai szerint dolgozz.",
           "Ha nem 0: mondd meg, hogy `$ARGUMENTS` nem telepített szerep, és sorold fel a "
           "`mentat.json` `roles.installed` listáját.",
           "A jogosultság az indításkoré marad: a szerep-őr az induló szerep tiltásait alkalmazza, "
           "ez a parancs semmit nem enged meg. Más jogokhoz indíts újra: `MENTAT_ROLE=<név> claude`."),
    "en": ("Switch role for this run (permissions stay those of the launch)", "Run from the repo root:",
           "If the exit code is 0: read the file named in the `file` field of the output and from "
           "now on work by that role's responsibility and limits.",
           "Otherwise: say that `$ARGUMENTS` is not an installed role and list `roles.installed` "
           "from `mentat.json`.",
           "Permissions stay those of the launch: the role guard keeps applying the launch role's "
           "denials, this command allows nothing. For other permissions relaunch: `MENTAT_ROLE=<name> claude`."),
}
EMPTY = {
    "hu": "Ha `$ARGUMENTS` üres: sorold fel a `mentat.json` `roles.installed` szerepeit, és semmi mást ne tegyél.",
    "en": "If `$ARGUMENTS` is empty: list `roles.installed` from `mentat.json` and do nothing else.",
}
EMAIL_META = {
    "hu": "# E-mail sablonok\n\nnincs jóváhagyott sablon — a szerep csak jelez, nem ír választ.\n",
    "en": "# E-mail templates\n\nno approved template — the role only flags, it does not write a reply.\n",
}
KIADO_MSG = ("a kiado nem lehet fő szerep: %s. A kiadást a kiadó ágens végzi; válassz más "
             "fő szerepet, a kiado mellé telepíthető (--kiado).")


def _settings(repo):
    try:
        szerep_hook.install(repo)
    except ValueError as e:
        raise hely.HelyError(str(e))


def _command(repo, lang):
    desc, intro, ok, bad, perm = COMMAND[lang]
    text = ("---\ndescription: %s\nargument-hint: <szerep>\n---\n\n%s\n\n%s\n\n`%s`\n\n- %s\n- %s\n- %s\n"
            % (desc, EMPTY[lang], intro, ROLE_CMD, ok, bad, perm))
    p = repo / ".claude" / "commands" / "szerep.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _fill(text, business, sources, root):
    text = text.replace("<BUSINESS>", business).replace("<FORRASOK>", sources)
    return text if root == "agy" else re.sub(r"(?<![\w-])agy/", root + "/", text)


def run(a):
    repo = pathlib.Path(a.repo)
    root = hely.brain_root(repo)
    a.lang = a.lang or ("en" if hely.language(repo) == "en" else "hu")
    cfg = hely.config(repo, a.business)
    if cfg is None:
        raise hely.HelyError("nincs %s/business/%s/bekotes.json — előbb a 2. lépés" % (root, a.business))
    names = [a.default] + [x.strip() for x in a.install.split(",") if x.strip()]
    names = list(dict.fromkeys(names + (["kiado"] if a.kiado else [])))
    for n in names:
        if not (rules.ROLE_NAME.fullmatch(n) and (HERE / "szerepek" / ("%s.%s.md" % (n, a.lang))).is_file()):
            raise hely.HelyError("nincs ilyen szerep-sablon: %s (%s)" % (n, a.lang))
    if a.default == "kiado":
        lel = hely.leltar(repo, a.business)
        if lel is None or lel.get("kiado_alapnak") is not True:
            why = "nincs leltar.json" if lel is None else "egy business-repóban van .release-agent/"
            print(KIADO_MSG % why, file=sys.stderr)
            return 1
    _settings(repo)
    mentat_roles.roles(argparse.Namespace(default=a.default, install=",".join(names[1:]), repo=str(repo)))
    business = cfg.get("name") or a.business
    sources = ", ".join(str(s.get("name")) for s in cfg.get("sources") or [] if isinstance(s, dict)) or "-"
    for n in names:
        dest = repo / root / "szerepek" / (n + ".md")
        if dest.exists():
            print("megvan, nem írom felül: %s" % dest.relative_to(repo))
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        tpl = (HERE / "szerepek" / ("%s.%s.md" % (n, a.lang))).read_text(encoding="utf-8")
        dest.write_text(_fill(tpl, business, sources, root), encoding="utf-8")
        print("szerep: %s" % dest.relative_to(repo))
    _command(repo, a.lang)
    meta = repo / root / "sablonok" / "email" / "_meta.md"
    if not meta.exists():
        meta.parent.mkdir(parents=True, exist_ok=True)
        meta.write_text(EMAIL_META[a.lang], encoding="utf-8")
    print("hookok: .claude/settings.json; parancs: .claude/commands/szerep.md")
    return 0
