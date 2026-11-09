#!/usr/bin/env python3
"""Check what the install downloaded before any of it runs. Stdlib only, imports nothing local.

    python3 mentat_verify.py --write release [--freeze]   # the sha256 list into release.json

--freeze (the release cut only): "files_frozen": true; from then on the gate requires the list
to be current (before the cut it checks the shape only). release.json "files" maps every file the
curl step of initialization.md puts in .mentat/bin/ to its sha256 (each there and unchanged; a
.en.md/.hu.md needs one language); "files_known" every tool .py the release ships: any other .py
under .mentat/bin/, or a changed one, is a stop with its name, never a delete. verify(bin_dir) ->
None or the one problem: the first mismatch asks for ONE clean re-download, the second ends the
install; it is never the USER's to waive. The dev tree is not checked; an installed copy without
a list is a stop. Run it with `python3 -I`, the tool folder at the END of sys.path. The list comes
from the same tag as the code: it catches a partial, mixed or changed download, not a replaced
tag (that needs an anchor outside the tag).
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys

PAIR = re.compile(r'-o\s+"?([^"\s]+)"?\s+"(https://[^"]+)"')
TAG = re.compile(r"^https://raw\.githubusercontent\.com/[^/]+/[^/]+/v[^/]+/")
DOCS = ("reference/initialization.md", "reference/initialization.hu.md")
TOOL_DIRS = ("reference/manifest", "reference/bekotes", "reference/web")


def listing(doc):
    """[(path under .mentat/bin/, path in the release tree)] from the curl step of a doc."""
    out = []
    for dest, url in PAIR.findall(doc):
        src = TAG.sub("", url)
        if not dest.startswith(".mentat/bin/") or src == url:
            continue
        dest = dest[len(".mentat/bin/"):]
        names = re.match(r"^(.*)\{([^}]*)\}$", src)
        for name in (names.group(2).split(",") if names else [None]):
            out.append((dest.replace("#1", name), names.group(1) + name) if names else (dest, src))
    return [(d, s) for d, s in out if d != "release.json"]


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def generate(tree):
    tree = pathlib.Path(tree)
    pairs = {d: s for doc in DOCS for d, s in listing((tree / doc).read_text(encoding="utf-8"))}
    return {d: sha(tree / s) for d, s in sorted(pairs.items())}


def is_test_only(name):
    """test_*.py and the _*.py test support (fakes, fixtures, _tmp_run): never on a user's machine."""
    return name.startswith(("test_", "_"))


def known(tree):
    tools = [p for d in TOOL_DIRS for p in sorted((pathlib.Path(tree) / d).glob("*.py"))
             if not is_test_only(p.name)]
    return {p.name: sha(p) for p in sorted(tools, key=lambda p: p.name)}


def _missing(bin_dir, files):
    out = []
    for d in files:
        if (bin_dir / d).is_file():
            continue
        alt = re.match(r"^(.*)\.(en|hu)\.md$", d)
        if alt and any((bin_dir / ("%s.%s.md" % (alt.group(1), x))).is_file() for x in ("en", "hu")):
            continue
        out.append(d)
    return out


GAP = "a letöltés nem sikerült teljesen (hiányzik: %s), ez nem eltérés: próbáld újra ugyanazzal a paranccsal, most vagy később"
ONCE = ("a letöltött fájlok nem egyeznek a kiadással (%s); semmi nincs még telepítve. Töltsd le újra "
        "EGYSZER, ugyanazzal a paranccsal, ugyanarról a címről, és mást ne változtass")
FINAL = ("a letöltés nem egyezik a kiadással (%s), újraletöltés után sem: a telepítés itt megáll, ebben a "
         "mappában a Mentatból semmi nincs telepítve. Mondd el a FELHASZNÁLÓnak egyszerű szavakkal: a "
         "letöltött csomag nem egyezik a kiadottal, ezért nem telepítem. Ez itt nem javítható, és nem a "
         "FELHASZNÁLÓ teendője: ne írd át a release.json-t, ne számolj új ellenőrző összeget, ne futtasd "
         "a fájlokat más úton, és ne építs helyettük saját megoldást (szkript, időzítő, ütemező) — erre a "
         "„csináld, ahogy jónak látod” sem engedély. Tovább csak egy későbbi tiszta újraletöltéssel "
         "(ajánld fel), vagy ha a kiadó javítja a kiadást")


def _strike(bin_dir, what):
    """One clean re-download, then the end (the count is in .mentat/state/, outside the download)."""
    mark = bin_dir.parent / "state" / "verify-failures"
    try:
        n = int(mark.read_text().strip() or 0) + 1 if mark.is_file() else 1
        mark.parent.mkdir(parents=True, exist_ok=True)
        mark.write_text(str(n))
    except (OSError, ValueError):  # cannot count: no second chance
        n = 2
    return (ONCE if n < 2 else FINAL) % what


def _problem(bin_dir, installed):
    meta = bin_dir / "release.json"
    if not meta.is_file():
        return GAP % "release.json" if installed else None
    copies = sorted(p.name for p in bin_dir.glob("release.json?*"))
    if copies:  # an edited list kept next to its original: recomputed sums are not a pass
        return FINAL % ("a kiadás listája itt át lett írva: " + ", ".join(copies))
    try:
        meta = json.loads(meta.read_text(encoding="utf-8"))
    except ValueError:
        meta = {}
    files = meta.get("files") if isinstance(meta, dict) else None
    if not isinstance(files, dict) or not files:
        return "a release.json-ban nincs ellenőrző lista (files): ezt a letöltést nem futtatom"
    tools = meta.get("files_known") or {}
    missing = _missing(bin_dir, files)
    if missing:
        return GAP % ", ".join(missing)  # a network failure is not a mismatch: no strike
    bad = [d for d, h in files.items() if (bin_dir / d).is_file() and sha(bin_dir / d) != h]
    listed = {(bin_dir / d).resolve() for d in files}
    for p in sorted(bin_dir.rglob("*.py")):
        if "__pycache__" not in p.parts and p.resolve() not in listed and tools.get(p.name) != sha(p):
            bad.append(str(p.relative_to(bin_dir)))
    if bad:  # never deleted: the files stay for whoever looks at it
        return _strike(bin_dir, ", ".join(sorted(bad)))
    return None


def verify(bin_dir):
    bin_dir = pathlib.Path(bin_dir)
    installed = bin_dir.name == "bin" and bin_dir.parent.name == ".mentat"
    problem = _problem(bin_dir, installed)
    if problem is None and installed and (bin_dir.parent / "state" / "verify-failures").is_file():
        (bin_dir.parent / "state" / "verify-failures").unlink()
    return problem


def main(argv=None):
    p = argparse.ArgumentParser(prog="mentat_verify.py")
    p.add_argument("--write", metavar="TREE", required=True, help="the release tree (release/)")
    p.add_argument("--freeze", action="store_true", help="the release cut: files_frozen = true")
    a = p.parse_args(argv)
    meta_path = pathlib.Path(a.write) / "release.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["files"] = generate(a.write)
    meta["files_known"] = known(a.write)
    if a.freeze:
        meta["files_frozen"] = True
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("%s: %d files%s" % (meta_path, len(meta["files"]), ", frozen" if a.freeze else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
