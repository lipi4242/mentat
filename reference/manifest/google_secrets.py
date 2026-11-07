"""The one place for the Google secrets: `.secrets/google/` (0700), every file 0600, git-ignored.

    client.json   the OAuth client (Desktop app) the USER downloaded from the Google Cloud console
    token.json    the sign-in (access + refresh token), written by mentat_google_auth.py
    pending.json  a remote sign-in waiting for its second step (expires in 10 minutes)

The connector note `<brain>/connectors/google.md` is generated from what is really there.
"""
import datetime
import os
import pathlib
import subprocess

from mentat_brain import settings

REL = ".secrets/google"


class SecretsError(Exception):
    pass


def folder(root):
    return pathlib.Path(root) / REL


def ensure(root):
    """Create the folder, make sure git ignores it and does not track anything in it."""
    root = pathlib.Path(root)
    d = folder(root)
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d.parent, 0o700)
    os.chmod(d, 0o700)
    ign = root / ".gitignore"
    lines = ign.read_text(encoding="utf-8").splitlines() if ign.exists() else []
    if not {".secrets/", ".secrets", "/.secrets/"} & set(lines):
        ign.write_text("\n".join(lines + [".secrets/"]) + "\n", encoding="utf-8")
    try:
        tracked = subprocess.run(["git", "-C", str(root), "ls-files", "--", ".secrets"],
                                 capture_output=True, text=True).stdout.strip()
    except FileNotFoundError:
        tracked = ""
    if tracked:
        raise SecretsError("STOP: %s is tracked by git (%s). Remove it from git first "
                           "(`git rm --cached -r .secrets`) and make a new client secret in the "
                           "Google Cloud console, because it may already be in the history."
                           % (REL, tracked.splitlines()[0]))
    return d


def write(path, text):
    path = pathlib.Path(path)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


NOTE = """---
type: connector
name: google
status: connected
auth_location: {rel}/token.json
tags: [google]
---

**Connects to:** Google ({services}), signed in on {day}.

**Auth + setup:** the OAuth client is `{rel}/client.json`, the sign-in `{rel}/token.json`
(both 0600, git-ignored; values never in notes or chat). Renew: `python3 .mentat/bin/mentat_google_auth.py login`.

**Available operations:** only through `python3 .mentat/bin/mentat_google.py` (calendar create/update,
gmail send, drive/sheets share, sheets write, read) — every change is checked against an approved
contract (`mentat_contract.py`) and read back. Steps: `reference/google.md`.

**Quirks / known limits:** scopes granted: {scopes}. A consent screen in "Testing" status lets a
sign-in live for 7 days; then sign in again.
"""


def connector_note(root, services, scopes):
    _lang, brain, _ = settings(pathlib.Path(root), None)
    d = pathlib.Path(root) / brain / "connectors"
    d.mkdir(parents=True, exist_ok=True)
    path = d / "google.md"
    path.write_text(NOTE.format(rel=REL, services=", ".join(services), scopes=", ".join(scopes),
                                day=datetime.date.today().isoformat()), encoding="utf-8")
    meta = d / "_meta.md"
    old = meta.read_text(encoding="utf-8") if meta.exists() else "# connectors\n"
    if "(google.md)" not in old:
        meta.write_text(old + ("" if old.endswith("\n") else "\n") + "- [Google](google.md) - connector\n",
                        encoding="utf-8")
    return path
