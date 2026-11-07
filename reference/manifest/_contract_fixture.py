"""Shared test fixture (tests only): a brain folder with a guest list and a contract proposal.

Every tool run gets a fresh HOME, so nothing outside the temporary folder is read or written.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
GUESTS = ("name,email,status,date,phone\n"
          "Anna,anna@example.com,confirmed,2026-11-03,+36 1 111 1111\n"
          "Bob,bob@example.com,confirmed,2026-11-05,+36 1 222 2222\n"
          "Péter,peter@example.com,declined,2026-11-04,+36 1 333 3333\n"
          "Alice,alice@example.com,confirmed,2026-11-12,+36 1 444 4444\n")
PROPOSAL = {
    "goal": "A list of the confirmed guests for next week's dinner, for the caterer.",
    "fields": ["name", "email", "date"],
    "exclude": {"fields": ["phone"], "records": [{"status": "declined"}], "values": ["+36 1 333"]},
    "audience": {"who": "the confirmed guests only", "from_records": "email", "visibility": "hidden"},
    "window": {"start": "2026-11-02", "end": "2026-11-08", "tz": "Europe/Budapest", "field": "date"},
    "defaults": {"paid": ""},
    "records": {"source": "data/guests.csv", "key": "email", "where": {"status": "confirmed"}},
}
GOOD_CSV = ("name,email,date\n"
            "Anna,anna@example.com,2026-11-03\n"
            "Bob,bob@example.com,2026-11-05\n")


def brain(lang="en"):
    root = pathlib.Path(tempfile.mkdtemp())
    folder = "brain" if lang == "en" else "agy"
    (root / folder).mkdir()
    (root / "data").mkdir()
    (root / "data" / "guests.csv").write_text(GUESTS, encoding="utf-8")
    (root / "mentat.json").write_text(json.dumps(
        {"schema": 1, "agent": {"language": lang}, "components": {"brain": {"root": folder}}}))
    return root


def write(root, name, data):
    path = root / name
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return path


def run(tool, root, *args, stdin=None):
    home = tempfile.mkdtemp()
    env = dict(os.environ, HOME=home)
    return subprocess.run([sys.executable, str(HERE / tool), "--repo", str(root), *args],
                          capture_output=True, text=True, env=env, input=stdin)


def approved(root, proposal=None, cid="dinner"):
    """Draft and approve a contract; returns the contract id."""
    write(root, "proposal.json", proposal or PROPOSAL)
    r = run("mentat_contract.py", root, "draft", cid, "--file", str(root / "proposal.json"))
    assert r.returncode == 0, r.stdout + r.stderr
    r = run("mentat_contract.py", root, "approve", cid, "--quote", "yes, that's it")
    assert r.returncode == 0, r.stdout + r.stderr
    return cid
