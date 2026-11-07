"""The final-action receipts (mentat_final.py) for the guard: an approved payload may go out.

approved_send(root, words, wd) -> True: the outbound command sends a file (`-d @f`, `--data-binary
@f`, `--json @f`, `-T f`, `--body-file f`, or a plain path) whose sha256 matches a receipt in
.mentat/state/final/ that was approved (the quote in a USER message after the preview, see
mentat_final.py) within FRESH_HOURS, AND every address in the command is that receipt's target
(host + path). Then the "post" gate does not ask again. An inline payload is undecidable: the
gate stays as it is. touched(root, tool, inp, cwd) -> path: the receipts or the recorded USER
messages (.mentat/state/user-said/) or .mentat/model.env (sourced by the box unit) are written by the agent (deny); the tools write them in their
own process, which no command line shows. Known limit: integrity, not authenticity.
"""
import hashlib
import json
import os
import pathlib
import time
import urllib.parse

FINAL = os.path.join(".mentat", "state", "final")
SAID = os.path.join(".mentat", "state", "user-said")
MODEL_ENV = os.path.join(".mentat", "model.env")  # the box unit sources it at restart: mentat_model.py writes it
FRESH_HOURS = 2


def _approved(root):
    out = {}
    for f in pathlib.Path(root, FINAL).glob("*.json"):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(r, dict) and r.get("approved") and r.get("to") and \
                time.time() - float(r.get("at") or 0) < FRESH_HOURS * 3600:
            out[r.get("sha256")] = r["to"]
    return out


def _where(url):
    u = urllib.parse.urlsplit(url if "://" in url else "https://" + url)
    return (u.hostname or "").lower(), u.path.rstrip("/")


def approved_send(root, words, wd):
    urls = [w for w in words[1:] if "://" in w]
    shas = None
    for w in words[1:]:
        p = w[1:] if w.startswith("@") else w.split("=", 1)[-1].lstrip("@")
        path = p if os.path.isabs(p) else os.path.join(wd or str(root), p)
        if not p or not os.path.isfile(path):
            continue
        shas = _approved(root) if shas is None else shas
        try:
            to = shas.get(hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest())
        except OSError:
            continue
        if to and urls and all(_where(u) == _where(to) for u in urls):
            return True
    return False


def touched(root, tool, inp, cwd):
    from szerep_kapu import _written
    from szerep_kint import real, under
    mine = [real(os.path.join(root, d)) for d in (FINAL, SAID, MODEL_ENV)]
    return next((p for p in _written(tool, inp, cwd) if any(under(real(p), m) for m in mine)), None)
