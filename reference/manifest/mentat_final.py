#!/usr/bin/env python3
"""mentat_final.py — anything final that goes out (sent, recorded, created) only after a read-back and a yes.

    python3 .mentat/bin/mentat_final.py preview ID --what "<what>" --to TARGET --file PAYLOAD [--require f1,f2] [--exclude a,b]
    python3 .mentat/bin/mentat_final.py approve ID | check ID | after ID --seen "<what you read back from there>"

`preview` prints every recipient and the read-back, and refuses empty mandatory fields (--require)
and excluded recipients (--exclude); the receipt holds the payload's sha256, the target and a
one-time 4-digit code. `approve` counts only when a USER message recorded AFTER the preview
(szerep_prompt.py) holds that code; once used it is spent. The guard lets an outbound POST through
without asking only with that unchanged file, to that target. Exit: 0 ok, 1 not ready, 2 usage.
"""
import argparse
import hashlib
import json
import pathlib
import re
import secrets
import sys
import time

sys.path.append(str(pathlib.Path(__file__).resolve().parent))  # at the END (python3 -I)
import mentat_final_to as to  # noqa: E402

STATE = pathlib.Path(".mentat", "state", "final")
SAID = pathlib.Path(".mentat", "state", "user-said")
FRESH_HOURS = 2


def _receipt(root, rid):
    return root / STATE / ("%s.json" % "".join(c for c in rid if c.isalnum() or c in "-_"))


def _sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def _save(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def _readback(text, doc):
    if isinstance(doc, dict):
        return ["%s: %s" % (k, json.dumps(v, ensure_ascii=False)) for k, v in doc.items()][:40]
    return text.splitlines()[:40] if doc is None else [json.dumps(doc, ensure_ascii=False)[:2000]]


def preview(root, a):
    pay = root / a.file
    text = pay.read_text(encoding="utf-8", errors="replace")
    try:
        doc = json.loads(text)
    except ValueError:
        doc = None
    need = [f for f in (a.require or "").split(",") if f.strip()]
    empty = [f for f in need if not isinstance(doc, dict) or doc.get(f.strip()) in (None, "", [], {})]
    found = to.recipients(doc)
    bad = to.excluded(found, a.exclude)
    if bad:
        print("NOT READY excluded recipient(s) in the payload: %s — take them out, then preview again" % ", ".join(bad))
        return 1
    if empty:
        print("NOT READY empty mandatory field(s): %s — fill the structured field itself (not a note or "
              "free text), then preview again; never send it and correct it afterwards" % ", ".join(empty))
        return 1
    code = "%04d" % secrets.randbelow(10000)
    _save(_receipt(root, a.id), {"id": a.id, "what": a.what, "to": a.to, "file": a.file, "sha256": _sha(pay),
                                 "at": time.time(), "code": code, "approved": None, "after": None})
    print("READ BACK to the USER, all of it, before it goes out — %s → %s:" % (a.what, a.to))
    print("\n".join(to.lines(found) + ["  " + ln for ln in _readback(text, doc)]))
    print("Ask the USER, in their language: \"If it is OK, reply: %s\" — then: mentat_final.py approve %s" % (code, a.id))
    return 0


def _ready(root, rid):
    path = _receipt(root, rid)
    if not path.is_file():
        return None, "no preview for %s: run preview first" % rid
    r = json.loads(path.read_text(encoding="utf-8"))
    pay = root / r["file"]
    if not pay.is_file() or _sha(pay) != r["sha256"]:
        return r, "the payload %s changed since the preview: preview and ask again" % r["file"]
    if time.time() - r["at"] > FRESH_HOURS * 3600:
        return r, "the preview is older than %d hours: preview and ask again" % FRESH_HOURS
    return r, None


def _said_after(root, code, since):
    """The code is in a USER message the hook recorded after the preview (a word of its own)."""
    want = re.compile(r"(?<!\d)%s(?!\d)" % re.escape(str(code or "x")))
    for f in (root / SAID).glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if code and float(e.get("at") or 0) > since and want.search(str(e.get("text") or "")):
                return True
    return False


def main(argv=None):
    p = argparse.ArgumentParser(prog="mentat_final.py")
    p.add_argument("--repo", default=".")
    p.add_argument("cmd", choices=["preview", "approve", "check", "after"])
    p.add_argument("id")
    p.add_argument("--what", default="")
    p.add_argument("--to", help="where it goes (an address, a system): the guard opens only that target")
    p.add_argument("--file")
    p.add_argument("--require")
    p.add_argument("--exclude", help="who must not get it (comma separated): a match stops the preview")
    p.add_argument("--quote")
    p.add_argument("--seen")
    a = p.parse_args(argv)
    root = pathlib.Path(a.repo)
    if a.cmd == "preview":
        if not a.file or not (root / a.file).is_file() or not a.to:
            print("usage: preview ID --what … --to TARGET --file PAYLOAD (the exact content and where it goes)")
            return 2
        return preview(root, a)
    r, why = _ready(root, a.id)
    if a.cmd == "approve":
        if why or r.get("approved") or not _said_after(root, r.get("code"), r["at"]):
            print("NOT APPROVED: " + (why or ("already used: preview again" if r.get("approved") else
                  "no USER reply with the code after the preview — show the preview and wait for their reply")))
            return 1
        r["approved"] = {"code": r.get("code"), "quote": (a.quote or "").strip(), "at": time.time()}
        _save(_receipt(root, a.id), r)
        print("APPROVED %s — it may go out now; afterwards: mentat_final.py after %s --seen \"…\"" % (a.id, a.id))
        return 0
    if why or not r.get("approved"):
        print("NOT READY: " + (why or "not approved: read it back and ask the USER"))
        return 1
    if a.cmd == "check":
        print("OK %s approved by the USER's reply, payload unchanged" % a.id)
        return 0
    if not (a.seen or "").strip():
        print("usage: after ID --seen \"<what the far side shows now, read back from there>\"")
        return 2
    r["after"] = {"seen": a.seen.strip(), "at": time.time()}
    _save(_receipt(root, a.id), r)
    print("DONE %s — tell the USER what is there now: %s" % (a.id, a.seen.strip()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
